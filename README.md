# LegisiMate: Evidence-Backed Case Preparation

A Section 138 cheque-dishonour legal preparation workbench for individuals, small businesses, and advocates, submitted under **Accessibility, Social Good & Sustainability** (*Sustainability & Social Impact*). It combines deterministic statutory calendar checks, a bounded tool-using research agent, local primary-law retrieval (**7,143 statutory provisions** and **10,139 Supreme Court / High Court judgment chunks**), source-bound quotation verification, and three isolated adversarial argument rehearsals.

### Hackathon Submission Artifacts

| Requirement | Artifact / Link |
| --- | --- |
| **Category Specification** | **Accessibility / Social Good / Sustainability** (*Sustainability & Social Impact*) |
| **Proposal Deck (PDF)** | [LegisiMate-Proposal-Deck.pdf](LegisiMate-Proposal-Deck.pdf) (14-slide widescreen PDF converted from [LegisiMate-presentation.html](LegisiMate-presentation.html)) |
| **Submission Guide & 3-Min Video Script** | [SUBMISSION.md](SUBMISSION.md) (Full rubric alignment, Cloud Run deploy commands, and 3-minute video script) |
| **Google Cloud AI & Cloud Run / Firebase** | Native **Google Gemini / Vertex AI** (`GeminiClient` in [misofish/core.py](misofish/core.py)) + **Cloud Run** ([Dockerfile](Dockerfile), [cloudbuild.yaml](cloudbuild.yaml), [scripts/deploy_cloud_run.sh](scripts/deploy_cloud_run.sh)) + **Firebase Hosting** ([firebase.json](firebase.json)) |
| **Pre-Seeded Showcase Case** | [data/showcase_cases.json](data/showcase_cases.json) (`/?case=c810d87708f94f318b01a2d80dc570e9` — 27/27 verified quotes across 9 turns & 3 paths) |

## Current Workbench

The home page at **http://127.0.0.1:8765/** (and on Cloud Run) provides:

- Confirmed-input date checks for notice, payment and complaint periods; missing dates remain unresolved. A calendar month is not treated as 30 days.
- Consent-based model analysis of anonymised facts and optional text extracts. Text, Markdown and CSV notes are supported; PDF/image OCR is not implemented.
- An inspectable research loop choosing statute searches, precedent searches, source reads and deadline checks, with a four-step research bound and a 36-call overall cap.
- Three case-specific argument paths, each with fresh conversation state: opposing counsel, the selected side's counsel and a neutral Magistrate. There is no jury or preset winning branch in this workflow.
- Source-bound passage IDs: the model selects a known source and passage; the server attaches its exact corpus text and checks the match. A matched quotation does not validate the legal interpretation or establish that a precedent is still good law.
- A preparation brief with missing evidence, next steps, advocate questions and voluntary-resolution considerations. Unknown or review-needed inputs qualify supportive model assessments.
- Saved local cases, cancellation, source inspection, Markdown export, local-record deletion and readable 2.5D courtroom replay. Changing saved inputs creates a new analysis; it does not overwrite the original.

The server supports **Google Gemini** (`GEMINI_API_KEY`), **Google Cloud Vertex AI** (`GOOGLE_CLOUD_PROJECT`), and OpenAI Responses-compatible providers (`OPENAI_API_KEY`), and ships with a Cloud Run `Dockerfile` and pre-seeded showcase casework (`data/showcase_cases.json`). No accuracy, judicial-outcome probability, automated filing or legal-clearance claim is made.

Case facts, notes, results and research are plaintext in the local `casework` table in `data/runs.db`. Consent is required before model analysis. Deleting a case removes its database record, not copies already sent to the provider, downloaded exports or a secure erasure of storage pages. Use synthetic or properly anonymised cases for demonstrations.

## Legacy Simulator

The original Misofish simulation is preserved at **http://127.0.0.1:8765/legacy**, including existing saved experiments. The capabilities below describe that legacy workflow. Its model-generated win percentages are not calibrated predictions and are not used in the new readiness brief.

---

### Legacy Capabilities

