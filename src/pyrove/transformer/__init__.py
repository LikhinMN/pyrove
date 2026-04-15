"""Transformer module — generates instruction-response pairs using Ollama"""
from .ollama import InstructionPair, query_ollama, transform_chunk

__all__ = ["InstructionPair", "query_ollama", "transform_chunk"]
