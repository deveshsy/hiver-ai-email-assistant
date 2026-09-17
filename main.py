import argparse
import json
import os
import sys
import time
from typing import List

from src.schemas import IncomingEmail, SuggestedReply
from src.retriever import EmailRetriever
from src.generator import ResponseGenerator
from src.evaluator import ReplyEvaluator

def load_test_emails(path: str = "data/test_emails.jsonl") -> List[IncomingEmail]:
    """Loads test email dataset, auto-building if missing."""
    if not os.path.exists(path):
        print(f"[*] Dataset not found at {path}. Generating now...")
        import scripts.build_dataset as bd
        bd.generate_datasets()

    emails = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                emails.append(IncomingEmail(**json.loads(line)))
    return emails

def print_separator(char="=", width=80):
    print(char * width)

def run_pipeline(demo_mode: bool = False, force_mock: bool = False, limit: int = 0):
    print_separator()
    print("      HIVER AI EMAIL SUGGESTED-RESPONSE & EVALUATION SYSTEM")
    print_separator()

    # 1. Load Data
    all_emails = load_test_emails()
    if demo_mode:
        test_set = all_emails[:2]
    elif limit > 0:
        test_set = all_emails[:limit]
    else:
        test_set = all_emails
    print(f"[*] Loaded {len(test_set)} test emails for evaluation (Demo Mode: {demo_mode})")

    # 2. Initialize Components
    retriever = EmailRetriever()
    generator = ResponseGenerator(mock_mode=force_mock, retriever=retriever)
    evaluator = ReplyEvaluator(mock_mode=force_mock)

    mode_str = "DETERMINISTIC MOCK" if generator.mock_mode else f"LIVE GEMINI ({generator.model_name})"
    print(f"[*] Execution Mode: {mode_str}")
    print_separator("-")

    # 3. Generate and Evaluate per response
    generated_replies: List[SuggestedReply] = []
    print("\n--- [PHASE 1: PER-RESPONSE GENERATION & ACCURACY SCORING] ---\n")

    for idx, email in enumerate(test_set, 1):
        print(f"[{idx}/{len(test_set)}] Processing: '{email.subject}' ({email.category}, Urgency: {email.urgency})")
        
        reply = generator.generate_reply(email)
        generated_replies.append(reply)
        
        # Pacing to avoid free-tier API quota spikes
        if not generator.mock_mode:
            time.sleep(2.0)

        # Evaluate single response
        eval_res = evaluator.evaluate_single_response(email, reply)

        # Print detailed per-response scorecard
        esc_str = f"YES ({reply.escalation_reason})" if reply.should_escalate else "NO (Auto-handled)"
        color_verdict = f"[PASS]" if eval_res.verdict == "PASS" else "[FAIL]"
        
        print(f"    Intent:        {reply.detected_intent}")
        print(f"    Escalate:      {esc_str}")
        print(f"    Scores:        Intent: {eval_res.intent_resolution_score}/100 | Grounding: {eval_res.factual_grounding_score}/100 | Tone: {eval_res.tone_empathy_score}/100 | Actionability: {eval_res.actionability_score}/100")
        print(f"    Composite:     {eval_res.composite_score}/100 -> Verdict: {color_verdict}")
        print(f"    Feedback:      {eval_res.feedback}")
        if eval_res.must_not_contain_violations:
            print(f"    VIOLATIONS:    {eval_res.must_not_contain_violations} (-15 penalty applied)")
        print()

        # Pacing between emails
        if not generator.mock_mode and idx < len(test_set):
            time.sleep(2.5)

    # 4. System-Wide Aggregate Report
    print_separator("=")
    print("            PHASE 2: OVERALL SYSTEM ACCURACY BENCHMARK")
    print_separator("=")

    report = evaluator.evaluate_system(test_set, generated_replies)

    print(f"Total Emails Evaluated:            {report.total_emails_evaluated}")
    print(f"Mean Composite Quality Score:      {report.mean_composite_score}/100")
    print(f"Overall Pass Rate:                 {report.overall_pass_rate_pct}%")
    print(f"Mean Intent Resolution Score:      {report.mean_intent_score}/100")
    print(f"Mean Factual Grounding Score:      {report.mean_grounding_score}/100")
    print(f"Mean Tone & Empathy Score:         {report.mean_tone_score}/100")
    print(f"Mean Actionability Score:          {report.mean_actionability_score}/100")
    escalation_recall = (
        f"{report.critical_risk_escalation_recall}%"
        if report.critical_risk_escalation_recall is not None
        else "N/A (no critical examples in this run)"
    )
    print(f"Critical Risk Escalation Recall:   {escalation_recall}")
    
    print("\n--- Per-Category Performance Breakdown ---")
    for cat, score in report.per_category_scores.items():
        print(f"  • {cat:<22}: {score:>6.1f}/100")

    # 5. Export JSON Artifact
    os.makedirs("results", exist_ok=True)
    report_file = "results/evaluation_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"\n[+] Full evaluation report exported to: {report_file}")
    print_separator()

