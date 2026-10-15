# MiroFish Reverse Engineering

Date: 2026-10-12. Target: <https://github.com/666ghj/MiroFish>.
Revision: `7657031ac01184afe2cb220f5ee3545573b5e843`.

Deep follow-up: 2026-10-14. The first pass below is retained as a dated
orchestration analysis. The [second pass](#second-pass-agent-behavior-and-reconstruction)
inspects the exact OASIS/CAMEL dependency source and supersedes its dependency-internals unknowns.

## Executive Summary

MiroFish is an orchestration application for LLM-driven social simulations. A Vue frontend submits documents and a scenario question to Flask. The backend asks an external LLM for an ontology, builds a Zep Cloud graph, converts typed entities into personas, runs Twitter/Reddit environments through OASIS/CAMEL, optionally feeds simulated actions back into Zep, and writes a tool-assisted narrative report.

The implementation's distinctive work is the pipeline, persona/configuration generation, process supervision, graph synchronization, and reporting. Social-environment and agent-action execution are delegated to dependencies. The inspected paths do not establish calibrated predictive accuracy; simulated narratives should not be treated as validated forecasts.

The repository was cloned and its frontend built without modifying tracked source. No backend service, paid LLM call, Zep request, simulation, or live deployment was exercised.

## Evidence And Method

The installed REA skill explicitly routes complete source repositories to ordinary source tools. Accordingly, backend and UI conclusions below are **source observations** or labelled **inferences**, not claims derived from a decompiled Python application. REA was additionally used on the frontend's locally built production-format artifact, not a publisher-signed release or the live demo.

Installation was verified before this investigation: all three configured agent launchers completed MCP initialization, advertised 170 tools, and answered `binary_session`. See the [installation guide](REA-SETUP.md) and [machine-readable verification](.rea/verification.json).

| Record | Evidence ID | Outcome |
| --- | --- | --- |
| [Default artifact analysis](.rea/mirofish-frontend.evidence.json) | `ev_6f579cc0479c80faeb8392edb4d68b19d7501dbdbae30b199a7992d567d0dca3` | Syntax observations retained; semantic worker exhausted its default heap |
| [Capped artifact retry](.rea/mirofish-frontend-2048.evidence.json) | `ev_711b92d711b7b004654c82e90b66b7e09bbcad40b133e4b9fd5c64425fc69ff1` | Same artifact, 2 GiB configured heap and 120-second deadline; semantic coverage still partial |

Both records identify artifact SHA-256 `f2ffc263c57a7d5722829106d1f4da99e2e4817b72213284f45c9b5490a58d0f`. REA read two relevant files, parsed one JavaScript bundle, visited 151,845 AST nodes, retained 25 findings, and recorded zero parse failures. Graph coverage is `partial`; semantic coverage is `partial` and truncated. A zero recovered-module count is not evidence that the application has no modules.

REA retained exact static observations for the UI route `/report/:reportId` and network calls `/api/report/generate` and `/api/simulation/prepare`, corroborating the corresponding [router](MiroFish/frontend/src/router/index.js#L34) and [API wrapper](MiroFish/frontend/src/api/simulation.js#L15). The artifact was never executed, so those observations do not prove endpoint availability or runtime reachability. Readable coverage details are in the [capped analysis summary](.rea/mirofish-frontend-2048-summary.json).

## Implementation Flow

### 1. Document Intake And Ontology

The home-to-project flow carries pending uploads into the project view. It sends multipart `files` and `simulation_requirement` to `POST /api/graph/ontology/generate`, replaces the temporary route with the returned project ID, then starts graph building. Source: [MainView.vue](MiroFish/frontend/src/views/MainView.vue#L194).

Flask creates a project, saves randomized upload filenames, extracts text, and calls `OntologyGenerator.generate()` synchronously. Accepted inputs are PDF, TXT, and Markdown, with a configured 50 MiB request ceiling. PDFs use text extraction rather than an OCR pipeline. The LLM returns entity/relationship definitions, which are normalized and persisted with the requirement. Sources: [upload API](MiroFish/backend/app/api/graph.py#L300), [file parser](MiroFish/backend/app/utils/file_parser.py#L81), [configuration](MiroFish/backend/app/config.py#L36), [ontology generator](MiroFish/backend/app/services/ontology_generator.py#L203).

Long documents are sampled into a bounded context rather than sent in full for ontology generation. This can omit relevant details even when the later graph ingestion uses the extracted text. Source: [ontology context selection](MiroFish/backend/app/services/ontology_generator.py#L251).

### 2. Zep Graph Construction

`POST /api/graph/build` claims a project build, reuses an active/completed build when appropriate, creates a progress task, and launches a daemon thread. The worker chunks the extracted text, creates a Zep graph, installs dynamically constructed ontology classes, and submits graph episodes through the Batch API. It journals graph/batch identities and reconciles ambiguous mutation replies instead of blindly replaying them. Sources: [build API](MiroFish/backend/app/api/graph.py#L448), [worker](MiroFish/backend/app/api/graph.py#L666), [batch ingestion](MiroFish/backend/app/services/graph_builder.py#L407).

Batch completion is polled, validated, and followed by paginated graph retrieval. The project becomes `graph_completed` only after successful ingestion. The UI polls task status and refreshes graph data. Sources: [batch completion](MiroFish/backend/app/services/graph_builder.py#L631), [graph publication](MiroFish/backend/app/api/graph.py#L770), [UI task polling](MiroFish/frontend/src/views/MainView.vue#L330).

Zep is an external Cloud dependency, explicitly bound to its v2 Cloud endpoint; this is not a wholly local graph database. Source: [Zep client policy](MiroFish/backend/app/utils/zep.py#L22).

### 3. Agent And Environment Preparation

`POST /api/simulation/create` binds a simulation to a project/graph. Preparation selects nodes with custom entity types, enriches them with relationships, and generates personas plus simulation configuration. Organizations can become representative personas; one graph entity does not necessarily equal one real human. Sources: [create API](MiroFish/backend/app/api/simulation.py#L195), [preparation manager](MiroFish/backend/app/services/simulation_manager.py#L242), [entity selection](MiroFish/backend/app/services/zep_entity_reader.py#L260).

Persona generation is concurrent and preserves entity-to-agent ordering; failures receive fallback profiles. Twitter receives CSV profiles, Reddit receives JSON profiles. Configuration includes time settings, actor activity, initial posts, and platform settings. Sources: [profile generation](MiroFish/backend/app/services/oasis_profile_generator.py#L894), [profile export](MiroFish/backend/app/services/oasis_profile_generator.py#L1112), [configuration generator](MiroFish/backend/app/services/simulation_config_generator.py#L244).

The normal UI requests LLM personas with five parallel profile workers and polls preparation progress. Source: [environment setup UI](MiroFish/frontend/src/components/Step2EnvSetup.vue#L780).

### 4. Simulation Execution And Memory

The UI starts the `parallel` platform with `force: true` and graph-memory updates enabled. `SimulationRunner` launches a Python child process, records its PID/state, redirects output to a simulation log, and monitors the child plus platform action logs. Sources: [UI start parameters](MiroFish/frontend/src/components/Step3Simulation.vue#L383), [start API](MiroFish/backend/app/api/simulation.py#L1501), [runner](MiroFish/backend/app/services/simulation_runner.py#L371).

The parallel script creates Twitter and Reddit OASIS environments and executes both coroutines with `asyncio.gather`. Initial posts use manual actions; subsequent rounds select actors using activity/time settings and ask OASIS to execute LLM actions. The configured hours and minutes-per-round determine the round budget, optionally capped by `max_rounds`. Sources: [actor selection](MiroFish/backend/scripts/run_parallel_simulation.py#L1040), [OASIS integration](MiroFish/backend/scripts/run_parallel_simulation.py#L1155), [round settings](MiroFish/backend/scripts/run_parallel_simulation.py#L1551).

OASIS/CAMEL supplies environment reset/step/close, social state, and agent-action/interview execution. MiroFish supplies scheduling, profiles, initial events, supervision, logging adapters, and synchronization. Pinned dependencies include `camel-oasis==0.2.5` and `camel-ai==0.2.78`; their internals were outside this source reconstruction. Source: [backend requirements](MiroFish/backend/requirements.txt#L20).

Optional memory updates convert meaningful successful actions into text episodes with simulation/platform/round provenance, batch them per platform, and wait for Cloud processing. The API makes this opt-in; the normal UI enables it. Source: [memory updater](MiroFish/backend/app/services/zep_graph_memory_updater.py#L213).

### 5. Completion, Reports, And Interviews

There are two different completion concepts: the social round loops can finish while the child remains alive for interview commands. The script defaults to this command-wait mode; `--no-wait` would opt out. Platform `simulation_end` records do not themselves make the runner terminal. Sources: [script lifecycle](MiroFish/backend/scripts/run_parallel_simulation.py#L1492), [runner event handling](MiroFish/backend/app/services/simulation_runner.py#L802).

The runner publishes successful terminal state only after child exit and memory-ingestion finalization. Report generation rejects an active runner or retained updater with HTTP 409 and additionally checks graph completion/identity. Source: [report barrier](MiroFish/backend/app/api/report.py#L86).

`ReportAgent` plans an outline and writes Markdown sections through a bounded ReACT loop. Its tools are `quick_search`, `panorama_search`, `insight_forge`, and `interview_agents`. Sections are saved incrementally and assembled into a report. This generation path does not establish an independent forecast-accuracy validation stage. Sources: [tool definitions](MiroFish/backend/app/services/report_agent.py#L925), [section generation](MiroFish/backend/app/services/report_agent.py#L1260), [report persistence](MiroFish/backend/app/services/report_agent.py#L1931).

Report chat accepts caller-supplied history and uses a bounded report context plus limited tool calls. Agent interviews use JSON-file IPC with a live child and SQLite-backed interaction history. Sources: [report chat](MiroFish/backend/app/services/report_agent.py#L1810), [IPC](MiroFish/backend/app/services/simulation_ipc.py#L41), [interview API](MiroFish/backend/app/api/simulation.py#L2304).

## Frontend And API Contract

The routed views are `/`, `/process/:projectId`, `/simulation/:simulationId`, `/simulation/:simulationId/start`, `/report/:reportId`, and `/interaction/:reportId`. The process route points to the current `MainView`, not every similarly named legacy view. Source: [router](MiroFish/frontend/src/router/index.js#L1).

The shared Axios client defaults to `http://localhost:5001`, has a five-minute request timeout, sends `Accept-Language`, and unwraps the API's `success` envelope. Vite also defines an `/api` development proxy, but the default absolute Axios URL goes directly to the backend unless the build-time base URL is changed. Sources: [HTTP client](MiroFish/frontend/src/api/index.js#L5), [Vite configuration](MiroFish/frontend/vite.config.js#L14).

| Stage | Main command | Progress/result retrieval |
| --- | --- | --- |
| Intake | `POST /api/graph/ontology/generate` | Returned project and ontology |
| Graph | `POST /api/graph/build` | `GET /api/graph/task/<task_id>`, graph/project reads |
| Preparation | `POST /api/simulation/create`, `POST /api/simulation/prepare` | `POST /api/simulation/prepare/status`, profile/config reads |
| Run | `POST /api/simulation/start` | Run status, action/detail and timeline reads |
| Finalization | `POST /api/simulation/stop` or `POST /api/simulation/close-env` | Authoritative runner status and ingestion barrier |
| Report | `POST /api/report/generate` | `GET /api/report/generate/status`, section/content/download reads |
| Interaction | Report chat and simulation interview endpoints | Tool-assisted answers and interview history |

These are code-defined endpoints, not a claim that a live server answered them. The simulation UI polls status every two seconds and details every three seconds. Source: [simulation polling](MiroFish/frontend/src/components/Step3Simulation.vue#L467).

## Persistence And External Boundaries

| Data | Persistence and ownership |
| --- | --- |
| Uploaded files, extracted text, project metadata/ontology | Project directories beneath backend uploads; local files |
| Task progress | Process-local singleton dictionary, not a durable distributed job queue |
| Simulation profiles/configuration/preparation/run state | Per-simulation files beneath backend uploads |
| Social state | Separate Twitter/Reddit SQLite databases managed through OASIS |
| Actions, environment status, IPC commands/responses | Per-simulation JSONL/JSON files and logs |
| Reports | Metadata, outline, progress, section Markdown, assembled Markdown and logs |
| Knowledge graph and simulated-memory episodes | Zep Cloud |
| Ontology, personas, configuration, actor decisions and report prose | External OpenAI-compatible LLM calls through the configured provider |

Sources: [project persistence](MiroFish/backend/app/models/project.py#L111), [task manager](MiroFish/backend/app/models/task.py#L65), [simulation state](MiroFish/backend/app/services/simulation_manager.py#L138), [SQLite trace adapter](MiroFish/backend/scripts/run_parallel_simulation.py#L657), [report manager](MiroFish/backend/app/services/report_agent.py#L1931).

Uploaded document context and requirements leave the machine for LLM calls, and extracted text/actions leave for Zep. Credentials belong in an operator-controlled environment, not in uploaded documents or committed source. No such data transfers were performed during this analysis.

## Material Limitations

1. **Report/interview lifecycle tension, inferred from connected code.** Default children remain alive after the rounds, while reports require terminal runner state. Gracefully closing or stopping allows reporting but removes that child's live interview environment. The report's live interview tool therefore needs a lifecycle strategy not demonstrated by the inspected normal path. Sources: [script wait mode](MiroFish/backend/scripts/run_parallel_simulation.py#L1517), [report barrier](MiroFish/backend/app/api/report.py#L86), [report interview implementation](MiroFish/backend/app/services/zep_tools.py#L1270).
2. **Incomplete restart/multi-worker guarantees, observed architecture.** Locks, worker threads, task records, process handles, and updater queues are process-local. Persisted batch IDs support some reconciliation; they do not turn the application into a durable distributed scheduler. Sources: [task manager](MiroFish/backend/app/models/task.py#L65), [runner state](MiroFish/backend/app/services/simulation_runner.py#L216), [graph lifecycle coordination](MiroFish/backend/app/utils/zep_lifecycle.py#L1).
3. **Configuration is not proof of effective control.** The inspected run scripts consume activity/time selection and initial events, but generated sentiment, posting rates, recommendation weights, and scheduled-event fields should not all be represented as experimentally enforced controls. The controlling scheduler and the external engine must be checked for each claimed intervention. Sources: [generated settings](MiroFish/backend/app/services/simulation_config_generator.py#L244), [actual scheduler](MiroFish/backend/scripts/run_parallel_simulation.py#L1040).
4. **Lossy context and weak scientific guarantees.** Ontology context is sampled; profiles can fall back; downstream prose is LLM-generated. No inspected path establishes representative population sampling, explicit seeded reproducibility, forecast calibration, uncertainty intervals, or validation against later real outcomes. These remain research/validation requirements, not features proven by this report.
5. **Local/development deployment assumptions.** Flask bootstrap enables wildcard API CORS, logs JSON bodies at DEBUG, and registers the inspected routes without an application authentication middleware. The documented Docker command starts development services. Do not expose this setup to untrusted networks without an appropriate authenticated boundary and deployment review. Sources: [app bootstrap](MiroFish/backend/app/__init__.py#L42), [request logging](MiroFish/backend/app/__init__.py#L51), [development scripts](MiroFish/package.json#L9).

The source is licensed under AGPL-3.0. Reuse or network deployment of modified code needs consideration of that license's source-availability obligations. Source: [license](MiroFish/LICENSE#L1).

## Verification And Remaining Work

| Question/check | Status |
| --- | --- |
| Does the installed skill have valid metadata and matching user copies? | Verified by the runnable installation smoke test |
| Can each configured launcher initialize REA and call a tool? | Verified for Claude Code, Copilot CLI, and VS Code |
| Were unrelated existing settings preserved? | Verified against installer backups |
| Does the unmodified frontend build from its lockfile? | Passed; Vite emitted bundle-size and mixed-import warnings |
| Do REA's artifact observations corroborate source-defined UI/API literals? | Verified for selected literal endpoints/routes; deeper graph remains partial |
| Can upload-to-graph-to-simulation-to-report be reconstructed from source? | Answered at the orchestration level; dependency internals not decompiled |
| Has the agent UI reloaded and displayed the new skill/tools? | Not exercised in this existing chat; restart/reconnect required |
| Do live LLM/Zep/OASIS workflows succeed and produce accurate forecasts? | Not verified; no credentials or paid calls used |

Backend tests exist for ontology budgets, Cloud SDK contracts/retries/pagination, graph lifecycle, simulation finalization, and report barriers. They were inspected, not run; the backend environment was not installed. Relevant examples: [ontology tests](MiroFish/backend/tests/test_ontology_generator.py#L27), [Cloud contract tests](MiroFish/backend/tests/test_zep_cloud_contracts.py#L192), [simulation barrier tests](MiroFish/backend/tests/test_zep_simulation_barrier.py#L58), [report barrier tests](MiroFish/backend/tests/test_zep_report_barrier.py#L26).

The source checkout remained clean after dependency installation, building, and REA analysis. Reproducible commands and installation checks are in the [REA setup guide](REA-SETUP.md).

## Second Pass: Agent Behavior And Reconstruction

This follow-up answers the behavior questions the original reconstruction omitted.
It uses source inspection, not decompilation, as explicitly required by the
installed REA skill for complete repositories. The existing frontend artifact
Evidence IDs remain valid but partial; repeating that analysis would not explain
agent cognition. No new REA artifact result or live reference simulation is claimed.

### Reference Identity

The exact pinned wheels were downloaded through the configured Python package
mirror using `pip download --no-deps --only-binary=:all: --python-version 3.11`.
They were hashed and unpacked for inspection, not installed or executed.

| Dependency | Locally computed SHA-256 | Inspected tree |
| --- | --- | --- |
| `camel-oasis==0.2.5` | `9ebd6ba8e331495ee56b25cc63982188b94125dde499e5e9c00398a1d47e606d` | `.rea/reference-packages/oasis-0.2.5/` |
| `camel-ai==0.2.78` | `356624da13dfe0c55ef43dc509c18ce029f67fe3997966495a4ce9be931078d5` | `.rea/reference-packages/camel-0.2.78/` |

OASIS requires Python `>=3.10,<3.12`; CAMEL requires `>=3.10,<3.13`.
Their compatible intersection is Python 3.10 or 3.11, not the current app's
Python 3.14 environment. This is an observed metadata constraint, not a runtime
compatibility experiment. Source: [OASIS metadata](.rea/reference-packages/oasis-0.2.5/camel_oasis-0.2.5.dist-info/METADATA#L11).

### What Actually Produces Interaction

1. **Graph-backed identity, not three fields.** MiroFish selects typed document
	entities and enriches them with incoming/outgoing relationship facts and linked
	node summaries. Additional semantic retrieval contributes bounded relevant
	context. Profiles include detailed history, interests, attitudes and event
	involvement, with source entity identity retained before platform export.
	Demographics and detailed biography can be generated rather than factual.
	Sources: [entity enrichment](MiroFish/backend/app/services/zep_entity_reader.py#L290),
	[profile context](MiroFish/backend/app/services/oasis_profile_generator.py#L348),
	[profile schema](MiroFish/backend/app/services/oasis_profile_generator.py#L81).
2. **Activation uses schedules and stochastic activity.** The harness filters by
	active hours and activity level, applies peak/off-peak multipliers, and samples
	active actors. This is random activation within a schedule, not random partner
	assignment and not graph-based activation. There is no seeded reproducibility
	established by this script. Source: [actor selection](MiroFish/backend/scripts/run_parallel_simulation.py#L1040).
3. **The model chooses platform tools after observing a feed.** OASIS refreshes
	the agent's environment, then calls CAMEL `astep` with its available functions.
	Twitter exposes posting, liking, reposting, following, quoting and doing nothing;
	Reddit also exposes comments, dislikes, searches, refresh and mute. The tools
	mutate social state, rather than merely returning a prescribed spoken reply.
	Sources: [LLM decision](.rea/reference-packages/oasis-0.2.5/oasis/social_agent/agent.py#L125),
	[enabled tools](MiroFish/backend/scripts/run_parallel_simulation.py#L178).
4. **Information exposure is selective.** Twitter combines recommended and
	followed-account posts; its default recommender uses profile/post embeddings.
	Reddit uses hot-score recommendations. An agent does not simply receive every
	participant's last twenty messages. Feed limits and final query ordering matter.
	Sources: [feed refresh](.rea/reference-packages/oasis-0.2.5/oasis/social_platform/platform.py#L258),
	[default recommenders](.rea/reference-packages/oasis-0.2.5/oasis/environment/env.py#L81),
	[Twitter relevance](.rea/reference-packages/oasis-0.2.5/oasis/social_platform/recsys.py#L419).
5. **Individual memory persists across rounds.** `SocialAgent` reuses a CAMEL
	`ChatAgent`. Its default chat history is in-memory, not durable across process
	restart. Stored history accumulates, while the prompt context is pruned to the
	model token limit using recency-weighted scores. A reset clears it. Sources:
	[agent construction](.rea/reference-packages/oasis-0.2.5/oasis/social_agent/agent.py#L108),
	[default memory](.rea/reference-packages/camel-0.2.78/camel/agents/chat_agent.py#L478),
	[context pruning](.rea/reference-packages/camel-0.2.78/camel/memories/context_creators/score_based.py#L65).
6. **Concurrency does not mean forced simultaneous conversations.** `env.step`
	refreshes recommendations and gathers active-agent tasks under a semaphore.
	Their platform mutation requests are consumed by a channel-backed dispatcher.
	The harness runs Twitter and Reddit concurrently. Dependency completion order
	can affect state; this is not deterministic snapshot isolation. Source:
	[actual step implementation](.rea/reference-packages/oasis-0.2.5/oasis/environment/env.py#L136).
7. **The knowledge graph and social graph are different.** Zep supplies source
	context and receives successful simulated-action episodes for later retrieval
	and reporting. Its edges are not automatically copied as OASIS follows. The
	profile generators MiroFish calls add agents without seeding follow edges.
	In OASIS's LLM path, updating the separate in-memory `AgentGraph` is commented
	out; platform follow rows still change. Sources:
	[initial graph generation](.rea/reference-packages/oasis-0.2.5/oasis/social_agent/agents_generator.py#L567),
	[disabled graph mutation](.rea/reference-packages/oasis-0.2.5/oasis/social_agent/agent.py#L150),
	[episode ingestion](MiroFish/backend/app/services/zep_graph_memory_updater.py#L494).
8. **An open-room discussion is an extension, not reference parity.** Normal
	MiroFish tools represent public posts/comments/quotes, not private room talk.
	OASIS has create/join/leave/send-to-group operations, but MiroFish does not
	enable them. A room mode needs membership-scoped message observation and a
	causal conversation adapter, not just enabling a tool or animating proximity.
	Source: [group tools](.rea/reference-packages/oasis-0.2.5/oasis/social_agent/agent_action.py#L703).

### Configuration And Reliability Gaps To Avoid Copying

- Generated recommendation weights and echo-chamber settings are not passed into
  `oasis.make`; configuration output alone is not proof of enforcement.
- The harness's simulated minutes and OASIS platform timestamps use different
  clocks. Empty active-agent rounds skip `env.step`, so the Twitter clock also
  does not advance on those rounds.
- `SocialAgent.perform_action_by_llm` catches exceptions and returns an exception
  object. A successful `env.step` return alone does not prove every action worked.
- The Twitter default loads `Twitter/twhin-bert-base`; model acquisition and CPU
  costs must be explicit, not silently removed from a claimed faithful engine.
- Appending action episodes to Zep is separate from CAMEL's decision memory;
  the inspected harness does not retrieve those episodes for every LLM action.

Sources: [configuration versus runtime](MiroFish/backend/scripts/run_parallel_simulation.py#L1155),
[clock advancement](.rea/reference-packages/oasis-0.2.5/oasis/environment/env.py#L198),
[swallowed agent error](.rea/reference-packages/oasis-0.2.5/oasis/social_agent/agent.py#L156).

### Current App Failure Evidence

Read-only snapshot, SQLite event metadata, and the existing server terminal
agree: run `bba6089ecb6f4505a8f61eaca7d686b6` completed two rounds and saved
22 actions. Two actions were committed during round three; four in-flight turns
then aborted. The terminal recorded only `ValueError`, and the saved error
collapsed all such exceptions to a generic message. The precise originating
error cannot be recovered from this evidence. Aborted peers need not be the
original failing task. No paid retry was started and no saved evidence changed.

A concrete contract mismatch is visible independently of that unknown cause:
the prompt asks an initiating persona to post or pass, but validation accepts
a reply to older visible evidence. Several saved initiating turns did that.
This is not proof of the third-round cause; it demonstrates why action semantics
need one authoritative tool contract rather than instructions and guards that
disagree. Sources: [prompt and validation](misofish/core.py#L230),
[lossy failure handling](misofish/server.py#L247).

### Evidence Status And Build Consequences

| Question | Status | Consequence |
| --- | --- | --- |
| Document graph to detailed profiles | Source-traced | Restore source-linked facts, adjacency and relevant retrieval |
| Activation, observation, decisions, mutations | Exact dependency source-traced | Reuse OASIS rather than arbitrary pairs |
| Per-agent memory and reset semantics | Exact CAMEL source-traced | Preserve identity and scoped memory across rounds |
| Knowledge graph versus social relationships | Source-traced | Store and display their different meanings |
| Direct room conversations in normal MiroFish | Not enabled in inspected action sets | Implement and test as an explicit extension |
| Live reference Azure/Zep/OASIS integration | Not executed | Requires supported runtime, cloud configuration and live verification |
| Third-round originating exception | Unrecoverable with saved diagnostics | Add safe error codes and per-decision outcomes, not a guessed fix |
| Predictive accuracy or human realism | Not established | Validate observable mechanics; do not claim human-equivalent cognition |

The proposed rebuild is specified in
[the graph-grounded simulation design](docs/superpowers/specs/2026-10-14-graph-grounded-simulation-design.md).

## Reconstruction And Runtime Verification

The approved local-graph rebuild is now implemented. Unlike the initial simplified app, its production v2 path does not pair people by proximity or impose a ten-person cap. It supervises the installed OASIS/CAMEL engines, with detailed graph-linked profiles and separate native Twitter/Reddit memories and databases. Ten is the editable default; the deployment ceiling and provider concurrency are independent.

The evidence graph is local SQLite/FTS5 with exact quoted spans, typed incoming/outgoing relationships and committed public episodes. The social-follow/group graph is a separate view. This is a deliberate alternative to Zep, not an equivalence claim. The Reddit-owned room group is an explicit extension to the inspected reference action sets. Its display reflects committed speech, rather than deciding who talks.

Runtime checks use real installed libraries and temporary native databases, with loopback Responses/Chat Completions providers. They establish observable behavior, not a successful live reference run:

| Gate | Observed Result |
| --- | --- |
| Isolated supported engine | Python 3.11.14, OASIS 0.2.5, CAMEL 0.2.78, MCP 1.26.0; both environments pass dependency checks |
| Actual Twitter recommender | Public TWHIN weights acquired with verified HTTPS; offline native dual-platform fixture observes another actor's committed post |
| Identity, tools and memory | Exact configured deployment name, real SQLite mutations, distinct platform-qualified effects, retained individual context across three ticks |
| Activation and failure | Empty ticks advance without calls; malformed tools, budgets, cancellation, failed third ticks and peer errors preserve earlier commits; queued provider requests stop |
| Group visibility | Native private-group membership prevents nonmember message observation; private effects are excluded from public graph retrieval/reporting |
| Durable evidence | Failed graph transactions retain the prior snapshot/search state; duplicate IPC and episode IDs do not create duplicate evidence |
| Population | Default ten, rich profile batches at most four, stable thirteen-person preparation, explicit source-actor shortfall |
| Reporting | Unknown IDs rejected, bounded public evidence retrieval, source/action links, explicit no-public-discussion result without a model request |
| Browser integration | Thirteen actors, both platforms, three ticks, 91 unique effects, 78 committed contributions, 85/500 calls and a published cited report |
| Workbench | Nonblank, responsive room at actual 375/768/1440 CSS widths; desktop movement, nonoverlapping labels, paused backlog, evidence navigation and keyboard tabs verified |
| Regression release | 74 unittest checks pass in 182.593 seconds; frontend build/syntax and host/worker dependency checks pass |
| Current social projection | Node/browser regression verifies duplicate suppression and platform-specific unfollows without mutating history; no CSP violations |
| Legacy preservation | All three complete saved snapshots remain byte-identical after production reload; old report citations and exports resolve |

The browser fixture predates the last worker-token-accounting change. Its archived token total is not evidence for that change; separate worker/manager tests verify the current aggregation. A read-only whole-change review identified crowded large-cast display; spaced scene positions and label collision suppression address it. The scene renders at most 100 figures, while all simulated personas remain selectable and recorded.

No new paid Azure simulation or Zep request was made for this reconstruction. Synthetic behavior quality remains a live-model evaluation question. No human-equivalent cognition, calibrated forecast, semantic entailment guarantee, post-crash CAMEL memory restoration or full MiroFish parity is claimed. Optional live persona interviews are deferred. The old third-round error is still unrecoverable; new failure-preservation tests do not diagnose that historical exception.

See [README.md](README.md) for reproducible prerequisites, workflow, privacy, offline-model setup and release commands.

### Post-Release Profile Contract Correction

On 2026-10-15, two newly reported runs failed after graph extraction and before actor creation. Three separately authorized, bounded Azure profile requests were used, with zero retries and no native simulation: the first returned three actors for four slots and non-null fictional identities; the second passed count/identity but failed unknown source references; the third passed all checks with four distinct profiles, null fictional identities and valid graph IDs (2,996 input / 894 output tokens).

The cause was a broad provider schema (`1..4` actors and unconstrained string references) paired with stricter local cross-field guards. Pydantic-generated per-batch provider schemas now enforce the exact count and allowed identity/evidence values. The guards are retained; invalid records are not repaired, dropped or fabricated. New failures preserve lifecycle stage and allowlisted error codes without logging private output. The final 76-test suite passes in 180.273 seconds; all seven saved snapshots are byte-identical after reloading the corrected backend. This verifies profile generation live, not a complete live Azure simulation or predictive validity.

### Timeout And Complete Preparation Verification

The subsequent generic API failure in run `ed045bc2a4134d3a9d62b87b78f89bae` was identified from the server's typed log as `APITimeoutError`, not a demonstrated schema/endpoint rejection. Its individual saved-graph profile request succeeded when reproduced. Both host and worker had hard-coded 60-second deadlines; they now share a configurable 180-second default through `MISOFISH_MODEL_TIMEOUT`, with retries still disabled and a specific `provider_timeout` diagnostic.

An initial authorized full-preparation check then failed graph validation before any profiles. The discarded response does not establish which graph guard failed; a separate instrumented extraction passed. Graph provider schemas were tightened to source IDs, ontology labels and exact supplied excerpts while retaining local span/endpoint validation and specific safe graph codes. A concurrent user preparation was left untouched until inactive.

Final separately authorized production check `52c4f83a09154196b26b90252ac80edd` completed the entire graph-to-ten-person preparation in five live requests: profile progress 4/10, 8/10, 10/10; status `ready`; zero simulation actions. All prior snapshots were hash-checked unchanged. The final regression suite passes 80 tests in 193.470 seconds and the Node social check passes. Native simulation was not started automatically; this is complete live preparation evidence, not a complete live simulation or predictive-validity claim.

### Persona Traits, Final Interviews And Reply Links

MiroFish's profile prompt asks for profession, MBTI, personality, stance and personal memories inside a long persona text ([oasis_profile_generator.py](MiroFish/backend/app/services/oasis_profile_generator.py#L747-L759)). Its simulation config also generates `sentiment_bias`, `stance` and `influence_weight` ([simulation_config_generator.py](MiroFish/backend/app/services/simulation_config_generator.py#L75-L81)). However, the runner scripts never read `sentiment_bias` or `stance`; activation is random sampling weighted by activity level and active hours ([run_parallel_simulation.py](MiroFish/backend/scripts/run_parallel_simulation.py#L1040-L1080)). After a run, MiroFish interviews agents through OASIS `ActionType.INTERVIEW`, prefixed so agents answer in text without tools ([simulation.py](MiroFish/backend/app/api/simulation.py#L53-L73)).

This reconstruction now generates outlook, openness to persuasion and a first-person opening view, all required by the per-batch provider schema. Saved profiles without them remain valid. The worker prompt uses these traits so people can change their minds and explain why. After a completed run, participants are interviewed through native OASIS `perform_interview` on each platform, using their CAMEL memory, without tools. The interview call budget is reserved before decisions start. The report provider schema has no `default` keywords, which strict structured outputs can reject. Local validation still applies defaults.

A saved run exposed a reply-link defect: OASIS trace rows for `create_comment` store only content and `comment_id`, so the host could not attach comments to their parent post, and all four comments in run `278b2a2cc0ef416f9717f89b6d196f3d` were labelled as posts. The worker now restores `post_id` from the native `comment` table before publishing the effect. Saved runs are not rewritten. The 3D scene was replaced by a dependency-free 2D canvas town; the Three.js bundle dependency was removed (vendor bundle 1.5 MB to 0.78 MB). No new paid simulation was run for this change.

### Rejected-Action Failure And Town Conversations

Run `e5aacb6739d24a48bdae1ead086ae2c7` failed in tick 2 with `target_not_observed`. Its saved events show agent 2 acting on its own Reddit post. Our guard treated that one rejected action as fatal. The failure barrier then aborted the 12 decisions already queued in that tick. Neither MiroFish nor OASIS stops a simulation for an invalid action; the platform just returns `success: false`. The guard now rejects only that action, tells the agent, saves `action_rejected`, and the run continues. Platform rejections such as a duplicate like behave the same way.

The user asked for face-to-face mixing instead of feed-driven contact. **Town Conversations** is therefore a documented extension, not a MiroFish behavior. Each tick it randomizes the group count, then group sizes, then membership, with sizes kept between 2 and 5. Groups talk in parallel, and every member's last line comes after hearing everyone else. Each line carries the speaker's evolving view, and memory follows them into later random groups. It reuses the graph-grounded profiles, strict provider schemas, call budget, persistence, SSE events and grounded report. A localhost real-SDK browser run grouped ten people as 5+5 and then 2+4+2+2, produced 34 lines and a report, and showed every group's bubble at once without overlap at 1440 and 375 px. No paid simulation was run for this change.