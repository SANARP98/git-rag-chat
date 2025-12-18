# Testing Guide - Git RAG Chat

Comprehensive testing framework for validating the Git RAG Chat system.

## Test Structure

```
tests/
├── integration/               # End-to-end integration tests
│   ├── test_1_docker.py      # Container health checks
│   ├── test_2_indexing.py    # Repository indexing
│   ├── test_3_commits.py     # Commit detection
│   └── helpers.py            # Test utilities
├── fixtures/                  # Test data
│   ├── sample-code.py        # Sample authentication module
│   └── sample-database.py    # Sample database module
├── run_all_tests.py          # Main test orchestrator
├── Dockerfile                # Test container
└── requirements.txt          # Test dependencies
```

## Quick Start

### Option 1: Automated Testing (Recommended)

Run all tests in a containerized environment:

```bash
# Build and run test container
docker-compose --profile testing up --build test-runner

# Or run tests manually in container
docker-compose --profile testing run --rm test-runner
```

### Option 2: Manual Testing

Run tests directly on your machine:

```bash
# 1. Start all services
docker-compose up -d

# 2. Install test dependencies
cd tests
pip install -r requirements.txt

# 3. Run all tests
python run_all_tests.py

# Or run individual tests
python integration/test_1_docker.py
python integration/test_2_indexing.py
python integration/test_3_commits.py
```

## Test Suites

### 1. Docker Health Tests (`test_1_docker.py`)

**Purpose**: Verify all Docker containers are running and healthy

**Tests**:
- ✅ Container Status - All required containers are running
- ✅ Container Health - Health checks pass
- ✅ API Accessibility - All APIs respond correctly
- ✅ Network Connectivity - Containers can communicate
- ✅ Volume Mounts - Data directories exist
- ✅ Container Logs - No critical errors in logs

**Expected Duration**: 30-60 seconds

**Example Output**:
```
=== Test: Container Status ===
✅ git-rag-chromadb is running
✅ git-rag-pipeline is running
✅ git-rag-ui is running

=== Test: API Accessibility ===
✅ RAG Pipeline is accessible at http://localhost:8001
✅ ChromaDB is accessible at http://localhost:8000
✅ Gradio UI is accessible at http://localhost:7860
```

### 2. Repository Indexing Tests (`test_2_indexing.py`)

**Purpose**: Validate repository indexing and querying

**Tests**:
- ✅ Add Repository - Repository can be added via API
- ✅ Indexing Completion - Indexing completes successfully
- ✅ Indexed Files - Expected files are indexed
- ✅ Basic Query - Simple queries return results
- ✅ Query Specific Module - Module-specific queries work
- ✅ Query API Endpoints - API endpoint queries work

**Test Repository**:
- Creates a fresh Git repository
- Adds Python files (auth, database, main, api)
- Contains ~5 files with multiple functions
- Total size: ~500 lines of code

**Expected Duration**: 2-5 minutes (depending on indexing speed)

**Example Output**:
```
=== Test: Add Repository ===
✅ Repository added with ID: abc123

=== Test: Indexing Completion ===
⏳ Indexing in progress: 3/5 files
⏳ Indexing in progress: 5/5 files
✅ Indexing completed for abc123
Files indexed: 5
Total chunks: 42

=== Test: Basic Query ===
✅ Query returned answer (1024 chars)
✅ Query returned 8 source(s)
✅ Sources include authentication module
```

### 3. Commit Detection Tests (`test_3_commits.py`)

**Purpose**: Verify commit tracking and incremental indexing

**Tests**:
- ✅ Initial Indexing - First indexing works
- ✅ Incremental Indexing (New File) - New commits are detected
- ✅ Query New Feature - Newly added code is queryable
- ✅ Incremental Indexing (Modified File) - Modified files are re-indexed

**Test Flow**:
1. Create repository with initial commit
2. Index repository
3. Add new feature (user service) via commit
4. Trigger incremental indexing
5. Query for new feature
6. Modify existing file via commit
7. Verify changes are indexed

**Expected Duration**: 2-4 minutes

**Example Output**:
```
=== Test: Incremental Indexing (New File) ===
Initial state: 1 files, 5 chunks
✅ Commit 2 (new feature): 4f8a92c3
Triggering incremental indexing...
New state: 2 files, 28 chunks
✅ Incremental indexing added 1 files, 23 chunks

=== Test: Query New Feature ===
✅ Query found newly added user service
```

## Test Data

### Sample Code Fixtures

Located in `tests/fixtures/`:

1. **sample-code.py** - Authentication module
   - User class with password hashing
   - AuthenticationManager with login/logout
   - Session management

2. **sample-database.py** - Database module
   - DatabaseConnection with context manager
   - UserRepository with CRUD operations
   - SQLite integration

These files simulate realistic Python code for testing.

## Test Helpers

The `helpers.py` module provides utilities:

### DockerHelper
- `is_container_running()` - Check container status
- `get_container_logs()` - Retrieve container logs
- `wait_for_container()` - Wait for container to start
- `get_container_health()` - Get health status

