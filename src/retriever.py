import json
import math
import os
import re
from typing import List, Dict, Tuple
from collections import Counter
from src.schemas import HistoricalEmail

class OkapiBM25Retriever:
    """Production Okapi BM25 retriever with inverted index, IDF weighting, and document length normalization."""

    def __init__(self, data_path: str = "data/historical_support_emails.jsonl", k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
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
        """Lowercases and extracts alpha-numeric word tokens."""
        return [w for w in re.findall(r"\b[a-zA-Z0-9_\-\$#]+\b", text.lower()) if len(w) > 1]

    def _build_index(self, data_path: str):
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
            # Weighted field representation: Subject terms given 2x weight
            tokens = self._tokenize(f"{rec.subject} {rec.subject} {rec.body} {' '.join(rec.key_points)}")
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

    def retrieve_similar_cases(self, subject: str, body: str, top_k: int = 2) -> List[HistoricalEmail]:
        """Calculates Okapi BM25 score between incoming query and historical corpus."""
        if not self.records or self.corpus_size == 0:
            return []

        query_tokens = self._tokenize(f"{subject} {subject} {body}")
        if not query_tokens:
            return self.records[:top_k]

        scores: List[Tuple[float, HistoricalEmail]] = []
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

            scores.append((score, rec))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scores[:top_k]]

# Alias for backward compatibility
EmailRetriever = OkapiBM25Retriever
