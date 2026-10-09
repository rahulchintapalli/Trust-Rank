---
title: TrustRank Reliable Search
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---

# TrustRank: Reliable Semantic Search System 🛡️

TrustRank is a Reliable Semantic Search web application featuring a modern HTML5/CSS3/JavaScript frontend and a FastAPI backend that jointly evaluates five critical dimensions for information retrieval and ranking:

1. **Relevance (Semantic Retrieval):** Hybrid dense (`BAAI/bge-m3` / `all-MiniLM-L6-v2` via ChromaDB) + lexical (`BM25Okapi`) search.
2. **Source Reliability:** Static source category base weights combined with dynamic trust scoring via `CATS` (`cats-scoring`) and `Prism API`.
3. **Freshness:** Temporal validity with domain-specific exponential decay math ($\text{decay}(t) = \exp(-\beta \cdot \Delta t)$).
4. **Contradiction Detection:** Natural Language Inference (`facebook/bart-large-mnli` & fast polarity/negation evaluation) and `ContraChecker`.
5. **Evidence Strength:** Composite ET-RAG quality scoring combining Cosine Similarity, GRADE Evidence Hierarchy, and Document Recency.

---

## 🏗️ Project Architecture

```
code flayer/
├── frontend/
│   ├── index.html          # Main HTML5 page
│   ├── css/
│   │   ├── style.css       # Global design tokens, dark mode & reset
│   │   ├── components.css  # Search bar, result cards, badges & SVG gauges
│   │   └── responsive.css  # Mobile and tablet grid breakpoints
│   ├── js/
│   │   ├── app.js          # Main UI controller & state management
│   │   ├── api.js          # Fetch client calls to POST /search
│   │   ├── render.js       # DOM card builder & skeleton loaders
│   │   └── scoreViz.js     # Score bar & SVG circular progress animators
│   └── assets/
│       └── logo.svg        # TrustRank shield logo
├── backend/
│   ├── __init__.py
│   ├── main.py               # FastAPI server with CORS & static file mounting
│   ├── semantic_retrieval.py # In-memory matrix dot-product + ChromaDB hybrid search
│   ├── reliability_scorer.py # Base weights + CATS/Prism dynamic source trust
│   ├── freshness_filter.py   # Exponential temporal decay math & threshold filtering
│   ├── contradiction_detector.py # Sub-second fast NLI contradiction evaluator
│   ├── evidence_scorer.py    # ET-RAG composite score (Similarity + GRADE + Recency)
│   ├── composite_ranker.py   # 5-dimensional weighted fusion ranker
│   └── sample_data.json      # Sample corpus for indexing
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── Dockerfile.fastapi        # Backend container definition
├── docker-compose.yml        # Docker Compose configuration (Port 8000 & 8001)
└── README.md                 # Setup & system documentation
```

---

## 🧮 Mathematical Scoring Formulas

$$S_{\text{TrustRank}} = w_{\text{sem}} \cdot S_{\text{sem}} + w_{\text{rel}} \cdot S_{\text{reliability}} + w_{\text{fresh}} \cdot S_{\text{freshness}} + w_{\text{con}} \cdot S_{\text{contradiction}} + w_{\text{evid}} \cdot S_{\text{evidence}}$$

Default Weights:
- $w_{\text{sem}} = 0.25$ (Semantic Match)
- $w_{\text{rel}} = 0.20$ (Source Reliability)
- $w_{\text{fresh}} = 0.15$ (Temporal Freshness)
- $w_{\text{con}} = 0.20$ (Contradiction Consistency)
- $w_{\text{evid}} = 0.20$ (ET-RAG Evidence Quality)

---

## 🚀 How to Run

### Option 1: Local Python Server

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start FastAPI Backend (serves UI & API together):**
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Open in Browser:**
   Visit **`http://localhost:8000`** (or `http://127.0.0.1:8000`).

---

### Option 2: Docker Compose

```bash
docker-compose up --build
```

Access services:
- **TrustRank Web UI:** `http://localhost:8000`
- **FastAPI OpenAPI Docs:** `http://localhost:8000/docs`
- **ChromaDB Vector Store:** `http://localhost:8001`
