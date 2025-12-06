"""Test 2: Repository Indexing."""

import sys
import time
import logging
import shutil
from pathlib import Path

# Add helpers to path
sys.path.insert(0, str(Path(__file__).parent))

from helpers import DockerHelper, APIHelper, GitRepoHelper, TestReporter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
RAG_API_URL = "http://localhost:8001"
TEST_REPO_DIR = Path(__file__).parent.parent / "fixtures" / "test-repo"


def setup_test_repository() -> Path:
    """Create a test Git repository with sample code."""
    logger.info("\n=== Setup: Creating Test Repository ===")

    # Clean up existing test repo
    if TEST_REPO_DIR.exists():
        shutil.rmtree(TEST_REPO_DIR)

    # Create new test repo
    repo_path = GitRepoHelper.create_test_repo(TEST_REPO_DIR.parent, TEST_REPO_DIR.name)

    # Add sample files
    # 1. README
    GitRepoHelper.add_file(
        repo_path,
        "README.md",
        """# Test Repository

This is a test repository for Git RAG Chat integration testing.

## Features

- User authentication
- Database operations
- API endpoints
"""
    )

    # 2. Authentication module
    auth_code = (Path(__file__).parent.parent / "fixtures" / "sample-code.py").read_text()
    GitRepoHelper.add_file(repo_path, "src/auth.py", auth_code)

    # 3. Database module
    db_code = (Path(__file__).parent.parent / "fixtures" / "sample-database.py").read_text()
    GitRepoHelper.add_file(repo_path, "src/database.py", db_code)

    # 4. Main module
    GitRepoHelper.add_file(
        repo_path,
        "src/main.py",
        """#!/usr/bin/env python
\"\"\"Main application entry point.\"\"\"

from auth import AuthenticationManager
from database import DatabaseConnection, UserRepository


def main():
    \"\"\"Main function.\"\"\"
    # Initialize database
    db = DatabaseConnection("app.db")
    user_repo = UserRepository(db)

    # Initialize auth manager
    auth_manager = AuthenticationManager()

    print("Application started successfully!")


if __name__ == "__main__":
    main()
"""
    )

    # 5. API module
    GitRepoHelper.add_file(
        repo_path,
        "src/api.py",
        """\"\"\"API endpoints module.\"\"\"

from typing import Dict, Any


def health_check() -> Dict[str, Any]:
    \"\"\"Health check endpoint.

    Returns:
        Health status
    \"\"\"
    return {"status": "healthy", "version": "1.0.0"}


def get_user_endpoint(user_id: int) -> Dict[str, Any]:
    \"\"\"Get user by ID.

    Args:
        user_id: User ID

    Returns:
        User data
    \"\"\"
    # TODO: Implement user retrieval
    return {"id": user_id, "name": "Test User"}


def create_user_endpoint(username: str, email: str) -> Dict[str, Any]:
    \"\"\"Create new user.

    Args:
        username: Username
        email: Email address

    Returns:
        Created user data
    \"\"\"
    # TODO: Implement user creation
    return {"username": username, "email": email}
"""
    )

    # Create initial commit
    GitRepoHelper.commit_changes(repo_path, "Initial commit with authentication and database modules")

    logger.info(f"✅ Test repository created at {repo_path}")
    logger.info(f"✅ Initial commit: {GitRepoHelper.get_latest_commit_hash(repo_path)}")

    return repo_path


def test_add_repository(api_helper: APIHelper, repo_path: Path, reporter: TestReporter) -> str:
    """Test adding repository via API."""
    logger.info("\n=== Test: Add Repository ===")
    start_time = time.time()

    repo_id = api_helper.add_repository(str(repo_path), "test-repo")

    if repo_id:
        logger.info(f"✅ Repository added with ID: {repo_id}")
        passed = True
    else:
        logger.error("❌ Failed to add repository")
        passed = False

    duration = time.time() - start_time
    reporter.add_result("Add Repository", passed, duration, f"Repo ID: {repo_id}" if repo_id else None)

    return repo_id


def test_indexing_completion(api_helper: APIHelper, repo_id: str, reporter: TestReporter) -> bool:
    """Test that indexing completes successfully."""
    logger.info("\n=== Test: Indexing Completion ===")
    start_time = time.time()

    # Wait for indexing to complete (5 minute timeout)
    completed = api_helper.wait_for_indexing(repo_id, timeout=300, check_interval=5)

    if completed:
        logger.info("✅ Indexing completed successfully")

        # Get final status
        status = api_helper.get_indexing_status(repo_id)
        if status:
            logger.info(f"Files indexed: {status.get('files_indexed', 0)}")
            logger.info(f"Total chunks: {status.get('total_chunks', 0)}")

    else:
        logger.error("❌ Indexing did not complete within timeout")

    duration = time.time() - start_time
    reporter.add_result("Indexing Completion", completed, duration)

    return completed


def test_indexed_files(api_helper: APIHelper, repo_id: str, reporter: TestReporter) -> bool:
    """Test that expected files were indexed."""
    logger.info("\n=== Test: Indexed Files ===")
    start_time = time.time()

    status = api_helper.get_indexing_status(repo_id)

    if not status:
        logger.error("❌ Could not get indexing status")
        reporter.add_result("Indexed Files", False, time.time() - start_time)
        return False

    files_indexed = status.get('files_indexed', 0)
    total_chunks = status.get('total_chunks', 0)

    # We expect at least 5 files (README, auth, database, main, api)
    expected_min_files = 5

    passed = files_indexed >= expected_min_files and total_chunks > 0

    if passed:
        logger.info(f"✅ Indexed {files_indexed} files with {total_chunks} chunks")
    else:
        logger.error(f"❌ Expected at least {expected_min_files} files, got {files_indexed}")

    duration = time.time() - start_time
    details = f"{files_indexed} files, {total_chunks} chunks"
    reporter.add_result("Indexed Files", passed, duration, details)

    return passed


