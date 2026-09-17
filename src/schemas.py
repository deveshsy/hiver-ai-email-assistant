from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class IncomingEmail(BaseModel):
    id: str
    category: str
    sender: str
    subject: str
    body: str
    expected_intent: Optional[str] = None
    must_contain: List[str] = Field(default_factory=list)
    must_not_contain: List[str] = Field(default_factory=list)
    urgency: str = "medium"

class HistoricalEmail(BaseModel):
    id: str
    category: str
    sender: str
    subject: str
    body: str
    ground_truth_reply: str
    key_points: List[str] = Field(default_factory=list)
    risk_level: str = "low"

class SuggestedReply(BaseModel):
    email_id: str
    suggested_subject: str
    suggested_body: str
    detected_intent: str
    risk_level: str = Field(description="low, medium, high, or critical")
    should_escalate: bool
    escalation_reason: Optional[str] = None
    retrieved_case_ids: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.85)

class ResponseEvaluation(BaseModel):
    email_id: str
    intent_resolution_score: float = Field(ge=0, le=100)
    factual_grounding_score: float = Field(ge=0, le=100)
    tone_empathy_score: float = Field(ge=0, le=100)
    actionability_score: float = Field(ge=0, le=100)
    composite_score: float = Field(ge=0, le=100)
    verdict: str = Field(description="PASS or FAIL")
    must_contain_hits: List[str] = Field(default_factory=list)
    must_not_contain_violations: List[str] = Field(default_factory=list)
    feedback: str

class SystemEvaluationReport(BaseModel):
    total_emails_evaluated: int
    mean_composite_score: float
    overall_pass_rate_pct: float
    mean_intent_score: float
    mean_grounding_score: float
    mean_tone_score: float
    mean_actionability_score: float
    critical_risk_escalation_recall: float
    per_category_scores: Dict[str, float]
    per_response_evaluations: List[ResponseEvaluation]
