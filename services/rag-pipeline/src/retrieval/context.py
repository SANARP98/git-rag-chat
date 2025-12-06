"""Context assembly for LLM prompts."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ContextAssembler:
    """Assemble context from retrieved chunks for LLM prompts."""

    def __init__(self, max_tokens: int = 4000):
        """Initialize context assembler.

        Args:
            max_tokens: Maximum tokens for context (rough estimate)
        """
        self.max_tokens = max_tokens
        self.max_chars = max_tokens * 4  # Rough: 1 token ≈ 4 chars

        logger.info(f"Context assembler initialized (max_tokens={max_tokens})")

    def assemble_context(
        self,
        chunks: List[Dict[str, Any]],
        query: str,
        include_metadata: bool = True,
        include_file_paths: bool = True,
        max_chunks: Optional[int] = None
    ) -> str:
        """Assemble context from retrieved chunks.

        Args:
            chunks: List of retrieved chunks
            query: User's query
            include_metadata: Include metadata annotations
            include_file_paths: Include file paths in context
            max_chunks: Maximum number of chunks to include

        Returns:
            Assembled context string
        """
        if not chunks:
            return ""

        logger.info(f"Assembling context from {len(chunks)} chunks")

        # Limit number of chunks
        if max_chunks:
            chunks = chunks[:max_chunks]

        context_parts = []
        total_chars = 0

        for idx, chunk in enumerate(chunks, 1):
            # Build chunk context
            chunk_text = self._format_chunk(
                chunk,
                idx,
                include_metadata,
                include_file_paths
            )

            # Check if we exceed max chars
            if total_chars + len(chunk_text) > self.max_chars:
                logger.info(f"Reached max chars, stopping at chunk {idx-1}")
                break

            context_parts.append(chunk_text)
            total_chars += len(chunk_text)

        context = "\n\n".join(context_parts)

        logger.info(f"Assembled context: {len(context_parts)} chunks, {total_chars} chars")
        return context

    def assemble_prompt(
        self,
        chunks: List[Dict[str, Any]],
        query: str,
        system_prompt: Optional[str] = None,
        include_instructions: bool = True
    ) -> str:
        """Assemble full prompt with context for LLM.

        Args:
            chunks: Retrieved chunks
            query: User's query
            system_prompt: Optional system prompt override
            include_instructions: Include query instructions

        Returns:
            Complete prompt string
        """
        # Default system prompt
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()

        # Assemble context
        context = self.assemble_context(chunks, query)

        # Build prompt sections
        sections = [system_prompt]

        if context:
            sections.append(f"# Relevant Code Context\n\n{context}")

        if include_instructions:
            sections.append(self._get_query_instructions())

        sections.append(f"# User Query\n\n{query}")

        prompt = "\n\n".join(sections)

        logger.info(f"Assembled prompt: {len(prompt)} chars")
        return prompt

    def assemble_chat_context(
        self,
        chunks: List[Dict[str, Any]],
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Assemble context for chat-based LLM APIs.

        Args:
            chunks: Retrieved chunks
            query: Current query
            conversation_history: Previous messages [{"role": "user/assistant", "content": "..."}]

        Returns:
            Dict with system message and messages list
        """
        context = self.assemble_context(chunks, query, max_chunks=10)

        system_message = f"""{self._get_default_system_prompt()}

# Relevant Code Context

{context}

Use the code context above to answer the user's question accurately."""

        messages = []

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)

        # Add current query
        messages.append({
            "role": "user",
            "content": query
        })

        return {
            "system": system_message,
            "messages": messages
        }

    def _format_chunk(
        self,
        chunk: Dict[str, Any],
        index: int,
        include_metadata: bool,
        include_file_paths: bool
    ) -> str:
        """Format a single chunk for context.

        Args:
            chunk: Chunk dictionary
            index: Chunk index
            include_metadata: Include metadata
            include_file_paths: Include file paths

        Returns:
            Formatted chunk string
        """
        parts = []

        # Header
        header_parts = [f"[{index}]"]

        if include_file_paths:
            file_path = chunk.get('file_path', 'unknown')
            header_parts.append(file_path)

        if include_metadata:
            name = chunk.get('name', '')
            chunk_type = chunk.get('chunk_type', '')
            language = chunk.get('language', '')

            if name and name != 'unknown':
                header_parts.append(f"{chunk_type}: {name}")

            if language and language != 'unknown':
                header_parts.append(f"({language})")

        header = " ".join(header_parts)
        parts.append(header)

        # Code content
        code = chunk.get('code', '')
        language = chunk.get('language', '').lower()

        # Format as code block
        parts.append(f"```{language}\n{code}\n```")

        # Additional metadata
        if include_metadata:
            metadata_items = []

            start_line = chunk.get('start_line')
            end_line = chunk.get('end_line')
            if start_line and end_line:
                metadata_items.append(f"Lines {start_line}-{end_line}")

            similarity = chunk.get('similarity')
            if similarity is not None:
                metadata_items.append(f"Relevance: {similarity:.2%}")

            if metadata_items:
                parts.append(f"({', '.join(metadata_items)})")

        return "\n".join(parts)

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for code Q&A.

        Returns:
            System prompt string
        """
        return """You are an expert programming assistant with deep knowledge of software development.

