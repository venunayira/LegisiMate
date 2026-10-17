"""Single-user loopback server; run with python -m misofish.server."""
import argparse
import fcntl
import json
import mimetypes
import os
import re
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from openai import APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError
from pydantic import ValidationError

from .casework import CaseFacts, CaseWorkbench, assess_timeline, export_brief, read_authority
from .core import (Agent, Config, DEFAULT_AGENT_COUNT, DISCLAIMER, MAX_AGENTS, MAX_ROUNDS, Model,
                   generate_grounded_report, markdown, prepare_population)
from .court import court_calls, run_court
from .engine import Engine
from .graph import GraphStore, build_graph
from .legal import legal_status, retrieve_legal_dossier
from .town import run_town, town_calls

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_STATES = {"preparing", "running", "reporting"}


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id), kind TEXT NOT NULL, payload TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS events_by_run ON events(run_id, id)")

    def save(self, run):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?)", (run["id"], json.dumps(run)))

    def append_event(self, run_id, kind, data, run=None):
        with closing(sqlite3.connect(self.path)) as db, db:
            if run is not None:
                db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?)", (run_id, json.dumps(run)))
            cursor = db.execute("INSERT INTO events (run_id,kind,payload) VALUES (?,?,?)", (run_id,kind,json.dumps(data)))
            return cursor.lastrowid

    def events(self, run_id, after=0):
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute("SELECT id,kind,payload FROM events WHERE run_id=? AND id>? ORDER BY id LIMIT 200", (run_id,after)).fetchall()
        return [{"id": event_id, "kind": kind, "data": json.loads(payload)} for event_id,kind,payload in rows]

    def view(self, run_id):
        """Read snapshot and draft replay under one SQLite read transaction."""
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN")
            row = db.execute("SELECT snapshot FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError("Run not found.")
            run = json.loads(row[0])
            rows = db.execute("SELECT id,kind,payload FROM events WHERE run_id=? ORDER BY id",(run_id,)).fetchall()
        drafts, report_draft = {}, {}
        room = run.get('room')
        for event_id,kind,payload in rows:
            data = json.loads(payload)
            if kind == 'room_state':
                room = data
            elif kind == "turn_start":
                drafts[data["turn_id"]] = data
            elif kind == "turn_delta":
                drafts[data["turn_id"]] = data
            elif kind in {"turn_complete","turn_abort"}:
                drafts.pop(data.get("turn_id", data.get("action",{}).get("turn_id")), None)
            elif kind == "report_delta":
                report_draft.update(data)
            elif kind in {"terminal","report_complete"}:
                drafts.clear(); report_draft.clear()
        run["event_cursor"] = rows[-1][0] if rows else 0
        run["drafts"] = list(drafts.values()) if run["status"] in ACTIVE_STATES else []
        run["report_draft"] = report_draft if run["status"] == "reporting" else {}
        run['room'] = room
        return run

    def get(self, run_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute("SELECT snapshot FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise KeyError("Run not found.")
        return json.loads(row[0])

    def list(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute("SELECT snapshot FROM runs ORDER BY rowid DESC").fetchall()
        return [{k: run[k] for k in ("id", "created_at", "status", "config", "round", "model")}
                for (snapshot,) in rows for run in [json.loads(snapshot)]]

    def recover(self):
        for summary in self.list():
            if summary["status"] in ACTIVE_STATES:
                run = self.view(summary["id"])
                for key in ('drafts','report_draft','event_cursor'):
                    run.pop(key,None)
                run.update(status="interrupted", error="Server restarted. Saved rounds are intact; create a new run to continue.")
                if run.get('room'):
                    run['room']['encounters'] = []
                    for person in run['room']['people']:
                        person['state'] = 'idle'
                    self.append_event(run['id'],'room_state',run['room'],run=run)
                self.append_event(run['id'], 'terminal', {"status":"interrupted"}, run=run)


class Manager:
    def __init__(self, store, model, engine=None):
        self.store = store
        self.model = model
        self.engine = engine or Engine()
        self.graph_store = GraphStore(store.path)
        self.lock = threading.RLock()
        self.active = None
        self.casework = CaseWorkbench(store.path, model, lock=self.lock, legacy_active=lambda: self.active)
        self.worker = None
        self.stop = threading.Event()
        self.changed = threading.Condition()
        self.stream_slots = threading.BoundedSemaphore(8)

    def emit(self, run_id, kind, data, run=None):
        with self.changed:
            self.store.append_event(run_id, kind, data, run)
            self.changed.notify_all()

    def create(self, data):
        config = Config.model_validate(data)
        with self.lock:
            self._available(config)
            run = {"id": uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
                   "config": config.model_dump(), "model": getattr(self.model, "name", "test-fixture"),
                   "status": "preparing", "round": 0, "agents": [], "actions": [], "report": None,
                   "usage": {"input_tokens": 0, "output_tokens": 0}, "error": None,
                   "version": 2, "model_calls": 0, "worker_calls": 0,
                   "storage": str(self.store.path.parent / "engine" / uuid.uuid4().hex)}
            self.emit(run['id'],'state', {"status":"preparing","round":0},run)
            self._launch(run, preparing=True)
            return run

    def _available(self, config=None):
        if self.casework.active:
            raise RuntimeError("A case analysis is active. Stop it before starting a legacy experiment.")
        if self.active:
            raise RuntimeError("One simulation is already active. Wait or cancel it before starting another.")
        if self.model is None:
            raise RuntimeError("Set OPENAI_API_KEY in your terminal and restart the server.")
        if (config is None or config.platform_mode not in {"town", "court"}) and not self.engine.available()["available"]:
            raise RuntimeError("The supported OASIS worker is unavailable. Run the worker setup in README.")
        if config and config.platform_mode == "both" and not self.engine.twitter_available():
            raise RuntimeError("Twitter recommender weights are unavailable. Download them using README, or explicitly choose Reddit + Shared Room.")

    def start(self, run_id):
        with self.lock:
            run = self.store.get(run_id)
            if run["status"] != "ready":
                raise RuntimeError("Only a prepared, ready simulation can start.")
            if run.get("version") != 2:
                raise RuntimeError("Legacy runs are inspectable, not resumable. Prepare a new graph-grounded run.")
            config = Config.model_validate(run["config"])
            self._available(config)
            agents = [Agent.model_validate(a) for a in run["agents"]]
            if len(agents) != config.agent_count or [a.id for a in agents] != list(range(1, len(agents) + 1)):
                raise ValueError("Stored roster does not match the configured population and stable IDs.")
            if run["model"] != getattr(self.model, "name", "test-fixture"):
                raise RuntimeError("Model changed since preparation; create a new run.")
            interviews = len(agents) * (2 if config.platform_mode == "both" else 1)
            remaining = config.model_call_budget - run.get("model_calls", 0)
            if config.platform_mode in {"town", "court"}:
                needed = (court_calls(config, agents) if config.platform_mode == "court"
                          else town_calls(config, [agent.id for agent in agents])) + 1
                if remaining < needed:
                    raise RuntimeError(f"These conversations need {needed} model calls but only {remaining} remain. "
                                       "Prepare a new run with a larger budget, fewer ticks or shorter conversations.")
            elif remaining < interviews + 2:
                raise RuntimeError(f"The remaining call budget must cover at least one decision, {interviews} final interviews "
                                   "and the report. Prepare a new run with a larger budget.")
            run["status"] = "running"
            self.emit(run['id'],'state', {"status":"running","round":run['round']},run)
            self._launch(run, preparing=False)
            return run

    def _launch(self, run, preparing):
        self.active = run["id"]
        self.stop = threading.Event()
        # Copy the snapshot: HTTP replies and worker mutations never share a mutable dictionary.
        self.worker = threading.Thread(target=self._execute, args=(json.loads(json.dumps(run)), preparing), daemon=True)
        self.worker.start()

    def cancel(self, run_id):
        with self.lock:
            if self.active != run_id:
                self.store.get(run_id)
                raise RuntimeError("This simulation is not active.")
            self.stop.set()
        return {"message": "Cancellation requested; waiting for in-flight calls. No further rounds will start."}

    def _execute(self, run, preparing):
        before = dict(self.model.usage)
        previous = dict(run["usage"])
        before_calls = getattr(self.model, "calls", 0)
        previous_calls = run.get("model_calls", 0)
        worker_calls = 0
        worker_tokens = {"input_tokens": 0, "output_tokens": 0}
        run_lock = threading.RLock()
        def checkpoint():
            run["usage"] = {key: previous[key] + self.model.usage[key] - before[key] + worker_tokens[key] for key in previous}
            run["model_calls"] = previous_calls + getattr(self.model, "calls", 0) - before_calls + worker_calls
            self.store.save(run)
        def emit(kind,data):
            nonlocal worker_calls
            with run_lock:
                if kind == "effect":
                    if any(action.get("effect_id") == data["effect_id"] for action in run["actions"]):
                        return
                    content = data["data"].get("content") or data["data"].get("message") or data["data"].get("response") or ""
                    interview = data["kind"] == "interview"
                    shift = re.match(r"\W*(unchanged|softened|hardened|reversed)\b\W*", content, re.I) if interview else None
                    if shift:
                        content = content[shift.end():]
                    reply_effect = data["data"].get("reply_to_effect")
                    parent = next((action for action in run["actions"] if (reply_effect and action.get("effect_id") == reply_effect)
                        or (data["kind"] == "create_comment" and action.get("platform") == data["platform"]
                            and action.get("engine_kind") == "create_post"
                            and action.get("data", {}).get("post_id") == data["data"].get("post_id"))), None)
                    reply = parent["id"] if parent else None
                    action = {**data, "id": len(run["actions"]) + 1, "engine_kind": data["kind"],
                        "kind": "interview" if interview else "reply" if reply else "post" if content else "pass", "text": content,
                        "round": data["tick"], "reply_to": reply, "stance": "neutral"}
                    if interview:
                        action["shift"] = shift.group(1).lower() if shift else None
                    self.graph_store.append_effect(run["id"], data)
                    run["actions"].append(action)
                    checkpoint()
                    self.emit(run["id"], "turn_complete", {"action": action, "usage": run["usage"]}, run)
                    return
                if kind == "worker_usage":
                    worker_calls = data["model_calls"]
                    run["worker_calls"] = worker_calls
                    worker_tokens.update({key: data.get(key, 0) for key in worker_tokens})
                    run["worker_usage"] = worker_tokens.copy()
                if kind == "tick_complete" and data.get("successful", True):
                    run["round"] = data["tick"]
                if kind == "groups_formed":
                    run.setdefault("groups", []).append(data)
                if kind in {"decision_start", "decision_complete", "decision_error"}:
                    for person in run.get("room", {}).get("people", []):
                        if person["id"] == data["agent_id"]:
                            person["state"] = "thinking" if kind == "decision_start" else "idle"
                checkpoint()
                self.emit(run['id'],kind,data,run)
        run["stage"] = "configuration"
        try:
            config = Config.model_validate(run["config"])
            self.model.call_limit = before_calls + config.model_call_budget - previous_calls
            if preparing:
                if config.platform_mode == "court" and not config.source.strip():
                    try:
                        dossier = retrieve_legal_dossier(config.scenario)
                        run["config"]["source"] = dossier["source"]
                        config = Config.model_validate(run["config"])
                    except FileNotFoundError:
                        pass
                run["stage"] = "graph_preparation"
                graph = build_graph(config, self.model, cancelled=self.stop.is_set, emit=emit)
                self.graph_store.save(run["id"], graph)
                run["graph"] = graph
                run["stage"] = "population_preparation"
                run["agents"] = [agent.model_dump() for agent in prepare_population(config, graph, self.model,
                    cancelled=self.stop.is_set, emit=emit, graph_store=self.graph_store, run_id=run["id"])]
                run["room"] = {"version": 2, "owner": "reddit", "encounters": [],
                    "people": [{"id": agent["id"], "state": "idle"} for agent in run["agents"]]}
                run["status"] = "cancelled" if self.stop.is_set() else "ready"
                checkpoint()
                self.emit(run['id'],'state', {"status":run['status'],"agents":run['agents'],"room":run['room']},run)
            else:
                agents = [Agent.model_validate(a) for a in run["agents"]]
                remaining = config.model_call_budget - previous_calls - 1
                if remaining < 1:
                    raise RuntimeError("model_call_budget")
                run["stage"] = "simulation"
                worker_run = {**run, "config": {**run["config"], "model_call_budget": remaining}}
                result = (run_court(config, agents, self.model, emit, self.stop.is_set) if config.platform_mode == "court"
                          else run_town(config, agents, self.model, emit, self.stop.is_set) if config.platform_mode == "town"
                          else self.engine.run(worker_run, emit, self.stop.is_set))
                checkpoint()
                if self.stop.is_set() or result["status"] == "cancelled":
                    run["status"] = "cancelled"
                elif result["status"] != "completed":
                    run["status"] = "failed"
                    code = result.get("error_code")
                    allowed = {"tool_schema_invalid", "tool_rejected", "target_not_observed", "model_call_budget",
                               "model_decision_failed", "worker_interrupted", "worker_initialization"}
                    run["error_code"] = code if code in allowed else "worker_failed"
                    run["error"] = f"Engine stopped ({run['error_code']}). Committed effects are saved; no automatic retry."
                else:
                    run["status"] = "reporting"
                    run["stage"] = "reporting"
                    self.model.call_limit = getattr(self.model, "calls", 0) + config.model_call_budget - run["model_calls"]
                    checkpoint()
                    emit('report_start',{"status":"reporting"})
                    report = generate_grounded_report(config, self.graph_store, run["id"], agents,
                        run["actions"], self.model, emit=emit, cancelled=self.stop.is_set)
                    if self.stop.is_set():
                        run["status"] = "cancelled"
                    else:
                        run["report"] = report.model_dump()
                        run["status"] = "completed"
                        self.emit(run['id'],'report_complete',{"report":run['report']},run)
        except Exception as exc:
            run["status"] = "cancelled" if self.stop.is_set() else "failed"
            if isinstance(exc, AuthenticationError):
                message = "OpenAI rejected credentials. Check OPENAI_API_KEY and restart."
            elif isinstance(exc, RateLimitError):
                message = "OpenAI rate/quota limit reached. Check billing and limits; no automatic retry was made."
            elif isinstance(exc, APITimeoutError):
                run["error_code"] = "provider_timeout"
                message = "Model request timed out. Saved graph and committed effects remain intact; no automatic retry was made."
            elif isinstance(exc, APIError):
                message = "OpenAI request failed. Check model, endpoint and connectivity; saved rounds remain intact."
            elif isinstance(exc, ValidationError):
                # Pydantic inputs/messages may contain private source; expose only schema labels.
                fields = {"name", "role", "perspective", "text", "kind", "stance", "reply_to",
                          "summary", "conclusion", "findings", "claim", "action_ids", "limitations",
                          "agreements", "disagreements", "open_questions"}
                issues = sorted({
                    f"{'.'.join(str(part) for part in issue['loc'] if part in fields) or 'output'}: {issue['type']}"
                    for issue in exc.errors(include_input=False, include_context=False, include_url=False)
                })
                message = "Model output failed validation (" + "; ".join(issues[:4]) + "). Finished turns are saved; no automatic retry was made."
            elif isinstance(exc, ValueError):
                messages = {
                    "graph_quote_mismatch": "Source graph quotation did not match the supplied text. No actors were started.",
                    "graph_entity_type": "Source graph used an unknown entity type. No actors were started.",
                    "graph_relationship_type": "Source graph used an unknown relationship type. No actors were started.",
                    "graph_edge_target": "Source graph referenced an unknown relationship endpoint. No actors were started.",
                    "graph_node_identity": "Source graph repeated an entity identity. No actors were started.",
                    "population_shortfall": "Not enough eligible source actors. Reduce the population or explicitly choose fictional archetypes.",
                    "population_count_mismatch": "Persona generation returned the wrong batch size. The graph is saved; no actors were started.",
                    "population_duplicate_name": "Persona generation repeated a name. The graph is saved; no actors were started.",
                    "population_entity_mismatch": "Persona generation changed an assigned identity. The graph is saved; no actors were started.",
                    "population_evidence_mismatch": "Persona generation cited an unknown source entity. The graph is saved; no actors were started.",
                    "population_evidence_missing": "Persona generation omitted its assigned source evidence. The graph is saved; no actors were started.",
                }
                code = str(exc).partition(":")[0]
                run["error_code"] = code if code in messages else "invalid_model_output"
                message = messages.get(code, "Invalid or incomplete model output. The run stopped safely; committed effects remain intact.")
            elif isinstance(exc, RuntimeError) and str(exc) == "model_call_budget":
                run["error_code"] = "model_call_budget"
                message = "Model-call budget exhausted. Committed work is saved; no automatic retry was made."
            else:
                message = "Simulation failed. Saved rounds remain intact."
            run["error"] = message
            print(json.dumps({"event": "run_failed", "run_id": run["id"], "stage": run.get("stage"),
                "error_code": run.get("error_code"), "exception_type": type(exc).__name__}), flush=True)
        finally:
            try:
                if run.get("room"):
                    for person in run["room"]["people"]:
                        person["state"] = "idle"
                checkpoint()
                emit('terminal',{"status":run['status'],"error":run['error'],"usage":run['usage'],
                    "stage":run.get("stage"),"error_code":run.get("error_code")})
            finally:
                with self.lock:
                    self.active = None


def make_server(manager, port=8000):
    asset_dir = ROOT / "web" / "assets"
    assets = {"/assets/" + path.name: path for path in asset_dir.iterdir() if path.is_file()} if asset_dir.exists() else {}
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_):
            pass

        def reply(self, code, value, content_type="application/json; charset=utf-8"):
            content = json.dumps(value).encode() if content_type.startswith("application/json") else value
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'sha256-pgvDUBa4IjFA2yuSJ2cqcyxmNYJMborsd0ORcRv9vw8='; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(content)

        def trusted(self, mutation=False):
            host = self.headers.get("Host", "")
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if host not in allowed:
                self.reply(403, {"error": "Untrusted Host header."})
                return False
            if mutation and (self.headers.get("Origin", f"http://{host}") != f"http://{host}" or
                             self.headers.get("Sec-Fetch-Site") == "cross-site"):
                self.reply(403, {"error": "Cross-origin mutation blocked."})
                return False
            return True

        def stream_events(self, run_id):
            manager.store.get(run_id)
            try:
                raw = self.headers.get('Last-Event-ID') or parse_qs(urlsplit(self.path).query).get('after',['0'])[0]
                cursor = int(raw)
                if cursor < 0:
                    raise ValueError()
            except ValueError:
                self.reply(400,{"error":"Invalid event cursor."})
                return
            if not manager.stream_slots.acquire(blocking=False):
                self.reply(503,{"error":"Too many live viewers. Close another tab and retry."})
                return
            try:
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Connection','close')
                self.end_headers()
                self.wfile.write(b': connected\n\n'); self.wfile.flush()
                while True:
                    with manager.changed:
                        events = manager.store.events(run_id,cursor)
                        if not events:
                            if manager.store.get(run_id)['status'] not in ACTIVE_STATES:
                                self.wfile.write(b'event: end\ndata: {}\n\n'); self.wfile.flush()
                                return
                            manager.changed.wait(5)
                    for event in events:
                        cursor = event['id']
                        self.wfile.write(f"id: {cursor}\nevent: update\ndata: {json.dumps(event)}\n\n".encode())
                    if not events:
                        self.wfile.write(b': heartbeat\n\n')
                    self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError,TimeoutError):
                pass
            finally:
                manager.stream_slots.release()

        def do_GET(self):
            if not self.trusted():
                return
            path = urlsplit(self.path).path
            try:
                if path == "/api/config":
                    self.reply(200, {"max_agents": MAX_AGENTS, "max_rounds": MAX_ROUNDS,
                                     "default_agents": DEFAULT_AGENT_COUNT,
                                     "worker": manager.engine.available(), "twitter_available": manager.engine.twitter_available(),
                                     "legal_corpus": legal_status(),
                                     "model": getattr(manager.model, "name", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
                                     "configured": manager.model is not None, "disclaimer": DISCLAIMER})
                elif path == "/api/runs":
                    self.reply(200, manager.store.list())
                elif path == "/api/cases":
                    self.reply(200, manager.casework.list())
                elif path.startswith("/api/authorities/"):
                    source = read_authority(path.removeprefix("/api/authorities/"))
                    if source is None:
                        raise KeyError("Source not found.")
                    self.reply(200, source)
                elif path.startswith("/api/cases/"):
                    parts = path.strip("/").split("/")
                    if len(parts) == 3:
                        self.reply(200, manager.casework.get(parts[2]))
                    elif len(parts) == 4 and parts[3] == "export":
                        self.reply(200, export_brief(manager.casework.get(parts[2])).encode(), "text/markdown; charset=utf-8")
                    else:
                        self.reply(404, {"error": "Not found."})
                elif path.startswith("/api/runs/"):
                    parts = path.strip("/").split("/")
                    if len(parts) == 3:
                        self.reply(200, manager.store.view(parts[2]))
                    elif len(parts) == 4 and parts[3] == 'events':
                        self.stream_events(parts[2])
                    elif len(parts) == 4 and parts[3] == "export":
                        self.reply(200, markdown(manager.store.get(parts[2])).encode(), "text/markdown; charset=utf-8")
                    else:
                        self.reply(404, {"error": "Not found."})
                elif path in {"/", "/legacy", "/app.js", "/style.css", "/room.js", "/room.css", "/cases.js", "/cases.css"}:
                    asset = "cases.html" if path == "/" else "index.html" if path == "/legacy" else path[1:]
                    mime = "text/html" if asset.endswith('.html') else "text/javascript" if asset.endswith('.js') else "text/css"
                    self.reply(200, (ROOT / "web" / asset).read_bytes(), mime + "; charset=utf-8")
                elif path in assets:
                    self.reply(200, assets[path].read_bytes(), mimetypes.guess_type(path)[0] or "application/octet-stream")
                else:
                    self.reply(404, {"error": "Not found."})
            except (KeyError, FileNotFoundError):
                self.reply(404, {"error": "Not found."})

        def do_POST(self):
            if not self.trusted(mutation=True):
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self.reply(415, {"error": "Use application/json."})
                return
            if self.headers.get("Transfer-Encoding") or "Content-Length" not in self.headers:
                self.reply(411, {"error": "A fixed Content-Length is required."})
                return
            try:
                length = int(self.headers["Content-Length"])
            except ValueError:
                self.reply(400, {"error": "Invalid Content-Length."})
                return
            if not 0 < length <= 150000:
                self.reply(413, {"error": "Request must contain 1..150000 bytes."})
                return
            try:
                body = json.loads(self.rfile.read(length))
                path = urlsplit(self.path).path.strip("/").split("/")
                if path == ["api", "runs"]:
                    self.reply(202, manager.create(body))
                elif path == ["api", "cases"]:
                    if manager.active:
                        raise RuntimeError("A legacy experiment is active. Stop it before analysing a case.")
                    self.reply(202, manager.casework.create(body))
                elif path == ["api", "cases", "timeline"]:
                    if not isinstance(body, dict) or set(body) != {"facts", "as_of"} or not isinstance(body["as_of"], str):
                        raise ValueError("Invalid timeline request.")
                    self.reply(200, assess_timeline(CaseFacts.model_validate(body["facts"]), body["as_of"]))
                elif len(path) == 4 and path[:2] == ["api", "cases"] and path[3] in {"cancel", "delete"}:
                    if body != {}:
                        raise ValueError("Use an empty JSON object.")
                    self.reply(200, getattr(manager.casework, path[3])(path[2]))
                elif path == ["api", "legal", "retrieve"]:
                    if not isinstance(body, dict) or set(body) - {"scenario", "domain"}:
                        raise ValueError("Invalid legal retrieval request.")
                    scenario = body.get("scenario", "")
                    domain = body.get("domain", "auto")
                    if not isinstance(scenario, str) or len(scenario) > 2000 or domain not in {"auto", "ni_act_138", "contract_breach", "constitution", "both"}:
                        raise ValueError("Invalid legal retrieval parameters.")
                    self.reply(200, retrieve_legal_dossier(scenario, domain))
                elif len(path) == 4 and path[:2] == ["api", "runs"] and path[3] in {"start", "cancel"}:
                    if body != {}:
                        raise ValueError("Start/cancel body must be an empty JSON object.")
                    self.reply(202, getattr(manager, path[3])(path[2]))
                else:
                    self.reply(404, {"error": "Not found."})
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.reply(400, {"error": "Invalid UTF-8 JSON."})
            except ValidationError:
                message = ("Review the case details, dates and consent. Case text must contain 25..6000 characters; dates must be valid, chronological YYYY-MM-DD values."
                           if path[:2] == ["api", "cases"] else
                           f"Invalid configuration. Scenario: 1..2000 characters; source: up to 20000; population: integer 1..{MAX_AGENTS}; ticks: integer 1..{MAX_ROUNDS}. Check run settings and use no extra fields.")
                self.reply(422, {"error": message})
            except ValueError:
                message = ("Invalid case request or dates. Use YYYY-MM-DD; completed-event dates cannot be after the assessment date."
                           if path[:2] == ["api", "cases"] else "Invalid request or roster.")
                self.reply(422, {"error": message})
            except KeyError:
                self.reply(404, {"error": "Run not found."})
            except RuntimeError as exc:
                self.reply(409, {"error": str(exc)})
            except TimeoutError:
                self.reply(408, {"error": "Request read timed out."})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="Local graph-grounded OASIS simulation (macOS/Linux).")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    # One process per data directory protects the global agent cap and restart recovery.
    with (args.data_dir / "server.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "Another Misofish server already owns this data directory.\n")
        store = Store(args.data_dir / "runs.db")
        store.recover()
        model = None
        if os.getenv("OPENAI_API_KEY"):
            model = Model(OpenAI(timeout=float(os.getenv("MISOFISH_MODEL_TIMEOUT", "180")), max_retries=0),
                os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        manager = Manager(store, model)
        server = make_server(manager, args.port)
        print(f"Misofish: http://127.0.0.1:{server.server_port} · default {DEFAULT_AGENT_COUNT} personas · deployment ceiling {MAX_AGENTS}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            manager.stop.set()
            manager.casework.stop.set()
            if manager.worker:
                manager.worker.join()
            if manager.casework.worker:
                manager.casework.worker.join()
            server.server_close()
            if model:
                model.client.close()


if __name__ == "__main__":
    main()
