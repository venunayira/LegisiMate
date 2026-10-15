"""Small spatial encounter model. Positions drive contacts, not preassigned pairs."""
import math
import random
from threading import RLock


class Room:
    def __init__(self, agents, seed=None, state=None):
        if not 1 <= len(agents) <= 10 or len({a.id for a in agents}) != len(agents):
            raise ValueError("Room requires 1..10 unique people.")
        self.rng = random.Random(seed)
        self.lock = RLock()
        self.people = {}
        self.encounters = {}
        self.serial = 0
        self.last_contact = {}
        saved = {p['id']: p for p in (state or {}).get('people', [])}
        for agent in agents:
            p = saved.get(agent.id, {})
            x, y = p.get('x', self.rng.uniform(1, 9)), p.get('y', self.rng.uniform(1, 9))
            if not all(isinstance(v, (int, float)) and math.isfinite(v) and .7 <= v <= 9.3 for v in (x, y)):
                raise ValueError("Invalid room coordinates.")
            self.people[agent.id] = {'id': agent.id, 'x': x, 'y': y, 'state': p.get('state', 'wandering'),
                                     'goal_x': x, 'goal_y': y}

    def snapshot(self):
        with self.lock:
            return {'width': 10, 'height': 10, 'people': [dict(p) for p in self.people.values()],
                    'encounters': [dict(e) for e in self.encounters.values()]}

    def _move(self, person, x, y, step):
        dx, dy = x - person['x'], y - person['y']
        distance = math.hypot(dx, dy)
        if distance > .001:
            ratio = min(1, step / distance)
            person['x'] += dx * ratio
            person['y'] += dy * ratio
        return distance <= step

    def roam(self):
        with self.lock:
            busy = {pid for e in self.encounters.values() for pid in (e['initiator'], e['partner']) if pid is not None}
            for pid, p in self.people.items():
                if pid in busy:
                    continue
                if math.hypot(p['goal_x'] - p['x'], p['goal_y'] - p['y']) < .3:
                    p['goal_x'], p['goal_y'] = self.rng.uniform(.7, 9.3), self.rng.uniform(.7, 9.3)
                self._move(p, p['goal_x'], p['goal_y'], .22)
                for other in self.people.values():
                    if other['id'] == pid:
                        continue
                    dx,dy = p['x']-other['x'],p['y']-other['y']
                    distance=math.hypot(dx,dy)
                    if .001 < distance < .9:
                        p['x']=min(9.3,max(.7,p['x']+dx/distance*.12))
                        p['y']=min(9.3,max(.7,p['y']+dy/distance*.12))
                p['state'] = 'wandering'

    def encounter(self, available, round_number):
        with self.lock:
            busy = {pid for e in self.encounters.values() for pid in (e['initiator'], e['partner'])}
            ids = sorted(set(available) - busy)
            if not ids:
                return None
            partner = None
            if len(ids) == 1:
                initiator = ids[0]
            else:
                candidates = [(a, b, math.hypot(self.people[a]['x'] - self.people[b]['x'],
                                                self.people[a]['y'] - self.people[b]['y']))
                              for i, a in enumerate(ids) for b in ids[i + 1:]]
                # shortcut: nearby weighted contacts, not social/pathfinding AI; upgrade for obstacles/crowds >10.
                candidates.sort(key=lambda pair: pair[2] + (1.5 if self.last_contact.get(pair[:2]) == round_number - 1 else 0))
                nearby = candidates[:min(3, len(candidates))]
                a, b, _ = self.rng.choices(nearby, weights=[1 / (.1 + c[2]) for c in nearby])[0]
                initiator, partner = (a, b) if self.rng.random() < .5 else (b, a)
                self.last_contact[tuple(sorted((a, b)))] = round_number
            self.serial += 1
            e = {'id': f'enc-{round_number}-{self.serial}', 'initiator': initiator, 'partner': partner,
                 'round': round_number, 'phase': 'approaching', 'speaker': None}
            a = self.people[initiator]
            if partner is not None:
                b = self.people[partner]
                cx, cy = (a['x'] + b['x']) / 2, (a['y'] + b['y']) / 2
                a['goal_x'], a['goal_y'] = max(.7, cx - .44), min(9.3, cy + .44)
                b['goal_x'], b['goal_y'] = min(9.3, cx + .44), max(.7, cy - .44)
                b['state'] = 'approaching'
            a['state'] = 'approaching'
            self.encounters[e['id']] = e
            return dict(e)

    def approach(self, encounter_id):
        with self.lock:
            e = self.encounters[encounter_id]
            arrived = True
            for pid in (e['initiator'], e['partner']):
                if pid is None:
                    continue
                p = self.people[pid]
                arrived = self._move(p, p['goal_x'], p['goal_y'], .55) and arrived
            if arrived:
                e['phase'] = 'talking'
            return arrived

    def speak(self, encounter_id, speaker):
        with self.lock:
            e = self.encounters[encounter_id]
            e.update(phase='talking', speaker=speaker)
            for pid in (e['initiator'], e['partner']):
                if pid is not None:
                    self.people[pid]['state'] = 'speaking' if pid == speaker else 'listening'

    def release(self, encounter_id):
        with self.lock:
            e = self.encounters.pop(encounter_id, None)
            if e:
                for pid in (e['initiator'], e['partner']):
                    if pid is not None:
                        self.people[pid]['state'] = 'wandering'

    def finish(self):
        with self.lock:
            self.encounters.clear()
            for p in self.people.values():
                p['state'] = 'idle'
