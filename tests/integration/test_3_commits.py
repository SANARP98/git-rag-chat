"""Test 3: Commit Detection and Incremental Indexing."""

import sys
import time
import logging
import shutil
from pathlib import Path

# Add helpers to path
sys.path.insert(0, str(Path(__file__).parent))

from helpers import APIHelper, GitRepoHelper, TestReporter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
RAG_API_URL = "http://localhost:8001"
TEST_REPO_DIR = Path(__file__).parent.parent / "fixtures" / "commit-test-repo"


def setup_test_repository_with_commits() -> Path:
    """Create a test repository with multiple commits."""
    logger.info("\n=== Setup: Creating Test Repository with Commits ===")

    # Clean up existing test repo
    if TEST_REPO_DIR.exists():
        shutil.rmtree(TEST_REPO_DIR)

    # Create new test repo
    repo_path = GitRepoHelper.create_test_repo(TEST_REPO_DIR.parent, TEST_REPO_DIR.name)

    # Commit 1: Initial README
    GitRepoHelper.add_file(
        repo_path,
        "README.md",
        """# Commit Test Repository

Testing commit detection and incremental indexing.
"""
    )
    GitRepoHelper.commit_changes(repo_path, "feat: Initial README")

    logger.info(f"✅ Test repository created at {repo_path}")
    logger.info(f"✅ Commit 1: {GitRepoHelper.get_latest_commit_hash(repo_path)[:8]}")

    return repo_path


def add_new_feature_commit(repo_path: Path):
    """Add a new feature with a commit."""
    logger.info("\n=== Adding New Feature Commit ===")

    # Add user service module
    GitRepoHelper.add_file(
        repo_path,
        "services/user_service.py",
        """\"\"\"User service module.\"\"\"

from typing import List, Optional


class UserService:
    \"\"\"Service for user operations.\"\"\"

    def __init__(self):
        \"\"\"Initialize user service.\"\"\"
        self.users = []

    def create_user(self, username: str, email: str) -> dict:
        \"\"\"Create a new user.

        Args:
            username: Username
            email: Email address

        Returns:
            Created user data
        \"\"\"
        user = {
            'id': len(self.users) + 1,
            'username': username,
            'email': email
        }
        self.users.append(user)
        return user

    def get_user(self, user_id: int) -> Optional[dict]:
        \"\"\"Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User data or None
        \"\"\"
        for user in self.users:
            if user['id'] == user_id:
                return user
        return None

    def list_users(self) -> List[dict]:
        \"\"\"List all users.

        Returns:
            List of user data
        \"\"\"
        return self.users.copy()
"""
    )

    GitRepoHelper.commit_changes(repo_path, "feat: Add user service module")

    commit_hash = GitRepoHelper.get_latest_commit_hash(repo_path)
    logger.info(f"✅ Commit 2 (new feature): {commit_hash[:8]}")

    return commit_hash


def modify_existing_code_commit(repo_path: Path):
    """Modify existing code and create commit."""
    logger.info("\n=== Modifying Existing Code ===")

    # Update user service with delete functionality
    GitRepoHelper.add_file(
        repo_path,
        "services/user_service.py",
        """\"\"\"User service module.\"\"\"

from typing import List, Optional


class UserService:
    \"\"\"Service for user operations.\"\"\"

    def __init__(self):
        \"\"\"Initialize user service.\"\"\"
        self.users = []

    def create_user(self, username: str, email: str) -> dict:
        \"\"\"Create a new user.

        Args:
            username: Username
            email: Email address

        Returns:
            Created user data
        \"\"\"
        user = {
            'id': len(self.users) + 1,
            'username': username,
            'email': email
        }
        self.users.append(user)
        return user

    def get_user(self, user_id: int) -> Optional[dict]:
        \"\"\"Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User data or None
        \"\"\"
        for user in self.users:
            if user['id'] == user_id:
                return user
        return None

    def delete_user(self, user_id: int) -> bool:
        \"\"\"Delete user by ID.

        Args:
            user_id: User ID to delete

        Returns:
            True if deleted, False otherwise
        \"\"\"
        for i, user in enumerate(self.users):
            if user['id'] == user_id:
                del self.users[i]
                return True
        return False

    def list_users(self) -> List[dict]:
        \"\"\"List all users.

        Returns:
            List of user data
        \"\"\"
        return self.users.copy()
"""
    )

    GitRepoHelper.commit_changes(repo_path, "feat: Add delete user functionality")

    commit_hash = GitRepoHelper.get_latest_commit_hash(repo_path)
    logger.info(f"✅ Commit 3 (modification): {commit_hash[:8]}")

    return commit_hash


