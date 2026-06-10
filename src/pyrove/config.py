"""Configuration settings for Pyrove."""
import os
from typing import Optional

# Ollama API settings
OLLAMA_API_URL: str = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))

# GitHub API settings
GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")
