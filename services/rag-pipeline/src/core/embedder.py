"""Embedding generation using OpenAI."""

import logging
import os
import time
from typing import List, Optional
from pathlib import Path
from abc import ABC, abstractmethod
import numpy as np
from openai import OpenAI
import hashlib
import pickle

logger = logging.getLogger(__name__)


class BaseEmbedder(ABC):
    """Abstract base class for embedders."""

    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Numpy array of embeddings
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            Embedding dimension
        """
        pass

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


# LocalEmbedder class removed - using OpenAI embeddings only
# If you need local embeddings, add sentence-transformers to requirements.txt


class OpenAIEmbedder(BaseEmbedder):
    """Generate embeddings using OpenAI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-large",
        batch_size: int = 100,
        max_retries: int = 3
    ):
        """Initialize the OpenAI embedder.

        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            model: OpenAI embedding model name
            batch_size: Batch size for API requests (OpenAI allows up to 2048)
            max_retries: Maximum number of retries for failed requests
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set. Please set it in environment variables or pass it directly.")

        self.model_name = model
        self.batch_size = batch_size
        self.max_retries = max_retries

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)

        # Set dimension based on model
        if model == "text-embedding-3-large":
            self._dimension = 3072
        elif model == "text-embedding-3-small":
            self._dimension = 1536
        elif model == "text-embedding-ada-002":
            self._dimension = 1536
        else:
            self._dimension = 1536  # Default

        logger.info(f"Initialized OpenAI embedder with model: {model} ({self._dimension} dimensions)")

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Numpy array of embeddings
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model_name
            )
            embedding = np.array(response.data[0].embedding)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate OpenAI embedding: {e}")
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
            batch_size: Batch size for encoding (will be capped to self.batch_size)
            show_progress: Whether to show progress (logged)

        Returns:
            Numpy array of embeddings (n_texts x embedding_dim)
        """
        embeddings = []
        batch_size = min(batch_size, self.batch_size)

        logger.info(f"Generating OpenAI embeddings for {len(texts)} texts in batches of {batch_size}")

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            if show_progress:
                logger.info(f"Processing batch {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}")

            # Retry logic with exponential backoff
            for attempt in range(self.max_retries):
                try:
                    response = self.client.embeddings.create(
                        input=batch,
                        model=self.model_name
                    )

                    # Extract embeddings from response
                    batch_embeddings = [np.array(data.embedding) for data in response.data]
                    embeddings.extend(batch_embeddings)
                    break  # Success, exit retry loop

                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.error(f"Failed to generate embeddings after {self.max_retries} attempts: {e}")
                        raise
                    else:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(f"Retry {attempt + 1}/{self.max_retries} after error: {e}. Waiting {wait_time}s...")
                        time.sleep(wait_time)

        logger.info(f"Generated {len(embeddings)} OpenAI embeddings")
        return np.array(embeddings)

    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            Embedding dimension
        """
        return self._dimension

    def get_model_info(self) -> dict:
        """Get information about the model.

        Returns:
            Dictionary with model information
        """
        return {
            'provider': 'openai',
            'model_name': self.model_name,
            'embedding_dimension': self._dimension,
            'batch_size': self.batch_size,
            'max_retries': self.max_retries
        }


def create_embedder(
    provider: str = "openai",
    model_name: Optional[str] = None,
    **kwargs
) -> BaseEmbedder:
    """Factory function to create an embedder based on provider.

    Args:
        provider: Only 'openai' is supported
        model_name: Model name (optional, uses defaults)
        **kwargs: Additional arguments for embedder

    Returns:
        Embedder instance

    Raises:
        ValueError: If provider is unknown
    """
    provider = provider.lower()

    if provider == "openai":
        default_model = "text-embedding-3-large"
        return OpenAIEmbedder(
            model=model_name or default_model,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown provider: {provider}. Only 'openai' is supported. For local embeddings, add sentence-transformers to requirements.txt")


# Utility functions for backward compatibility and caching

def get_cache_key(text: str) -> str:
    """Generate a cache key for a text.

    Args:
        text: Text to hash

    Returns:
        MD5 hash of the text
    """
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def save_embeddings(embeddings: np.ndarray, file_path: str) -> bool:
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


def load_embeddings(file_path: str) -> Optional[np.ndarray]:
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


def preprocess_code(code: str, max_length: int = 512) -> str:
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


# For backward compatibility - use OpenAIEmbedder directly
Embedder = OpenAIEmbedder
