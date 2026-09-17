import json
import os
import re
from typing import List, Dict, Tuple
from src.schemas import HistoricalEmail

class EmailRetriever:
    """Historical email retriever using BM25 keyword matching and term frequency."""

    def __init__(self, data_path: str = "data/historical_support_emails.jsonl"):
        self.records: List[HistoricalEmail] = []
        self.data_path = data_path
        self._load_corpus()

    def _tokenize(self, text: str) -> List[str]:
        return [w for w in re.findall(r"\w+", text.lower()) if len(w) > 2]

    def _load_corpus(self):
        if not os.path.exists(self.data_path):
            return
        with open(self.data_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    self.records.append(HistoricalEmail(**data))

    def retrieve_similar_cases(self, subject: str, body: str, top_k: int = 2) -> List[HistoricalEmail]:
        """Ranks historical emails based on query term overlap with subject + body."""
        if not self.records:
            return []

        query_tokens = set(self._tokenize(f"{subject} {body}"))
        if not query_tokens:
            return self.records[:top_k]

        scored: List[Tuple[float, HistoricalEmail]] = []
        for rec in self.records:
            doc_tokens = self._tokenize(f"{rec.subject} {rec.body} {' '.join(rec.key_points)}")
            if not doc_tokens:
                continue

            # Calculate TF-IDF style term overlap
            overlap = sum(1.5 if t in rec.subject.lower() else 1.0 for t in query_tokens if t in doc_tokens)
            score = overlap / (len(doc_tokens) ** 0.5)

            # Category boost if explicit matching
            if rec.category in body.lower() or rec.category in subject.lower():
                score += 1.0

            scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]
