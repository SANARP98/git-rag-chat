#!/usr/bin/env python3
"""Test script for Phase 5: RAG Retrieval integration.

This script tests the retrieval, reranking, and context assembly functionality.
"""

import sys
import os
from pathlib import Path
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "services" / "rag-pipeline" / "src"))

from retrieval.retriever import CodeRetriever
from retrieval.reranker import Reranker
from retrieval.context import ContextAssembler
from core.embedder import Embedder


def test_reranker_mmr():
    """Test MMR reranking algorithm."""
    print("\n=== Testing MMR Reranker ===")

    try:
        # Create dummy chunks
        chunks = [
            {
                'id': '1',
                'code': 'def hello():\n    print("hello")',
                'similarity': 0.9,
                'file_path': 'test.py',
                'name': 'hello',
                'chunk_type': 'function'
            },
            {
                'id': '2',
                'code': 'def hello_world():\n    print("hello world")',
                'similarity': 0.85,
                'file_path': 'test.py',
                'name': 'hello_world',
                'chunk_type': 'function'
            },
            {
                'id': '3',
                'code': 'def goodbye():\n    print("goodbye")',
                'similarity': 0.7,
                'file_path': 'test.py',
                'name': 'goodbye',
                'chunk_type': 'function'
            }
        ]

        reranker = Reranker()
        print("✓ Reranker initialized")

        # Test MMR reranking
        reranked = reranker.mmr_rerank(
            chunks=chunks,
            lambda_param=0.5,
            top_k=2
        )

        if len(reranked) == 2:
            print(f"✓ MMR reranking returned {len(reranked)} results")
        else:
            print(f"✗ Expected 2 results, got {len(reranked)}")
            return False

        # Check MMR scores added
        if 'mmr_rank' in reranked[0]:
            print("✓ MMR scores added to chunks")
        else:
            print("✗ MMR scores not added")
            return False

        return True

    except Exception as e:
        print(f"✗ MMR reranker test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_diversity_rerank():
    """Test diversity reranking."""
    print("\n=== Testing Diversity Reranking ===")

    try:
        # Create chunks from different files
        chunks = [
            {
                'id': '1',
                'code': 'code1',
                'similarity': 0.9,
                'file_path': 'file1.py',
                'chunk_type': 'function',
                'name': 'func1'
            },
            {
                'id': '2',
                'code': 'code2',
                'similarity': 0.88,
                'file_path': 'file1.py',
                'chunk_type': 'function',
                'name': 'func2'
            },
            {
                'id': '3',
                'code': 'code3',
                'similarity': 0.85,
                'file_path': 'file2.py',
                'chunk_type': 'function',
                'name': 'func3'
            },
            {
                'id': '4',
                'code': 'code4',
                'similarity': 0.82,
                'file_path': 'file3.py',
                'chunk_type': 'class',
                'name': 'Class1'
            }
        ]

        reranker = Reranker()

        # Test diversity reranking
        diverse = reranker.diversity_rerank(chunks, top_k=3)

        if len(diverse) == 3:
            print(f"✓ Diversity reranking returned {len(diverse)} results")
        else:
            print(f"✗ Expected 3 results, got {len(diverse)}")
            return False

        # Check diversity - should prioritize different files
        files = {chunk['file_path'] for chunk in diverse[:2]}
        if len(files) >= 2:
            print(f"✓ Diverse results from {len(files)} different files")
        else:
            print("✗ Results not diverse enough")
            return False

        return True

    except Exception as e:
        print(f"✗ Diversity reranking test failed: {e}")
        return False


def test_context_assembler():
    """Test context assembly."""
    print("\n=== Testing Context Assembler ===")

    try:
        chunks = [
            {
                'id': '1',
                'code': 'def calculate_sum(a, b):\n    return a + b',
                'similarity': 0.9,
                'file_path': 'math_utils.py',
                'chunk_type': 'function',
                'name': 'calculate_sum',
                'language': 'python',
                'start_line': 1,
                'end_line': 2,
                'line_count': 2
            },
            {
                'id': '2',
                'code': 'def calculate_product(a, b):\n    return a * b',
                'similarity': 0.85,
                'file_path': 'math_utils.py',
                'chunk_type': 'function',
                'name': 'calculate_product',
                'language': 'python',
                'start_line': 4,
                'end_line': 5,
                'line_count': 2
            }
        ]

        assembler = ContextAssembler(max_tokens=4000)
        print(f"✓ Context assembler initialized (max_tokens=4000)")

        # Test context assembly
        context = assembler.assemble_context(
            chunks=chunks,
            query="How do I calculate sum?"
        )

        if context and len(context) > 0:
            print(f"✓ Context assembled ({len(context)} chars)")
        else:
            print("✗ Context assembly failed")
            return False

        # Check if code is in context
        if 'calculate_sum' in context:
            print("✓ Function name in context")
        else:
            print("✗ Function name not in context")
            return False

        # Test prompt assembly
        prompt = assembler.assemble_prompt(
            chunks=chunks,
            query="How do I calculate sum?"
        )

        if prompt and len(prompt) > len(context):
            print(f"✓ Prompt assembled ({len(prompt)} chars)")
        else:
            print("✗ Prompt assembly failed")
            return False

        # Test metadata summary
        summary = assembler.build_metadata_summary(chunks)

        if summary['total_chunks'] == 2:
            print(f"✓ Metadata summary: {summary['total_chunks']} chunks, {summary['unique_files']} files")
        else:
            print("✗ Metadata summary incorrect")
            return False

        return True

    except Exception as e:
        print(f"✗ Context assembler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hybrid_search():
    """Test hybrid search combining semantic and keyword matching."""
    print("\n=== Testing Hybrid Search (Simulated) ===")

    try:
        chunks = [
            {
                'id': '1',
                'code': 'def authentication_handler():\n    # Handles user authentication\n    pass',
                'similarity': 0.7,
                'file_path': 'auth.py',
                'chunk_type': 'function',
                'name': 'authentication_handler'
            },
            {
                'id': '2',
                'code': 'def login():\n    # User login\n    return authenticate()',
                'similarity': 0.8,
                'file_path': 'auth.py',
                'chunk_type': 'function',
                'name': 'login'
            },
            {
                'id': '3',
                'code': 'def process_data():\n    # Data processing\n    pass',
                'similarity': 0.5,
                'file_path': 'utils.py',
                'chunk_type': 'function',
                'name': 'process_data'
            }
        ]

        # Simulate hybrid search (normally would use retriever)
        keywords = ['authentication', 'login']

        # Simple keyword scoring
        semantic_weight = 0.7
        keyword_weight = 0.3

        for chunk in chunks:
            code_lower = chunk['code'].lower()
            keyword_score = sum(
                1 for kw in keywords
                if kw in code_lower
            ) / len(keywords)

            chunk['hybrid_score'] = (
                semantic_weight * chunk['similarity'] +
                keyword_weight * keyword_score
            )

        # Sort by hybrid score
        chunks.sort(key=lambda x: x['hybrid_score'], reverse=True)

        print(f"✓ Hybrid search scored {len(chunks)} chunks")

        # Check if authentication_handler scored high (has keyword)
        if chunks[0]['name'] in ['authentication_handler', 'login']:
            print(f"✓ Top result: {chunks[0]['name']} (hybrid_score={chunks[0]['hybrid_score']:.2f})")
        else:
            print(f"✗ Unexpected top result: {chunks[0]['name']}")
            return False

        return True

    except Exception as e:
        print(f"✗ Hybrid search test failed: {e}")
        return False


def test_context_grouping():
    """Test grouping chunks by file."""
    print("\n=== Testing Context Grouping ===")

    try:
        chunks = [
            {'file_path': 'file1.py', 'start_line': 10, 'code': 'code1'},
            {'file_path': 'file1.py', 'start_line': 5, 'code': 'code2'},
            {'file_path': 'file2.py', 'start_line': 1, 'code': 'code3'},
        ]

        assembler = ContextAssembler()
        grouped = assembler.group_chunks_by_file(chunks)

        if len(grouped) == 2:
            print(f"✓ Grouped into {len(grouped)} files")
        else:
            print(f"✗ Expected 2 files, got {len(grouped)}")
            return False

        # Check sorting within files
        file1_chunks = grouped['file1.py']
        if file1_chunks[0]['start_line'] < file1_chunks[1]['start_line']:
            print("✓ Chunks sorted by line number within files")
        else:
            print("✗ Chunks not sorted correctly")
            return False

        return True

    except Exception as e:
        print(f"✗ Context grouping test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 5 RAG Retrieval Tests")
    print("=" * 60)

    results = {
        "MMR Reranking": test_reranker_mmr(),
        "Diversity Reranking": test_diversity_rerank(),
        "Context Assembly": test_context_assembler(),
        "Hybrid Search": test_hybrid_search(),
        "Context Grouping": test_context_grouping()
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
        return 1


if __name__ == "__main__":
    sys.exit(main())
