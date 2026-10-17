"""Indian Courtroom Trial & Multiverse Decision-Tree Simulator:
Fixed Court Officers (Bench, Opposing Counsel, Witnesses) + Configurable Jury Panel,
where each Tick explores a distinct Strategic Branch (Future #1..#N) with live Legal RAG."""
from __future__ import annotations

from threading import Event
from typing import Literal

from pydantic import Field, field_validator

from .legal import retrieve_turn_authorities
from .town import MEMORY_LINES, Utterance

FIXED_COURT_OFFICERS = (
    "Presiding Judge (Bench)",
    "Complainant / Plaintiff Lead Counsel",
    "Accused / Respondent Defense Counsel",
    "Complainant / Plaintiff Key Witness",
    "Accused / Respondent Key Witness",
    "Junior Counsel for Complainant / Plaintiff",
    "Junior Counsel for Accused / Respondent",
)

JURY_SPECIALTIES = (
    "Foreperson of the Jury & Assessor Panel",
    "Jury Member (Banking & Commercial Assessor)",
    "Jury Member (Statutory & Evidentiary Assessor)",
    "Jury Member (Contract & Damages Assessor)",
    "Jury Member (Corporate Governance Assessor)",
    "Jury Member (Financial Forensics Assessor)",
)

BRANCH_STRATEGIES = (
    (
        "Future #1: Threshold Statutory & Procedural Bar Path",
        "Test what happens when Complainant relies on bare statutory presumption (Sec 139 NI Act / Sec 74 stipulated sum) "
        "without documentary timeline proof, and Defense attacks threshold maintainability (30-day notice clock under Sec 138 "
        "Proviso (b), time-barred debt under the Limitation Act, or unproved loss under Sec 73).",
    ),
    (
        "Future #2: Evidentiary Corroboration vs. Commercial Breach Counter-Claim",
        "Test what happens when Complainant produces primary dispatch and ledger records, but Defense counters with substantive "
        "commercial breach (delayed/defective performance under Sec 39 & 55, impossibility under Sec 56, stop-payment on security "
        "cheque prior to debt crystallization, and Proviso to Sec 141(1) director immunity).",
    ),
    (
        "Future #3: The Winning Playbook (Full Statutory + Documentary + SC Precedent Cure)",
        "Test the optimal winning litigation strategy: Counsel proves exact statutory timeline compliance, establishes crystallized "
        "liability or mitigated damages through witness records, distinguishes opposing High Court rulings using binding Supreme Court "
        "ratio decidendi under Article 141, and secures a favourable Jury & Bench Verdict.",
    ),
    (
        "Future #4: Interim Relief, Sec 143A Deposit & Specific Performance Path",
        "Test interim statutory remedies: Sec 143A/148 NI Act interim compensation, Specific Relief Act injunctions, and conditional "
        "bank-guarantee protection.",
    ),
    (
        "Future #5: Compounding, Restitution & Structured Settlement Path",
        "Test court-monitored compounding under Sec 147 NI Act and restitution under Sec 64/65 Indian Contract Act.",
    ),
)

COURT_INSTRUCTIONS = (
    "You are participating in an Indian Courtroom Decision-Tree Simulation (like exploring alternate litigation futures to find "
    "which courtroom strategy wins and which loses). "
    "Speak in the first person in your assigned courtroom role (Presiding Judge on the Bench, Complainant/Plaintiff Counsel, "
    "Accused/Respondent Defense Counsel, Key Witness, or Jury/Assessor Panel Member). "
    "This tick represents the supplied branch_strategy (an alternate litigation path in the decision tree). "
    "React directly to the opponent lawyer's or witness's latest statement: "
    "1. In text, deliver your realistic courtroom statement (2 to 4 crisp sentences) citing specific sections/provisos from "
    "live_rag_authorities and distinguishing or invoking Supreme Court and High Court precedents (under Article 141, Supreme Court "
    "and larger Benches bind High Courts and smaller Benches). "
    "2. In if_opponent_argues, state the exact defense/opponent claim or judicial question this turn responds to (1 concise sentence). "
    "3. In tactical_move, state the concrete legal move or argument to make at this point in the trial (1 concise sentence). "
    "4. In counter_strategy, state the actionable 'What to state & cite' takeaway for a lawyer or law student at this node (1 concise sentence). "
    "5. Set branch_outcome to who currently holds the upper hand in this branch ('complainant_favour', 'defense_favour', or 'balanced_split') "
    "and win_probability (0..100) to the Complainant/Plaintiff's estimated win percentage at this node. "
    "If you are on the Jury Panel, state your finding on whether the statutory ingredients and burden of proof are met in this branch. "
    "If you are the Presiding Judge on the final turn of the branch (turns_left == 0), pronounce the final Bench Verdict & Order for "
    "this branch, stating clearly whether the Complainant/Plaintiff or Accused/Defense wins this future and why."
)