def test_initial_indexing(api_helper: APIHelper, repo_path: Path, reporter: TestReporter) -> str:
    """Test initial indexing of repository."""
    logger.info("\n=== Test: Initial Indexing ===")
    start_time = time.time()

    repo_id = api_helper.add_repository(str(repo_path), "commit-test-repo")

    if not repo_id:
        logger.error("❌ Failed to add repository")
        reporter.add_result("Initial Indexing", False, time.time() - start_time)
        return None

    # Wait for indexing
    completed = api_helper.wait_for_indexing(repo_id, timeout=120)

    if completed:
        status = api_helper.get_indexing_status(repo_id)
        files_count = status.get('files_indexed', 0) if status else 0
        logger.info(f"✅ Initial indexing completed: {files_count} files")
    else:
        logger.error("❌ Initial indexing failed")

    duration = time.time() - start_time
    reporter.add_result("Initial Indexing", completed, duration, f"Repo ID: {repo_id}")

    return repo_id if completed else None


def test_incremental_after_new_commit(
    api_helper: APIHelper,
    repo_id: str,
    repo_path: Path,
    reporter: TestReporter
) -> bool:
    """Test incremental indexing after new commit."""
    logger.info("\n=== Test: Incremental Indexing (New File) ===")
    start_time = time.time()

    # Get initial status
    initial_status = api_helper.get_indexing_status(repo_id)
    initial_chunks = initial_status.get('total_chunks', 0) if initial_status else 0
    initial_files = initial_status.get('files_indexed', 0) if initial_status else 0

    logger.info(f"Initial state: {initial_files} files, {initial_chunks} chunks")

    # Add new commit
    new_commit_hash = add_new_feature_commit(repo_path)

    # Trigger incremental indexing
    logger.info("Triggering incremental indexing...")
    response = api_helper.client.post(f"{api_helper.base_url}/api/repos/{repo_id}/index/incremental")

    if response.status_code != 200:
        logger.error(f"❌ Failed to trigger incremental indexing: {response.text}")
        reporter.add_result("Incremental Indexing (New File)", False, time.time() - start_time)
        return False

    # Wait for indexing
    time.sleep(10)  # Give it time to process
    completed = api_helper.wait_for_indexing(repo_id, timeout=60)

    if not completed:
        logger.error("❌ Incremental indexing did not complete")
        reporter.add_result("Incremental Indexing (New File)", False, time.time() - start_time)
        return False

    # Check new status
    new_status = api_helper.get_indexing_status(repo_id)
    new_chunks = new_status.get('total_chunks', 0) if new_status else 0
    new_files = new_status.get('files_indexed', 0) if new_status else 0

    logger.info(f"New state: {new_files} files, {new_chunks} chunks")

    # We should have more files and chunks
    passed = new_files > initial_files and new_chunks > initial_chunks

    if passed:
        logger.info(f"✅ Incremental indexing added {new_files - initial_files} files, {new_chunks - initial_chunks} chunks")
    else:
        logger.error(f"❌ No new files/chunks indexed")

    duration = time.time() - start_time
    details = f"+{new_files - initial_files} files, +{new_chunks - initial_chunks} chunks"
    reporter.add_result("Incremental Indexing (New File)", passed, duration, details)

    return passed


def test_query_new_feature(api_helper: APIHelper, repo_id: str, reporter: TestReporter) -> bool:
    """Test querying for newly added feature."""
    logger.info("\n=== Test: Query New Feature ===")
    start_time = time.time()

    query = "Show me the user service code"

    result = api_helper.query(query, repo_id=repo_id)

    if not result:
        logger.error("❌ Query failed")
        reporter.add_result("Query New Feature", False, time.time() - start_time)
        return False

    sources = result.get('sources', [])

    # Check if user_service.py is in sources
    user_service_found = any('user_service' in s.get('file_path', '').lower() for s in sources)

    passed = user_service_found

    if passed:
        logger.info("✅ Query found newly added user service")
    else:
        logger.warning("⚠️  Query did not find user service")
        logger.info(f"Sources: {[s.get('file_path') for s in sources]}")

    duration = time.time() - start_time
    reporter.add_result("Query New Feature", passed, duration)

    return passed


