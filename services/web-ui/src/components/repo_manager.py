"""Repository management component with directory picker."""

import logging
from pathlib import Path
from typing import Optional, Tuple
import httpx

from .repo_validator import RepositoryValidator

logger = logging.getLogger(__name__)


class RepositoryManager:
    """Manage repository selection and indexing."""

    def __init__(self, rag_api_url: str, allowed_paths: Optional[list] = None):
        """Initialize repository manager.

        Args:
            rag_api_url: URL of RAG pipeline API
            allowed_paths: List of allowed parent directories
        """
        self.rag_api_url = rag_api_url
        self.allowed_paths = allowed_paths or []
        # Increased timeout to 10 minutes for large repository indexing with OpenAI embeddings
        self.http_client = httpx.Client(timeout=600.0)
        self.current_repo_id: Optional[str] = None

    def validate_path(self, repo_path: str) -> str:
        """Quick validation for real-time feedback.

        Args:
            repo_path: Path to validate

        Returns:
            Status message
        """
        # Use validator for quick check
        status = RepositoryValidator.quick_validate(repo_path)

        # Additional security check if allowed_paths configured
        if status.startswith("✅") and self.allowed_paths:
            if not RepositoryValidator.is_path_allowed(repo_path, self.allowed_paths):
                return "❌ Path not in allowed directories"

        return status

    def add_repository(self, repo_path: str) -> Tuple[str, str, bool]:
        """Validate and add repository to system.

        Args:
            repo_path: Path to repository

        Returns:
            Tuple of (status_message, repo_info_markdown, success)
        """
        if not repo_path or not repo_path.strip():
            return "⚠️ Please enter a repository path", "", False

        # Validate
        is_valid, message, repo_info = RepositoryValidator.validate_and_get_info(repo_path)

        if not is_valid:
            return message, "", False

        # Security check
        if self.allowed_paths and not RepositoryValidator.is_path_allowed(
            repo_path, self.allowed_paths
        ):
            return "❌ Error: Path not in allowed directories", "", False

        # Call RAG API to add repository
        try:
            response = self.http_client.post(
                f"{self.rag_api_url}/api/repos",
                json={"path": repo_info['path'], "name": repo_info['name']}
            )

            if response.status_code == 200:
                result = response.json()
                repo_id = result.get('repo_id')
                self.current_repo_id = repo_id

                # Format repository info
                info_md = self._format_repo_info(repo_info, indexing=True)

                success_msg = f"✅ Repository added and indexing started"
                return success_msg, info_md, True

            else:
                error = response.json().get('detail', 'Unknown error')
                return f"❌ API Error: {error}", "", False

        except httpx.RequestError as e:
            logger.error(f"Failed to add repository: {e}")
            return f"❌ Connection Error: {str(e)}", "", False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"❌ Error: {str(e)}", "", False

    def get_indexing_status(self, repo_id: Optional[str] = None) -> str:
        """Get indexing status for repository.

        Args:
            repo_id: Repository ID (uses current if not specified)

        Returns:
            Status markdown
        """
        target_repo_id = repo_id or self.current_repo_id

        if not target_repo_id:
            return "⚠️ No repository selected"

        try:
            response = self.http_client.get(
                f"{self.rag_api_url}/api/repos/{target_repo_id}/status"
            )

            if response.status_code == 200:
                status_data = response.json()

                # Format status
                status_md = f"""
### Indexing Status

**Repository:** {status_data.get('repo_name', 'Unknown')}
**Status:** {status_data.get('status', 'Unknown')}
**Files Indexed:** {status_data.get('files_indexed', 0)} / {status_data.get('total_files', 0)}
**Chunks:** {status_data.get('total_chunks', 0)}
**Last Updated:** {status_data.get('last_indexed_at', 'Never')}
"""
                return status_md.strip()

            else:
                return f"❌ Could not fetch status (HTTP {response.status_code})"

        except httpx.RequestError as e:
            logger.error(f"Failed to get status: {e}")
            return f"❌ Connection Error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"❌ Error: {str(e)}"

    def list_repositories(self) -> str:
        """List all repositories in system.

        Returns:
            Markdown formatted list
        """
        try:
            response = self.http_client.get(f"{self.rag_api_url}/api/repos")

            if response.status_code == 200:
                repos = response.json().get('repositories', [])

                if not repos:
                    return "No repositories indexed yet."

                # Format list
                lines = ["### Available Repositories\n"]
                for repo in repos:
                    active_marker = "**[ACTIVE]**" if repo.get('is_active') else ""
                    lines.append(
                        f"- {active_marker} **{repo['name']}**  \n"
                        f"  Path: `{repo['path']}`  \n"
                        f"  Chunks: {repo.get('total_chunks', 0)} | "
                        f"Files: {repo.get('total_files', 0)}  \n"
                        f"  Last Indexed: {repo.get('last_indexed_at', 'Never')}\n"
                    )

                return "\n".join(lines)

            else:
                return f"❌ Could not fetch repositories (HTTP {response.status_code})"

        except httpx.RequestError as e:
            logger.error(f"Failed to list repositories: {e}")
            return f"❌ Connection Error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"❌ Error: {str(e)}"

    def switch_repository(self, repo_id: str) -> str:
        """Switch active repository.

        Args:
            repo_id: Repository ID to activate

        Returns:
            Status message
        """
        try:
            response = self.http_client.put(
                f"{self.rag_api_url}/api/repos/{repo_id}/activate"
            )

            if response.status_code == 200:
                self.current_repo_id = repo_id
                return f"✅ Switched to repository {repo_id}"
            else:
                return f"❌ Failed to switch repository (HTTP {response.status_code})"

        except httpx.RequestError as e:
            logger.error(f"Failed to switch repository: {e}")
            return f"❌ Connection Error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"❌ Error: {str(e)}"

    def _format_repo_info(self, repo_info: dict, indexing: bool = False) -> str:
        """Format repository information as markdown.

        Args:
            repo_info: Repository information dict
            indexing: Whether indexing is in progress

        Returns:
            Formatted markdown
        """
        status_line = "**Status:** Indexing in progress..." if indexing else "**Status:** Ready"

        info = f"""
### ✅ Repository Information

**Name:** {repo_info['name']}
**Path:** `{repo_info['path']}`
**Branch:** {repo_info['branch']}
**Latest Commit:** {repo_info['commit_hash']}
**Commit Message:** {repo_info['commit_message']}
**Author:** {repo_info['author']}
**Date:** {repo_info['commit_date']}
**Total Files:** {repo_info['file_count']}
**Tracked Files:** {repo_info['tracked_count']}

{status_line}
"""
        return info.strip()

    def close(self):
        """Close HTTP client."""
        self.http_client.close()
