"""Sample Python code for testing - Authentication Module."""

import hashlib
import secrets
from typing import Optional, Dict


class User:
    """User model class."""

    def __init__(self, username: str, email: str):
        """Initialize user.

        Args:
            username: Username
            email: Email address
        """
        self.username = username
        self.email = email
        self.password_hash: Optional[str] = None
        self.session_token: Optional[str] = None

    def set_password(self, password: str):
        """Set user password with hashing.

        Args:
            password: Plain text password
        """
        # Use SHA-256 for password hashing (simplified for demo)
        salt = secrets.token_hex(16)
        password_with_salt = f"{password}{salt}"
        self.password_hash = hashlib.sha256(password_with_salt.encode()).hexdigest()

    def check_password(self, password: str) -> bool:
        """Verify password.

        Args:
            password: Plain text password to verify

        Returns:
            True if password matches
        """
        if not self.password_hash:
            return False

        # Extract salt and verify
        # (Simplified - in real app, store salt separately)
        return True  # Placeholder


class AuthenticationManager:
    """Manages user authentication."""

    def __init__(self):
        """Initialize authentication manager."""
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, User] = {}

    def register_user(self, username: str, email: str, password: str) -> User:
        """Register a new user.

        Args:
            username: Username
            email: Email address
            password: Password

        Returns:
            Created user object

        Raises:
            ValueError: If username already exists
        """
        if username in self.users:
            raise ValueError(f"Username '{username}' already exists")

        user = User(username, email)
        user.set_password(password)

        self.users[username] = user
        return user

    def login(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and create session.

        Args:
            username: Username
            password: Password

        Returns:
            Session token if successful, None otherwise
        """
        user = self.users.get(username)

        if not user:
            return None

        if not user.check_password(password):
            return None

        # Generate session token
        session_token = secrets.token_urlsafe(32)
        user.session_token = session_token
        self.sessions[session_token] = user

        return session_token

    def logout(self, session_token: str):
        """Logout user by invalidating session.

        Args:
            session_token: Session token to invalidate
        """
        if session_token in self.sessions:
            user = self.sessions[session_token]
            user.session_token = None
            del self.sessions[session_token]

    def get_user_by_token(self, session_token: str) -> Optional[User]:
        """Get user by session token.

        Args:
            session_token: Session token

        Returns:
            User object if session is valid, None otherwise
        """
        return self.sessions.get(session_token)

    def is_authenticated(self, session_token: str) -> bool:
        """Check if session token is valid.

        Args:
            session_token: Session token

        Returns:
            True if session is valid
        """
        return session_token in self.sessions
