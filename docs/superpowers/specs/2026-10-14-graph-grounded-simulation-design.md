# Graph-Grounded Misofish Rebuild

Status: approved with a local graph backend. Date: 2026-10-14.
User selected "Use Local Graph Instead" after reviewing the proposed architecture.

## Intent And Requirements

Replace the shallow proximity-driven discussion with a mature, inspectable
simulation grounded in MiroFish's actual document-graph, profile, OASIS/CAMEL,
memory and reporting mechanisms. Ten personas is the default population, not
a hard limit or the number required to speak in every round. Population is
user-configurable. The user explicitly withdrew the earlier requirement to
simplify away graphs and social-environment logic.

Keep the requested shared-room view and natural causal conversation, genuine
parallel independent decisions, sequential dependent responses, readable pacing,
an obvious final synthesis, and all existing saved experiments. The reported
third-round failure remains a reliability requirement. This is not satisfied by
adding more persona prose to the same random-pair loop.

Evidence: [the deep investigation](../../../MIROFISH-REVERSE-ENGINEERING.md).

## Proposed Architecture

Recommendation: reuse the real OASIS/CAMEL engine in an isolated Python 3.11
worker, with graph-backed preparation and reporting. Keep the current configured
Azure `gpt-5.4-mini` provider and loopback-only application boundary. Do not
silently substitute another homemade action engine or discard Twitter's default
recommendation model to reduce installation effort.

Approved change: the source graph and simulated-action episodes are stored
locally in SQLite, with typed nodes/edges, source spans and full-text retrieval.
Graph extraction and profile/action/report generation still use the configured
Azure model, under the app's existing consent boundary. There are no Zep calls,
Zep credentials or new cloud recipients. Local graph retrieval and temporal
semantics are tested independently and are not described as Zep-equivalent.

Reuse the installed OASIS/CAMEL libraries through adapters, and build the local
graph boundary independently. MiroFish remains the read-only behavioral
reference; do not copy its prompts or source unnecessarily. Any adopted
MiroFish service retains its AGPL-3.0 terms, attribution and original notices.
Do not imply that independent code automatically inherits reference behavior.

Separate these six capabilities and validate each before integrating the next:

1. **Source evidence and knowledge graph.** Accept source documents and a
   scenario; retain document identity and extracted text, generate an ontology,
   build entities/relationships, and expose the graph for inspection. Statements
   extracted by an LLM are attributed to sources, not asserted as independently
   verified facts. Graph writes have operation identity and an ingestion barrier.
2. **Graph-backed population.** Select a configurable number of entities or
   explicitly fictional stakeholder archetypes; enrich each with adjacent facts,
   relevant retrieval, history, interests, goals, existing relationships and
   speaking style. Distinguish source-grounded facts from invented biography,
   beliefs and social assumptions. Review the cast and graph before starting.
3. **Social environment and individual memory.** OASIS owns posts, comments,
   reactions, follows, groups and tool effects. CAMEL supplies scoped agent
   memory; an adapter saves/restores the appropriate state if supported, rather
   than promising continuity from a transcript alone. Keep document relationships
   distinct from social ties. Record assumed social ties explicitly with origins.
4. **Time and decisions.** Activate actors using configured schedules/activity
   and event exposure, not a nearest-person loop. Each decision receives its
   visible feed, permitted tools, personal memory and relevant conversation state.
   Store the observation IDs and selected action. Independent agents can work
   concurrently; a dependent response cannot see a draft as completed evidence.
5. **Durable events and reporting.** Save successful effects and safe decision
   outcomes immediately. Update graph memory with provenance, wait for ingestion,
   then run bounded evidence retrieval and sectioned report synthesis. Reports
   distinguish observed actions, interpretation, uncertainty and missing evidence.
6. **Simulation workbench.** Show room activity, knowledge/social graph, threaded
   discussion, person inspection, timeline and report as linked views of the same
   records. Coordinates visualize an interaction; they cannot cause it.

