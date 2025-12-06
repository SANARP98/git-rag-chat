"""Git operations for repository management."""

import git
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GitOperations:
    """Handle Git operations for repository indexing."""

    def __init__(self, repo_path: str):
        """Initialize Git operations.

        Args:
            repo_path: Path to Git repository

        Raises:
            git.exc.InvalidGitRepositoryError: If path is not a Git repository
        """
        self.repo_path = Path(repo_path).resolve()
        self.repo = git.Repo(self.repo_path)
        logger.info(f"Initialized Git operations for {self.repo_path}")

    def is_valid_repo(self) -> bool:
        """Check if the repository is valid.

        Returns:
            True if valid Git repository
        """
        try:
            return not self.repo.bare
        except Exception as e:
            logger.error(f"Invalid repository: {e}")
            return False

    def get_current_branch(self) -> str:
        """Get the name of the current branch.

        Returns:
            Branch name
        """
        try:
            return self.repo.active_branch.name
        except TypeError:
            return "HEAD"  # Detached HEAD state

    def get_latest_commit(self) -> Optional[git.Commit]:
        """Get the latest commit.

        Returns:
            Latest commit object or None
        """
        try:
            return self.repo.head.commit
        except ValueError:
            logger.warning("No commits found in repository")
            return None

    def get_commit_history(self, max_count: int = 100) -> List[Dict[str, Any]]:
        """Get commit history.

        Args:
            max_count: Maximum number of commits to retrieve

        Returns:
            List of commit data dicts
        """
        commits = []
        try:
            for commit in self.repo.iter_commits(max_count=max_count):
                commits.append({
                    "hash": commit.hexsha,
                    "short_hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": commit.author.name,
                    "author_email": commit.author.email,
                    "committed_at": datetime.fromtimestamp(commit.committed_date),
                    "files_changed": len(commit.stats.files)
                })
        except Exception as e:
            logger.error(f"Error retrieving commit history: {e}")

        return commits

    def get_commits_since(self, since_hash: str) -> List[Dict[str, Any]]:
        """Get commits since a specific commit.

        Args:
            since_hash: Commit hash to start from (exclusive)

        Returns:
            List of commit data dicts
        """
        commits = []
        try:
            for commit in self.repo.iter_commits(f"{since_hash}..HEAD"):
                commits.append({
                    "hash": commit.hexsha,
                    "short_hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": commit.author.name,
                    "author_email": commit.author.email,
                    "committed_at": datetime.fromtimestamp(commit.committed_date),
                    "files_changed": len(commit.stats.files)
                })
        except Exception as e:
            logger.error(f"Error retrieving commits since {since_hash}: {e}")

        return commits

    def get_changed_files(self, commit_hash: str) -> List[str]:
        """Get list of files changed in a commit.

        Args:
            commit_hash: Commit hash

        Returns:
            List of file paths
        """
        try:
            commit = self.repo.commit(commit_hash)
            return list(commit.stats.files.keys())
        except Exception as e:
            logger.error(f"Error getting changed files for {commit_hash}: {e}")
            return []

    def get_file_content(self, file_path: str, commit_hash: Optional[str] = None) -> Optional[str]:
        """Get file content at a specific commit.

        Args:
            file_path: Relative path to file
            commit_hash: Optional commit hash (defaults to HEAD)

        Returns:
            File content as string or None
        """
        try:
            if commit_hash:
                commit = self.repo.commit(commit_hash)
                blob = commit.tree / file_path
            else:
                blob = self.repo.head.commit.tree / file_path

            return blob.data_stream.read().decode('utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"Could not read file {file_path}: {e}")
            return None

    def get_tracked_files(self, extensions: Optional[List[str]] = None) -> List[Path]:
        """Get list of tracked files in the repository.

        Args:
            extensions: Optional list of file extensions to filter (e.g., ['.py', '.js'])

        Returns:
            List of file paths relative to repo root
        """
        files = []
        try:
            # Get all tracked files from the index
            for item in self.repo.head.commit.tree.traverse():
                if item.type == 'blob':  # It's a file
                    file_path = Path(item.path)

                    # Filter by extension if specified
                    if extensions:
                        if file_path.suffix.lower() in extensions:
                            files.append(file_path)
                    else:
                        files.append(file_path)

        except Exception as e:
            logger.error(f"Error getting tracked files: {e}")

        return files

    def get_untracked_changes(self) -> List[str]:
        """Get list of untracked files.

        Returns:
            List of untracked file paths
        """
        try:
            return self.repo.untracked_files
        except Exception as e:
            logger.error(f"Error getting untracked files: {e}")
            return []

    def get_modified_files(self) -> List[str]:
        """Get list of modified but not committed files.

        Returns:
            List of modified file paths
        """
        try:
            # Get modified files (both staged and unstaged)
            modified = [item.a_path for item in self.repo.index.diff(None)]
            # Add staged files
            staged = [item.a_path for item in self.repo.index.diff("HEAD")]
            return list(set(modified + staged))
        except Exception as e:
            logger.error(f"Error getting modified files: {e}")
            return []

    def get_repo_stats(self) -> Dict[str, Any]:
        """Get repository statistics.

        Returns:
            Dictionary with repository stats
        """
        try:
            latest_commit = self.get_latest_commit()
            tracked_files = self.get_tracked_files()
            modified_files = self.get_modified_files()
            untracked_files = self.get_untracked_changes()

            return {
                "path": str(self.repo_path),
                "branch": self.get_current_branch(),
                "total_commits": len(list(self.repo.iter_commits(max_count=10000))),
                "latest_commit": {
                    "hash": latest_commit.hexsha if latest_commit else None,
                    "message": latest_commit.message.strip() if latest_commit else None,
                    "author": latest_commit.author.name if latest_commit else None,
                    "date": datetime.fromtimestamp(latest_commit.committed_date) if latest_commit else None,
                } if latest_commit else None,
                "total_files": len(tracked_files),
                "modified_files": len(modified_files),
                "untracked_files": len(untracked_files),
            }
        except Exception as e:
            logger.error(f"Error getting repository stats: {e}")
            return {}

    def is_file_ignored(self, file_path: str) -> bool:
        """Check if a file is ignored by .gitignore.

        Args:
            file_path: Relative path to file

        Returns:
            True if file is ignored
        """
        try:
            # Check if file matches any .gitignore pattern
            return self.repo.git.check_ignore(file_path) is not None
        except git.exc.GitCommandError:
            return False

    @staticmethod
    def is_git_repository(path: str) -> bool:
        """Check if a path is a Git repository.

        Args:
            path: Path to check

        Returns:
            True if it's a Git repository
        """
        try:
            git.Repo(path)
            return True
        except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError):
            return False
