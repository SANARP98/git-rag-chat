"""Reranking algorithms for improving retrieval quality."""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class Reranker:
    """Rerank retrieved chunks to improve diversity and relevance."""

    def __init__(self, embedder=None):
        """Initialize reranker.

        Args:
            embedder: Optional embedder for computing embeddings
        """
        self.embedder = embedder
        logger.info("Reranker initialized")

    def mmr_rerank(
        self,
        chunks: List[Dict[str, Any]],
        query_embedding: Optional[np.ndarray] = None,
        lambda_param: float = 0.5,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Rerank using Maximal Marginal Relevance (MMR).

        MMR balances relevance and diversity:
        - High relevance: Results similar to query
        - High diversity: Results different from each other

        Args:
            chunks: List of retrieved chunks with 'code' field
            query_embedding: Query embedding (optional, uses similarity from chunks)
            lambda_param: Trade-off between relevance and diversity (0-1)
                         1.0 = pure relevance, 0.0 = pure diversity
            top_k: Number of results to return (None = all)

        Returns:
            Reranked list of chunks
        """
        if not chunks:
            return []

        logger.info(f"MMR reranking {len(chunks)} chunks (λ={lambda_param})")

        # If we don't have embeddings, fall back to similarity scores
        if query_embedding is None and 'similarity' in chunks[0]:
            return self._mmr_rerank_by_similarity(chunks, lambda_param, top_k)

        # Need embedder to compute new embeddings
        if self.embedder is None:
            logger.warning("No embedder available, returning original order")
            return chunks[:top_k] if top_k else chunks

        try:
            # Generate embeddings for all chunks
            chunk_texts = [chunk['code'] for chunk in chunks]
            chunk_embeddings = self.embedder.embed_batch(
                chunk_texts,
                show_progress=False
            )

            # Compute MMR
            selected_indices = self._mmr_select(
                query_embedding,
                chunk_embeddings,
                lambda_param,
                top_k or len(chunks)
            )

            # Reorder chunks
            reranked = [chunks[i] for i in selected_indices]

            # Add MMR scores
            for idx, chunk in enumerate(reranked):
                chunk['mmr_rank'] = idx + 1
                chunk['mmr_score'] = 1.0 - (idx / len(reranked))

            logger.info(f"MMR reranking complete: {len(reranked)} results")
            return reranked

        except Exception as e:
            logger.error(f"MMR reranking failed: {e}")
            return chunks[:top_k] if top_k else chunks

    def _mmr_rerank_by_similarity(
        self,
        chunks: List[Dict[str, Any]],
        lambda_param: float,
        top_k: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Simplified MMR using pre-computed similarity scores.

        Args:
            chunks: Chunks with 'similarity' field
            lambda_param: Relevance vs diversity trade-off
            top_k: Number of results

        Returns:
            Reranked chunks
        """
        if not chunks:
            return []

        # Sort by similarity initially
        sorted_chunks = sorted(
            chunks,
            key=lambda x: x.get('similarity', 0.0),
            reverse=True
        )

        selected = []
        remaining = sorted_chunks.copy()
        k = top_k or len(chunks)

        # Select first (most relevant)
        if remaining:
            selected.append(remaining.pop(0))

        # Iteratively select remaining
        while len(selected) < k and remaining:
            max_mmr_score = -float('inf')
            max_idx = 0

            for idx, candidate in enumerate(remaining):
                # Relevance score
                relevance = candidate.get('similarity', 0.0)

                # Diversity: max similarity to already selected
                max_sim_to_selected = max(
                    self._text_similarity(
                        candidate['code'],
                        sel['code']
                    )
                    for sel in selected
                )

                # MMR score
                mmr_score = (
                    lambda_param * relevance -
                    (1 - lambda_param) * max_sim_to_selected
                )

                if mmr_score > max_mmr_score:
                    max_mmr_score = mmr_score
                    max_idx = idx

            selected.append(remaining.pop(max_idx))

        return selected

    def _mmr_select(
        self,
        query_embedding: np.ndarray,
        document_embeddings: np.ndarray,
        lambda_param: float,
        k: int
    ) -> List[int]:
        """Select k document indices using MMR algorithm.

        Args:
            query_embedding: Query embedding vector
            document_embeddings: Matrix of document embeddings (n_docs x dim)
            lambda_param: Relevance vs diversity parameter
            k: Number of documents to select

        Returns:
            List of selected document indices
        """
        # Compute similarities to query
        query_sims = self._cosine_similarity_batch(
            query_embedding,
            document_embeddings
        )

        # Initialize
        selected_indices = []
        remaining_indices = list(range(len(document_embeddings)))

        # Select first document (most relevant)
        first_idx = int(np.argmax(query_sims))
        selected_indices.append(first_idx)
        remaining_indices.remove(first_idx)

        # Iteratively select remaining documents
        while len(selected_indices) < k and remaining_indices:
            mmr_scores = []

            for idx in remaining_indices:
                # Relevance: similarity to query
                relevance = query_sims[idx]

                # Diversity: max similarity to selected documents
                if selected_indices:
                    selected_embeddings = document_embeddings[selected_indices]
                    doc_sims = self._cosine_similarity_batch(
                        document_embeddings[idx],
                        selected_embeddings
                    )
                    max_sim = np.max(doc_sims)
                else:
                    max_sim = 0.0

                # MMR score
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
                mmr_scores.append(mmr_score)

            # Select document with highest MMR score
            best_idx = remaining_indices[int(np.argmax(mmr_scores))]
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

        return selected_indices

    def _cosine_similarity_batch(
        self,
        vec1: np.ndarray,
        vec2_batch: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity between one vector and a batch.

        Args:
            vec1: Single vector (dim,)
            vec2_batch: Batch of vectors (n x dim)

        Returns:
            Array of similarity scores (n,)
        """
        # Ensure vec1 is 1D
        if vec1.ndim == 2:
            vec1 = vec1.flatten()

        # Ensure vec2_batch is 2D
        if vec2_batch.ndim == 1:
            vec2_batch = vec2_batch.reshape(1, -1)

        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
        vec2_norms = vec2_batch / (
            np.linalg.norm(vec2_batch, axis=1, keepdims=True) + 1e-8
        )

        # Compute dot product
        similarities = np.dot(vec2_norms, vec1_norm)

        return similarities

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple text similarity using character overlap.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        # Simple character-level Jaccard similarity
        set1 = set(text1.lower())
        set2 = set(text2.lower())

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def diversity_rerank(
        self,
        chunks: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Rerank to maximize diversity (spread across files/types).

        Args:
            chunks: List of chunks
            top_k: Number of results

        Returns:
            Reranked chunks with diverse sources
        """
        if not chunks:
            return []

        logger.info(f"Diversity reranking {len(chunks)} chunks")

        # Track what we've selected
        selected = []
        seen_files = set()
        seen_types = set()

        k = top_k or len(chunks)

        # Sort by similarity initially
        sorted_chunks = sorted(
            chunks,
            key=lambda x: x.get('similarity', 0.0),
            reverse=True
        )

        # First pass: one chunk per file
        for chunk in sorted_chunks:
            file_path = chunk.get('file_path', '')

            if file_path not in seen_files:
                selected.append(chunk)
                seen_files.add(file_path)
                seen_types.add(chunk.get('chunk_type', ''))

                if len(selected) >= k:
                    break

        # Second pass: different types from same files
        if len(selected) < k:
            for chunk in sorted_chunks:
                if chunk in selected:
                    continue

                chunk_type = chunk.get('chunk_type', '')
                chunk_key = (chunk.get('file_path', ''), chunk_type)

                # Select if different type in same file
                if chunk_key not in {(c.get('file_path', ''), c.get('chunk_type', '')) for c in selected}:
                    selected.append(chunk)

                    if len(selected) >= k:
                        break

        # Third pass: fill remaining with most relevant
        if len(selected) < k:
            for chunk in sorted_chunks:
                if chunk not in selected:
                    selected.append(chunk)

                    if len(selected) >= k:
                        break

        logger.info(f"Diversity reranking complete: {len(selected)} results from {len(seen_files)} files")
        return selected

    def reciprocal_rank_fusion(
        self,
        result_lists: List[List[Dict[str, Any]]],
        k: int = 60,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Combine multiple ranking lists using Reciprocal Rank Fusion.

        Args:
            result_lists: List of ranked result lists
            k: Constant for RRF formula (default 60)
            top_k: Number of final results

        Returns:
            Fused ranking
        """
        if not result_lists:
            return []

        logger.info(f"RRF fusion of {len(result_lists)} result lists")

        # Compute RRF scores
        rrf_scores = {}

        for result_list in result_lists:
            for rank, chunk in enumerate(result_list):
                chunk_id = chunk.get('id', chunk.get('code', '')[:50])

                if chunk_id not in rrf_scores:
                    rrf_scores[chunk_id] = {
                        'chunk': chunk,
                        'score': 0.0
                    }

                # RRF formula: 1 / (k + rank)
                rrf_scores[chunk_id]['score'] += 1.0 / (k + rank + 1)

        # Sort by RRF score
        sorted_items = sorted(
            rrf_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )

        # Extract chunks
        fused_results = [item['chunk'] for item in sorted_items]

        # Add RRF scores
        for idx, chunk in enumerate(fused_results):
            chunk['rrf_score'] = sorted_items[idx]['score']
            chunk['rrf_rank'] = idx + 1

        if top_k:
            fused_results = fused_results[:top_k]

        logger.info(f"RRF fusion complete: {len(fused_results)} results")
        return fused_results
