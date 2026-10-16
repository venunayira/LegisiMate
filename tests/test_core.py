import copy
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError
from misofish.core import (Action, Agent, Config, Model, Personas, Report,
                          generate_report, prepare, run_round)
import misofish.core as core


class PopulationModel:
    def __init__(self):
        self.payloads = []

    def generate(self, output_type, instructions, payload, max_tokens, **kwargs):
        self.payloads.append(copy.deepcopy(payload))
        return output_type.model_validate({"agents": [{
            "name": f"Person {slot['index']}", "role": "Resident", "perspective": "Cautious about access.",
            "profile": {"entity_id": slot["entity_id"], "goal": "Protect reliable access.",
                        "background": "A fictional stakeholder with a long commute.",
                        "interests": ["access", "funding"], "beliefs": ["Costs need a public explanation."],
                        "speaking_style": "Direct, informal and specific.",
                        "source_entity_ids": [node["id"] for node in payload["graph"]["nodes"]],
                        "activity_level": 0.7, "active_hours": list(range(24)),
                        "outlook": ["optimistic", "pessimistic", "skeptical", "pragmatic"][slot["index"] % 4],
                        "openness": "medium", "initial_view": "Access should not depend on income."}
        } for slot in payload["slots"]]})


def roster(count=2):
    return [Agent(id=i, name=f"Agent {i}", role="Resident", perspective="Cautious")
            for i in range(1, count + 1)]


class FakeModel:
    def __init__(self):
        self.payloads = []
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.calls = 0
        self.call_limit = None

    def generate(self, output_type, instructions, payload, max_tokens, on_delta=None, cancelled=lambda:False):
        if self.call_limit is not None and self.calls >= self.call_limit:
            raise RuntimeError("model_call_budget")
        self.calls += 1
        self.payloads.append(copy.deepcopy(payload))
        if output_type.__name__ == "Ontology":
            return output_type(entity_types=["organization"], actor_types=["organization"], relationship_types=["relates"])
        if output_type.__name__ == "GraphBatch":
            quote = (payload.get("evidence_excerpts") or [payload["text"][:1000]])[0]
            return output_type.model_validate({"nodes": [{"id": "library", "name": "Fictional library",
                "kind": "organization", "summary": quote, "synthetic": True,
                "evidence": [{"source_id": payload["source_id"], "quote": quote}]}], "edges": []})
        if output_type.__name__ == "PopulationBatch":
            return PopulationModel().generate(output_type, instructions, payload, max_tokens)
        if output_type is Personas:
            return Personas(agents=roster(payload["agent_count"]))
        if output_type.__name__ == "Utterance":
            return output_type(text=f"{payload['you']['name']} answers {len(payload['conversation'])} remarks.",
                view=f"{payload['you']['name']} now weighs {len(payload['memories'])} memories.",
                shift="softened" if payload["memories"] else "unchanged")
        if output_type.__name__ == "CourtUtterance":
            branch_num = payload.get("branch_number", 1)
            win_prob = 78 if branch_num >= 3 else (32 if branch_num == 1 else 54)
            outcome = "complainant_favour" if branch_num >= 3 else ("defense_favour" if branch_num == 1 else "balanced_split")
            return output_type(
                text=f"{payload['you']['name']} argues branch {branch_num} after {len(payload['conversation'])} turns.",
                view=f"{payload['you']['name']} assesses branch {branch_num} at {win_prob}% win probability.",
                shift="softened" if payload["memories"] else "unchanged",
                if_opponent_argues="Opponent challenges statutory notice timeline and debt enforceability.",
                tactical_move="Cite statutory presumption and prove primary dispatch records.",
                counter_strategy="State exact dispatch dates under Section 138 Proviso (b) and binding SC precedent.",
                branch_outcome=outcome,
                win_probability=win_prob,
            )
        if output_type is Action:
            if on_delta:
                on_delta({"text": "Please consider"})
            return Action(kind="reply" if payload.get("reply_to") else "post", text="Please consider access.",
                          stance="neutral", reply_to=payload.get("reply_to"))
        if on_delta:
            on_delta({"summary":"Access matters.","conclusion":"Access remains contested."})
        report = Report(summary="Access matters.", findings=[{
            "claim": "Access was raised.", "action_ids": [1]}], limitations="Synthetic, not a forecast.").model_dump()
        if "opinion_changes" in output_type.model_fields:
            report["opinion_changes"] = ["One resident softened after hearing about phased funding."]
        return output_type.model_validate(report)


