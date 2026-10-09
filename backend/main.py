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
from backend.live_knowledge import get_live_evidence_for_query

# Load environment variables
load_dotenv()

app = FastAPI(
    title="TrustRank Reliable Semantic Search API",
    description="Jointly evaluates relevance, source reliability, freshness, contradiction, and evidence strength.",
    version="2.0.0"
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

USER_FEEDBACK_STORE: Dict[str, Dict[str, int]] = {}

@app.on_event("startup")
def startup_event():
    seed_data_path = os.path.join(os.path.dirname(__file__), "sample_data.json")
    if os.path.exists(seed_data_path):
        try:
            with open(seed_data_path, "r", encoding="utf-8") as f:
                documents = json.load(f)
            retriever.index_documents(documents)
            print(f"[FastAPI] Successfully indexed {len(documents)} initial corpus documents.")
        except Exception as e:
            print(f"[FastAPI] Error seeding default data: {e}")

class SearchRequest(BaseModel):
    query: str = Field(..., example="Is cancer curable?")
    top_k: Optional[int] = Field(10, ge=1, le=50)
    freshness_threshold: Optional[float] = Field(0.0, ge=0.0, le=1.0)
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

class FeedbackRequest(BaseModel):
    doc_id: str
    vote: str = Field(..., example="trustworthy")

def generate_citations(source_name: str, text_snippet: str, pub_date: str) -> Dict[str, str]:
    year = pub_date[:4] if pub_date and len(pub_date) >= 4 else "2026"
    title_short = text_snippet[:60] + "..." if len(text_snippet) > 60 else text_snippet
    
    apa = f"{source_name}. ({year}). {title_short} TrustRank Corpus Repository."
    bibtex = f"@article{{{source_name.lower().replace(' ', '_')[:20]}_{year},\n  author = {{{source_name}}},\n  title = {{{title_short}}},\n  year = {{{year}}},\n  journal = {{TrustRank Verified Search}}\n}}"
    return {"apa": apa, "bibtex": bibtex}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TrustRank Semantic Search Backend",
        "chroma_status": "connected"
    }

@app.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    doc_id = req.doc_id
    if doc_id not in USER_FEEDBACK_STORE:
        USER_FEEDBACK_STORE[doc_id] = {"trustworthy": 0, "disputed": 0}

    if req.vote.lower() == "trustworthy":
        USER_FEEDBACK_STORE[doc_id]["trustworthy"] += 1
    elif req.vote.lower() == "disputed":
        USER_FEEDBACK_STORE[doc_id]["disputed"] += 1

    return {
        "message": f"Feedback recorded for {doc_id}",
        "stats": USER_FEEDBACK_STORE[doc_id]
    }

