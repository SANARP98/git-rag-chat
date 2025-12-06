"""Main file watcher service for Git repository monitoring."""

import logging
import os
import sys
import time
import signal
from typing import Optional, List
from pathlib import Path
import httpx

from watcher import FileWatcher
from git_monitor import GitCommitMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WatcherService:
    """Main service that coordinates file watching and Git monitoring."""

    def __init__(
        self,
        repo_path: str,
        repo_id: str,
        rag_api_url: str = "http://rag-pipeline:8001",
        debounce_seconds: float = 2.0,
        poll_interval: float = 5.0
    ):
        """Initialize watcher service.

        Args:
            repo_path: Path to repository to watch
            repo_id: Repository UUID for API calls
            rag_api_url: URL of RAG pipeline API
            debounce_seconds: Debounce period for file changes
            poll_interval: Poll interval for Git commits
        """
        self.repo_path = Path(repo_path).resolve()
        self.repo_id = repo_id
        self.rag_api_url = rag_api_url.rstrip('/')
        self.debounce_seconds = debounce_seconds
        self.poll_interval = poll_interval

        # Validate repository
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        # HTTP client for API calls
        self.http_client = httpx.Client(timeout=30.0)

        # Initialize watchers
        self.file_watcher = FileWatcher(
            repo_path=str(self.repo_path),
            callback=self._on_file_changed,
            debounce_seconds=debounce_seconds
        )

        self.git_monitor = GitCommitMonitor(
            repo_path=str(self.repo_path),
            callback=self._on_new_commit,
            poll_interval=poll_interval
        )

        self._running = False
        logger.info(f"Watcher service initialized for repo: {repo_id}")
        logger.info(f"Repository path: {self.repo_path}")
        logger.info(f"RAG API URL: {self.rag_api_url}")

    def _on_file_changed(self, relative_path: str):
        """Handle file change event.

        Args:
            relative_path: Path relative to repository root
        """
        logger.info(f"File changed: {relative_path}")

        try:
            # Call RAG pipeline API to re-index the file
            url = f"{self.rag_api_url}/api/repos/{self.repo_id}/index/file"
            params = {"file_path": relative_path}

            logger.debug(f"Calling API: POST {url}")
            response = self.http_client.post(url, params=params)

            if response.status_code == 200:
                result = response.json()
                chunks_added = result.get('chunks_added', 0)
                logger.info(f"File re-indexed: {relative_path} ({chunks_added} chunks)")
            else:
                logger.error(
                    f"API error: {response.status_code} - {response.text}"
                )

        except httpx.RequestError as e:
            logger.error(f"Failed to call RAG API: {e}")
        except Exception as e:
            logger.error(f"Error handling file change: {e}")

    def _on_new_commit(self, commit_hash: str, changed_files: List[str]):
        """Handle new commit event.

        Args:
            commit_hash: New commit hash
            changed_files: List of files changed in the commit
        """
        logger.info(f"New commit: {commit_hash[:8]} ({len(changed_files)} files)")

        try:
            # Call RAG pipeline API to trigger incremental indexing
            url = f"{self.rag_api_url}/api/repos/{self.repo_id}/index/incremental"

            logger.debug(f"Calling API: POST {url}")
            response = self.http_client.post(url)

            if response.status_code == 200:
                result = response.json()
                indexed_files = result.get('indexed_files', 0)
                total_chunks = result.get('total_chunks', 0)
                logger.info(
                    f"Incremental indexing completed: {indexed_files} files, {total_chunks} chunks"
                )
            else:
                logger.error(
                    f"API error: {response.status_code} - {response.text}"
                )

        except httpx.RequestError as e:
            logger.error(f"Failed to call RAG API: {e}")
        except Exception as e:
            logger.error(f"Error handling new commit: {e}")

    def start(self):
        """Start the watcher service."""
        if self._running:
            logger.warning("Watcher service already running")
            return

        logger.info("Starting watcher service")

        # Start file watcher
        self.file_watcher.start()
        logger.info("File watcher started")

        # Start Git monitor
        self.git_monitor.start()
        logger.info("Git monitor started")

        self._running = True
        logger.info("Watcher service is now running")

    def stop(self):
        """Stop the watcher service."""
        if not self._running:
            return

        logger.info("Stopping watcher service")

        # Stop watchers
        self.file_watcher.stop()
        self.git_monitor.stop()

        # Close HTTP client
        self.http_client.close()

        self._running = False
        logger.info("Watcher service stopped")

    def is_running(self) -> bool:
        """Check if service is running.

        Returns:
            True if service is running
        """
        return self._running

    def run_forever(self):
        """Run the service until interrupted."""
        self.start()

        try:
            # Keep main thread alive
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.stop()


def get_env_var(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Get environment variable with validation.

    Args:
        name: Environment variable name
        default: Default value if not set
        required: If True, raise error if not set

    Returns:
        Environment variable value or default

    Raises:
        ValueError: If required variable is not set
    """
    value = os.environ.get(name, default)

    if required and value is None:
        raise ValueError(f"Required environment variable not set: {name}")

    return value


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Git RAG File Watcher Service")
    logger.info("=" * 60)

    # Get configuration from environment
    try:
        repo_path = get_env_var('REPO_PATH', required=True)
        repo_id = get_env_var('REPO_ID', required=True)
        rag_api_url = get_env_var('RAG_API_URL', default='http://rag-pipeline:8001')
        debounce_seconds = float(get_env_var('DEBOUNCE_SECONDS', default='2.0'))
        poll_interval = float(get_env_var('POLL_INTERVAL', default='5.0'))

        logger.info(f"Configuration:")
        logger.info(f"  REPO_PATH: {repo_path}")
        logger.info(f"  REPO_ID: {repo_id}")
        logger.info(f"  RAG_API_URL: {rag_api_url}")
        logger.info(f"  DEBOUNCE_SECONDS: {debounce_seconds}")
        logger.info(f"  POLL_INTERVAL: {poll_interval}")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Create and run service
    try:
        service = WatcherService(
            repo_path=repo_path,
            repo_id=repo_id,
            rag_api_url=rag_api_url,
            debounce_seconds=debounce_seconds,
            poll_interval=poll_interval
        )

        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            service.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run service
        service.run_forever()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
