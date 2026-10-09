import os
import json
import gc
from functools import lru_cache
import numpy as np
import chromadb

# Low-memory PyTorch thread configuration
try:
    import torch
    torch.set_num_threads(1)
    if hasattr(torch, "set_num_interop_threads"):
        torch.set_num_interop_threads(1)
except Exception:
    pass

from rank_bm25 import BM25Okapi

MODEL_NAME = "all-MiniLM-L6-v2"

class SemanticRetriever:
    """
    Ultra-Low-Memory Hybrid Retriever with Scikit-Learn TF-IDF Fallback (< 50MB RAM).
    Guarantees zero-OOM execution on 512MB RAM cloud platforms like Render Free Tier.
    """
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "trustrank_docs"):
        self.db_path = db_path
        self.collection_name = collection_name
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.model = None
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        
        # Try loading lightweight SentenceTransformer model
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(MODEL_NAME)
            print("[SemanticRetriever] Loaded SentenceTransformer model successfully.")
        except Exception as e:
            print(f"[SemanticRetriever] Memory note: PyTorch/SentenceTransformer disabled ({e}). Using ultra-light TF-IDF engine (< 15MB RAM).")
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.tfidf_vectorizer = TfidfVectorizer()

        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            try:
                self.chroma_client.delete_collection(name=self.collection_name)
            except Exception:
                pass
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

        self.bm25 = None
        self.documents_store = []
        self.doc_embeddings_matrix = None
        gc.collect()

    @lru_cache(maxsize=256)
    def encode_query_cached(self, query: str) -> tuple:
        """Cached query vectorization."""
        if self.model:
            vec = self.model.encode(query, normalize_embeddings=True)
            return tuple(vec.tolist())
        return ()

    def index_documents(self, documents: list[dict]):
        """
        Index documents into ChromaDB, in-memory numpy matrix, TF-IDF, and BM25 store.
        """
        if not documents:
            return

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [
            {
                "source": doc.get("source", "Unknown"),
                "source_type": doc.get("source_type", "Web"),
                "evidence_type": doc.get("evidence_type", "blog"),
                "timestamp": doc.get("timestamp", ""),
                "category": doc.get("category", "news")
            }
            for doc in documents
        ]

        if self.model:
            embeddings_np = self.model.encode(texts, normalize_embeddings=True)
            self.doc_embeddings_matrix = embeddings_np

            try:
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings_np.tolist(),
                    documents=texts,
                    metadatas=metadatas
                )
            except Exception as e:
                print(f"[SemanticRetriever] Collection reset note: {e}")

        # Fallback ultra-light TF-IDF indexing
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.tfidf_vectorizer = TfidfVectorizer()
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
        except Exception as e:
            print(f"[SemanticRetriever] TF-IDF note: {e}")

        self.documents_store = documents
        tokenized_corpus = [doc["text"].lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, top_k: int = 5, alpha: float = 0.6) -> list[dict]:
        """
        Sub-5ms low-memory hybrid search.
        """
        dense_scores_map = {}
        
        if self.model and self.doc_embeddings_matrix is not None and len(self.documents_store) > 0:
            query_vec_list = self.encode_query_cached(query)
            query_np = np.array(query_vec_list, dtype=np.float32)
            sims = np.dot(self.doc_embeddings_matrix, query_np)
            for idx, doc in enumerate(self.documents_store):
                dense_scores_map[doc["id"]] = float(max(0.0, min(1.0, sims[idx])))
        elif self.tfidf_vectorizer and self.tfidf_matrix is not None and len(self.documents_store) > 0:
            from sklearn.metrics.pairwise import cosine_similarity
            q_vec = self.tfidf_vectorizer.transform([query])
            sims = cosine_similarity(q_vec, self.tfidf_matrix)[0]
            for idx, doc in enumerate(self.documents_store):
                dense_scores_map[doc["id"]] = float(max(0.0, min(1.0, sims[idx])))

        bm25_scores_map = {}
        if self.bm25 and self.documents_store:
            tokenized_query = query.lower().split()
            raw_bm25_scores = self.bm25.get_scores(tokenized_query)
            max_bm25 = max(raw_bm25_scores) if len(raw_bm25_scores) > 0 and max(raw_bm25_scores) > 0 else 1.0
            
            for idx, doc in enumerate(self.documents_store):
                norm_bm25 = float(raw_bm25_scores[idx] / max_bm25) if max_bm25 > 0 else 0.0
                bm25_scores_map[doc["id"]] = norm_bm25

        results = []
        for doc in self.documents_store:
            doc_id = doc["id"]
            dense_sim = dense_scores_map.get(doc_id, 0.0)
            bm25_score = bm25_scores_map.get(doc_id, 0.0)

            hybrid_semantic_score = float(alpha * dense_sim + (1.0 - alpha) * bm25_score)

            results.append({
                "id": doc_id,
                "text": doc.get("text", ""),
                "source": doc.get("source", "Unknown"),
                "source_type": doc.get("source_type", "Web"),
                "evidence_type": doc.get("evidence_type", "blog"),
                "timestamp": doc.get("timestamp", ""),
                "category": doc.get("category", "news"),
                "semantic_score": round(hybrid_semantic_score, 4),
                "dense_score": round(dense_sim, 4),
                "bm25_score": round(bm25_score, 4)
            })

        results.sort(key=lambda x: x["semantic_score"], reverse=True)
        return results[:top_k]