## Population And Budget Semantics

- Default `persona_count=10`; remove the coupled `MAX_AGENTS=10` assumptions from
  schema, roster IDs, preparation token limits, scheduler, UI and messages.
- Runtime resource limits remain explicit and configurable independently of
  population. A deployment ceiling is an operator setting, not a hidden product
  maximum. Never launch 1,000 simultaneous model requests because count is 1,000.
- Select diverse scenario-relevant roles from the full graph, not the first ten
  returned nodes. Persist the selected entity IDs and sampling policy. This is
  not statistically representative population sampling.
- If there are fewer eligible grounded actors, show the shortfall. Additional
  fictional archetypes require an explicit generation choice and are labelled
  synthetic; never manufacture source entities to hit the requested count.
- Generate profiles in bounded batches so changing population does not exceed a
  single structured-output/token ceiling. Keep stable identities across platforms.
- Active count varies by time and behavior; inactivity is valid and advances the
  simulation clock. A round no longer requires exactly one action per persona.
- Display population, active actors, model calls, reported usage and configured
  budget separately. Initial graph/profile calls and report tool calls also count.

## Natural Interaction And Room Extension

MiroFish's normal interactions are social posts, comments and quotes, not private
room conversations. Preserve those reference mechanisms. The requested room
mode is an explicit extension built on OASIS group and comment tools, not a
claim about the original MiroFish UI.

Participants choose to publish, respond, ask, join a discussion, react or remain
silent using their goals, exposed information, prior exchanges and relationships.
Record a short inspectable action reason, not hidden chain-of-thought. Do not
force everyone to disagree, concede or address a randomly assigned partner.

For direct conversation, the observation adapter includes only messages in
groups the actor belongs to, with completed message IDs and participant identity.
Tools validate membership and visible reply targets. Groups and discussion topics
may persist for multiple rounds; do not reserve fixed pairs for two turns and
discard them. Conflict, trust and opinion shifts must cite visible exchanges;
generated narrative is not a psychological measurement.

Builder decision: room groups belong to the Reddit OASIS environment. Twitter
and Reddit retain separate social state and agent memories, as in the reference,
while a stable persona identity connects their profiles in the UI. Do not silently
forward room messages into Twitter or share private group observations with
nonmembers. Graph episodes aggregate both platforms with explicit provenance;
that does not make all their contents visible to all agent decisions.

The room displays real group/thread membership and speaker/listener events.
Moving to another discussion reflects a committed join/leave or interaction
decision. Background idle animation is decoration only and is disabled under
reduced motion. Clicking a person shows their role, source facts, goals, known
relationships, exposed messages and public action history.

## UI And Pacing

Use a compact operational workbench rather than a marketing hero or a stack of
decorative cards: project/run navigation, scenario controls, a central observation
surface, a readable conversation pane and a contextual inspector. Provide Room,
Graph, Discussion and Report views with a shared selected person/action.

The room is an unframed, responsive isometric/3D scene with clear depth, stable
camera framing and visibly distinct people. Use Three.js for a true 3D scene;
validate its canvas and controls in desktop/mobile browsers. Graph inspection
uses a proven graph layout/renderer; list/table equivalents keep it accessible.
Prefer restrained charcoal/white surfaces with distinct teal, amber and red
semantic accents, readable typography and compact headings. Do not adopt the
design-search tool's landing page/glassmorphism template.

Keep complete speech in the conversation pane; bubbles are a preview, not the
only way to read text. Present time, activity, completed/draft status and failure
state clearly. The final report remains directly accessible from the run header.

Separate provider streaming, simulation time and viewer playback. Live drafts
are provisional; committed speech is durable. Playback has speed, pause, resume,
step and live-catch-up controls. Pausing the viewer must not be confused with
pausing generation. An optional readable run pace holds dependent exchanges for
a configurable dwell interval with interruptible waits; it does not falsely
label replayed text as new provider tokens. Reduced-motion disables movement,
not access to events. Never drop unseen completed turns to keep up visually.

