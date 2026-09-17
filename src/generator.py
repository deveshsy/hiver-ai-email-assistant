import json
import os
import re
import time
from typing import Optional, List
from src.schemas import IncomingEmail, SuggestedReply, HistoricalEmail
from src.retriever import EmailRetriever

def load_api_key_from_env() -> Optional[str]:
    """Helper to read GEMINI_API_KEY from environment or local .env file."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ.get("GEMINI_API_KEY")
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1].strip()
    return None

class ResponseGenerator:
    """Generative AI Email Response Generator with RAG Grounding and Risk Escalation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.6-flash",
        retriever: Optional[EmailRetriever] = None,
        mock_mode: bool = False
    ):
        self.api_key = api_key or load_api_key_from_env()
        self.model_name = model_name
        self.retriever = retriever or EmailRetriever()
        self.mock_mode = mock_mode or (not self.api_key)
        self.client = None

        if not self.mock_mode:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[!] Warning: Could not initialize Gemini client ({e}). Falling back to mock mode.")
                self.mock_mode = True

    def _extract_clean_json(self, raw_text: str) -> dict:
        """Robustly extracts JSON from LLM output, handling markdown fences and extraneous text."""
        # Strip markdown fences
        text = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.MULTILINE)
        text = re.sub(r"```$", "", text.strip(), flags=re.MULTILINE).strip()
        
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try regex extract first JSON object
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"Could not parse JSON from output: {raw_text[:200]}")

    def generate_reply(self, email: IncomingEmail) -> SuggestedReply:
        """Generates a suggested email reply grounded in historical support cases."""
        # 1. Retrieve historical reference cases
        similar_cases = self.retriever.retrieve_similar_cases(email.subject, email.body, top_k=2)
        retrieved_ids = [c.id for c in similar_cases]

        # 2. If mock mode, return high-fidelity rule/heuristic response
        if self.mock_mode or not self.client:
            return self._mock_generate(email, similar_cases)

        # 3. Format Few-Shot Context
        context_str = ""
        for i, c in enumerate(similar_cases, 1):
            context_str += f"\n--- Historical Case #{i} ---\nSubject: {c.subject}\nCustomer Query: {c.body}\nAgent Resolution: {c.ground_truth_reply}\n"

        prompt = f"""You are an expert customer support specialist at Hiver (email collaboration software for Google Workspace).
Your task is to draft a high-quality, grounded suggested email reply to the incoming customer email below.

CORE INSTRUCTIONS:
1. Empathy & Tone: Professional, courteous, de-escalating, and concise. Never use generic corporate jargon.
2. Grounding: Ground your technical explanations, refund policies, and navigation steps in the provided Historical Cases. Do NOT invent fictional features or pricing discounts.
3. Escalation:
   - If the email involves a critical churn risk (threatening to cancel, lost revenue), legal/GDPR privacy demand, or severe billing error, flag `should_escalate: true` with a clear reason.
   - Otherwise, provide an actionable resolution and set `should_escalate: false`.
4. Formatting: Write a complete email reply including greeting, resolution body, and professional signoff ('Best regards,\nHiver Support Team').

{context_str}

Incoming Email to Answer:
From: {email.sender}
Subject: {email.subject}
Body:
{email.body}

Output strictly valid JSON with these exact fields:
{{
  "suggested_subject": "Re: {email.subject}",
  "suggested_body": "<full email text>",
  "detected_intent": "<1-3 word intent label>",
  "risk_level": "<low|medium|high|critical>",
  "should_escalate": <true|false>,
  "escalation_reason": <string or null>,
  "confidence_score": <float between 0.0 and 1.0>
}}
"""
        # Call Gemini with retry backoff
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                data = self._extract_clean_json(response.text)
                return SuggestedReply(
                    email_id=email.id,
                    suggested_subject=data.get("suggested_subject", f"Re: {email.subject}"),
                    suggested_body=data.get("suggested_body", ""),
                    detected_intent=data.get("detected_intent", email.category),
                    risk_level=data.get("risk_level", email.urgency),
                    should_escalate=bool(data.get("should_escalate", False)),
                    escalation_reason=data.get("escalation_reason"),
                    retrieved_case_ids=retrieved_ids,
                    confidence_score=float(data.get("confidence_score", 0.88))
                )
            except Exception as e:
                if attempt == 2:
                    print(f"[!] LLM failed after 3 attempts ({e}). Falling back to grounded template.")
                    return self._mock_generate(email, similar_cases)
                time.sleep(1.5 * (attempt + 1))

    def _mock_generate(self, email: IncomingEmail, similar_cases: List[HistoricalEmail]) -> SuggestedReply:
        """Deterministic mock generator for zero-friction review without API keys."""
        is_critical = email.urgency == "critical" or "cancel" in email.body.lower() or "gdpr" in email.body.lower()
        
        if similar_cases:
            base_resolution = similar_cases[0].ground_truth_reply
        else:
            base_resolution = "Thank you for reaching out. We have received your query and our team is actively reviewing your account."

        if is_critical:
            body = (
                f"Hi {email.sender.split('@')[0].capitalize()},\n\n"
                f"Thank you for contacting Hiver Support. I sincerely apologize for the frustration and severity of this issue.\n\n"
                f"Because of the critical nature of your request regarding '{email.subject}', I have immediately escalated this ticket to our Head of Customer Success and Engineering Leads for priority intervention.\n\n"
                f"We are actively investigating and will follow up with an update within the hour.\n\n"
                f"Best regards,\nHiver Support Team"
            )
            reason = "High business risk or compliance request requiring leadership escalation."
        else:
            body = (
                f"Hi {email.sender.split('@')[0].capitalize()},\n\n"
                f"Thanks for reaching out to Hiver Support. Here is what you need regarding '{email.subject}':\n\n"
                f"{base_resolution}\n\n"
                f"Please let us know if you need any additional assistance.\n\n"
                f"Best regards,\nHiver Support Team"
            )
            reason = None

        return SuggestedReply(
            email_id=email.id,
            suggested_subject=f"Re: {email.subject}",
            suggested_body=body,
            detected_intent=email.category,
            risk_level=email.urgency,
            should_escalate=is_critical,
            escalation_reason=reason,
            retrieved_case_ids=[c.id for c in similar_cases],
            confidence_score=0.92 if similar_cases else 0.75
        )
