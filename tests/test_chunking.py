import pytest
from pyrove.chunking.chunker import chunk_text, estimate_tokens

def test_estimate_tokens():
    text = "Hello world!"
    # 12 chars // 4 = 3 tokens
    assert estimate_tokens(text) == 3

def test_chunk_text_basic():
    text = "This is a sentence. This is another sentence! And a third one?"
    # Total chars: ~62 -> ~15 tokens.
    chunks = chunk_text(text, source="test", tokens_per_chunk=10)
    # Should split into multiple chunks because 15 > 10.
    assert len(chunks) >= 2
    assert chunks[0].source == "test"
    assert chunks[0].chunk_id == 0
    assert chunks[1].chunk_id == 1

def test_chunk_text_small():
    text = "Short text."
    chunks = chunk_text(text, source="test", tokens_per_chunk=10)
    assert len(chunks) == 1
    assert chunks[0].text == "Short text."
