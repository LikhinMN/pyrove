"""Topic decomposition module for breaking complex topics into subtopics"""
import httpx
import logging
import asyncio
from typing import List, Optional

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"


async def decompose_topic(
    topic: str,
    model: str = DEFAULT_MODEL,
    max_subtopics: int = 7,
) -> List[str]:
    """
    Decompose a complex topic into subtopics using LLM.
    
    Examples:
        "kubernetes" → ["architecture", "networking", "storage", "security", "scaling", "monitoring", "deployment"]
        "linux kernel" → ["process scheduling", "memory management", "filesystem", "networking", "interrupts", "device drivers", "security"]
        "machine learning" → ["supervised learning", "unsupervised learning", "neural networks", "optimization", "data preprocessing", "evaluation metrics", "deployment"]
    
    Args:
        topic: The main topic to decompose
        model: Ollama model to use
        max_subtopics: Maximum number of subtopics to generate
    
    Returns:
        List of subtopic strings
    """
    if not topic or not topic.strip():
        logger.warning("Empty topic provided to decompose_topic")
        return []
    
    prompt = f"""Break down the topic '{topic}' into {max_subtopics} key subtopics that cover all important aspects.

Return ONLY the subtopics as a simple comma-separated list, nothing else.
Example format: subtopic1, subtopic2, subtopic3

Topic: {topic}
Subtopics:"""

    try:
        logger.info(f"🧠 Decomposing topic: '{topic}'")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get("response", "").strip()
            
            if not response_text:
                logger.warning(f"Empty response from Ollama for topic: {topic}")
                return []
            
            # Parse comma-separated list
            subtopics = [
                s.strip()
                for s in response_text.split(",")
                if s.strip()
            ]
            
            # Clean up subtopics (remove numbering, etc.)
            cleaned = []
            for sub in subtopics:
                # Remove leading digits and periods (e.g., "1. architecture" → "architecture")
                cleaned_sub = sub.lstrip("0123456789. ").strip()
                if cleaned_sub and len(cleaned_sub) > 2:
                    cleaned.append(cleaned_sub.lower())
            
            # Remove duplicates while preserving order
            seen = set()
            unique_subtopics = []
            for sub in cleaned:
                if sub not in seen:
                    seen.add(sub)
                    unique_subtopics.append(sub)
            
            # Limit to requested number
            unique_subtopics = unique_subtopics[:max_subtopics]
            
            logger.info(f"✓ Decomposed '{topic}' into {len(unique_subtopics)} subtopics")
            return unique_subtopics
    
    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama. Make sure it's running on localhost:11434")
        return []
    except httpx.TimeoutException:
        logger.error(f"Timeout decomposing topic '{topic}'")
        return []
    except Exception as e:
        logger.error(f"Error decomposing topic '{topic}': {e}")
        return []


def decompose_topic_sync(
    topic: str,
    model: str = DEFAULT_MODEL,
    max_subtopics: int = 7,
) -> List[str]:
    """
    Synchronous wrapper for decompose_topic.
    
    Args:
        topic: The main topic to decompose
        model: Ollama model to use
        max_subtopics: Maximum number of subtopics to generate
    
    Returns:
        List of subtopic strings
    """
    try:
        return asyncio.run(decompose_topic(topic, model, max_subtopics))
    except RuntimeError:
        # Handle case where event loop already exists
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                decompose_topic(topic, model, max_subtopics),
                loop
            ).result()
        raise


# Example decomposition map for offline mode
EXAMPLE_DECOMPOSITIONS = {
    "kubernetes": [
        "architecture and components",
        "networking and services",
        "storage and volumes",
        "security and rbac",
        "scaling and load balancing",
        "monitoring and logging",
        "deployment patterns",
    ],
    "linux kernel": [
        "process scheduling",
        "memory management",
        "filesystem",
        "networking stack",
        "interrupt handling",
        "device drivers",
        "security and permissions",
    ],
    "machine learning": [
        "supervised learning",
        "unsupervised learning",
        "neural networks",
        "optimization algorithms",
        "data preprocessing",
        "evaluation metrics",
        "deployment and inference",
    ],
    "docker": [
        "containers and images",
        "networking",
        "volumes and storage",
        "composition and orchestration",
        "registry and distribution",
        "security",
        "performance optimization",
    ],
    "python": [
        "core language features",
        "object-oriented programming",
        "functional programming",
        "async programming",
        "error handling and testing",
        "data structures",
        "performance optimization",
    ],
}


def get_example_decomposition(topic: str) -> Optional[List[str]]:
    """
    Get example decomposition for known topics (for testing/demo).
    
    Args:
        topic: Topic to look up
    
    Returns:
        List of subtopics or None if not found
    """
    topic_lower = topic.lower().strip()
    return EXAMPLE_DECOMPOSITIONS.get(topic_lower)


async def decompose_with_fallback(
    topic: str,
    model: str = DEFAULT_MODEL,
    max_subtopics: int = 7,
    use_examples: bool = True,
) -> List[str]:
    """
    Decompose topic with fallback to examples if Ollama unavailable.
    
    Args:
        topic: Topic to decompose
        model: Ollama model to use
        max_subtopics: Maximum number of subtopics
        use_examples: Whether to use examples as fallback
    
    Returns:
        List of subtopics
    """
    # Try LLM decomposition first
    subtopics = await decompose_topic(topic, model, max_subtopics)
    
    if subtopics:
        return subtopics
    
    # Fallback to examples
    if use_examples:
        example = get_example_decomposition(topic)
        if example:
            logger.info(f"Using example decomposition for '{topic}'")
            return example[:max_subtopics]
    
    # Final fallback: generic approach
    logger.warning(f"No decomposition available for '{topic}', using generic approach")
    generic_subtopics = [
        f"{topic} basics",
        f"{topic} advanced topics",
        f"{topic} best practices",
        f"{topic} performance",
        f"{topic} troubleshooting",
    ]
    return generic_subtopics[:max_subtopics]
