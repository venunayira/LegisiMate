import importlib
import importlib.util
import io
import inspect
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from test_sdk import ChatProviderFixture, provider_fixture


class EngineTests(unittest.TestCase):
    def test_engine_duplicate_ipc_effect_is_committed_once(self):
        engine = self.engine_type()()
        effect = {"kind": "effect", "data": {"effect_id": "reddit:trace:1", "outcome": "committed"}}
        lines = [effect, effect, {"kind": "worker_terminal", "data": {"status": "completed"}}]
        process = Mock(stdin=io.StringIO(), stdout=io.StringIO("\n".join(json.dumps(line) for line in lines)))
        process.poll.return_value = 0
        with tempfile.TemporaryDirectory() as directory, patch.object(engine, "available", return_value={"available": True}), patch("misofish.engine.subprocess.Popen", return_value=process):
            events = []
            result = engine.run({"version": 2, "model": "fixture", "config": {}, "agents": [], "storage": directory},
                lambda kind, data: events.append((kind, data)), lambda: False)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(len(events), 1)

    def test_engine_actual_dual_platform_effects_have_separate_identity(self):
        result, events, _ = self.run_fixture({"platform_mode": "both", "rounds": 2}, actors=2)
        self.assertEqual(result["status"], "completed")
        effects = [data for kind, data in events if kind == "effect"]
        self.assertTrue(any(effect["platform"] == "twitter" and effect["kind"] == "create_post" for effect in effects))
        self.assertTrue(any(effect["platform"] == "reddit" and effect["kind"] == "create_post" for effect in effects))
        self.assertEqual(len(effects), len({effect["effect_id"] for effect in effects}))
        self.assertTrue(any(kind == "observation" and data["platform"] == "twitter" and data["effect_ids"]
                            for kind, data in events))

    def test_engine_rejected_target_does_not_stop_the_run(self):
        def tools(request):
            ticks = sum("Please perform social media actions" in str(message.get("content"))
                        for message in request["messages"] if message["role"] == "user")
            calls = [{"id": "proposal", "type": "function", "function": {
                "name": "create_post", "arguments": json.dumps({"content": "Protect access."})}}]
            if ticks >= 2:
                calls.append({"id": "own_post", "type": "function", "function": {
                    "name": "like_post", "arguments": json.dumps({"post_id": 1})}})
            return calls
        result, events, _ = self.run_fixture(tool_factory=tools)
        self.assertEqual(result["status"], "completed")
        rejected = [data for kind, data in events if kind == "action_rejected"]
        self.assertTrue(rejected and all(data["code"] == "target_not_observed" for data in rejected))
        posts = [data for kind, data in events if kind == "effect" and data["kind"] == "create_post"]
        self.assertEqual([post["tick"] for post in posts], [1, 2, 3])
        self.assertEqual([data["tick"] for kind, data in events if kind == "tick_complete" and data["successful"]], [1, 2, 3])

    def run_fixture(self, config=None, actors=1, tool_factory=None):
        class Fixture(ChatProviderFixture):
            requests = []
        Fixture.tool_factory = staticmethod(tool_factory) if tool_factory else None
        server, thread = provider_fixture(Fixture)
        try:
            with tempfile.TemporaryDirectory() as directory:
                run = {"version": 2, "model": "gpt-5.4-mini", "storage": directory,
                    "config": {"scenario": "Library access", "rounds": 3, "start_hour": 9,
                        "minutes_per_round": 30, "seed": 42, "readable_dwell": 0,
                        "model_call_budget": 40, **(config or {})},
                    "agents": [{"id": actor + 1, "name": "Elin" if actor == 0 else "Boris",
                        "role": "Resident", "perspective": "Access",
                        "profile": {"activity_level": 1, "active_hours": list(range(24))}}
                        for actor in range(actors)]}
                if config and config.get("inactive"):
                    for actor in run["agents"]:
                        actor["profile"]["activity_level"] = 0
                events = []
                stop = threading.Event()
                def emit(kind, data):
                    events.append((kind, data))
                    if config and config.get("cancel_after_effect") and kind == "effect" and data["kind"] == "create_post":
                        stop.set()
                result = self.engine_type()(environment={"OPENAI_API_KEY": "local-fixture",
                    "OPENAI_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1"}).run(
                        run, emit, stop.is_set)
                return result, events, Fixture.requests
        finally:
            server.shutdown(); server.server_close(); thread.join(3)

    def test_engine_comment_effect_identifies_parent_post(self):
        def tools(request):
            elin = "Elin" in request["messages"][0]["content"]
            ticks = sum("Please perform social media actions" in str(message.get("content"))
                        for message in request["messages"] if message["role"] == "user")
            if elin and ticks == 1:
                return [{"id": "post", "type": "function", "function": {
                    "name": "create_post", "arguments": json.dumps({"content": "Protect access."})}}]
            if not elin and ticks >= 2:
                return [{"id": "reply", "type": "function", "function": {
                    "name": "create_comment", "arguments": json.dumps({"post_id": 1, "content": "Who pays?"})}}]
            return [{"id": "quiet", "type": "function", "function": {"name": "do_nothing", "arguments": "{}"}}]
        result, events, _ = self.run_fixture(actors=2, tool_factory=tools)
        self.assertEqual(result["status"], "completed")
        comments = [data for kind, data in events if kind == "effect" and data["kind"] == "create_comment"]
        self.assertTrue(comments)
        self.assertTrue(all(comment["data"].get("post_id") == 1 for comment in comments))

    def test_engine_repeated_room_speech(self):
        tools = lambda _: [{"id": "speech", "type": "function", "function": {
            "name": "send_to_group", "arguments": json.dumps({"group_id": 1, "message": "Who funds access?"})}}]
        result, events, _ = self.run_fixture(tool_factory=tools)
        self.assertEqual(result["status"], "completed")
        speech = [data for kind, data in events if kind == "effect" and data["kind"] == "send_to_group"]
        self.assertEqual([effect["tick"] for effect in speech], [1, 2, 3])
        self.assertTrue(speech[1]["observed_effect_ids"])

    def test_engine_interviews_participants_on_every_platform_after_final_tick(self):
        result, events, requests = self.run_fixture({"platform_mode": "both", "rounds": 1}, actors=2)
        self.assertEqual(result["status"], "completed")
        interviews = [(index, data) for index, (kind, data) in enumerate(events)
                      if kind == "effect" and data["kind"] == "interview"]
        self.assertEqual(sorted((data["platform"], data["agent_id"]) for _, data in interviews),
                         [("reddit", 1), ("reddit", 2), ("twitter", 1), ("twitter", 2)])
        self.assertTrue(all(data["visibility"] == "interview" and data["data"]["response"].startswith("[SOFTENED]")
                            for _, data in interviews))
        last_tick = max(index for index, (kind, _) in enumerate(events) if kind == "tick_complete")
        self.assertTrue(all(index > last_tick for index, _ in interviews))
        asked = [request for request in requests if "[UNCHANGED]" in str(request["messages"][-1].get("content"))]
        self.assertEqual(len(asked), 4)
        self.assertFalse(any(request.get("tools") for request in asked))

    def test_engine_reserves_budget_for_final_interviews(self):
        result, events, requests = self.run_fixture({"model_call_budget": 4})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(requests), 4)
        self.assertIn("[UNCHANGED]", requests[-1]["messages"][-1]["content"])
        self.assertEqual(len([data for kind, data in events if kind == "effect" and data["kind"] == "interview"]), 1)

    def test_engine_budget_failure_preserves_successful_effect(self):
        result, events, requests = self.run_fixture({"model_call_budget": 2})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "model_call_budget")
        self.assertEqual(len(requests), 1)
        self.assertEqual(len([data for kind, data in events if kind == "effect" and data["kind"] == "create_post"]), 1)

    def test_engine_empty_ticks_advance_without_provider_calls(self):
        result, events, requests = self.run_fixture({"inactive": True})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(requests, [])
        self.assertEqual([data["simulation_minute"] for kind, data in events if kind == "tick_complete"], [30, 60, 90])

    def test_engine_cancellation_preserves_committed_effect(self):
        result, events, _ = self.run_fixture({"cancel_after_effect": True, "readable_dwell": 2})
        self.assertEqual(result["status"], "cancelled")
        self.assertTrue(any(kind == "effect" and data["kind"] == "create_post" for kind, data in events))
        self.assertLess(len([data for kind, data in events if kind == "tick_complete"]), 3)

    def test_engine_private_group_is_membership_scoped(self):
        def tools(request):
            if "Elin" in request["messages"][0]["content"] and not any(
                    "PRIVATE_FIXTURE" in str(message.get("content")) for message in request["messages"]):
                return [{"id": "private_create", "type": "function", "function": {
                    "name": "create_group", "arguments": json.dumps({"group_name": "Private meeting"})}},
                    {"id": "private_speech", "type": "function", "function": {
                    "name": "send_to_group", "arguments": json.dumps({"group_id": 2, "message": "PRIVATE_FIXTURE"})}}]
            return [{"id": "quiet", "type": "function", "function": {"name": "do_nothing", "arguments": "{}"}}]
        result, events, requests = self.run_fixture(actors=2, tool_factory=tools)
        self.assertEqual(result["status"], "completed")
        private = [data for kind, data in events if kind == "effect" and data["kind"] == "send_to_group"]
        self.assertEqual(len(private), 1)
        self.assertEqual(private[0]["visibility"], "private")
        boris = [request for request in requests if "Boris" in request["messages"][0]["content"]]
        self.assertTrue(boris)
        self.assertFalse(any("PRIVATE_FIXTURE" in json.dumps(request) for request in boris))

    def test_engine_malformed_tool_is_not_success(self):
        tools = lambda _: [{"id": "invalid", "type": "function", "function": {
            "name": "send_to_group", "arguments": json.dumps({"group_id": 1, "content": "Wrong schema"})}}]
        result, _, _ = self.run_fixture(tool_factory=tools)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "tool_schema_invalid")

    def test_engine_peer_failure_stops_queued_model_calls(self):
        tools = lambda _: [{"id": "invalid", "type": "function", "function": {
            "name": "send_to_group", "arguments": json.dumps({"group_id": 1, "content": "Wrong schema"})}}]
        result, _, requests = self.run_fixture(actors=6, tool_factory=tools)
        self.assertEqual(result["status"], "failed")
        self.assertLessEqual(len(requests), 4)

    def test_engine_three_ticks_retains_memory_and_group_effects(self):
        engine_type = self.engine_type()
        self.assertTrue(hasattr(engine_type, "run"), "Production worker lifecycle is missing.")
        ChatProviderFixture.requests = []
        server, thread = provider_fixture(ChatProviderFixture)
        try:
            with tempfile.TemporaryDirectory() as directory:
                engine = engine_type(environment={"OPENAI_API_KEY": "local-fixture",
                    "OPENAI_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1"})
                run = {"version": 2, "model": "gpt-5.4-mini", "storage": directory,
                       "config": {"scenario": "Library access", "rounds": 3,
                           "start_hour": 9, "minutes_per_round": 30, "seed": 42,
                           "readable_dwell": 0, "model_call_budget": 40},
                       "agents": [{"id": 1, "name": "Elin", "role": "Resident",
                           "perspective": "Access", "profile": {"activity_level": 1,
                           "active_hours": list(range(24)), "goal": "Fund access"}}]}
                events = []
                result = engine.run(run, lambda kind, data: events.append((kind, data)), lambda: False)
                self.assertEqual(result["status"], "completed")
                ticks = [data for kind, data in events if kind == "tick_complete"]
                self.assertEqual([data["tick"] for data in ticks], [1, 2, 3])
                self.assertEqual([data["simulation_minute"] for data in ticks], [30, 60, 90])
                effects = [data for kind, data in events if kind == "effect"]
                self.assertEqual(len({data["effect_id"] for data in effects}), len(effects))
                self.assertTrue(any(data["kind"] == "create_group" for data in effects))
                self.assertGreaterEqual(max(len(request["messages"])
                    for request in ChatProviderFixture.requests), 6)
                usage = [data for kind, data in events if kind == "worker_usage"][-1]
                self.assertGreater(usage["input_tokens"], 0)
                with closing(sqlite3.connect(Path(directory) / "reddit.db")) as database:
                    self.assertGreaterEqual(database.execute("SELECT COUNT(*) FROM post").fetchone()[0], 1)
                    self.assertEqual(database.execute("SELECT COUNT(*) FROM group_members").fetchone()[0], 1)
        finally:
            server.shutdown(); server.server_close(); thread.join(3)

    def engine_type(self):
        self.assertIsNotNone(importlib.util.find_spec("misofish.engine"),
                             "The real OASIS worker supervisor is not implemented.")
        return importlib.import_module("misofish.engine").Engine

    def test_engine_requires_supported_python(self):
        engine = self.engine_type()(python=sys.executable)
        result = engine.available()
        self.assertFalse(result["available"])
        self.assertEqual(result["code"], "python_unsupported")

    def test_engine_real_tool_effect(self):
        engine = self.engine_type()()
        self.assertTrue(engine.available()["available"])
        with tempfile.TemporaryDirectory() as directory:
            result = engine.self_test(directory)
            self.assertEqual(result["status"], "completed")
            self.assertGreaterEqual(len(result["effects"]), 2)
            self.assertEqual(len({effect["effect_id"] for effect in result["effects"]}),
                             len(result["effects"]))
            with closing(sqlite3.connect(Path(directory) / "reddit.db")) as database:
                self.assertEqual(database.execute("SELECT COUNT(*) FROM post").fetchone()[0], 1)
                self.assertEqual(database.execute("SELECT COUNT(*) FROM comment").fetchone()[0], 1)

    def test_engine_partial_tool_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.engine_type()().self_test(directory, reject_action=True)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error_code"], "tool_rejected")
            self.assertEqual(len(result["effects"]), 1)
            with closing(sqlite3.connect(Path(directory) / "reddit.db")) as database:
                self.assertEqual(database.execute("SELECT COUNT(*) FROM post").fetchone()[0], 1)
                self.assertEqual(database.execute("SELECT COUNT(*) FROM comment").fetchone()[0], 0)

    def test_engine_uses_configured_deployment_tools(self):
        engine = self.engine_type()()
        self.assertIn("provider_url", inspect.signature(engine.self_test).parameters,
                      "The actual worker has no local provider integration check.")
        ChatProviderFixture.requests = []
        server, thread = provider_fixture(ChatProviderFixture)
        try:
            with tempfile.TemporaryDirectory() as directory:
                result = engine.self_test(directory,
                    provider_url=f"http://127.0.0.1:{server.server_port}/v1")
                self.assertEqual(result["status"], "completed")
                self.assertTrue(ChatProviderFixture.requests)
                self.assertTrue(all(request["model"] == "gpt-5.4-mini"
                                    for request in ChatProviderFixture.requests))
                self.assertTrue(any(effect["kind"] == "create_post" for effect in result["effects"]))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == "__main__":
    unittest.main()