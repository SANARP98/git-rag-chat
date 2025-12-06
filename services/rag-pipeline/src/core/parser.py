"""Code parser using tree-sitter for AST-based parsing."""

import tree_sitter
from tree_sitter import Language, Parser
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CodeParser:
    """Parse code files using tree-sitter to extract semantic chunks."""

    # Supported language file extensions
    LANGUAGE_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'cpp',
        '.hpp': 'cpp',
    }

    def __init__(self):
        """Initialize code parser.

        Note: For initial implementation, we'll use a simplified approach.
        Full tree-sitter integration requires building language libraries.
        """
        self.parsers = {}
        logger.info("Code parser initialized")

    def detect_language(self, file_path: Path) -> Optional[str]:
        """Detect programming language from file extension.

        Args:
            file_path: Path to file

        Returns:
            Language name or None
        """
        suffix = file_path.suffix.lower()
        return self.LANGUAGE_EXTENSIONS.get(suffix)

    def parse_file(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Parse a code file and extract semantic chunks.

        Args:
            file_path: Path to file
            content: File content

        Returns:
            List of parsed chunks with metadata
        """
        language = self.detect_language(file_path)

        if not language:
            logger.debug(f"Unsupported file type: {file_path.suffix}")
            return []

        # For now, use a simplified parsing approach
        # TODO: Integrate actual tree-sitter parsing
        if language == 'python':
            return self._parse_python_simple(content, file_path)
        elif language in ['javascript', 'typescript']:
            return self._parse_javascript_simple(content, file_path)
        else:
            return self._parse_generic(content, file_path, language)

    def _parse_python_simple(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Simple Python parser (line-based).

        This is a simplified implementation. For production, use tree-sitter AST parsing.

        Args:
            content: Python code
            file_path: File path

        Returns:
            List of code chunks
        """
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        chunk_type = None
        chunk_name = None
        start_line = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Detect function or class definitions
            if stripped.startswith('def ') or stripped.startswith('class '):
                # Save previous chunk if exists
                if current_chunk:
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk),
                        chunk_type or 'code',
                        chunk_name or 'unknown',
                        file_path,
                        start_line,
                        i - 1
                    ))

                # Start new chunk
                current_chunk = [line]
                start_line = i
                if stripped.startswith('def '):
                    chunk_type = 'function'
                    chunk_name = stripped.split('(')[0].replace('def ', '').strip()
                else:
                    chunk_type = 'class'
                    chunk_name = stripped.split('(')[0].replace('class ', '').replace(':', '').strip()
            elif current_chunk:
                current_chunk.append(line)

        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                '\n'.join(current_chunk),
                chunk_type or 'code',
                chunk_name or 'unknown',
                file_path,
                start_line,
                len(lines)
            ))

        return chunks

    def _parse_javascript_simple(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Simple JavaScript/TypeScript parser (line-based).

        Args:
            content: JavaScript/TypeScript code
            file_path: File path

        Returns:
            List of code chunks
        """
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        chunk_type = None
        chunk_name = None
        start_line = 0
        brace_count = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Detect function definitions
            if 'function ' in stripped or '=>' in stripped or stripped.startswith('class '):
                if current_chunk and brace_count == 0:
                    # Save previous chunk
                    chunks.append(self._create_chunk(
                        '\n'.join(current_chunk),
                        chunk_type or 'code',
                        chunk_name or 'unknown',
                        file_path,
                        start_line,
                        i - 1
                    ))
                    current_chunk = []

                start_line = i if not current_chunk else start_line
                if 'function' in stripped:
                    chunk_type = 'function'
                    # Extract function name
                    if 'function ' in stripped:
                        chunk_name = stripped.split('function ')[1].split('(')[0].strip()
                    else:
                        chunk_name = stripped.split('=')[0].strip()
                elif 'class ' in stripped:
                    chunk_type = 'class'
                    chunk_name = stripped.split('class ')[1].split('{')[0].strip()

            if current_chunk or stripped:
                current_chunk.append(line)
                brace_count += stripped.count('{') - stripped.count('}')

        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                '\n'.join(current_chunk),
                chunk_type or 'code',
                chunk_name or 'unknown',
                file_path,
                start_line,
                len(lines)
            ))

        return chunks

    def _parse_generic(self, content: str, file_path: Path, language: str) -> List[Dict[str, Any]]:
        """Generic parser for unsupported languages.

        Args:
            content: Code content
            file_path: File path
            language: Language name

        Returns:
            List with single chunk (entire file)
        """
        return [self._create_chunk(
            content,
            'file',
            file_path.stem,
            file_path,
            1,
            len(content.split('\n'))
        )]

    def _create_chunk(self, code: str, chunk_type: str, name: str,
                      file_path: Path, start_line: int, end_line: int) -> Dict[str, Any]:
        """Create a code chunk with metadata.

        Args:
            code: Code content
            chunk_type: Type of chunk (function, class, file, etc.)
            name: Name of the chunk
            file_path: File path
            start_line: Starting line number
            end_line: Ending line number

        Returns:
            Chunk dictionary
        """
        language = self.detect_language(file_path)

        return {
            'code': code,
            'chunk_type': chunk_type,
            'name': name,
            'file_path': str(file_path),
            'language': language,
            'start_line': start_line,
            'end_line': end_line,
            'line_count': end_line - start_line + 1
        }

    def extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from code.

        Args:
            content: Code content
            language: Programming language

        Returns:
            List of import statements
        """
        imports = []
        lines = content.split('\n')

        if language == 'python':
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('from '):
                    imports.append(stripped)

        elif language in ['javascript', 'typescript']:
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('require('):
                    imports.append(stripped)

        return imports
