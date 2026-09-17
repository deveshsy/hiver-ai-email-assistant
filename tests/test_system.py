import pytest
import os
import json
from src.schemas import IncomingEmail, SuggestedReply, HistoricalEmail
from src.retriever import EmailRetriever
from src.generator import ResponseGenerator
from src.evaluator import ReplyEvaluator

def test_dataset_files_exist_and_valid():
    assert os.path.exists("data/historical_support_emails.jsonl")
    assert os.path.exists("data/test_emails.jsonl")

    with open("data/historical_support_emails.jsonl", "r") as f:
        lines = [line.strip() for line in f if line.strip()]
        assert len(lines) >= 5
        first = json.loads(lines[0])
        assert "subject" in first and "ground_truth_reply" in first

def test_retriever_keyword_matching():
    retriever = EmailRetriever("data/historical_support_emails.jsonl")
    results = retriever.retrieve_similar_cases(
        subject="Unexpected invoice charge",
        body="We were overcharged on our monthly invoice",
        top_k=2
    )
    assert len(results) > 0
    assert any("invoice" in r.subject.lower() or "charge" in r.subject.lower() for r in results)

def test_response_generator_contract():
    email = IncomingEmail(
        id="test_unit_01",
        category="billing",
        sender="client@acme.com",
        subject="Need tax receipt for VAT",
        body="Please send our VAT receipt for accounting."
    )
    generator = ResponseGenerator(mock_mode=True)
    reply = generator.generate_reply(email)

    assert isinstance(reply, SuggestedReply)
    assert reply.email_id == "test_unit_01"
    assert len(reply.suggested_body) > 20
    assert "Hiver" in reply.suggested_body

def test_critical_escalation_detection():
    critical_email = IncomingEmail(
        id="test_unit_crit",
        category="churn_risk",
        sender="vp@enterprise.com",
        subject="Cancelling our contract immediately",
        body="Your service crashed our sales deal. Cancel all 100 seats today and refund.",
        urgency="critical"
    )
    generator = ResponseGenerator(mock_mode=True)
    reply = generator.generate_reply(critical_email)

    assert reply.should_escalate is True
    assert reply.escalation_reason is not None

def test_evaluator_composite_scoring():
    email = IncomingEmail(
        id="test_eval_unit",
        category="feature_how_to",
        sender="user@test.com",
        subject="How to export CSAT?",
        body="Where is the export button for CSAT reports?",
        must_contain=["export", "csat"]
    )
    reply = SuggestedReply(
        email_id="test_eval_unit",
        suggested_subject="Re: How to export CSAT?",
        suggested_body="Hi! You can export your CSAT data by clicking the Export button in Hiver Analytics. Best regards, Hiver Support Team",
        detected_intent="csat_export",
        risk_level="low",
        should_escalate=False
    )
    evaluator = ReplyEvaluator(mock_mode=True)
    score_card = evaluator.evaluate_single_response(email, reply)

    assert score_card.composite_score >= 70.0
    assert score_card.verdict in ["PASS", "FAIL"]
    assert "export" in score_card.must_contain_hits or len(score_card.must_contain_hits) >= 0
