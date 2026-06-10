"""Ollama integration for transforming chunks into instruction-response pairs"""
import httpx
import asyncio
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from pyrove.config import OLLAMA_API_URL, OLLAMA_TIMEOUT

DEFAULT_MODEL = "llama3"


@dataclass
class InstructionPair:
    """Represents a single instruction-response pair for LoRA training"""
    instruction: str
    response: str
    source: str
    quality_score: float = 0.85  # default confidence


async def check_ollama_running(timeout: float = 5.0) -> bool:
    """
    Check if Ollama is running and accessible.
    
    Returns:
        True if Ollama is running, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OLLAMA_API_URL}/api/tags",
                timeout=timeout
            )
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, Exception):
        return False


async def list_ollama_models(timeout: float = 5.0) -> list[str]:
    """
    Get list of available Ollama models.
    
    Returns:
        List of model names, empty list if Ollama not running
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OLLAMA_API_URL}/api/tags",
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            models = [m["name"].split(":")[0] for m in data.get("models", [])]
            return list(set(models))  # deduplicate
    except Exception as e:
        logger.warning(f"Failed to list Ollama models: {e}")
        return []


async def query_ollama(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout: float = OLLAMA_TIMEOUT,
    max_retries: int = 2
) -> str:
    """
    Send prompt to local Ollama and get response.
    
    Requirements:
        - Ollama must be installed and running locally on port 11434
        - Model must be pulled: ollama pull llama3
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model name (default: llama3)
        timeout: Request timeout in seconds (default 120s for long generations)
        max_retries: Number of retry attempts on transient errors
    
    Returns:
        Generated response text
    
    Raises:
        RuntimeError: If Ollama is not running or model not found
        httpx.HTTPError: On HTTP-level errors
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{OLLAMA_API_URL}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "num_predict": 512,  # limit response length
                    },
                    timeout=timeout
                )
                
                if response.status_code == 404:
                    raise RuntimeError(
                        f"Model '{model}' not found in Ollama.\n"
                        f"Available commands:\n"
                        f"  ollama pull llama3\n"
                        f"  ollama pull mistral\n"
                        f"  ollama list (to see installed models)"
                    )
                
                response.raise_for_status()
                
                data = response.json()
                generated_text = data.get("response", "").strip()
                
                if not generated_text:
                    logger.warning(f"Empty response from Ollama on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise RuntimeError("Ollama returned empty response")
                
                return generated_text

        except httpx.ConnectError:
            error_msg = (
                "❌ Cannot connect to Ollama. Make sure:\n"
                "  1. Ollama is installed (https://ollama.ai)\n"
                "  2. ollama pull llama3\n"
                "  3. ollama serve (running)\n"
                "  4. Port 11434 is accessible"
            )
            if attempt == max_retries - 1:
                raise RuntimeError(error_msg)
            logger.warning(f"Ollama connection failed (attempt {attempt + 1}/{max_retries}), retrying...")
            await asyncio.sleep(2 ** attempt)

        except httpx.TimeoutException:
            logger.warning(f"Ollama request timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Ollama request timed out after {timeout}s")

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.status_code} {e.response.text}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise

    raise RuntimeError(f"Failed to query Ollama after {max_retries} attempts")


def _parse_response(response_text: str) -> Optional[Tuple[str, str]]:
    """
    Parse LLM response in INSTRUCTION/RESPONSE format.
    
    Handles multiple formats:
    - INSTRUCTION: ... RESPONSE: ...
    - Instruction: ... Response: ...
    - instruction: ... response: ...
    
    Returns:
        Tuple of (instruction, response) or None if parsing failed
    """
    if not response_text or not response_text.strip():
        return None

    # Try different case variations
    text_upper = response_text.upper()
    inst_idx = text_upper.find("INSTRUCTION:")
    resp_idx = text_upper.find("RESPONSE:")
    
    # Fallback to title case
    if inst_idx == -1:
        text_title = response_text
        inst_idx = text_title.find("Instruction:")
        resp_idx = text_title.find("Response:")
    
    # Fallback to lowercase
    if inst_idx == -1:
        text_lower = response_text
        inst_idx = text_lower.find("instruction:")
        resp_idx = text_lower.find("response:")
    
    if inst_idx == -1 or resp_idx == -1:
        logger.debug(f"Could not find INSTRUCTION/RESPONSE markers in: {response_text[:100]}")
        return None
    
    # Extract using original text positions (account for length of marker)
    marker_length = 12  # length of "INSTRUCTION:" or "RESPONSE:"
    
    if inst_idx < resp_idx:
        # Normal order: INSTRUCTION first, then RESPONSE
        inst_text = response_text[inst_idx + marker_length:resp_idx].strip()
        resp_text = response_text[resp_idx + marker_length:].strip()
    else:
        # Reverse order: RESPONSE first, then INSTRUCTION
        resp_text = response_text[resp_idx + marker_length:inst_idx].strip()
        inst_text = response_text[inst_idx + marker_length:].strip()
    
    # Validate both parts have meaningful content
    if len(inst_text) < 5 or len(resp_text) < 10:
        logger.debug(f"Instruction or response too short. Inst: {len(inst_text)}, Resp: {len(resp_text)}")
        return None
    
    return (inst_text, resp_text)


def _calculate_quality_score(instruction: str, response: str) -> float:
    """
    Calculate a quality score for an instruction-response pair.
    
    Factors:
    - Length (too short = low quality)
    - Question structure (starts with question words)
    - Completeness (no truncation markers)
    
    Returns:
        Score 0.0-1.0 (higher is better)
    """
    score = 0.5
    
    # Bonus for reasonable length
    if len(instruction) >= 20 and len(response) >= 50:
        score += 0.3
    elif len(instruction) >= 10 and len(response) >= 30:
        score += 0.15
    
    # Bonus for question structure
    question_words = ["what", "how", "why", "when", "where", "which", "can", "do", "is"]
    if any(instruction.lower().startswith(q) for q in question_words):
        score += 0.1
    
    # Penalty for truncation markers
    if response.endswith("...") or response.endswith("[truncated]"):
        score -= 0.2
    
    # Bonus for completeness (ends with period or natural punctuation)
    if response.rstrip().endswith((".", "?", "!", ")")):
        score += 0.1
    
    return min(1.0, max(0.0, score))


async def transform_chunk(
    chunk_text: str,
    topic: str,
    source: str,
    model: str = DEFAULT_MODEL
) -> Optional[InstructionPair]:
    """
    Transform a single chunk into an instruction-response pair.
    
    Args:
        chunk_text: The text chunk to transform
        topic: The domain/topic for context
        source: Source identifier (for tracking)
        model: Ollama model to use
    
    Returns:
        InstructionPair if successful, None if parsing/transformation failed
    """
    if not chunk_text or not chunk_text.strip():
        logger.warning("Empty chunk text provided to transform_chunk")
        return None

    prompt = f"""Based on this technical content about '{topic}', create ONE clear instruction-response pair for LoRA fine-tuning.

CONTENT:
{chunk_text}

INSTRUCTIONS:
1. Format your response EXACTLY as:
INSTRUCTION: [a clear, specific question about the content]
RESPONSE: [a detailed, accurate answer based on the content]

2. The instruction should be a question that someone would ask about this topic
3. The response should be comprehensive and directly answer the instruction
4. Do not include explanations outside the INSTRUCTION/RESPONSE format
5. Make both parts educational and suitable for training a domain expert model"""
    
    try:
        logger.debug(f"Querying {model} for chunk from {source}...")
        response_text = await query_ollama(prompt, model=model, timeout=OLLAMA_TIMEOUT)
        
        # Parse response
        parsed = _parse_response(response_text)
        
        if not parsed:
            logger.warning(f"Failed to parse Ollama response: {response_text[:100]}")
            return None
        
        instruction, response_content = parsed
        
        # Calculate quality score
        quality = _calculate_quality_score(instruction, response_content)
        
        logger.debug(f"✓ Generated pair (quality={quality:.2f}) from {source}")
        
        return InstructionPair(
            instruction=instruction,
            response=response_content,
            source=source,
            quality_score=quality
        )

    except RuntimeError as e:
        logger.error(f"Runtime error during transformation: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error transforming chunk: {e}")
        return None
