"""Text chunking module — splits content into 512-token chunks"""
import re
from typing import List
from dataclasses import dataclass


@dataclass
class Chunk:
    """Represents a 512-token chunk of text"""
    text: str
    source: str  # which README/file
    chunk_id: int


def estimate_tokens(text: str) -> int:
    """Rough estimate: ~1 token per 4 characters"""
    return len(text) // 4


def chunk_text(text: str, source: str, tokens_per_chunk: int = 512) -> List[Chunk]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Raw content to chunk
        source: Source identifier (e.g., 'repo_0', 'arxiv_001')
        tokens_per_chunk: Target chunk size in tokens (default 512)
    
    Returns:
        List of Chunk objects
    """
    chunks = []
    
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    current_chunk = ""
    chunk_count = 0
    
    for sentence in sentences:
        # Check if adding this sentence would exceed token limit
        if estimate_tokens(current_chunk + " " + sentence) <= tokens_per_chunk:
            current_chunk += " " + sentence
        else:
            # Save current chunk if it has content
            if current_chunk.strip():
                chunks.append(Chunk(
                    text=current_chunk.strip(),
                    source=source,
                    chunk_id=chunk_count
                ))
                chunk_count += 1
            # Start new chunk with current sentence
            current_chunk = sentence
    
    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(Chunk(
            text=current_chunk.strip(),
            source=source,
            chunk_id=chunk_count
        ))
    
    return chunks
