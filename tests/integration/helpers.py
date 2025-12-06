"""Test helper utilities for integration tests."""

import os
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
import docker

logger = logging.getLogger(__name__)


class DockerHelper:
    """Helper for Docker container operations."""

    def __init__(self):
        """Initialize Docker client."""
        try:
            self.client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            self.client = None

    def is_container_running(self, container_name: str) -> bool:
        """Check if container is running.

        Args:
            container_name: Name of container

        Returns:
            True if running
        """
        if not self.client:
            return False

        try:
            container = self.client.containers.get(container_name)
            return container.status == 'running'
        except docker.errors.NotFound:
            return False
        except Exception as e:
            logger.error(f"Error checking container {container_name}: {e}")
            return False

    def get_container_logs(self, container_name: str, tail: int = 50) -> str:
        """Get container logs.

        Args:
            container_name: Name of container
            tail: Number of lines to retrieve

        Returns:
            Log output
        """
        if not self.client:
            return ""

        try:
            container = self.client.containers.get(container_name)
            logs = container.logs(tail=tail).decode('utf-8')
            return logs
        except Exception as e:
            logger.error(f"Error getting logs for {container_name}: {e}")
            return ""

    def wait_for_container(
        self,
        container_name: str,
        timeout: int = 60,
        check_interval: int = 2
    ) -> bool:
        """Wait for container to be running.

        Args:
            container_name: Name of container
            timeout: Maximum wait time in seconds
            check_interval: Check interval in seconds

        Returns:
            True if container is running
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_container_running(container_name):
                logger.info(f"✅ Container {container_name} is running")
                return True

            time.sleep(check_interval)

        logger.error(f"❌ Container {container_name} failed to start within {timeout}s")
        return False

    def get_container_health(self, container_name: str) -> Optional[str]:
        """Get container health status.

        Args:
            container_name: Name of container

        Returns:
            Health status or None
        """
        if not self.client:
            return None

        try:
            container = self.client.containers.get(container_name)
            health = container.attrs.get('State', {}).get('Health', {})
            return health.get('Status')
        except Exception as e:
            logger.error(f"Error getting health for {container_name}: {e}")
            return None


class APIHelper:
    """Helper for API testing."""

    def __init__(self, base_url: str, timeout: int = 30):
        """Initialize API helper.

        Args:
            base_url: Base URL for API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.client = httpx.Client(timeout=timeout)

    def wait_for_api(
        self,
        endpoint: str = "/api/health",
        timeout: int = 60,
        check_interval: int = 2
    ) -> bool:
        """Wait for API to be available.

        Args:
            endpoint: Health check endpoint
            timeout: Maximum wait time in seconds
            check_interval: Check interval in seconds

        Returns:
            True if API is available
        """
        start_time = time.time()
        url = f"{self.base_url}{endpoint}"

        while time.time() - start_time < timeout:
            try:
                response = self.client.get(url)
                if response.status_code == 200:
                    logger.info(f"✅ API available at {self.base_url}")
                    return True
            except httpx.RequestError:
                pass

            time.sleep(check_interval)

        logger.error(f"❌ API at {self.base_url} not available within {timeout}s")
        return False

    def add_repository(self, repo_path: str, repo_name: Optional[str] = None) -> Optional[str]:
        """Add repository via API.

        Args:
            repo_path: Path to repository
            repo_name: Repository name (optional)

        Returns:
            Repository ID if successful, None otherwise
        """
        url = f"{self.base_url}/api/repos"

        payload = {"path": repo_path}
        if repo_name:
            payload["name"] = repo_name

        try:
            response = self.client.post(url, json=payload)

            if response.status_code == 200:
                result = response.json()
                repo_id = result.get('repo_id')
                logger.info(f"✅ Repository added: {repo_id}")
                return repo_id
            else:
                logger.error(f"❌ Failed to add repository: {response.text}")
                return None

        except httpx.RequestError as e:
            logger.error(f"❌ API request failed: {e}")
            return None

    def get_indexing_status(self, repo_id: str) -> Optional[Dict[str, Any]]:
        """Get repository indexing status.

        Args:
            repo_id: Repository ID

        Returns:
            Status dict or None
        """
        url = f"{self.base_url}/api/repos/{repo_id}/status"

        try:
            response = self.client.get(url)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Failed to get status: {response.text}")
                return None

        except httpx.RequestError as e:
            logger.error(f"❌ API request failed: {e}")
            return None

    def wait_for_indexing(
        self,
        repo_id: str,
        timeout: int = 300,
        check_interval: int = 5
    ) -> bool:
        """Wait for repository indexing to complete.

        Args:
            repo_id: Repository ID
            timeout: Maximum wait time in seconds
            check_interval: Check interval in seconds

        Returns:
            True if indexing completed
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_indexing_status(repo_id)

            if status:
                status_value = status.get('status', '')

                if status_value == 'completed':
                    logger.info(f"✅ Indexing completed for {repo_id}")
                    return True
                elif status_value == 'failed':
                    logger.error(f"❌ Indexing failed for {repo_id}")
                    return False

                logger.info(f"⏳ Indexing in progress: {status.get('files_indexed', 0)}/{status.get('total_files', 0)} files")

            time.sleep(check_interval)

        logger.error(f"❌ Indexing timeout for {repo_id}")
        return False

    def query(
        self,
        query: str,
        repo_id: Optional[str] = None,
        top_k: int = 10,
        temperature: float = 0.1
    ) -> Optional[Dict[str, Any]]:
        """Query repository.

        Args:
            query: Query string
            repo_id: Repository ID (optional)
            top_k: Number of results
            temperature: LLM temperature

        Returns:
            Query response or None
        """
        url = f"{self.base_url}/api/query"

        payload = {
            "query": query,
            "top_k": top_k,
            "temperature": temperature,
            "include_sources": True
        }

        if repo_id:
            payload["repo_id"] = repo_id

        try:
            response = self.client.post(url, json=payload)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Query failed: {response.text}")
                return None

        except httpx.RequestError as e:
            logger.error(f"❌ API request failed: {e}")
            return None

    def close(self):
        """Close HTTP client."""
        self.client.close()


class GitRepoHelper:
    """Helper for Git repository operations."""

    @staticmethod
    def create_test_repo(path: Path, repo_name: str = "test-repo") -> Path:
        """Create a test Git repository.

        Args:
            path: Parent path for repository
            repo_name: Repository name

        Returns:
            Path to created repository
        """
        repo_path = path / repo_name
        repo_path.mkdir(parents=True, exist_ok=True)

        # Initialize Git repo
        subprocess.run(['git', 'init'], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        logger.info(f"✅ Created test repository at {repo_path}")
        return repo_path

    @staticmethod
    def add_file(repo_path: Path, file_path: str, content: str):
        """Add a file to repository.

        Args:
            repo_path: Repository path
            file_path: Relative file path
            content: File content
        """
        full_path = repo_path / file_path

        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        full_path.write_text(content)

        logger.info(f"✅ Added file: {file_path}")

    @staticmethod
    def commit_changes(repo_path: Path, message: str):
        """Commit all changes.

        Args:
            repo_path: Repository path
            message: Commit message
        """
        subprocess.run(['git', 'add', '.'], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        logger.info(f"✅ Created commit: {message}")

    @staticmethod
    def get_latest_commit_hash(repo_path: Path) -> str:
        """Get latest commit hash.

        Args:
            repo_path: Repository path

        Returns:
            Commit hash
        """
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )

        return result.stdout.strip()


class TestReporter:
    """Test result reporter."""

    def __init__(self):
        """Initialize reporter."""
        self.results: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def add_result(
        self,
        test_name: str,
        passed: bool,
        duration: float,
        details: Optional[str] = None
    ):
        """Add test result.

        Args:
            test_name: Name of test
            passed: Whether test passed
            duration: Test duration in seconds
            details: Additional details
        """
        self.results.append({
            'test_name': test_name,
            'passed': passed,
            'duration': duration,
            'details': details
        })

    def print_summary(self):
        """Print test summary."""
        total_duration = time.time() - self.start_time
        passed_count = sum(1 for r in self.results if r['passed'])
        total_count = len(self.results)

        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        for result in self.results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            duration = f"{result['duration']:.2f}s"
            print(f"{status} - {result['test_name']} ({duration})")

            if result['details']:
                print(f"    {result['details']}")

        print("=" * 70)
        print(f"Results: {passed_count}/{total_count} tests passed")
        print(f"Total Duration: {total_duration:.2f}s")
        print("=" * 70)

        return passed_count == total_count
