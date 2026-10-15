import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

from misofish.core import Config, PopulationBatch
from misofish.server import Manager, Store, main, make_server
from test_core import FakeModel, FixtureEngine, roster


class ServerTests(unittest.TestCase):
    def test_graph_quote_failure_has_safe_specific_diagnostic(self):
        original = self.manager.model.generate
        def bad_quote(*args, **kwargs):
            if args[0].__name__ == "GraphBatch":
                raise ValueError("graph_quote_mismatch")
            return original(*args, **kwargs)
        self.manager.model.generate = bad_quote
        run = self.manager.create({"scenario": "Change"})
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        self.assertEqual(result.get("error_code"), "graph_quote_mismatch")
        self.assertEqual(result.get("stage"), "graph_preparation")
        self.assertIn("quotation", result["error"])

    def test_provider_timeout_is_specific_and_preserves_prepared_graph(self):
        import httpx
        from openai import APITimeoutError
        original = self.manager.model.generate
        def timed_out(*args, **kwargs):
            if args[0].__name__ == "PopulationBatch":
                raise APITimeoutError(request=httpx.Request("POST", "http://fixture/v1/responses"))
            return original(*args, **kwargs)
        self.manager.model.generate = timed_out
        run = self.manager.create({"scenario": "Change"})
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        self.assertEqual(result.get("error_code"), "provider_timeout")
        self.assertEqual(result.get("stage"), "population_preparation")
        self.assertIn("timed out", result["error"])
        self.assertTrue(result["graph"]["nodes"])

    def test_launcher_model_timeout_is_configurable_without_retries(self):
        server = Mock(server_port=8765)
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch.dict(os.environ, {"OPENAI_API_KEY": "local-fixture", "MISOFISH_MODEL_TIMEOUT": "240"}), \
                patch("sys.argv", ["misofish", "--data-dir", self.tmp.name]), \
                patch("misofish.server.OpenAI") as client, \
                patch("misofish.server.make_server", return_value=server):
            main()
        client.assert_called_once_with(timeout=240.0, max_retries=0)

    def test_population_identity_failure_has_specific_safe_diagnostic(self):
        original = self.manager.model.generate
        def mismatched(*args, **kwargs):
            batch = original(*args, **kwargs)
            if args[0].__name__ == "PopulationBatch":
                batch = PopulationBatch.model_validate(batch.model_dump())
                batch.agents[0].profile.entity_id = "PRIVATE_FIXTURE"
            return batch
        self.manager.model.generate = mismatched
        run = self.manager.create({"scenario": "Change", "agent_count": 2})
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result.get("error_code"), "population_entity_mismatch")
        self.assertEqual(result.get("stage"), "population_preparation")
        self.assertIn("identity", result["error"])
        self.assertNotIn("PRIVATE_FIXTURE", result["error"])
        self.assertEqual(result["agents"], [])
        self.assertTrue(result["graph"]["nodes"])
        terminal = self.store.events(run["id"])[-1]["data"]
        self.assertEqual(terminal.get("error_code"), "population_entity_mismatch")

    def test_missing_twitter_weights_stops_before_any_provider_call(self):
        with patch.object(self.manager.engine, "twitter_available", return_value=False, create=True):
            with self.assertRaisesRegex(RuntimeError, "Twitter"):
                self.manager.create({"scenario": "Change", "platform_mode": "both"})
        self.assertEqual(self.manager.model.payloads, [])

    def test_grounded_shortfall_is_actionable_and_safe(self):
        run = self.manager.create({"scenario": "Change", "agent_count": 2, "population_mode": "grounded"})
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result.get("error_code"), "population_shortfall")
        self.assertIn("source actors", result["error"])

    def test_new_runs_have_durable_graph_and_versioned_engine_contract(self):
        run = self.ready()
        self.assertEqual(run.get("version"), 2)
        self.assertEqual(run["graph"]["status"], "complete")
        self.assertTrue(run["agents"][0]["profile"]["goal"])

    def test_prepared_population_above_ten_does_not_use_legacy_room_cap(self):
        run = self.manager.create({"scenario": "Change", "agent_count": 13})
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["agents"]), 13)

    def test_sqlite_connections_are_closed_after_each_operation(self):
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.execute.return_value.fetchone.return_value = ('{"id": "test"}',)
        connection.execute.return_value.fetchall.return_value = []
        with patch("misofish.server.sqlite3.connect", return_value=connection):
            store = Store(Path(self.tmp.name) / "closed.db")
            store.save({"id": "test"})
            self.assertEqual(store.get("test")["id"], "test")
            store.list()
        self.assertEqual(connection.close.call_count, 4)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "runs.db")
        model = FakeModel()
        self.manager = Manager(self.store, model, engine=FixtureEngine(model))

    def tearDown(self):
        worker = self.manager.worker
        if worker:
            self.manager.stop.set()
            worker.join(10)
            self.assertFalse(worker.is_alive(), 'Worker must finish before removing its database.')
        self.tmp.cleanup()

    def ready(self):
        run = self.manager.create({"scenario": "Change", "agent_count": 2, "rounds": 2})
        self.manager.worker.join(3)
        return self.store.get(run["id"])

    def test_prepare_run_and_storage_reload(self):
        run = self.ready()
        self.assertEqual(run["status"], "ready")
        self.manager.start(run["id"])
        self.manager.worker.join(3)
        result = Store(self.store.path).get(run["id"])
        self.assertEqual((result["status"], result["round"], len(result["actions"])), ("completed", 2, 4))
        self.assertEqual(result["report"]["findings"][0]["action_ids"], [1])
        self.assertEqual(len(self.store.list()), 1)

    def test_fixture_workload_accounts_for_graph_and_profile_preparation(self):
        run = self.manager.create({"scenario": "Change", "agent_count": 10, "rounds": 10})
        self.manager.worker.join(3)
        self.manager.start(run["id"])
        self.manager.worker.join(10)
        self.assertFalse(self.manager.worker.is_alive(), 'Maximum workload must complete within the functional-test budget.')
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["agents"]), 10)
        self.assertEqual(len(result["actions"]), 100)
        self.assertEqual(len(self.manager.model.payloads), 106)

    def test_cancel_during_round_retains_first_round_without_report(self):
        run = self.ready()
        entered, release = threading.Event(), threading.Event()
        original = self.manager.model.generate
        def blocked(output_type, instructions, payload, max_tokens, **kwargs):
            if payload.get("round") == 2:
                entered.set()
                release.wait(3)
            return original(output_type, instructions, payload, max_tokens, **kwargs)
        self.manager.model.generate = blocked
        self.manager.start(run["id"])
        self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(RuntimeError):
                self.manager.start(run["id"])
            self.manager.cancel(run["id"])
        finally:
            release.set()
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "cancelled")
        self.assertGreaterEqual(result["round"], 1)
        self.assertIsNone(result["report"])
        self.assertFalse(any("actions" in p for p in self.manager.model.payloads))

    def test_missing_credentials_and_report_failure_stop_safely(self):
        unconfigured = Manager(self.store, None)
        with self.assertRaises(RuntimeError):
            unconfigured.create({"scenario": "Change"})
        run = self.ready()
        original = self.manager.model.generate
        def invalid_report(output_type, instructions, payload, max_tokens, **kwargs):
            result = original(output_type, instructions, payload, max_tokens, **kwargs)
            if "actions" in payload:
                result.findings[0].action_ids = [999]
            return result
        self.manager.model.generate = invalid_report
        self.manager.start(run["id"])
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        self.assertEqual((result["status"], result["round"]), ("failed", 2))
        self.assertIsNone(result["report"])

    def test_single_global_job_and_cancel(self):
        entered, release = threading.Event(), threading.Event()
        model = FakeModel()
        generate = model.generate
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(3)
            return generate(*args, **kwargs)
        model.generate = blocked
        self.manager.model = model
        run = self.manager.create({"scenario": "Change", "agent_count": 10})
        self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(RuntimeError):
                self.manager.create({"scenario": "Another"})
            with self.assertRaises(RuntimeError):
                self.manager.start(run["id"])
            self.manager.cancel(run["id"])
        finally:
            release.set()
        self.manager.worker.join(3)
        self.assertEqual(self.store.get(run["id"])["status"], "cancelled")
        self.assertIsNone(self.manager.active)

    def test_model_failure_preserves_completed_round_and_safe_error(self):
        run = self.ready()
        original = self.manager.model.generate
        def fail_second(output_type, instructions, payload, max_tokens, **kwargs):
            if payload.get("round") == 2:
                raise RuntimeError("secret-token-private-source")
            return original(output_type, instructions, payload, max_tokens, **kwargs)
        self.manager.model.generate = fail_second
        self.manager.start(run["id"])
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        self.assertEqual((result["status"], result["round"], len(result["actions"])), ("failed", 1, 2))
        self.assertIsNone(result["report"])
        self.assertNotIn("secret", result["error"])

    def test_recovery_does_not_replay_calls_or_destroy_actions(self):
        run = self.ready()
        run.update(status="running", actions=[{"id": 1}], round=1)
        self.store.save(run)
        self.store.recover()
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["actions"], [{"id": 1}])
        with self.assertRaises(RuntimeError):
            self.manager.start(run["id"])

    def test_final_interviews_are_recorded_with_self_reported_shift(self):
        run = self.ready()
        class InterviewEngine(FixtureEngine):
            def run(self, run, emit, cancelled):
                result = super().run(run, emit, cancelled)
                emit("effect", {"effect_id": "reddit:trace:98", "agent_id": 2, "platform": "reddit", "tick": 2,
                    "kind": "create_comment", "visibility": "public", "outcome": "committed", "simulation_minute": 60,
                    "data": {"comment_id": 9, "post_id": 1, "content": "Who pays for it?"}})
                emit("effect", {"effect_id": "reddit:trace:99", "agent_id": 1, "platform": "reddit", "tick": 2,
                    "kind": "interview", "visibility": "interview", "outcome": "committed", "simulation_minute": 60,
                    "data": {"prompt": "Final view?", "response": "[SOFTENED] I now accept a phased plan."}})
                return result
        self.manager.engine = InterviewEngine(self.manager.model)
        self.manager.start(run["id"])
        self.manager.worker.join(3)
        result = self.store.get(run["id"])
        interview, comment = result["actions"][-1], result["actions"][-2]
        self.assertEqual((comment["kind"], comment["reply_to"]), ("reply", 1))
        self.assertEqual(result["status"], "completed")
        self.assertEqual((interview["kind"], interview["shift"], interview["text"]),
                         ("interview", "softened", "I now accept a phased plan."))
        self.assertEqual(self.manager.model.payloads[-1]["final_interviews"][0]["id"], interview["id"])

    def test_start_requires_budget_for_final_interviews_and_report(self):
        run = self.ready()
        run["model_calls"] = run["config"]["model_call_budget"] - 5
        self.store.save(run)
        with self.assertRaisesRegex(RuntimeError, "final interviews"):
            self.manager.start(run["id"])
        self.assertEqual(self.store.get(run["id"])["status"], "ready")
        run["model_calls"] -= 1
        self.store.save(run)
        self.manager.start(run["id"])
        self.manager.worker.join(3)

    def test_town_conversations_regroup_every_tick_and_report_final_views(self):
        from misofish.town import town_calls
        run = self.manager.create({"scenario": "Change", "agent_count": 5, "rounds": 2, "platform_mode": "town"})
        self.manager.worker.join(3)
        self.manager.start(run["id"])
        self.manager.worker.join(10)
        result = self.store.get(run["id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual([entry["tick"] for entry in result["groups"]], [1, 2])
        for entry in result["groups"]:
            self.assertEqual(sorted(member for group in entry["groups"] for member in group["members"]), [1, 2, 3, 4, 5])
        said = [action for action in result["actions"] if action["platform"] == "town"]
        self.assertEqual(len(said), town_calls(Config.model_validate(result["config"]), [1, 2, 3, 4, 5]))
        self.assertTrue(all(action["view"] and action["shift"] for action in said))
        self.assertTrue(any(action["reply_to"] for action in said))
        self.assertEqual(len(self.manager.model.payloads[-1]["final_interviews"]), 5)

    def test_town_start_requires_budget_for_every_planned_turn(self):
        run = self.manager.create({"scenario": "Change", "agent_count": 4, "rounds": 2, "platform_mode": "town"})
        self.manager.worker.join(3)
        run = self.store.get(run["id"])
        run["model_calls"] = run["config"]["model_call_budget"] - 5
        self.store.save(run)
        with self.assertRaisesRegex(RuntimeError, "model calls"):
            self.manager.start(run["id"])
        self.assertEqual(self.store.get(run["id"])["status"], "ready")

    def test_start_revalidates_stored_agent_cap(self):
        run = self.ready()
        run["config"]["agent_count"] = 11
        self.store.save(run)
        with self.assertRaises(ValueError):
            self.manager.start(run["id"])

    def test_web_assets_and_report_export(self):
        server = make_server(self.manager, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for path, expected in [("/", b"Town square map"), ("/app.js", b"EventSource"),
                                   ("/style.css", b"focus-visible"), ("/room.js", b"getContext('2d')"),
                                   ("/room.css", b"prefers-reduced-motion")]:
                with urllib.request.urlopen(base + path, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(expected, response.read())
            run = self.ready()
            self.manager.start(run["id"])
            self.manager.worker.join(3)
            with urllib.request.urlopen(base + f"/api/runs/{run['id']}/export", timeout=3) as response:
                self.assertIn(b"[A1]", response.read())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)

    def test_http_validation_origin_and_static_allowlist(self):
        server = make_server(self.manager, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        def request(path, body=None, headers=None):
            data = None if body is None else json.dumps(body).encode()
            req = urllib.request.Request(base + path, data=data,
                                         headers={"Content-Type": "application/json", **(headers or {})})
            try:
                response = urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                return response.status, response.read(), response.headers
        try:
            code, body, headers = request("/api/config")
            self.assertEqual(code, 200)
            from misofish.core import MAX_AGENTS
            self.assertEqual(json.loads(body)["max_agents"], MAX_AGENTS)
            self.assertEqual(json.loads(body).get("default_agents"), 10)
            self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
            for count in [MAX_AGENTS + 1, True, "10"]:
                self.assertEqual(request("/api/runs", {"scenario": "Change", "agent_count": count})[0], 422)
            self.assertEqual(request("/api/runs", {"scenario": "Change"}, {"Origin": "https://evil.example"})[0], 403)
            self.assertEqual(request("/api/config", headers={"Host": "evil.example"})[0], 403)
            self.assertEqual(request("/.env")[0], 404)
            self.assertEqual(request("/../MiroFish/README.md")[0], 404)
            self.assertEqual(request("/api/runs/unknown")[0], 404)
            self.assertEqual(request("/api/runs", [], {})[0], 422)
            self.assertEqual(request("/api/runs", {"scenario": "Change"}, {"Content-Type": "text/plain"})[0], 415)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == "__main__":
    unittest.main()
