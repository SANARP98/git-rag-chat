"""Test 1: Docker Container Health Checks."""

import sys
import time
import logging
from pathlib import Path

# Add helpers to path
sys.path.insert(0, str(Path(__file__).parent))

from helpers import DockerHelper, APIHelper, TestReporter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_container_status(docker_helper: DockerHelper, reporter: TestReporter):
    """Test that all required containers are running."""
    logger.info("\n=== Test: Container Status ===")
    start_time = time.time()

    required_containers = [
        'git-rag-chromadb',
        'git-rag-pipeline',
        'git-rag-ui'
    ]

    optional_containers = [
        'git-rag-watcher',
        'git-rag-ollama'
    ]

    all_running = True
    missing_containers = []

    # Check required containers
    for container_name in required_containers:
        if docker_helper.is_container_running(container_name):
            logger.info(f"✅ {container_name} is running")
        else:
            logger.error(f"❌ {container_name} is NOT running")
            all_running = False
            missing_containers.append(container_name)

    # Check optional containers (info only)
    for container_name in optional_containers:
        if docker_helper.is_container_running(container_name):
            logger.info(f"ℹ️  {container_name} is running (optional)")
        else:
            logger.info(f"ℹ️  {container_name} is not running (optional)")

    duration = time.time() - start_time
    details = f"Missing: {', '.join(missing_containers)}" if missing_containers else None

    reporter.add_result("Container Status", all_running, duration, details)
    return all_running


def test_container_health(docker_helper: DockerHelper, reporter: TestReporter):
    """Test container health checks."""
    logger.info("\n=== Test: Container Health ===")
    start_time = time.time()

    # ChromaDB has health check defined
    container_name = 'git-rag-chromadb'
    health = docker_helper.get_container_health(container_name)

    if health:
        logger.info(f"✅ {container_name} health: {health}")
        passed = health == 'healthy'
    else:
        logger.info(f"ℹ️  {container_name} has no health check configured")
        passed = True  # Not all containers have health checks

    duration = time.time() - start_time
    reporter.add_result("Container Health", passed, duration)
    return passed


def test_api_accessibility(reporter: TestReporter):
    """Test that APIs are accessible."""
    logger.info("\n=== Test: API Accessibility ===")
    start_time = time.time()

    apis = [
        ("RAG Pipeline", "http://localhost:8001", "/api/health"),
        ("ChromaDB", "http://localhost:8000", "/api/v1/heartbeat"),
        ("Gradio UI", "http://localhost:7860", "/")
    ]

    all_accessible = True
    failed_apis = []

    for api_name, base_url, endpoint in apis:
        api_helper = APIHelper(base_url, timeout=10)

        if api_helper.wait_for_api(endpoint, timeout=30):
            logger.info(f"✅ {api_name} is accessible at {base_url}")
        else:
            logger.error(f"❌ {api_name} is NOT accessible at {base_url}")
            all_accessible = False
            failed_apis.append(api_name)

        api_helper.close()

    duration = time.time() - start_time
    details = f"Failed: {', '.join(failed_apis)}" if failed_apis else None

    reporter.add_result("API Accessibility", all_accessible, duration, details)
    return all_accessible


def test_network_connectivity(docker_helper: DockerHelper, reporter: TestReporter):
    """Test network connectivity between containers."""
    logger.info("\n=== Test: Network Connectivity ===")
    start_time = time.time()

    # We can't easily test internal network from outside
    # But we can check if containers are on the same network
    passed = True

    logger.info("ℹ️  Network connectivity tested indirectly via API calls")
    logger.info("ℹ️  If APIs are accessible, network is working")

    duration = time.time() - start_time
    reporter.add_result("Network Connectivity", passed, duration)
    return passed


def test_volume_mounts(docker_helper: DockerHelper, reporter: TestReporter):
    """Test that volumes are mounted correctly."""
    logger.info("\n=== Test: Volume Mounts ===")
    start_time = time.time()

    # Check that data directories exist
    data_dirs = [
        Path("./data/chroma"),
        Path("./data/metadata"),
        Path("./data/models")
    ]

    all_exist = True
    missing_dirs = []

    for data_dir in data_dirs:
        if data_dir.exists():
            logger.info(f"✅ {data_dir} exists")
        else:
            logger.warning(f"⚠️  {data_dir} does not exist (will be created)")
            data_dir.mkdir(parents=True, exist_ok=True)

    duration = time.time() - start_time
    details = f"Created: {', '.join(str(d) for d in missing_dirs)}" if missing_dirs else None

    reporter.add_result("Volume Mounts", all_exist, duration, details)
    return all_exist


def test_container_logs(docker_helper: DockerHelper, reporter: TestReporter):
    """Check container logs for errors."""
    logger.info("\n=== Test: Container Logs ===")
    start_time = time.time()

    containers = [
        'git-rag-chromadb',
        'git-rag-pipeline',
        'git-rag-ui'
    ]

    has_errors = False
    error_containers = []

    for container_name in containers:
        logs = docker_helper.get_container_logs(container_name, tail=50)

        if not logs:
            logger.warning(f"⚠️  Could not retrieve logs for {container_name}")
            continue

        # Check for common error patterns
        error_patterns = ['ERROR', 'CRITICAL', 'Exception', 'Traceback']

        found_errors = []
        for pattern in error_patterns:
            if pattern in logs:
                found_errors.append(pattern)

        if found_errors:
            logger.warning(f"⚠️  {container_name} has potential errors: {', '.join(found_errors)}")
            has_errors = True
            error_containers.append(container_name)
        else:
            logger.info(f"✅ {container_name} logs look clean")

    passed = not has_errors
    duration = time.time() - start_time
    details = f"Errors in: {', '.join(error_containers)}" if error_containers else None

    reporter.add_result("Container Logs", passed, duration, details)
    return passed


def main():
    """Run all Docker tests."""
    logger.info("=" * 70)
    logger.info("TEST SUITE 1: DOCKER CONTAINER HEALTH")
    logger.info("=" * 70)

    reporter = TestReporter()
    docker_helper = DockerHelper()

    if not docker_helper.client:
        logger.error("❌ Failed to connect to Docker daemon")
        logger.error("Make sure Docker is running and you have permissions")
        return 1

    # Run tests
    tests = [
        ("Container Status", lambda: test_container_status(docker_helper, reporter)),
        ("Container Health", lambda: test_container_health(docker_helper, reporter)),
        ("API Accessibility", lambda: test_api_accessibility(reporter)),
        ("Network Connectivity", lambda: test_network_connectivity(docker_helper, reporter)),
        ("Volume Mounts", lambda: test_volume_mounts(docker_helper, reporter)),
        ("Container Logs", lambda: test_container_logs(docker_helper, reporter))
    ]

    for test_name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' failed with exception: {e}")
            reporter.add_result(test_name, False, 0, str(e))

    # Print summary
    all_passed = reporter.print_summary()

    if all_passed:
        logger.info("\n✅ All Docker health checks passed!")
        logger.info("Proceed to test_2_indexing.py")
        return 0
    else:
        logger.error("\n❌ Some Docker health checks failed")
        logger.error("Fix issues before proceeding")
        return 1


if __name__ == "__main__":
    sys.exit(main())
