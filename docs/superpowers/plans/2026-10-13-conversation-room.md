# Conversation Room Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. User approved direct implementation defaults.

**Goal:** Streamed human-shaped conversation room with genuine sequential replies, parallel independent lanes and visible final synthesis.
**Architecture:** Existing local server/SDK/SQLite; rotating paired lanes plus durable SSE events. Vanilla SVG/CSS room is a presentation of actual dialogue, not an extra agent environment.
**Tech Stack:** Existing Python/OpenAI/Pydantic, SQLite, EventSource, vanilla SVG/CSS/JS.
**Spec:** ../specs/2026-10-13-conversation-room-design.md

## Global Constraints
- Hard cap 10 agents, 10 rounds; 2 + agents*rounds logical calls; at most 4 SDK streams.
- No MiroFish copied implementation/assets; preserve saved runs and private configuration.
- Provisional deltas cannot be used as evidence/reply targets; no auto replay or paid verification runs.

## Review Focus
- Partial/failed streams cannot produce finalized turns or cited findings.
- Within-lane replies wait for exact parent; concurrent lanes share no partial content.
- SSE reconnect replays without repeating model calls or duplicating displayed turns.
- Cancel/failure retains committed turns and terminally clears all drafts.
- Old reports and 375px/reduced-motion UI remain usable without unsafe HTML.

### Task 1 — Streamed paired dialogue
Modify core.py, test_core.py, test_sdk.py; add tests/test_conversation.py.
Interfaces: Model.generate(..., on_delta=None, cancelled=None); run_round(..., emit=None, on_action=None); generate_report(..., emit=None, cancelled=None).
- [ ] RED: test sequential parent visibility, parallel lanes, SDK text deltas/final validation and cancellation.
- [ ] GREEN: native partial JSON, SDK stream context, bounded rotating pairs/turn metadata, richer backward-compatible Report.
- [ ] VERIFY: all core and real SDK fixture tests green; update prior tests for intentionally replaced round-only semantics, never suppress checks.

### Task 2 — Durable SSE events
Modify server.py/test_server.py; add tests/test_events.py.
Interfaces: Store.append_event/events/save_event; Manager event condition; GET /api/runs/{id}/events.
- [ ] RED: event order/cursor persistence, terminal SSE, committed partial progress and safe stream errors.
- [ ] GREEN: atomic finalized-turn snapshot/events; notify readers; heartbeat, bounded clients, terminal close; disconnect doesn't cancel job.
- [ ] VERIFY: full suite, GET safety, cancellation/failure/restart.

### Task 3 — Room, live transcript and final synthesis
Modify web/index.html/app.js/style.css; add web/room.js/room.css; update static allowlist and fixture/test harness.
- [ ] RED: UI asset/SSE fixture expectations before implementation.
- [ ] GREEN: human SVG figures, spatial lanes and speaker bubbles, real event state, transcript incrementally updated; saved-run replay labeled recorded; synthesis tab and summary jump.
- [ ] VERIFY: browser fixture, existing election saved report, live draft before completed action, reply/citation navigation, old-run compatibility, mobile and reduced-motion checks.

## Ledger
Ruling: execute inline in user-specified folder; not a Git repository, no worktree/commit/push or private config edits.
Ruling: old atomic-round semantics intentionally replaced with per-turn commits; failed/cancelled partial rounds stay visible, no silent deletion.
Research complete: actual summary present but buried; reference concurrency/whole-record polling corroborated by read-only Explore subagent. REA artifact analysis not rerun since complete source exists.

## Verified completion
- Task 1 complete: missing stream/dependency tests observed failing; paired-lane and real SDK streaming tests now pass. Native Pydantic partial JSON handles Unicode/escaping; exact partner target validated; cancelled/failed drafts never finalized. One/odd/ten-agent cases and logical-call ceilings retained.
- Task 2 complete: event storage/SSE missing baseline failed; durable ordered cursor replay and per-turn snapshot/event commits pass. Cancel-after-parent starts no dependent turn; failed reply retains parent in partial round; recovery clears drafts and never replays generation.
- Task 3 complete: missing room UI contract failed before assets. Native SVG people, perspective floor/shadows, speaking/listening cues, genuine event-driven bubbles, transcript and prominent synthesis. Existing saved report compatibility verified; duplicate old-summary rendering removed.
- Full suite: `.venv/bin/python -W default -m unittest discover -s tests -v` → 33 tests OK, no warnings. Both JavaScript syntax checks and pip check pass; editor diagnostics no errors; reference MiroFish working tree clean.
- Browser proof: MutationObserver samples during actual SDK localhost SSE delivery recorded 71 live render samples, maximum two simultaneous lanes; partial speech text before any committed action. Eight finalized turns with eight unique IDs; recorded playback labeled; evidence link switches to transcript. No page errors.
- Existing user election run preserved: completed, 10 people, 30 turns; final synthesis selected on open with summary preview. Room overflow tests: 375/768/1024/1440px all content width equals viewport; reduced-motion animation is none.
- Ruling: browser click stability/time-sensitive waits were flaky; verified keyboard controls, fixture-only API setup and event/render observation instead of inferring from screenshots. No private source or paid Azure simulation sent. User's existing live run was read only.
- Ruling: fresh final reviewer dispatch failed at provider; direct connected-code review and added failure/cancellation/recovery regressions substituted. REA source exploration subagent succeeded. No dependency vulnerability audit, new live Azure streaming run, voice/realistic 3D assets or predictive evaluation performed.

## Live user run observation and final guards
During final refresh, user drought run 8c348f011705460586ce843de0b5bac8 was found failed with ValidationError after one full round. Ten finalized actions retained, round-two drafts aborted. Exact validation cause unavailable from retained safe trace. SDK source confirms parsing occurs at text.done. Reasoning-token exhaustion is a hypothesis, not a proven diagnosis. Added explicit reasoning.effort=none for configured GPT-5 short-turn calls and safe validation field/type diagnostics. Tests failed before guard changes (missing reasoning param; generic error hid json_invalid), then pass in full suite. No retry or paid diagnostic run performed; failed record remains intact. Final suite count 35; earlier 33-test entry is historical.
