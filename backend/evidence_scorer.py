from datetime import datetime, timezone
from typing import Dict, Any

EVIDENCE_QUALITY_WEIGHTS = {
    "peer-reviewed": 1.0,
    "clinical trial": 0.9,
    "news": 0.5,
    "blog": 0.2
}

class EvidenceScorer:
    """
    ET-RAG Evidence Scorer:
    EvidenceScore = 0.5 * CosineSim + 0.3 * EvidenceQuality + 0.2 * Recency
    """
    def __init__(self):
        pass

    def calculate_recency(self, timestamp_str: str, max_age_years: float = 10.0) -> float:
        """
        Normalized age of document (1.0 = today/0 years old, 0.0 = 10+ years old).
        """
        if not timestamp_str:
            return 0.5

        try:
            cleaned_ts = timestamp_str.replace("Z", "+00:00")
            doc_date = datetime.fromisoformat(cleaned_ts)
            if doc_date.tzinfo is None:
                doc_date = doc_date.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            age_years = (now - doc_date).total_seconds() / (365.25 * 24 * 3600)
            
            if age_years <= 0:
                return 1.0
            
            recency = max(0.0, 1.0 - (age_years / max_age_years))
            return round(recency, 4)
        except Exception:
            return 0.5

    def get_evidence_quality(self, evidence_type: str) -> float:
        """GRADE-based evidence hierarchy weight."""
        return EVIDENCE_QUALITY_WEIGHTS.get(evidence_type.lower(), 0.3)

    def score(self, doc: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculates composite evidence score using ET-RAG formula.
        """
        cosine_sim = doc.get("dense_score", doc.get("semantic_score", 0.5))
        evidence_type = doc.get("evidence_type", "blog")
        timestamp_str = doc.get("timestamp", "")

        quality_score = self.get_evidence_quality(evidence_type)
        recency_score = self.calculate_recency(timestamp_str)

        evidence_score = (
            0.5 * cosine_sim +
            0.3 * quality_score +
            0.2 * recency_score
        )

        return {
            "evidence_score": round(evidence_score, 4),
            "cosine_sim": round(cosine_sim, 4),
            "evidence_quality": round(quality_score, 4),
            "recency": round(recency_score, 4)
        }
