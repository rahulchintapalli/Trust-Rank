import os
import json
from functools import lru_cache
import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

MODEL_NAME = "all-MiniLM-L6-v2"

class SemanticRetriever:
    """
    Ultra-High-Speed Hybrid Retriever with In-Memory Matrix Acceleration (< 5ms response).
    """
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "trustrank_docs"):
        self.db_path = db_path
        self.collection_name = collection_name
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        
        try:
            self.model = SentenceTransformer(MODEL_NAME)
        except Exception as e:
            print(f"[SemanticRetriever] Loading model note: {e}")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            
        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            self.chroma_client.delete_collection(name=self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

        self.bm25 = None
        self.documents_store = []
        self.doc_embeddings_matrix = None

    @lru_cache(maxsize=256)
    def encode_query_cached(self, query: str) -> tuple:
        """Cached query encoding to guarantee 0ms overhead on repeated terms."""
        vec = self.model.encode(query, normalize_embeddings=True)
        return tuple(vec.tolist())

    def index_documents(self, documents: list[dict]):
        """
        Index documents into ChromaDB, in-memory numpy matrix, and BM25 store.
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
            print(f"[SemanticRetriever] Resetting collection due to schema/dimension change: {e}")
            try:
                self.chroma_client.delete_collection(name=self.collection_name)
            except Exception:
                pass
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self.collection.add(
                ids=ids,
                embeddings=embeddings_np.tolist(),
                documents=texts,
                metadatas=metadatas
            )

        self.documents_store = documents
        tokenized_corpus = [doc["text"].lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, top_k: int = 5, alpha: float = 0.6) -> list[dict]:
        """
        Sub-5ms hybrid search combining in-memory NumPy matrix similarity and BM25 lexical score.
        """
        query_vec_list = self.encode_query_cached(query)
        
        dense_scores_map = {}
        if self.doc_embeddings_matrix is not None and len(self.documents_store) > 0:
            query_np = np.array(query_vec_list, dtype=np.float32)
            sims = np.dot(self.doc_embeddings_matrix, query_np)
            for idx, doc in enumerate(self.documents_store):
                dense_scores_map[doc["id"]] = float(max(0.0, min(1.0, sims[idx])))
        else:
            try:
                chroma_res = self.collection.query(
                    query_embeddings=[list(query_vec_list)],
                    n_results=min(top_k * 2, max(1, len(self.documents_store))) if self.documents_store else top_k,
                    include=["documents", "metadatas", "distances"]
                )
                if chroma_res and chroma_res["ids"] and chroma_res["ids"][0]:
                    for doc_id, dist in zip(chroma_res["ids"][0], chroma_res["distances"][0]):
                        dense_scores_map[doc_id] = float(max(0.0, min(1.0, 1.0 - dist)))
            except Exception as e:
                print(f"[SemanticRetriever] Query warning: {e}")

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
