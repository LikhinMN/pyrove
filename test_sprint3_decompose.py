"""Tests for Sprint 3 - Topic Decomposition"""
import asyncio
from pyrove.decompose import (
    decompose_topic_sync,
    get_example_decomposition,
    decompose_with_fallback,
)


def test_example_decomposition():
    """Test that example decompositions are available"""
    print("\n→ Testing Example Decompositions")
    
    topics = ["kubernetes", "linux kernel", "machine learning", "docker", "python"]
    
    for topic in topics:
        decomp = get_example_decomposition(topic)
        assert decomp is not None, f"No example for {topic}"
        assert len(decomp) > 0, f"Empty decomposition for {topic}"
        print(f"  ✓ {topic:20} → {len(decomp)} subtopics")
        for i, sub in enumerate(decomp, 1):
            print(f"     {i}. {sub}")
        print()


def test_decomposition_with_fallback():
    """Test decomposition with fallback"""
    print("→ Testing Decomposition with Fallback")
    
    # This will use example since Ollama might not be running
    subtopics = asyncio.run(
        decompose_with_fallback(
            "kubernetes",
            use_examples=True
        )
    )
    
    assert isinstance(subtopics, list), "Result should be a list"
    assert len(subtopics) > 0, "Should return at least one subtopic"
    
    print(f"  ✓ Decomposed 'kubernetes' into {len(subtopics)} subtopics:")
    for i, sub in enumerate(subtopics, 1):
        print(f"     {i}. {sub}")
    print()


def test_unknown_topic_fallback():
    """Test fallback for unknown topics"""
    print("→ Testing Unknown Topic Fallback")
    
    # Unknown topic should use generic approach
    subtopics = asyncio.run(
        decompose_with_fallback(
            "cryptocurrency quantum computing",
            use_examples=False  # Force generic fallback
        )
    )
    
    assert isinstance(subtopics, list), "Result should be a list"
    assert len(subtopics) > 0, "Should generate generic subtopics"
    
    print(f"  ✓ Generated {len(subtopics)} generic subtopics:")
    for i, sub in enumerate(subtopics, 1):
        print(f"     {i}. {sub}")
    print()


def test_multiple_topics():
    """Test decomposition of various topics"""
    print("→ Testing Multiple Topics")
    
    test_topics = [
        ("machine learning", 5),
        ("docker", 4),
        ("linux kernel", 6),
    ]
    
    for topic, num in test_topics:
        subtopics = asyncio.run(
            decompose_with_fallback(topic, max_subtopics=num)
        )
        print(f"  ✓ {topic:25} → {len(subtopics):1} subtopics")
    
    print()


def main():
    """Run all decomposition tests"""
    print("\n" + "=" * 60)
    print("Sprint 3 - Topic Decomposition Tests")
    print("=" * 60)
    
    try:
        test_example_decomposition()
        test_decomposition_with_fallback()
        test_multiple_topics()
        test_unknown_topic_fallback()
        
        print("=" * 60)
        print("[✓] All decomposition tests passed!")
        print("=" * 60 + "\n")
        
        return 0
    except Exception as e:
        print(f"\n[✗] Test failed: {e}\n")
        return 1


if __name__ == "__main__":
    exit(main())
