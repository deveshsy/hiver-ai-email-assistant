# Hiver AI Email Suggested-Response & Evaluation System
**Candidate:** Devesh Singh Yadav  
**Challenge:** Hiver 100-Minute Open Challenge — Generative AI Email Assistant & Accuracy Engine  
**Repository:** [https://github.com/deveshsy/hiver-ai-email-assistant](https://github.com/deveshsy/hiver-ai-email-assistant)

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

### 2. Run Automated Unit Tests (0.1s)
```bash
python -m pytest tests/test_system.py -v
```

### 3. Run End-to-End Suggested-Response & Accuracy System
```bash
# Option A: Run rapid 2-email evaluation demo
python main.py --demo

# Option B: Run full evaluation across all 13 enterprise test scenarios
python main.py

# Option C: Run zero-dependency deterministic mock mode (no API key required)
python main.py --mock
```

Outputs are streamed in real time to the terminal and exported to `results/evaluation_report.json`.

---

## 🏗️ 1. Dataset Design & Provenance

### Why This Dataset is Representative
Hiver powers customer email collaboration inside Google Workspace and Gmail. Real customer email in this domain is **high-context, workflow-dependent, and commercially sensitive**. 

We built a dedicated dataset generator (`scripts/build_dataset.py`) reflecting realistic B2B SaaS support operations across 7 operational categories:
1. **Billing & Invoicing:** Duplicate credit card charges, tax-exempt 501(c)(3) adjustments, VAT receipts, accidental seat additions with 24-hour grace periods.
2. **Technical & Synchronization:** Gmail tab memory crashes on large attachments, Google Workspace OAuth token expirations, WebSocket collision detection bugs, tag indexing delays.
3. **Account & Access Control:** Offboarding employee seat revocation, Okta SAML 2.0 SSO configuration, Google Admin console API whitelisting.
4. **Churn & High-Urgency Crises:** Enterprise customers threatening cancellation due to missed $50k deals, contractual SLA penalty demands.
5. **Feature Guidance & Workflows:** Business-hours-only SLA rules, CSAT export procedures, internal notes confidentiality.
6. **Security & Compliance:** GDPR Article 17 ("Right to be Forgotten") data deletion demands.
7. **Adversarial & Safety:** Prompt injection attacks attempting system override to extract system prompts and API keys.

### Data Splits
* **`data/historical_support_emails.jsonl` (13 records):** Curated past email exchanges with verified human agent resolutions, official product paths, and key policy points. This serves as the ground-truth knowledge base for RAG retrieval.
* **`data/test_emails.jsonl` (13 records):** Fresh, unseen incoming customer emails containing varied emotional tones (angry, urgent, neutral), edge cases, and strict evaluation constraints (`must_contain` and `must_not_contain`).

---

## 🧠 2. Response Generator Architecture & Trade-Offs

The response generator (`src/generator.py`) processes incoming emails into complete, context-aware suggested replies using **Gemini 3.6 Flash** coupled with a **BM25 Retrieval-Augmented Generation (RAG)** pipeline.

```
Incoming Customer Email
         │
         ▼
[1. EmailRetriever (BM25)] ──► Fetches Top-2 Historical Support Resolutions
         │
         ▼
[2. Context Assembler] ──────► Injects Few-Shot Historical Resolutions + Persona Prompt
         │
         ▼
[3. LLM Generator] ──────────► Generates SuggestedReply (JSON Schema)
         │
         ├─► Intent Classification & Confidence Score
         ├─► Risk-Aware Triage (Auto-Handle vs. Escalate to Human with Reason)
         └─► Grounded, De-escalating Email Body
```

### Architectural Trade-Off Justification

| Approach | Pros | Cons | Why Chosen / Rejected |
| :--- | :--- | :--- | :--- |
| **Zero-Shot Prompting** | Fast, zero index overhead. | Severe hallucination; invents fake features/discounts; inconsistent tone. | **Rejected** as unsafe for enterprise support. |
| **Model Fine-Tuning** | Learns historical brand style directly. | High training cost; catastrophic forgetting; cannot update policies without retraining. | **Rejected** for 100m scope and policy rigidity. |
| **RAG (Few-Shot Retrieval)** | **Deterministic policy grounding; dynamic policy updates; zero retraining; verifiable citations.** | Minor latency for retrieval step (~2ms). | **CHOSEN:** Ensures replies mirror historical resolutions without hallucinating. |

### Risk-Aware Escalation Philosophy
Not all emails should be automated. The generator enforces strict escalation guardrails:
* **Auto-handled:** Routine questions, step-by-step navigation, standard feature explanations.
* **Human Escalation:** Triggered automatically for legal/GDPR requests, enterprise cancellations (e.g. lost revenue), SLA penalty claims, or duplicate billing disputes requiring finance ledger audits.

---

## 🎯 3. Accuracy & Evaluation System (The Core Engine)

### What Does "Accurate" Mean for a Support Reply?
In customer email, **exact string matching (BLEU/ROUGE) is deeply flawed**: two responses can share zero words while both being 100% correct, or share 80% words while getting a refund policy completely wrong.

We define accuracy through a **Multi-Dimensional Quality & Policy Index (0–100)**:

$$\text{Composite Score} = 0.35 \cdot \text{Intent} + 0.30 \cdot \text{Grounding} + 0.20 \cdot \text{Actionability} + 0.15 \cdot \text{Tone} - \text{Violations}$$

### The 4 Evaluation Dimensions:
1. **Intent Resolution (35%):** Did the reply identify the customer's root problem and solve the core query?
2. **Factual Grounding & Policy Safety (30%):** Does the reply adhere strictly to valid SaaS support procedures? Heavy deductions if the model hallucinates non-existent discounts or promises impossible SLAs.
3. **Actionability & Next Steps (20%):** Are clear, concrete steps provided? Does the customer know what happens next?
4. **Tone, Empathy & De-escalation (15%):** Is the tone calm, professional, and de-escalating? (Crucial for churn risks).
5. **Red-Line Negative Constraints:** Automated penalization (-15 points per violation) if the model outputs forbidden phrases (e.g. telling an angry cancelling enterprise customer to *"have a nice day"*).

### Pass/Fail Gate
A response receives a **`[PASS]`** if:
$$\text{Composite Score} \ge 75.0 \quad \text{AND} \quad \text{Intent} \ge 70.0 \quad \text{AND} \quad \text{Grounding} \ge 70.0 \quad \text{AND} \quad \text{Zero Red-Line Violations}$$
Otherwise, it receives a **`[FAIL]`**.

### What Is Misleading About Naive Headline Numbers?
* **Leniency & Politeness Bias:** LLM judges inherently over-score polite, verbose responses even when the underlying technical answer is useless. Our system counters this by decoupling Factual Grounding and Actionability from Tone, and applying hard negative-constraint penalties.
* **Aggregated Means Mask Critical Tail Risks:** A system can achieve an impressive 88/100 average while failing catastrophically on a GDPR deletion email. We explicitly report **Critical Risk Escalation Recall** alongside mean scores.

---

## 🛠️ 4. AI Tooling & Engineering Methodology Disclosure
In compliance with the challenge rules:
* **Code Assistant Usage:** Google Antigravity / Gemini was used for rapid scaffolding, test boilerplate generation, and schema ideation during the 100-minute sprint.
* **Architecture & Design Ownership:** The data taxonomy, multi-tier evaluation rubric, risk-aware escalation thresholds, and adversarial failure analysis were designed specifically for Hiver's shared inbox use cases.
* **Secrets & Security:** API keys are managed strictly via environment variables (`.env` is excluded in `.gitignore`; `.env.example` provided).
