"""Factory for creating LLM provider instances."""

import logging
from typing import Optional, Dict, Any

from .base import LLMProvider
from .codex_provider import CodexCLIProvider
from .ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM provider instances."""

    @staticmethod
    def create(provider_type: str, config: Optional[Dict[str, Any]] = None) -> LLMProvider:
        """Create an LLM provider instance.

        Args:
            provider_type: Type of provider ('codex', 'ollama', 'chatgpt-enterprise')
            config: Provider-specific configuration

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider type is unknown
        """
        provider_type = provider_type.lower()

        logger.info(f"Creating LLM provider: {provider_type}")

        if provider_type == 'codex':
            return CodexCLIProvider(config)

        elif provider_type == 'ollama':
            return OllamaProvider(config)

        elif provider_type == 'chatgpt-enterprise':
            # For now, use Codex CLI which connects to ChatGPT Enterprise
            logger.info("Using Codex CLI for ChatGPT Enterprise")
            return CodexCLIProvider(config)

        else:
            raise ValueError(
                f"Unknown provider type: {provider_type}. "
                f"Supported types: codex, ollama, chatgpt-enterprise"
            )

    @staticmethod
    def create_from_settings(settings) -> LLMProvider:
        """Create LLM provider from application settings.

        Args:
            settings: Application settings object

        Returns:
            LLMProvider instance
        """
        provider_type = settings.llm_provider

        # Build config based on provider type
        if provider_type == 'codex':
            config = {
                'profile': settings.codex_profile,
                'timeout': 180  # Increased to 3 minutes for complex queries with large context
            }
        elif provider_type == 'ollama':
            config = {
                'base_url': settings.ollama_base_url,
                'model': settings.ollama_model,
                'timeout': 120
            }
        else:
            config = {}

        return LLMFactory.create(provider_type, config)

    @staticmethod
    def get_available_providers() -> list:
        """Get list of available provider types.

        Returns:
            List of provider type strings
        """
        return ['codex', 'ollama', 'chatgpt-enterprise']
