"""SQLite metadata database for multi-repository tracking."""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class MetadataDB:
    """Manage SQLite database for repository metadata."""

    def __init__(self, db_path: str = "/app/data/metadata/repos.db"):
        """Initialize metadata database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Repository tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    chroma_collection_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_indexed_at TIMESTAMP,
                    last_commit_hash TEXT,
                    is_active BOOLEAN DEFAULT 0,
                    indexing_status TEXT CHECK(indexing_status IN ('pending', 'in_progress', 'completed', 'failed')),
                    total_chunks INTEGER DEFAULT 0,
                    total_files INTEGER DEFAULT 0,
                    embedding_provider TEXT DEFAULT 'local',
                    embedding_model TEXT DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
                    embedding_dimension INTEGER DEFAULT 384
                )
            """)

            # File tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indexed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    last_indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    chunk_count INTEGER DEFAULT 0,
                    language TEXT,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                    UNIQUE(repo_id, file_path)
                )
            """)

            # Commit tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indexed_commits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id TEXT NOT NULL,
                    commit_hash TEXT NOT NULL,
                    commit_message TEXT,
                    author TEXT,
                    committed_at TIMESTAMP,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    chunk_count INTEGER DEFAULT 0,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                    UNIQUE(repo_id, commit_hash)
                )
            """)

            # Indexing jobs queue
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indexing_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id TEXT NOT NULL,
                    job_type TEXT CHECK(job_type IN ('full', 'incremental', 'file', 'commit')),
                    target_path TEXT,
                    status TEXT CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexed_files_repo ON indexed_files(repo_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexed_files_hash ON indexed_files(file_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexed_commits_repo ON indexed_commits(repo_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_indexing_queue_status ON indexing_queue(status, created_at)")

            # Run migrations for embedding tracking (Phase 1.7)
            self._migrate_embedding_columns(cursor)

            logger.info(f"Database initialized at {self.db_path}")

    def _migrate_embedding_columns(self, cursor):
        """Migrate existing databases to add embedding tracking columns.

        Args:
            cursor: Database cursor
        """
        try:
            # Check if embedding columns exist
            cursor.execute("PRAGMA table_info(repositories)")
            columns = [col[1] for col in cursor.fetchall()]

            # Add missing columns if they don't exist
            if 'embedding_provider' not in columns:
                cursor.execute("ALTER TABLE repositories ADD COLUMN embedding_provider TEXT DEFAULT 'local'")
                logger.info("Added embedding_provider column to repositories table")

            if 'embedding_model' not in columns:
                cursor.execute("ALTER TABLE repositories ADD COLUMN embedding_model TEXT DEFAULT 'sentence-transformers/all-MiniLM-L6-v2'")
                logger.info("Added embedding_model column to repositories table")

            if 'embedding_dimension' not in columns:
                cursor.execute("ALTER TABLE repositories ADD COLUMN embedding_dimension INTEGER DEFAULT 384")
                logger.info("Added embedding_dimension column to repositories table")

        except Exception as e:
            logger.warning(f"Migration check/execution encountered issue: {e}")

    # Repository methods
    def add_repository(self, path: str, name: Optional[str] = None) -> str:
        """Add a new repository to track.

        Args:
            path: Absolute path to repository
            name: Optional name (defaults to directory name)

        Returns:
            Repository ID (UUID)
        """
        repo_path = Path(path).resolve()
        repo_id = str(uuid.uuid4())
        repo_name = name or repo_path.name
        collection_name = f"repo_{repo_id.replace('-', '_')}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO repositories (id, name, path, chroma_collection_name, indexing_status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (repo_id, repo_name, str(repo_path), collection_name))

            logger.info(f"Added repository: {repo_name} ({repo_id})")
            return repo_id

    def get_repository(self, repo_id: str) -> Optional[Dict[str, Any]]:
        """Get repository by ID.

        Args:
            repo_id: Repository UUID

        Returns:
            Repository data dict or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories WHERE id = ?", (repo_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_repository_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get repository by path.

        Args:
            path: Repository path

        Returns:
            Repository data dict or None
        """
        repo_path = str(Path(path).resolve())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories WHERE path = ?", (repo_path,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_repositories(self) -> List[Dict[str, Any]]:
        """List all repositories.

        Returns:
            List of repository dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def set_active_repository(self, repo_id: str):
        """Set a repository as active (deactivate others).

        Args:
            repo_id: Repository UUID to activate
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Deactivate all
            cursor.execute("UPDATE repositories SET is_active = 0")
            # Activate specified
            cursor.execute("UPDATE repositories SET is_active = 1 WHERE id = ?", (repo_id,))
            logger.info(f"Set active repository: {repo_id}")

    def get_active_repository(self) -> Optional[Dict[str, Any]]:
        """Get the currently active repository.

        Returns:
            Active repository dict or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_repository_status(self, repo_id: str, status: str, **kwargs):
        """Update repository status and metadata.

        Args:
            repo_id: Repository UUID
            status: Indexing status
            **kwargs: Additional fields to update
        """
        fields = {"indexing_status": status}
        fields.update(kwargs)

        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [repo_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE repositories SET {set_clause} WHERE id = ?", values)
            logger.debug(f"Updated repository {repo_id}: {fields}")

    def update_repository(self, repo_id: str, **kwargs):
        """Update repository fields.

        Args:
            repo_id: Repository UUID
            **kwargs: Fields to update (e.g., last_indexed_at, total_chunks, indexing_status)
        """
        if not kwargs:
            logger.warning(f"No fields provided to update for repository {repo_id}")
            return

        # Handle CURRENT_TIMESTAMP for timestamp fields
        set_clause_parts = []
        values = []

        for key, value in kwargs.items():
            if value == 'CURRENT_TIMESTAMP':
                set_clause_parts.append(f"{key} = CURRENT_TIMESTAMP")
            else:
                set_clause_parts.append(f"{key} = ?")
                values.append(value)

        set_clause = ", ".join(set_clause_parts)
        values.append(repo_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE repositories SET {set_clause} WHERE id = ?", values)
            logger.debug(f"Updated repository {repo_id}: {kwargs}")

    def update_repository_embedding_info(
        self,
        repo_id: str,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimension: int
    ):
        """Update embedding information for a repository.

        Args:
            repo_id: Repository UUID
            embedding_provider: Embedding provider ('local' or 'openai')
            embedding_model: Model name used for embeddings
            embedding_dimension: Dimension of the embeddings
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE repositories
                SET embedding_provider = ?, embedding_model = ?, embedding_dimension = ?
                WHERE id = ?
            """, (embedding_provider, embedding_model, embedding_dimension, repo_id))
            logger.info(f"Updated embedding info for repository {repo_id}: {embedding_provider}/{embedding_model} ({embedding_dimension}D)")

    def delete_repository(self, repo_id: str):
        """Delete a repository and all associated data.

        Args:
            repo_id: Repository UUID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            logger.info(f"Deleted repository: {repo_id}")

    # File tracking methods
    def upsert_file(self, repo_id: str, file_path: str, file_hash: str,
                    chunk_count: int = 0, language: Optional[str] = None):
        """Insert or update file tracking record.

        Args:
            repo_id: Repository UUID
            file_path: Relative file path
            file_hash: SHA256 hash of file content
            chunk_count: Number of chunks created
            language: Programming language
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO indexed_files (repo_id, file_path, file_hash, chunk_count, language, last_indexed_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(repo_id, file_path) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    chunk_count = excluded.chunk_count,
                    language = excluded.language,
                    last_indexed_at = CURRENT_TIMESTAMP
            """, (repo_id, file_path, file_hash, chunk_count, language))

    def get_file(self, repo_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file tracking record.

        Args:
            repo_id: Repository UUID
            file_path: Relative file path

        Returns:
            File data dict or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM indexed_files
                WHERE repo_id = ? AND file_path = ?
            """, (repo_id, file_path))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_files(self, repo_id: str) -> List[Dict[str, Any]]:
        """List all indexed files for a repository.

        Args:
            repo_id: Repository UUID

        Returns:
            List of file dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM indexed_files
                WHERE repo_id = ?
                ORDER BY last_indexed_at DESC
            """, (repo_id,))
            return [dict(row) for row in cursor.fetchall()]

    # Commit tracking methods
    def upsert_commit(self, repo_id: str, commit_hash: str, commit_message: str,
                      author: str, committed_at: datetime, chunk_count: int = 0):
        """Insert or update commit tracking record.

        Args:
            repo_id: Repository UUID
            commit_hash: Git commit hash
            commit_message: Commit message
            author: Commit author
            committed_at: Commit timestamp
            chunk_count: Number of chunks created
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO indexed_commits (repo_id, commit_hash, commit_message, author, committed_at, chunk_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_id, commit_hash) DO UPDATE SET
                    commit_message = excluded.commit_message,
                    chunk_count = excluded.chunk_count,
                    indexed_at = CURRENT_TIMESTAMP
            """, (repo_id, commit_hash, commit_message, author, committed_at, chunk_count))

    def get_commit(self, repo_id: str, commit_hash: str) -> Optional[Dict[str, Any]]:
        """Get commit tracking record.

        Args:
            repo_id: Repository UUID
            commit_hash: Git commit hash

        Returns:
            Commit data dict or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM indexed_commits
                WHERE repo_id = ? AND commit_hash = ?
            """, (repo_id, commit_hash))
            row = cursor.fetchone()
            return dict(row) if row else None

    # Indexing queue methods
    def add_indexing_job(self, repo_id: str, job_type: str, target_path: Optional[str] = None) -> int:
        """Add a new indexing job to the queue.

        Args:
            repo_id: Repository UUID
            job_type: Job type (full, incremental, file, commit)
            target_path: Optional target file or commit hash

        Returns:
            Job ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO indexing_queue (repo_id, job_type, target_path, status)
                VALUES (?, ?, ?, 'pending')
            """, (repo_id, job_type, target_path))
            return cursor.lastrowid

    def get_pending_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending indexing jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of job dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM indexing_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_job_status(self, job_id: int, status: str, error_message: Optional[str] = None):
        """Update indexing job status.

        Args:
            job_id: Job ID
            status: New status
            error_message: Optional error message
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if status == 'processing':
                cursor.execute("""
                    UPDATE indexing_queue
                    SET status = ?, started_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, job_id))
            elif status in ('completed', 'failed'):
                cursor.execute("""
                    UPDATE indexing_queue
                    SET status = ?, completed_at = CURRENT_TIMESTAMP, error_message = ?
                    WHERE id = ?
                """, (status, error_message, job_id))
            else:
                cursor.execute("""
                    UPDATE indexing_queue
                    SET status = ?
                    WHERE id = ?
                """, (status, job_id))