def handle_single_email(body_text: str, subject: str = "Support Inquiry", force_mock: bool = False):
    """Processes an ad-hoc incoming email for live testing and demonstration."""
    print_separator("=")
    print("      HIVER AI EMAIL ASSISTANT — INTERACTIVE SUGGESTION MODE")
    print_separator("=")
    print(f"Incoming Subject:  {subject}")
    print(f"Incoming Body:     {body_text.strip()}")
    print_separator("-")

    email = IncomingEmail(
        id="adhoc_custom",
        category="inquiry",
        sender="customer@external.io",
        subject=subject,
        body=body_text,
        urgency="medium"
    )

    retriever = EmailRetriever()
    similar_cases = retriever.retrieve_similar_cases(subject, body_text, top_k=2)

    print("[*] Retrieved Top-2 Relevant Historical Cases:")
    for i, c in enumerate(similar_cases, 1):
        print(f"    [{i}] ID: {c.id} | Subject: '{c.subject}' | Category: {c.category}")
    print_separator("-")

    generator = ResponseGenerator(mock_mode=force_mock, retriever=retriever)
    reply = generator.generate_reply(email)

    print("\n--- SUGGESTED REPLY GENERATED ---")
    print(f"Suggested Subject: {reply.suggested_subject}")
    print(f"Detected Intent:   {reply.detected_intent}")
    print(f"Assessed Risk:     {reply.risk_level.upper()}")
    if reply.should_escalate:
        print(f"⚠️  ESCALATION REQUIRED: {reply.escalation_reason}")
    else:
        print("✅ ROUTE: Auto-handled by agent")
    print("\nBody:\n")
    print(reply.suggested_body)
    print_separator("-")

    # Run Evaluator
    evaluator = ReplyEvaluator(mock_mode=True)
    ev = evaluator.evaluate_single_response(email, reply)
    print("--- EVALUATOR SCORING & POLICY CHECK ---")
    print(f"Composite Score:   {ev.composite_score}/100 -> Verdict: [{ev.verdict}]")
    print(f"Intent Resolution: {ev.intent_resolution_score}/100")
    print(f"Factual Grounding: {ev.factual_grounding_score}/100")
    print(f"Tone & Empathy:    {ev.tone_empathy_score}/100")
    print(f"Actionability:     {ev.actionability_score}/100")
    print(f"Rubric Feedback:   {ev.feedback}")
    print_separator("=")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hiver AI Email Response & Accuracy System")
    parser.add_argument("--demo", action="store_true", help="Run quick 2-email evaluation demo")
    parser.add_argument("--mock", action="store_true", help="Run in deterministic mock mode without API calls")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of emails to evaluate")
    parser.add_argument("--reply", type=str, default=None, help="Generate and evaluate a suggested reply for an ad-hoc custom incoming email")
    parser.add_argument("--subject", type=str, default="Customer Support Inquiry", help="Subject line for ad-hoc customer email (used with --reply)")
    args = parser.parse_args()

    if args.reply:
        handle_single_email(body_text=args.reply, subject=args.subject, force_mock=args.mock)
    else:
        run_pipeline(demo_mode=args.demo, force_mock=args.mock, limit=args.limit)

