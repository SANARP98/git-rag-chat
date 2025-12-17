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
        """Simple Python parser (line-based) with enhanced metadata extraction.

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
        chunk_signature = None
        chunk_decorators = []
        chunk_docstring = None
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
                        i - 1,
                        signature=chunk_signature,
                        decorators=chunk_decorators,
                        docstring=chunk_docstring
                    ))

                # Extract signature info for new chunk
                sig_info = self._extract_function_signature(lines, i - 1)

                # Start new chunk
                current_chunk = [line]
                start_line = i
                chunk_decorators = sig_info['decorators']
                chunk_signature = sig_info['signature']
                chunk_docstring = sig_info['docstring']

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
                len(lines),
                signature=chunk_signature,
                decorators=chunk_decorators,
                docstring=chunk_docstring
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

    def _extract_function_signature(self, lines: List[str], start_idx: int) -> Dict[str, str]:
        """Extract complete function signature with decorators and docstring.

        Args:
            lines: All lines of code
            start_idx: Index of the function/class definition line (0-based)

        Returns:
            Dictionary with signature, decorators, and docstring
        """
        result = {
            'signature': '',
            'decorators': [],
            'docstring': ''
        }

        # Look backward for decorators (@decorator)
        i = start_idx - 1
        while i >= 0 and lines[i].strip().startswith('@'):
            result['decorators'].insert(0, lines[i].strip())
            i -= 1

        # Get function signature (may span multiple lines for long params)
        sig_lines = []
        paren_count = 0
        i = start_idx
        while i < len(lines):
            line = lines[i]
            sig_lines.append(line)
            paren_count += line.count('(') - line.count(')')
            if paren_count == 0 and ':' in line:
                break
            i += 1
        result['signature'] = '\n'.join(sig_lines)

        # Extract docstring (if follows immediately)
        next_idx = i + 1
        if next_idx < len(lines):
            next_line = lines[next_idx].strip()
            if next_line.startswith('"""') or next_line.startswith("'''"):
                quote = '"""' if '"""' in next_line else "'''"
                # Handle single-line and multi-line docstrings
                if next_line.count(quote) >= 2:
                    result['docstring'] = next_line.strip(quote).strip()
                else:
                    docstring_lines = [next_line.strip(quote)]
                    i = next_idx + 1
                    while i < len(lines) and quote not in lines[i]:
                        docstring_lines.append(lines[i].strip())
                        i += 1
                    if i < len(lines):
                        docstring_lines.append(lines[i].strip(quote))
                    result['docstring'] = ' '.join(docstring_lines).strip()

        return result

    def _parse_signature_components(self, signature: str, language: str) -> Dict[str, str]:
        """Parse signature into searchable components.

        Args:
            signature: Function signature string
            language: Programming language

        Returns:
            Dictionary with params, return_type, param_count
        """
        result = {'params': '', 'return_type': '', 'param_count': '0'}

        if not signature:
            return result

        if language == 'python':
            # Extract parameters
            if '(' in signature and ')' in signature:
                params_str = signature[signature.index('(') + 1:signature.rindex(')')]
                result['params'] = params_str.strip()
                if params_str.strip():
                    param_count = len([p for p in params_str.split(',') if p.strip() and p.strip() != 'self'])
                    result['param_count'] = str(param_count)

            # Extract return type
            if '->' in signature:
                return_type = signature.split('->')[1].split(':')[0].strip()
                result['return_type'] = return_type

        return result

    def _extract_imports_from_chunk(self, code: str, language: str) -> List[str]:
        """Extract import statements relevant to this chunk.

        Args:
            code: Code chunk
            language: Programming language

        Returns:
            List of import statements
        """
        imports = []
        lines = code.split('\n')

        for line in lines:
            stripped = line.strip()
            if language == 'python':
                if stripped.startswith('import ') or stripped.startswith('from '):
                    imports.append(stripped)
            elif language in ['javascript', 'typescript']:
                if stripped.startswith('import ') or stripped.startswith('require('):
                    imports.append(stripped)

        return imports

    def _create_chunk(self, code: str, chunk_type: str, name: str,
                      file_path: Path, start_line: int, end_line: int,
                      signature: Optional[str] = None,
                      decorators: Optional[List[str]] = None,
                      docstring: Optional[str] = None) -> Dict[str, Any]:
        """Create a code chunk with enhanced metadata (Phase 2).

        Args:
            code: Code content
            chunk_type: Type of chunk (function, class, file, etc.)
            name: Name of the chunk
            file_path: File path
            start_line: Starting line number
            end_line: Ending line number
            signature: Function/class signature (optional)
            decorators: List of decorators (optional)
            docstring: Docstring content (optional)

        Returns:
            Chunk dictionary with enhanced metadata
        """
        language = self.detect_language(file_path)

        chunk = {
            'code': code,
            'chunk_type': chunk_type,
            'name': name,
            'file_path': str(file_path),
            'language': language,
            'start_line': start_line,
            'end_line': end_line,
            'line_count': end_line - start_line + 1
        }

        # Phase 2: Enhanced metadata
        if signature:
            sig_components = self._parse_signature_components(signature, language)
            chunk['signature'] = signature
            chunk['signature_params'] = sig_components['params']
            chunk['signature_return'] = sig_components['return_type']
            chunk['param_count'] = sig_components['param_count']

        if decorators:
            chunk['decorators'] = decorators

        if docstring:
            chunk['docstring'] = docstring.split('\n')[0][:200]  # First line, max 200 chars
            chunk['docstring_full'] = docstring[:500]  # Full text, truncated
            chunk['has_docstring'] = True

        # Extract imports from chunk
        imports = self._extract_imports_from_chunk(code, language)
        if imports:
            chunk['imports'] = imports

        return chunk

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
