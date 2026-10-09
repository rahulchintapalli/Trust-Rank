# TrustRank: Reliable Semantic Search System Specification

**Status:** FINALIZED

## 1. Overview
TrustRank is a Reliable Semantic Search web application that jointly evaluates five critical dimensions for information retrieval and ranking:
1. **Relevance (Semantic Retrieval):** Hybrid dense (BGE-M3 / ChromaDB) + lexical (BM25) search.
2. **Source Reliability:** Source-type base weights augmented with dynamic trust scoring (CATS / Prism API).
3. **Freshness:** Temporal validity decay based on domain-specific half-lives ($exp(-\beta \cdot \Delta t)$).
4. **Contradiction Detection:** Natural Language Inference (BART-Large-MNLI & ContraChecker) to penalize contradictory claims.
5. **Evidence Strength:** Composite ET-RAG quality scoring (Similarity, GRADE evidence hierarchy, Recency).

---

## 2. System Architecture

```
[ Streamlit UI (Port 8501) ]
            │ (HTTP POST /search)
            ▼
 [ FastAPI Backend (Port 8000) ]
            │
            ├─► 1. Semantic Retrieval (ChromaDB + RankBM25)
            ├─► 2. Reliability Scorer (CATS / Source Type Weights)
            ├─► 3. Freshness Filter (Exponential Decay)
            ├─► 4. Contradiction Detector (BART-Large-MNLI NLI)
            ├─► 5. Evidence Scorer (ET-RAG GRADE + Recency)
            └─► 6. Composite Ranker (Weighted Fusion)
```

---

## 3. Dimension Scoring Math & Formulas

1. **Relevance Score ($S_{sem}$):**
   $$S_{sem} = \alpha \cdot \text{Sim}_{\text{dense}} + (1 - \alpha) \cdot \text{Score}_{\text{BM25\_norm}}$$

2. **Source Reliability ($S_{reliability}$):**
   - Base Weights: Corpus/Registry (0.90), Academic (0.88), Web (0.72), Social (0.72), News (0.68)
   - Dynamic Scoring via CATS / Prism API:
     $$S_{reliability} = S_{sem} \times \text{TrustScore}_{\text{CATS}}$$

3. **Freshness Score ($S_{freshness}$):**
   $$\text{Decay}(t) = \exp(-\beta \cdot \Delta t)$$
   - Decay rates ($\beta$): Vital signs ($0.05$), News ($0.01$), Demographics ($0.0001$).
   - Threshold filtering: Exclude documents with freshness $< 0.30$.

4. **Contradiction Score ($S_{contradiction}$):**
   - Evaluated via NLI pair probabilities between query/top candidate context and retrieved evidence chunk:
     $$S_{contradiction} = 1.0 - P(\text{contradiction})$$

5. **Evidence Score ($S_{evidence}$):**
   $$S_{evidence} = 0.50 \cdot \text{CosineSim} + 0.30 \cdot \text{EvidenceQuality} + 0.20 \cdot \text{Recency}$$
   - Evidence Quality: Peer-reviewed (1.0), Clinical trial (0.9), News (0.5), Blog (0.2).

6. **Composite Score ($S_{final}$):**
   $$S_{final} = 0.25 \cdot S_{sem} + 0.20 \cdot S_{reliability} + 0.15 \cdot S_{freshness} + 0.20 \cdot S_{contradiction} + 0.20 \cdot S_{evidence}$$

---

## 4. UI Requirements
- Minimalist, premium dark/light mode capable Streamlit frontend.
- Score breakdown badges (Color coded: Green $\ge 0.75$, Amber $0.50 - 0.74$, Red $< 0.50$).
- Contradiction risk alerts highlighted in red banners.
- Interactive "Why this result?" breakdown drawer for explainability.
