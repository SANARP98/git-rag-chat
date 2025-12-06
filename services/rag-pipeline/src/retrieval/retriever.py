"""RAG retrieval module for semantic code search."""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

from ..core.vector_store import VectorStore
from ..core.embedder import Embedder

logger = logging.getLogger(__name__)


class CodeRetriever:
    """Retrieve relevant code chunks using semantic search."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: Embedder
    ):
        """Initialize retriever.

        Args:
            vector_store: Vector store instance
            embedder: Embedder instance
        """
        self.vector_store = vector_store
        self.embedder = embedder

        logger.info("Code retriever initialized")

    def retrieve(
        self,
        collection_name: str,
        query: str,
        n_results: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant code chunks for a query.

        Args:
            collection_name: ChromaDB collection name
            query: Natural language query
            n_results: Maximum number of results to return
            filters: Metadata filters (e.g., {"language": "python"})
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of retrieved chunks with metadata and scores
        """
        logger.info(f"Retrieving {n_results} chunks for query: {query[:100]}")

        try:
            # Query vector store
            results = self.vector_store.query(
                collection_name=collection_name,
                query_text=query,
                n_results=n_results,
                where=filters
            )

            # Format results
            chunks = self._format_results(results, min_similarity)

            logger.info(f"Retrieved {len(chunks)} relevant chunks")
            return chunks

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            raise

    def retrieve_with_context(
        self,
        collection_name: str,
        query: str,
        n_results: int = 10,
        context_lines: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks with additional context from surrounding code.

        Args:
            collection_name: ChromaDB collection name
            query: Natural language query
            n_results: Maximum number of results
            context_lines: Number of lines before/after to include
            filters: Metadata filters

        Returns:
            List of chunks with expanded context
        """
        # Get base results
        chunks = self.retrieve(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            filters=filters
        )

        # TODO: Add logic to fetch surrounding chunks from same file
        # For now, return as-is
        return chunks

    def retrieve_by_file(
        self,
        collection_name: str,
        query: str,
        file_path: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks from a specific file.

        Args:
            collection_name: ChromaDB collection name
            query: Natural language query
            file_path: File path to search within
            n_results: Maximum number of results

        Returns:
            List of chunks from the specified file
        """
        filters = {"file_path": file_path}

        return self.retrieve(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            filters=filters
        )

    def retrieve_by_language(
        self,
        collection_name: str,
        query: str,
        language: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks of a specific programming language.

        Args:
            collection_name: ChromaDB collection name
            query: Natural language query
            language: Programming language (e.g., "python", "javascript")
            n_results: Maximum number of results

        Returns:
            List of chunks in the specified language
        """
        filters = {"language": language}

        return self.retrieve(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            filters=filters
        )

    def retrieve_by_type(
        self,
        collection_name: str,
        query: str,
        chunk_type: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks of a specific type.

        Args:
            collection_name: ChromaDB collection name
            query: Natural language query
            chunk_type: Type of chunk (e.g., "function", "class")
            n_results: Maximum number of results

        Returns:
            List of chunks of the specified type
        """
        filters = {"chunk_type": chunk_type}

        return self.retrieve(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            filters=filters
        )

    def retrieve_uncommitted(
        self,
        collection_name: str,
        query: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve only uncommitted changes.

        Args:
            collection_name: ChromaDB collection name
            query: Natural language query
            n_results: Maximum number of results

        Returns:
            List of uncommitted chunks
        """
        filters = {"is_uncommitted": "True"}

        return self.retrieve(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            filters=filters
        )

    def find_similar_code(
        self,
        collection_name: str,
        code_snippet: str,
        n_results: int = 5,
        exclude_exact: bool = True
    ) -> List[Dict[str, Any]]:
        """Find code similar to a given snippet.

        Args:
            collection_name: ChromaDB collection name
            code_snippet: Code to find similar examples of
            n_results: Maximum number of results
            exclude_exact: If True, exclude exact matches

        Returns:
            List of similar code chunks
        """
        logger.info(f"Finding similar code (n={n_results})")

        # Use code as query (embedder handles code well)
        chunks = self.retrieve(
            collection_name=collection_name,
            query=code_snippet,
            n_results=n_results + (1 if exclude_exact else 0)
        )

        # Filter exact matches if requested
        if exclude_exact:
            chunks = [
                chunk for chunk in chunks
                if chunk['code'].strip() != code_snippet.strip()
            ][:n_results]

        return chunks

    def _format_results(
        self,
        raw_results: Dict[str, Any],
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Format raw ChromaDB results into structured chunks.

        Args:
            raw_results: Raw results from ChromaDB
            min_similarity: Minimum similarity threshold

        Returns:
            List of formatted chunks
        """
        chunks = []

        # ChromaDB returns results in lists
        ids = raw_results.get('ids', [[]])[0]
        documents = raw_results.get('documents', [[]])[0]
        metadatas = raw_results.get('metadatas', [[]])[0]
        distances = raw_results.get('distances', [[]])[0]

        for idx, chunk_id in enumerate(ids):
            # Convert distance to similarity (ChromaDB uses L2 distance)
            # Similarity = 1 / (1 + distance)
            distance = distances[idx] if idx < len(distances) else 1.0
            similarity = 1.0 / (1.0 + distance)

            # Skip if below threshold
            if similarity < min_similarity:
                continue

            metadata = metadatas[idx] if idx < len(metadatas) else {}

            # Build chunk dict
            chunk = {
                'id': chunk_id,
                'code': documents[idx] if idx < len(documents) else '',
                'similarity': similarity,
                'distance': distance,
                'metadata': metadata,
                # Extract common metadata fields
                'file_path': metadata.get('file_path', ''),
                'chunk_type': metadata.get('chunk_type', 'unknown'),
                'name': metadata.get('name', 'unknown'),
                'language': metadata.get('language', 'unknown'),
                'start_line': int(metadata.get('start_line', 0)),
                'end_line': int(metadata.get('end_line', 0)),
                'line_count': int(metadata.get('line_count', 0)),
            }

            chunks.append(chunk)

        return chunks

    def compute_chunk_relevance(
        self,
        query_embedding: np.ndarray,
        chunk_embeddings: List[np.ndarray]
    ) -> List[float]:
        """Compute relevance scores between query and chunks.

        Args:
            query_embedding: Query embedding vector
            chunk_embeddings: List of chunk embedding vectors

        Returns:
            List of relevance scores (cosine similarity)
        """
        scores = []

        for chunk_emb in chunk_embeddings:
            score = self.embedder.compute_similarity(query_embedding, chunk_emb)
            scores.append(score)

        return scores

    def hybrid_search(
        self,
        collection_name: str,
        query: str,
        keywords: List[str],
        n_results: int = 10,
        semantic_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining semantic and keyword matching.

        Args:
            collection_name: ChromaDB collection name
            query: Natural language query
            keywords: Keywords to boost
            n_results: Maximum number of results
            semantic_weight: Weight for semantic score (1 - weight for keyword)

        Returns:
            List of chunks with hybrid scores
        """
        # Get semantic results
        semantic_chunks = self.retrieve(
            collection_name=collection_name,
            query=query,
            n_results=n_results * 2  # Get more for reranking
        )

        # Compute keyword scores
        keyword_weight = 1.0 - semantic_weight

        for chunk in semantic_chunks:
            # Count keyword matches
            code_lower = chunk['code'].lower()
            keyword_score = sum(
                1 for kw in keywords
                if kw.lower() in code_lower
            ) / max(len(keywords), 1)

            # Compute hybrid score
            chunk['semantic_score'] = chunk['similarity']
            chunk['keyword_score'] = keyword_score
            chunk['hybrid_score'] = (
                semantic_weight * chunk['similarity'] +
                keyword_weight * keyword_score
            )

        # Sort by hybrid score
        semantic_chunks.sort(key=lambda x: x['hybrid_score'], reverse=True)

        return semantic_chunks[:n_results]

    def get_statistics(self, collection_name: str) -> Dict[str, Any]:
        """Get retrieval statistics for a collection.

        Args:
            collection_name: ChromaDB collection name

        Returns:
            Dictionary with collection statistics
        """
        return self.vector_store.get_collection_stats(collection_name)
