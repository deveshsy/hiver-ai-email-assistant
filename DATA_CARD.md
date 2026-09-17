# Data Card: Hiver AI Email Assistant Grounding & Evaluation Corpora

## 1. Dataset Overview & Provenance

This repository utilizes two distinct corpora designed for retrieval-augmented generation (RAG) grounding and rigorous multi-dimensional evaluation:

| Corpus File | Records | Provenance (`source_type`) | Source Name | Primary Purpose |
| :--- | :---: | :--- | :--- | :--- |
| **`data/historical_support_emails.jsonl`** | 20 | `domain_synthetic` | `hiver_support_synthetic_v1` | Retrieval Knowledge Base: verified past resolutions, SaaS policies, workflows |
| **`data/test_emails.jsonl`** | 14 | `domain_synthetic` | `hiver_support_synthetic_v1` | Evaluation Benchmark: fresh customer queries with strict ground-truth constraints |

### Optional Real-World Public Corpus Support
* **Source:** CMU Enron Email Corpus (Public Domain / Historical Archive, collected by FERC and prepared by Carnegie Mellon University).
* **Ingestion Script:** `scripts/ingest_enron_corpus.py`
* **Honest Role & Contrast:** The Enron corpus provides authentic workplace email phrasing, conversational turns, and politeness conventions, but it is **not** customer support data and contains **no** Hiver product workflows or SaaS billing policies. The synthetic Hiver dataset provides domain-specific workflows (OAuth sync, shared drafts, GDPR Article 17, 501(c)(3) tax exemption) that do not exist in general workplace email datasets. Enron ingestion is optional and not required for the default demo.

---

## 2. Synthetic vs. Real Status

* **Status:** The primary benchmark (`historical_support_emails.jsonl` and `test_emails.jsonl`) is **domain-specific synthetic data**, author-curated to reflect real-world B2B SaaS shared-inbox workflows (Google Workspace / Gmail integration).
* **No Artificial Inflation:** All 20 historical cases and 14 test cases represent distinct, mutually exclusive support scenarios. Mechanically expanded superficial permutations (e.g. duplicating records with name swaps) are explicitly forbidden and excluded.

---

## 3. Data Splits & Leakage Prevention Policy

### Split Isolation Policy
* **Separation by Base Scenario & Thread:** Every record contains a `base_case_id` identifying the core customer situation.
* **Strict Disjoint Partitioning:**
  $$\text{base\_case\_ids}(\text{historical}) \cap \text{base\_case\_ids}(\text{test}) = \emptyset$$
  No base scenario or customer thread from the test evaluation split appears in the historical retrieval knowledge base.
* **Generalization Testing:** The test set evaluates whether the retrieval system can match general support policies (e.g. duplicate charge dispute procedure, Google Admin OAuth approval steps) and apply them correctly to a new customer's specific identifiers (e.g. invoice `INV-9940`, user `user_88192a`), rather than regurgitating memorized past answers.

---

## 4. Cleaning, Anonymization & PII Handling

For the synthetic domain datasets:
* All customer names, email domains (`fintechpulse.io`, `growthloop.com`), and invoice numbers (`INV-8821`, `INV-9940`) are fictional placeholders.
* No live customer PII or proprietary corporate data is contained in the repository.

For the optional Enron ingestion pipeline (`scripts/ingest_enron_corpus.py`):
* Forwarded text and quoted reply chains (`> ...`, `-----Original Message-----`) are stripped to prevent echo leakage.
* Email addresses and phone numbers are normalized and redacted using regex masking (`[EMAIL_REDACTED]`, `[PHONE_REDACTED]`).
* Messages are paired into single-turn query-reply pairs only where explicit `In-Reply-To` threading or normalized subject matching exists with high confidence.

---

## 5. Domain Categories Covered

The 20 historical and 14 test cases span 7 core operational domains:
1. **Billing & Invoicing:** Duplicate card charges, W-9/VAT receipts, 20% annual commitment discounts, 24-hour grace periods, 501(c)(3) tax-exemption verification.
2. **Technical & Synchronization:** OAuth token expiration backfill, WebSocket collision detection VPN throttles, macOS Chrome extension disappearing, >15MB PDF draft memory crashes, tag indexing delays.
3. **Account & Access Control:** Employee offboarding ticket reassignment, Okta SAML 2.0 SSO configuration, Google Admin console API client ID whitelisting.
4. **Churn & High-Urgency Crises:** Enterprise outage churn threats ($50k deal impact), contractual SLA breach penalty claims under Master Services Agreements.
5. **Feature Guidance:** Round-robin auto-assignment, CSAT raw CSV export, internal notes confidentiality guarantees.
6. **Integrations:** Private Slack channel bot invites (`/invite @Hiver`), webhook payload metadata specifications.
7. **Security & Adversarial:** GDPR Article 17 Right to Erasure handling (30-day DPO SLA), prompt injection defense (refusing system override and credential extraction).
8. **Out-of-Domain / Abstention:** Unsupported custom mainframe integrations (testing safe refusal and human escalation).

---

## 6. Known Limitations

1. **Synthetic Bias:** While scenarios were authored to mirror enterprise support tickets, synthetic data inherently lacks the grammatical noise, typos, and ambiguity of real end-user incoming tickets.
2. **Single-Turn Scope:** Current benchmark pairs represent single incoming emails and suggested responses; multi-turn conversational threads with ongoing negotiations are outside the immediate scope.
3. **Sample Size:** 14 test cases serve as a deterministic regression suite and sanity benchmark, not a statistically comprehensive representation of high-volume production operations.
