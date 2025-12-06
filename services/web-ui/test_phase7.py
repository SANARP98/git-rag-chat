"""Test script for Phase 7: Gradio Web UI."""

import os
import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all components can be imported."""
    logger.info("Testing imports...")

    try:
        from components import ChatInterface, RepositoryManager, RepositoryValidator
        logger.info("✅ All components imported successfully")
        return True
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False


def test_repository_validator():
    """Test repository validator."""
    logger.info("\nTesting RepositoryValidator...")

    from components.repo_validator import RepositoryValidator

    # Test non-existent path
    result = RepositoryValidator.quick_validate("/nonexistent/path")
    assert "does not exist" in result, f"Expected 'does not exist', got: {result}"
    logger.info("✅ Non-existent path validation works")

    # Test empty path
    result = RepositoryValidator.quick_validate("")
    assert result == "", f"Expected empty string, got: {result}"
    logger.info("✅ Empty path validation works")

    # Test current directory (if it's a git repo)
    current_dir = str(Path(__file__).parent.parent.parent)
    result = RepositoryValidator.quick_validate(current_dir)
    logger.info(f"Current directory validation: {result}")

    # Test path allowed check
    allowed = RepositoryValidator.is_path_allowed("/Users/test/repo", ["/Users", "/home"])
    assert allowed, "Path should be allowed"
    logger.info("✅ Path allowed check works")

    not_allowed = RepositoryValidator.is_path_allowed("/etc/passwd", ["/Users", "/home"])
    assert not not_allowed, "Path should not be allowed"
    logger.info("✅ Path not allowed check works")

    logger.info("✅ RepositoryValidator tests passed")
    return True


def test_repository_manager():
    """Test repository manager (without API calls)."""
    logger.info("\nTesting RepositoryManager...")

    from components.repo_manager import RepositoryManager

    # Create manager with mock API URL
    manager = RepositoryManager(
        rag_api_url="http://localhost:8001",
        allowed_paths=["/Users", "/home"]
    )

    # Test path validation
    result = manager.validate_path("")
    assert result == "", f"Expected empty string, got: {result}"
    logger.info("✅ Empty path validation works")

    result = manager.validate_path("/nonexistent")
    assert "does not exist" in result, f"Expected 'does not exist', got: {result}"
    logger.info("✅ Non-existent path validation works")

    # Cleanup
    manager.close()

    logger.info("✅ RepositoryManager tests passed")
    return True


def test_chat_interface():
    """Test chat interface (without API calls)."""
    logger.info("\nTesting ChatInterface...")

    from components.chat import ChatInterface

    # Create interface with mock API URL
    interface = ChatInterface(rag_api_url="http://localhost:8001")

    # Test response formatting
    answer = "Here's the answer to your question."
    sources = [
        {
            'file_path': 'src/main.py',
            'start_line': 10,
            'end_line': 20,
            'language': 'python',
            'code': 'def main():\n    print("Hello")'
        }
    ]

    formatted = interface._format_response(answer, sources)
    assert "src/main.py" in formatted, "File path should be in formatted response"
    assert "```python" in formatted, "Code block should be in formatted response"
    logger.info("✅ Response formatting works")

    # Test clear history
    history = interface.clear_history()
    assert history == [], "History should be empty"
    logger.info("✅ Clear history works")

    # Test export history
    test_history = [
        ("What is this?", "This is a test response."),
        ("Another question?", "Another answer.")
    ]
    exported = interface.export_history(test_history)
    assert "Exchange 1" in exported, "Export should contain exchange markers"
    assert "What is this?" in exported, "Export should contain user messages"
    logger.info("✅ Export history works")

    # Cleanup
    interface.close()

    logger.info("✅ ChatInterface tests passed")
    return True


def test_gradio_app():
    """Test Gradio app structure (without launching)."""
    logger.info("\nTesting Gradio app...")

    # Set environment variables
    os.environ['RAG_API_URL'] = 'http://localhost:8001'
    os.environ['GRADIO_SERVER_PORT'] = '7860'
    os.environ['GRADIO_ALLOWED_PATHS'] = '/Users,/home'

    try:
        # Import app module
        import app

        # Check that app object exists
        assert hasattr(app, 'app'), "app.py should have 'app' object"
        logger.info("✅ Gradio app object exists")

        # Check that components are initialized
        assert hasattr(app, 'chat_interface'), "app should have chat_interface"
        assert hasattr(app, 'repo_manager'), "app should have repo_manager"
        logger.info("✅ App components initialized")

        logger.info("✅ Gradio app structure tests passed")
        return True

    except Exception as e:
        logger.error(f"❌ Gradio app test failed: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Phase 7: Gradio Web UI - Test Suite")
    logger.info("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("RepositoryValidator", test_repository_validator),
        ("RepositoryManager", test_repository_manager),
        ("ChatInterface", test_chat_interface),
        ("Gradio App", test_gradio_app)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")

    logger.info("=" * 60)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 60)

    if passed == total:
        logger.info("\n🎉 All Phase 7 tests passed!")
        logger.info("\nNext steps:")
        logger.info("1. Build Docker images: docker-compose build")
        logger.info("2. Start services: docker-compose up -d")
        logger.info("3. Access UI: http://localhost:7860")
        return 0
    else:
        logger.error("\n⚠️ Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
