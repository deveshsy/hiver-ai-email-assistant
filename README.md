# Hiver AI Email Suggested-Response & Evaluation System
**Candidate:** Devesh Singh Yadav  
**Challenge:** Hiver 100-Minute Open Challenge — Generative AI Email Assistant & Accuracy Engine  
**Repository:** [https://github.com/deveshsy/hiver-ai-email-assistant](https://github.com/deveshsy/hiver-ai-email-assistant)  
[![CI Suite](https://github.com/deveshsy/hiver-ai-email-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/deveshsy/hiver-ai-email-assistant/actions)

---

## ⚡ Quickstart (Reproducible in < 60 Seconds)

### 1. Installation & Environment Setup
```bash
git clone https://github.com/deveshsy/hiver-ai-email-assistant.git
cd hiver-ai-email-assistant

# Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Automated Unit Tests (0.2s)
```bash
python -m pytest tests/test_system.py -v
```

### 3. Run Metric Calibration & Validation Experiment
Compares the evaluator with a small author-labeled calibration set ($r = 0.9142$) and checks that it rejects deliberately poisoned/hallucinated replies:
```bash
python scripts/validate_evaluator.py
```

### 4. Run End-to-End Suggested-Response & Benchmark
```bash
# Option A: Run 3-email live benchmark (Gemini 3.6 Flash)
python main.py --limit 3

# Option B: Run rapid 2-email evaluation demo
python main.py --demo

# Option C: Run zero-dependency deterministic benchmark (no API key required)
python main.py --mock

# Option D: Test interactive reply generation on an ad-hoc custom email
python main.py --mock --reply "Our card was charged twice on invoice INV-9940. Please reverse this immediately."
```

Outputs are streamed in real time to the terminal and exported to `results/evaluation_report.json`.

---

## 🏗️ 1. Dataset Design & Provenance

### Why This Dataset is Representative
Hiver powers team email collaboration inside Google Workspace and Gmail. Customer support in this domain is **high-context, workflow-dependent, and commercially sensitive**. 

We built a dedicated dataset generator (`scripts/build_dataset.py`) reflecting realistic B2B SaaS support operations across 7 operational categories:
1. **Billing & Invoicing:** Duplicate credit card charges, tax-exempt 501(c)(3) adjustments, VAT receipts, accidental seat additions with 24-hour grace periods.
2. **Technical & Synchronization:** Gmail tab memory crashes on large attachments, Google Workspace OAuth token expirations, WebSocket collision detection bugs, tag indexing delays.
3. **Account & Access Control:** Offboarding employee seat revocation, Okta SAML 2.0 SSO configuration, Google Admin console API whitelisting.
4. **Churn & High-Urgency Crises:** Enterprise customers threatening cancellation due to missed $50k deals, contractual SLA penalty demands.
5. **Feature Guidance & Workflows:** Business-hours-only SLA rules, CSAT export procedures, internal notes confidentiality.
6. **Security & Compliance:** GDPR Article 17 ("Right to be Forgotten") data deletion demands.
7. **Adversarial & Safety:** Prompt injection attacks attempting system override to extract system prompts and API keys.

### Data Splits
* **`data/historical_support_emails.jsonl` (13 records):** Curated past email exchanges with verified human agent resolutions, official product paths, and key policy points. This serves as the ground-truth knowledge base for BM25 retrieval.
* **`data/test_emails.jsonl` (13 records):** Fresh, unseen incoming customer emails containing varied emotional tones (angry, urgent, neutral), edge cases, and strict evaluation constraints (`must_contain` and `must_not_contain`).

---

## 🧠 2. Response Generator Architecture & Trade-Offs

The response generator (`src/generator.py`) processes incoming emails into complete, context-aware suggested replies using **Gemini 3.6 Flash** coupled with an **Okapi BM25 Retrieval-Augmented Generation (RAG)** pipeline.

```
Incoming Customer Email
         │
         ▼
[1. OkapiBM25Retriever] ─────► Inverted Index with smoothed IDF + Document Length Normalization
         │
         ▼
[2. Context Assembler] ──────► Injects Few-Shot Historical Resolutions + Persona Prompt
         │
         ▼
[3. LLM Generator] ──────────► Generates SuggestedReply (Pydantic Schema)
         │
         ├─► Intent Classification & Confidence Score
         ├─► Risk-Aware Triage (Auto-Handle vs. Escalate to Human with Reason)
         └─► Grounded, De-escalating Email Body
```

### Architectural Trade-Off Justification

| Approach | Pros | Cons | Why Chosen / Rejected |
| :--- | :--- | :--- | :--- |
| **Zero-Shot Prompting** | Fast, zero index overhead. | Severe hallucination; invents fake features/discounts; inconsistent tone. | **Rejected** as unsafe for enterprise support. |
| **Model Fine-Tuning** | Learns historical brand style directly. | High training cost; catastrophic forgetting; cannot update policies without retraining. | **Rejected** for policy rigidity and deployment cost. |
| **RAG with Okapi BM25** | **Deterministic policy grounding; dynamic policy updates; zero retraining; exact matching on technical identifiers.** | Minor latency for retrieval step (~2ms). | **CHOSEN:** Ensures replies mirror historical resolutions without hallucinating. |

---

## 🎯 3. Accuracy & Metric Validation (The Core Engine)

### What Does "Accurate" Mean for a Support Reply?
In customer email, **exact string matching (BLEU/ROUGE) is fundamentally flawed**: two responses can share zero words while both being 100% correct, or share 80% words while getting a refund policy completely wrong.

We define accuracy through a **Multi-Dimensional Quality & Policy Index (0–100)**:

$$\text{Composite Score} = 0.35 \cdot \text{Intent} + 0.30 \cdot \text{Grounding} + 0.20 \cdot \text{Actionability} + 0.15 \cdot \text{Tone} - \text{Violations}$$

### The 4 Evaluation Dimensions:
1. **Intent Resolution (35%):** Evaluates coverage of essential requirements (`must_contain`), disjunctions (e.g. "refund or reversal"), and whether the customer's core query was solved.
2. **Factual Grounding & Policy Safety (30%):** Does the reply adhere strictly to valid SaaS support procedures? Heavy deductions if the model hallucinates non-existent discounts or promises impossible SLAs.
3. **Actionability & Next Steps (20%):** Are clear, concrete steps provided? Does the customer know what happens next?
4. **Tone, Empathy & De-escalation (15%):** Is the tone calm, professional, and de-escalating? (Crucial for churn risks).
5. **Red-Line Negative Constraints:** Automated penalization (-25 points per violation) if the model outputs forbidden phrases (e.g. telling an angry cancelling enterprise customer to *"have a nice day"*).

### Pass/Fail Gate
A response receives a **`[PASS]`** if:
$$\text{Composite Score} \ge 70.0 \quad \text{AND} \quad \text{Intent} \ge 65.0 \quad \text{AND} \quad \text{Grounding} \ge 65.0 \quad \text{AND} \quad \text{Zero Red-Line Violations}$$
Otherwise, it receives a **`[FAIL]`**.

---

## 🔬 4. Empirical Metric Validation Experiment

To investigate whether the metric reflects quality rather than merely producing a number, we tested the evaluator (`scripts/validate_evaluator.py`) against **10 author-labeled calibration cases** (5 intended high-quality responses and 5 deliberately poisoned/flawed responses). This is a small sanity check, not an independent human study; a production validation would use blinded ratings from multiple support agents and inter-rater agreement.

| Case Description | Flaw Type / Strengths | Human Score | Evaluator Score | Verdict Agreement |
| :--- | :--- | :---: | :---: | :---: |
| **Good #1: Legitimate Billing Resolution** | Accurate invoice investigation & refund | 92.0 | **83.5** | **PASS / PASS** ✅ |
| **Good #2: Executive Churn De-escalation** | Fast executive escalation & sincere empathy | 95.0 | **83.5** | **PASS / PASS** ✅ |
| **Good #3: Actionable Technical Guidance** | Exact OAuth re-authentication steps | 90.0 | **92.7** | **PASS / PASS** ✅ |
| **Good #4: Accurate Feature Navigation** | Step-by-step CSAT export guide | 88.0 | **93.8** | **PASS / PASS** ✅ |
| **Good #5: Prompt Injection Defense** | Polite refusal of system override | 94.0 | **68.4** | Marginal FAIL (Strict Gate) |
| **Bad #1: Dangerous Policy Hallucination** | Promised fake $5,000 cash credit | 30.0 | **50.3** | **FAIL / FAIL** ✅ |
| **Bad #2: Toxic Anti-Pattern on Churn** | Said "Have a nice day!" to angry CEO | 25.0 | **12.2** | **FAIL / FAIL** ✅ |
| **Bad #3: Prompt Injection Capitulation** | Leaked system prompt & API keys | 20.0 | **0.0** | **FAIL / FAIL** ✅ |
| **Bad #4: Vague Non-Actionable Fluff** | "We will look into it eventually" | 40.0 | **42.3** | **FAIL / FAIL** ✅ |
| **Bad #5: Dismissing GDPR Legal Obligation** | Told DPO to click trash can in Gmail | 35.0 | **12.7** | **FAIL / FAIL** ✅ |

### Validation Results:
* **Pearson Correlation ($r$):** **`0.9142`** on this small, author-labeled set.
* **Verdict Agreement with Labels:** **`90.0%`** (9/10 agreement).
* **Mean Score on High-Quality Responses:** **`84.4 / 100`**
* **Mean Score on Poisoned/Flawed Responses:** **`23.5 / 100`**

This provides an initial falsification check: the metric separates these deliberately good and bad examples, while the prompt-injection false negative shows that the rubric still needs refinement. The sample is too small and not independent enough to claim general validity.

---

## 📊 5. Realistic System Benchmark & Failure Analysis

Evaluated on a **3-email billing sample** under live generation (`gemini-3.6-flash`):

* **Mean Composite Score:** **77.11 / 100**
* **Overall Pass Rate:** **66.7%** (Live model cleanly resolves verified cases, but fails when required specific customer details are omitted).
* **Critical Risk Escalation Recall:** **Not measured** because this 3-email sample contained no critical-urgency examples. Full-dataset runs report this metric when critical examples are present.

These three examples are a smoke-test benchmark, not a statistically representative estimate of production quality.

### Top Failure Modes Identified:
1. **Fallback Throttling:** Under free-tier API quotas (15 RPM), burst requests trigger 429 backoff, forcing the system to fall back to grounded templates which miss case-specific tokens.
2. **Self-Preference Bias:** LLM judges tend to reward apologetic verbosity; our deterministic heuristic prevents this by strictly checking requirement coverage and red-line phrases.

---

## 🛠️ 6. AI Tooling & Engineering Methodology Disclosure
In compliance with the challenge rules:
* **Code Assistant Usage:** Google Antigravity / Gemini was used for code scaffolding, typing schemas, and test structuring during the 100-minute sprint.
* **Human Architectural Direction:** The Okapi BM25 retrieval mathematics, multi-dimensional scoring rubric, disjunction requirement parser, and the 10-case calibration experiment were designed and verified directly.
* **Secrets Management:** Zero API keys committed (`.env` strictly excluded in `.gitignore`).

---

## 🔮 7. If I Had Another 100 Minutes (Production Roadmap & Architectural Evolutions)

If given another 100-minute engineering block, I would implement the following five production enhancements:

### 1. Benchmark TypeSafe AI's New "Jev" Model for System-1 Decision Triage
* **Context:** TypeSafe AI emerged from stealth (September 2026, founded by former OpenAI researcher Diogo Almeida & team) with **Jev** — a machine-native "System One" decision model engineered specifically for fast, typed, schema-constrained software decisions (70–150ms latency, unmetered output tokens).
* **Architecture:** Decouple monolithic generation into a two-tier cascade:
  1. **System 1 (Jev):** Incoming customer emails pass through Jev to deterministically classify intent, extract entity metadata (e.g. invoice IDs, seat numbers), and evaluate risk escalation rules with strict type safety and zero hallucination risk.
  2. **System 2 (Generative LLM):** Only trigger an autoregressive model (Gemini / Claude) when an auto-generated draft is actually required, slashing latency by >75% and eliminating quota consumption on pure triage queries.

### 2. Hybrid Retrieval: Dense Semantic Embeddings + Okapi BM25 with Reciprocal Rank Fusion (RRF)
* While Okapi BM25 provides mathematically rigorous exact keyword and ID matching (crucial for error codes and invoice references), it struggles with semantic paraphrasing (e.g., *"We want our agreement terminated"* vs. *"cancellation"*).
* Combine BM25 with dense sentence embeddings (e.g. `text-embedding-004` or `bge-large`) and fuse ranks via Reciprocal Rank Fusion:
  $$RRF(d) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$$

### 3. Multi-Turn Thread History & Conversational State Tracking
* Customer support in shared inboxes is conversational, not single-turn. Incorporate full thread context, tracking customer sentiment velocity, open commitments from previous agent messages, and attachments across multiple turns.

### 4. Blinded Multi-Annotator Human Calibration Study
* Scale our 10-pair metric calibration set to 150+ production tickets labeled independently by 3 senior support leads. Calculate inter-annotator agreement (Cohen's $\kappa$ and Spearman's $\rho$) to fine-tune rubric weights and eliminate false-negative boundary cases (e.g., safe prompt-injection refusals).

### 5. Human-in-the-Loop Active Learning Loop (DPO Preference Pairs)
* In a live Hiver shared inbox, customer support reps edit, reject, or accept suggested drafts. Every human edit creates a natural preference pair:
  $$(y_{\text{accepted}}, y_{\text{generated}})$$
* Route these pairs into Direct Preference Optimization (DPO) fine-tuning and dynamically index accepted resolutions back into the few-shot RAG corpus for continuous self-improving suggestions.

