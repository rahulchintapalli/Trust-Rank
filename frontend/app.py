import os
import json
import requests
import streamlit as st

# Configure Streamlit Page Settings
st.set_page_config(
    page_title="TrustRank - Reliable Semantic Search",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Minimalistic Premium UI
st.markdown("""
<style>
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1A365D 0%, #2B6CB0 50%, #319795 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #4A5568;
        font-size: 1.05rem;
        font-weight: 400;
        margin-bottom: 1.8rem;
    }
    .result-card {
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1.2rem;
        background-color: #FFFFFF;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: all 0.2s ease-in-out;
    }
    .result-card:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 6px;
        margin-right: 0.5rem;
    }
    .badge-green { background-color: #DEF7EC; color: #03543F; border: 1px solid #84E1BC; }
    .badge-amber { background-color: #FEF08A; color: #713F12; border: 1px solid #FDE047; }
    .badge-red { background-color: #FDE8E8; color: #9B1C1C; border: 1px solid #F8B4B4; }
    .badge-source { background-color: #EBF5FF; color: #1E429F; border: 1px solid #A4CAFE; }
    .alert-box {
        background-color: #FDF2F2;
        border-left: 4px solid #F05252;
        color: #9B1C1C;
        padding: 0.8rem 1rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.9rem;
        margin-top: 0.8rem;
        margin-bottom: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Primary backend URLs (IPv4 127.0.0.1 to avoid Windows localhost ::1 mismatch)
PRIMARY_BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Cache local engine in case FastAPI backend server is offline
@st.cache_resource
def get_local_engine():
    try:
        from backend.semantic_retrieval import SemanticRetriever
        from backend.reliability_scorer import ReliabilityScorer
        from backend.freshness_filter import FreshnessFilter
        from backend.contradiction_detector import ContradictionDetector
        from backend.evidence_scorer import EvidenceScorer
        from backend.composite_ranker import CompositeRanker

        retriever = SemanticRetriever(db_path="./chroma_db")
        
        # Seed default sample data if chroma is empty
        seed_path = os.path.join(os.path.dirname(__file__), "..", "backend", "sample_data.json")
        if os.path.exists(seed_path):
            with open(seed_path, "r", encoding="utf-8") as f:
                retriever.index_documents(json.load(f))
                
        return {
            "retriever": retriever,
            "reliability_scorer": ReliabilityScorer(),
            "freshness_filter": FreshnessFilter(),
            "contradiction_detector": ContradictionDetector(),
            "evidence_scorer": EvidenceScorer(),
            "composite_ranker": CompositeRanker()
        }
    except Exception as e:
        print(f"[Streamlit Direct Pipeline] Initialization note: {e}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def execute_local_search(query: str, top_k: int, freshness_thresh: float, weights: dict) -> dict:
    engine = get_local_engine()
    if not engine:
        return {"total_results": 0, "results": []}

    retrieved_docs = engine["retriever"].search(query=query, top_k=top_k * 2)
    fresh_docs = engine["freshness_filter"].filter_and_score(retrieved_docs, threshold=freshness_thresh)

    scored_docs = []
    for doc in fresh_docs:
        rel_data = engine["reliability_scorer"].score(doc, doc.get("semantic_score", 0.0))
        evid_data = engine["evidence_scorer"].score(doc)

        merged_doc = dict(doc)
        merged_doc["reliability_score"] = rel_data["reliability_score"]
        merged_doc["evidence_score"] = evid_data["evidence_score"]
        merged_doc["evidence_quality"] = evid_data["evidence_quality"]
        merged_doc["recency"] = evid_data["recency"]
        scored_docs.append(merged_doc)

    nli_evaluated_docs = engine["contradiction_detector"].evaluate_documents(query, scored_docs)
    final_ranked_results = engine["composite_ranker"].rank(nli_evaluated_docs, custom_weights=weights)

    return {
        "query": query,
        "total_results": len(final_ranked_results[:top_k]),
        "results": final_ranked_results[:top_k]
    }

# Header Section
st.markdown("<div class='main-title'>TrustRank 🛡️</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Reliable Semantic Search evaluating Relevance, Source Reliability, Freshness, Contradiction & Evidence Strength</div>", unsafe_allow_html=True)

# Sidebar Controls
st.sidebar.header("⚙️ Evaluation Weights")
st.sidebar.markdown("Adjust the 5-dimension fusion weights:")

w_sem = st.sidebar.slider("Semantic Relevance ($S_{sem}$)", 0.0, 1.0, 0.25, 0.05)
w_rel = st.sidebar.slider("Source Reliability ($S_{reliability}$)", 0.0, 1.0, 0.20, 0.05)
w_fresh = st.sidebar.slider("Freshness ($S_{freshness}$)", 0.0, 1.0, 0.15, 0.05)
w_con = st.sidebar.slider("Contradiction Consistency ($S_{contradiction}$)", 0.0, 1.0, 0.20, 0.05)
w_evid = st.sidebar.slider("Evidence Strength ($S_{evidence}$)", 0.0, 1.0, 0.20, 0.05)

st.sidebar.divider()
st.sidebar.header("⏳ Freshness Filter")
freshness_thresh = st.sidebar.slider("Minimum Freshness Cutoff", 0.0, 1.0, 0.30, 0.05)

st.sidebar.divider()
st.sidebar.header("🔍 Example Queries")
preset_query = st.sidebar.selectbox(
    "Or select a sample query:",
    [
        "Custom...",
        "What is the clinical efficacy and mortality rate of Treatment X?",
        "What are global population life expectancy demographics?",
        "Quantum computing error-corrected qubit logical operations breakthrough"
    ]
)

# Search Input
default_input = "" if preset_query == "Custom..." else preset_query
query_input = st.text_input("Enter your search query:", value=default_input, placeholder="e.g. Is Treatment X safe and effective for patients?")

col_btn, col_info = st.columns([1, 4])
with col_btn:
    search_clicked = st.button("Search TrustRank", type="primary", use_container_width=True)

def get_badge_class(score: float) -> str:
    if score >= 0.75:
        return "badge-green"
    elif score >= 0.50:
        return "badge-amber"
    else:
        return "badge-red"

# Execution Logic
if search_clicked and query_input:
    payload = {
        "query": query_input,
        "top_k": 5,
        "freshness_threshold": freshness_thresh,
        "weights": {
            "w_sem": w_sem,
            "w_rel": w_rel,
            "w_fresh": w_fresh,
            "w_con": w_con,
            "w_evid": w_evid
        }
    }

    results = []
    total = 0

    with st.spinner("Analyzing semantic relevance, source credibility, NLI contradictions & evidence strength..."):
        # Try HTTP request to FastAPI backend (trying 127.0.0.1 and localhost)
        backend_urls = [PRIMARY_BACKEND_URL, "http://localhost:8000"]
        backend_success = False

        for url in backend_urls:
            try:
                resp = requests.post(f"{url}/search", json=payload, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    total = data.get("total_results", 0)
                    backend_success = True
                    break
            except Exception:
                continue

        # If FastAPI backend service is not running, run in-process search directly!
        if not backend_success:
            data = execute_local_search(query_input, 5, freshness_thresh, payload["weights"])
            results = data.get("results", [])
            total = data.get("total_results", 0)

        st.markdown(f"### Found {total} Verified Results")

        if not results:
            st.warning("No documents met the freshness or search criteria. Try lowering the freshness threshold.")

        for idx, item in enumerate(results, 1):
            final_score = item.get("trust_rank_score", 0.0)
            text = item.get("text", "")
            source = item.get("source", "Unknown")
            source_type = item.get("source_type", "Web")
            evidence_type = item.get("evidence_type", "blog")
            timestamp = item.get("timestamp", "N/A")
            has_alert = item.get("contradiction_alert", False)
            breakdown = item.get("dimension_breakdown", {})

            overall_badge = get_badge_class(final_score)

            # Card layout
            st.markdown(f"""
            <div class="result-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <div>
                        <span class="badge badge-source">🏢 {source} ({source_type})</span>
                        <span class="badge badge-source">📑 {evidence_type}</span>
                        <span style="font-size: 0.8rem; color: #718096;">🕒 {timestamp[:10]}</span>
                    </div>
                    <div>
                        <span class="badge {overall_badge}" style="font-size: 0.95rem; padding: 0.3rem 0.8rem;">
                            TrustRank Score: <b>{final_score:.2f}</b>
                        </span>
                    </div>
                </div>
                <p style="font-size: 1.05rem; color: #2D3748; margin-top: 0.6rem; margin-bottom: 0.6rem;">{text}</p>
            """, unsafe_allow_html=True)

            if has_alert:
                st.markdown("""
                <div class="alert-box">
                    ⚠️ CONTRADICTION WARNING: This claim directly conflicts with top medical/consensus evidence.
                </div>
                """, unsafe_allow_html=True)

            # Expandable "Why this result?" panel
            with st.expander(f"🔍 Why this result? (Score Breakdown for Result #{idx})"):
                c1, c2, c3, c4, c5 = st.columns(5)

                s_relevance = breakdown.get("relevance", 0.0)
                s_reliability = breakdown.get("reliability", 0.0)
                s_freshness = breakdown.get("freshness", 0.0)
                s_contradiction = breakdown.get("contradiction", 0.0)
                s_evidence = breakdown.get("evidence_strength", 0.0)

                c1.metric("Relevance", f"{s_relevance:.2f}", delta=f"wt: {w_sem:.2f}")
                c2.metric("Reliability", f"{s_reliability:.2f}", delta=f"wt: {w_rel:.2f}")
                c3.metric("Freshness", f"{s_freshness:.2f}", delta=f"wt: {w_fresh:.2f}")
                c4.metric("Consistency", f"{s_contradiction:.2f}", delta=f"wt: {w_con:.2f}")
                c5.metric("Evidence", f"{s_evidence:.2f}", delta=f"wt: {w_evid:.2f}")

                st.progress(s_relevance, text=f"Semantic Match: {s_relevance * 100:.1f}%")
                st.progress(s_reliability, text=f"Source Credibility: {s_reliability * 100:.1f}%")
                st.progress(s_freshness, text=f"Temporal Validity: {s_freshness * 100:.1f}%")
                st.progress(s_contradiction, text=f"Non-Contradiction Confidence: {s_contradiction * 100:.1f}%")
                st.progress(s_evidence, text=f"GRADE Evidence Quality: {s_evidence * 100:.1f}%")

            st.markdown("</div>", unsafe_allow_html=True)
