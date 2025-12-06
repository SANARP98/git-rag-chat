"""Run all integration tests in sequence."""

import sys
import subprocess
import logging
from pathlib import Path
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestRunner:
    """Orchestrate all integration tests."""

    def __init__(self):
        """Initialize test runner."""
        self.test_dir = Path(__file__).parent / "integration"
        self.results = []

    def run_test(self, test_script: str) -> bool:
        """Run a single test script.

        Args:
            test_script: Name of test script

        Returns:
            True if test passed
        """
        logger.info(f"\n{'=' * 70}")
        logger.info(f"Running: {test_script}")
        logger.info(f"{'=' * 70}\n")

        test_path = self.test_dir / test_script
        start_time = time.time()

        try:
            result = subprocess.run(
                [sys.executable, str(test_path)],
                capture_output=False,
                text=True
            )

            duration = time.time() - start_time
            passed = result.returncode == 0

            self.results.append({
                'test': test_script,
                'passed': passed,
                'duration': duration
            })

            if passed:
                logger.info(f"\n✅ {test_script} PASSED ({duration:.2f}s)\n")
            else:
                logger.error(f"\n❌ {test_script} FAILED ({duration:.2f}s)\n")

            return passed

        except Exception as e:
            logger.error(f"❌ Failed to run {test_script}: {e}")
            self.results.append({
                'test': test_script,
                'passed': False,
                'duration': time.time() - start_time
            })
            return False

    def print_summary(self):
        """Print overall test summary."""
        logger.info("\n" + "=" * 70)
        logger.info("INTEGRATION TEST SUMMARY")
        logger.info("=" * 70 + "\n")

        total_duration = sum(r['duration'] for r in self.results)
        passed_count = sum(1 for r in self.results if r['passed'])
        total_count = len(self.results)

        for result in self.results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            duration = f"{result['duration']:.2f}s"
            logger.info(f"{status} - {result['test']:<30} ({duration})")

        logger.info("\n" + "=" * 70)
        logger.info(f"Results: {passed_count}/{total_count} test suites passed")
        logger.info(f"Total Duration: {total_duration:.2f}s")
        logger.info("=" * 70 + "\n")

        return passed_count == total_count


def main():
    """Main test orchestrator."""
    logger.info("=" * 70)
    logger.info("GIT RAG CHAT - INTEGRATION TEST SUITE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("This will run all integration tests in sequence:")
    logger.info("1. Docker container health checks")
    logger.info("2. Repository indexing tests")
    logger.info("3. Commit detection and incremental indexing")
    logger.info("")
    logger.info("=" * 70 + "\n")

    runner = TestRunner()

    # Define test sequence
    tests = [
        "test_1_docker.py",
        "test_2_indexing.py",
        "test_3_commits.py"
    ]

    # Run tests in sequence
    all_passed = True

    for test_script in tests:
        passed = runner.run_test(test_script)

        if not passed:
            logger.error(f"\n⚠️  Test {test_script} failed!")
            logger.error("Stopping test execution (fix issues before continuing)")
            all_passed = False
            break

        # Wait between tests
        if test_script != tests[-1]:
            logger.info("⏳ Waiting 5 seconds before next test...\n")
            time.sleep(5)

    # Print summary
    runner.print_summary()

    if all_passed:
        logger.info("🎉 All integration tests passed!")
        logger.info("")
        logger.info("System is ready for production use!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("- Access UI: http://localhost:7860")
        logger.info("- Add your own repositories")
        logger.info("- Start querying your code!")
        return 0
    else:
        logger.error("⚠️  Some integration tests failed")
        logger.error("")
        logger.error("Please review the errors above and:")
        logger.error("1. Check Docker container logs")
        logger.error("2. Verify all services are running")
        logger.error("3. Check network connectivity")
        logger.error("4. Review API endpoints")
        return 1


if __name__ == "__main__":
    sys.exit(main())
