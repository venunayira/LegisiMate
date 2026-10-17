# LegisiMate — Hackathon Submission Kit & Form Copy

All submission materials, code, documentation, and presentation artifacts are in **English** and mapped directly to the mandatory submission requirements and the four weighted judging criteria.

---

## 1. Quick Submission Checklist

| Mandatory Requirement | Artifact / Value in Repository | Status |
| --- | --- | --- |
| **Category Specification** | **Accessibility / Social Good / Sustainability** (*Sustainability & Social Impact — Access to Legal Preparation*) | Ready |
| **Clear Proposal (Deck converted to PDF)** | [LegisiMate-Proposal-Deck.pdf](LegisiMate-Proposal-Deck.pdf) (14-slide widescreen PDF) & [LegisiMate-presentation.html](LegisiMate-presentation.html) | Ready |
| **Functional Prototype (Google Cloud AI & Cloud Run / Firebase)** | Native **Google Gemini / Vertex AI** (`GeminiClient` in [legisimate/core.py](legisimate/core.py)) + **Cloud Run** ([Dockerfile](Dockerfile), [cloudbuild.yaml](cloudbuild.yaml), [scripts/deploy_cloud_run.sh](scripts/deploy_cloud_run.sh)) + **Firebase Hosting** ([firebase.json](firebase.json)) + pre-seeded verified showcase case ([data/showcase_cases.json](data/showcase_cases.json)) | Ready |
| **Live Cloud Run App** | [https://legisimate-587527883402.europe-west1.run.app/](https://legisimate-587527883402.europe-west1.run.app/) | Live |
| **Public GitHub Repository** | `https://github.com/venunayira/LegisiMate` | Live |
| **3-Minute Demo Video Link (YouTube / Vimeo / Google Drive)** | [https://youtu.be/-pd5MmUemtE](https://youtu.be/-pd5MmUemtE) (also in the repo as [LegisiMate.mp4](LegisiMate.mp4)) | Live |

---

## 2. Copy-Paste Submission Form Answers

### Project Title
**LegisiMate — Evidence-Backed Legal Case Preparation & Adversarial Rehearsal Workbench**

### Category Specification
- **Primary Category:** **Social Good** / **Accessibility** / **Sustainability** (*Sustainability & Social Impact*)
- **Social Challenge Addressed:** Bridging the legal preparation gap for individuals, micro/small businesses (MSMEs), junior advocates, and legal-aid clinics facing Section 138 negotiable-instrument (cheque dishonour) disputes in India.

### One-Line Pitch
LegisiMate aims to turn case facts into evidence-backed legal preparation across every country with a constitution; the proof of concept demonstrates that workflow through a selected Indian-law slice, independent courtroom hearings and an advocate-ready brief.

### Product Vision And Demo Scope
The intended product covers constitutions, legislation, regulations and relevant case law across **every country with a constitution**, rather than stopping at India or one dispute type. For this demo/POC, we deliberately selected **7,143 Indian statutory provisions and 10,139 judgment chunks across 1,600 cases** to exercise Section 138 cheque-dishonour preparation. This slice is not the full Indian corpus and is not evidence of implemented worldwide support. Wider coverage requires authoritative source access, language support, versioned jurisdiction rules and qualified local evaluation.

Every home-page load automatically starts a six-step guided tour over the real case form. It loads the fictional sample, explains what it filled in, the dates and records, the assessment date and the calendar review results, then shows where to start an own case and add TXT/Markdown/CSV notes, ending at hearing depth and consent. Users can skip it, and restart it from **Take the tour** in the page header. Notes do not parse dates, authenticate originals or support PDF/image extraction. Completing the tour never grants consent or starts model analysis automatically.

---

### Clear Proposal: Problem Statement & Community Benefit
1. **The Problem:**
   - Millions of individuals and small businesses face severe financial distress when commercial payments are dishonoured. Under Section 138 of the Negotiable Instruments Act, 1881, strict statutory clocks govern cheque presentation, the 30-day written demand notice (`Section 138 Proviso (b)`), the 15-day payment cure window (`Section 138 Proviso (c)`), and the 1-calendar-month complaint filing window (`Section 142(1)(b)`).
   - Citizens and small business owners frequently confuse the date printed on a bank return memo with the date bank information was received, overlook missing dispatch/service proof, or rely on generic AI chatbots that hallucinate legal citations, guess dates, and fabricate "win probabilities."
2. **How LegisiMate Benefits the Community:**
   - **Reduces the Preparation Barrier (Accessibility & Social Good):** Helps individuals and MSMEs organize confirmed vs. unconfirmed dates, identify missing documentary proof (return memos, postal receipts, ledger acknowledgements), and prepare structured questions before meeting a qualified advocate or legal-aid clinic.
  - **Binds Quoted Passages to Sources:** The model selects retrieved passage IDs (`quote_id`); the server attaches and verifies the exact corpus text. This constrains quotations, not every free-form legal assertion or its relevance. Interpretation and good-law status still require qualified review.
   - **Encourages Proportional, Informed Resolution:** Surfaces missing evidence and voluntary settlement considerations (`Section 147 NI Act` compounding) alongside adversarial preparation, keeping human judgement and professional legal review at the center.

---

### Alignment with the Four Weighted Judging Criteria

#### 1. Technical Merit & Gen AI Implementation (40%)
- **Meaningful Use of Generative AI:**
  - Generative AI (**Google Gemini** via Google AI Studio `GEMINI_API_KEY` or **Google Cloud Vertex AI** `GOOGLE_CLOUD_PROJECT`, plus OpenAI-compatible fallback) drives three distinct cognitive stages that static code cannot perform:
    1. **Bounded Agentic Legal Research (`ResearchDecision`):** Selects among `search_statutes`, `search_precedents`, `read_authority`, and `check_deadlines`, with at most four research decisions. The hearing-sized total ceiling is 72 calls by default and 93 at maximum settings.
    2. **Case-Specific Planning & Full Adversarial Hearings (`CasePlan` & `CaseStatement`):** Plans three independent questions, then schedules nine core participants: Magistrate, two lead counsel, two parties, two witnesses and two juniors. Each path includes openings, parties, direct and cross-examination, one to three rebuttal cycles and final bench assessment. Defaults produce 22 statements per path, 66 total. Optional 0-3 educational assessors are not an Indian jury. Missing testimony is not fabricated.
    3. **Actionable Case-Readiness Brief (`CaseBrief`):** Synthesizes confirmed timeline checks, rehearsed objections, evidence to collect, questions for an advocate, and voluntary resolution options.
- **Technical Soundness & Neuro-Symbolic Guardrails:**
  - **Deterministic Statutory Calendar Engine ([legisimate/casework.py](legisimate/casework.py)):** Never delegates date arithmetic to an LLM. Computes exact 30-day notice deadlines, 15-day cure periods, and true calendar-month complaint windows (`add_calendar_month`), while leaving missing dates explicitly unresolved.
  - **Source-Bound Quotation Verification (`grounded_statement_schema` & `verify_quotes`):** Dynamically binds each retrieved `source_id` to its `quote_id` passages. A complete fictional live OpenAI-compatible run recorded **69 statements, 10 participants, 73/75 allowed calls and 206/206 source-text quotation matches**. The packaged nine-statement showcase is an older compatibility example, not the new hearing depth. Neither result establishes legal accuracy or Gemini/cloud deployment.
  - **Local SQLite + FTS5 Legal Corpus ([legisimate/legal.py](legisimate/legal.py)):** Indexes **7,143 statutory/regulatory provisions** and **10,139 reconstructed chunks across 1,600 Supreme Court, Delhi HC, and Bombay HC judgments** with hierarchy and section-priority weighting, auto-materialized in ~1.5 seconds from tracked Parquet slices (`11.8 MB`).

#### 2. Problem Alignment & Impact (25%)
- Directly targets **Accessibility, Social Good & Sustainability** by empowering underserved citizens, MSMEs, law students, and legal-aid clinics with structured, source-verifiable pre-consultation preparation.
- Refuses to act as a black-box "verdict predictor": when critical dates or service records are missing, automatic guardrails downgrade any overly optimistic `"supported"` model label to `"needs_evidence"` and disclose what documents must be collected.

#### 3. Innovation & Creativity (25%)
- **Adversarial Multi-Path Rehearsal with Fresh Memory:** Plans three case-specific questions and conducts full hearings with parties, witnesses, cross-examination, juniors and rebuttals. Conversation and reply links reset for every path; no winning branch is preset.
- **Interactive Hearing Tree:** Select a path/stage node or its keyboard-accessible list to inspect recorded statements and quotations, then open that exact statement in courtroom replay. This visualises recorded alternatives; it is not a calibrated strategy-search engine.
- **Interactive 2.5D Courtroom Replay + Brief-First Workbench:** Pairs a serious, document-first legal readiness brief with an accessible 2.5D architectural courtroom replay ([web/room.js](web/room.js)) featuring word-by-word readable speech pacing, role-specific Indian judicial/advocate attire, and one-click source inspection.

#### 4. User Experience & Solution Design (10%)
- **Six Cohesive Views in One Accessible Workbench ([web/cases.html](web/cases.html)):**
  1. **Case Details & Live Calendar Preview:** Instant client/server date checks without calling the model until explicit user consent is granted.
  2. **Readiness Brief:** Clear recommendation, next-step checklist, questions for an advocate, and Markdown export.
  3. **Argument Paths:** Side-by-side comparison of the three rehearsed paths with `what_to_say`, `why_it_matters`, and verified quotation badges.
  4. **Decision Tree:** Independent paths and hearing stages with speech/citation inspection and exact-statement replay links.
  5. **Courtroom Rehearsal:** Readable 2.5D replay with separate party/witness seating, previous/next, statement jump, play/pause, speed and reduced-motion support.
  6. **Research & Sources:** Full agentic tool trace and full-text statutory/judgment drawer.

Verification on 2026-10-17: all 124 backend tests passed, including the optional legacy engine, plus Node graph/playback checks. Browser fixtures completed the 12-person, 87-statement maximum and checked cancellation, sources, export, reload and mobile layout. A separate full live run used the configured OpenAI-compatible model, not Gemini. These are integration checks, not legal-accuracy or hosting evaluations.

---

### Feasibility, Scalability & Google Cloud Compatibility
- **Stateless Cloud Run Container + Pre-Built Legal Index:** The [Dockerfile](Dockerfile) compiles `legal_poc.db` (`7,143` provisions + `10,139` judgment chunks) during image build so Cloud Run instances start in `< 1 second` with zero external database dependencies.
- **Google Gemini & Vertex AI Native Adapter:** [legisimate/core.py](legisimate/core.py) (`GeminiClient`) connects directly to Google AI Studio (`GEMINI_API_KEY`) or Google Cloud Vertex AI (`GOOGLE_CLOUD_PROJECT` using Cloud Run's default service account via the GCE metadata server—no API keys baked into the container).
- **International Scalability via Versioned Jurisdiction Packs:** As detailed in Slides 09–12 of [LegisiMate-Proposal-Deck.pdf](LegisiMate-Proposal-Deck.pdf), the core engine (deterministic rule module + scoped hybrid RAG + source-bound passage contract + isolated multi-role rehearsal) is jurisdiction-agnostic and scales to new legal domains and countries through versioned, rights-verified Jurisdiction Packs (Akoma Ntoso / ELI / USLM).

---

## 3. Deploying to Google Cloud Run / Firebase (1 Command)

You can deploy from **Google Cloud Shell** (recommended—pre-authenticated with `gcloud` and bypasses local corporate proxy restrictions) or any terminal with `gcloud` installed:

```bash
# 1. Clone the public repository in Google Cloud Shell
git clone https://github.com/venunayira/LegisiMate.git
cd LegisiMate

# 2. Set your Google Cloud Project ID and (optionally) Gemini API Key
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GEMINI_API_KEY="your-gemini-api-key"   # Optional if Vertex AI API is enabled on the project

# 3. Deploy to Google Cloud Run (asia-south1)
chmod +x scripts/deploy_cloud_run.sh
./scripts/deploy_cloud_run.sh
```

Or run the `gcloud run deploy` command directly:

```bash
gcloud run deploy legisimate \
  --source . \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project),GEMINI_MODEL=gemini-2.5-flash"
```

Once deployed, the Cloud Run URL immediately serves:
- **Live Case-Preparation Workbench:** `https://<your-cloud-run-url>/`
- **Pre-Seeded Verified Showcase Case:** `https://<your-cloud-run-url>/?case=c810d87708f94f318b01a2d80dc570e9`
- **Health Check Endpoint:** `https://<your-cloud-run-url>/healthz`

The submitted public deployment is [https://legisimate-587527883402.europe-west1.run.app/](https://legisimate-587527883402.europe-west1.run.app/).

---

## 4. 3-Minute Demo Video (YouTube / Vimeo / Google Drive)

**Watch:** [https://youtu.be/-pd5MmUemtE](https://youtu.be/-pd5MmUemtE)

The demo is a 2:49 motion-graphics explainer generated from real captures of the running workbench and the proposal deck. It is narrated by the macOS "Aman" voice (Indian English), with captions burned in, a separate SRT file, and a music bed generated locally. All case data shown is fictional: the packaged showcase case `c810d877…` (recorded with Gemini 2.5 Flash) supplies the brief, research trace and 27/27 quotation result; the fictional verification case `de055d87…` supplies the full-hearing decision tree and courtroom footage.

A 720p copy is committed as [LegisiMate.mp4](LegisiMate.mp4). Rendered build outputs (not committed): `video/build/LegisiMate-explainer-1080p.mp4` and `video/build/LegisiMate-explainer.srt`. To regenerate them with the workbench running on port 8765:

```sh
.venv/bin/python video/build_audio.py                                     # narration, timeline, captions, SRT
swiftc -O video/audio.swift -o video/build/audio && video/build/audio video # music bed, sound effects, mix
swiftc -O video/studio.swift -o video/build/studio
video/build/studio capture video/shots.json                               # product and deck captures
video/build/studio render video/explainer.html video/build/mix.wav video/build/LegisiMate-explainer-1080p.mp4
```

To screen record instead of rendering: run `.venv/bin/python video/serve.py`, open `http://127.0.0.1:8899/video/explainer.html?play` in Safari or Chrome, press **F** for full screen, start a screen recording, then click. A white sync flash precedes playback, so the recording can be silent:

```sh
video/build/studio addaudio "<recording>.mov" video/build/mix.wav video/build/LegisiMate-explainer.mp4
```

This finds the flash, crops the player area to 1920x1080, trims to the narration length and adds the narration and music.

| Time | Scene | On screen | Narration |
| --- | --- | --- | --- |
| **0:00 – 0:07** | Opening | Scales icon draws itself; LegisiMate wordmark and tagline | *(music)* |
| **0:07 – 0:35** | The problem | The three case documents, a statutory clock (30 / 15 days, 1 month), open questions, a chatbot answer with a guessed date and a missing citation | *"When a small business owner in India has a ₹2.4 lakh cheque dishonoured, the hardest part comes before court. Which dates start the statutory clock under Section 138 of the Negotiable Instruments Act? Which documents are missing? What will the other side argue? Generic chatbots guess dates and invent citations. So we built LegisiMate: an evidence-backed legal preparation workbench, for accessibility and social good."* |
| **0:35 – 1:03** | Case details & calendar | Load sample case, the guided tour, the Dates & records fields, a timeline computed from the sample dates, and the "Not confirmed" check after the receipt date is cleared | *"In the workbench, you enter anonymised facts, or load our sample textile-supply dispute. A guided tour walks new users through every field. Before any AI model is called, deterministic code checks the dates: the thirty-day window for the demand notice, the fifteen-day payment period, and the one-calendar-month filing window under Section 142. If the notice receipt date isn't confirmed, LegisiMate marks it "not confirmed" instead of guessing."* |
| **1:03 – 1:36** | Research & sources | Readiness brief, corpus counters (7,143 provisions, 10,139 judgment passages), the agent trace, passage-ID binding to stored Section 138(c) text, and 27/27 matched quotations | *"With explicit consent, a bounded research agent, Gemini in this showcase case, searches a local legal index: more than 7,000 Indian statutory provisions, and 10,000 Supreme Court and High Court judgment passages. Every tool call is visible. And the model can't invent a quotation: it must pick a passage ID from the retrieved sources, and the server checks the text. In this case, all 27 quotations match their sources exactly. That proves where each quote comes from, not that an argument is right."* |
| **1:36 – 2:10** | Courtroom hearings | Three independent paths and their stages, the nine core roles, the 22-statement schedule, the decision-tree inspector and courtroom replay | *"Then LegisiMate rehearses three case-specific hearings, each starting fresh. Parties speak. Witnesses face direct and cross-examination. Junior counsel join the rebuttals, and the magistrate closes. That's 22 statements per path, by default. The decision tree links every stage to the actual speeches and their sources. Open any statement, and replay it in the courtroom. The magistrate, counsel, parties and witnesses each take their own seat. Optional assessors give educational feedback only. Never a jury, and never a promised outcome."* |
| **2:10 – 2:49** | Brief, architecture & vision | The exported brief, local storage and consent, the architecture slide, a globe with the Indian-law slice today and planned jurisdiction packs, closing logo | *"You leave with a downloadable readiness brief: documents to collect, and questions for your advocate. Cases are saved locally, and nothing goes to a model without your consent. Date rules run as code, retrieval runs locally, and Gemini and Vertex AI adapters are built in, packaged for Cloud Run. This demo uses a selected slice of Indian law. The goal is every country with a constitution, through versioned, locally verified jurisdiction packs. LegisiMate. Justice begins with preparation."* |