Your role is to help developers understand their codebase by:
- Answering questions about code functionality and structure
- Explaining complex code patterns and algorithms
- Identifying potential bugs or issues
- Suggesting improvements and best practices
- Providing clear, concise explanations

Use the provided code context to give accurate, relevant answers. If the context doesn't contain enough information, say so clearly.

Always cite specific files and line numbers when referencing code."""

    def _get_query_instructions(self) -> str:
        """Get query-specific instructions.

        Returns:
            Instruction string
        """
        return """# Instructions

Answer the user's query based on the code context provided above. Be specific and reference exact file paths, function names, and line numbers when applicable.

If the context is insufficient to answer the question completely, acknowledge what you can answer and what information is missing."""

    def group_chunks_by_file(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group chunks by file path.

        Args:
            chunks: List of chunks

        Returns:
            Dictionary mapping file paths to chunk lists
        """
        grouped = {}

        for chunk in chunks:
            file_path = chunk.get('file_path', 'unknown')

            if file_path not in grouped:
                grouped[file_path] = []

            grouped[file_path].append(chunk)

        # Sort chunks within each file by line number
        for file_path in grouped:
            grouped[file_path].sort(
                key=lambda c: c.get('start_line', 0)
            )

        return grouped

    def build_file_summary(
        self,
        chunks: List[Dict[str, Any]]
    ) -> str:
        """Build a summary of files in the context.

        Args:
            chunks: List of chunks

        Returns:
            Summary string
        """
        grouped = self.group_chunks_by_file(chunks)

        summary_lines = ["# Files in Context\n"]

        for file_path, file_chunks in grouped.items():
            languages = {c.get('language', 'unknown') for c in file_chunks}
            chunk_types = {c.get('chunk_type', 'unknown') for c in file_chunks}

            summary_lines.append(
                f"- {file_path} ({', '.join(languages)}): "
                f"{len(file_chunks)} chunk(s) - {', '.join(chunk_types)}"
            )

        return "\n".join(summary_lines)

    def estimate_token_count(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4

    def truncate_to_tokens(
        self,
        text: str,
        max_tokens: int,
        preserve_end: bool = False
    ) -> str:
        """Truncate text to approximate token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens
            preserve_end: If True, truncate from start instead of end

        Returns:
            Truncated text
        """
        max_chars = max_tokens * 4

        if len(text) <= max_chars:
            return text

        if preserve_end:
            # Keep end
            truncated = "...\n" + text[-max_chars:]
        else:
            # Keep start
            truncated = text[:max_chars] + "\n..."

        return truncated

    def build_metadata_summary(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build summary statistics about retrieved chunks.

        Args:
            chunks: List of chunks

        Returns:
            Dictionary with summary statistics
        """
        if not chunks:
            return {}

        languages = {}
        chunk_types = {}
        files = set()

        for chunk in chunks:
            lang = chunk.get('language', 'unknown')
            languages[lang] = languages.get(lang, 0) + 1

            ctype = chunk.get('chunk_type', 'unknown')
            chunk_types[ctype] = chunk_types.get(ctype, 0) + 1

            files.add(chunk.get('file_path', 'unknown'))

        avg_similarity = sum(
            c.get('similarity', 0) for c in chunks
        ) / len(chunks)

        return {
            'total_chunks': len(chunks),
            'unique_files': len(files),
            'languages': languages,
            'chunk_types': chunk_types,
            'avg_similarity': avg_similarity,
            'files': sorted(files)
        }
