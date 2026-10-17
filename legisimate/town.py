"""Town conversations: every tick, three randomizers regroup everyone, groups talk at once, views carry forward."""
import random
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Literal

from pydantic import field_validator

from .core import StrictModel

MIN_GROUP, MAX_GROUP, MEMORY_LINES = 2, 5, 16
INSTRUCTIONS = (
    "You are the supplied synthetic person standing in a small group in a town square, talking face to face "
    "about the scenario. Speak in the first person to the people in group, by name when natural. React to "
    "specific points in conversation: agree, push back, ask a question, or share something you heard in earlier "
    "conversations (memories). Let your profession, outlook and openness shape how you hear others; change your "
    "mind only when an argument persuades you, more readily if your openness is high. Never force consensus. "
    "text is one to four natural spoken sentences. view is your honest current opinion on the scenario after this "
    "moment, in one or two first-person sentences; shift compares it with opening_view. If turns_left is 0, "
    "close your part of the conversation. Ground factual claims in your evidence; your biography and beliefs "
    "are synthetic assumptions.")


class Utterance(StrictModel):
    text: str
    view: str
    shift: Literal["unchanged", "softened", "hardened", "reversed"]

    @field_validator("text", "view")
    @classmethod
    def bounded_text(cls, value):
        if not value or len(value) > 1200:
            raise ValueError("utterance_length")
        return value


def form_groups(members, rng):
    """Randomize how many groups form, then each group's size, then who joins which group."""
    count = len(members)
    sizes = [MIN_GROUP] * rng.randint(-(-count // MAX_GROUP), count // MIN_GROUP)
    for _ in range(count - sum(sizes)):
        sizes[rng.choice([index for index, size in enumerate(sizes) if size < MAX_GROUP])] += 1
    shuffled, groups = rng.sample(members, count), []
    for size in sizes:
        groups.append(shuffled[:size])
        shuffled = shuffled[size:]
    return groups


def schedule(config, members):
    rng, plan = random.Random(config.seed), []
    for _ in range(config.rounds):
        groups = []
        for number, group in enumerate(form_groups(members, rng), 1):
            order = rng.sample(group, len(group))
            # Each member's last turn comes after hearing everyone else at least once.
            turns = max(config.conversation_minutes, 2 * len(order) - 1)
            groups.append({"id": number, "members": group, "turns": [order[index % len(order)] for index in range(turns)]})
        plan.append(groups)
    return plan


def town_calls(config, members):
    return sum(len(group["turns"]) for tick in schedule(config, members) for group in tick)


def run_town(config, agents, model, emit, cancelled):
    cast = {agent.id: agent for agent in agents}
    opening = {agent.id: (agent.profile.initial_view if agent.profile and agent.profile.initial_view else agent.perspective)
               for agent in agents}
    memory = {identity: {"view": view, "heard": []} for identity, view in opening.items()}
    failed = Event()
    stopped = lambda: cancelled() or failed.is_set()

    def converse(tick, group):
        lines, previous = [], None
        try:
            for index, speaker in enumerate(group["turns"]):
                if stopped():
                    return
                agent = cast[speaker]
                emit("decision_start", {"agent_id": speaker, "tick": tick, "platform": "town"})
                result = model.generate(Utterance, INSTRUCTIONS, {
                    "scenario": config.scenario, "tick": tick, "minute": index + 1,
                    "turns_left": len(group["turns"]) - index - 1,
                    "you": {"name": agent.name, "role": agent.role, "perspective": agent.perspective,
                            "profile": agent.profile.model_dump() if agent.profile else None,
                            "evidence": agent.graph_context},
                    "opening_view": opening[speaker], "current_view": memory[speaker]["view"],
                    "memories": memory[speaker]["heard"],
                    "group": [{"name": cast[member].name, "role": cast[member].role}
                              for member in group["members"] if member != speaker],
                    "conversation": lines[-12:]}, 700, cancelled=stopped)
                result = Utterance.model_validate(result.model_dump())
                memory[speaker]["view"] = result.view
                effect_id = f"town:{tick}:{group['id']}:{index + 1}"
                emit("effect", {"effect_id": effect_id, "agent_id": speaker, "platform": "town", "kind": "say",
                    "tick": tick, "simulation_minute": (tick - 1) * config.minutes_per_round + index + 1,
                    "visibility": "public", "outcome": "committed", "origin": "decision",
                    "view": result.view, "shift": result.shift,
                    "data": {"content": result.text, "group": group["id"], "members": group["members"],
                             "turn": index + 1, "reply_to_effect": previous}})
                emit("decision_complete", {"agent_id": speaker, "tick": tick, "platform": "town"})
                lines.append(f"{agent.name} ({agent.role}): {result.text}")
                previous = effect_id
        except Exception:
            failed.set()
            raise
        # Members only join one group per tick, so each memory has a single writer.
        for member in group["members"]:
            memory[member]["heard"] = (memory[member]["heard"] + [f"Tick {tick}, {line}"[:500] for line in lines])[-MEMORY_LINES:]

    for tick, groups in enumerate(schedule(config, list(cast)), 1):
        if stopped():
            break
        emit("groups_formed", {"tick": tick, "groups": [{"id": group["id"], "members": group["members"]} for group in groups]})
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(converse, tick, group) for group in groups]
        for future in futures:
            future.result()
        if cancelled():
            break
        emit("tick_complete", {"tick": tick, "simulation_minute": tick * config.minutes_per_round, "successful": True})
    return {"status": "cancelled" if cancelled() else "completed"}