def test_query_basic(api_helper: APIHelper, repo_id: str, reporter: TestReporter) -> bool:
    """Test basic query functionality."""
    logger.info("\n=== Test: Basic Query ===")
    start_time = time.time()

    query = "How does authentication work?"

    result = api_helper.query(query, repo_id=repo_id)

    if not result:
        logger.error("❌ Query failed")
        reporter.add_result("Basic Query", False, time.time() - start_time)
        return False

    answer = result.get('answer', '')
    sources = result.get('sources', [])

    # Check that we got an answer and sources
    has_answer = len(answer) > 0
    has_sources = len(sources) > 0

    passed = has_answer and has_sources

    if passed:
        logger.info(f"✅ Query returned answer ({len(answer)} chars)")
        logger.info(f"✅ Query returned {len(sources)} source(s)")

        # Check if auth-related code is in sources
        auth_mentioned = any('auth' in s.get('file_path', '').lower() for s in sources)
        if auth_mentioned:
            logger.info("✅ Sources include authentication module")
        else:
            logger.warning("⚠️  Sources don't mention authentication module")

    else:
        logger.error(f"❌ Query issues: answer={has_answer}, sources={has_sources}")

    duration = time.time() - start_time
    details = f"Answer: {len(answer)} chars, Sources: {len(sources)}"
    reporter.add_result("Basic Query", passed, duration, details)

    return passed


def test_query_specific_module(api_helper: APIHelper, repo_id: str, reporter: TestReporter) -> bool:
    """Test query about specific module."""
    logger.info("\n=== Test: Query Specific Module ===")
    start_time = time.time()

    query = "Show me the database connection code"

    result = api_helper.query(query, repo_id=repo_id)

    if not result:
        logger.error("❌ Query failed")
        reporter.add_result("Query Specific Module", False, time.time() - start_time)
        return False

    sources = result.get('sources', [])

    # Check if database.py is in sources
    db_mentioned = any('database' in s.get('file_path', '').lower() for s in sources)

    passed = db_mentioned

    if passed:
        logger.info("✅ Query correctly retrieved database module")
    else:
        logger.warning("⚠️  Query did not retrieve database module")
        logger.info(f"Sources: {[s.get('file_path') for s in sources]}")

    duration = time.time() - start_time
    details = f"Sources: {len(sources)}, DB mentioned: {db_mentioned}"
    reporter.add_result("Query Specific Module", passed, duration, details)

    return passed


def test_query_api_endpoints(api_helper: APIHelper, repo_id: str, reporter: TestReporter) -> bool:
    """Test query about API endpoints."""
    logger.info("\n=== Test: Query API Endpoints ===")
    start_time = time.time()

    query = "What API endpoints are available?"

    result = api_helper.query(query, repo_id=repo_id)

    if not result:
        logger.error("❌ Query failed")
        reporter.add_result("Query API Endpoints", False, time.time() - start_time)
        return False

    answer = result.get('answer', '')
    sources = result.get('sources', [])

    # Check if api.py is in sources
    api_mentioned = any('api' in s.get('file_path', '').lower() for s in sources)

    # Check if answer mentions endpoints
    answer_lower = answer.lower()
    mentions_endpoints = 'endpoint' in answer_lower or 'health' in answer_lower or 'user' in answer_lower

    passed = api_mentioned and mentions_endpoints

    if passed:
        logger.info("✅ Query correctly identified API endpoints")
    else:
        logger.warning("⚠️  Query may not have correctly identified endpoints")

    duration = time.time() - start_time
    details = f"API mentioned: {api_mentioned}, Endpoints in answer: {mentions_endpoints}"
    reporter.add_result("Query API Endpoints", passed, duration, details)

    return passed


def cleanup_test_repository():
    """Clean up test repository."""
    logger.info("\n=== Cleanup: Removing Test Repository ===")

    if TEST_REPO_DIR.exists():
        shutil.rmtree(TEST_REPO_DIR)
        logger.info("✅ Test repository cleaned up")


def main():
    """Run all indexing tests."""
    logger.info("=" * 70)
    logger.info("TEST SUITE 2: REPOSITORY INDEXING")
    logger.info("=" * 70)

    reporter = TestReporter()
    api_helper = APIHelper(RAG_API_URL, timeout=60)

    # Check if API is available
    if not api_helper.wait_for_api(timeout=30):
        logger.error("❌ RAG API is not available")
        logger.error("Make sure services are running: docker-compose up -d")
        return 1

    try:
        # Setup
        repo_path = setup_test_repository()

        # Run tests
        repo_id = test_add_repository(api_helper, repo_path, reporter)

        if repo_id:
            test_indexing_completion(api_helper, repo_id, reporter)
            test_indexed_files(api_helper, repo_id, reporter)
            test_query_basic(api_helper, repo_id, reporter)
            test_query_specific_module(api_helper, repo_id, reporter)
            test_query_api_endpoints(api_helper, repo_id, reporter)
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
        logger.info("\n✅ All indexing tests passed!")
        logger.info("Proceed to test_3_commits.py")
        return 0
    else:
        logger.error("\n❌ Some indexing tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