### APIHelper
- `wait_for_api()` - Wait for API availability
- `add_repository()` - Add repository via API
- `get_indexing_status()` - Get indexing status
- `wait_for_indexing()` - Wait for indexing completion
- `query()` - Query repository

### GitRepoHelper
- `create_test_repo()` - Create test Git repository
- `add_file()` - Add file to repository
- `commit_changes()` - Create Git commit
- `get_latest_commit_hash()` - Get commit hash

### TestReporter
- `add_result()` - Record test result
- `print_summary()` - Print final summary

## Expected Results

### All Tests Passing

```
======================================================================
INTEGRATION TEST SUMMARY
======================================================================

✅ PASS - test_1_docker.py               (45.23s)
✅ PASS - test_2_indexing.py             (187.45s)
✅ PASS - test_3_commits.py              (142.67s)

======================================================================
Results: 3/3 test suites passed
Total Duration: 375.35s
======================================================================

🎉 All integration tests passed!

System is ready for production use!
```

### Some Tests Failing

```
======================================================================
TEST SUMMARY
======================================================================
❌ FAIL - Container Status (10.50s)
    Missing: git-rag-pipeline

======================================================================
Results: 5/6 tests passed
======================================================================

❌ Some Docker health checks failed
Fix issues before proceeding
```

## Troubleshooting

### Test Failures

#### Docker Tests Fail

**Problem**: Containers not running

**Solution**:
```bash
# Check containers
docker ps

# Start all services
docker-compose up -d

# Check logs
docker logs git-rag-pipeline
docker logs git-rag-chromadb
```

#### Indexing Tests Timeout

**Problem**: Indexing takes too long or hangs

**Solution**:
1. Check RAG pipeline logs:
   ```bash
   docker logs git-rag-pipeline
   ```

2. Verify ChromaDB is accessible:
   ```bash
   curl http://localhost:8000/api/v1/heartbeat
   ```

3. Check embedding model is downloaded:
   ```bash
   docker exec git-rag-pipeline ls -la /app/data/models
   ```

#### Query Tests Return Empty

**Problem**: Queries don't return results

**Solution**:
1. Verify repository is fully indexed
2. Check LLM provider configuration
3. Test embedding generation:
   ```bash
   docker exec git-rag-pipeline python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
   ```

### Common Issues

#### Port Conflicts

**Error**: `Bind for 0.0.0.0:8001 failed: port is already allocated`

**Solution**:
```bash
# Find process using port
lsof -i :8001

# Kill process or change port in .env
```

#### Permission Denied

**Error**: `Permission denied while trying to connect to Docker daemon`

**Solution**:
```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER

# Restart session
newgrp docker
```

#### Network Issues

**Error**: `Failed to resolve 'rag-pipeline'`

**Solution**:
```bash
# Check network exists
docker network ls | grep rag-network

# Recreate network
docker-compose down
docker-compose up -d
```

## Performance Benchmarks

Target performance metrics:

| Metric | Target | Actual |
|--------|--------|--------|
| Container Startup | < 30s | TBD |
| Index 100 files | < 2 min | TBD |
| Query Response | < 5s | TBD |
| Incremental Index (1 file) | < 10s | TBD |
| Commit Detection | < 5s | TBD |

## Adding New Tests

### Template for New Test

```python
"""Test X: Description."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from helpers import TestReporter, APIHelper

def test_feature(api_helper: APIHelper, reporter: TestReporter) -> bool:
    """Test a specific feature."""
    logger.info("\n=== Test: Feature Name ===")
    start_time = time.time()

    # Test logic here
    passed = True

    duration = time.time() - start_time
    reporter.add_result("Feature Name", passed, duration)
    return passed

def main():
    """Run all tests."""
    reporter = TestReporter()
    api_helper = APIHelper("http://localhost:8001")

    test_feature(api_helper, reporter)

    all_passed = reporter.print_summary()
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
```

### Add to Test Runner

Edit `run_all_tests.py`:

```python
tests = [
    "test_1_docker.py",
    "test_2_indexing.py",
    "test_3_commits.py",
    "test_4_your_new_test.py"  # Add here
]
```

## Continuous Integration

For CI/CD integration:

```yaml
# .github/workflows/test.yml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Start services
        run: docker-compose up -d

      - name: Run tests
        run: docker-compose --profile testing up --build test-runner

      - name: Stop services
        run: docker-compose down
```

## Test Cleanup

All tests automatically clean up:
- Test repositories are deleted after tests
- No data persists between test runs
- Containers remain running for next test

To manually clean up:

```bash
# Remove test repositories
rm -rf tests/fixtures/test-repo
rm -rf tests/fixtures/commit-test-repo

# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v
```

## Next Steps

After all tests pass:

1. **Production Deployment**: System is validated for production use
2. **Add Your Repositories**: Start indexing your own code
3. **Performance Tuning**: Optimize based on your repository size
4. **Custom Tests**: Add tests for your specific use cases

## Support

If tests fail consistently:

1. Check logs in `docker logs <container>`
2. Review [troubleshooting section](#troubleshooting)
3. Check system requirements (RAM, disk space)
4. Verify Docker/Docker Compose versions
5. Open an issue with test output
