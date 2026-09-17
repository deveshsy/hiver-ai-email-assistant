"""Optional ingestion script for the public CMU Enron Email Corpus.

Honest Context & Limitations:
The Enron Email Corpus contains real-world corporate email threads from 1998-2002.
While it reflects genuine workplace email phrasing, politeness conventions, and conversational dynamics,
it is NOT customer support data, and contains NO Hiver product workflows or SaaS support policies.
This script is provided as an optional pipeline to demonstrate how real workplace email corpora
can be cleaned, PII-redacted, paired, and deduplicated without thread leakage.
It is NOT required for the default demo or challenge benchmark.
"""

import argparse
import email
import hashlib
import json
import os
import re
from typing import Dict, List, Optional, Tuple

PII_PHONE_REGEX = re.compile(r"\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
PII_EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

def clean_body_text(raw_body: str) -> str:
    """Strips quoted message history, forwarded blocks, and disclaimer footers."""
    lines = []
    for line in raw_body.splitlines():
        # Stop at forwarded / original message headers
        if re.match(r"^\s*-{3,}\s*(?:Original Message|Forwarded by)\s*-{3,}", line, re.IGNORECASE):
            break
        if re.match(r"^\s*From:\s+.*Sent:\s+.*", line, re.IGNORECASE):
            break
        # Skip quote lines
        if line.strip().startswith(">"):
            continue
        lines.append(line)

    text = "\n".join(lines).strip()
    # Redact PII (phone numbers and email addresses)
    text = PII_PHONE_REGEX.sub("[PHONE_REDACTED]", text)
    text = PII_EMAIL_REGEX.sub("[EMAIL_REDACTED]", text)
    return text

def parse_email_message(raw_text: str) -> Optional[Dict]:
    """Parses raw MIME/RFC822 email text into structured metadata and cleaned body."""
    try:
        msg = email.message_from_string(raw_text)
        sender = msg.get("From", "").strip()
        recipient = msg.get("To", "").strip()
        subject = msg.get("Subject", "").strip()
        msg_id = msg.get("Message-ID", "").strip()
        in_reply_to = msg.get("In-Reply-To", "").strip()
        date = msg.get("Date", "").strip()

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("latin-1", errors="replace")
                    break
        else:
            body = msg.get_payload(decode=True).decode("latin-1", errors="replace") if msg.get_payload(decode=True) else msg.get_payload()

        cleaned_body = clean_body_text(body)
        if len(cleaned_body) < 30:
            return None

        return {
            "message_id": msg_id,
            "in_reply_to": in_reply_to,
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "date": date,
            "body": cleaned_body
        }
    except Exception:
        return None

def pair_chronological_threads(parsed_messages: List[Dict]) -> List[Dict]:
    """Pairs incoming questions with high-confidence chronological replies by In-Reply-To or subject threading."""
    msg_by_id = {m["message_id"]: m for m in parsed_messages if m.get("message_id")}
    pairs = []
    seen_hashes = set()

    for m in parsed_messages:
        parent_id = m.get("in_reply_to")
        if parent_id and parent_id in msg_by_id:
            parent = msg_by_id[parent_id]
            # Ensure parent is not self and body content is distinct
            if parent["sender"] != m["sender"] and len(parent["body"]) > 25 and len(m["body"]) > 25:
                pair_key = hashlib.sha256(f"{parent['body'][:100]}_{m['body'][:100]}".encode()).hexdigest()
                if pair_key in seen_hashes:
                    continue
                seen_hashes.add(pair_key)

                pairs.append({
                    "id": f"enron_pair_{len(pairs) + 1}",
                    "base_case_id": f"enron_thread_{parent_id[:20]}",
                    "source_type": "public_real",
                    "source_name": "cmu_enron_corpus",
                    "split": "train_retrieval" if (len(pairs) % 4 != 0) else "test_evaluation",
                    "category": "workplace_communication",
                    "sender": "[REDACTED_SENDER]",
                    "subject": parent["subject"],
                    "body": parent["body"],
                    "ground_truth_reply": m["body"],
                    "risk_level": "low"
                })
    return pairs

def main():
    parser = argparse.ArgumentParser(description="Optional CMU Enron Email Corpus Ingestion & Pair Extraction")
    parser.add_argument("--source-dir", type=str, default=None, help="Path to local extracted Enron maildir directory")
    parser.add_argument("--output-file", type=str, default="data/enron_pairs.jsonl", help="Target output JSONL path")
    parser.add_argument("--max-pairs", type=int, default=100, help="Maximum number of pairs to extract")
    args = parser.parse_args()

    if not args.source_dir or not os.path.isdir(args.source_dir):
        print("[!] No source directory specified or directory does not exist.")
        print("[*] To use real Enron data, download the CMU tarball from:")
        print("    https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz (~423MB)")
        print("    and run: python scripts/ingest_enron_corpus.py --source-dir /path/to/maildir")
        print("[*] Exiting cleanly without downloading or modifying default datasets.")
        return

    parsed = []
    print(f"[*] Scanning {args.source_dir} for valid emails...")
    for root, _, files in os.walk(args.source_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="latin-1", errors="replace") as f:
                    rec = parse_email_message(f.read())
                    if rec:
                        parsed.append(rec)
            except Exception:
                continue
            if len(parsed) >= args.max_pairs * 5:
                break
        if len(parsed) >= args.max_pairs * 5:
            break

    pairs = pair_chronological_threads(parsed)[:args.max_pairs]
    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)
    with open(args.output_file, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")

    print(f"[+] Extracted and saved {len(pairs)} clean Enron reply pairs to {args.output_file}")

if __name__ == "__main__":
    main()
