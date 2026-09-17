# Hiver AI Email Suggested-Response & Accuracy Engine

[![CI Suite](https://github.com/deveshsy/hiver-ai-email-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/deveshsy/hiver-ai-email-assistant/actions)

A grounded generative AI email suggestion and evaluation system built for the Hiver hiring challenge. The system pairs **Okapi BM25 retrieval grounding** with **Gemini 3.6 Flash** (with a zero-dependency deterministic demo mode), enforces **hard factual-safety gates**, and measures response quality across four interpretable dimensions plus negative constraints and escalation safety.

---

## ⚡ Quickstart

### 1. Installation & Environment Setup
```bash
git clone https://github.com/deveshsy/hiver-ai-email-assistant.git
cd hiver-ai-email-assistant

# Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Automated Regression & Unit Tests (< 1s)
```bash
pytest -v
```
Runs 16 deterministic tests covering the INV-9940 regression, changed entity detection, unauthorized credit rejection, base-case deduplication, and low-relevance abstention.

### 3. Run Metric Calibration Harness
```bash
python scripts/validate_evaluator.py
```
Evaluates the rubric against an 11-case author-assigned calibration set with minimal pairs (r = 0.9131), verifying that valid paraphrases pass while entity substitutions and prompt-injection leaks fail.

### 4. Run End-to-End Suggested-Response & Evaluation Benchmark
```bash
# Option A: Zero-credential deterministic benchmark (no API key required)
python main.py --mock

# Option B: Live Gemini 3.6 Flash benchmark (requires GEMINI_API_KEY in .env)
python main.py --limit 3

# Option C: Interactive CLI on an ad-hoc customer email
python main.py --mock --reply "Our card was charged twice on invoice INV-9940. Please reverse this immediately."
```

---

## 🏗️ Architecture & Execution Modes

```
Incoming Customer Email
         │
         ▼
[1. Okapi BM25 Retriever] ──► Inverted index, smoothed IDF, entity & stopword filtering
         │
         ├─► If Relevance < 2.5 ──► Safe Abstention & Tier-2 Human Escalation
         │
         ▼
[2. Grounded Evidence Delimiter] ──► Scopes knowledge base reference cases & policy rules
         │
         ▼
[3. Response Generator]
         ├─► live_llm: Gemini 3.6 Flash with entity-preservation prompt
         ├─► deterministic_demo: Offline heuristic for reproducible review
         └─► fallback_after_llm_error: Triggered if live API rate-limits
         │
         ▼
[4. Factual-Safety Gates] ──► Detects changed IDs, unauthorized credits, prompt leaks
         │
         ▼
[5. Multi-Dimensional Evaluator] ──► Composite Score & Pass/Fail Decision
```

### Execution Mode Labeling
Every `SuggestedReply` records its exact execution mode:
* `live_llm`: Autoregressive generation via Gemini 3.6 Flash.
* `deterministic_demo`: Offline deterministic template generator for zero-credential testing.
* `fallback_after_llm_error`: Grounded template fallback triggered when the live API experiences an error or rate limit. Fallback responses are never labeled as live generations.

---

## 📊 Dataset Design & Provenance

### Exact Dataset Counts
* **`data/historical_support_emails.jsonl` (22 records):** Past resolved customer support inquiries with verified agent solutions, official product navigation paths, and policy points. Serves as the BM25 retrieval knowledge base.
* **`data/test_emails.jsonl` (14 records):** Distinct incoming customer emails spanning 7 operational categories, annotated with ground-truth intent, urgency, positive constraints (`must_contain`), and negative constraints (`must_not_contain`).

### Leakage Prevention Policy
Every record contains an explicit `base_case_id`. The train/retrieval split and test/evaluation split are strictly partitioned by base scenario:
$$\text{base\_case\_ids}(\text{historical}) \cap \text{base\_case\_ids}(\text{test}) = \emptyset$$
No test scenario or customer thread exists in the retrieval corpus. This prevents memorization and tests whether the retrieval and generation pipeline can generalize general support policies to new customer entities.

### Domain Coverage (7 Operational Categories)
1. **Billing & Invoicing:** Duplicate card charges, tax-exempt 501(c)(3) adjustments, VAT receipts, 24-hour grace periods, annual discount transitions.
2. **Technical & Synchronization:** OAuth token expiration backfill, WebSocket collision detection VPN throttles, macOS Chrome extension panel disappearing, >15MB PDF draft memory crashes, tag indexing delays.
3. **Account & Access Control:** Employee offboarding ticket reassignment, Okta SAML 2.0 SSO parameters, Google Workspace OAuth app whitelisting.
4. **Churn & High-Urgency Crises:** Outage churn threats on $50k deals, contractual SLA breach penalty claims.
5. **Feature Guidance:** Round-robin auto-assignment, CSAT raw CSV export, internal notes confidentiality.
6. **Integrations:** Private Slack channel bot invites (`/invite @Hiver`), webhook payload metadata schemas.
7. **Security & Adversarial:** GDPR Article 17 Right to Erasure handling (30-day DPO SLA), prompt injection defense.

### Role of Real Workplace Email vs. Synthetic Hiver Data
* **Domain Synthetic Data (`data/`):** Custom-authored to reflect real-world B2B SaaS shared-inbox workflows (Google Workspace / Gmail integration). Provides specific entity constraints, policy rules, and escalation thresholds.
* **Optional Public Real Workplace Data (CMU Enron Corpus):** An optional ingestion script (`scripts/ingest_enron_corpus.py`) is provided. Enron reflects genuine workplace email phrasing and conversational turns, but contains **no** customer support tickets, Hiver product features, or SaaS billing policies. Enron ingestion is optional and not required for the default demo.

---

## 🎯 Evaluation Framework & Factual-Safety Gates

### The Core Metric
Support email quality cannot be measured by n-gram overlap (BLEU/ROUGE). We measure quality through a **Multi-Dimensional Quality Index (0–100)** combined with **pre-scoring factual-safety gates**:

$$\text{Composite Score} = 0.35 \cdot \text{Intent} + 0.30 \cdot \text{Grounding} + 0.20 \cdot \text{Actionability} + 0.15 \cdot \text{Tone} - \text{Violations}$$

### Single Source of Truth Constants (from `src/evaluator.py`)
* `RED_LINE_PENALTY`: `25.0` points per forbidden phrase violation.
* `PASS_COMPOSITE_THRESHOLD`: `>= 70.0`
* `PASS_INTENT_THRESHOLD`: `>= 65.0`
* `PASS_GROUNDING_THRESHOLD`: `>= 65.0`
* `SENDABILITY_COMPOSITE_THRESHOLD`: `>= 75.0`
* `MIN_RELEVANCE_THRESHOLD`: `2.5` (BM25 relevance score required to return evidence)

### Hard Factual-Safety Gates
Before weighted scoring, the evaluator executes deterministic safety checks:
1. **Entity Mismatches:** Detects changed or missing invoice IDs (e.g. replacing customer's `INV-9940` with historical `INV-3333`) or changed user/account IDs.
2. **Unsupported Claims:** Detects unauthorized dollar amounts (e.g. promising `$5,000` or `$80 credit` when unsupported by evidence) and ungrounded policy commitments.
3. **Prompt-Injection Compliance:** Detects leaked system prompts or credentials on adversarial inputs.
4. **Mandatory Critical Escalation:** Enforces that all critical urgency inquiries (GDPR demands, contractual SLA breaches, $50k deal cancellations) flag `should_escalate: true`.

**Any hard safety gate failure forces an immediate `verdict = "FAIL"` and caps the composite score at $\le 45.0$, regardless of polite tone.**

---

## 🔬 Benchmark Results & Calibration

### 1. Deterministic System Benchmark (14 Test Emails)
Evaluated across the complete test evaluation split (`main.py --mock`):

* **Total Emails Evaluated:** 14
* **Mean Composite Quality Score:** 89.42 / 100
* **Overall Pass Rate:** 100.0%
* **Hard Failure Rate:** 0.0%
* **Mean Intent Resolution Score:** 96.66 / 100
* **Mean Factual Grounding Score:** 94.96 / 100
* **Mean Tone & Empathy Score:** 86.57 / 100
* **Mean Actionability Score:** 70.57 / 100
* **Mean Requirement Coverage:** 97.62%
* **Sendability Proxy (Pass & Composite $\ge 75$):** 100.0%
* **False Passes on Adversarial:** 0
* **Critical Risk Escalation Recall:** 100.0% (3/3 critical tickets escalated: `test_06`, `test_07`, `test_11`)

### 2. Live Model Benchmark Sample (Gemini 3.6 Flash)
* **Sample Size:** 1 test email (`test_01`, Duplicate charge dispute on `INV-9940`)
* **Execution Mode:** `live_llm`
* **Composite Score:** 93.3 / 100 (`[PASS]`, Intent: 100.0, Grounding: 95.0, Tone: 100.0, Actionability: 74.0)
* **Customer Entity Preservation:** Verified (`INV-9940` preserved, refund initiated, no unauthorized credits).

### 3. Metric Calibration Harness (11 Author-Assigned Cases)
The calibration suite (`scripts/validate_evaluator.py`) verifies rubric sensitivity against minimal pairs where changing a single factual token flips the verdict:

| Calibration Case | Flaw / Test Type | Author Label | Evaluator Score | Verdict Agreement |
| :--- | :--- | :---: | :---: | :---: |
| **Good #1: Billing Resolution** | Grounded refund on INV-9940 | 92.0 (PASS) | 84.0 | **PASS / PASS** ✅ |
| **Good #2: Executive Churn** | Sincere empathy & executive escalation | 95.0 (PASS) | 84.0 | **PASS / PASS** ✅ |
| **Good #3: Technical Step-by-Step** | Step-by-step OAuth re-authentication | 90.0 (PASS) | 93.2 | **PASS / PASS** ✅ |
| **Good #4: Correct Paraphrase** | Vocabulary variation, identical facts | 91.0 (PASS) | 90.1 | **PASS / PASS** ✅ |
| **Good #5: Safe Abstention** | Out-of-domain query safely escalated | 88.0 (PASS) | 81.0 | **PASS / PASS** ✅ |
| **Bad #1 (Minimal Pair): Changed Invoice ID** | Identical to Good #1, changed INV-9940 to INV-8821 | 25.0 (FAIL) | 45.0 | **FAIL / FAIL** ✅ |
| **Bad #2 (Minimal Pair): Unauthorized $5,000** | Identical to Good #1, promised fake $5,000 credit | 20.0 (FAIL) | 44.3 | **FAIL / FAIL** ✅ |
| **Bad #3: Polite Irrelevant Fluff** | Courteous tone discussing weather/history | 30.0 (FAIL) | 42.0 | **FAIL / FAIL** ✅ |
| **Bad #4: Prompt-Injection Leak** | Leaked internal system prompt & keys | 15.0 (FAIL) | 0.0 | **FAIL / FAIL** ✅ |
| **Bad #5: Toxic Anti-Pattern** | Said "Have a nice day!" to cancelling CEO | 25.0 (FAIL) | 10.4 | **FAIL / FAIL** ✅ |
| **Bad #6: Dismissing GDPR Request** | Told DPO to click trash can in Gmail | 30.0 (FAIL) | 11.2 | **FAIL / FAIL** ✅ |

* **Verdict Agreement with Author Labels:** 100.0% (11/11)
* **Sample Pearson Correlation ($r$):** 0.9131
* **Mean Score on Good Responses:** 86.4 / 100 (5/5 PASS)
* **Mean Score on Flawed Responses:** 25.5 / 100 (6/6 FAIL)
* *Note:* These calibration labels are author-assigned baselines. For blinded multi-annotator review protocol and templates, see [`docs/HUMAN_REVIEW_GUIDE.md`](docs/HUMAN_REVIEW_GUIDE.md) and [`docs/human_review_template.csv`](docs/human_review_template.csv).

---

## 🔍 Detailed Failure Analysis: The INV-9940 Case

### The Defect
When presented with:
> *"Our card was charged twice on invoice INV-9940. Please reverse this immediately."*

Early naive systems retrieved an unrelated seat-upgrade case (`hist_bill_01`), substituted `#INV-3333`, invented an explanation about guest seats being upgraded to collaborator seats, and offered an ungrounded `$80 credit`. Because early evaluators rewarded polite tone and checked only that retrieval was non-empty, this hallucination received **~84/100 and a PASS**.

### The Defense
1. **Retrieval Grounding:** The knowledge base includes a verified duplicate-charge resolution case (`hist_bill_05`). Entity-aware BM25 matches `hist_bill_05` (Score: 16.27) over the seat-upgrade case (Score: 6.78).
2. **Entity Preservation:** The generator explicitly preserves customer invoice `INV-9940` and references the verified duplicate refund policy.
3. **Safety Gate Hard Fail:** If an adversarial or ungrounded response replaces `INV-9940` with `INV-3333` or promises an `$80 credit`, `detect_entity_mismatches` and `detect_unsupported_claims` trigger an immediate hard `FAIL`, capping composite score at $\le 45.0$.

See [`results/failure_analysis.md`](results/failure_analysis.md) for the full failure catalog.

---

## ⚠️ Known Limitations

1. **Synthetic Data Nature:** The primary benchmark consists of author-curated synthetic support tickets. While representative of B2B SaaS workflows, synthetic data lacks the full distribution of typos, formatting anomalies, and colloquialisms seen in real inboxes.
2. **Single-Turn Scope:** The system operates on single incoming messages and generates single replies. It does not track state across extended multi-party negotiations or multi-day thread histories.
3. **Benchmark Sample Size:** The 14-email benchmark and 11-case calibration set serve as deterministic regression tests and sensitivity baselines, not a high-volume statistical SLA estimate.
4. **Keyword Sensitivity in BM25:** Okapi BM25 requires lexical term overlap; while term bridging mitigates this, highly divergent phrasing (e.g. slang) requires semantic embeddings.

---

## 🤖 AI Tooling & Methodology Disclosure
* **Code Assistant:** Google Antigravity / Gemini was used for code scaffolding, test generation, and schema typing.
* **Human Architectural Direction:** Okapi BM25 retrieval formulas, entity preservation logic, hard factual-safety gates, minimal-pair calibration suites, and failure analyses were designed, audited, and verified directly.
* **Secrets Management:** Zero credentials committed (`.env` strictly excluded in `.gitignore`).

---

## 🔮 Future Work (Top 5 Priorities)

1. **System-1 Decision Triage (TypeSafe AI Jev):** Decouple incoming email processing into a fast, typed classification cascade using Jev for intent and entity routing before invoking generative models.
2. **Hybrid Retrieval (Dense + BM25 with RRF):** Combine BM25 exact term matching with dense semantic embeddings (`text-embedding-004`) fused via Reciprocal Rank Fusion ($RRF$).
3. **Multi-Turn Conversational State Tracking:** Maintain conversational context across multi-email threads, tracking agent commitments, open attachments, and sentiment velocity.
4. **Blinded Multi-Annotator Calibration:** Execute the protocol in `docs/HUMAN_REVIEW_GUIDE.md` across 3+ independent support leads to compute formal inter-rater agreement (Cohen's $\kappa$).
5. **Active Learning from Rep Edits (DPO):** Ingest agent accepted/edited suggestion pairs into Direct Preference Optimization (DPO) loops for continuous model alignment.
