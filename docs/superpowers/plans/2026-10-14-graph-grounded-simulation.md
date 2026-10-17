# Graph-Grounded LegisiMate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Do not commit or branch unless the user asks.

**Goal:** Build a mature local-graph simulation with actual OASIS/CAMEL behavior, configurable population, causal room discussion, readable playback and grounded reporting.

**Architecture:** The existing loopback application supervises an isolated Python 3.11 OASIS/CAMEL worker. A local SQLite evidence graph supplies profiles and retrieval; the worker persists platform effects and emits versioned events. A linked room/graph/discussion/report workbench observes those records, rather than causing interactions by proximity.

**Tech Stack:** Existing Python/OpenAI/Pydantic host, Python 3.11 worker with `camel-oasis==0.2.5` and `camel-ai==0.2.78`, SQLite/FTS5, original browser JavaScript, Three.js, a proven graph renderer, unittest and browser fixtures.

**Spec:** [Approved design](../specs/2026-10-14-graph-grounded-simulation-design.md).

**Execution Record:** Tasks 1-7 are implemented within the approved local scope. Current release checks pass: 74 tests in 182.593 seconds, both dependency checks, frontend build/syntax and the Node social-graph regression. Native-engine tests live in `tests/test_engine.py`; legacy conversation/space tests remain regression contracts, not the production scheduler. Browser fixtures use localhost providers, not live Azure. Saved snapshots are byte-identical after reload; legacy reports, citations and exports work. Optional live interviews and an unauthorized paid Azure experiment are not claimed as completed.

## Global Constraints

- Default `persona_count=10`; deployment population ceiling configurable independently of four concurrent provider calls.
- No Zep calls or credentials; Azure remains the only model recipient. No automatic paid retry/restart.
- Keep the reference checkout, current credentials and existing run IDs/actions/reports untouched.
- Separate document facts, synthetic profile/social assumptions, social actions and private observations.
- Validate actual tool effects; neither successful `env.step` nor a draft is proof of a committed action.
- First release preserves interrupted runs but does not promise post-crash CAMEL memory continuation.
- Direct room talk is an explicit extension; no claim of calibrated prediction or full MiroFish parity.

## Review Focus

- Source containing instructions or nonexistent quoted evidence must not gain source-grounded status (Task 2).
- Count above ten, or too few eligible entities, must not silently truncate/fabricate the cast (Task 3).
- Multi-tool decisions that fail after a successful effect must preserve that effect once (Tasks 1 and 4).
- Private group messages and unexposed action IDs must not leak into another actor's observation (Task 4).
- Paused/reconnected viewers and legacy runs must retain every completed action without imaginary history (Tasks 6 and 7).

## Task 1: Supported Real-Engine Worker

**Files:** create `worker/requirements.txt`, `worker/main.py`, `legisimate/engine.py`; add worker checks to `tests/test_engine.py` and local provider helpers to `tests/test_sdk.py`.

**Interfaces:** `Engine.run(run, emit, cancelled)` supervises JSONL worker events; `Engine.available()` reports a supported interpreter/dependency state without a paid request. Worker input is a versioned config/profile/graph summary plus a per-run storage path; secrets are inherited only through the environment, never written into events.

- [x] Add `test_engine_requires_supported_python`, `test_engine_real_tool_effect` and `test_engine_partial_tool_failure`; assert actual SQLite mutation, safe failure outcome, and no fake success from an exception return.
- [x] Run focused SDK/engine checks, using failure output to validate the local adapter path before progressing.
- [x] Create a separately managed Python 3.11 environment, install pinned engine dependencies, and implement the supervisor/worker using OASIS and CAMEL (not reimplemented platform logic). Verify the actual GPT deployment name and tool schema against a local Chat Completions fixture. Preserve the recommender's real dependency requirements.
- [x] Rerun the focused checks with the worker interpreter; confirm no external LLM call was made. Do not proceed with an unavailable worker or silently switch to the old scheduler.

## Task 2: Local Evidence Graph

**Files:** create `legisimate/graph.py`, `tests/test_graph.py`; extend `legisimate/server.py` storage only as needed.

**Interfaces:** `build_graph(config, model) -> dict`; `GraphStore.save(run_id, graph)`, `GraphStore.context(run_id, entity_id, query, limit) -> dict`, `GraphStore.append_effect(run_id, effect)`. Graph objects carry stable nodes/edges, evidence source IDs/spans, synthetic flags and episode/action IDs. Retrieval uses FTS5 relevance plus explicit incoming/outgoing adjacency, not an asserted embedding equivalent.

- [x] Add `test_graph_rejects_invented_source_spans`, `test_graph_adjacency_both_directions`, `test_graph_retrieves_committed_episode` and `test_graph_prompt_injection_is_data`.
- [x] Run focused graph checks and repair the local defects they expose.
- [x] Implement bounded chunked structured extraction with source-span validation, typed edges, durable transactions, full-text search and exact provenance. Synthetic scenario/archetype assumptions stay distinguishable from source evidence.
- [x] Rerun graph tests; assert transaction rollback and no duplicate episode under the same effect identity.

## Task 3: Configurable Graph-Grounded Population

**Files:** modify `legisimate/core.py`, `legisimate/server.py`, `tests/test_core.py`; use the existing graph tests for selection.

**Interfaces:** `prepare_population(config, graph, model) -> list[Agent]`; `Config` separates default population, deploy ceiling, rounds/time and model-call budget. Profiles retain entity/evidence identities, goals, history, topics, speaking style, activity schedule and synthetic facts. Legacy profiles remain readable with their original fields.

