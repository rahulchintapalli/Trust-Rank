import math
from datetime import datetime, timezone
from typing import Dict, Any, List

DECAY_RATES = {
    "vital signs": 0.005,  # Adjusted for realistic temporal decay
    "news": 0.001,
    "demographics": 0.00005
}

DEFAULT_BETA = 0.001

class FreshnessFilter:
    """
    Fact-level temporal validity filter with domain-specific exponential decay:
    decay(t) = exp(-beta * delta_days)
    """
    def __init__(self, default_threshold: float = 0.0):
        self.default_threshold = default_threshold

    def calculate_decay(self, timestamp_str: str, category: str = "news", reference_date: datetime = None) -> float:
        """
        Calculates exponential decay factor given ISO timestamp string and category.
        """
        if not reference_date:
            reference_date = datetime.now(timezone.utc)

        if not timestamp_str:
            return 0.70  # Reasonable default for unknown dates

        try:
            cleaned_ts = timestamp_str.replace("Z", "+00:00")
            doc_date = datetime.fromisoformat(cleaned_ts)
            if doc_date.tzinfo is None:
                doc_date = doc_date.replace(tzinfo=timezone.utc)
            
            delta_days = (reference_date - doc_date).total_seconds() / (24 * 3600)
            if delta_days < 0:
                delta_days = 0

            beta = DECAY_RATES.get(category.lower(), DEFAULT_BETA)
            freshness_score = math.exp(-beta * delta_days)
            return min(1.0, max(0.05, freshness_score))

        except Exception as e:
            print(f"[FreshnessFilter] Timestamp parsing note: {e}")
            return 0.70

    def filter_and_score(self, documents: List[Dict[str, Any]], threshold: float = None) -> List[Dict[str, Any]]:
        """
        Calculates freshness_score for each document and keeps documents above threshold.
        """
        min_threshold = threshold if threshold is not None else self.default_threshold
        scored_docs = []

        for doc in documents:
            timestamp_str = doc.get("timestamp", "")
            category = doc.get("category", "news")
            
            freshness = self.calculate_decay(timestamp_str, category)
            
            doc_copy = dict(doc)
            doc_copy["freshness_score"] = round(freshness, 4)
            doc_copy["is_fresh"] = freshness >= min_threshold

            # Include documents unless explicitly below custom threshold
            if min_threshold <= 0.0 or doc_copy["is_fresh"]:
                scored_docs.append(doc_copy)

        return scored_docs
