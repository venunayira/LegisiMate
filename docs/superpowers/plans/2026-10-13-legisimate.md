# LegisiMate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax.

**Goal:** Independent local scenario simulator with a hard ten-agent cap and direct OpenAI SDK use.
**Architecture:** One local server, one worker job and SQLite snapshots. Independent persona calls use identical previous-round context; server publishes a completed round atomically and generates a citation-checked report.
**Tech Stack:** Python 3.11+, OpenAI SDK/Pydantic already required by SDK, sqlite3, unittest, vanilla browser UI.
**Spec:** ../specs/2026-10-13-legisimate-design.md

## Global Constraints
- 1..10 agents; 1..10 rounds; default 10 agents/3 rounds; never copy MiroFish implementation.
- <=2,000 scenario characters, <=20,000 source characters; localhost only; one active job/data directory.
- No API secrets in browser, storage or model context; no paid tests.
- No commits/pushes or modifications to the reference checkout.

## Review Focus
- Malformed external JSON cannot bypass count, text or ID restrictions.
- Concurrent starts cannot exceed global ten-persona cap.
- Restart must preserve prior work without replaying paid calls.
- Cancellation/provider failures must not claim successful reporting.
- Cross-origin requests and DOM rendering cannot trigger paid actions or execute input.

### Task 1: Simulation core and SDK adapter
Files: create legisimate/core.py, tests/test_core.py, requirements.txt.
Interfaces: Config.model_validate(dict), prepare(config, model)->list[Agent], run_round(config, agents, actions, model)->list[dict], generate_report(config, agents, actions, model)->Report; Model.generate(output_type, instructions, payload, max_tokens).
- [ ] Write tests for boundaries, overgenerated agents, same-round isolation, reply/citation rejection and SDK refusal.
- [ ] Run .venv/bin/python -m unittest discover -s tests -v; confirm missing core before implementation.
- [ ] Implement bounded schemas, direct Responses parsing, stable round thread pool and citation validation.
- [ ] Run tests; confirm pass without network.

### Task 2: Persistence and local HTTP API
Files: create legisimate/server.py, tests/test_server.py.
Interfaces: Store(path).save/get/list/recover; Manager(store, model).create/start/cancel; make_server(manager, port=8000).
API: GET /api/config, GET /api/runs, GET /api/runs/{id}; POST /api/runs, POST /api/runs/{id}/start, POST /api/runs/{id}/cancel; static asset allowlist.
- [ ] Write persistence/recovery, global exclusivity, cancellation/failure and real local HTTP input/origin tests.
- [ ] Run focused tests; confirm missing server.
- [ ] Implement SQLite snapshots and lock-protected background worker; generic safe failures, interrupted recovery, strict body/Host/Origin checks; exclusive OS lock for live server.
- [ ] Run complete unittest suite; confirm pass.

### Task 3: Minimal usable UI and documentation
Files: create web/index.html, web/app.js, web/style.css, README.md, .gitignore; tests/test_sdk.py for real SDK localhost fixture.
- [ ] Add HTTP static-serving expectations and SDK fixture parse tests; watch failure before implementation.
- [ ] Build responsive form, TXT/MD import, prepared roster, action feed, report with evidence links, history/reload, progress/cancel and actionable errors.
- [ ] Pin installed dependencies, document setup/environment/privacy/limitations and evidence-vs-design changes.
- [ ] Run suite, syntax checks, SDK fixture and real-browser 375px/desktop empty/error workflow.
- [ ] Read connected code for correctness/security/simplicity; attempt fresh reviewer if rate limit allows, record any unavailable verification.

## Execution ledger
Ruling: execute inline following user's 'create our own' continuation; no extra approval round — existing proposed core accepted, remaining defaults disclosed.
Ruling: no Git worktree or workflow helper scripts — outer directory is not a Git repo; reference checkout left clean and separate. No commits without explicit authorization.
Ruling: exploration subagent unavailable twice due provider rate limits; bounded direct source reads and reused REA evidence substitute.
Ruling: workspace scaffold tool cannot see an opened VS Code folder; direct file tools work at explicit user-specified path, so no editor/config repair needed.

## Completed verification — 2026-10-13
- Task 1: complete — six initial core tests failed on missing module before implementation, then passed. Real installed OpenAI SDK 3.28.0 Responses structured parsing verified through localhost HTTP.
- Task 2: complete — missing-server red baseline, then SQLite/recovery/single-job/cancellation/HTTP checks green. Global lock rejected a second production server against the same data directory.
- Task 3: complete — missing-static-asset red baseline, then UI and export checks green. Browser: ten personas, two rounds, twenty actions, report/evidence links, filtering and reload verified; no page errors; HTML-like scenario text did not create images. Overflow checks passed at 375/768/1024/1440px. Eleven-agent form input rejected without creating a run.
- Final checks: `.venv/bin/python -W default -m unittest discover -s tests -v` → 20 tests, OK, no resource warnings; compileall and node --check → exit 0; pip check → no broken requirements; editor diagnostics → no errors; `git -C MiroFish status --short` → clean.
- Regression: maximum-run test exposed unclosed SQLite connections. Added ownership test → FAIL (0 closures, expected 4); changed all Store connections to stdlib closing + transaction contexts → full suite green.
- Maximum workload verified locally: ten personas, ten rounds, one hundred actions, 102 logical model calls, no more than four simultaneous decisions.
- Ruling: port 8000 already occupied; preserved existing service, preview uses 8765. Temporary full-workflow fixture used 8001 and was stopped after browser verification.
- Not checked: live paid OpenAI model quality/rate limits, predictive validity, runtime benchmarks vs MiroFish, dependency vulnerability audit, or independent reviewer (provider dispatch failed). Python runtime verified is 3.14.7, not every supported 3.11+ version.
- REA evidence reused, not regenerated. Source behavior observations and new implementation choices are kept separate in the design and README. No copied reference code or commits/pushes.

## Authorized model setup — 2026-10-13
- User requested reuse of MANTA's GPT-5.4 mini configuration. Confirmed `AZURE_LIGHT_DEPLOYMENT=gpt-5.4-mini`; copied only the matching Azure key, endpoint and deployment to ignored owner-only `.env`, mapped to existing OpenAI SDK environment variables. MANTA unchanged; secrets never displayed.
- Used Azure's documented `/openai/v1/` Responses endpoint with the existing OpenAI client; no extra provider implementation or dependency. Added `run.sh` to explicitly load this project's trusted shell config.
- Launcher tests failed before script creation, then passed; full suite → 22 tests, OK; shell syntax and private file permissions checked.
- Two small live calls verified: structured connectivity response, then actual preparation of one fictional persona (272 reported tokens). No project source/documents sent. Full live ten-agent run and predictive quality remain unverified.
