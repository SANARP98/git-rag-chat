"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize LLM provider.

        Args:
            config: Provider-specific configuration
        """
        self.config = config or {}
        logger.info(f"Initializing {self.__class__.__name__}")

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            Generated text
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate a streaming response from the LLM.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Yields:
            Chunks of generated text
        """
        pass

    @abstractmethod
    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate a response using chat-based API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            system: Optional system message
            **kwargs: Provider-specific parameters

        Returns:
            Generated text
        """
        pass

    @abstractmethod
    async def generate_chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate a streaming response using chat-based API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            system: Optional system message
            **kwargs: Provider-specific parameters

        Yields:
            Chunks of generated text
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model.

        Returns:
            Dictionary with model information
        """
        return {
            'provider': self.__class__.__name__,
            'config': self.config
        }

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Estimate cost for a request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD (0.0 if not applicable)
        """
        return 0.0

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming.

        Returns:
            True if streaming is supported
        """
        return True

    def supports_chat(self) -> bool:
        """Check if provider supports chat format.

        Returns:
            True if chat format is supported
        """
        return True


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class LLMConnectionError(LLMError):
    """Exception for connection errors."""
    pass


class LLMTimeoutError(LLMError):
    """Exception for timeout errors."""
    pass


class LLMRateLimitError(LLMError):
    """Exception for rate limit errors."""
    pass


class LLMInvalidRequestError(LLMError):
    """Exception for invalid request errors."""
    pass
