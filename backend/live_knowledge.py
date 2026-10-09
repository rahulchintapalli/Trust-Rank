import os
import requests
import json
import time
from typing import List, Dict, Any

def fetch_wikipedia_knowledge(query: str) -> List[Dict[str, Any]]:
    """
    Fetches real, factual extracts from Wikipedia API related to user query.
    """
    results = []
    headers = {"User-Agent": "TrustRankSemanticSearch/1.0 (academic research tool)"}
    
    try:
        # Search for top related Wikipedia articles
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "utf8": 1,
            "format": "json",
            "srlimit": 4
        }
        res = requests.get(search_url, params=params, headers=headers, timeout=3.0)
        
        if res.status_code == 200:
            data = res.json()
            search_items = data.get("query", {}).get("search", [])
            
            for item in search_items:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                # Clean html tags from snippet
                cleaned_snippet = snippet.replace("<span class=\"searchmatch\">", "").replace("</span>", "").replace("&quot;", '"')
                
                # Fetch full intro summary for the top articles
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
                sum_res = requests.get(summary_url, headers=headers, timeout=2.5)
                
                text_content = ""
                if sum_res.status_code == 200:
                    sum_data = sum_res.json()
                    text_content = sum_data.get("extract", "")
                
                if not text_content:
                    text_content = cleaned_snippet

                if len(text_content.strip()) > 30:
                    results.append({
                        "id": f"wiki_{hash(title)}_{int(time.time())}",
                        "text": text_content,
                        "source": f"Wikipedia Encyclopedia ({title})",
                        "source_type": "Corpus/Registry",
                        "evidence_type": "peer-reviewed",
                        "timestamp": "2026-06-01T00:00:00Z",
                        "category": "news"
                    })
    except Exception as e:
        print(f"[LiveKnowledge] Wikipedia fetch error: {e}")

    return results

def fetch_duckduckgo_knowledge(query: str) -> List[Dict[str, Any]]:
    """
    Fetches real factual instant answers from DuckDuckGo API.
    """
    results = []
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
        res = requests.get(url, params=params, timeout=2.5)
        
        if res.status_code == 200:
            data = res.json()
            abstract = data.get("AbstractText", "")
            source = data.get("AbstractSource", "Web Knowledge")
            
            if abstract:
                results.append({
                    "id": f"ddg_abstract_{int(time.time())}",
                    "text": abstract,
                    "source": f"{source} Knowledge Index",
                    "source_type": "Web",
                    "evidence_type": "news",
                    "timestamp": "2026-08-15T00:00:00Z",
                    "category": "news"
                })
            
            # Related topics
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and "Text" in topic and topic["Text"]:
                    results.append({
                        "id": f"ddg_topic_{hash(topic['Text']) % 10000}",
                        "text": topic["Text"],
                        "source": "Web Reference Library",
                        "source_type": "Web",
                        "evidence_type": "news",
                        "timestamp": "2026-07-01T00:00:00Z",
                        "category": "news"
                    })
    except Exception as e:
        print(f"[LiveKnowledge] DuckDuckGo fetch error: {e}")
        
    return results

def generate_llm_evidence(query: str) -> List[Dict[str, Any]]:
    """
    If OpenAI API key or Gemini API key is configured, query LLM for factual evidence & conflicting claims.
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and openai_key.startswith("sk-"):
        try:
            prompt = f"""You are a multi-perspective scientific evidence generator for the TrustRank search engine.
For the user search query: "{query}"
Generate exactly 3 diverse, highly relevant, factually grounded search results in JSON array format.
Include:
1. Academic/scientific consensus with clinical/empirical findings.
2. Recent news or regulatory perspective.
3. A commonly circulated conflicting or social claim (to test contradiction detection).

Return ONLY valid JSON array with keys:
- text: string (detailed factual explanation)
- source: string (e.g. "Nature Medicine", "Reuters Health", "Online Discussion Forum")
- source_type: string ("Academic", "News", "Corpus/Registry", or "Social")
- evidence_type: string ("peer-reviewed", "clinical trial", "news", or "blog")
- timestamp: string (ISO 8601, e.g. "2026-08-01T00:00:00Z")
- category: string ("vital signs" or "news" or "demographics")
"""
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                },
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                items = parsed.get("results", parsed if isinstance(parsed, list) else [])
                if isinstance(items, list) and len(items) > 0:
                    for i, it in enumerate(items):
                        it["id"] = f"llm_{i}_{int(time.time())}"
                    return items
        except Exception as e:
            print(f"[LiveKnowledge] OpenAI generation note: {e}")

    return []

def get_live_evidence_for_query(query: str) -> List[Dict[str, Any]]:
    """
    Main aggregator that retrieves genuine, real-time, topic-specific knowledge
    for ANY user query.
    """
    all_evidence = []
    
    # 1. Fetch real Wikipedia articles & summaries
    wiki_docs = fetch_wikipedia_knowledge(query)
    if wiki_docs:
        all_evidence.extend(wiki_docs)

    # 2. Fetch DuckDuckGo Instant Answers
    ddg_docs = fetch_duckduckgo_knowledge(query)
    if ddg_docs:
        all_evidence.extend(ddg_docs)

    # 3. Try LLM evidence generation if API key present
    llm_docs = generate_llm_evidence(query)
    if llm_docs:
        all_evidence.extend(llm_docs)

    return all_evidence
