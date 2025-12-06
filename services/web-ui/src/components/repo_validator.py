"""Repository validation for directory picker."""

import logging
from pathlib import Path
from typing import Tuple, Optional
import git

logger = logging.getLogger(__name__)


class RepositoryValidator:
    """Validate Git repositories for directory picker."""

    @staticmethod
    def quick_validate(repo_path: str) -> str:
        """Quick validation for real-time feedback.

        Args:
            repo_path: Path to validate

        Returns:
            Status message
        """
        if not repo_path or not repo_path.strip():
            return ""

        try:
            path = Path(repo_path).resolve()

            if not path.exists():
                return "❌ Path does not exist"

            if not path.is_dir():
                return "❌ Path is not a directory"

            if not (path / ".git").exists():
                return "⚠️ Not a Git repository"

            return "✅ Valid Git repository"

        except Exception as e:
            return f"❌ Error: {str(e)}"

    @staticmethod
    def validate_and_get_info(repo_path: str) -> Tuple[bool, str, Optional[dict]]:
        """Full validation and extract repository information.

        Args:
            repo_path: Path to repository

        Returns:
            Tuple of (is_valid, message, repo_info)
        """
        if not repo_path or not repo_path.strip():
            return False, "Please enter a repository path", None

        try:
            path = Path(repo_path).resolve()

            # Check existence
            if not path.exists():
                return False, "❌ Error: Path does not exist", None

            if not path.is_dir():
                return False, "❌ Error: Path is not a directory", None

            # Check Git repository
            try:
                repo = git.Repo(path)

                # Get repository info
                branch = repo.active_branch.name
                latest_commit = repo.head.commit

                # Count files
                all_files = list(path.rglob("*"))
                file_count = sum(1 for f in all_files if f.is_file())

                # Get tracked files
                tracked_files = repo.git.ls_files().split('\n')
                tracked_count = len([f for f in tracked_files if f.strip()])

                repo_info = {
                    'path': str(path),
                    'name': path.name,
                    'branch': branch,
                    'commit_hash': latest_commit.hexsha[:8],
                    'commit_message': latest_commit.message.strip(),
                    'file_count': file_count,
                    'tracked_count': tracked_count,
                    'author': f"{latest_commit.author.name} <{latest_commit.author.email}>",
                    'commit_date': latest_commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S')
                }

                success_msg = f"✅ Repository validated: {path.name}"
                return True, success_msg, repo_info

            except git.exc.InvalidGitRepositoryError:
                return False, "❌ Error: Not a valid Git repository", None

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False, f"❌ Error: {str(e)}", None

    @staticmethod
    def is_path_allowed(repo_path: str, allowed_paths: list) -> bool:
        """Check if path is within allowed directories.

        Args:
            repo_path: Path to check
            allowed_paths: List of allowed parent paths

        Returns:
            True if path is allowed
        """
        try:
            path = Path(repo_path).resolve()

            for allowed in allowed_paths:
                allowed_path = Path(allowed).resolve()
                try:
                    path.relative_to(allowed_path)
                    return True
                except ValueError:
                    continue

            return False

        except Exception:
            return False
