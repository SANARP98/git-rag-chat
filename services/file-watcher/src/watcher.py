"""File system watcher for monitoring uncommitted changes."""

import logging
import time
from typing import Dict, Set, Optional, Callable
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import threading

logger = logging.getLogger(__name__)


class DebounceHandler(FileSystemEventHandler):
    """File system event handler with debouncing."""

    def __init__(
        self,
        callback: Callable[[str], None],
        debounce_seconds: float = 2.0,
        file_extensions: Optional[Set[str]] = None
    ):
        """Initialize debounce handler.

        Args:
            callback: Function to call with file path when debounce period expires
            debounce_seconds: Seconds to wait before triggering callback
            file_extensions: Set of file extensions to monitor (e.g., {'.py', '.js'})
        """
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.file_extensions = file_extensions or {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs',
            '.rb', '.c', '.cpp', '.h', '.hpp', '.md', '.txt', '.json',
            '.yaml', '.yml', '.toml', '.ini', '.cfg'
        }

        # Track pending changes with their last modification time
        self._pending_changes: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification event."""
        if event.is_directory:
            return

        self._handle_event(event.src_path)

    def on_created(self, event: FileSystemEvent):
        """Handle file creation event."""
        if event.is_directory:
            return

        self._handle_event(event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion event."""
        if event.is_directory:
            return

        # For deletions, trigger immediately
        self._handle_event(event.src_path, immediate=True)

    def _handle_event(self, file_path: str, immediate: bool = False):
        """Handle a file system event with debouncing.

        Args:
            file_path: Path to the file that changed
            immediate: If True, trigger callback immediately without debouncing
        """
        path = Path(file_path)

        # Check if we should monitor this file
        if not self._should_monitor(path):
            return

        logger.debug(f"File change detected: {file_path}")

        with self._lock:
            if immediate:
                # Trigger callback immediately
                self.callback(file_path)
            else:
                # Update pending changes
                current_time = time.time()
                self._pending_changes[file_path] = current_time

                # Cancel existing timer if any
                if self._timer:
                    self._timer.cancel()

                # Start new timer
                self._timer = threading.Timer(
                    self.debounce_seconds,
                    self._process_pending_changes
                )
                self._timer.daemon = True
                self._timer.start()

    def _should_monitor(self, path: Path) -> bool:
        """Check if a file should be monitored.

        Args:
            path: File path

        Returns:
            True if file should be monitored
        """
        # Skip hidden files
        if path.name.startswith('.'):
            return False

        # Skip files in common ignore directories
        ignore_dirs = {
            '__pycache__', 'node_modules', '.git', '.venv', 'venv',
            'env', 'dist', 'build', 'target', '.pytest_cache',
            '.mypy_cache', '.tox', 'coverage', 'htmlcov'
        }
        if any(part in ignore_dirs for part in path.parts):
            return False

        # Skip files without relevant extensions
        if self.file_extensions and path.suffix.lower() not in self.file_extensions:
            return False

        return True

    def _process_pending_changes(self):
        """Process all pending changes after debounce period."""
        with self._lock:
            if not self._pending_changes:
                return

            current_time = time.time()
            files_to_process = []

            # Find files that have exceeded debounce period
            for file_path, mod_time in list(self._pending_changes.items()):
                if current_time - mod_time >= self.debounce_seconds:
                    files_to_process.append(file_path)
                    del self._pending_changes[file_path]

            # Trigger callback for each file
            for file_path in files_to_process:
                try:
                    logger.info(f"Processing change: {file_path}")
                    self.callback(file_path)
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")

            # If there are still pending changes, schedule another check
            if self._pending_changes:
                self._timer = threading.Timer(
                    self.debounce_seconds,
                    self._process_pending_changes
                )
                self._timer.daemon = True
                self._timer.start()

    def stop(self):
        """Stop the debounce timer."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None


class FileWatcher:
    """Monitor file system for changes in a repository."""

    def __init__(
        self,
        repo_path: str,
        callback: Callable[[str], None],
        debounce_seconds: float = 2.0,
        recursive: bool = True
    ):
        """Initialize file watcher.

        Args:
            repo_path: Path to repository to watch
            callback: Function to call with file path when changes are detected
            debounce_seconds: Seconds to wait before triggering callback
            recursive: Whether to watch subdirectories
        """
        self.repo_path = Path(repo_path).resolve()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.recursive = recursive

        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        # Create event handler
        self.event_handler = DebounceHandler(
            callback=self._on_file_changed,
            debounce_seconds=debounce_seconds
        )

        # Create observer
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(self.repo_path),
            recursive=recursive
        )

        self._running = False
        logger.info(f"File watcher initialized for: {self.repo_path}")

    def _on_file_changed(self, file_path: str):
        """Handle file change event.

        Args:
            file_path: Absolute path to changed file
        """
        try:
            # Convert to relative path
            path = Path(file_path)
            relative_path = path.relative_to(self.repo_path)

            logger.info(f"File changed: {relative_path}")

            # Call user callback with relative path
            self.callback(str(relative_path))

        except ValueError:
            # Path is not relative to repo (shouldn't happen)
            logger.warning(f"File outside repo: {file_path}")
        except Exception as e:
            logger.error(f"Error handling file change: {e}")

    def start(self):
        """Start watching for file changes."""
        if self._running:
            logger.warning("File watcher already running")
            return

        logger.info(f"Starting file watcher for: {self.repo_path}")
        self.observer.start()
        self._running = True

    def stop(self):
        """Stop watching for file changes."""
        if not self._running:
            return

        logger.info("Stopping file watcher")
        self.observer.stop()
        self.observer.join(timeout=5)
        self.event_handler.stop()
        self._running = False

    def is_running(self) -> bool:
        """Check if watcher is running.

        Returns:
            True if watcher is running
        """
        return self._running

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