def test_incremental_after_modification(
    api_helper: APIHelper,
    repo_id: str,
    repo_path: Path,
    reporter: TestReporter
) -> bool:
    """Test incremental indexing after file modification."""
    logger.info("\n=== Test: Incremental Indexing (Modified File) ===")
    start_time = time.time()

    # Get current status
    initial_status = api_helper.get_indexing_status(repo_id)
    initial_chunks = initial_status.get('total_chunks', 0) if initial_status else 0

    # Modify file and commit
    modified_commit_hash = modify_existing_code_commit(repo_path)

    # Trigger incremental indexing
    logger.info("Triggering incremental indexing for modification...")
    response = api_helper.client.post(f"{api_helper.base_url}/api/repos/{repo_id}/index/incremental")

    if response.status_code != 200:
        logger.error(f"❌ Failed to trigger incremental indexing: {response.text}")
        reporter.add_result("Incremental Indexing (Modified File)", False, time.time() - start_time)
        return False

    # Wait for indexing
    time.sleep(10)
    completed = api_helper.wait_for_indexing(repo_id, timeout=60)

    if not completed:
        logger.error("❌ Incremental indexing did not complete")
        reporter.add_result("Incremental Indexing (Modified File)", False, time.time() - start_time)
        return False

    # Query for new functionality
    query = "How do I delete a user?"
    result = api_helper.query(query, repo_id=repo_id)

    if not result:
        logger.error("❌ Query failed")
        passed = False
    else:
        answer = result.get('answer', '').lower()
        sources = result.get('sources', [])

        # Check if delete functionality is mentioned
        mentions_delete = 'delete' in answer

        # Check if user_service is in sources
        has_user_service = any('user_service' in s.get('file_path', '').lower() for s in sources)

        passed = mentions_delete and has_user_service

        if passed:
            logger.info("✅ Modified code indexed and queryable")
        else:
            logger.warning("⚠️  Modified functionality not properly indexed")
            logger.info(f"Delete mentioned: {mentions_delete}, User service in sources: {has_user_service}")

    duration = time.time() - start_time
    reporter.add_result("Incremental Indexing (Modified File)", passed, duration)

    return passed


def cleanup_test_repository():
    """Clean up test repository."""
    logger.info("\n=== Cleanup: Removing Test Repository ===")

    if TEST_REPO_DIR.exists():
        shutil.rmtree(TEST_REPO_DIR)
        logger.info("✅ Test repository cleaned up")


def main():
    """Run all commit detection tests."""
    logger.info("=" * 70)
    logger.info("TEST SUITE 3: COMMIT DETECTION & INCREMENTAL INDEXING")
    logger.info("=" * 70)

    reporter = TestReporter()
    api_helper = APIHelper(RAG_API_URL, timeout=60)

    # Check if API is available
    if not api_helper.wait_for_api(timeout=30):
        logger.error("❌ RAG API is not available")
        return 1

    try:
        # Setup
        repo_path = setup_test_repository_with_commits()

        # Run tests
        repo_id = test_initial_indexing(api_helper, repo_path, reporter)

        if repo_id:
            test_incremental_after_new_commit(api_helper, repo_id, repo_path, reporter)
            test_query_new_feature(api_helper, repo_id, reporter)
            test_incremental_after_modification(api_helper, repo_id, repo_path, reporter)
        else:
            logger.error("❌ Cannot proceed without valid repository ID")

    except Exception as e:
        logger.error(f"❌ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        api_helper.close()
        cleanup_test_repository()

    # Print summary
    all_passed = reporter.print_summary()

    if all_passed:
        logger.info("\n✅ All commit detection tests passed!")
        logger.info("Incremental indexing is working correctly")
        return 0
    else:
        logger.error("\n❌ Some commit detection tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
