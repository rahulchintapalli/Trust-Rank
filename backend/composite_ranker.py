from typing import List, Dict, Any

DEFAULT_WEIGHTS = {
    "w_sem": 0.25,
    "w_rel": 0.20,
    "w_fresh": 0.15,
    "w_con": 0.20,
    "w_evid": 0.20
}

class CompositeRanker:
    """
    Jointly evaluates all 5 dimensions to produce a final TrustRank score:
    Final Score = w_sem * S_sem + w_rel * S_reliability + w_fresh * S_freshness + w_con * S_contradiction + w_evid * S_evidence
    """
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def rank(self, documents: List[Dict[str, Any]], custom_weights: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Ranks documents based on 5-dimension weighted fusion.
        """
        w = custom_weights or self.weights
        
        # Normalize weights if sum != 1.0
        total_w = sum(w.values())
        if total_w > 0 and abs(total_w - 1.0) > 1e-4:
            w = {k: v / total_w for k, v in w.items()}

        ranked_results = []
        for doc in documents:
            s_sem = doc.get("semantic_score", 0.0)
            s_rel = doc.get("reliability_score", 0.0)
            s_fresh = doc.get("freshness_score", 0.0)
            s_con = doc.get("contradiction_score", 1.0)
            s_evid = doc.get("evidence_score", 0.0)

            final_score = (
                w.get("w_sem", 0.25) * s_sem +
                w.get("w_rel", 0.20) * s_rel +
                w.get("w_fresh", 0.15) * s_fresh +
                w.get("w_con", 0.20) * s_con +
                w.get("w_evid", 0.20) * s_evid
            )

            doc_entry = dict(doc)
            doc_entry["trust_rank_score"] = round(final_score, 4)
            doc_entry["dimension_breakdown"] = {
                "relevance": round(s_sem, 4),
                "reliability": round(s_rel, 4),
                "freshness": round(s_fresh, 4),
                "contradiction": round(s_con, 4),
                "evidence_strength": round(s_evid, 4)
            }
            ranked_results.append(doc_entry)

        # Sort by final score descending
        ranked_results.sort(key=lambda x: x["trust_rank_score"], reverse=True)
        return ranked_results
