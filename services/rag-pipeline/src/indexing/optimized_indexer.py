"""Optimized indexing orchestration with parallel processing."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time

from ..core.git_ops import GitOperations
from ..core.parser import CodeParser
from ..core.chunker import CodeChunker
from ..core.embedder import BaseEmbedder
from ..core.vector_store import VectorStore
from ..db.metadata_db import MetadataDB

logger = logging.getLogger(__name__)


class OptimizedRepositoryIndexer:
    """Optimized indexer with parallel processing and batching."""

    def __init__(
        self,
        metadata_db: MetadataDB,
        vector_store: VectorStore,
        embedder: BaseEmbedder,
        parser: Optional[CodeParser] = None,
        chunker: Optional[CodeChunker] = None,
        max_workers: int = 4,
        batch_size: int = 50
    ):
        """Initialize the optimized indexer.

        Args:
            metadata_db: Metadata database instance
            vector_store: Vector store instance
            embedder: Embedder instance (BaseEmbedder)
            parser: Code parser (optional)
            chunker: Code chunker (optional)
            max_workers: Maximum number of parallel workers
            batch_size: Number of chunks to batch for embedding
        """
        self.metadata_db = metadata_db
        self.vector_store = vector_store
        self.embedder = embedder
        self.parser = parser or CodeParser()
        self.chunker = chunker or CodeChunker()
        self.max_workers = max_workers
        self.batch_size = batch_size

        # Thread-safe counters
        self._lock = Lock()
        self._total_chunks = 0
        self._indexed_files = 0
        self._skipped_files = 0
        self._failed_files = 0

        logger.info(f"Optimized indexer initialized with {max_workers} workers, batch size {batch_size}")

    def index_repository(
        self,
        repo_id: str,
        repo_path: str,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """Index entire repository with parallel processing.

        Args:
            repo_id: Repository UUID
            repo_path: Path to the repository
            force_reindex: If True, reindex all files even if unchanged

        Returns:
            Dictionary with indexing results
        """
        start_time = time.time()
        logger.info(f"Starting optimized repository indexing: {repo_path}")

        # Update indexing status
        self.metadata_db.update_repository(repo_id, indexing_status='in_progress')

        # Reset counters
        self._total_chunks = 0
        self._indexed_files = 0
        self._skipped_files = 0
        self._failed_files = 0

        try:
            # Initialize Git operations
            git_ops = GitOperations(repo_path)

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

            # Filter files that need indexing
            files_to_index = []
            for file_path in tracked_files:
                absolute_file_path = Path(repo_path) / file_path

                # Check if we should index this file
                if not self.chunker.should_index_file(file_path):
                    with self._lock:
                        self._skipped_files += 1
                    continue

                # Check if file has changed (unless force_reindex)
                if not force_reindex:
                    file_hash = self._compute_file_hash(absolute_file_path)
                    existing_file = self.metadata_db.get_file(repo_id, str(file_path))

                    if existing_file and existing_file['file_hash'] == file_hash:
                        logger.debug(f"Skipping unchanged file: {file_path}")
                        with self._lock:
                            self._skipped_files += 1
                        continue

                files_to_index.append((absolute_file_path, file_path, latest_commit))

            logger.info(f"Indexing {len(files_to_index)} files in parallel with {self.max_workers} workers")

            # Process files in parallel
            all_chunks = []
            file_metadata = []

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all files for processing
                future_to_file = {
                    executor.submit(
                        self._process_file,
                        repo_id,
                        absolute_path,
                        relative_path,
                        commit_hash
                    ): (absolute_path, relative_path)
                    for absolute_path, relative_path, commit_hash in files_to_index
                }

                # Collect results as they complete
                for future in as_completed(future_to_file):
                    absolute_path, relative_path = future_to_file[future]
                    try:
                        chunks, metadata = future.result()
                        if chunks:
                            all_chunks.extend(chunks)
                            file_metadata.append(metadata)

                            with self._lock:
                                self._indexed_files += 1

                            if len(all_chunks) % 100 == 0:
                                logger.info(f"Processed {self._indexed_files}/{len(files_to_index)} files, {len(all_chunks)} chunks so far")
                    except Exception as e:
                        logger.error(f"Failed to process file {relative_path}: {e}")
                        with self._lock:
                            self._failed_files += 1

            # Batch embed and store all chunks
            if all_chunks:
                logger.info(f"Embedding and storing {len(all_chunks)} chunks in batches...")
                self._batch_embed_and_store(collection_name, all_chunks)

                with self._lock:
                    self._total_chunks = len(all_chunks)

            # Update file metadata in database
            logger.info("Updating file metadata in database...")
            for metadata in file_metadata:
                self.metadata_db.upsert_file(**metadata)

            # Update repository metadata
            self.metadata_db.update_repository(
                repo_id,
                last_indexed_at='CURRENT_TIMESTAMP',
                last_commit_hash=latest_commit,
                total_chunks=self._total_chunks,
                total_files=self._indexed_files,
                indexing_status='completed'
            )

            elapsed_time = time.time() - start_time
            result = {
                'repo_id': repo_id,
                'repo_path': repo_path,
                'collection_name': collection_name,
                'total_files': len(tracked_files),
                'indexed_files': self._indexed_files,
                'skipped_files': self._skipped_files,
                'failed_files': self._failed_files,
                'total_chunks': self._total_chunks,
                'latest_commit': latest_commit,
                'elapsed_time_seconds': round(elapsed_time, 2),
                'chunks_per_second': round(self._total_chunks / elapsed_time, 2) if elapsed_time > 0 else 0,
                'status': 'completed'
            }

            logger.info(
                f"Repository indexing completed: {self._indexed_files} files, "
                f"{self._total_chunks} chunks in {elapsed_time:.2f}s "
                f"({result['chunks_per_second']:.2f} chunks/sec)"
            )
            return result

        except Exception as e:
            logger.error(f"Repository indexing failed: {e}", exc_info=True)
            self.metadata_db.update_repository(repo_id, indexing_status='failed')
            raise

    def _process_file(
        self,
        repo_id: str,
        file_path: Path,
        relative_path: str,
        commit_hash: Optional[str]
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Process a single file (parse and chunk).

        Args:
            repo_id: Repository UUID
            file_path: Absolute path to file
            relative_path: Relative path from repo root
            commit_hash: Git commit hash

        Returns:
            Tuple of (chunks, file_metadata)
        """
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            logger.warning(f"Skipping binary file: {file_path}")
            return [], {}
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return [], {}

        # Parse file into chunks
        parsed_chunks = self.parser.parse_file(file_path, content)

        # If parser doesn't support this file type, try text chunking
        if not parsed_chunks:
            parsed_chunks = self.chunker.chunk_text(content, file_path)

        # Apply chunking strategy
        final_chunks = self.chunker.chunk_code(parsed_chunks)

        # Add metadata to chunks
        for chunk in final_chunks:
            chunk['commit_hash'] = commit_hash or ''
            chunk['is_uncommitted'] = False

        # Prepare file metadata for DB
        file_hash = self._compute_file_hash(file_path)
        file_metadata = {
            'repo_id': repo_id,
            'file_path': str(file_path),
            'file_hash': file_hash,
            'chunk_count': len(final_chunks),
            'language': parsed_chunks[0].get('language', 'unknown') if parsed_chunks else 'unknown'
        }

        return final_chunks, file_metadata

    def _batch_embed_and_store(
        self,
        collection_name: str,
        chunks: List[Dict[str, Any]]
    ):
        """Embed and store chunks in batches.

        Args:
            collection_name: ChromaDB collection name
            chunks: List of chunks to embed and store
        """
        total_batches = (len(chunks) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1

            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)")

            # Extract texts for embedding
            texts = [chunk['code'] for chunk in batch]

            # Generate embeddings
            try:
                embeddings = self.embedder.embed_batch(texts, show_progress=False)

                # Store in vector database
                self.vector_store.add_chunks(collection_name, batch, embeddings=embeddings)

                logger.debug(f"Batch {batch_num} stored successfully")
            except Exception as e:
                logger.error(f"Failed to process batch {batch_num}: {e}")
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