1. **Multiverse Legal Decision Tree ("Doctor Strange" Outcome Branches):**
   - Each tick represents a distinct **Outcome Branch (`Future #1..#N`)** in a litigation decision tree rather than a generic chat round:
     - **Future #1 (*Threshold Statutory & Procedural Bar Path*):** Tests what happens when Complainant relies on bare statutory presumption (`Sec 139 NI Act` / `Sec 74 Contract Act`) without documentary timeline proof, and Defense attacks threshold maintainability (`30-day notice clock under Sec 138 Proviso (b)`, `Limitation Act time-bar`, or unproved loss under `Sec 73`).
     - **Future #2 (*Evidentiary Corroboration vs. Commercial Breach Counter-Claim*):** Tests witness cross-examination on primary ledger/dispatch records against substantive commercial breach (`Sec 39, 55, 56 Contract Act`, stop-payment on a security cheque prior to debt crystallization, and `Sec 141(1) Proviso` director immunity).
     - **Future #3 (*The Winning Playbook — Full Statutory + Documentary + SC Precedent Cure*):** Tests the complete winning strategy where Counsel proves statutory timeline compliance, establishes crystallized debt or mitigated damages through witness records, and invokes binding Supreme Court `ratio_decidendi` under `Article 141 of the Constitution of India`.
     - **Futures #4–#10:** Explore interim remedies (`Sec 143A/148 NI Act`, `Specific Relief Act` injunctions), compounding (`Sec 147`), and restitution (`Sec 64/65`).
   - Every courtroom turn produces structured tactical guidance:
     - **`if_opponent_argues`** — the exact opposing claim or judicial question being countered.
     - **`tactical_move`** — what to state and argue at this node of the trial.
     - **`counter_strategy`** — the actionable legal takeaway and statutory/case citations.
     - **`branch_outcome` & `win_probability`** — real-time Complainant vs. Defense win meter (`0–100%`).

2. **Fixed Court Officers + Configurable Jury Panel:**
   - Every courtroom trial automatically seats **7 fixed Court Officers**:
     1. `Presiding Judge (Bench)`
     2. `Complainant / Plaintiff Lead Counsel`
     3. `Accused / Respondent Defense Counsel`
     4. `Complainant / Plaintiff Key Witness`
     5. `Accused / Respondent Key Witness`
     6. `Junior Counsel for Complainant / Plaintiff`
     7. `Junior Counsel for Accused / Respondent`
   - You choose the number of **`Jury Members`** (`1..12`, default `3`: *Foreperson*, *Banking & Commercial Assessor*, *Statutory & Evidentiary Assessor*, etc.).

3. **2.5D Architectural Courtroom View (`web/room.js`):**
   - Top-center elevated **Presiding Bench** dais with stairs, flanked by the **Witness Stand** (left) and **Court Clerk** box (right).
   - Stepped 2-column **Jury Box** along the left wall, **Party / Witness Dock** on the right wall, two parallel **Counsel Tables** in the well of the court, and a **Public Gallery** behind the Bar Railing with 3 rows of seated audience members.
   - Modelled Indian courtroom attire: black judicial robe with crimson stole and white collar bands for the Presiding Judge; black advocate gowns with white neck bands and side lapel badges for Complainant and Defense Counsel.
   - Non-occluding speech bubbles with active speaker spotlight halos so the speaker and Bench are always visible.

4. **Live Per-Turn Indian Legal RAG (`misofish/legal.py`):**
   - Before every single courtroom turn, `retrieve_turn_authorities()` queries the local SQLite + FTS5 legal corpus (`data/open_india_law/legal_poc.db`) using the opponent's latest remarks.
   - Weights results by Indian court hierarchy (`Supreme Court of India` > `High Court`), `bench_strength`, and `section_priority` (`ratio_decidendi`, `conclusion`, `analysis`, `arguments`, `facts`), boosting statutory provisos (`has_proviso`, `has_non_obstante`) for Defense Counsel.

---

## Where Is the Data Stored?

All data lives under the `data/` directory at the repository root:

