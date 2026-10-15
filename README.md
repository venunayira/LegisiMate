# Misofish

A local graph-grounded scenario workbench: **source evidence -> rich synthetic personas -> native OASIS social actions and room discussion -> cited synthesis**.

Default population: **10**, editable in the UI. `MISOFISH_MAX_AGENTS` controls the deployment ceiling independently (default 1,000). Four concurrent model calls are shared across both platforms, with an explicit end-to-end call budget. Increasing the population does not force everyone to act each tick.

## Run

This workspace is provisioned. Start the configured app with:

```sh
./run.sh --port 8765
```

Open http://127.0.0.1:8765. The launcher reads only this project's trusted, ignored `.env`. Keep credentials there or in the server environment, never in browser inputs or chat. `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OPENAI_MODEL` configure both host and worker. The endpoint must support Responses structured output and Chat Completions tool calling. The current operator configuration uses Azure GPT-5.4 Mini. Full engine verification uses localhost providers; a separately authorized live four-person profile batch also passed count, identity and evidence-reference validation. No full paid Azure simulation was launched for validation.

### Fresh Installation

The host needs Python 3.11+; the isolated engine requires Python 3.11. Node/npm are used only to build local browser assets.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install uv==0.9.5
export UV_PYTHON_INSTALL_DIR="$PWD/.runtime"
.venv/bin/uv python install 3.11.14 --no-bin
.venv/bin/uv venv --python 3.11.14 .worker-venv
.worker-venv/bin/python -m ensurepip --upgrade
.worker-venv/bin/python -m pip install -r worker/requirements.txt
npm ci
npm run build
```

The worker pins `camel-oasis==0.2.5`, `camel-ai==0.2.78` and `mcp==1.26.0`. The host and system Python are not replaced. `MISOFISH_WORKER_PYTHON` can identify another equivalently provisioned worker interpreter.

The default Twitter recommender additionally needs its public tokenizer and approximately 1.12 GB of model weights. Download them once; runs use the workspace cache **offline**, without transmitting source material to Hugging Face:

```sh
HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 .worker-venv/bin/python - <<'PY'
from pathlib import Path
import truststore
truststore.inject_into_ssl()
from huggingface_hub import snapshot_download
snapshot_download("Twitter/twhin-bert-base", token=False,
    cache_dir=str(Path.cwd() / ".cache" / "huggingface"),
    allow_patterns=["*.json", "*.model", "*.safetensors"], max_workers=2)
