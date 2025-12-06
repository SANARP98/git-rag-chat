"""Embedding generation using sentence-transformers."""

import logging
from typing import List, Optional
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
import hashlib
import pickle

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings for code and text using sentence-transformers."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: Optional[str] = None,
        device: Optional[str] = None
    ):
        """Initialize the embedding model.

        Args:
            model_name: Name of the sentence-transformers model
            cache_dir: Directory to cache the model (optional)
            device: Device to run model on ('cpu', 'cuda', etc.) (optional)
        """
        self.model_name = model_name
        self.cache_dir = cache_dir or "/app/data/models"
        self.device = device

        logger.info(f"Loading embedding model: {model_name}")

        try:
            # Ensure cache directory exists
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

            # Load model
            self.model = SentenceTransformer(
                model_name,
                cache_folder=self.cache_dir,
                device=device
            )

            # Get model info
            self.embedding_dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded successfully. Embedding dimension: {self.embedding_dimension}")

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Numpy array of embeddings
        """
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            Numpy array of embeddings (n_texts x embedding_dim)
        """
        try:
            logger.info(f"Generating embeddings for {len(texts)} texts")

            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True
            )

            logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    def embed_code_chunks(
        self,
        chunks: List[dict],
        batch_size: int = 32
    ) -> List[np.ndarray]:
        """Generate embeddings for code chunks.

        Args:
            chunks: List of chunk dictionaries with 'code' field
            batch_size: Batch size for encoding

        Returns:
            List of embeddings (one per chunk)
        """
        # Extract code from chunks
        code_texts = [chunk.get('code', '') for chunk in chunks]

        # Generate embeddings
        embeddings = self.embed_batch(code_texts, batch_size=batch_size)

        return embeddings

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score (-1 to 1)
        """
        # Normalize embeddings
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Compute cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        return float(similarity)

    def get_cache_key(self, text: str) -> str:
        """Generate a cache key for a text.

        Args:
            text: Text to hash

        Returns:
            MD5 hash of the text
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def save_embeddings(self, embeddings: np.ndarray, file_path: str) -> bool:
        """Save embeddings to disk.

        Args:
            embeddings: Numpy array of embeddings
            file_path: Path to save embeddings

        Returns:
            True if successful
        """
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'wb') as f:
                pickle.dump(embeddings, f)

            logger.info(f"Saved embeddings to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save embeddings: {e}")
            return False

    def load_embeddings(self, file_path: str) -> Optional[np.ndarray]:
        """Load embeddings from disk.

        Args:
            file_path: Path to embeddings file

        Returns:
            Numpy array of embeddings or None if failed
        """
        try:
            with open(file_path, 'rb') as f:
                embeddings = pickle.load(f)

            logger.info(f"Loaded embeddings from {file_path}")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")
            return None

    def preprocess_code(self, code: str, max_length: int = 512) -> str:
        """Preprocess code for embedding.

        Args:
            code: Code text
            max_length: Maximum length in tokens (approximate)

        Returns:
            Preprocessed code
        """
        # Remove excessive whitespace
        lines = code.split('\n')
        lines = [line.rstrip() for line in lines]
        code = '\n'.join(lines)

        # Truncate if too long (rough estimate: 1 token ≈ 4 chars)
        max_chars = max_length * 4
        if len(code) > max_chars:
            code = code[:max_chars]
            logger.debug(f"Truncated code to {max_chars} characters")

        return code

    def get_model_info(self) -> dict:
        """Get information about the loaded model.

        Returns:
            Dictionary with model information
        """
        return {
            'model_name': self.model_name,
            'embedding_dimension': self.embedding_dimension,
            'max_sequence_length': self.model.max_seq_length,
            'device': str(self.model.device),
            'cache_dir': self.cache_dir
        }
