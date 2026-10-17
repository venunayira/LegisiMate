import json
import os
import subprocess
import queue
import signal
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class Engine:
    def __init__(self, python=None, environment=None):
        self.python = str(python or os.environ.get("LEGISIMATE_WORKER_PYTHON") or
                          ROOT / ".worker-venv" / "bin" / "python")
        self.environment = environment or {}

    def run(self, run, emit, cancelled):
        if not self.available()["available"]:
            raise RuntimeError("worker_unavailable")
        storage = Path(run["storage"]).resolve()
        storage.mkdir(parents=True, exist_ok=True, mode=0o700)
        events = queue.Queue()
        environment = {**os.environ, **self.environment,
                       "TIKTOKEN_CACHE_DIR": str(ROOT / ".cache" / "tiktoken"),
                       "HF_HUB_CACHE": str(ROOT / ".cache" / "huggingface"),
                       "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1"}
        process = subprocess.Popen([self.python, str(ROOT / "worker" / "main.py"),
            "--run", "--storage", str(storage)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=environment)
        def read_events():
            try:
                for line in process.stdout:
                    events.put(line)
            finally:
                events.put(None)
        reader = threading.Thread(target=read_events, daemon=True)
        reader.start()
        result = None
        stop_time = None
        seen = set()
        try:
            process.stdin.write(json.dumps({key: run[key] for key in ("version", "model", "config", "agents")}) + "\n")
            process.stdin.flush()
            process.stdin.close()
            while True:
                if cancelled() and stop_time is None:
                    stop_time = time.monotonic()
                    if process.poll() is None:
                        process.send_signal(signal.SIGTERM)
                if stop_time is not None and time.monotonic() - stop_time > 75 and process.poll() is None:
                    process.kill()
                try:
                    line = events.get(timeout=0.2)
                except queue.Empty:
                    continue
                if line is None:
                    break
                if len(line) > 500000:
                    raise RuntimeError("worker_event_invalid")
                event = json.loads(line)
                kind, data = event["kind"], event["data"]
                if kind == "worker_terminal":
                    result = data
                elif kind == "effect":
                    if data["effect_id"] not in seen:
                        seen.add(data["effect_id"])
                        emit(kind, data)
                elif kind in {"observation", "decision_start", "decision_complete", "decision_error",
                              "tick_complete", "worker_usage", "membership", "interview_error", "action_rejected"}:
                    emit(kind, data)
                else:
                    raise RuntimeError("worker_event_invalid")
            process.wait(timeout=5)
            if result is None:
                return {"status": "cancelled" if cancelled() else "failed", "error_code": "worker_interrupted"}
            return result
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            process.stdout.close()
            if not process.stdin.closed:
                process.stdin.close()
            reader.join(2)

    def available(self):
        if not Path(self.python).is_file():
            return {"available": False, "code": "worker_missing"}
        try:
            response = subprocess.run(
                [self.python, str(ROOT / "worker" / "main.py"), "--check"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if response.returncode:
                return {"available": False, "code": "worker_check_failed"}
            return json.loads(response.stdout.strip().splitlines()[-1])
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return {"available": False, "code": "worker_check_failed"}

    def twitter_available(self):
        snapshots = ROOT / ".cache" / "huggingface" / "models--Twitter--twhin-bert-base" / "snapshots"
        files = ("config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors")
        return any(all((snapshot / name).is_file() for name in files) for snapshot in snapshots.glob("*"))

    def self_test(self, directory, reject_action=False, provider_url=None):
        command = [self.python, str(ROOT / "worker" / "main.py"),
                   "--self-test", "--storage", str(Path(directory).resolve())]
        if reject_action:
            command.append("--reject-action")
        if provider_url:
            command.extend(["--fixture-provider", provider_url])
        response = subprocess.run(command, capture_output=True, text=True,
                                  timeout=90, check=False,
                                  env={**os.environ, "TIKTOKEN_CACHE_DIR": str(ROOT / ".cache" / "tiktoken")})
        if response.returncode:
            try:
                result = json.loads(response.stdout.strip().splitlines()[-1])
                error_type = result.get("error_type", "WorkerError")
            except (ValueError, IndexError):
                error_type = "WorkerError"
            if not isinstance(error_type, str) or not error_type.isidentifier() or len(error_type) > 80:
                error_type = "WorkerError"
            raise RuntimeError(f"Real-engine self-check failed ({error_type}).")
        return json.loads(response.stdout.strip().splitlines()[-1])