# LegisiMate — Project Knowledge

Working understanding of product intent and implementation, reconciled with the original Copilot chat on 2026-10-16 and updated for the restored full-hearing workbench on 2026-10-17.
Status tags: **[Chat]** original conversation; **[V]** inspected source or manifest, not necessarily executed; **[R]** historical claim not independently verified; **[?]** unresolved. Setup observations below are from the earlier local-start attempt, not a new health check.

## Evidence And Authority

- Primary intent source: the Downloads JSON export for session `3d83f095-ab5e-4432-a441-83df98a92c70`, 86 turns, 67,110,578 bytes. SHA-256: `1378f84478573c99b0bb5fcc12ba1bc4fe34d5ec4e4f43abf8af39467052d3d9`.
- Parsed the original JSON locally. All 86 user-message texts and assistant-prose sequences matched the repository export before its removal. Equality was checked for those fields, not every tool payload.
- Read the requirements chronologically, the complete legal-design request in turn 75, and relevant assistant handoffs. Turn numbers below refer to the original Downloads export. Public chat-export files were removed from the working tree for privacy; the original Downloads file and Git history remain unchanged.
- Later direct user instructions supersede earlier ones. Prior assistant completion claims and advice from another AI pasted into the chat are not independent proof. Current source determines what is implemented; tests and live evaluation determine what actually works.

## Current Local Workbench (2026-10-17)

