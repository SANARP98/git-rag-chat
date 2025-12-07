"""Codex CLI provider for ChatGPT Enterprise integration."""

import subprocess
import json
import asyncio
import logging
from typing import Optional, AsyncIterator, Dict, Any, List

from .base import LLMProvider, LLMConnectionError, LLMTimeoutError, LLMInvalidRequestError

logger = logging.getLogger(__name__)


class CodexCLIProvider(LLMProvider):
    """LLM provider using Codex CLI with ChatGPT Enterprise.

    This provider calls the Codex CLI tool which is authenticated
    with ChatGPT Enterprise credentials.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Codex CLI provider.

        Args:
            config: Configuration dict with optional keys:
                - profile: Codex profile name (None = default Enterprise)
                - timeout: Request timeout in seconds (default: 60)
                - temperature: Default temperature (default: 0.7)
                - max_tokens: Default max tokens (default: 2000)
        """
        super().__init__(config)

        self.profile = self.config.get('profile')
        self.timeout = self.config.get('timeout', 120)  # Increased from 60s to 120s for complex queries
        self.default_temperature = self.config.get('temperature', 0.7)
        self.default_max_tokens = self.config.get('max_tokens', 2000)

        # Verify Codex CLI is available
        try:
            result = subprocess.run(
                ['codex', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.warning("Codex CLI not found or not working")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Codex CLI check failed: {e}")

        logger.info(f"Codex CLI provider initialized (profile={self.profile or 'default'})")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response using Codex CLI.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        logger.info("Generating response via Codex CLI")

        try:
            # Build command
            # Note: --skip-git-repo-check and --dangerously-bypass-approvals-and-sandbox
            # are required when running in Docker containers
            cmd = ['codex', 'exec', '--skip-git-repo-check', '--dangerously-bypass-approvals-and-sandbox']

            if self.profile:
                cmd.extend(['--profile', self.profile])

            cmd.extend(['--json', prompt])

            # Execute Codex CLI
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                result.kill()
                raise LLMTimeoutError(f"Codex CLI timeout after {self.timeout}s")

            if result.returncode != 0:
                error_msg = stderr.decode('utf-8')
                logger.error(f"Codex CLI error: {error_msg}")
                raise LLMConnectionError(f"Codex CLI failed: {error_msg}")

            # Parse JSONL output
            output = stdout.decode('utf-8')
            response_text = self._parse_jsonl_output(output)

            logger.info(f"Generated {len(response_text)} chars")
            return response_text

        except (FileNotFoundError, PermissionError) as e:
            raise LLMConnectionError(f"Codex CLI not available: {e}")
        except Exception as e:
            logger.error(f"Codex generation failed: {e}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming response using Codex CLI.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Chunks of generated text
        """
        logger.info("Generating streaming response via Codex CLI")

        try:
            # Build command
            # Note: --skip-git-repo-check and --dangerously-bypass-approvals-and-sandbox
            # are required when running in Docker containers
            cmd = ['codex', 'exec', '--skip-git-repo-check', '--dangerously-bypass-approvals-and-sandbox']

            if self.profile:
                cmd.extend(['--profile', self.profile])

            cmd.extend(['--json', prompt])

            # Execute Codex CLI
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Read output line by line
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                try:
                    event = json.loads(line.decode('utf-8'))

                    # Handle different event types
                    if event.get('type') == 'message_delta':
                        delta = event.get('data', {}).get('delta', '')
                        if delta:
                            yield delta

                    elif event.get('type') == 'turn_completed':
                        # Final message
                        message = event.get('data', {}).get('message', '')
                        if message:
                            yield message
                        break

                    elif event.get('type') == 'error':
                        error_msg = event.get('data', {}).get('message', 'Unknown error')
                        raise LLMConnectionError(f"Codex error: {error_msg}")

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSONL line: {line}")
                    continue

            await process.wait()

        except (FileNotFoundError, PermissionError) as e:
            raise LLMConnectionError(f"Codex CLI not available: {e}")
        except Exception as e:
            logger.error(f"Codex streaming failed: {e}")
            raise

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate response using chat format.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system: System message
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        # Convert chat messages to single prompt
        prompt = self._format_chat_prompt(messages, system)
        return await self.generate(prompt, temperature, max_tokens, **kwargs)

    async def generate_chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming response using chat format.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system: System message
            **kwargs: Additional parameters

        Yields:
            Chunks of generated text
        """
        # Convert chat messages to single prompt
        prompt = self._format_chat_prompt(messages, system)

        async for chunk in self.generate_stream(prompt, temperature, max_tokens, **kwargs):
            yield chunk

    def _parse_jsonl_output(self, output: str) -> str:
        """Parse JSONL output from Codex CLI.

        Args:
            output: JSONL output string

        Returns:
            Final response text
        """
        lines = output.strip().split('\n')
        response_text = ""

        for line in lines:
            if not line.strip():
                continue

            try:
                event = json.loads(line)
                event_type = event.get('type', '')

                # Look for completed items with agent_message
                if event_type == 'item.completed':
                    item = event.get('item', {})
                    if item.get('type') == 'agent_message':
                        response_text = item.get('text', '')
                        # Don't break - keep looking for later messages

                # Also look for turn.completed
                elif event_type == 'turn.completed':
                    # Turn completed, we should have the message already
                    break

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSONL line: {line}")
                continue

        if not response_text:
            logger.warning("No response found in Codex output")
            # Fallback: return raw output
            response_text = output

        return response_text

    def _format_chat_prompt(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None
    ) -> str:
        """Format chat messages into a single prompt.

        Args:
            messages: List of message dicts
            system: Optional system message

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        # Add system message
        if system:
            prompt_parts.append(f"System: {system}\n")

        # Add conversation history
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
            elif role == 'system':
                prompt_parts.append(f"System: {content}")

        return "\n\n".join(prompt_parts)

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information.

        Returns:
            Model info dict
        """
        return {
            'provider': 'Codex CLI (ChatGPT Enterprise)',
            'profile': self.profile or 'default',
            'backend': 'ChatGPT Enterprise (GPT-4)',
            'timeout': self.timeout,
            'streaming': True,
            'chat_format': True
        }

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Estimate cost (free with Enterprise).

        Returns:
            0.0 (included in Enterprise subscription)
        """
        return 0.0
