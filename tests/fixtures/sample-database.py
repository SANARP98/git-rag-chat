"""Sample Python code for testing - Database Module."""

import sqlite3
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class DatabaseConnection:
    """Manages SQLite database connections."""

    def __init__(self, db_path: str):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self):
        """Establish database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row

    def disconnect(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    @contextmanager
    def get_cursor(self):
        """Get database cursor with context manager.

        Yields:
            Database cursor
        """
        self.connect()
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()


class UserRepository:
    """Repository for user data operations."""

    def __init__(self, db_connection: DatabaseConnection):
        """Initialize user repository.

        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection
        self._create_tables()

    def _create_tables(self):
        """Create user tables if they don't exist."""
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def create_user(self, username: str, email: str, password_hash: str) -> int:
        """Create a new user.

        Args:
            username: Username
            email: Email address
            password_hash: Hashed password

        Returns:
            User ID

        Raises:
            sqlite3.IntegrityError: If username or email already exists
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            return cursor.lastrowid

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username.

        Args:
            username: Username to search for

        Returns:
            User data dict or None if not found
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT id, username, email, password_hash, created_at FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()

            if row:
                return dict(row)

            return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email.

        Args:
            email: Email address to search for

        Returns:
            User data dict or None if not found
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT id, username, email, password_hash, created_at FROM users WHERE email = ?",
                (email,)
            )
            row = cursor.fetchone()

            if row:
                return dict(row)

            return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users.

        Returns:
            List of user data dicts
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "SELECT id, username, email, created_at FROM users ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def update_password(self, username: str, new_password_hash: str) -> bool:
        """Update user password.

        Args:
            username: Username
            new_password_hash: New hashed password

        Returns:
            True if updated successfully
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (new_password_hash, username)
            )
            return cursor.rowcount > 0

    def delete_user(self, username: str) -> bool:
        """Delete user.

        Args:
            username: Username to delete

        Returns:
            True if deleted successfully
        """
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            return cursor.rowcount > 0
