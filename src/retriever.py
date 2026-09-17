import json
import math
import os
import re
from typing import List, Dict, Tuple, Optional
from collections import Counter
from src.schemas import HistoricalEmail

STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "with", "is", "was",
    "are", "were", "from", "by", "as", "it", "this", "that", "be", "have", "has",
    "had", "do", "does", "did", "we", "our", "us", "you", "your", "they", "their",
    "i", "my", "me", "and", "or", "but", "hi", "hello", "hey", "dear", "thanks",
    "thank", "regards", "please", "hiver", "support", "customer", "inquiry", "email",
    "team"
}

TERM_BRIDGES = {
    "double": "duplicate",
    "twice": "duplicate",
    "reverse": "refund",
    "reversal": "refund",
    "cancelling": "cancellation",
    "cancel": "cancellation",
    "breach": "sla",
    "downtime": "outage",
    "erasure": "gdpr",
    "forgotten": "gdpr",
    "crash": "memory",
    "freezing": "crash",
}

class OkapiBM25Retriever:
    """Production Okapi BM25 retriever with inverted index, IDF weighting, document length normalization,
    base_case_id deduplication, entity-aware weighting, stopword filtering, and configurable minimum relevance thresholding.
    """

    def __init__(
        self,
        data_path: str = "data/historical_support_emails.jsonl",
        k1: float = 1.5,
        b: float = 0.75,
        min_relevance_threshold: float = 2.5
    ):
        self.k1 = k1
        self.b = b
        self.min_relevance_threshold = min_relevance_threshold
        self.records: List[HistoricalEmail] = []
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lens: List[int] = []
        self.doc_freqs: Dict[str, int] = Counter()
        self.term_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}

        if os.path.exists(data_path):
            self._build_index(data_path)

    def _tokenize(self, text: str) -> List[str]:
        """Lowercases, filters stopwords, expands known domain bridges, and extracts alphanumeric/entity tokens."""
        raw_tokens = [
            w for w in re.findall(r"\b[a-zA-Z0-9_\-\$#\(\)]+\b", text.lower())
            if len(w) > 1 and w not in STOP_WORDS
        ]
        tokens = []
        for t in raw_tokens:
            tokens.append(t)
            if t in TERM_BRIDGES:
                tokens.append(TERM_BRIDGES[t])
        return tokens

    def _build_index(self, data_path: str):
        self.records = []
        self.doc_lens = []
        self.doc_freqs = Counter()
        self.term_freqs = []
        self.idf = {}

        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    self.records.append(HistoricalEmail(**data))

        self.corpus_size = len(self.records)
        if self.corpus_size == 0:
            return

        total_len = 0
        for rec in self.records:
            # Weighted field representation:
            # Subject given 3x weight, key_points 2x weight, category 2x weight, body 1x
            weighted_text = (
                f"{rec.subject} {rec.subject} {rec.subject} "
                f"{rec.category} {rec.category} "
                f"{' '.join(rec.key_points)} {' '.join(rec.key_points)} "
                f"{rec.body}"
            )
            tokens = self._tokenize(weighted_text)
            doc_len = len(tokens)
            self.doc_lens.append(doc_len)
            total_len += doc_len

            tf = Counter(tokens)
            self.term_freqs.append(tf)
            for term in tf.keys():
                self.doc_freqs[term] += 1

        self.avg_doc_len = total_len / self.corpus_size

        # Compute standard Lucene/Okapi smoothed IDF
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def retrieve_with_scores(
        self,
        subject: str,
        body: str,
        top_k: int = 2
    ) -> List[Tuple[HistoricalEmail, float]]:
        """Calculates BM25 relevance, deduplicates by base_case_id, and filters by min_relevance_threshold."""
        if not self.records or self.corpus_size == 0:
            return []

        query_tokens = self._tokenize(f"{subject} {subject} {body}")
        if not query_tokens:
            return []

        raw_scores: List[Tuple[float, HistoricalEmail]] = []
        for idx, rec in enumerate(self.records):
            doc_len = self.doc_lens[idx]
            tf = self.term_freqs[idx]
            score = 0.0

            for q_term in query_tokens:
                if q_term not in tf:
                    continue
                term_count = tf[q_term]
                idf = self.idf.get(q_term, 0.0)

                # Standard Okapi BM25 numerator and denominator
                numerator = idf * term_count * (self.k1 + 1.0)
                denominator = term_count + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                score += (numerator / denominator)

            raw_scores.append((score, rec))

        # Sort descending by relevance score
        raw_scores.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate strictly by base_case_id (never return multiple variants of same base scenario)
        seen_base_cases = set()
        deduped: List[Tuple[HistoricalEmail, float]] = []

        for score, rec in raw_scores:
            base_id = rec.base_case_id or rec.id
            if base_id in seen_base_cases:
                continue
            seen_base_cases.add(base_id)

            # Apply minimum relevance threshold
            if score >= self.min_relevance_threshold:
                deduped.append((rec, round(score, 2)))

            if len(deduped) >= top_k:
                break

        return deduped

    def retrieve_similar_cases(self, subject: str, body: str, top_k: int = 2) -> List[HistoricalEmail]:
        """Convenience method returning matched HistoricalEmail documents."""
        pairs = self.retrieve_with_scores(subject, body, top_k=top_k)
        return [item[0] for item in pairs]

# Alias for backward compatibility
EmailRetriever = OkapiBM25Retriever