- The user confirmed a registered team, selected Sustainability & Social Impact, delegated the jury/cleanup choices and deferred deployment. The new home page is a Section 138 case-preparation workbench; the original simulator and its records remain at `/legacy`. The architecture described in sections 1-10 below is the historical legacy baseline unless explicitly updated here.
- The latest direct user request names the project LegisiMate throughout, including its folders and package. The product vision spans constitutions, legislation, regulations and relevant case law for every country with a constitution. The current selected Indian-law slice is only a demo/POC, not a complete national corpus or global implementation.
- Every home-page load automatically runs a six-step on-page tour that spotlights the real case form (the rest of the page is inert): load the sample, what the sample filled in, each date and record (read from the form), the calendar review results (read from the live timeline), supporting notes plus the inline New case / Add text file route for an own case, then hearing depth and consent. It is not an upload popup. **Skip tour** or Escape closes it and returns to the previous tab (or the restored case's brief); **Take the tour** in the header restarts it. No remembered dismissal, automatic consent or model analysis is used. Loading the sample starts a new case, so asynchronous saved-case restoration cannot overwrite it; a restoration that finishes mid-tour keeps the form visible.
- [legisimate/casework.py](legisimate/casework.py) owns consent validation, confirmed-input timing checks, bounded research, three case-specific independent hearings and a preparation brief. `build_hearing()` schedules nine core roles: Magistrate, two leads, two parties, two witnesses and two juniors. Each path has openings, parties, witness examination/cross-examination, rebuttals and a bench assessment. One shared lock excludes simultaneous legacy and casework use of model-call accounting.
- `rebuttal_rounds` accepts strict integers 1-3 (default 2); `review_panel_size` accepts 0-3 (default 0). Assessors are educational, never an authentic Indian jury or judicial authority. Per-path statements are `14 + 4*r + p`; all three paths plus at most six planning/research/brief calls set the budget. Defaults: 66 statements / 72 calls; maximum: 87 statements / 93 calls. Party and witness roles may use only supplied material; absent testimony remains absent.
- [web/cases.html](web/cases.html), [web/cases.css](web/cases.css) and [web/cases.js](web/cases.js) provide six views: intake, brief, argument paths, decision tree, courtroom and research/sources. The Cytoscape tree groups actual speeches by stage, with keyboard-accessible selection, quotations and exact-statement replay. It visualises generated alternatives, not recursive strategy search. Replay includes previous/next and statement jump. Text extracts are supported; PDF/image extraction and multilingual output are not implemented.
- Calendar checks leave unknowns unresolved, reject future completed-event dates and distinguish calendar months from 30 days. They do not authenticate debt records, service or cheque validity, or implement holidays and judicial condonation. Supportive model assessments are qualified when inputs are missing or need review.
- A live sample exposed paraphrased quotation failures. The model now selects source-specific passage IDs; the server attaches exact corpus text and verifies the pairing. The provider accepts this contract. Text matches are not legal-interpretation or good-law verification. Regression tests and captured responses support offline iteration without repeated full live runs.
- The full live verification used the configured OpenAI-compatible provider. Gemini/Vertex adapter code and Cloud Run/Firebase packaging now exist in the repository, but were not deployed or exercised by this restoration. Nationwide corpus expansion and validated outcome prediction remain unimplemented. The research loop uses typed action selection, not a claim of native provider function calling or ADK integration.
- Case records are plaintext in the `casework` table of `data/runs.db`. Saved legacy records are not migrated or erased. Explicit consent is required for case analysis; the UI's calendar preview does not call the model. The user subsequently authorized committing and pushing the local workbench and chat-export cleanup. Git history is preserved without rewriting or force-pushing.
- Verification for this restoration: `.venv/bin/python -W default -m unittest discover -s tests -q` passed all 124 tests, including the optional legacy engine. Node regressions cover complete tree projection, unchanged stored hearings, full-cast seating, label bounds, educational review and legacy playback. Fixture browser runs completed 69- and 87-statement cases, including issuer-side maximum settings, cancellation, tree clicks, exact-statement replay, source opening, export and reload. Maximum-cast labels/captions were contained and non-overlapping at 390px; desktop was checked at 1440px. Canvas pixels confirmed nonblank content.
- The complete fictional live run `de055d87693347628092387a1ec21789` used `gpt-5.4-mini`: 10 participants, 23 statements in each of three paths, 73 of 75 allowed calls, completed brief/export, and 206/206 source-text quotation matches. A sampled witness answer explicitly preserved missing bank/postal/court records. Text provenance is not legal correctness or good-law verification. Existing saved cases remain unchanged; the older three-turn-per-path case still renders.
- Presentation SVG root cause: nested Lucide SVGs had no explicit `width`/`height` attributes and inherited the diagram viewport despite 19px CSS dimensions. Explicit 24-unit viewports reduced the oversized 230px-plus glyphs to their intended approximately 19px size. The deck now illustrates complete hearing stages and embeds the six-view workbench. All 14 chapters fit at 1600x1000 and navigate without page-wide overflow at 390px. Stage playback, document dialogs, image expansion and both architecture traces passed.
- [LegisiMate-Proposal-Deck.pptx](LegisiMate-Proposal-Deck.pptx) and its PDF are built on the organiser's AI Builder Cup submission template (16 template slides; the instruction slide and the empty spare slide were removed, leaving 14). The PDF was exported by Microsoft PowerPoint and every page was rendered and reviewed. The earlier interactive HTML deck was retired; it remains in git history.

## 1. What it is, in one paragraph

A single-user, loopback-only web app (Python stdlib HTTP server + vanilla-JS UI) that takes a **scenario** (free text, max 2000 chars) plus optional **source text** (max 20,000 chars), asks an **OpenAI-compatible LLM** to turn it into an evidence graph and a cast of personas, and then has those personas speak turn by turn while an LLM generates each line. LegisiMate started as a generic "social simulation" tool (a local re-implementation of the MiroFish idea: documents -> graph -> personas -> simulated discussion -> report). LegisiMate is the later specialisation: an **Indian courtroom simulator** (`platform_mode="court"`) where each simulation tick is one litigation "future" (an outcome branch) and every turn is grounded by **SQLite FTS5 retrieval over Indian statutes and judgments**. [V]

The intended product is an Indian-jurisdiction litigation strategy simulator: given a case, explore alternative arguments and responses for either side, inspect which paths end in favourable or adverse outcomes, and use those paths for case preparation or legal education. Prediction for practising lawyers is an explicit ambition, not something to erase from the requirements: in turn 75 the user says "it will be a predictive tool," and in turn 84 describes "what has to [be] stated when" and planning for winning and losing futures. It is not merely a generic persona conversation or a courtroom animation. The present implementation is a bounded prototype of that goal; its LLM-generated win percentages are not calibrated predictions. [Chat + V]

### How The Intent Evolved

| Chat | Requirement or decision | Current interpretation |
| --- | --- | --- |
| Turns 1-3 | Study MiroFish; build a simpler independent implementation using the OpenAI SDK, initially capped at 10 agents. | MiroFish is the reference for the pipeline, not a requirement to copy its code or retain every external service. |
| Turns 21, 51, 56 | Natural reactions, parallel independent discussions but sequential replies, visible people, slow speech and final synthesis; fix third-round failures. | Inspectable interactions and readable playback are central requirements, not decorative extras. |
| Turn 58 | Preserve graph/persona depth; 10 is the default, with editable population. | Supersedes the hard 10-person cap. The approved local graph replaces Zep; OASIS remains for social-platform modes. |
| Turns 67-68 | Top-down people with professions, outlook and evolving views; randomize group count, sizes and members each tick. | Explains the separate town mode. "Five minutes" became bounded dialogue turns, not five minutes of real-time simulation. |
| Turn 70 | Retain internal registry URLs for another developer in the organisation. | Do not bypass the approved registry to make setup easier. |
| Turn 72 | Move to Indian case-fighting scenarios; investigate English Supreme Court/High Court data, tribunals and constitutional coverage. | Broad product direction. S3 inventory is data discovery, not an already integrated national legal corpus. |
| Turn 75, followed by implementation approval in turn 76 | Start with a domain-focused extraction rather than downloading everything. The plan selects NI Act cheque dishonour and contract breach, plus related law, from SC/Delhi/Bombay. | The two-domain corpus is deliberate PoC scope, not evidence that full national coverage has been delivered. Tribunal OCR and Qdrant snapshots were explicitly deferred. |
| Turn 79 | "ACTUAL COURT CASE simulation": lawyers react to opponents using retrieved law and previous cases; judge and jury participate. | Requires adversarial, evidence-backed courtroom interaction, not renamed town personas. |
| Turn 84 | Realistic 2.5D courtroom, non-occluding bubbles, fixed officers plus selectable jury; three ticks mean alternative decision-tree futures and a strategy playbook. | Supersedes both the earlier top-down generic room preference and the prior interpretation of ticks as successive stages of one trial. |

### Chat-To-Code Correlation

| Intended capability | Implementation evidence | Alignment and limit |
| --- | --- | --- |
| Case facts -> source evidence -> personas | [legisimate/graph.py](legisimate/graph.py), [legisimate/core.py](legisimate/core.py) | Ontology, quote-validated graph and batched profiles exist. If source text is present, graph extraction targets that source, not an independently extracted combined facts-and-law graph. |
| Opponent-aware arguments grounded in real law | [legisimate/court.py](legisimate/court.py), [legisimate/legal.py](legisimate/legal.py) | Each turn receives recent statements and freshly retrieved statutes/precedents. It is FTS5/BM25 with metadata boosts, not dense-vector retrieval or a learned legal reasoning engine. |
| Fixed court roles and selectable jury | [legisimate/core.py](legisimate/core.py), [web/app.js](web/app.js) | UI converts jury count to 7 fixed officers + jury; population preparation enforces exact assigned roles. Jury/assessors are the requested simulation device, not evidence that the model faithfully reproduces all Indian court procedures. |
| Alternative litigation futures | [legisimate/court.py](legisimate/court.py) | Five preset branch directives, reused for branches 6-10. Views and memory carry across branches. No independent-world reset or search over competing next moves. |
| What to say, counters, outcomes | [web/app.js](web/app.js) | Structured tactical cards and a root -> future -> linear sequence of turns -> verdict graph exist. The graph visualises generated hearings; it does not drive a branching strategy search. |
| Find a winning path rather than assert one | [legisimate/court.py](legisimate/court.py) | Gap: Future #3 is already called "The Winning Playbook" and directs a favourable verdict. Generated percentages and narrative outcomes are not discovered or calibrated success rates. |
| Human-readable, court-like presentation | [web/room.js](web/room.js) | Canvas 2D drawing simulates 2.5D depth, seats, gallery and role-specific attire. Slow speech is a word-by-word client reveal of completed turns, not streaming courtroom model tokens. Current browser appearance was not re-tested. |
| Final synthesis and evidence inspection | [legisimate/core.py](legisimate/core.py), [web/app.js](web/app.js) | Generic grounded report, final views and citation navigation exist. Findings must cite supplied IDs; legal entailment and the best litigation strategy are not independently verified. |
| Robust multi-round execution | [legisimate/server.py](legisimate/server.py), [tests/test_open_india_law.py](tests/test_open_india_law.py) | Budgets, committed events, cancellation and a three-branch fake-model test exist. Historical chat claims of successful tests/live runs do not establish current local readiness or live-model reliability. |

## 2. How a run works end to end

```
Browser (web/*)  --POST /api/legal/retrieve-->  legal.retrieve_legal_dossier()  -> "source" text (statutes + precedents)
                 --POST /api/runs-------------->  Manager.create()  (status: preparing)
                      thread: build_graph() -> GraphStore.save() -> prepare_population()   (LLM calls)
                      status: ready
                 --POST /api/runs/{id}/start--->  Manager.start()   (status: running)
                      thread: run_court() | run_town() | Engine.run() (OASIS worker subprocess)
                      status: reporting -> generate_grounded_report() -> completed
                 <--GET  /api/runs/{id}/events--  SSE stream of rows from the `events` table
```

1. **Retrieve law (optional, court mode).** The UI button calls `/api/legal/retrieve`. `retrieve_legal_dossier()` detects a domain by keyword (`ni_act_138`, `contract_breach`, `constitution`, `both`), pulls anchor statute chunks plus BM25 FTS matches, picks up to 5 precedent cases, and formats a ~2,600-char "dossier" that is pasted into the `source` box. [V]
2. **Prepare (`Manager.create` -> `_execute(preparing=True)`).**
   - In court mode with an empty `source`, the server auto-retrieves a dossier. [V]
     - `build_graph()`: one LLM call for an ontology, then one call per ~5,500-char chunk to extract nodes and edges. Both scenario and optional source are retained, but extraction selects `source` when supplied, otherwise `scenario`; the scenario also guides the prompt. Dynamically built Pydantic models constrain quotes, and `_validate_graph` re-checks exact source offsets. Quote mismatch aborts the run. A quote match establishes textual provenance, not legal truth. [V]
   - `prepare_population()` (`core.py`): LLM generates detailed personas in batches of 4 (`PROFILE_BATCH_SIZE`). In court mode each slot gets a `court_role` (7 fixed officers, then jury seats). `population_mode`: `fictional` (archetypes seeded from graph nodes) or `grounded` (must map to source actors, errors with `population_shortfall` if too few). [V]
   - Run ends in `ready`. Nothing is spoken yet. [V]
3. **Start.** Needs remaining `model_call_budget` >= number of scheduled turns + 1 (town/court) or >= interviews + 2 (OASIS). [V]
4. **Court run (`court.run_court`).** For each tick (= "Future #n"): a fixed speaking order (Judge frames -> complainant counsel -> defence counsel -> witnesses -> juniors -> jury -> Judge delivers branch verdict). Each turn supplies `lines[-3:] + [directive]` to retrieval, which itself takes the final three entries: at most two recent statements plus the directive. It boosts provisos for defence roles, then sends the persona, evidence, authorities, memories and last 8 conversation lines to the model. `CourtUtterance` contains `text`, `view`, `shift`, `if_opponent_argues`, `tactical_move`, `counter_strategy`, `branch_outcome`, `win_probability` (0-100). Calls are sequential; the court runner retries a timeout once. Simulated minutes are metadata, not wall-clock guarantees. [V]
5. **Report.** `generate_grounded_report()` reads the complete source graph, committed public effects and final views (last per-speaker view for court/town). It samples public histories above 80 actions, retrieves graph context for up to four agents and makes one generic synthesis request. Every finding must cite supplied action/entity/relationship IDs; unknown or missing IDs reject publication. This validates reference identity, not whether a legal claim follows from the cited material. Per-turn RAG metadata is not explicitly included in the report's compact action evidence. Markdown export includes findings, actions and graph quotations. [V]
6. **Persist and stream.** Every state change goes into SQLite (`data/runs.db`: `runs` snapshot + append-only `events`). The browser replays/streams events over SSE, so a page reload or a second tab sees the same run. On restart, any run left in `preparing/running/reporting` is marked `interrupted`. [V: `Store`, `Store.recover`]

## 3. Simulation modes (`Config.platform_mode`)

| Mode | Runs where | Needs | LLM calls |
| --- | --- | --- | --- |
| `court` (UI default) | in-process `court.py` | API key only | 1 per scheduled turn |
| `town` | in-process `town.py` (random 2-5 person groups per tick, groups run in a 4-thread pool) | API key only | 1 per turn |
| `reddit`, `both` | `worker/main.py` subprocess using **OASIS/CAMEL** | `.worker-venv` with oasis + camel; `both` also needs the Twitter recommender weights under `.cache/huggingface` | many |

The earlier setup attempt found no `.worker-venv`. Court and town bypass OASIS, but still need the main dependencies and configured provider; they were not started successfully in that attempt. The original chat reports an OASIS setup on the original developer's machine, not proof of one on this machine. [V + R]

## 4. Courtroom specifics

- **Cast.** 7 fixed officers (`FIXED_COURT_OFFICERS`: Judge, two lead counsel, two witnesses, two juniors) + 1..12 jury members. The UI sends `agent_count = 7 + jury`. Seat type is inferred from role-text keywords (`classify_court_seat`). [V]
- **Futures.** `BRANCH_STRATEGIES` hard-codes **5** strategies, all themed on cheque dishonour / contract breach (Sec 138/139/141 NI Act, Sec 73/74/55/56 Contract Act, Sec 143A, Sec 147). The UI allows up to 10 branches (`MAX_ROUNDS = 10`); ticks 6-10 reuse strategies 1-5 under "Extended Tactical Permutations". Do not read README language as ten distinct implemented strategies. [V]
- **Decision tree view.** `renderGraph()` builds one root, one node per future, then a linear chain of generated actions. `branchSummary()` uses the latest action, so a displayed verdict can be provisional before the branch finishes. It also has text-based fallback classifications for actions without structured outcomes. [V]
- **Room.** Canvas 2D rendering with depth effects, no current Three.js runtime. Model decisions arrive through SSE; the browser reveals completed speeches at roughly one word per 400 ms, adjusted by playback speed. This is separate from the report's model-output streaming. [V]

## 5. Legal corpus

- Source: Open India Law `v2026.08.1` (attribution/licence per README and historical chat), plus separately fetched and normalised Constitution text. [scripts/extract_open_india_law.py](scripts/extract_open_india_law.py) includes `fetch_constitution_rows()` and repairs mislabelled Contract Act Section 73 rows. The pasted AI advice that the Constitution was already in the central Parquet was corrected during implementation, not accepted as fact. [Chat + V]
- Tracked inputs: `data/open_india_law/target_legislation.parquet` (2.1 MB) and `domain_judgments.parquet` (9.7 MB), plus `extraction_manifest.json`. All other `data/*` is gitignored. [V: `.gitignore`]
- At the earlier setup check, `legal_poc.db` (~144 MB per manifest) did not exist. `ensure_legal_db()` attempts to build it from the two Parquet files, swallowing exceptions. A missing DB is reported unavailable by status and returns empty per-turn authorities; dossier retrieval raises if the DB is still missing. An existing but invalid DB is not automatically rebuilt. [V]
- Counts (manifest, re-added by hand): legislation 7,143 across 14 sources; judgments 1,600 cases / 10,139 chunks (SC 318, Delhi HC 665, Bombay HC 617); 12,714 citation edges. README numbers match. [V]
- **Deliberately bounded corpus.** 1,336 of the 1,600 cases are tagged `ni_act_138`, 262 `contract_breach`, 2 `both`; none are tagged `constitution`. The manifest records scans of 28/56 SC, 6/54 Delhi and 6/140 Bombay row groups. The extractor retains complete ordered cases within its selection, not every relevant case in those courts. Broader courts, tribunal PDFs/OCR and full national coverage remain future scope. [Chat + V]
- **Constitution domain gap.** The UI offers a constitutional/writ scenario, but its precedent query searches the NI/contract corpus rather than a dedicated constitutional corpus. It can return commercial cases, not established coverage of the writ issue. The test checks counts and labels, not substantive constitutional relevance. [V]
- **Citation graph is not citator validation.** `extract_citations_for_cases()` extracts reference strings into `case_citations`; there are no treatment labels proving followed/distinguished/overruled status. Hierarchy/bench metadata boosts ranking but does not implement a legal validity check. [V]
- `detect_legal_domain` is plain keyword matching; anything unmatched defaults to `ni_act_138`. [V]

## 6. Side data and scripts (not used by the running app)

| Path | What it is |
| --- | --- |
| `data/vaquill_judgments*`, `scripts/scrape_vaquill_judgments.py` | Separate listings/inventory; the prior check counted 9,129 lines across 2,016 year files. The script calls a browse API, but the provenance of every existing file was not established. Neither these files nor S3 counts feed current legal retrieval. |
| `data/open_judgments/s3_index_counts.jsonl`, `scripts/s3_judgment_counts.py` | Per-year judgment counts read from the AWS Open Data indexes of `indian-supreme-court-judgments` / `indian-high-court-judgments` (CC-BY-4.0) without downloading archives. Untracked in git. |
| `MIROFISH-REVERSE-ENGINEERING.md`, `REA-SETUP.md` | Analysis of the upstream MiroFish repo and setup for the REA tooling. Not part of runtime. |
| `docs/superpowers/{specs,plans}` | Design docs for conversation room, graph-grounded simulation, etc. |
| Original chat exports | Removed from the current working tree for privacy; the Downloads source remains available for provenance. |

**Compliance caution (from repo memory, verified 2026-10-16):** Vaquill's Terms of Service forbid scraping and bulk extraction. The AWS S3 buckets are the open-licence route for judgments. Treat `scrape_vaquill_judgments.py` as something not to run. [R]

## 7. Code map

| File | Role |
| --- | --- |
| `legisimate/server.py` | `ThreadingHTTPServer` on 127.0.0.1; `Store` (SQLite runs/events), `Manager` (one active run at a time, worker thread, call budget, error mapping), HTTP routes, SSE, security headers/Host+Origin checks, single-instance `flock` on `data/server.lock`. |
| `legisimate/core.py` | `Config` and all strict Pydantic schemas, `Model` wrapper over `client.responses.parse/stream` (OpenAI **Responses API**, `store=False`, call and token accounting, `call_limit`), `prepare_population`, `generate_grounded_report`, `markdown` export. |
| `legisimate/graph.py` | Ontology + quote-validated graph extraction; `GraphStore` (graph, per-turn "episodes", FTS5 index in the same `runs.db`). |
| `legisimate/court.py` | Court cast, branch strategies, turn schedule, `run_court`. |
| `legisimate/legal.py` | Corpus bootstrap, domain detection, dossier + per-turn retrieval. |
| `legisimate/town.py` | Random-group conversation mode, shared `Utterance` schema. |
| `legisimate/space.py` | Spatial `Room` encounter model (max 10 people), used by the Reddit/OASIS shared-room path. |
| `legisimate/engine.py` | Spawns `worker/main.py` in `.worker-venv`, JSON-lines protocol, cancel via SIGTERM then kill after 75 s. |
| `worker/main.py` | OASIS/CAMEL driver (Reddit/Twitter), separate Python env. |
| `web/` | `index.html`, `app.js` (state, API, SSE, graph), `room.js` (canvas courtroom), vendored Cytoscape + Lucide in `assets/` (built by `npm run build`). |
| `tests/` | `unittest` suite (`test_*.py`) and two Node VM checks; `serve_fixture.py` for UI fixtures. |
| `run.sh` | Sources `.env`, then `exec .venv/bin/python -m legisimate.server "$@"`. |

## 8. Running it locally

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt   # openai, pyarrow, pydantic (requirements.lock pins the runtime-only set)
# .env (gitignored):
#   OPENAI_API_KEY=...            # without it the UI loads but "Prepare Experiment" is disabled
#   OPENAI_BASE_URL=...           # optional; NOTE server.py builds OpenAI() so the SDK reads this env var
#   OPENAI_MODEL=gpt-4o-mini      # default
#   LEGISIMATE_MODEL_TIMEOUT=180
./run.sh --port 8765              # http://127.0.0.1:8765
PYTHONPATH=tests .venv/bin/python -W default -m unittest discover -s tests -v
```

- Port default is 8000 (`--port`); the README uses 8765. [V]
- Host header must be `127.0.0.1:<port>` or `localhost:<port>`, otherwise 403. Do not reverse-proxy it under another hostname. [V]
- One simulation at a time. [V]
- Frontend bundle is committed (`web/assets/vendor.js`); `npm install && npm run build` is only needed to change vendored libs. [V]

### Historical Setup Findings On This Machine (2026-10-16)

- Python 3.14.3 (Homebrew). `requirements.txt` pins `openai==3.28.0`, `pydantic==2.14.0`, `pyarrow==26.0.0`.
- `pip` is configured for the LSEG Artifactory PyPI remote. The credential in `~/.netrc` returns **HTTP 401**, so pip falls back to an interactive username prompt and hangs. Refresh the Artifactory credential (outside the agent), then re-run the pip install.
- No `.env` and no `OPENAI_API_KEY` yet. No `.worker-venv`.

### Setup Resolution (2026-10-16)

- With the user's approval, the system npm config's `npm-remotes` token authenticated successfully to the existing Artifactory Python registry. Other tested npm tokens returned 401. Installed the pinned main dependencies using a temporary mode-0600 netrc file, then removed it; no credential values or persistent auth changes were added to this project or the system config.
- Dependency imports verified: OpenAI 3.28.0, PyArrow 26.0.0, Pydantic 2.14.0. Started and opened http://127.0.0.1:8765/; the page and legal retrieval returned HTTP 200. The auto-built corpus reports 7,143 provisions, 1,600 cases, 10,139 chunks and 12,714 citation edges; a cheque-dishonour request returned six statutes and five precedents.
- The model remains unconfigured (`configured: false`); browsing and legal retrieval work, but preparing/running an AI simulation still requires the user's model credentials. No live model calls were made.

## 9. Questioned assumptions

1. *"Futures are distinct simulated universes."* They are not separate worlds. Each is one sequential hearing with a different **prompt directive**; memory (`memory[speaker]["heard"]`, last 16 lines) carries across branches, so later branches can be influenced by earlier ones. Only 5 distinct directives exist. [V]
2. *"Win probability is a prediction."* It is a number the model writes per turn. No ground-truth calibration or outcome data exists in the repo. [V]
3. *"Citations are real."* Authorities passed to the model come from the local corpus, but the model's *text* is free-form. Nothing verifies that a section or case it names was actually in `live_rag_authorities`. `rag_citations` in each effect lists what was **retrieved**, not what the speaker **used**. [V]
4. *"The graph grounds the personas."* With a dossier present, the evidence graph is extracted from the dossier, guided by the scenario. Otherwise it is extracted from the scenario. Quotes are validated against the selected text only. In `fictional` mode source context informs synthetic profiles; it does not turn them into real actors. [V]
5. *"RAG covers Indian law."* The manifest lists 14 legislative/regulatory sources, not just 14 individual statutes, plus 1,600 NI/contract cases from three courts. This is the agreed initial slice, not the eventual nationwide product. [Chat + V]
6. *"Works offline / without a key."* The server and legal retrieval work without a key once dependencies exist; model-driven steps do not. If `OPENAI_API_KEY` is unset `model is None` and `create()` raises. [V]
7. *"The winning future was found."* Future #3 is preset as a winning strategy and asks for a favourable verdict. That is prompt-directed exploration, not a demonstrated search or an assurance that a favourable path exists for the supplied facts. [V]
8. *Model-call estimate:* 10 participants produce 11 turns per branch because the judge speaks twice: 33 turns for three branches. With one dossier extraction chunk, preparation takes 1 ontology + 1 graph + 3 profile calls; report takes 1. Nominal total: **39 calls**, excluding timeouts/retries, extra source chunks or failure. Budget default is 500. Court speaking length does not use `conversation_minutes`. [V]

## 10. Verification Boundary And Working Understanding

- This reconciliation parsed the original export, compared user text and assistant prose across all 86 turns, and correlated the requirements with source, manifest, the report pipeline, graph UI, courtroom rendering logic and the existing fake-model court test.
- No application runtime was changed. No new browser session, dependency installation, unit suite, paid model call, external data download or legal-accuracy evaluation was performed for this reconciliation. Historical test counts, sample percentages, local servers and credentials mentioned in the original chat are not present-day verification.
- The earlier description as a legal-education "toy" was wrong about intent. The accurate description is **a prototype of an Indian litigation strategy and intended predictive platform, initially scoped to two legal domains, with an inspectable courtroom simulation and an educational use case**.
- Still needed before claiming the broader ambition is met: scenario-specific branching with independent futures, evidence-backed handling of factual changes, neutral outcome evaluation rather than a preset winning directive, legal citation/treatment verification, wider domain coverage and measured outcome calibration on held-out cases. These are gaps relative to intent, not changes authorised by this documentation task.
- Keep this file aligned by recording the latest user requirement, its owning code path and the evidence used to verify it. Do not conflate legal research/RAG, source provenance, narrative plausibility and predictive accuracy.
