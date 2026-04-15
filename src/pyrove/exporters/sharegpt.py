"""ShareGPT format exporter for instruction-response pairs"""
import json
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


async def export_sharegpt(
    pairs: List,
    output_path: Path = None
) -> Path:
    """
    Export pairs to ShareGPT JSON format.
    
    ShareGPT format structure:
    {
        "conversations": [
            {
                "from": "human",
                "value": "instruction"
            },
            {
                "from": "gpt",
                "value": "response"
            }
        ]
    }
    
    Args:
        pairs: List of InstructionPair objects
        output_path: Where to save the JSON file (default: ~/.pyrove/sharegpt_output.json)
    
    Returns:
        Path to the created file
    """
    if output_path is None:
        output_path = Path.home() / ".pyrove" / "sharegpt_output.json"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    sharegpt_data = []
    
    for pair in pairs:
        conversation = [
            {
                "from": "human",
                "value": pair.instruction
            },
            {
                "from": "gpt",
                "value": pair.response
            }
        ]
        
        sharegpt_data.append({
            "conversations": conversation,
            "source": getattr(pair, 'source', 'pyrove'),
            "quality": getattr(pair, 'quality_score', 0.85)
        })
    
    # Write JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sharegpt_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ Exported {len(sharegpt_data)} conversations to ShareGPT format")
    print(f"✓ Exported {len(sharegpt_data)} conversations to {output_path}")
    
    return output_path


async def export_format(
    pairs: List,
    format: str = "alpaca",
    output_path: Path = None
) -> Path:
    """
    Export pairs in specified format.
    
    Args:
        pairs: List of InstructionPair objects
        format: Export format ('alpaca' or 'sharegpt')
        output_path: Output file path
    
    Returns:
        Path to exported file
    
    Raises:
        ValueError: If unsupported format
    """
    if format.lower() == "alpaca":
        from pyrove.exporters.alpaca import export_alpaca
        return await export_alpaca(pairs, output_path)
    
    elif format.lower() == "sharegpt":
        return await export_sharegpt(pairs, output_path)
    
    else:
        raise ValueError(f"Unsupported export format: {format}. Use 'alpaca' or 'sharegpt'")
