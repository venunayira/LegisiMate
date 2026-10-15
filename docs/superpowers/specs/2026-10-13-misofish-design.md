# Misofish: ten-agent local simulation

## Intent and authorization
Build an independent small MiroFish-inspired scenario exploration app. User requirements: no copied source/logic, at most 10 agents, simpler implementation, OpenAI SDK, REA/Superpowers/Ponytail workflow. User authorized creation after the proposed core; implementation defaults below are builder decisions, not separately user-specified requirements.

## Evidence
REA skill routes complete source repos to ordinary source tools. Reused artifact evidence ev_711b92d711b7b004654c82e90b66b7e09bbcad40b133e4b9fd5c64425fc69ff1 (.rea/mirofish-frontend-2048-summary.json): static observations only, partial semantic coverage after heap exhaustion. No new REA runtime was executed. Source inspection of MiroFish/backend/app/services/simulation_manager.py:242, simulation_runner.py:370 and api/report.py:80 confirms graph-dependent preparation, process scheduling and report finalization barriers. Full earlier investigation: ../../..//MIROFISH-REVERSE-ENGINEERING.md. MiroFish is AGPL-3.0; no source, prompts, assets or implementation copied into this app. This is not a legal assurance about licensing.

## Design decisions
- Python 3.11+, standard-library HTTP server/SQLite/thread pool, vanilla single-page frontend. OpenAI SDK plus its Pydantic schema dependency; no agent framework or frontend build.
- Official Responses API structured-output parsing, default gpt-4o-mini, operator-configured model. SDK retries disabled, 60-second per-request timeout. No tools, browsing, filesystem access or child processes for model personas.
- Scenario <=2,000 chars, optional source <=20,000 chars; TXT/Markdown imported in browser. No PDF, OCR, cloud graph, social-platform emulation, live interviews, deployment or forecast accuracy claim.
- Agent count integer 1..10, default 10; rounds integer 1..10, default 3. Model-generated personas must match requested count. Agent IDs assigned by application, never by model. Hard cap validated at intake, generation and execution; only one active job/server for the local data directory.
- Prepare personas first for review, then explicitly start. Each persona makes one action per round from the identical previous-round feed (last 20 actions) plus its own last action. Four concurrent SDK calls maximum; stable publication order. No participant sees same-round actions.
- Immutable numbered actions with post/reply/pass, short text, stance and reply target. Replies must reference an existing visible non-pass action. Report findings cite existing action IDs; citation existence is checked, factual entailment remains human review.
- Local SQLite JSON snapshots persist completed rounds, usage token totals and safe errors. Lifecycle: preparing -> ready -> running -> reporting -> completed; failed/cancelled/interrupted terminal. No automatic replay after restart. Cancellation waits for in-flight requests, saves completed round then stops without report.
- Maximum logical model calls per run = 2 + agents * rounds (102 at maximum). Bounded output tokens per call; no claim about dollar cost or deterministic model output.
- Localhost-only macOS/Linux tool; exclusive data-directory server lock. Host/Origin checks and JSON-only mutations defend browser cross-origin abuse; textContent rendering, CSP, request limits and parameterized SQL. Credentials environment-only, never client/prompt/storage. Source, personas and action text are sent to configured OpenAI endpoint when user starts; local storage is plaintext and user-managed. No paid calls during automated checks.

## Acceptance
Tests prove cap bypass rejection (including bool/string/fraction), malformed provider output, response refusal/incomplete output, round isolation, reply validity, citation checks, cancelled/failed/interrupted persistence, duplicate/global start rejection and HTTP boundaries. Verify real SDK parsing against a localhost fixture and real-browser empty/error flow; live paid model quality is explicitly unverified.