PY
```

Ordinary HTTPS worked on this Mac; the Xet transport returned HTTP 403. Certificate verification remains enabled. Missing weights are rejected before preparation spends model calls. Explicitly selecting **Reddit + Shared Room** avoids the Twitter prerequisite without substituting a fake recommender.

## Experiment Workflow

1. Supply a scenario and optionally UTF-8 TXT/Markdown source context. Choose population, platform mode, ticks, simulation time, activity seed, call budget and optional generation dwell.
2. Accept the endpoint-sharing notice and prepare. Typed graph nodes/relations retain exact source quotations and character offsets. Profiles receive relevant graph adjacency and retrieval context, plus a profession, goals, beliefs, background, interests, speaking style, activity schedule, an outlook (optimistic, pessimistic, skeptical or pragmatic), openness to persuasion (low, medium or high) and a first-person opening view.
3. Review the cast and graph, then explicitly start. **Source Actors Only** rejects a population shortfall; **Graph + Fictional Archetypes** generates clearly synthetic people informed by the evidence, not purported real-person opinions.
4. Observe Town, Graph, Discussion and Report. The knowledge graph is separate from the social/group graph. The inspector links personas to evidence, opening and final views, and committed participation.
5. Pause, step, change playback speed, replay or catch up to live. These controls do not cancel generation or drop its backlog. Full speech remains readable below the map. Every persona is drawn; crowded labels are hidden rather than overlaid.
6. Export evidence and synthesis. Private group effects are labelled in the complete export but excluded from the public report.

The Town is a top-down 2D map with homes, a Shared Room hall (the group chat) and a Public Board (public posts). Movement only shows committed engine effects: a reply makes its author walk to the person being answered, group messages are spoken at the hall, posts at the board, and final interviews at home. The speaker's bubble reveals one word every 400 milliseconds at 1x after the walk; the speed control also speeds walking. Pause freezes the reveal, and automatic playback waits for the walk, the complete message and a reading pause. Reduced-motion settings and Pause Scene Motion skip walking; reduced motion also shows complete text immediately. This is paced playback of committed native speech, not provider token streaming.

Who meets whom is decided by the engine, as in MiroFish: active personas are sampled from their activity schedules, see a recommended feed or the shared group, and choose whether to post, reply, repost, like, follow or stay quiet. Their CAMEL memory carries what they read and said into later ticks. After a completed simulation, every persona who took part is interviewed through OASIS on each platform. Each answer starts with a self-reported shift (held, softened, hardened or changed sides). The report summarizes how views changed; shift counts cover every interview. These are self-reports, not measured beliefs.

### Town Conversations (default)

This mode is a deliberate extension beyond MiroFish, which only simulates social media. Every tick, three seeded randomizers regroup the whole population:

1. Choose how many groups form, so every group has 2-5 people.
2. Choose each group's size.
3. Choose who joins which group.

All groups talk at the same time, with up to four model calls at once. Each conversation lasts **Conversation Minutes** lines (default 5), but always long enough for every member's last line to come after hearing everyone else. Each line returns the speech plus the speaker's private current view and shift from their opening view. A persona's latest view and the last 16 lines they heard travel with them into the next tick's random group. The Town shows every group gathering and talking at once, with one bubble per group. The inspector shows each persona's thought evolution, and the report uses each person's last view as their final thought. Starting is refused unless the remaining budget covers every planned line plus the report. **Random Seed** makes the grouping reproducible. Town mode does not need the OASIS worker or Twitter weights.

In Twitter/Reddit mode, an action on an unseen post, a self-like or another platform rejection now rejects only that action. The agent sees the failure, an `action_rejected` event is saved, and the run continues. Previously one such action stopped every other agent's decision and failed the run.

## Actual Engine Behavior


## Bounds, Privacy And Recovery

Scenario: 2,000 characters; source: 20,000. Ticks: 1-10. Profile batches contain at most four actors, independent of the population ceiling. The default 500-call budget covers preparation, engine calls, final interviews and reporting. Starting requires enough remaining budget for one decision, one interview per persona per platform, and the report; decisions cannot spend the interview reserve. Reported token totals include host and worker responses. Failed/incomplete provider requests can incur charges not represented in returned usage.

This is a single-user loopback tool, not an authenticated deployment. It binds `127.0.0.1`, allowlists static assets/Host, rejects cross-origin mutations, bounds JSON requests, parameterizes SQL, and renders untrusted text without HTML. Scripts and fonts are served locally. Do not expose it through a public tunnel.

Source, profiles and discussion are transmitted to the **configured model endpoint** only with the workflow's consent. `store=False` is not a guarantee of provider non-retention. Local SQLite, worker profiles and traces are plaintext; use non-sensitive material. Third-party prompt logging is disabled. Credentials stay in the inherited environment, not events or prompts.

Existing saved run IDs, actions and reports remain inspectable/exportable. Restarted active runs become interrupted; committed work is preserved and never automatically replayed. Live CAMEL memory is not claimed to be recoverable after a crash. Legacy proximity runs remain historical records, not silently restarted in the new engine.

Host and native-worker requests use a 180-second timeout, configurable with `MISOFISH_MODEL_TIMEOUT`. Retries remain disabled. Provider timeouts are recorded as `provider_timeout`, with the failed stage, instead of implying that the endpoint or credentials are wrong. Increasing the deadline does not guarantee provider availability.

No calibrated prediction, representative sampling, semantic fact-entailment guarantee, PDF/OCR, audio or interactive interview endpoint is claimed. Review quotations and cited speech yourself: an existing citation does not prove its claim. Synthetic biographies and inferred relationships are not verified real-world facts.

## Verification

The 2026-10-15 profile failure was a provider/runtime contract mismatch: a live response returned three actors for four requested slots, assigned source identities in fictional mode, and a later request exposed unknown evidence references. Provider schemas now enforce exact per-batch counts, null-only fictional identities, assigned grounded identity choices and supplied evidence IDs. Runtime checks remain in place. Safe stage/error codes are saved for future failures. Old failed snapshots remain unchanged and are not automatically retried.

```sh
.venv/bin/python -W default -m unittest discover -s tests -v
.venv/bin/python -m pip check
.worker-venv/bin/python -m pip check
node --check web/app.js
node --check web/room.js
node tests/check_social_graph.js
node tests/check_room_speech.js
npm run build
```
The current operator configuration uses Azure GPT-5.4 Mini. The complete live production preparation now passed graph extraction and all three profile batches: ten valid personas, five requests, status `ready`, no simulation actions. Run `52c4f83a09154196b26b90252ac80edd` is saved for review. No full paid Azure simulation was launched for validation.

The current regression run passes **94 tests** (222.935 seconds), plus the Node town-speech and social-graph regressions and both environment dependency checks. Graph provider schemas bind source IDs, ontology labels and exact evidence excerpts; local quote/endpoint checks remain mandatory. Prior saved snapshots were hash-checked unchanged after the successful live preparation.

## Evidence And Architecture

- [Reverse-engineering evidence](MIROFISH-REVERSE-ENGINEERING.md): observed source/dependency behavior, inferences and unknowns, including the second-pass reconstruction.
- [Approved design](docs/superpowers/specs/2026-10-14-graph-grounded-simulation-design.md).
- [Implementation and verification plan](docs/superpowers/plans/2026-10-14-graph-grounded-simulation.md).
- [worker/main.py](worker/main.py): actual engine adapter and bounded native lifecycle.
- [misofish/graph.py](misofish/graph.py): source graph, provenance and public episode retrieval.
- [misofish/core.py](misofish/core.py): strict profiles, SDK requests and synthesis.
- [misofish/server.py](misofish/server.py): persistence, lifecycle and local API.
- [misofish/town.py](misofish/town.py): random regrouping, parallel group conversations and evolving views.
- [web/room.js](web/room.js): display-only 2D town; it does not determine social behavior.

REA v37 explicitly routes a complete source repository to ordinary source tools. The second pass inspected the reference revision and exact installed engine wheels, then verified native behavior with real libraries. This is not a claim that static REA evidence observed the runtime. The AGPL-3.0 reference checkout remains separate and untouched; this implementation uses installed libraries and independently written local adapters. This is not licensing advice.