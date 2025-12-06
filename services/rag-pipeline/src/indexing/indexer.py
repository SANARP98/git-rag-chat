"""Main indexing orchestration for Git repositories."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib

from ..core.git_ops import GitOperations
from ..core.parser import CodeParser
from ..core.chunker import CodeChunker
from ..core.embedder import Embedder
from ..core.vector_store import VectorStore
from ..db.metadata_db import MetadataDB

logger = logging.getLogger(__name__)


class RepositoryIndexer:
    """Orchestrates the indexing of Git repositories into ChromaDB."""

    def __init__(
        self,
        metadata_db: MetadataDB,
        vector_store: VectorStore,
        embedder: Embedder,
        parser: Optional[CodeParser] = None,
        chunker: Optional[CodeChunker] = None
    ):
        """Initialize the indexer.

        Args:
            metadata_db: Metadata database instance
            vector_store: Vector store instance
            embedder: Embedder instance
            parser: Code parser (optional, creates new if not provided)
            chunker: Code chunker (optional, creates new if not provided)
        """
        self.metadata_db = metadata_db
        self.vector_store = vector_store
        self.embedder = embedder
        self.parser = parser or CodeParser()
        self.chunker = chunker or CodeChunker()

        logger.info("Repository indexer initialized")

    def index_repository(
        self,
        repo_id: str,
        repo_path: str,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """Index an entire repository.

        Args:
            repo_id: Repository UUID
            repo_path: Path to the repository
            force_reindex: If True, reindex all files even if unchanged

        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Starting full repository indexing: {repo_path}")

        # Update indexing status
        self.metadata_db.update_repository(
            repo_id,
            indexing_status='in_progress'
        )

        try:
            # Initialize Git operations
            git_ops = GitOperations(repo_path)

            # Verify it's a valid Git repository
            if not git_ops.is_git_repository(repo_path):
                raise ValueError(f"Not a valid Git repository: {repo_path}")

            # Get repository info
            repo_info = self.metadata_db.get_repository(repo_id)
            if not repo_info:
                raise ValueError(f"Repository not found: {repo_id}")

            collection_name = repo_info['chroma_collection_name']

            # Get all tracked files
            tracked_files = git_ops.get_tracked_files()
            logger.info(f"Found {len(tracked_files)} tracked files")

            # Get latest commit hash
            commits = git_ops.get_commit_history(max_count=1)
            latest_commit = commits[0]['hash'] if commits else None

            # Process files
            total_chunks = 0
            indexed_files = 0
            skipped_files = 0

            for file_path in tracked_files:
                # Check if we should index this file
                if not self.chunker.should_index_file(file_path):
                    skipped_files += 1
                    continue

                # Check if file has changed (unless force_reindex)
                if not force_reindex:
                    file_hash = self._compute_file_hash(file_path)
                    existing_file = self.metadata_db.get_file(repo_id, str(file_path))

                    if existing_file and existing_file['file_hash'] == file_hash:
                        logger.debug(f"Skipping unchanged file: {file_path}")
                        skipped_files += 1
                        continue

                # Index the file
                try:
                    chunks_added = self._index_file(
                        repo_id=repo_id,
                        collection_name=collection_name,
                        file_path=file_path,
                        commit_hash=latest_commit,
                        is_uncommitted=False
                    )

                    total_chunks += chunks_added
                    indexed_files += 1

                except Exception as e:
                    logger.error(f"Failed to index file {file_path}: {e}")
                    continue

            # Update repository metadata
            self.metadata_db.update_repository(
                repo_id,
                last_indexed_at='CURRENT_TIMESTAMP',
                last_commit_hash=latest_commit,
                total_chunks=total_chunks,
                total_files=indexed_files,
                indexing_status='completed'
            )

            result = {
                'repo_id': repo_id,
                'repo_path': repo_path,
                'collection_name': collection_name,
                'total_files': len(tracked_files),
                'indexed_files': indexed_files,
                'skipped_files': skipped_files,
                'total_chunks': total_chunks,
                'latest_commit': latest_commit,
                'status': 'completed'
            }

            logger.info(f"Repository indexing completed: {indexed_files} files, {total_chunks} chunks")
            return result

        except Exception as e:
            logger.error(f"Repository indexing failed: {e}")

            # Update status to failed
            self.metadata_db.update_repository(
                repo_id,
                indexing_status='failed'
            )

            raise

    def index_file(
        self,
        repo_id: str,
        file_path: str,
        is_uncommitted: bool = False
    ) -> int:
        """Index a single file.

        Args:
            repo_id: Repository UUID
            file_path: Path to the file (relative or absolute)
            is_uncommitted: Whether this is an uncommitted change

        Returns:
            Number of chunks indexed
        """
        logger.info(f"Indexing file: {file_path}")

        try:
            # Get repository info
            repo_info = self.metadata_db.get_repository(repo_id)
            if not repo_info:
                raise ValueError(f"Repository not found: {repo_id}")

            collection_name = repo_info['chroma_collection_name']
            repo_path = Path(repo_info['path'])

            # Resolve file path
            file_path = Path(file_path)
            if not file_path.is_absolute():
                file_path = repo_path / file_path

            # Get latest commit hash
            git_ops = GitOperations(str(repo_path))
            commits = git_ops.get_commit_history(max_count=1)
            latest_commit = commits[0]['hash'] if commits else None

            # Index the file
            chunks_added = self._index_file(
                repo_id=repo_id,
                collection_name=collection_name,
                file_path=file_path,
                commit_hash=latest_commit,
                is_uncommitted=is_uncommitted
            )

            logger.info(f"File indexed: {chunks_added} chunks")
            return chunks_added

        except Exception as e:
            logger.error(f"Failed to index file {file_path}: {e}")
            raise

    def _index_file(
        self,
        repo_id: str,
        collection_name: str,
        file_path: Path,
        commit_hash: Optional[str] = None,
        is_uncommitted: bool = False
    ) -> int:
        """Internal method to index a single file.

        Args:
            repo_id: Repository UUID
            collection_name: ChromaDB collection name
            file_path: Path to the file
            commit_hash: Commit hash (if committed)
            is_uncommitted: Whether this is an uncommitted change

        Returns:
            Number of chunks indexed
        """
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            logger.warning(f"Skipping binary file: {file_path}")
            return 0
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return 0

        # Parse file into chunks
        parsed_chunks = self.parser.parse_file(file_path, content)

        # If parser doesn't support this file type, try text chunking
        if not parsed_chunks:
            parsed_chunks = self.chunker.chunk_text(content, file_path)

        # Apply chunking strategy (may split large chunks)
        final_chunks = self.chunker.chunk_code(parsed_chunks)

        # Add metadata to chunks
        for chunk in final_chunks:
            chunk['commit_hash'] = commit_hash or ''
            chunk['is_uncommitted'] = is_uncommitted

        # Add chunks to vector store
        if final_chunks:
            self.vector_store.add_chunks(collection_name, final_chunks)

            # Update file tracking in metadata DB
            file_hash = self._compute_file_hash(file_path)
            self.metadata_db.upsert_file(
                repo_id=repo_id,
                file_path=str(file_path),
                file_hash=file_hash,
                chunk_count=len(final_chunks),
                language=parsed_chunks[0].get('language', 'unknown') if parsed_chunks else 'unknown'
            )

        return len(final_chunks)

    def delete_file_chunks(
        self,
        repo_id: str,
        file_path: str
    ) -> bool:
        """Delete all chunks for a specific file.

        Args:
            repo_id: Repository UUID
            file_path: Path to the file

        Returns:
            True if successful
        """
        logger.info(f"Deleting chunks for file: {file_path}")

        try:
            # Get repository info
            repo_info = self.metadata_db.get_repository(repo_id)
            if not repo_info:
                raise ValueError(f"Repository not found: {repo_id}")

            collection_name = repo_info['chroma_collection_name']

            # Delete chunks from vector store using metadata filter
            self.vector_store.delete_chunks(
                collection_name,
                where={'file_path': str(file_path)}
            )

            # Delete file from metadata DB
            # Note: metadata_db doesn't have a delete_file method yet
            # This would need to be added to metadata_db.py

            logger.info(f"Deleted chunks for file: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete file chunks: {e}")
            return False

    def incremental_index(
        self,
        repo_id: str
    ) -> Dict[str, Any]:
        """Perform incremental indexing (only modified files).

        Args:
            repo_id: Repository UUID

        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Starting incremental indexing for repo: {repo_id}")

        try:
            # Get repository info
            repo_info = self.metadata_db.get_repository(repo_id)
            if not repo_info:
                raise ValueError(f"Repository not found: {repo_id}")

            repo_path = repo_info['path']
            collection_name = repo_info['chroma_collection_name']

            # Initialize Git operations
            git_ops = GitOperations(repo_path)

            # Get modified files (uncommitted changes)
            modified_files = git_ops.get_modified_files()
            logger.info(f"Found {len(modified_files)} modified files")

            total_chunks = 0
            indexed_files = 0

            for file_path_str in modified_files:
                file_path = Path(repo_path) / file_path_str

                if not self.chunker.should_index_file(file_path):
                    continue

                try:
                    # Delete old chunks for this file
                    self.delete_file_chunks(repo_id, str(file_path))

                    # Re-index the file
                    chunks_added = self._index_file(
                        repo_id=repo_id,
                        collection_name=collection_name,
                        file_path=file_path,
                        commit_hash=None,
                        is_uncommitted=True
                    )

                    total_chunks += chunks_added
                    indexed_files += 1

                except Exception as e:
                    logger.error(f"Failed to index modified file {file_path}: {e}")
                    continue

            result = {
                'repo_id': repo_id,
                'indexed_files': indexed_files,
                'total_chunks': total_chunks,
                'status': 'completed'
            }

            logger.info(f"Incremental indexing completed: {indexed_files} files, {total_chunks} chunks")
            return result

        except Exception as e:
            logger.error(f"Incremental indexing failed: {e}")
            raise

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            SHA256 hash as hex string
        """
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to compute hash for {file_path}: {e}")
            return ''

    def get_indexing_stats(self, repo_id: str) -> Dict[str, Any]:
        """Get indexing statistics for a repository.

        Args:
            repo_id: Repository UUID

        Returns:
            Dictionary with statistics
        """
        try:
            # Get repository info
            repo_info = self.metadata_db.get_repository(repo_id)
            if not repo_info:
                raise ValueError(f"Repository not found: {repo_id}")

            # Get collection stats from vector store
            collection_stats = self.vector_store.get_collection_stats(
                repo_info['chroma_collection_name']
            )

            # Combine with metadata DB stats
            stats = {
                'repo_id': repo_id,
                'repo_name': repo_info['name'],
                'repo_path': repo_info['path'],
                'total_files': repo_info.get('total_files', 0),
                'total_chunks': repo_info.get('total_chunks', 0),
                'last_indexed_at': repo_info.get('last_indexed_at'),
                'last_commit_hash': repo_info.get('last_commit_hash'),
                'indexing_status': repo_info.get('indexing_status', 'unknown'),
                'chroma_chunk_count': collection_stats.get('count', 0),
                'collection_name': repo_info['chroma_collection_name']
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get indexing stats: {e}")
            return {}
