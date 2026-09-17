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
    base_case_id: Optional[str] = None
    source_type: str = "domain_synthetic"
    source_name: str = "hiver_support_synthetic_v1"
    split: str = "test_evaluation"

class HistoricalEmail(BaseModel):
    id: str
    category: str
    sender: str
    subject: str
    body: str
    ground_truth_reply: str
    key_points: List[str] = Field(default_factory=list)
    risk_level: str = "low"
    base_case_id: Optional[str] = None
    source_type: str = "domain_synthetic"
    source_name: str = "hiver_support_synthetic_v1"
    split: str = "train_retrieval"

class SuggestedReply(BaseModel):
    email_id: str
    suggested_subject: str
    suggested_body: str
    detected_intent: str
    risk_level: str = Field(description="low, medium, high, or critical")
    should_escalate: bool
    escalation_reason: Optional[str] = None
    retrieved_case_ids: List[str] = Field(default_factory=list)
    retrieval_scores: List[float] = Field(default_factory=list)
    execution_mode: str = Field(
        default="deterministic_demo",
        description="live_llm, deterministic_demo, or fallback_after_llm_error"
    )
    is_abstention: bool = False
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
    entity_mismatches: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    hard_fail_reasons: List[str] = Field(default_factory=list)
    requirement_coverage_pct: float = Field(ge=0, le=100, default=100.0)
    entity_consistency_score: float = Field(ge=0, le=100, default=100.0)
    retrieval_relevance_score: float = Field(ge=0, le=100, default=100.0)
    escalation_correctness: bool = True
    is_sendable: bool = True
    feedback: str

class SystemEvaluationReport(BaseModel):
    total_emails_evaluated: int
    mean_composite_score: float
    overall_pass_rate_pct: float
    hard_failure_rate_pct: float = 0.0
    mean_intent_score: float
    mean_grounding_score: float
    mean_tone_score: float
    mean_actionability_score: float
    mean_requirement_coverage_pct: float = 0.0
    sendability_proxy_pct: float = 0.0
    false_pass_count_adversarial: int = 0
    critical_risk_escalation_recall: Optional[float] = Field(
        default=None,
        description="Percentage of critical emails escalated, or null when the evaluation set has no critical emails",
    )
    per_category_scores: Dict[str, float]
    per_response_evaluations: List[ResponseEvaluation]
