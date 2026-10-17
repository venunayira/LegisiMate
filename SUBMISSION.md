# LegisiMate — Hackathon Submission Kit & Form Copy

All submission materials, code, documentation, and presentation artifacts are in **English** and mapped directly to the mandatory submission requirements and the four weighted judging criteria.

---

## 1. Quick Submission Checklist

| Mandatory Requirement | Artifact / Value in Repository | Status |
| --- | --- | --- |
| **Category Specification** | **Accessibility / Social Good / Sustainability** (*Sustainability & Social Impact — Access to Legal Preparation*) | Ready |
| **Clear Proposal (Deck converted to PDF)** | [LegisiMate-Proposal-Deck.pdf](LegisiMate-Proposal-Deck.pdf) (14-slide widescreen PDF) & [LegisiMate-presentation.html](LegisiMate-presentation.html) | Ready |
| **Functional Prototype (Google Cloud AI & Cloud Run / Firebase)** | Native **Google Gemini / Vertex AI** (`GeminiClient` in [misofish/core.py](misofish/core.py)) + **Cloud Run** ([Dockerfile](Dockerfile), [cloudbuild.yaml](cloudbuild.yaml), [scripts/deploy_cloud_run.sh](scripts/deploy_cloud_run.sh)) + **Firebase Hosting** ([firebase.json](firebase.json)) + pre-seeded verified showcase case ([data/showcase_cases.json](data/showcase_cases.json)) | Ready |
| **Public GitHub Repository** | `https://github.com/venunayira/LegisiMate` | Live |
| **3-Minute Demo Video Link (YouTube / Vimeo / Google Drive)** | Follow the exact 3-minute recording script in Section 4 below | Script Ready |

---

## 2. Copy-Paste Submission Form Answers

### Project Title
**LegisiMate — Evidence-Backed Legal Case Preparation & Adversarial Rehearsal Workbench**

### Category Specification
- **Primary Category:** **Social Good** / **Accessibility** / **Sustainability** (*Sustainability & Social Impact*)
- **Social Challenge Addressed:** Bridging the legal preparation gap for individuals, micro/small businesses (MSMEs), junior advocates, and legal-aid clinics facing Section 138 negotiable-instrument (cheque dishonour) disputes in India.

### One-Line Pitch
LegisiMate turns scattered payment-dispute facts into a deterministic statutory timeline check, a bounded agentic legal-research trace over 7,143 Indian statutory provisions and 10,139 court judgment chunks, three isolated adversarial courtroom rehearsals with 100% source-bound quotations, and an actionable Case-Readiness Brief for human advocates.

---

### Clear Proposal: Problem Statement & Community Benefit
1. **The Problem:**
   - Millions of individuals and small businesses face severe financial distress when commercial payments are dishonoured. Under Section 138 of the Negotiable Instruments Act, 1881, strict statutory clocks govern cheque presentation, the 30-day written demand notice (`Section 138 Proviso (b)`), the 15-day payment cure window (`Section 138 Proviso (c)`), and the 1-calendar-month complaint filing window (`Section 142(1)(b)`).
   - Citizens and small business owners frequently confuse the date printed on a bank return memo with the date bank information was received, overlook missing dispatch/service proof, or rely on generic AI chatbots that hallucinate legal citations, guess dates, and fabricate "win probabilities."
2. **How LegisiMate Benefits the Community:**
   - **Reduces the Preparation Barrier (Accessibility & Social Good):** Helps individuals and MSMEs organize confirmed vs. unconfirmed dates, identify missing documentary proof (return memos, postal receipts, ledger acknowledgements), and prepare structured questions before meeting a qualified advocate or legal-aid clinic.
   - **Eliminates Hallucinated Legal Citations:** The generative model cannot invent a statutory quote or case passage. Instead, it selects from retrieved source passage IDs (`quote_id`), and the server deterministically attaches and verifies the exact text from the local Open India Law corpus.
   - **Encourages Proportional, Informed Resolution:** Surfaces missing evidence and voluntary settlement considerations (`Section 147 NI Act` compounding) alongside adversarial preparation, keeping human judgement and professional legal review at the center.

---

### Alignment with the Four Weighted Judging Criteria