| Path | Size | Tracked in Git? | Description |
| --- | ---: | :---: | --- |
| `data/open_india_law/target_legislation.parquet` | **2.1 MB** | **Yes** | **7,143 English provisions** across 14 sources: *Negotiable Instruments Act 1881*, *Indian Contract Act 1872*, *Specific Relief Act 1963*, *Limitation Act 1963*, *Payment & Settlement Systems Act 2007*, *Arbitration & Conciliation Act 1996*, *CPC 1908*, *BNSS 2023*, *BSA 2023 / Evidence Act 1872*, *Constitution of India 1950* (465 Articles + Preamble), *RBI Cheque & Payment Directions*, and *Delhi & Maharashtra Commercial/Procedural Acts*. |
| `data/open_india_law/domain_judgments.parquet` | **9.7 MB** | **Yes** | **1,600 complete multi-chunk English judgments** (**10,139 contiguous chunks**, `0..total_chunks-1`) from the **Supreme Court of India** (318 cases), **Delhi High Court** (665 cases), and **Bombay High Court** (617 cases). |
| `data/open_india_law/extraction_manifest.json` | **4.0 KB** | **Yes** | SHA-256 verification digests, court scan statistics, and provision counts from Open India Law `v2026.08.1`. |
| `data/open_india_law/legal_poc.db` | **144 MB** | Auto-built (gitignored) | Local **SQLite + FTS5** RAG database (`legislation_provisions`, `judgment_cases`, `judgment_chunks`, `case_citations` with **12,714 citation edges**, and `legal_fts`). **Automatically built in ~1.5 seconds on first run** from the two tracked Parquet files above via `ensure_legal_db()` in `misofish/legal.py`. |
| `data/open_india_law/target_legislation.csv` & `domain_judgments.csv` | **51 MB** | Local export (gitignored) | Optional flat CSV exports generated by `scripts/extract_open_india_law.py`. |
| `data/open_india_law/raw/` | **121 MB** | Local cache (gitignored) | Cached upstream Parquet files downloaded from `https://oss-data-in.vaquill.ai/v2026.08.1/`. |
| `data/runs.db` | **~4 MB** | Local state (gitignored) | SQLite store holding your saved simulation runs, event streams, and local evidence graphs. |

Because `target_legislation.parquet` (2.1 MB) and `domain_judgments.parquet` (9.7 MB) are committed to Git and `misofish/legal.py` auto-builds `legal_poc.db` on startup if missing, **any developer who clones this repository gets the full Indian Legal RAG corpus working immediately without downloading 10+ GB of upstream files.**

---

## Developer Quick Start

### 1. Clone & Install Dependencies

Requires Python 3.11+ on macOS/Linux.

```sh
git clone https://github.com/venunayira/LegisiMate.git
cd LegisiMate
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

### 2. Configure Your Model Endpoint (`.env`)

Create a `.env` file in the project root (ignored by Git):

```sh
OPENAI_API_KEY="your-api-key"
# Optional custom endpoint / model (defaults to OpenAI API and gpt-4o-mini):
OPENAI_BASE_URL="http://127.0.0.1:4010/v1"
OPENAI_MODEL="gpt-5.4-mini"
MISOFISH_MODEL_TIMEOUT="180"
```

### 3. Start the Workbench Server

```sh
./run.sh --port 8765
```

Open **http://127.0.0.1:8765** in your browser:
1. Enter an anonymised cheque-dishonour case or use **Load sample case**. Select recipient or issuer, and confirm only dates supported by records.
2. Review the calendar checks. Add optional text extracts, give consent, and select **Analyse case**.
3. Inspect the readiness brief, argument paths, source quotations and agent activity. The courtroom replays the recorded statements; it is not a real judicial ruling.
4. Download the brief or delete its local saved record when finished. **Legacy experiments** opens the previous simulator.

Courtroom analysis does not require the optional OASIS worker. Only one analysis or legacy experiment runs at a time to keep model-call accounting isolated. Failed or cancelled analyses retain their completed checks and sources.

---

## Expanding or Rebuilding the Legal Corpus

To re-run or expand the extraction from Vaquill AI's Open India Law (`v2026.08.1`) public mirror (`https://oss-data-in.vaquill.ai/v2026.08.1/`):

