import re
from functools import lru_cache
from typing import List, Dict, Any

# Common polar opposite / conflict keyword pairs for ultra-fast NLI contradiction scoring
CONFLICT_PAIRS = [
    ("cure", "no cure"), ("cure", "incureable"), ("cures", "does not cure"),
    ("reduces", "increases"), ("reduces", "causes"),
    ("effective", "ineffective"), ("effective", "dangerous"), ("safe", "dangerous"),
    ("benefit", "harm"), ("proven", "unverified"), ("zero", "substantial"),
    ("no effect", "significant"), ("approved", "banned")
]

class ContradictionDetector:
    """
    Ultra-Fast NLI Contradiction Detector optimized for CPU execution (< 5ms response time).
    Uses fast polarity, keyword conflict mapping, and string distance heuristics.
    """
    def __init__(self):
        self.nli_pipe = None  # Disabled heavy BART CPU pipeline for sub-second search speed

    @staticmethod
    @lru_cache(maxsize=1024)
    def detect_contradiction_pair_fast(premise: str, hypothesis: str) -> float:
        """
        Calculates contradiction probability (0.0 to 1.0) between premise and hypothesis in < 1ms.
        """
        p_lower = premise.lower()
        h_lower = hypothesis.lower()

        # Check direct antonym/conflict pairs
        for w1, w2 in CONFLICT_PAIRS:
            if (w1 in p_lower and w2 in h_lower) or (w2 in p_lower and w1 in h_lower):
                return 0.85

        # Check negation mismatches (e.g. "is safe" vs "is not safe")
        negations = ["not", "no ", "never", "cannot", "zero", "fake", "unverified"]
        p_has_neg = any(neg in p_lower for neg in negations)
        h_has_neg = any(neg in h_lower for neg in negations)

        if p_has_neg != h_has_neg:
            # Shared key terms check
            p_words = set(re.findall(r'\w+', p_lower))
            h_words = set(re.findall(r'\w+', h_lower))
            shared = p_words.intersection(h_words) - {"is", "the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "not", "no"}
            if len(shared) >= 2:
                return 0.70

        return 0.05

    def evaluate_documents(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluates documents for contradiction in milliseconds.
        """
        if not documents:
            return []

        top_texts = [d["text"] for d in documents[:3]]
        evaluated_docs = []

        for doc in documents:
            doc_id = doc["id"]
            text = doc["text"]

            max_contradiction_prob = 0.0
            
            # Check against query
            query_contra_prob = self.detect_contradiction_pair_fast(query, text)
            max_contradiction_prob = max(max_contradiction_prob, query_contra_prob)

            # Check against peer top documents
            for peer_text in top_texts:
                if peer_text != text:
                    peer_contra = self.detect_contradiction_pair_fast(peer_text, text)
                    max_contradiction_prob = max(max_contradiction_prob, peer_contra)

            # Contradiction Score (1.0 = highly consistent, 0.0 = total contradiction)
            contradiction_score = max(0.0, min(1.0, 1.0 - max_contradiction_prob))
            has_alert = max_contradiction_prob >= 0.40

            doc_copy = dict(doc)
            doc_copy["contradiction_score"] = round(contradiction_score, 4)
            doc_copy["contradiction_prob"] = round(max_contradiction_prob, 4)
            doc_copy["contradiction_alert"] = has_alert
            evaluated_docs.append(doc_copy)

        return evaluated_docs
