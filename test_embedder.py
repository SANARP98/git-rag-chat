"""Test script for embedder implementation."""

import sys
import os
from pathlib import Path

# Add the rag-pipeline src to path
sys.path.insert(0, str(Path(__file__).parent / "services" / "rag-pipeline" / "src"))

from core.embedder import create_embedder, LocalEmbedder, OpenAIEmbedder

print("=" * 80)
print("Testing Embedder Implementation")
print("=" * 80)

# Test 1: Local Embedder
print("\n[Test 1] Testing Local Embedder (sentence-transformers)")
print("-" * 80)
try:
    local_embedder = create_embedder(provider="local")
    print(f"✅ Local embedder created successfully")
    print(f"   Model: {local_embedder.model_name}")
    print(f"   Dimension: {local_embedder.get_embedding_dimension()}")

    # Test embedding generation
    test_text = "def hello_world():\n    print('Hello, World!')"
    embedding = local_embedder.embed_text(test_text)
    print(f"✅ Generated embedding for test code")
    print(f"   Shape: {embedding.shape}")
    print(f"   First 5 values: {embedding[:5]}")

except Exception as e:
    print(f"❌ Local embedder failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: OpenAI Embedder
print("\n[Test 2] Testing OpenAI Embedder (text-embedding-3-large)")
print("-" * 80)

# Check if API key is set
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("⚠️  OPENAI_API_KEY not found in environment")
    print("   Skipping OpenAI embedder test")
else:
    print(f"✅ Found OPENAI_API_KEY: {api_key[:10]}...")

    try:
        openai_embedder = create_embedder(provider="openai", api_key=api_key)
        print(f"✅ OpenAI embedder created successfully")
        print(f"   Model: {openai_embedder.model_name}")
        print(f"   Dimension: {openai_embedder.get_embedding_dimension()}")

        # Test embedding generation
        test_text = "def hello_world():\n    print('Hello, World!')"
        print(f"\n   Generating embedding for test code...")
        embedding = openai_embedder.embed_text(test_text)
        print(f"✅ Generated embedding from OpenAI")
        print(f"   Shape: {embedding.shape}")
        print(f"   Expected dimension: 3072")
        print(f"   Actual dimension: {embedding.shape[0]}")
        print(f"   First 5 values: {embedding[:5]}")

        # Verify dimension
        if embedding.shape[0] == 3072:
            print("✅ Dimension matches expected (3072)")
        else:
            print(f"❌ Dimension mismatch! Expected 3072, got {embedding.shape[0]}")

    except Exception as e:
        print(f"❌ OpenAI embedder failed: {e}")
        import traceback
        traceback.print_exc()

# Test 3: Batch Processing
print("\n[Test 3] Testing Batch Processing")
print("-" * 80)
try:
    embedder = create_embedder(provider="local")

    test_texts = [
        "def add(a, b): return a + b",
        "def subtract(a, b): return a - b",
        "def multiply(a, b): return a * b"
    ]

    print(f"   Processing batch of {len(test_texts)} texts...")
    embeddings = embedder.embed_batch(test_texts, show_progress=False)
    print(f"✅ Batch processing successful")
    print(f"   Shape: {embeddings.shape}")
    print(f"   Expected: ({len(test_texts)}, {embedder.get_embedding_dimension()})")

    if embeddings.shape[0] == len(test_texts):
        print("✅ Batch size matches")
    else:
        print(f"❌ Batch size mismatch!")

except Exception as e:
    print(f"❌ Batch processing failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Factory Function
print("\n[Test 4] Testing Factory Function")
print("-" * 80)
try:
    # Test with default parameters
    embedder1 = create_embedder()
    print(f"✅ Default embedder: {type(embedder1).__name__}")

    # Test explicit local
    embedder2 = create_embedder(provider="local")
    print(f"✅ Explicit local: {type(embedder2).__name__}")

    # Test with custom model
    embedder3 = create_embedder(
        provider="local",
        model_name="sentence-transformers/all-mpnet-base-v2"
    )
    print(f"✅ Custom model: {embedder3.model_name}")

    # Test OpenAI if key available
    if api_key:
        embedder4 = create_embedder(provider="openai", api_key=api_key)
        print(f"✅ OpenAI embedder: {type(embedder4).__name__}")

    print("✅ Factory function working correctly")

except Exception as e:
    print(f"❌ Factory function failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Similarity Computation
print("\n[Test 5] Testing Similarity Computation")
print("-" * 80)
try:
    embedder = create_embedder(provider="local")

    text1 = "def add(a, b): return a + b"
    text2 = "def sum_numbers(x, y): return x + y"
    text3 = "def print_hello(): print('hello')"

    emb1 = embedder.embed_text(text1)
    emb2 = embedder.embed_text(text2)
    emb3 = embedder.embed_text(text3)

    sim_similar = embedder.compute_similarity(emb1, emb2)
    sim_different = embedder.compute_similarity(emb1, emb3)

    print(f"   Similarity (add vs sum): {sim_similar:.4f}")
    print(f"   Similarity (add vs print): {sim_different:.4f}")

    if sim_similar > sim_different:
        print("✅ Similar functions have higher similarity")
    else:
        print("⚠️  Similarity scores unexpected")

except Exception as e:
    print(f"❌ Similarity computation failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("Testing Complete!")
print("=" * 80)
