#!/usr/bin/env python3
"""Test script for Phase 3: Embedding & Vector Store integration.

This script tests the core functionality of:
- ChromaDB connection and collection management
- Embedding generation using sentence-transformers
- Repository indexing workflow
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "services" / "rag-pipeline" / "src"))

from core.vector_store import VectorStore
from core.embedder import Embedder
from core.parser import CodeParser
from core.chunker import CodeChunker
from db.metadata_db import MetadataDB
from indexing.indexer import RepositoryIndexer


def test_embedder():
    """Test embedding generation."""
    print("\n=== Testing Embedder ===")

    try:
        embedder = Embedder(model_name="sentence-transformers/all-MiniLM-L6-v2")
        print(f"✓ Embedder initialized")
        print(f"  Model: {embedder.model_name}")
        print(f"  Embedding dimension: {embedder.embedding_dimension}")

        # Test single embedding
        text = "def hello_world():\n    print('Hello, world!')"
        embedding = embedder.embed_text(text)
        print(f"✓ Single embedding generated: shape {embedding.shape}")

        # Test batch embedding
        texts = [
            "def add(a, b):\n    return a + b",
            "class Calculator:\n    pass",
            "import math"
        ]
        embeddings = embedder.embed_batch(texts, show_progress=False)
        print(f"✓ Batch embeddings generated: shape {embeddings.shape}")

        return True
    except Exception as e:
        print(f"✗ Embedder test failed: {e}")
        return False


def test_vector_store():
    """Test ChromaDB vector store."""
    print("\n=== Testing Vector Store ===")

    try:
        # This will fail if ChromaDB is not running
        vector_store = VectorStore(
            host="localhost",
            port=8000,
            embedding_model="sentence-transformers/all-MiniLM-L6-v2"
        )
        print(f"✓ Connected to ChromaDB")

        # Test collection creation
        test_collection = "test_collection_123"
        vector_store.create_collection(test_collection)
        print(f"✓ Created test collection: {test_collection}")

        # Test adding chunks
        test_chunks = [
            {
                'code': 'def test():\n    pass',
                'chunk_type': 'function',
                'name': 'test',
                'file_path': '/test/test.py',
                'language': 'python',
                'start_line': 1,
                'end_line': 2,
                'line_count': 2,
                'char_count': 20,
                'token_count_estimate': 5
            }
        ]

        chunks_added = vector_store.add_chunks(test_collection, test_chunks)
        print(f"✓ Added {chunks_added} chunks to collection")

        # Test querying
        results = vector_store.query(
            test_collection,
            "test function",
            n_results=1
        )
        print(f"✓ Query returned {len(results['ids'][0])} results")

        # Clean up
        vector_store.delete_collection(test_collection)
        print(f"✓ Deleted test collection")

        return True
    except Exception as e:
        print(f"✗ Vector store test failed: {e}")
        print("  Note: Make sure ChromaDB is running (docker-compose up chromadb)")
        return False


def test_parser_and_chunker():
    """Test code parser and chunker."""
    print("\n=== Testing Parser & Chunker ===")

    try:
        parser = CodeParser()
        chunker = CodeChunker()

        # Test Python parsing
        python_code = """
def hello():
    print("Hello")

class MyClass:
    def __init__(self):
        self.value = 42
"""

        file_path = Path("/test/example.py")
        parsed_chunks = parser.parse_file(file_path, python_code)
        print(f"✓ Parsed Python code: {len(parsed_chunks)} chunks")

        # Test chunking
        final_chunks = chunker.chunk_code(parsed_chunks)
        print(f"✓ Chunked code: {len(final_chunks)} final chunks")

        for chunk in final_chunks:
            print(f"  - {chunk['chunk_type']}: {chunk['name']} ({chunk['line_count']} lines)")

        return True
    except Exception as e:
        print(f"✗ Parser/Chunker test failed: {e}")
        return False


def test_metadata_db():
    """Test metadata database."""
    print("\n=== Testing Metadata Database ===")

    try:
        # Use a test database
        test_db_path = "/tmp/test_metadata.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        db = MetadataDB(test_db_path)
        print(f"✓ Metadata database initialized")

        # Test adding repository
        repo_id = db.add_repository("/test/repo", "Test Repo")
        print(f"✓ Added repository: {repo_id}")

        # Test retrieving repository
        repo = db.get_repository(repo_id)
        print(f"✓ Retrieved repository: {repo['name']}")

        # Test adding file
        db.upsert_file(repo_id, "/test/repo/file.py", "abc123", chunk_count=5)
        print(f"✓ Added file to repository")

        # Clean up
        os.remove(test_db_path)
        print(f"✓ Cleaned up test database")

        return True
    except Exception as e:
        print(f"✗ Metadata database test failed: {e}")
        return False


def test_full_integration():
    """Test full integration (requires ChromaDB running)."""
    print("\n=== Testing Full Integration ===")

    try:
        # Initialize components
        test_db_path = "/tmp/test_integration.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        db = MetadataDB(test_db_path)
        vector_store = VectorStore(host="localhost", port=8000)
        embedder = Embedder()
        indexer = RepositoryIndexer(db, vector_store, embedder)

        print(f"✓ All components initialized")

        # This is just a structure test - actual indexing would require a real repo
        print(f"✓ Indexer ready for repository indexing")

        # Clean up
        os.remove(test_db_path)

        return True
    except Exception as e:
        print(f"✗ Full integration test failed: {e}")
        print("  Note: Make sure ChromaDB is running")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 3 Integration Tests")
    print("=" * 60)

    results = {
        "Embedder": test_embedder(),
        "Parser & Chunker": test_parser_and_chunker(),
        "Metadata Database": test_metadata_db(),
        "Vector Store": test_vector_store(),
        "Full Integration": test_full_integration()
    }

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:.<40} {status}")

    total_passed = sum(results.values())
    total_tests = len(results)

    print(f"\nTotal: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed")
        print("\nNote: Some tests require ChromaDB to be running:")
        print("  docker-compose up -d chromadb")
        return 1


if __name__ == "__main__":
    sys.exit(main())
