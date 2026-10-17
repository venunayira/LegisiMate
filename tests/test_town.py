import random
import unittest

from legisimate.core import Agent, Config, Profile
from legisimate.town import form_groups, run_town, schedule, town_calls
from test_core import FakeModel


def people(count):
    return [Agent(id=index, name=f"Person {index}", role="Resident", perspective="Unsure",
                  profile=Profile(entity_id=None, goal="Fair rules", background="Local", interests=["water"],
                                  beliefs=["Rules must be fair"], speaking_style="Plain", source_entity_ids=[],
                                  activity_level=0.5, active_hours=[9], initial_view=f"Opening view {index}"))
            for index in range(1, count + 1)]


class TownTests(unittest.TestCase):
    def test_three_randomizers_partition_everyone_into_small_groups(self):
        counts = set()
        for seed in range(60):
            groups = form_groups(list(range(1, 11)), random.Random(seed))
            counts.add(len(groups))
            self.assertTrue(2 <= len(groups) <= 5)
            self.assertTrue(all(2 <= len(group) <= 5 for group in groups))
            self.assertEqual(sorted(member for group in groups for member in group), list(range(1, 11)))
        self.assertGreater(len(counts), 1, "The number of groups must itself be random")
        self.assertEqual(form_groups(list(range(1, 11)), random.Random(7)), form_groups(list(range(1, 11)), random.Random(7)))

    def test_every_member_speaks_after_hearing_everyone_else(self):
        for tick in schedule(Config(scenario="Water", rounds=3, platform_mode="town", seed=3), list(range(1, 11))):
            for group in tick:
                turns, members = group["turns"], set(group["members"])
                self.assertGreaterEqual(len(turns), 5)
                for member in members:
                    last = max(index for index, speaker in enumerate(turns) if speaker == member)
                    self.assertEqual(set(turns[:last]) | {member}, members)

    def test_groups_converse_in_parallel_and_views_carry_into_later_ticks(self):
        config = Config(scenario="Water", agent_count=4, rounds=2, platform_mode="town", conversation_minutes=3)
        model, events = FakeModel(), []
        result = run_town(config, people(4), model, lambda kind, data: events.append((kind, data)), lambda: False)
        self.assertEqual(result["status"], "completed")
        said = [data for kind, data in events if kind == "effect"]
        self.assertEqual(len(said), town_calls(config, [1, 2, 3, 4]))
        self.assertEqual([data["tick"] for kind, data in events if kind == "groups_formed"], [1, 2])
        self.assertTrue(all(data["view"] and data["visibility"] == "public" for data in said))
        self.assertTrue(all(data["data"]["reply_to_effect"] for data in said if data["data"]["turn"] > 1))
        later = [payload for payload in model.payloads if payload.get("tick") == 2]
        self.assertTrue(later and all(payload["memories"] for payload in later))
        self.assertTrue(all(payload["current_view"] != payload["opening_view"] for payload in later))

    def test_town_needs_two_people(self):
        with self.assertRaises(ValueError):
            Config(scenario="Water", agent_count=1, platform_mode="town")

    def test_real_sdk_structured_utterances(self):
        import json
        from openai import OpenAI
        from legisimate.core import Model
        from test_sdk import ProviderFixture, provider_fixture
        class Fixture(ProviderFixture):
            requests = []
        server, thread = provider_fixture(Fixture)
        try:
            with OpenAI(api_key="local-fixture", base_url=f"http://127.0.0.1:{server.server_port}/v1",
                        max_retries=0, timeout=5) as client:
                config = Config(scenario="Water", agent_count=3, rounds=2, platform_mode="town", conversation_minutes=2)
                events = []
                result = run_town(config, people(3), Model(client, "gpt-5.4-mini"),
                                  lambda kind, data: events.append((kind, data)), lambda: False)
            self.assertEqual(result["status"], "completed")
            formats = [request["text"]["format"] for request in Fixture.requests]
            self.assertTrue(formats and all(item["name"] == "Utterance" and item["strict"] for item in formats))
            self.assertNotIn('"default"', json.dumps(formats))
            self.assertEqual(len([data for kind, data in events if kind == "effect"]), town_calls(config, [1, 2, 3]))
        finally:
            server.shutdown(); server.server_close(); thread.join(3)


if __name__ == "__main__":
    unittest.main()