## Failure And Saved-Run Guarantees

The exact originating exception of the previous third-round failure is unknown:
saved records contain only a generic `ValueError`. Preserve its 22 actions and
report it honestly; do not claim it was repaired by a speculative retry.

New decisions have allowlisted error codes, phase, actor, round, provider status
and safe target IDs. Do not log private source/model output or secret-bearing
exception strings. OASIS returning an exception object must be treated as a failed
decision even if `env.step` returns normally. Validation and tool execution share
one action contract. Invalid output cannot mutate social state or become evidence.

Differentiate completed, cancelled, interrupted and failed runs. Save completed
effects even if peers fail. No automatic paid restart/retry. Checkpoint/recovery
must not duplicate actions or claim agent-memory restoration without a tested
restore path. Wait for worker shutdown before releasing ownership.

Builder decision: the first release preserves interrupted experiments for
inspection but does not resume them automatically or claim exact continuation
of in-memory CAMEL state after a crash. A new experiment is a separate explicit
action, not a replay billed as recovery.

The commit unit is a successful platform tool effect, not an entire LLM decision
or round. One decision can produce several effects; previously completed effects
remain evidence if a later tool fails. Capture each effect and its platform trace
identity, then record the decision's overall outcome. On an unrecoverable error,
stop new scheduling, settle in-flight calls, and mark the run failed; never label
their incomplete batch successful merely because `env.step` returned.

Preserve OASIS's live observation semantics rather than claim snapshot isolation:
capture exactly what each agent received and when, and validate mutations against
committed visible IDs. Concurrent completion order is recorded, not predicted.
Deterministic tests control model completion order as well as scheduling seeds.
The adapter maps a canonical simulation tick to platform clocks explicitly;
inactive ticks advance time without dummy paid model calls. Record platform-native
timestamps separately so they are not mistaken for the canonical simulation time.

Version new runs and migrate storage additively. Old runs retain IDs, actions,
reports and export links, and remain readable as legacy discussions. Do not
fabricate historical graphs, memories, semantic reasons or movement for them.

## Acceptance Gates

1. Exact engine provenance and supported worker interpreter verified; provider
   integration tested through a local fake endpoint before any live paid run.
2. Graph extraction, selection, persona-source mapping, adjacency and retrieval
   tested; 10 is the default and a larger requested population works in batches.
3. Seeded scheduling with controlled-completion deterministic model fixtures
   reproduces decisions; real model reproducibility is not promised. Empty rounds
   advance canonical and mapped platform time without a model call.
4. Feed visibility and group membership tested: agents cannot reply to unseen,
   self, draft or nonexistent evidence; unrelated agents retain separate memories.
5. Actual OASIS action effects, failed-action detection and durable outcomes
   tested across at least three rounds, including partial failures and cancellation.
6. Source graph, social ties and group membership render differently and are
   linked to their provenance; positions never select a target.
7. Playback pause/step/speed and readable dwell tested without losing events;
   SSE reconnect, recovery and legacy saved-run fixtures remain passing.
8. Report citations resolve to committed source/actions; ingestion and terminal
   barriers enforced; report and optional persona interviews are reachable.
9. Browser checks at 375, 768 and 1440 pixels verify no overlapping controls,
   nonblank/framed scene, meaningful interactions, keyboard access and reduced
   motion. Full text is readable without chasing moving bubbles.
10. A separately authorized live end-to-end run verifies graph preparation,
    provider action selection, three-round persistence and reporting. Fixture
    success is never represented as live Zep/Azure verification.

## Decisions Requiring Approval

The user approved the local graph variant, with a separately managed Python
3.11 OASIS/CAMEL worker and the stated fidelity tradeoffs. No Zep Cloud transfer
is authorized. Credentials are configured directly on the machine, not collected
in chat. Neither approval nor installation grants permission to run unbounded
paid experiments. The implementation plan records the remaining execution steps.