class FixtureEngine:
    def __init__(self, model):
        self.model = model

    def available(self):
        return {"available": True, "code": "explicit_unit_fixture"}

    def twitter_available(self):
        return True

    def run(self, run, emit, cancelled):
        config = Config.model_validate(run["config"])
        agents = [Agent.model_validate(actor) for actor in run["agents"]]
        actions = []
        def commit(action):
            actions.append(action)
            emit("effect", {"effect_id": f"fixture:trace:{action['id']}", "agent_id": action["agent_id"],
                "platform": "reddit", "tick": action["round"], "kind": "create_comment" if action["reply_to"] else "create_post",
                "visibility": "public", "outcome": "committed", "simulation_minute": action["round"] * 30,
                "data": {"post_id": action["reply_to"] or action["id"], "content": action["text"]}})
        for tick in range(1, config.rounds + 1):
            batch = run_round(config, agents, actions.copy(), self.model, cancelled,
                emit=emit, on_action=commit)
            if cancelled():
                return {"status": "cancelled"}
            if len(batch) != config.agent_count:
                return {"status": "failed", "error_code": "fixture_incomplete"}
            emit("tick_complete", {"tick": tick, "successful": True, "simulation_minute": tick * 30})
        return {"status": "completed"}


class CoreTests(unittest.TestCase):
    def test_grounded_report_excludes_private_and_rejects_unknown_evidence(self):
        generate = getattr(core, "generate_grounded_report", None)
        self.assertTrue(callable(generate), "Graph-grounded synthesis is missing.")
        from misofish.graph import GraphStore, build_graph
        from test_graph import GraphModel, SOURCE
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            config = Config(scenario="Clinic policy", source=SOURCE)
            graph_store = GraphStore(Path(directory) / "graph.db")
            graph_store.save("report", build_graph(config, GraphModel()))
            effects = [{"id": 1, "effect_id": "reddit:trace:1", "agent_id": 1,
                        "kind": "post", "text": "Access matters.", "visibility": "public",
                        "outcome": "committed", "data": {"content": "Access matters."}},
                       {"id": 2, "effect_id": "reddit:trace:2", "agent_id": 2,
                        "kind": "post", "text": "PRIVATE_FIXTURE", "visibility": "private",
                        "outcome": "committed", "data": {"content": "PRIVATE_FIXTURE"}}]
            for effect in effects:
                graph_store.append_effect("report", effect)
            model = FakeModel()
            report = generate(config, graph_store, "report", roster(), effects, model)
            self.assertEqual(report.findings[0].action_ids, [1])
            self.assertNotIn("PRIVATE_FIXTURE", json.dumps(model.payloads))
            empty_model = FakeModel()
            empty = generate(config, graph_store, "report", roster(), [], empty_model)
            self.assertEqual(empty.findings, [])
            self.assertEqual(empty.agreements, [])
            self.assertFalse(empty_model.payloads)
            original = model.generate
            def invalid(*args, **kwargs):
                report = original(*args, **kwargs)
                report.findings[0].entity_ids = ["nonexistent"]
                return report
            model.generate = invalid
            with self.assertRaises(ValueError):
                generate(config, graph_store, "report", roster(), effects, model)

    def test_grounded_report_uses_final_interviews_and_default_free_schema(self):
        from openai.lib._pydantic import to_strict_json_schema
        from misofish.graph import GraphStore, build_graph
        from test_graph import GraphModel, SOURCE
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            config = Config(scenario="Clinic policy", source=SOURCE)
            graph_store = GraphStore(Path(directory) / "graph.db")
            graph_store.save("report", build_graph(config, GraphModel()))
            effects = [{"id": 1, "effect_id": "reddit:trace:1", "agent_id": 1, "kind": "post",
                        "text": "Access matters.", "visibility": "public", "outcome": "committed"},
                       {"id": 2, "effect_id": "reddit:trace:2", "agent_id": 2, "kind": "interview",
                        "platform": "reddit", "shift": "softened", "text": "A phased plan persuaded me.",
                        "visibility": "interview", "outcome": "committed"}]
            model, schemas = FakeModel(), []
            original = model.generate
            def capture(output_type, *args, **kwargs):
                schemas.append(to_strict_json_schema(output_type))
                result = original(output_type, *args, **kwargs)
                result.findings[0].action_ids = [2]
                return result
            model.generate = capture
            report = core.generate_grounded_report(config, graph_store, "report", roster(), effects, model)
            payload = model.payloads[-1]
            self.assertEqual(payload["final_interviews"][0]["id"], 2)
            self.assertEqual(payload["shift_counts"], {"softened": 1})
            self.assertEqual(report.findings[0].action_ids, [2])
            self.assertTrue(report.opinion_changes)
            self.assertNotIn('"default"', json.dumps(schemas[-1]))

    def test_population_defaults_to_ten_but_allows_more(self):
        self.assertEqual(Config(scenario="Change").agent_count, 10)
        self.assertGreater(core.MAX_AGENTS, 10)
        self.assertEqual(Config(scenario="Change", agent_count=23).agent_count, 23)

    def test_population_above_ten_is_batched(self):
        prepare_population = getattr(core, "prepare_population", None)
        self.assertTrue(callable(prepare_population), "Rich graph-backed preparation is missing.")
        from misofish.graph import build_graph
        from test_graph import GraphModel, SOURCE
        config = Config(scenario="Clinic policy", source=SOURCE, agent_count=13)
        graph = build_graph(config, GraphModel())
        model = PopulationModel()
        agents = prepare_population(config, graph, model)
        self.assertEqual([agent.id for agent in agents], list(range(1, 14)))
        self.assertEqual(len({agent.name for agent in agents}), 13)
        self.assertGreater(len(model.payloads), 1)
        self.assertTrue(all(len(payload["slots"]) <= 4 for payload in model.payloads))
        self.assertTrue(all(agent.profile.goal and agent.graph_context for agent in agents))

    def test_population_provider_schema_enforces_exact_fictional_slots(self):
        from misofish.graph import build_graph
        from test_graph import GraphModel, SOURCE
        config = Config(scenario="Clinic policy", source=SOURCE, agent_count=5)
        graph = build_graph(config, GraphModel())
        model = PopulationModel()
        original = model.generate
        schemas = []
        def capture(output_type, *args, **kwargs):
            schemas.append(output_type.model_json_schema())
            return original(output_type, *args, **kwargs)
        model.generate = capture
        agents = core.prepare_population(config, graph, model)
        self.assertEqual(len(agents), 5)
        for schema, expected in zip(schemas, (4, 1)):
            field = schema["properties"]["agents"]
            self.assertEqual((field["minItems"], field["maxItems"]), (expected, expected))
            persona = schema["$defs"][field["items"]["$ref"].split("/")[-1]]
            profile = schema["$defs"][persona["properties"]["profile"]["$ref"].split("/")[-1]]
            self.assertEqual(profile["properties"]["entity_id"]["type"], "null")
            self.assertEqual(set(profile["properties"]["source_entity_ids"]["items"]["enum"]),
                {node["id"] for node in graph["nodes"]})
            self.assertLessEqual({"outlook", "openness", "initial_view"}, set(profile["required"]))
            self.assertEqual(set(profile["properties"]["outlook"]["enum"]),
                {"optimistic", "pessimistic", "skeptical", "pragmatic"})
        self.assertTrue(all(agent.profile.entity_id is None for agent in agents))
        self.assertTrue(all(agent.profile.outlook and agent.profile.initial_view for agent in agents))

    def test_saved_profiles_without_traits_remain_valid(self):
        profile = core.Profile.model_validate({"entity_id": None, "goal": "Access", "background": "Resident",
            "interests": ["access"], "beliefs": ["Fair rules"], "speaking_style": "Plain",
            "source_entity_ids": [], "activity_level": 0.5, "active_hours": [9]})
        self.assertIsNone(profile.outlook)

    def test_population_shortfall_is_explicit(self):
        prepare_population = getattr(core, "prepare_population", None)
        self.assertTrue(callable(prepare_population), "Rich graph-backed preparation is missing.")
        from misofish.graph import build_graph
        from test_graph import GraphModel, SOURCE
        config = Config(scenario="Clinic policy", source=SOURCE, agent_count=3, population_mode="grounded")
        graph = build_graph(config, GraphModel())
        model = PopulationModel()
        with self.assertRaisesRegex(ValueError, "population_shortfall"):
            prepare_population(config, graph, model)
        self.assertFalse(model.payloads)

    def test_population_grounded_actor_context_and_mapping(self):
        prepare_population = getattr(core, "prepare_population", None)
        self.assertTrue(callable(prepare_population), "Rich graph-backed preparation is missing.")
        from misofish.graph import build_graph
        from test_graph import GraphModel, SOURCE
        config = Config(scenario="Clinic policy", source=SOURCE, agent_count=2, population_mode="grounded")
        graph = build_graph(config, GraphModel())
        agents = prepare_population(config, graph, PopulationModel())
        self.assertEqual({agent.profile.entity_id for agent in agents}, {node["id"] for node in graph["nodes"]})
        self.assertTrue(all(agent.graph_context["relationships"] for agent in agents))

    def test_ten_agents_never_exceed_four_concurrent_decisions(self):
        entered, release = threading.Event(), threading.Event()
        lock = threading.Lock()
        concurrent = {"active": 0, "peak": 0}
        fake = FakeModel()
        original = fake.generate
        def blocked(*args):
            with lock:
                concurrent["active"] += 1
                concurrent["peak"] = max(concurrent["peak"], concurrent["active"])
                if concurrent["active"] == 4:
                    entered.set()
            release.wait(3)
            result = original(*args)
            with lock:
                concurrent["active"] -= 1
            return result
        fake.generate = blocked
        results = []
        thread = threading.Thread(target=lambda: results.extend(
            run_round(Config(scenario="Change", agent_count=10), roster(10), [], fake)))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
        finally:
            release.set()
            thread.join(3)
        self.assertEqual(concurrent["peak"], 4)
        self.assertEqual([a["id"] for a in results], list(range(1, 11)))

    def test_strict_cap_and_input_boundaries(self):
        self.assertEqual(Config(scenario="A change").agent_count, 10)
        for bad in [0, core.MAX_AGENTS + 1, True, "10", 2.5, None]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                Config(scenario="A change", agent_count=bad)
        for fields in [{"rounds": 11}, {"scenario": " "}, {"source": "x" * 20001},
                       {"scenario": "x" * 2001}, {"surprise": 1}]:
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                Config.model_validate({"scenario": "A change", **fields})

    def test_generation_must_match_requested_count(self):
        fake = FakeModel()
        self.assertEqual([a.id for a in prepare(Config(scenario="Change", agent_count=2), fake)], [1, 2])
        self.assertEqual([agent.id for agent in prepare(Config(scenario="Change", agent_count=13), fake)],
                         list(range(1, 14)))
        fake.generate = lambda *args: Personas(agents=roster(3))
        with self.assertRaises(ValueError):
            prepare(Config(scenario="Change", agent_count=2), fake)
        with self.assertRaises(ValidationError):
            Personas(agents=roster(11))

    def test_round_context_includes_exact_parent_and_previous_round(self):
        fake = FakeModel()
        config = Config(scenario="Change", agent_count=2)
        first = run_round(config, roster(), [], fake)
        self.assertEqual([(a["id"], a["round"]) for a in first], [(1, 1), (2, 1)])
        self.assertEqual({a['agent_id'] for a in first},{1,2})
        self.assertEqual(fake.payloads[0]["feed"], [])
        self.assertEqual(fake.payloads[1]["feed"], [first[0]])
        second = run_round(config, roster(), first, fake)
        self.assertEqual([a["id"] for a in second], [3, 4])
        self.assertEqual(fake.payloads[2]["feed"], first)
        self.assertEqual(fake.payloads[3]["feed"], first + [second[0]])
        self.assertEqual(len(first), 2)
        with self.assertRaises(ValueError):
            run_round(config, roster(11), [], fake)

    def test_reply_requires_visible_existing_post(self):
        fake = FakeModel()
        fake.generate = lambda *args: Action(kind="reply", text="Agree", stance="support", reply_to=99)
        with self.assertRaises(ValueError):
            run_round(Config(scenario="Change", agent_count=2), roster(), [], fake)
        for fields in [{"kind": "post", "reply_to": 1}, {"kind": "reply", "reply_to": None}]:
            with self.assertRaises(ValidationError):
                Action(text="Hello", stance="neutral", **fields)

    def test_reply_can_reference_a_prior_visible_post(self):
        fake = FakeModel()
        config = Config(scenario="Change", agent_count=2)
        first = run_round(config, roster(), [], fake)
        fake.generate = lambda output_type,instructions,payload,max_tokens: Action(
            kind="reply", text="Agree", stance="support", reply_to=payload['reply_to'] or next(
                a['id'] for a in payload['feed'] if a['agent_id'] != payload['persona']['id'] and a['kind'] != 'pass'))
        second = run_round(config, roster(), first, fake)
        self.assertIn(second[0]['reply_to'],[1,2])
        self.assertEqual(second[1]['reply_to'],second[0]['id'])

    def test_report_rejects_invented_or_pass_citations(self):
        config = Config(scenario="Change", agent_count=2)
        fake = FakeModel()
        actions = run_round(config, roster(), [], fake)
        self.assertEqual(generate_report(config, roster(), actions, fake).findings[0].action_ids, [1])
        fake.generate = lambda *args: Report(summary="Result", findings=[{
            "claim": "Invented", "action_ids": [99]}], limitations="Synthetic")
        with self.assertRaises(ValueError):
            generate_report(config, roster(), actions, fake)
        fake.generate = lambda *args: Report(summary="Result", findings=[{
            "claim": "No evidence", "action_ids": [1]}], limitations="Synthetic")
        actions[0]["kind"] = "pass"
        with self.assertRaises(ValueError):
            generate_report(config, roster(), actions, fake)

    def test_model_uses_sdk_parse_and_handles_refusal_or_incomplete(self):
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(status="completed", output_parsed=Personas(agents=roster()),
                                                              usage=SimpleNamespace(input_tokens=12, output_tokens=7))
        model = Model(client, "gpt-4o-mini")
        model.generate(Personas, "Test", {"scenario": "Change"}, 100)
        params = client.responses.parse.call_args.kwargs
        self.assertFalse(params["store"])
        self.assertEqual(params["max_output_tokens"], 100)
        self.assertEqual(json.loads(params["input"]), {"scenario": "Change"})
        self.assertEqual(model.usage, {"input_tokens": 12, "output_tokens": 7})
        for state, parsed in [("incomplete", None), ("completed", None)]:
            client.responses.parse.return_value = SimpleNamespace(status=state, output_parsed=parsed, usage=None)
            with self.assertRaises(ValueError):
                model.generate(Personas, "Test", {}, 100)

    def test_gpt5_short_calls_disable_hidden_reasoning_budget(self):
        client=Mock()
        client.responses.parse.return_value=SimpleNamespace(status='completed',
            output_parsed=Personas(agents=roster()),usage=None)
        Model(client,'gpt-5.4-mini').generate(Personas,'Test',{},3000)
        self.assertEqual(client.responses.parse.call_args.kwargs['reasoning'],{'effort':'none'})



if __name__ == "__main__":
    unittest.main()
