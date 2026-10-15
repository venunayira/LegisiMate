import random
import unittest
from misofish.space import Room
from test_core import roster
from test_core import FakeModel
from misofish.core import Config,run_round


class SpaceTests(unittest.TestCase):
    def test_room_events_drive_actual_turn_positions_and_contacts(self):
        model=FakeModel();room=Room(roster(4),seed=24);events=[]
        result=run_round(Config(scenario='Change',agent_count=4),roster(4),[],model,room=room,
                         emit=lambda k,d:events.append((k,d)))
        contacts=[d for k,d in events if k=='encounter_start']
        self.assertEqual(len(contacts),2)
        for turn in result:
            encounter=next(e for e in contacts if e['id']==turn['encounter_id'])
            self.assertIn(turn['agent_id'],[encounter['initiator'],encounter['partner']])
            self.assertEqual(len(turn['positions']),4)
        self.assertTrue(any(k=='room_state' for k,d in events))
        self.assertEqual(room.snapshot()['encounters'],[])

    def test_roaming_is_seeded_bounded_and_not_a_prearranged_cast(self):
        first=Room(roster(10),seed=42)
        second=Room(roster(10),seed=42)
        start=first.snapshot()
        for _ in range(20):
            first.roam();second.roam()
        self.assertEqual(first.snapshot(),second.snapshot())
        self.assertNotEqual(start['people'],first.snapshot()['people'])
        self.assertEqual(len(first.snapshot()['people']),10)
        for person in first.snapshot()['people']:
            self.assertTrue(0.7 <= person['x'] <= 9.3)
            self.assertTrue(0.7 <= person['y'] <= 9.3)
        self.assertEqual(first.snapshot()['encounters'],[])

    def test_encounters_choose_nearby_available_people_and_reserve_them(self):
        room=Room(roster(4),seed=1)
        room.people[1].update(x=1,y=1)
        room.people[2].update(x=1.2,y=1)
        room.people[3].update(x=8,y=8)
        room.people[4].update(x=8.2,y=8)
        encounter=room.encounter({1,2,3,4},1)
        participants={encounter['initiator'],encounter['partner']}
        self.assertIn(participants,[{1,2},{3,4}])
        another=room.encounter({1,2,3,4}-participants,1)
        self.assertFalse(participants & {another['initiator'],another['partner']})
        self.assertEqual(len(room.snapshot()['encounters']),2)
        before={p['id']:(p['x'],p['y']) for p in room.snapshot()['people']}
        room.roam()
        self.assertEqual(before,{p['id']:(p['x'],p['y']) for p in room.snapshot()['people']})
        room.release(encounter['id'])
        self.assertEqual(len(room.snapshot()['encounters']),1)

    def test_approach_happens_before_speaking_and_layout_restores(self):
        room=Room(roster(2),seed=4)
        room.people[1].update(x=1,y=1)
        room.people[2].update(x=8,y=8)
        encounter=room.encounter({1,2},1)
        self.assertEqual(encounter['phase'],'approaching')
        for _ in range(30):
            if room.approach(encounter['id']):break
        state=room.snapshot()
        a=room.people[encounter['initiator']];b=room.people[encounter['partner']]
        self.assertLessEqual(((a['x']-b['x'])**2+(a['y']-b['y'])**2)**.5,1.25)
        room.speak(encounter['id'],encounter['initiator'])
        self.assertEqual(room.people[encounter['initiator']]['state'],'speaking')
        self.assertEqual(room.people[encounter['partner']]['state'],'listening')
        restored=Room(roster(2),seed=4,state=room.snapshot())
        self.assertEqual(restored.snapshot()['people'],room.snapshot()['people'])

    def test_new_round_contacts_come_from_positions_not_id_rotation(self):
        choices=[]
        for seed in range(12):
            room=Room(roster(6),seed=seed)
            encounter=room.encounter(set(range(1,7)),1)
            choices.append((encounter['initiator'],encounter['partner']))
        self.assertGreater(len(set(choices)),3)
        self.assertTrue(any(abs(a-b)>1 for a,b in choices))

    def test_invalid_positions_fail_closed(self):
        with self.assertRaises(ValueError):
            Room(roster(2),state={'people':[{'id':1,'x':float('nan'),'y':1},{'id':2,'x':1,'y':1}]})
        with self.assertRaises(ValueError):
            Room(roster(11))
