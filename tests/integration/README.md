# Integration Testing Framework

Comprehensive end-to-end testing for Git RAG Chat system.

## Test Structure

```
tests/
├── integration/           # End-to-end integration tests
│   ├── test_1_docker.py          # Container health checks
│   ├── test_2_indexing.py        # Repository indexing tests
│   ├── test_3_commits.py         # Commit tracking tests
│   ├── test_4_queries.py         # Query pipeline tests
│   ├── test_5_file_watcher.py    # File watcher tests
│   ├── test_6_ui.py              # Gradio UI tests
│   └── helpers.py                # Test utilities
├── fixtures/              # Test data
│   └── sample-repo/              # Sample Git repository
└── run_all_tests.py      # Test orchestrator

```

## Running Tests

### Option 1: Automated Test Container

```bash
# Build and run test container
docker-compose --profile testing up test-runner

# Or manually
docker-compose build test-runner
docker-compose run --rm test-runner
```

### Option 2: Manual Testing

```bash
# Start services
docker-compose up -d

# Run tests
cd tests
python run_all_tests.py

# Run specific test
python integration/test_2_indexing.py
```

## Test Coverage

### 1. Docker Container Health (`test_1_docker.py`)
- All containers start successfully
- Health checks pass
- Network connectivity between containers
- Volume mounts are correct
- API endpoints are accessible

### 2. Repository Indexing (`test_2_indexing.py`)
- Add repository via API
- Verify indexing completes
- Check ChromaDB collection creation
- Verify SQLite metadata
- Test incremental re-indexing

### 3. Commit Tracking (`test_3_commits.py`)
- Create new commits in test repo
- Verify commit detection
- Check incremental indexing
- Validate new chunks in ChromaDB
- Test commit history queries

### 4. Query Pipeline (`test_4_queries.py`)
- Semantic search retrieval
- LLM response generation
- Source code citations
- Query various code patterns
- Test different languages (Python, JS, etc.)

### 5. File Watcher (`test_5_file_watcher.py`)
- Detect uncommitted file changes
- Verify debouncing works
- Test incremental indexing
- Check deleted files handling

### 6. Gradio UI (`test_6_ui.py`)
- UI loads successfully
- Repository addition workflow
- Chat interface functionality
- Settings persistence

## Test Data

### Sample Repository Structure

```
tests/fixtures/sample-repo/
├── .git/
├── src/
│   ├── main.py           # Entry point
│   ├── auth.py           # Authentication module
│   ├── database.py       # Database connections
│   └── utils/
│       ├── helpers.py    # Utility functions
│       └── validators.py # Input validation
├── tests/
│   └── test_auth.py      # Auth tests
├── README.md
└── requirements.txt
```

## Test Scenarios

### Scenario 1: Fresh Repository
1. Create new Git repository
2. Add initial commit
3. Index repository
4. Verify all files indexed
5. Query: "How does authentication work?"
6. Verify response includes auth.py content

### Scenario 2: Code Changes
1. Modify auth.py
2. Create new commit
3. Wait for incremental indexing
4. Query: "What changed in authentication?"
5. Verify response reflects new code

### Scenario 3: Uncommitted Changes
1. Modify database.py (don't commit)
2. Wait for file watcher detection
3. Query: "Show database connection code"
4. Verify response includes uncommitted changes

### Scenario 4: Multi-Language Support
1. Add JavaScript files
2. Create commit
3. Index repository
4. Query: "Show all API endpoints"
5. Verify retrieval from both Python and JS

## Assertions

Each test should verify:
- ✅ Operation completes successfully
- ✅ Expected data is present
- ✅ No errors in logs
- ✅ Performance within acceptable range
- ✅ State is consistent across services

## Performance Benchmarks

- **Container Startup**: < 30 seconds
- **Repository Indexing**: < 2 minutes for 100 files
- **Query Response**: < 5 seconds end-to-end
- **Incremental Index**: < 10 seconds for single file
- **File Watch Detection**: < 5 seconds after change

## Continuous Testing

The test suite can be run:
- Manually during development
- Automatically via test container
- In CI/CD pipeline (future)
- Before each release

## Troubleshooting Tests

### Tests Fail to Connect
- Ensure Docker containers are running
- Check network connectivity: `docker network inspect git-rag-chat-local_rag-network`
- Verify ports are exposed correctly

### Indexing Tests Timeout
- Increase timeout values
- Check RAG pipeline logs: `docker logs git-rag-pipeline`
- Verify ChromaDB is accessible

### Query Tests Return Empty
- Ensure repository is fully indexed
- Check embedding model is loaded
- Verify LLM provider configuration

## Next Steps After Testing

1. Document all identified issues
2. Create GitHub issues for bugs
3. Implement fixes
4. Re-run tests to verify
5. Update performance benchmarks
6. Add new test cases for edge cases
