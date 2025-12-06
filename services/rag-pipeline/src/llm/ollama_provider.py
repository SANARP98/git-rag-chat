"""Ollama provider for offline LLM capability."""

import httpx
import json
import logging
from typing import Optional, AsyncIterator, Dict, Any, List

from .base import LLMProvider, LLMConnectionError, LLMTimeoutError

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider using Ollama for offline capability."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Ollama provider.

        Args:
            config: Configuration dict with optional keys:
                - base_url: Ollama API URL (default: http://ollama:11434)
                - model: Model name (default: deepseek-coder:33b)
                - timeout: Request timeout in seconds (default: 120)
        """
        super().__init__(config)

        self.base_url = self.config.get('base_url', 'http://ollama:11434')
        self.model = self.config.get('model', 'deepseek-coder:33b')
        self.timeout = self.config.get('timeout', 120)

        self.client = httpx.AsyncClient(timeout=self.timeout)

        logger.info(f"Ollama provider initialized (model={self.model}, url={self.base_url})")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response using Ollama.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        logger.info(f"Generating response via Ollama ({self.model})")

        try:
            url = f"{self.base_url}/api/generate"

            payload = {
                'model': self.model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': temperature,
                }
            }

            if max_tokens:
                payload['options']['num_predict'] = max_tokens

            response = await self.client.post(url, json=payload)

            if response.status_code != 200:
                raise LLMConnectionError(
                    f"Ollama API error: {response.status_code} - {response.text}"
                )

            result = response.json()
            generated_text = result.get('response', '')

            logger.info(f"Generated {len(generated_text)} chars")
            return generated_text

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"Ollama timeout after {self.timeout}s")
        except httpx.RequestError as e:
            raise LLMConnectionError(f"Ollama connection failed: {e}")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming response using Ollama.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Chunks of generated text
        """
        logger.info(f"Generating streaming response via Ollama ({self.model})")

        try:
            url = f"{self.base_url}/api/generate"

            payload = {
                'model': self.model,
                'prompt': prompt,
                'stream': True,
                'options': {
                    'temperature': temperature,
                }
            }

            if max_tokens:
                payload['options']['num_predict'] = max_tokens

            async with self.client.stream('POST', url, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise LLMConnectionError(
                        f"Ollama API error: {response.status_code} - {error_text}"
                    )

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        chunk = json.loads(line)
                        text = chunk.get('response', '')
                        if text:
                            yield text

                        # Check if done
                        if chunk.get('done', False):
                            break

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse chunk: {line}")
                        continue

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"Ollama timeout after {self.timeout}s")
        except httpx.RequestError as e:
            raise LLMConnectionError(f"Ollama connection failed: {e}")
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            raise

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate response using chat API.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system: System message
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        logger.info(f"Generating chat response via Ollama ({self.model})")

        try:
            url = f"{self.base_url}/api/chat"

            # Build messages list
            chat_messages = []

            if system:
                chat_messages.append({
                    'role': 'system',
                    'content': system
                })

            chat_messages.extend(messages)

            payload = {
                'model': self.model,
                'messages': chat_messages,
                'stream': False,
                'options': {
                    'temperature': temperature,
                }
            }

            if max_tokens:
                payload['options']['num_predict'] = max_tokens

            response = await self.client.post(url, json=payload)

            if response.status_code != 200:
                raise LLMConnectionError(
                    f"Ollama API error: {response.status_code} - {response.text}"
                )

            result = response.json()
            message = result.get('message', {})
            generated_text = message.get('content', '')

            logger.info(f"Generated {len(generated_text)} chars")
            return generated_text

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"Ollama timeout after {self.timeout}s")
        except httpx.RequestError as e:
            raise LLMConnectionError(f"Ollama connection failed: {e}")
        except Exception as e:
            logger.error(f"Ollama chat generation failed: {e}")
            raise

    async def generate_chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming response using chat API.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system: System message
            **kwargs: Additional parameters

        Yields:
            Chunks of generated text
        """
        logger.info(f"Generating streaming chat response via Ollama ({self.model})")

        try:
            url = f"{self.base_url}/api/chat"

            # Build messages list
            chat_messages = []

            if system:
                chat_messages.append({
                    'role': 'system',
                    'content': system
                })

            chat_messages.extend(messages)

            payload = {
                'model': self.model,
                'messages': chat_messages,
                'stream': True,
                'options': {
                    'temperature': temperature,
                }
            }

            if max_tokens:
                payload['options']['num_predict'] = max_tokens

            async with self.client.stream('POST', url, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise LLMConnectionError(
                        f"Ollama API error: {response.status_code} - {error_text}"
                    )

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        chunk = json.loads(line)
                        message = chunk.get('message', {})
                        text = message.get('content', '')
                        if text:
                            yield text

                        # Check if done
                        if chunk.get('done', False):
                            break

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse chunk: {line}")
                        continue

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"Ollama timeout after {self.timeout}s")
        except httpx.RequestError as e:
            raise LLMConnectionError(f"Ollama connection failed: {e}")
        except Exception as e:
            logger.error(f"Ollama chat streaming failed: {e}")
            raise

    async def check_health(self) -> bool:
        """Check if Ollama is accessible.

        Returns:
            True if Ollama is healthy
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = await self.client.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available models.

        Returns:
            List of model names
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = await self.client.get(url)

            if response.status_code != 200:
                return []

            result = response.json()
            models = result.get('models', [])
            return [m.get('name', '') for m in models]

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information.

        Returns:
            Model info dict
        """
        return {
            'provider': 'Ollama',
            'model': self.model,
            'base_url': self.base_url,
            'timeout': self.timeout,
            'streaming': True,
            'chat_format': True,
            'offline': True
        }

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Estimate cost (free for local Ollama).

        Returns:
            0.0 (local/offline)
        """
        return 0.0

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