class CourtUtterance(Utterance):
    if_opponent_argues: str
    tactical_move: str
    counter_strategy: str
    branch_outcome: Literal["complainant_favour", "defense_favour", "balanced_split"]
    win_probability: int = Field(ge=0, le=100)

    @field_validator("if_opponent_argues", "tactical_move", "counter_strategy")
    @classmethod
    def bounded_strategy(cls, value: str) -> str:
        if not value or len(value) > 400:
            raise ValueError("strategy_text_length")
        return value


def court_role_for_slot(index_one_based: int) -> str:
    if 1 <= index_one_based <= len(FIXED_COURT_OFFICERS):
        return FIXED_COURT_OFFICERS[index_one_based - 1]
    jury_idx = index_one_based - len(FIXED_COURT_OFFICERS) - 1
    if 0 <= jury_idx < len(JURY_SPECIALTIES):
        return JURY_SPECIALTIES[jury_idx]
    return f"Jury Member (Assessor #{jury_idx + 1})"


def classify_court_seat(role: str | None, index_one_based: int) -> str:
    lower = (role or "").lower()
    if any(k in lower for k in ("judge", "justice", "bench", "magistrate", "presiding")):
        return "bench"
    if any(k in lower for k in ("jury", "juror", "foreperson", "assessor")):
        return "jury"
    if any(k in lower for k in ("witness", "deponent")):
        return "witness"
    if any(k in lower for k in ("defense", "defence", "respondent", "accused", "opposite")):
        return "defense"
    if any(k in lower for k in ("complainant", "plaintiff", "petitioner", "claimant", "prosecut", "appellant")):
        return "petitioner"
    fallback = ("bench", "petitioner", "defense", "witness", "witness", "petitioner", "defense", "jury", "jury", "jury")
    return fallback[(index_one_based - 1) % len(fallback)]


def branch_info(tick: int, total_rounds: int) -> tuple[str, str]:
    idx = (tick - 1) % len(BRANCH_STRATEGIES)
    title, directive = BRANCH_STRATEGIES[idx]
    if tick > len(BRANCH_STRATEGIES):
        title = f"Future #{tick}: Extended Tactical Permutations ({title.split(':', 1)[-1].strip()})"
    return title, directive


def stage_title(tick: int, total_rounds: int) -> str:
    return branch_info(tick, total_rounds)[0]


def schedule_court(config, agents) -> list[list[dict]]:
    by_seat: dict[str, list[int]] = {"bench": [], "petitioner": [], "defense": [], "witness": [], "jury": []}
    for idx, agent in enumerate(agents, 1):
        seat = classify_court_seat(getattr(agent, "role", ""), idx)
        by_seat[seat].append(agent.id)

    all_ids = [agent.id for agent in agents]
    bench = by_seat["bench"] or [all_ids[0]]
    pet = by_seat["petitioner"] or [all_ids[min(1, len(all_ids) - 1)]]
    defn = by_seat["defense"] or [all_ids[min(2, len(all_ids) - 1)]]
    wit = by_seat["witness"]
    jury = by_seat["jury"]

    plan: list[list[dict]] = []
    for tick in range(1, config.rounds + 1):
        title, directive = branch_info(tick, config.rounds)
        # Complete decision-tree path per branch:
        # Judge frames branch issue -> Complainant Lead -> Defense Lead -> Complainant Witness -> Defense Witness
        # -> Junior Counsel rejoinders -> Jury Panel deliberation -> Presiding Judge Branch Verdict last
        base_order = [*bench[:1], *pet[:1], *defn[:1], *wit, *pet[1:], *defn[1:], *jury, *bench[:1]]

        seen = set()
        ordered: list[int] = []
        for aid in base_order:
            ordered.append(aid)
            seen.add(aid)
        for aid in all_ids:
            if aid not in seen:
                ordered.append(aid)
                seen.add(aid)
        # Always conclude every branch with the Presiding Judge delivering that branch's Verdict
        if bench and ordered[-1] != bench[0]:
            ordered.append(bench[0])

        plan.append([{
            "id": 1,
            "stage": title,
            "directive": directive,
            "members": all_ids,
            "turns": ordered,
        }])
    return plan


def court_calls(config, agents) -> int:
    return sum(len(group["turns"]) for tick in schedule_court(config, agents) for group in tick)


