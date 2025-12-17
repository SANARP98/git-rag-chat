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
        """Smart splitting at logical boundaries (empty lines, comments, block endings).

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

        # Find logical split points
        split_points = self._find_split_points(lines, lines_per_chunk)

        prev_end = 0
        for idx, split_point in enumerate(split_points, 1):
            # Add overlap from previous chunk
            overlap_start = max(0, prev_end - int(self.overlap_chars / avg_line_length))
            chunk_lines = lines[overlap_start:split_point]

            sub_code = '\n'.join(chunk_lines)
            sub_chunk = chunk.copy()
            sub_chunk['code'] = sub_code
            sub_chunk['name'] = f"{chunk['name']}_part{idx}"
            sub_chunk['start_line'] = chunk['start_line'] + overlap_start
            sub_chunk['end_line'] = chunk['start_line'] + split_point - 1
            sub_chunk['line_count'] = len(chunk_lines)
            sub_chunk['is_partial'] = True
            sub_chunk['part_number'] = idx
            sub_chunk['parent_chunk'] = chunk['name']

            # Preserve signature in split chunks
            if 'signature' in chunk:
                sub_chunk['parent_signature'] = chunk['signature']
            if 'docstring' in chunk and idx == 1:
                sub_chunk['docstring'] = chunk['docstring']

            sub_chunks.append(self._finalize_chunk(sub_chunk))
            prev_end = split_point

        return sub_chunks

    def _find_split_points(self, lines: List[str], target_chunk_size: int) -> List[int]:
        """Find logical split points (empty lines, comments, block endings).

        Args:
            lines: List of code lines
            target_chunk_size: Target number of lines per chunk

        Returns:
            List of line indices where splits should occur
        """
        split_points = []
        current_pos = 0

        while current_pos < len(lines):
            target_pos = min(current_pos + target_chunk_size, len(lines))

            # Search for best split point within a window around target position
            window = 10
            search_start = max(current_pos + target_chunk_size - window, current_pos)
            search_end = min(target_pos + window, len(lines))

            best_split = target_pos
            best_score = 0

            for i in range(search_start, search_end):
                score = self._score_split_point(lines, i)
                if score > best_score:
                    best_score = score
                    best_split = i

            split_points.append(best_split)
            current_pos = best_split

        return split_points

    def _score_split_point(self, lines: List[str], idx: int) -> int:
        """Score split point quality (higher = better).

        Args:
            lines: List of code lines
            idx: Line index to score

        Returns:
            Score (0-10, higher is better)
        """
        if idx >= len(lines):
            return 0

        line = lines[idx].strip()

        # Empty line - perfect split
        if not line:
            return 10

        # Comment - good split
        if line.startswith('#') or line.startswith('//') or line.startswith('/*'):
            return 8

        # Check for dedent (block boundary)
        if idx + 1 < len(lines):
            current_indent = len(lines[idx]) - len(lines[idx].lstrip())
            next_indent = len(lines[idx + 1]) - len(lines[idx + 1].lstrip())
            if next_indent < current_indent:
                return 7

        # Closing brace/bracket/return
        if line in ['}', ')', ']'] or line.startswith('return') or line.startswith('}'):
            return 6

        # Regular line
        return 1

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
        """Finalize chunk by adding computed fields and complexity metrics (Phase 2).

        Args:
            chunk: Chunk dictionary

        Returns:
            Finalized chunk with additional metadata
        """
        code = chunk['code']

        # Existing metrics
        chunk['char_count'] = len(code)
        chunk['token_count_estimate'] = chunk['char_count'] // 4
        chunk['preview'] = code[:100] + '...' if len(code) > 100 else code

        # Phase 2: Complexity estimation
        lines = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]

        # Base complexity: lines of code
        complexity = len(lines)

        # Conditionals add complexity
        complexity += code.count('if ') * 2
        complexity += code.count('elif ') * 2
        complexity += code.count('else:') * 1

        # Loops add significant complexity
        complexity += code.count('for ') * 3
        complexity += code.count('while ') * 3

        # Error handling adds complexity
        complexity += code.count('try:') * 2
        complexity += code.count('except ') * 2

        # Function calls and complexity indicators
        complexity += code.count('lambda ') * 2
        complexity += code.count('yield ') * 2

        chunk['complexity_estimate'] = min(complexity, 1000)  # Cap at 1000
        chunk['loc'] = len(lines)  # Lines of code (non-comment, non-blank)

        # Phase 2: Function classification (if it's a function chunk)
        if chunk.get('chunk_type') == 'function':
            chunk['is_public'] = not chunk.get('name', '').startswith('_')
            chunk['is_property'] = '@property' in ' '.join(chunk.get('decorators', []))
            chunk['is_async'] = 'async def' in chunk.get('signature', '')
        else:
            chunk['is_public'] = True  # Classes and other chunks default to public
            chunk['is_property'] = False
            chunk['is_async'] = False

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