```sh
# Fast rebuild of SQLite FTS5 DB + CSVs from cached judgments (~2 seconds):
.venv/bin/python scripts/extract_open_india_law.py --reuse-cached-judgments

# Expand High Court row-group coverage from the remote mirror via HTTP Range streaming:
.venv/bin/python scripts/extract_open_india_law.py --sc-row-groups 56 --hc-row-groups 16 --max-cases-per-domain 1000 --workers 12
```

---

## Running Tests & Verification

The historical server tests additionally import `httpx` (test-only). Install it with the approved package registry if missing. The `test_engine` module requires the optional OASIS worker environment; it is not required by the current casework application.

```sh
# Run the full Python test suite (courtroom, Open India Law RAG, graph, town, server, SDK):
PYTHONPATH=tests .venv/bin/python -W default -m unittest discover -s tests -v

# Run frontend JavaScript syntax and VM regressions:
node --check web/app.js
node --check web/cases.js
node --check web/room.js
node tests/check_room_speech.js
node tests/check_social_graph.js
```

Local verification on 2026-10-17: all 102 backend tests outside the optional 18-test OASIS module passed, as did the JavaScript regressions. The five workbench views were checked at 390, 768 and 1440 pixels, including consent, invalid dates, source inspection, export, actor selection and deletion. A live model workflow exposed free-form quotation failures; the corrected passage-ID contract was then checked with the provider and the revised workflow with deterministic tests. This is integration evidence, not a legal-accuracy or outcome-prediction evaluation.

---

## Repository Structure

- [misofish/casework.py](misofish/casework.py) - date checks, consent/request schemas, bounded research tools, source-bound quotations, independent paths, local case storage and export.
- [web/cases.html](web/cases.html), [web/cases.css](web/cases.css), [web/cases.js](web/cases.js) - the current brief-first workbench.
- [tests/test_casework.py](tests/test_casework.py) - timeline boundaries, missing facts, source pairing, independent paths, failure preservation and cancellation regressions.
- `misofish/court.py` — Indian Courtroom Trial & Multiverse Decision-Tree engine (`Future #1..#N`, `CourtUtterance`, fixed Court Officers + configurable Jury Panel).
- `misofish/legal.py` — SQLite + FTS5 Indian Legal RAG retriever (`retrieve_legal_dossier`, `retrieve_turn_authorities`, `ensure_legal_db`).
- `scripts/extract_open_india_law.py` — 2-Range coalesced Parquet extractor for Open India Law `v2026.08.1` + Constitution of India + Section 73 repair + citation graph extractor.
- `misofish/graph.py` — Verbatim quote-validated evidence graph builder and SQLite FTS5 `GraphStore`.
- `misofish/core.py` — Strict Pydantic schemas, persona preparation, and grounded report synthesis.
- `misofish/town.py` — Seeded 3-stage randomized group conversations.
- `misofish/server.py` — Loopback HTTP server (`/api/cases`, `/api/cases/timeline`, `/api/authorities/{id}`, `/api/config`) and legacy run/SSE routes.
- `web/room.js`, `web/app.js`, `web/index.html`, `web/room.css`, `web/style.css` — 2.5D Courtroom canvas, Future outcome cards, 4-box Strategy Playbook card, and Cytoscape Decision-Tree viewer.
- `data/open_india_law/` — Extracted Indian legislation & court judgment Parquet slices and auto-materialized SQLite FTS5 RAG database.

## Attribution & Disclaimer

- **Legal Corpus Attribution:** Structured Indian primary-law data extracted from the [Open India Law (`v2026.08.1`)](https://github.com/Vaquill-AI/open-india-law) corpus by Vaquill AI (CC BY 4.0) and the Constitution of India (Government work under s.17(d) / s.52(1)(q) of the Copyright Act, 1957).
- **Disclaimer:** Synthetic scenario and litigation-strategy exploration for research and legal education. Not legal advice or a calibrated judicial forecast.