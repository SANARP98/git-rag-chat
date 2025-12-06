"""Chat interface component with code syntax highlighting."""

import logging
from typing import List, Tuple, Optional, AsyncIterator
import httpx
import asyncio

logger = logging.getLogger(__name__)


class ChatInterface:
    """Chat interface for querying repositories."""

    def __init__(self, rag_api_url: str):
        """Initialize chat interface.

        Args:
            rag_api_url: URL of RAG pipeline API
        """
        self.rag_api_url = rag_api_url
        self.http_client = httpx.Client(timeout=120.0)
        self.async_http_client = httpx.AsyncClient(timeout=120.0)

    def query(
        self,
        message: str,
        history: List[Tuple[str, str]],
        repo_id: Optional[str] = None,
        temperature: float = 0.1,
        max_results: int = 10
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """Process user query and return response.

        Args:
            message: User query
            history: Chat history
            repo_id: Repository ID to query
            temperature: LLM temperature
            max_results: Number of chunks to retrieve

        Returns:
            Tuple of (response, updated_history)
        """
        if not message or not message.strip():
            return "", history

        # Show thinking state
        history.append((message, "Thinking..."))

        try:
            # Call query API
            response = self.http_client.post(
                f"{self.rag_api_url}/api/query",
                json={
                    "query": message,
                    "repo_id": repo_id,
                    "top_k": max_results,
                    "temperature": temperature,
                    "include_sources": True
                }
            )

            if response.status_code == 200:
                result = response.json()

                answer = result.get('answer', 'No response generated')
                sources = result.get('sources', [])

                # Format response with sources
                formatted_response = self._format_response(answer, sources)

                # Update history
                history[-1] = (message, formatted_response)

                return "", history

            else:
                error_detail = response.json().get('detail', 'Unknown error')
                error_msg = f"❌ Error: {error_detail}"
                history[-1] = (message, error_msg)
                return "", history

        except httpx.RequestError as e:
            logger.error(f"Query request failed: {e}")
            error_msg = f"❌ Connection Error: {str(e)}\n\nPlease check if RAG pipeline is running."
            history[-1] = (message, error_msg)
            return "", history

        except Exception as e:
            logger.error(f"Unexpected error during query: {e}")
            error_msg = f"❌ Unexpected Error: {str(e)}"
            history[-1] = (message, error_msg)
            return "", history

    async def query_stream(
        self,
        message: str,
        history: List[Tuple[str, str]],
        repo_id: Optional[str] = None,
        temperature: float = 0.1,
        max_results: int = 10
    ) -> AsyncIterator[Tuple[str, List[Tuple[str, str]]]]:
        """Process user query with streaming response.

        Args:
            message: User query
            history: Chat history
            repo_id: Repository ID to query
            temperature: LLM temperature
            max_results: Number of chunks to retrieve

        Yields:
            Tuple of (empty_string, updated_history) with streaming response
        """
        if not message or not message.strip():
            yield "", history
            return

        # Initialize response in history
        history.append((message, ""))
        accumulated_response = ""

        try:
            # Call streaming query API
            async with self.async_http_client.stream(
                'POST',
                f"{self.rag_api_url}/api/query/stream",
                json={
                    "query": message,
                    "repo_id": repo_id,
                    "top_k": max_results,
                    "temperature": temperature,
                    "include_sources": True
                }
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    error_msg = f"❌ Error: {error_text.decode('utf-8')}"
                    history[-1] = (message, error_msg)
                    yield "", history
                    return

                # Stream response chunks
                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # Remove "data: " prefix if present (SSE format)
                    if line.startswith("data: "):
                        line = line[6:]

                    # Accumulate response
                    accumulated_response += line

                    # Update history with accumulated response
                    history[-1] = (message, accumulated_response)
                    yield "", history

        except httpx.RequestError as e:
            logger.error(f"Streaming query failed: {e}")
            error_msg = f"❌ Connection Error: {str(e)}"
            history[-1] = (message, accumulated_response + "\n\n" + error_msg)
            yield "", history

        except Exception as e:
            logger.error(f"Unexpected streaming error: {e}")
            error_msg = f"❌ Error: {str(e)}"
            history[-1] = (message, accumulated_response + "\n\n" + error_msg)
            yield "", history

    def _format_response(self, answer: str, sources: List[dict]) -> str:
        """Format response with sources.

        Args:
            answer: LLM generated answer
            sources: List of source chunks

        Returns:
            Formatted markdown response
        """
        formatted = f"{answer}\n\n"

        if sources:
            formatted += "---\n\n### 📚 Sources\n\n"

            for idx, source in enumerate(sources, 1):
                file_path = source.get('file_path', 'Unknown')
                start_line = source.get('start_line', '?')
                end_line = source.get('end_line', '?')
                language = source.get('language', '')
                code_snippet = source.get('code', '')

                formatted += f"**{idx}. {file_path}** (lines {start_line}-{end_line})\n\n"

                # Add code snippet with syntax highlighting
                if code_snippet:
                    formatted += f"```{language}\n{code_snippet}\n```\n\n"

        return formatted.strip()

    def clear_history(self) -> List[Tuple[str, str]]:
        """Clear chat history.

        Returns:
            Empty history list
        """
        return []

    def export_history(self, history: List[Tuple[str, str]]) -> str:
        """Export chat history as markdown.

        Args:
            history: Chat history

        Returns:
            Markdown formatted history
        """
        if not history:
            return "No chat history to export."

        lines = ["# Chat History\n"]

        for idx, (user_msg, bot_msg) in enumerate(history, 1):
            lines.append(f"## Exchange {idx}\n")
            lines.append(f"**User:** {user_msg}\n")
            lines.append(f"**Assistant:**\n{bot_msg}\n")
            lines.append("---\n")

        return "\n".join(lines)

    def close(self):
        """Close HTTP clients."""
        self.http_client.close()
        asyncio.create_task(self.async_http_client.aclose())
