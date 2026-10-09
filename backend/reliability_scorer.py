import os
import requests
from typing import Dict, Any

# Base reliability weights by source category
SOURCE_BASE_WEIGHTS = {
    "Corpus/Registry": 0.90,
    "Academic": 0.88,
    "Web": 0.72,
    "Social": 0.72,
    "News": 0.68
}

class ReliabilityScorer:
    """
    Source Reliability Scorer using source category base weights combined with
    dynamic trust scoring via CATS (cats-scoring) and Prism API integration.
    """
    def __init__(self, prism_api_key: str = None, cats_api_key: str = None):
        self.prism_api_key = prism_api_key or os.getenv("PRISM_API_KEY", "")
        self.cats_api_key = cats_api_key or os.getenv("CATS_API_KEY", "")
        
        # Check if cats library is available
        self.has_cats = False
        try:
            from cats.lite import score as cats_score
            self._cats_score = cats_score
            self.has_cats = True
        except ImportError:
            self._cats_score = None

    def get_base_weight(self, source_type: str) -> float:
        """Returns the static base weight for a given source type."""
        return SOURCE_BASE_WEIGHTS.get(source_type, 0.70)

    def compute_dynamic_trust(self, source_name: str, source_type: str, text_content: str = "") -> float:
        """
        Dynamically computes trust score using CATS / Prism API if available,
        or structured fallback rules.
        """
        # Try CATS scoring library if installed
        if self.has_cats and self._cats_score:
            try:
                messages = [{"role": "user", "content": f"Source: {source_name}. Claim: {text_content}"}]
                res = self._cats_score(messages, source_type=source_type.lower())
                if isinstance(res, dict) and "trust_score" in res:
                    return float(res["trust_score"])
            except Exception as e:
                print(f"[ReliabilityScorer] CATS scoring warning: {e}")

        # Try Prism API if API key provided
        if self.prism_api_key:
            try:
                # Simulated Prism API call structure
                resp = requests.post(
                    "https://api.prism-credibility.com/v1/score",
                    json={"source": source_name, "type": source_type},
                    headers={"Authorization": f"Bearer {self.prism_api_key}"},
                    timeout=2.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data.get("credibility_score", 0.85))
            except Exception as e:
                print(f"[ReliabilityScorer] Prism API warning: {e}")

        # Domain heuristic trust modifier
        trust_modifier = 1.0
        source_lower = source_name.lower()
        if "journal" in source_lower or "cdc" in source_lower or "nature" in source_lower or "registry" in source_lower:
            trust_modifier = 1.05
        elif "blog" in source_lower or "unverified" in source_lower:
            trust_modifier = 0.80

        base_weight = self.get_base_weight(source_type)
        return min(1.0, max(0.0, base_weight * trust_modifier))

    def score(self, doc: Dict[str, Any], semantic_score: float) -> Dict[str, float]:
        """
        Scores source reliability and computes weighted semantic score.
        """
        source_type = doc.get("source_type", "Web")
        source_name = doc.get("source", "Unknown")
        text = doc.get("text", "")

        base_weight = self.get_base_weight(source_type)
        dynamic_trust = self.compute_dynamic_trust(source_name, source_type, text)

        # Composite Reliability Score (0.0 to 1.0)
        reliability_score = min(1.0, max(0.0, 0.5 * base_weight + 0.5 * dynamic_trust))
        adjusted_semantic_score = min(1.0, semantic_score * reliability_score)

        return {
            "reliability_score": round(reliability_score, 4),
            "base_weight": round(base_weight, 4),
            "dynamic_trust": round(dynamic_trust, 4),
            "adjusted_semantic_score": round(adjusted_semantic_score, 4)
        }