- [x] Add population default, above-ten batching, explicit shortfall and grounded actor-context/mapping checks; update only tests whose old hard-ten expectation conflicts with the approved requirement.
- [x] Run focused core and manager population checks; repair the contiguous-ID and legacy Room(max10) defects they expose.
- [x] Implement graph-based selection and bounded profile batches, stable IDs and explicit fictional-archetype choice. Generate exactly the reviewed requested cast; do not equate active actors with population.
- [x] Rerun core/graph checks; verify changing count does not increase provider concurrency or one-response token budget.

## Task 4: Social Decisions, Room Conversations And Durable Outcomes

**Files:** modify `worker/main.py`, `legisimate/engine.py`, `legisimate/server.py`; replace proximity causality in the new engine path; extend `tests/test_conversation.py`, `tests/test_events.py`, `tests/test_space.py`.

**Interfaces:** v2 events include observation IDs, platform/group membership, safe decision reason, canonical tick, platform trace/effect ID and effect outcome. `GraphStore.append_effect` consumes committed public effects; private group effects obey visibility boundaries. Existing event IDs and SSE cursor semantics remain stable.

- [x] Add three-tick native memory/group, membership isolation, empty activity and malformed-tool checks; retain legacy visible-target/self/draft regression coverage.
- [x] Add partial-effect failure, cancellation, duplicate IPC event and empty-tick clock tests; run the focused checks before proceeding.
- [x] Implement scheduled activation through actual OASIS decisions, bounded concurrency, Reddit-owned room group observation, and visible target validation. Preserve live observation timing; control completion order in fixtures only.
- [x] Persist each successful platform effect immediately, detect returned engine exceptions, stop new scheduling on unrecoverable errors, and emit allowlisted diagnostic codes. Preserve completed effects after peers fail. Advance canonical/platform clocks explicitly on empty ticks.
- [x] Rerun focused native-engine and legacy conversation/events/space tests, including a failing third-tick fixture that preserves earlier effects and a successful three-tick fixture. Never present this as a recovered diagnosis of the old run.

## Task 5: Graph Memory, Reports And Persona Inspection

**Files:** extend `legisimate/graph.py`, `legisimate/core.py`, `legisimate/server.py`, `tests/test_core.py`, `tests/test_graph.py`.

**Interfaces:** `generate_grounded_report(config, graph_store, run_id, agents, effects, model, emit, cancelled) -> Report`; bounded retrieval returns only committed source/effect identities. Persona inspection exposes profile assumptions, source links and committed participation. Optional live interviews remain deferred rather than pretending saved traces restore live CAMEL memory.

- [x] Add tests for nonexistent citations, private evidence exclusion, committed episode retrieval, cancellation and graph/worker terminal barriers.
- [x] Run the focused report/graph checks, including no-public-evidence behavior and unknown citation rejection.
- [x] Implement bounded sectioned synthesis from retrieved graph and action evidence; expose report progress, source/action links and profile/evidence inspection. Define local graph completion as a durable transaction barrier, not a simulated Cloud ingestion poll. Optional live interviews are deferred.
- [x] Rerun report/graph checks; preserve old Markdown exports and summary fields.

## Task 6: Linked Workbench And Readable Scene

**Files:** modify `web/index.html`, `web/style.css`, `web/app.js`, `web/room.js`, `web/room.css`; add one local frontend asset manifest/build entry only if needed for Three.js and the graph renderer. Extend the existing fixture server.

**Interfaces:** all views consume versioned backend records; room motion reflects committed membership/interaction changes. A viewer cursor is separate from the live SSE cursor. Graph/person selection links to discussion/evidence/report without paid side effects.

- [x] Exercise browser fixtures for linked selection, readable full speech, graph provenance, paused backlog retention, step/speed controls and live catch-up. Saved legacy runs are covered by the final preservation/reload gate.
- [x] Verify corrected rendering at actual 375, 768 and 1440 CSS pixels. Early screenshot/viewport races are not accepted as valid viewport evidence.
- [x] Replace the hero/card-heavy layout with a compact workbench and unframed Three.js room; add distinct knowledge/social graph views, readable discussion pane, contextual inspector and prominent synthesis.
- [x] Implement playback pause/step/speed and optional interruptible run dwell; distinguish drafts, committed speech, playback and live generation. Preserve all events and reduce motion without hiding evidence.
- [x] Run JS syntax/build checks and browser fixtures; check nonblank canvas pixels, asset rendering, movement/controls, focus, overflow and text overlap on all required viewports.

## Task 7: Integration, Preservation And Release Verification

**Files:** update `README.md`, `run.sh` and existing test fixtures; update this plan's completed checkboxes incrementally.

**Interfaces:** existing `./run.sh --port 8765` continues to launch the configured app; worker prerequisite failures are actionable and do not trigger an old-engine fallback. New runs are versioned and old snapshots remain inspectable.

- [x] Verify restart/interruption and legacy-run regressions; assert all three complete saved snapshots, including the old 22-action failure, remain unchanged after production reload and old report links resolve.
- [x] Run `.venv/bin/python -W default -m unittest discover -s tests -q`, including worker smoke tests, frontend build/syntax and dependency checks: 74 tests, OK.
- [x] Run complete local-provider graph-to-three-tick-to-report browser flow; verify actual engine database effects, room/group correlation and safe third-tick failure handling.
- [x] Request a focused whole-change review, repair verified findings, and rerun affected checks. Do not weaken assertions to claim parity.
- [x] Check for active user work before restarting the app; leave the local server running at http://127.0.0.1:8765. Update docs with real prerequisites, graph differences and any unverified live gates. Temporary fixture server stopped.
- [ ] Run an explicitly bounded live Azure experiment only with separate authorization; report fixture versus live results distinctly. No live Zep verification exists or is needed for this approved local variant.

The unchecked Azure experiment is intentionally deferred: no separate paid-call authorization was provided. It is not a failed release gate and must not be silently executed.