def run_court(config, agents, model, emit, cancelled):
    cast = {agent.id: agent for agent in agents}
    seats = {agent.id: classify_court_seat(agent.role, idx) for idx, agent in enumerate(agents, 1)}
    opening = {
        agent.id: (agent.profile.initial_view if agent.profile and agent.profile.initial_view else agent.perspective)
        for agent in agents
    }
    memory = {identity: {"view": view, "heard": []} for identity, view in opening.items()}
    failed = Event()
    stopped = lambda: cancelled() or failed.is_set()

    for tick, groups in enumerate(schedule_court(config, agents), 1):
        if stopped():
            break
        group = groups[0]
        stage = group["stage"]
        directive = group.get("directive") or stage
        emit(
            "groups_formed",
            {
                "tick": tick,
                "groups": [{"id": group["id"], "stage": stage, "directive": directive, "members": group["members"]}],
            },
        )
        lines: list[str] = []
        previous = None
        try:
            for index, speaker in enumerate(group["turns"]):
                if stopped():
                    break
                agent = cast[speaker]
                rag = retrieve_turn_authorities(
                    config.scenario,
                    lines[-3:] + [directive],
                    speaker_role=agent.role,
                    limit_statutes=2,
                    limit_precedents=2,
                )
                raw_ev = agent.graph_context or {}
                compact_ev = {
                    "entity": raw_ev.get("entity"),
                    "relationships": (raw_ev.get("relationships") or [])[:4],
                    "matches": (raw_ev.get("matches") or [])[:4],
                }
                emit("decision_start", {"agent_id": speaker, "tick": tick, "platform": "court"})
                turn_payload = {
                    "scenario": config.scenario,
                    "tick": tick,
                    "branch_number": tick,
                    "total_branches": config.rounds,
                    "hearing_stage": stage,
                    "branch_strategy": directive,
                    "minute": index + 1,
                    "turns_left": len(group["turns"]) - index - 1,
                    "you": {
                        "name": agent.name,
                        "role": agent.role,
                        "court_seat": seats[speaker],
                        "perspective": agent.perspective,
                        "profile": agent.profile.model_dump() if agent.profile else None,
                        "evidence": compact_ev,
                    },
                    "live_rag_authorities": rag["authorities"],
                    "opening_view": opening[speaker],
                    "current_view": memory[speaker]["view"],
                    "memories": memory[speaker]["heard"][-6:],
                    "group": [
                        {"name": cast[m].name, "role": cast[m].role, "seat": seats[m]}
                        for m in group["members"]
                        if m != speaker
                    ],
                    "conversation": lines[-8:],
                }
                try:
                    result = model.generate(CourtUtterance, COURT_INSTRUCTIONS, turn_payload, 650, cancelled=stopped)
                except Exception as exc:
                    if stopped() or type(exc).__name__ not in {"APITimeoutError", "ReadTimeout"}:
                        raise
                    result = model.generate(CourtUtterance, COURT_INSTRUCTIONS, turn_payload, 650, cancelled=stopped)
                result = CourtUtterance.model_validate(result.model_dump())
                memory[speaker]["view"] = result.view
                effect_id = f"court:{tick}:{group['id']}:{index + 1}"
                emit(
                    "effect",
                    {
                        "effect_id": effect_id,
                        "agent_id": speaker,
                        "platform": "court",
                        "kind": "say",
                        "tick": tick,
                        "simulation_minute": (tick - 1) * config.minutes_per_round + index + 1,
                        "visibility": "public",
                        "outcome": "committed",
                        "origin": "decision",
                        "view": result.view,
                        "shift": result.shift,
                        "data": {
                            "content": result.text,
                            "group": group["id"],
                            "stage": stage,
                            "directive": directive,
                            "seat": seats[speaker],
                            "if_opponent_argues": result.if_opponent_argues,
                            "tactical_move": result.tactical_move,
                            "counter_strategy": result.counter_strategy,
                            "branch_outcome": result.branch_outcome,
                            "win_probability": result.win_probability,
                            "rag_citations": rag["citations"],
                            "members": group["members"],
                            "turn": index + 1,
                            "reply_to_effect": previous,
                        },
                    },
                )
                emit("decision_complete", {"agent_id": speaker, "tick": tick, "platform": "court"})
                lines.append(f"{agent.name} ({agent.role}): {result.text}")
                previous = effect_id
        except Exception:
            failed.set()
            raise

        for member in group["members"]:
            memory[member]["heard"] = (
                memory[member]["heard"] + [f"Tick {tick} ({stage}), {line}"[:500] for line in lines]
            )[-MEMORY_LINES:]

        if cancelled():
            break
        emit("tick_complete", {"tick": tick, "simulation_minute": tick * config.minutes_per_round, "successful": True})

    return {"status": "cancelled" if cancelled() else "completed"}