#### 1. Technical Merit & Gen AI Implementation (40%)
- **Meaningful Use of Generative AI:**
  - Generative AI (**Google Gemini** via Google AI Studio `GEMINI_API_KEY` or **Google Cloud Vertex AI** `GOOGLE_CLOUD_PROJECT`, plus OpenAI-compatible fallback) drives three distinct cognitive stages that static code cannot perform:
    1. **Bounded Agentic Legal Research (`ResearchDecision`):** Iteratively selects among `search_statutes`, `search_precedents`, `read_authority`, and `check_deadlines` (bounded to $\le 4$ research decisions and a 36-call hard cap) to uncover both supporting and adverse authorities.
    2. **Case-Specific Path Planning & Isolated Adversarial Rehearsal (`CasePlan` & `CaseStatement`):** Generates three independent preparation paths tailored to the user's facts (e.g., *Notice & Service Maintainability*, *Security Cheque & Enforceable Debt*, *Documentary Cure & Resolution*) and rehearses each path across **Opposing Counsel $\rightarrow$ Selected Side's Counsel $\rightarrow$ Neutral Magistrate** with isolated conversation memory per path.
    3. **Actionable Case-Readiness Brief (`CaseBrief`):** Synthesizes confirmed timeline checks, rehearsed objections, evidence to collect, questions for an advocate, and voluntary resolution options.
- **Technical Soundness & Neuro-Symbolic Guardrails:**
  - **Deterministic Statutory Calendar Engine ([misofish/casework.py](misofish/casework.py)):** Never delegates date arithmetic to an LLM. Computes exact 30-day notice deadlines, 15-day cure periods, and true calendar-month complaint windows (`add_calendar_month`), while leaving missing dates explicitly unresolved.
  - **Source-Bound Quotation Verification (`grounded_statement_schema` & `verify_quotes`):** Dynamically constructs a per-turn Pydantic schema binding each retrieved `source_id` to its exact `quote_id` passages. In our verified showcase case (`c810d87708f94f318b01a2d80dc570e9`), **27 / 27 (100%)** cited passages across 9 courtroom turns match the primary corpus character-for-character.
  - **Local SQLite + FTS5 Legal Corpus ([misofish/legal.py](misofish/legal.py)):** Indexes **7,143 statutory/regulatory provisions** and **10,139 reconstructed chunks across 1,600 Supreme Court, Delhi HC, and Bombay HC judgments** with hierarchy and section-priority weighting, auto-materialized in ~1.5 seconds from tracked Parquet slices (`11.8 MB`).

#### 2. Problem Alignment & Impact (25%)
- Directly targets **Accessibility, Social Good & Sustainability** by empowering underserved citizens, MSMEs, law students, and legal-aid clinics with structured, source-verifiable pre-consultation preparation.
- Refuses to act as a black-box "verdict predictor": when critical dates or service records are missing, automatic guardrails downgrade any overly optimistic `"supported"` model label to `"needs_evidence"` and disclose what documents must be collected.

#### 3. Innovation & Creativity (25%)
- **Adversarial Multi-Path Rehearsal with Fresh Memory:** Unlike single-turn legal chatbots or scripted simulations with preset winners, LegisiMate plans three case-specific questions from the retrieved law and rehearses each in an isolated courtroom exchange (Opposing Counsel, Your Counsel, Neutral Magistrate) without cross-branch memory contamination.
- **Interactive 2.5D Courtroom Replay + Brief-First Workbench:** Pairs a serious, document-first legal readiness brief with an accessible 2.5D architectural courtroom replay ([web/room.js](web/room.js)) featuring word-by-word readable speech pacing, role-specific Indian judicial/advocate attire, and one-click source inspection.

#### 4. User Experience & Solution Design (10%)
- **Five Cohesive Views in One Accessible Workbench ([web/cases.html](web/cases.html)):**
  1. **Case Details & Live Calendar Preview:** Instant client/server date checks without calling the model until explicit user consent is granted.
  2. **Readiness Brief:** Clear recommendation, next-step checklist, questions for an advocate, and Markdown export.
  3. **Argument Paths:** Side-by-side comparison of the three rehearsed paths with `what_to_say`, `why_it_matters`, and verified quotation badges.
  4. **Courtroom Rehearsal:** Readable 2.5D visual replay of each path with play/pause, speed controls, and reduced-motion support.
  5. **Research & Sources:** Full agentic tool trace and full-text statutory/judgment drawer.

---

