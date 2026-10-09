# TrustRank Project Roadmap

## Phase 1: Environment Setup & Data Pipeline
- [x] Define requirements in `.gsd/SPEC.md`
- [x] Create `requirements.txt` and `.env.example`
- [x] Create sample dataset (`sample_data.json`) for seeding ChromaDB

## Phase 2: Core Scoring & Retrieval Modules
- [x] Implement `semantic_retrieval.py` (Dense ChromaDB + BM25 hybrid search)
- [x] Implement `reliability_scorer.py` (CATS & Source Type trust scoring)
- [x] Implement `freshness_filter.py` (Fact-level decay & validity filtering)
- [x] Implement `contradiction_detector.py` (BART-large-MNLI & ContraChecker)
- [x] Implement `evidence_scorer.py` (ET-RAG quality & recency metrics)
- [x] Implement `composite_ranker.py` (5-dimensional weighted fusion)

## Phase 3: FastAPI Backend & Streamlit Frontend
- [x] Implement `main.py` FastAPI app (`/search`, `/health`, `/seed`)
- [x] Implement `app.py` Streamlit premium UI
- [x] Write `README.md` and Docker Compose configuration (`docker-compose.yml`, Dockerfiles)

## Phase 4: Verification & Final Polish
- [x] Verify core search and 5-dimension scoring end-to-end
- [x] Confirm UI breakdown and contradiction alerts render correctly
