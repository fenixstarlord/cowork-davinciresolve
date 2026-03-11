"""
Hybrid retrieval: vector similarity (ChromaDB) + BM25 keyword search with
Reciprocal Rank Fusion (RRF) merging.
"""

import os

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "./vectorstore")
COLLECTION_NAME = "resolve_docs"


class HybridRetriever:
    def __init__(self, vectorstore_path: str = None, chunks: list[dict] = None):
        """
        Initialize the hybrid retriever.

        Args:
            vectorstore_path: Path to the persisted ChromaDB store.
            chunks: Pre-loaded chunk dicts (with 'text' and 'metadata' keys).
                    If None, chunks are loaded from ChromaDB.
        """
        self.vectorstore_path = vectorstore_path or VECTORSTORE_PATH
        self.model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)

        # Load ChromaDB collection
        client = chromadb.PersistentClient(path=self.vectorstore_path)
        self.collection = client.get_collection(name=COLLECTION_NAME)

        # Load all chunks for BM25
        if chunks is not None:
            self.chunks = chunks
        else:
            results = self.collection.get(include=["documents", "metadatas"])
            self.chunks = [
                {"text": doc, "metadata": meta}
                for doc, meta in zip(results["documents"], results["metadatas"])
            ]

        # Build BM25 index
        tokenized = [self._tokenize(c["text"]) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized)

        # Map chunk texts to indices for fast lookup
        self._text_to_idx = {c["text"]: i for i, c in enumerate(self.chunks)}

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple whitespace + lowercased tokenization."""
        return text.lower().split()

    def retrieve(self, query: str, top_k: int = 6) -> list[dict]:
        """
        Retrieve the top-k most relevant chunks using hybrid search (vector + BM25)
        merged with Reciprocal Rank Fusion.

        Args:
            query: The user's query string.
            top_k: Number of results to return after fusion.

        Returns:
            List of chunk dicts with text, metadata, and rrf_score.
        """
        vector_results = self._vector_search(query, k=10)
        bm25_results = self._bm25_search(query, k=10)
        fused = self._reciprocal_rank_fusion(vector_results, bm25_results, k=60)
        return fused[:top_k]

    def _vector_search(self, query: str, k: int = 10) -> list[dict]:
        """Embed the query and retrieve top-K from ChromaDB."""
        query_embedding = self.model.encode(
            [query], normalize_embeddings=True
        ).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        ranked = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            ranked.append({
                "text": doc,
                "metadata": meta,
                "score": 1 - dist,  # cosine distance to similarity
            })
        return ranked

    def _bm25_search(self, query: str, k: int = 10) -> list[dict]:
        """Run BM25 over all chunk texts."""
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        ranked = []
        for idx in top_indices:
            if scores[idx] > 0:
                ranked.append({
                    "text": self.chunks[idx]["text"],
                    "metadata": self.chunks[idx]["metadata"],
                    "score": float(scores[idx]),
                })
        return ranked

    @staticmethod
    def _reciprocal_rank_fusion(
        *result_lists: list[dict], k: int = 60
    ) -> list[dict]:
        """
        Merge multiple ranked result lists using Reciprocal Rank Fusion.
        RRF score = sum(1 / (k + rank)) across all lists.
        """
        # Map text -> accumulated RRF score and metadata
        fused_scores: dict[str, float] = {}
        fused_meta: dict[str, dict] = {}

        for result_list in result_lists:
            for rank, item in enumerate(result_list):
                text = item["text"]
                rrf_score = 1.0 / (k + rank + 1)
                fused_scores[text] = fused_scores.get(text, 0.0) + rrf_score
                if text not in fused_meta:
                    fused_meta[text] = item["metadata"]

        # Sort by fused score descending
        sorted_texts = sorted(fused_scores.keys(), key=lambda t: fused_scores[t], reverse=True)

        results = []
        for text in sorted_texts:
            results.append({
                "text": text,
                "metadata": fused_meta[text],
                "rrf_score": fused_scores[text],
            })
        return results
