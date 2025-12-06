"""Git commit monitor for tracking new commits."""

import logging
import time
import threading
from typing import Optional, Callable, List
from pathlib import Path
import git

logger = logging.getLogger(__name__)


class GitCommitMonitor:
    """Monitor a Git repository for new commits."""

    def __init__(
        self,
        repo_path: str,
        callback: Callable[[str, List[str]], None],
        poll_interval: float = 5.0
    ):
        """Initialize Git commit monitor.

        Args:
            repo_path: Path to Git repository
            callback: Function to call with (commit_hash, changed_files) when new commit detected
            poll_interval: Seconds between Git status checks
        """
        self.repo_path = Path(repo_path).resolve()
        self.callback = callback
        self.poll_interval = poll_interval

        # Validate Git repository
        try:
            self.repo = git.Repo(self.repo_path)
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Not a valid Git repository: {repo_path}")

        # Get initial HEAD commit
        try:
            self.last_commit_hash = self.repo.head.commit.hexsha
            logger.info(f"Initial commit: {self.last_commit_hash[:8]}")
        except ValueError:
            # Empty repository (no commits yet)
            self.last_commit_hash = None
            logger.info("Repository has no commits yet")

        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info(f"Git monitor initialized for: {self.repo_path}")

    def _monitor_loop(self):
        """Main monitoring loop (runs in separate thread)."""
        logger.info("Git monitor loop started")

        while self._running:
            try:
                self._check_for_new_commits()
            except Exception as e:
                logger.error(f"Error checking for commits: {e}")

            # Sleep for poll interval
            time.sleep(self.poll_interval)

        logger.info("Git monitor loop stopped")

    def _check_for_new_commits(self):
        """Check if there are new commits since last check."""
        try:
            # Refresh repository state
            self.repo.git.fetch('--all', '--quiet')

            # Get current HEAD commit
            try:
                current_commit = self.repo.head.commit
                current_hash = current_commit.hexsha
            except ValueError:
                # Repository still has no commits
                return

            # Check if commit has changed
            if current_hash != self.last_commit_hash:
                logger.info(f"New commit detected: {current_hash[:8]}")

                # Get list of changed files
                changed_files = self._get_changed_files(
                    self.last_commit_hash,
                    current_hash
                )

                # Update last commit hash
                old_commit = self.last_commit_hash
                self.last_commit_hash = current_hash

                # Trigger callback
                try:
                    self.callback(current_hash, changed_files)
                except Exception as e:
                    logger.error(f"Error in commit callback: {e}")

                logger.info(
                    f"Processed commit: {old_commit[:8] if old_commit else 'none'} -> {current_hash[:8]}"
                )

        except git.GitCommandError as e:
            logger.error(f"Git command failed: {e}")
        except Exception as e:
            logger.error(f"Error checking commits: {e}")

    def _get_changed_files(
        self,
        old_commit: Optional[str],
        new_commit: str
    ) -> List[str]:
        """Get list of files changed between commits.

        Args:
            old_commit: Old commit hash (None if first commit)
            new_commit: New commit hash

        Returns:
            List of changed file paths (relative to repo root)
        """
        try:
            if old_commit is None:
                # First commit - get all files in the commit
                commit = self.repo.commit(new_commit)
                changed_files = [item.path for item in commit.tree.traverse()]
            else:
                # Get diff between commits
                old = self.repo.commit(old_commit)
                new = self.repo.commit(new_commit)
                diff = old.diff(new)

                # Extract file paths from diff
                changed_files = []
                for item in diff:
                    if item.a_path:
                        changed_files.append(item.a_path)
                    if item.b_path and item.b_path != item.a_path:
                        changed_files.append(item.b_path)

            logger.debug(f"Changed files: {len(changed_files)}")
            return changed_files

        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            return []

    def get_uncommitted_files(self) -> List[str]:
        """Get list of files with uncommitted changes.

        Returns:
            List of file paths with uncommitted changes
        """
        try:
            # Get modified files (unstaged changes)
            modified_files = [item.a_path for item in self.repo.index.diff(None)]

            # Get staged files (staged changes)
            staged_files = [item.a_path for item in self.repo.index.diff('HEAD')]

            # Get untracked files
            untracked_files = self.repo.untracked_files

            # Combine all (remove duplicates)
            all_files = set(modified_files + staged_files + untracked_files)

            logger.debug(f"Uncommitted files: {len(all_files)}")
            return list(all_files)

        except Exception as e:
            logger.error(f"Error getting uncommitted files: {e}")
            return []

    def start(self):
        """Start monitoring for new commits."""
        if self._running:
            logger.warning("Git monitor already running")
            return

        logger.info("Starting Git commit monitor")
        self._running = True

        # Start monitoring thread
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="GitMonitor"
        )
        self._thread.start()

    def stop(self):
        """Stop monitoring for new commits."""
        if not self._running:
            return

        logger.info("Stopping Git commit monitor")
        self._running = False

        # Wait for thread to finish
        if self._thread:
            self._thread.join(timeout=self.poll_interval + 1)
            self._thread = None

    def is_running(self) -> bool:
        """Check if monitor is running.

        Returns:
            True if monitor is running
        """
        return self._running

    def get_current_commit(self) -> Optional[str]:
        """Get current HEAD commit hash.

        Returns:
            Commit hash or None if no commits
        """
        try:
            return self.repo.head.commit.hexsha
        except ValueError:
            return None

    def get_branch_name(self) -> Optional[str]:
        """Get current branch name.

        Returns:
            Branch name or None if detached HEAD
        """
        try:
            return self.repo.active_branch.name
        except TypeError:
            return None

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
