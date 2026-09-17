import json
import os
import re
import time
from typing import List, Dict, Tuple, Optional
from src.schemas import IncomingEmail, SuggestedReply, ResponseEvaluation, SystemEvaluationReport

class ReplyEvaluator:
    """Multi-dimensional Accuracy and Quality Evaluation System for AI-generated support emails."""

    EVAL_PROMPT = """You are a Principal QA Auditor evaluating AI-suggested customer support email replies for Hiver.
Evaluate the AI's generated reply against the incoming customer email and ground truth requirements.

Scoring Criteria (0-100 points each):

1. INTENT RESOLUTION (0-100):
   - Does the reply address the customer's actual problem and all core questions?
   - 0-40: Misunderstands problem, answers wrong topic.
   - 41-70: Partially addresses but misses key aspect.
   - 71-100: Fully resolves the customer's query with correct context.

2. FACTUAL GROUNDING & POLICY SAFETY (0-100):
   - Does the reply adhere to realistic SaaS support policy?
   - Deduct heavily if the model hallucinates non-existent features, promises impossible refunds, or exposes security risks.
   - 0-50: Hallucinates fake capabilities or dangerous commitments.
   - 51-80: Standard plausible advice with minor speculation.
   - 81-100: Accurately grounded in support workflows and standard policies.

3. TONE, EMPATHY & DE-ESCALATION (0-100):
   - Is the tone professional, polite, and empathetic?
   - For high-urgency or angry customers, does it appropriately apologize and de-escalate without robotic boilerplate?
   - 0-50: Cold, dismissive, or inappropriate.
   - 51-80: Generic polite boilerplate.
   - 81-100: Exceptional, human-like empathy and professional warmth.

4. ACTIONABILITY & CLEAR NEXT STEPS (0-100):
   - Are clear next steps provided? Does the customer know exactly what happens next or what to do?
   - 0-50: Vague fluff ('we will look into it').
   - 51-80: Basic instruction.
   - 81-100: Crystal clear step-by-step guidance or explicit escalation timeline.

Incoming Customer Email:
From: {sender}
Subject: {subject}
Body: {body}
Urgency Level: {urgency}
Expected Intent: {expected_intent}

AI Suggested Reply:
Subject: {suggested_subject}
Body: {suggested_body}
Detected Intent: {detected_intent}
Escalate to Human: {should_escalate} (Reason: {escalation_reason})

Output strictly valid JSON with these fields:
{{
  "intent_resolution_score": <float 0-100>,
  "factual_grounding_score": <float 0-100>,
  "tone_empathy_score": <float 0-100>,
  "actionability_score": <float 0-100>,
  "feedback": "<2 sentences explaining the grade and any detected flaws>"
}}
"""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.6-flash", mock_mode: bool = False):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("GEMINI_API_KEY="):
                            self.api_key = line.strip().split("=", 1)[1].strip()

        self.model_name = model_name
        self.mock_mode = mock_mode or (not self.api_key)
        self.client = None

        if not self.mock_mode:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[!] Warning: Could not initialize Gemini evaluator ({e}). Using heuristic evaluator.")
                self.mock_mode = True

    def _extract_clean_json(self, raw_text: str) -> dict:
        text = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.MULTILINE)
        text = re.sub(r"```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"Could not parse JSON: {raw_text[:150]}")

    def evaluate_single_response(self, email: IncomingEmail, reply: SuggestedReply) -> ResponseEvaluation:
        """Evaluates a single generated email reply across multi-dimensional criteria."""
        # 1. Negative & Positive Constraint Verification (Heuristic Sanity Check)
        lower_body = reply.suggested_body.lower()
        must_contain_hits = []
        for phrase in email.must_contain:
            words = [w.lower() for w in phrase.split()]
            if any(w in lower_body for w in words):
                must_contain_hits.append(phrase)

        violations = []
        for phrase in email.must_not_contain:
            if phrase.lower() in lower_body:
                violations.append(phrase)

        # 2. Score with LLM or deterministic heuristic
        if self.mock_mode or not self.client:
            scores = self._heuristic_evaluate(email, reply, len(must_contain_hits), len(violations))
        else:
            prompt = self.EVAL_PROMPT.format(
                sender=email.sender,
                subject=email.subject,
                body=email.body,
                urgency=email.urgency,
                expected_intent=email.expected_intent or email.category,
                suggested_subject=reply.suggested_subject,
                suggested_body=reply.suggested_body,
                detected_intent=reply.detected_intent,
                should_escalate=reply.should_escalate,
                escalation_reason=reply.escalation_reason or "None"
            )
            scores = None
            for attempt in range(3):
                try:
                    res = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt
                    )
                    scores = self._extract_clean_json(res.text)
                    break
                except Exception:
                    time.sleep(1.0 * (attempt + 1))

            if not scores:
                scores = self._heuristic_evaluate(email, reply, len(must_contain_hits), len(violations))

        i_score = float(scores.get("intent_resolution_score", 80.0))
        g_score = float(scores.get("factual_grounding_score", 85.0))
        t_score = float(scores.get("tone_empathy_score", 85.0))
        a_score = float(scores.get("actionability_score", 80.0))

        # Apply constraint penalty: -15 points per red-line violation
        penalty = len(violations) * 15.0
        composite = max(0.0, (0.35 * i_score + 0.30 * g_score + 0.20 * a_score + 0.15 * t_score) - penalty)
        composite = round(composite, 2)

        # Pass condition: Composite >= 75 AND Intent >= 70 AND Grounding >= 70 AND zero severe violations
        is_pass = (composite >= 75.0 and i_score >= 70.0 and g_score >= 70.0 and len(violations) == 0)
        verdict = "PASS" if is_pass else "FAIL"

        return ResponseEvaluation(
            email_id=email.id,
            intent_resolution_score=round(i_score, 1),
            factual_grounding_score=round(g_score, 1),
            tone_empathy_score=round(t_score, 1),
            actionability_score=round(a_score, 1),
            composite_score=composite,
            verdict=verdict,
            must_contain_hits=must_contain_hits,
            must_not_contain_violations=violations,
            feedback=scores.get("feedback", "Evaluation completed successfully.")
        )

    def _heuristic_evaluate(self, email: IncomingEmail, reply: SuggestedReply, hits: int, violations: int) -> dict:
        """Deterministic heuristic evaluator for offline/mock validation."""
        i_score = 85.0
        g_score = 90.0 if reply.retrieved_case_ids else 75.0
        t_score = 88.0 if ("thank" in reply.suggested_body.lower() or "apologize" in reply.suggested_body.lower()) else 72.0
        a_score = 85.0 if ("please" in reply.suggested_body.lower() or "follow" in reply.suggested_body.lower()) else 70.0

        if email.urgency == "critical" and not reply.should_escalate:
            i_score -= 30.0
            t_score -= 25.0

        return {
            "intent_resolution_score": i_score,
            "factual_grounding_score": g_score,
            "tone_empathy_score": t_score,
            "actionability_score": a_score,
            "feedback": "Heuristic evaluation based on policy keywords, grounding citations, and escalation compliance."
        }

    def evaluate_system(self, emails: List[IncomingEmail], replies: List[SuggestedReply]) -> SystemEvaluationReport:
        """Computes comprehensive system-wide metrics and category breakdown."""
        evals: List[ResponseEvaluation] = []
        cat_scores: Dict[str, List[float]] = {}
        crit_escalations_correct = 0
        crit_total = 0

        for email, reply in zip(emails, replies):
            ev = self.evaluate_single_response(email, reply)
            evals.append(ev)

            # Track category scores
            cat = email.category
            cat_scores.setdefault(cat, []).append(ev.composite_score)

            # Check critical risk escalation recall
            if email.urgency == "critical":
                crit_total += 1
                if reply.should_escalate:
                    crit_escalations_correct += 1

        total = len(evals)
        mean_comp = sum(e.composite_score for e in evals) / total if total else 0.0
        pass_count = sum(1 for e in evals if e.verdict == "PASS")
        pass_rate = (pass_count / total * 100.0) if total else 0.0

        mean_i = sum(e.intent_resolution_score for e in evals) / total if total else 0.0
        mean_g = sum(e.factual_grounding_score for e in evals) / total if total else 0.0
        mean_t = sum(e.tone_empathy_score for e in evals) / total if total else 0.0
        mean_a = sum(e.actionability_score for e in evals) / total if total else 0.0

        esc_recall = (crit_escalations_correct / crit_total * 100.0) if crit_total else 100.0
        cat_avg = {cat: round(sum(scores)/len(scores), 2) for cat, scores in cat_scores.items()}

        return SystemEvaluationReport(
            total_emails_evaluated=total,
            mean_composite_score=round(mean_comp, 2),
            overall_pass_rate_pct=round(pass_rate, 2),
            mean_intent_score=round(mean_i, 2),
            mean_grounding_score=round(mean_g, 2),
            mean_tone_score=round(mean_t, 2),
            mean_actionability_score=round(mean_a, 2),
            critical_risk_escalation_recall=round(esc_recall, 2),
            per_category_scores=cat_avg,
            per_response_evaluations=evals
        )