@app.post("/seed")
def seed_documents(req: Optional[DocumentIngestRequest] = None):
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
    Executes 5-dimension TrustRank Search Pipeline with real-time factual knowledge retrieval.
    """
    start_time = time.time()
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    top_k = req.top_k or 10
    freshness_thresh = req.freshness_threshold if req.freshness_threshold is not None else 0.0

    raw_w = req.weights or {}
    w = {
        "w_sem": raw_w.get("w_sem", raw_w.get("wRel", 0.25)),
        "w_rel": raw_w.get("w_rel", raw_w.get("wSup", 0.20)),
        "w_fresh": raw_w.get("w_fresh", raw_w.get("wFresh", 0.15)),
        "w_con": raw_w.get("w_con", raw_w.get("wCon", 0.20)),
        "w_evid": raw_w.get("w_evid", raw_w.get("wEvi", 0.20))
    }

    # 1. Fetch real-time live knowledge from Wikipedia / DuckDuckGo / LLM for this exact query
    live_docs = get_live_evidence_for_query(req.query)
    
    # 2. Retrieve candidates from local index
    local_retrieved = retriever.search(query=req.query, top_k=top_k * 2)

    # Combine live topic knowledge + relevant local documents
    combined_docs = []
    seen_texts = set()

    # Priority to genuinely retrieved live knowledge for the query
    for d in live_docs:
        t_key = d["text"][:50].lower()
        if t_key not in seen_texts:
            seen_texts.add(t_key)
            combined_docs.append(d)

    for d in local_retrieved:
        t_key = d["text"][:50].lower()
        # Only include local docs if they have meaningful similarity to this query (> 0.30)
        if t_key not in seen_texts and d.get("semantic_score", 0.0) >= 0.30:
            seen_texts.add(t_key)
            combined_docs.append(d)

    # If still empty (e.g. offline and no matches), take top local docs
    if not combined_docs:
        combined_docs = local_retrieved

    total_candidates = len(combined_docs)

    # 3. Calculate dense & lexical relevance score for each doc against query
    for doc in combined_docs:
        # Re-verify semantic similarity with sentence transformer
        query_vec = retriever.encode_query_cached(req.query)
        doc_vec = retriever.model.encode(doc["text"], normalize_embeddings=True)
        import numpy as np
        sim = float(max(0.0, min(1.0, np.dot(query_vec, doc_vec))))
        doc["semantic_score"] = round(sim, 4)
        doc["dense_score"] = round(sim, 4)

    # 4. Freshness Filtering & Scoring
    fresh_docs = freshness_filter.filter_and_score(combined_docs, threshold=freshness_thresh)

    # 5. Reliability & Evidence Scoring
    scored_docs = []
    for doc in fresh_docs:
        rel_data = reliability_scorer.score(doc, doc.get("semantic_score", 0.0))
        evid_data = evidence_scorer.score(doc)

        fb = USER_FEEDBACK_STORE.get(doc["id"], {"trustworthy": 0, "disputed": 0})
        user_boost = (fb["trustworthy"] * 0.05) - (fb["disputed"] * 0.08)
        adj_rel = min(1.0, max(0.0, rel_data["reliability_score"] + user_boost))

        merged_doc = dict(doc)
        merged_doc["reliability_score"] = adj_rel
        merged_doc["evidence_score"] = evid_data["evidence_score"]
        merged_doc["evidence_quality"] = evid_data["evidence_quality"]
        merged_doc["recency"] = evid_data["recency"]
        merged_doc["feedback_stats"] = fb
        scored_docs.append(merged_doc)

    # 6. Contradiction Detection
    nli_evaluated_docs = contradiction_detector.evaluate_documents(req.query, scored_docs)

    # 7. Composite 5-Dimensional Ranking
    final_ranked_results = composite_ranker.rank(nli_evaluated_docs, custom_weights=w)
    final_results = final_ranked_results[:top_k]

    # Format output items cleanly for JavaScript frontend
    formatted_results = []
    total_composite_sum = 0
    flagged_count = 0
    source_counts = {}

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

        source_counts[cat_type] = source_counts.get(cat_type, 0) + 1

        pub_date = doc.get("timestamp", "")
        if pub_date and "T" in pub_date:
            pub_date = pub_date.split("T")[0]

        has_alert = doc.get("contradiction_alert", False)
        if has_alert:
            flagged_count += 1

        contra_prob = doc.get("contradiction_prob", 0.0)
        contra_details = None
        if has_alert:
            contra_details = f"Conflict risk detected ({int(contra_prob*100)}%). Claim contradicts empirical/consensus evidence."

        comp_score = doc.get("trust_rank_score", 0.0)
        total_composite_sum += comp_score

        explanation = f"Evaluated with semantic relevance {int(breakdown.get('relevance',0)*100)}%, source reliability {int(breakdown.get('reliability',0)*100)}%, and GRADE evidence {int(breakdown.get('evidence_strength',0)*100)}%."

        citations = generate_citations(doc.get("source", "Unknown"), doc.get("text", ""), pub_date)

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
                "composite": comp_score
            },
            "trust_rank_score": comp_score,
            "dimension_breakdown": breakdown,
            "contradiction_alert": has_alert,
            "contradictionAlert": has_alert,
            "contradiction_details": contra_details,
            "contradictionDetails": contra_details,
            "explanation": explanation,
            "citations": citations,
            "feedback": doc.get("feedback_stats", {"trustworthy": 0, "disputed": 0})
        })

    avg_trust = (total_composite_sum / len(final_results)) if final_results else 0.0
    overall_trust_index = int(avg_trust * 100)

    if flagged_count == 0 and overall_trust_index >= 75:
        consensus_status = "High Evidence Consensus ✅"
    elif flagged_count > 0:
        consensus_status = "Contested Claims / Conflict Flagged ⚠️"
    else:
        consensus_status = "Moderate / Mixed Evidence ℹ️"

    query_time_ms = int((time.time() - start_time) * 1000)

    return {
        "query": req.query,
        "total_candidates": total_candidates,
        "total_results": len(formatted_results),
        "query_time_ms": query_time_ms,
        "analytics": {
            "overall_trust_index": overall_trust_index,
            "consensus_status": consensus_status,
            "flagged_contradictions": flagged_count,
            "source_distribution": source_counts
        },
        "results": formatted_results
    }

# Mount static subdirectories
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
