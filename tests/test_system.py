import pytest
import os
import json
from src.schemas import IncomingEmail, SuggestedReply, HistoricalEmail
from src.retriever import OkapiBM25Retriever
from src.generator import ResponseGenerator
from src.evaluator import ReplyEvaluator, check_requirement_satisfied, check_forbidden_violated

def test_dataset_files_exist_and_valid():
    assert os.path.exists("data/historical_support_emails.jsonl")
    assert os.path.exists("data/test_emails.jsonl")

    with open("data/historical_support_emails.jsonl", "r") as f:
        lines = [line.strip() for line in f if line.strip()]
        assert len(lines) >= 10
        first = json.loads(lines[0])
        assert "subject" in first and "ground_truth_reply" in first

def test_okapi_bm25_retrieval():
    retriever = OkapiBM25Retriever("data/historical_support_emails.jsonl")
    assert retriever.corpus_size >= 10
    assert retriever.avg_doc_len > 0
    assert len(retriever.idf) > 0

    results = retriever.retrieve_similar_cases(
        subject="Unexpected invoice charge on August bill",
        body="We were charged $240 instead of $160 for collaborator seats",
        top_k=2
    )
    assert len(results) > 0
    top = results[0]
    assert "invoice" in top.subject.lower() or "charge" in top.subject.lower()

def test_disjunction_requirement_satisfied():
    # Should satisfy either 'refund' or 'reversal'
    req = "refund or reversal"
    text1 = "We will issue a full refund to your corporate card."
    text2 = "We have requested a transaction reversal with finance."
    text3 = "We have received your email."
    
    assert check_requirement_satisfied(req, text1) is True
    assert check_requirement_satisfied(req, text2) is True
    assert check_requirement_satisfied(req, text3) is False

def test_forbidden_anti_pattern_detection():
    forbidden = "have a nice day"
    text_bad = "Your contract is terminated effective immediately. Have a nice day!"
    text_good = "Your contract cancellation request has been escalated to executive management."

    assert check_forbidden_violated(forbidden, text_bad) is True
    assert check_forbidden_violated(forbidden, text_good) is False

def test_evaluator_rejects_poisoned_response():
    email = IncomingEmail(
        id="test_crit_churn",
        category="churn_risk",
        sender="ceo@client.com",
        subject="Cancelling 100 seats due to missing emails",
        body="Cancel our subscription immediately.",
        must_contain=["executive empathy", "immediate human escalation", "cancellation"],
        must_not_contain=["have a nice day", "casual automated closing"],
        urgency="critical"
    )
    # Poisoned response: rude, no escalation, forbidden phrase
    bad_reply = SuggestedReply(
        email_id="test_crit_churn",
        suggested_subject="Re: Cancelling",
        suggested_body="Sorry you are upset. We cancelled your seats. Have a nice day!",
        detected_intent="churn",
        risk_level="low",
        should_escalate=False
    )
    evaluator = ReplyEvaluator(mock_mode=True)
    res = evaluator.evaluate_single_response(email, bad_reply)

    assert res.verdict == "FAIL"
    assert res.composite_score < 50.0
    assert len(res.must_not_contain_violations) > 0


def test_critical_recall_is_not_reported_without_critical_examples():
    email = IncomingEmail(
        id="noncritical",
        category="billing",
        sender="user@example.com",
        subject="Invoice copy",
        body="Please send an invoice copy.",
        must_contain=["invoice"],
        urgency="low",
    )
    reply = SuggestedReply(
        email_id=email.id,
        suggested_subject="Re: Invoice copy",
        suggested_body="Hi,\n\nPlease download the invoice from Billing Settings.\n\nBest,\nSupport",
        detected_intent="billing",
        risk_level="low",
        should_escalate=False,
    )

    report = ReplyEvaluator(mock_mode=True).evaluate_system([email], [reply])

    assert report.critical_risk_escalation_recall is None


def test_score_clamping_bounds():
    email = IncomingEmail(
        id="test_clamp",
        category="security",
        sender="test@example.com",
        subject="Test query",
        body="Body text",
        must_contain=["missing_item_1", "missing_item_2"],
        must_not_contain=["bad_word_1", "bad_word_2", "bad_word_3"],
        urgency="high"
    )
    reply = SuggestedReply(
        email_id="test_clamp",
        suggested_subject="Re: Test",
        suggested_body="bad_word_1 bad_word_2 bad_word_3",
        detected_intent="unknown",
        risk_level="low",
        should_escalate=False
    )
    evaluator = ReplyEvaluator(mock_mode=True)
    res = evaluator.evaluate_single_response(email, reply)
    assert res.composite_score >= 0.0
    assert res.composite_score <= 100.0
    assert res.verdict == "FAIL"


def test_critical_escalation_detection():
    email = IncomingEmail(
        id="test_crit",
        category="churn_risk",
        sender="enterprise_ceo@client.com",
        subject="Cancelling our contract due to service outage",
        body="We are cancelling our contract immediately and moving to a competitor.",
        urgency="critical"
    )
    generator = ResponseGenerator(mock_mode=True)
    reply = generator.generate_reply(email)
    assert reply.should_escalate is True
    assert reply.escalation_reason is not None


def test_bm25_empty_query_resilience():
    retriever = OkapiBM25Retriever()
    results_empty = retriever.retrieve_similar_cases("", "", top_k=2)
    assert isinstance(results_empty, list)
    results_punct = retriever.retrieve_similar_cases("??? !!! ...", "### $$$ %%%", top_k=2)
    assert isinstance(results_punct, list)