### Feasibility, Scalability & Google Cloud Compatibility
- **Stateless Cloud Run Container + Pre-Built Legal Index:** The [Dockerfile](Dockerfile) compiles `legal_poc.db` (`7,143` provisions + `10,139` judgment chunks) during image build so Cloud Run instances start in `< 1 second` with zero external database dependencies.
- **Google Gemini & Vertex AI Native Adapter:** [misofish/core.py](misofish/core.py) (`GeminiClient`) connects directly to Google AI Studio (`GEMINI_API_KEY`) or Google Cloud Vertex AI (`GOOGLE_CLOUD_PROJECT` using Cloud Run's default service account via the GCE metadata server—no API keys baked into the container).
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

---

## 4. 3-Minute Demo Video Script (YouTube / Vimeo / Google Drive)

Record at `1440x900` or `1920x1080` with two tabs open:
- **Tab 1:** [LegisiMate-presentation.html](LegisiMate-presentation.html) (Interactive Proposal Deck)
- **Tab 2:** Live LegisiMate Workbench (`/?case=c810d87708f94f318b01a2d80dc570e9`)

| Timestamp | Screen Action | Voiceover Script |
| --- | --- | --- |
| **0:00 – 0:30** | **Tab 1 (Presentation Slide 01 & Slide 02):** Click through the 3 case documents (*The cheque*, *Bank return memo*, *Written demand*) and toggle *Business owner* / *Junior advocate*. | *"When a small business owner in India has a ₹2.4 lakh cheque dishonoured, the hardest part comes before court: knowing which dates trigger statutory deadlines under Section 138 of the Negotiable Instruments Act, what documents are missing, and what opposing counsel will argue. Generic chatbots guess dates and hallucinate citations. We built LegisiMate—an evidence-backed legal preparation workbench under the Accessibility and Social Good track."* |
| **0:30 – 1:05** | **Tab 2 (Workbench — Case Details view):** Click **Load sample case**, show the confirmed dates vs. blank service date, and highlight the **Calendar checks** panel on the right. | *"In the LegisiMate workbench, we enter anonymised case facts or load our sample MSME textile dispute. Notice that before any AI model is called, deterministic Python calendar rules compute the 30-day demand notice window under Section 138 Proviso (b), the 15-day payment period, and the one-calendar-month filing window under Section 142. Because the notice receipt date isn't confirmed by a postal acknowledgement yet, LegisiMate flags it as missing rather than guessing."* |
| **1:05 – 1:45** | **Tab 2 (Workbench — Readiness Brief & Research & Sources views):** Click the completed case in the sidebar (`A small textile supplier...`), show the **Readiness Brief**, then click **Research & sources** and open a cited Supreme Court / statutory record in the drawer. | *"Once the user grants explicit consent, our bounded Gemini research agent queries a local SQLite FTS5 corpus of 7,143 Indian statutory provisions and 10,139 Supreme Court and High Court judgment chunks. In the Research & Sources tab, every tool call is transparent. Crucially, the model cannot invent quotations—it must select a passage ID from retrieved sources, and the server verifies 27 out of 27 exact quote matches."* |
| **1:45 – 2:30** | **Tab 2 (Workbench — Argument Paths & Courtroom Rehearsal views):** Show the **Argument paths** tab comparing Path 1, Path 2, and Path 3, then switch to **Courtroom rehearsal** and click **Play**. | *"Instead of a scripted winner, LegisiMate plans three case-specific preparation paths—testing complainant documentary proof, the strongest adverse security-cheque defence, and evidence-gathering/settlement. Each path runs with fresh memory across Defence Counsel, Complainant Counsel, and a Neutral Magistrate. In the 2.5D Courtroom Rehearsal view, users can watch and read each exchange step by step, seeing exactly what to say, why it matters, and which statutory or Supreme Court passage backs it."* |
| **2:30 – 3:00** | **Tab 1 (Presentation Slide 08, Slide 09 & Slide 14):** Show the Architecture trace and the Global Jurisdiction Pack roadmap, then click **Export brief (.md)** in Tab 2. | *"Users leave with a downloadable Markdown Readiness Brief listing the exact documents to collect and questions for their advocate. Built with Google Gemini, Vertex AI, and Cloud Run with zero-cold-start embedded legal indexing, LegisiMate's engine is designed to scale globally through versioned, locally verified Jurisdiction Packs. Thank you!"* |
