"""Temporary localhost test harness for browser verification, not a production mode."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import OpenAI
from misofish.core import Model
from misofish.engine import Engine
from misofish.server import Manager, Store, make_server
from test_sdk import ProviderFixture, provider_fixture


if __name__ == "__main__":
    ProviderFixture.pacing = 0.06
    provider, thread = provider_fixture()
    with tempfile.TemporaryDirectory(prefix="misofish-browser-") as directory:
        with OpenAI(api_key="local-fixture", base_url=f"http://127.0.0.1:{provider.server_port}/v1",
                    max_retries=0, timeout=5) as client:
            ProviderFixture.tool_factory = staticmethod(lambda request: [{"id": "fixture_speech", "type": "function",
                "function": {"name": "send_to_group", "arguments": '{"group_id":1,"message":"I want to answer the funding concern. Can we protect evening access without cutting staff hours?"}'}}
                if any(tool["function"]["name"] == "send_to_group" for tool in request["tools"]) else
                {"id": "fixture_public", "type": "function", "function": {"name": "create_post",
                 "arguments": '{"content":"Evening access requires a funded staffing plan, not only longer opening hours."}'}}])
            manager = Manager(Store(Path(directory) / "runs.db"), Model(client, "gpt-5.4-mini"),
                engine=Engine(environment={"OPENAI_API_KEY": "local-fixture",
                    "OPENAI_BASE_URL": f"http://127.0.0.1:{provider.server_port}/v1"}))
            server = make_server(manager, 8001)
            print("TEST HARNESS ONLY: http://127.0.0.1:8001 — real SDK, localhost response fixture", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                manager.stop.set()
                if manager.worker:
                    manager.worker.join()
                server.server_close()
    provider.shutdown()
    provider.server_close()
    thread.join()
