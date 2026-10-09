import os
import json
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from backend.semantic_retrieval import SemanticRetriever
from backend.reliability_scorer import ReliabilityScorer
from backend.freshness_filter import FreshnessFilter
from backend.contradiction_detector import ContradictionDetector
from backend.evidence_scorer import EvidenceScorer
from backend.composite_ranker import CompositeRanker

# Load environment variables
load_dotenv()

app = FastAPI(
    title="TrustRank Reliable Semantic Search API",
    description="Jointly evaluates relevance, source reliability, freshness, contradiction, and evidence strength.",
    version="1.0.0"
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core scoring modules
retriever = SemanticRetriever(db_path="./chroma_db")
reliability_scorer = ReliabilityScorer()
freshness_filter = FreshnessFilter()
contradiction_detector = ContradictionDetector()
evidence_scorer = EvidenceScorer()
composite_ranker = CompositeRanker()

# Seed default dataset on startup if ChromaDB collection is empty
@app.on_event("startup")
def startup_event():
    seed_data_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
    if os.path.exists(seed_data_path):
        try:
            with open(seed_data_path, "r", encoding="utf-8") as f:
                documents = json.load(f)
            retriever.index_documents(documents)
            print(f"[FastAPI] Successfully initialized ChromaDB with {len(documents)} sample documents.")
        except Exception as e:
            print(f"[FastAPI] Error seeding default data: {e}")

class SearchRequest(BaseModel):
    query: str = Field(..., example="What is the clinical efficacy and safety of Treatment X?")
    top_k: Optional[int] = Field(10, ge=1, le=50)
    freshness_threshold: Optional[float] = Field(0.3, ge=0.0, le=1.0)
    weights: Optional[Dict[str, float]] = Field(
        default={
            "w_sem": 0.25,
            "w_rel": 0.20,
            "w_fresh": 0.15,
            "w_con": 0.20,
            "w_evid": 0.20
        }
    )

class DocumentIngestRequest(BaseModel):
    documents: List[Dict[str, Any]]

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TrustRank Semantic Search Backend",
        "chroma_status": "connected"
    }

@app.post("/seed")
def seed_documents(req: Optional[DocumentIngestRequest] = None):
    """Seed documents into vector database."""
    if req and req.documents:
        docs = req.documents
    else:
        seed_data_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
        with open(seed_data_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

    retriever.index_documents(docs)
    return {"message": f"Successfully indexed {len(docs)} documents."}

@app.post("/search")
def search_documents(req: SearchRequest):
    """
    Executes the 5-dimension TrustRank Search Pipeline:
    Returns structured results with relevance, reliability, freshness, contradiction, evidence & composite scores.
    """
    start_time = time.time()
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    top_k = req.top_k or 10
    freshness_thresh = req.freshness_threshold if req.freshness_threshold is not None else 0.3

    raw_w = req.weights or {}
    w = {
        "w_sem": raw_w.get("w_sem", raw_w.get("wRel", 0.25)),
        "w_rel": raw_w.get("w_rel", raw_w.get("wSup", 0.20)),
        "w_fresh": raw_w.get("w_fresh", raw_w.get("wFresh", 0.15)),
        "w_con": raw_w.get("w_con", raw_w.get("wCon", 0.20)),
        "w_evid": raw_w.get("w_evid", raw_w.get("wEvi", 0.20))
    }

    # 1. Semantic Retrieval
    retrieved_docs = retriever.search(query=req.query, top_k=top_k * 2)
    total_candidates = len(retrieved_docs)

    if not retrieved_docs:
        query_time_ms = int((time.time() - start_time) * 1000)
        return {
            "query": req.query,
            "total_candidates": 0,
            "query_time_ms": query_time_ms,
            "results": []
        }

    # 2. Freshness Filtering
    fresh_docs = freshness_filter.filter_and_score(retrieved_docs, threshold=freshness_thresh)

    # 3. Reliability & Evidence Scoring
    scored_docs = []
    for doc in fresh_docs:
        rel_data = reliability_scorer.score(doc, doc.get("semantic_score", 0.0))
        evid_data = evidence_scorer.score(doc)

        merged_doc = dict(doc)
        merged_doc["reliability_score"] = rel_data["reliability_score"]
        merged_doc["evidence_score"] = evid_data["evidence_score"]
        merged_doc["evidence_quality"] = evid_data["evidence_quality"]
        merged_doc["recency"] = evid_data["recency"]
        scored_docs.append(merged_doc)

    # 4. Contradiction Detection
    nli_evaluated_docs = contradiction_detector.evaluate_documents(req.query, scored_docs)

    # 5. Composite Ranking
    final_ranked_results = composite_ranker.rank(nli_evaluated_docs, custom_weights=w)
    final_results = final_ranked_results[:top_k]

    # Format output items cleanly for JavaScript frontend
    formatted_results = []
    for doc in final_results:
        breakdown = doc.get("dimension_breakdown", {})
        s_type = doc.get("source_type", "web").lower()
        if "academic" in s_type or "journal" in s_type:
            cat_type = "academic"
        elif "news" in s_type:
            cat_type = "news"
        elif "social" in s_type or "blog" in s_type:
            cat_type = "social"
        elif "corpus" in s_type or "registry" in s_type:
            cat_type = "corpus"
        else:
            cat_type = "web"

        pub_date = doc.get("timestamp", "")
        if pub_date and "T" in pub_date:
            pub_date = pub_date.split("T")[0]

        has_alert = doc.get("contradiction_alert", False)
        contra_prob = doc.get("contradiction_prob", 0.0)

        contra_details = None
        if has_alert:
            contra_details = f"Conflict risk detected ({int(contra_prob*100)}%). Claim contradicts top peer evidence."

        explanation = f"Evaluated with semantic match {int(breakdown.get('relevance',0)*100)}%, source reliability {int(breakdown.get('reliability',0)*100)}%, and GRADE quality {int(breakdown.get('evidence_strength',0)*100)}%."

        formatted_results.append({
            "id": doc.get("id"),
            "text": doc.get("text", ""),
            "source": doc.get("source", "Unknown"),
            "sourceName": doc.get("source", "Unknown"),
            "source_type": cat_type,
            "sourceType": cat_type,
            "published_date": pub_date,
            "publishedDate": pub_date,
            "timestamp": doc.get("timestamp", ""),
            "scores": {
                "relevance": breakdown.get("relevance", 0.0),
                "reliability": breakdown.get("reliability", 0.0),
                "freshness": breakdown.get("freshness", 0.0),
                "contradiction": breakdown.get("contradiction", 0.0),
                "evidence": breakdown.get("evidence_strength", 0.0),
                "composite": doc.get("trust_rank_score", 0.0)
            },
            "trust_rank_score": doc.get("trust_rank_score", 0.0),
            "dimension_breakdown": breakdown,
            "contradiction_alert": has_alert,
            "contradictionAlert": has_alert,
            "contradiction_details": contra_details,
            "contradictionDetails": contra_details,
            "explanation": explanation
        })

    query_time_ms = int((time.time() - start_time) * 1000)

    return {
        "query": req.query,
        "total_candidates": total_candidates,
        "total_results": len(formatted_results),
        "query_time_ms": query_time_ms,
        "results": formatted_results
    }

# Mount static subdirectories for CSS, JS, Assets, and serve HTML at root /
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    assets_dir = os.path.join(frontend_dir, "assets")

    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def serve_frontend():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "TrustRank API active."}
