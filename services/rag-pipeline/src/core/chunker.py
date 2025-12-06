"""Chunking strategies for code and text."""

from typing import List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CodeChunker:
    """Chunk code and text for embedding."""

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 50):
        """Initialize chunker.

        Args:
            max_chunk_size: Maximum chunk size in tokens (approximate with chars/4)
            overlap: Overlap size in tokens for fixed-size chunks
        """
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.max_chars = max_chunk_size * 4  # Rough estimate: 1 token ≈ 4 chars
        self.overlap_chars = overlap * 4

    def chunk_code(self, parsed_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chunk parsed code, splitting large chunks if necessary.

        Args:
            parsed_chunks: List of parsed code chunks from parser

        Returns:
            List of processed chunks (may include sub-chunks)
        """
        processed_chunks = []

        for chunk in parsed_chunks:
            code = chunk['code']
            code_length = len(code)

            # If chunk is small enough, keep as-is
            if code_length <= self.max_chars:
                processed_chunks.append(self._finalize_chunk(chunk))
            else:
                # Split large chunks with overlap
                logger.debug(f"Splitting large chunk: {chunk['name']} ({code_length} chars)")
                sub_chunks = self._split_with_overlap(chunk)
                processed_chunks.extend(sub_chunks)

        return processed_chunks

    def chunk_text(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Chunk plain text files (markdown, documentation, etc.).

        Args:
            content: Text content
            file_path: File path

        Returns:
            List of text chunks
        """
        chunks = []

        # For markdown, try to split by sections (headers)
        if file_path.suffix.lower() in ['.md', '.markdown']:
            chunks = self._chunk_markdown(content, file_path)
        else:
            # Generic text chunking with overlap
            chunks = self._chunk_generic_text(content, file_path)

        return chunks

    def _split_with_overlap(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split a large chunk into smaller chunks with overlap.

        Args:
            chunk: Original chunk

        Returns:
            List of sub-chunks
        """
        code = chunk['code']
        lines = code.split('\n')
        sub_chunks = []

        # Calculate lines per chunk (approximate)
        avg_line_length = len(code) / len(lines) if lines else 100
        lines_per_chunk = int(self.max_chars / avg_line_length) if avg_line_length > 0 else 50
        overlap_lines = int(self.overlap_chars / avg_line_length) if avg_line_length > 0 else 5

        i = 0
        part_num = 1
        while i < len(lines):
            # Get chunk lines with overlap
            end_idx = min(i + lines_per_chunk, len(lines))
            chunk_lines = lines[i:end_idx]

            # Create sub-chunk
            sub_code = '\n'.join(chunk_lines)
            sub_chunk = chunk.copy()
            sub_chunk['code'] = sub_code
            sub_chunk['name'] = f"{chunk['name']}_part{part_num}"
            sub_chunk['start_line'] = chunk['start_line'] + i
            sub_chunk['end_line'] = chunk['start_line'] + end_idx - 1
            sub_chunk['line_count'] = len(chunk_lines)
            sub_chunk['is_partial'] = True
            sub_chunk['part_number'] = part_num
            sub_chunk['parent_chunk'] = chunk['name']

            sub_chunks.append(self._finalize_chunk(sub_chunk))

            # Move to next chunk with overlap
            i += lines_per_chunk - overlap_lines
            part_num += 1

        return sub_chunks

    def _chunk_markdown(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Chunk markdown content by sections (headers).

        Args:
            content: Markdown content
            file_path: File path

        Returns:
            List of markdown chunks
        """
        chunks = []
        lines = content.split('\n')
        current_section = []
        section_header = None
        start_line = 1

        for i, line in enumerate(lines, 1):
            # Detect markdown headers (# Header)
            if line.strip().startswith('#'):
                # Save previous section
                if current_section:
                    section_text = '\n'.join(current_section)
                    if len(section_text.strip()) > 0:
                        chunks.append({
                            'code': section_text,
                            'chunk_type': 'section',
                            'name': section_header or 'intro',
                            'file_path': str(file_path),
                            'language': 'markdown',
                            'start_line': start_line,
                            'end_line': i - 1,
                            'line_count': len(current_section)
                        })

                # Start new section
                section_header = line.strip().lstrip('#').strip()
                current_section = [line]
                start_line = i
            else:
                current_section.append(line)

            # Split if section gets too large
            if len('\n'.join(current_section)) > self.max_chars and current_section:
                section_text = '\n'.join(current_section)
                chunks.append({
                    'code': section_text,
                    'chunk_type': 'section',
                    'name': section_header or 'content',
                    'file_path': str(file_path),
                    'language': 'markdown',
                    'start_line': start_line,
                    'end_line': i,
                    'line_count': len(current_section)
                })
                current_section = []
                start_line = i + 1

        # Add final section
        if current_section:
            section_text = '\n'.join(current_section)
            if len(section_text.strip()) > 0:
                chunks.append({
                    'code': section_text,
                    'chunk_type': 'section',
                    'name': section_header or 'content',
                    'file_path': str(file_path),
                    'language': 'markdown',
                    'start_line': start_line,
                    'end_line': len(lines),
                    'line_count': len(current_section)
                })

        return [self._finalize_chunk(chunk) for chunk in chunks]

    def _chunk_generic_text(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Chunk generic text with fixed-size and overlap.

        Args:
            content: Text content
            file_path: File path

        Returns:
            List of text chunks
        """
        chunks = []
        lines = content.split('\n')

        # Estimate lines per chunk
        avg_line_length = len(content) / len(lines) if lines else 100
        lines_per_chunk = int(self.max_chars / avg_line_length) if avg_line_length > 0 else 50
        overlap_lines = int(self.overlap_chars / avg_line_length) if avg_line_length > 0 else 5

        i = 0
        part_num = 1
        while i < len(lines):
            end_idx = min(i + lines_per_chunk, len(lines))
            chunk_lines = lines[i:end_idx]
            chunk_text = '\n'.join(chunk_lines)

            chunks.append({
                'code': chunk_text,
                'chunk_type': 'text',
                'name': f"{file_path.stem}_part{part_num}",
                'file_path': str(file_path),
                'language': 'text',
                'start_line': i + 1,
                'end_line': end_idx,
                'line_count': len(chunk_lines)
            })

            i += lines_per_chunk - overlap_lines
            part_num += 1

        return [self._finalize_chunk(chunk) for chunk in chunks]

    def _finalize_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize chunk by adding computed fields.

        Args:
            chunk: Chunk dictionary

        Returns:
            Finalized chunk with additional metadata
        """
        # Add character count
        chunk['char_count'] = len(chunk['code'])

        # Estimate token count (rough: chars / 4)
        chunk['token_count_estimate'] = chunk['char_count'] // 4

        # Add preview (first 100 chars)
        chunk['preview'] = chunk['code'][:100] + '...' if len(chunk['code']) > 100 else chunk['code']

        return chunk

    def should_index_file(self, file_path: Path) -> bool:
        """Determine if a file should be indexed.

        Args:
            file_path: Path to file

        Returns:
            True if file should be indexed
        """
        # Skip binary files
        binary_extensions = {
            '.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe',
            '.jpg', '.jpeg', '.png', '.gif', '.ico', '.pdf',
            '.zip', '.tar', '.gz', '.bz2', '.xz',
            '.db', '.sqlite', '.sqlite3'
        }

        if file_path.suffix.lower() in binary_extensions:
            return False

        # Skip hidden files (except .gitignore, etc.)
        if file_path.name.startswith('.') and file_path.name not in {'.gitignore', '.env.example'}:
            return False

        # Skip common non-code directories
        skip_dirs = {'node_modules', '__pycache__', '.git', '.venv', 'venv', 'env', 'dist', 'build'}
        if any(part in skip_dirs for part in file_path.parts):
            return False

        return True
