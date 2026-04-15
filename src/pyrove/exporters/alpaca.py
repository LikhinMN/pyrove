"""Exporter for Alpaca JSONL format"""
import json
from pathlib import Path
from typing import List


async def export_alpaca(pairs: List, output_path: Path = None) -> Path:
    """
    Export pairs to Alpaca JSONL format.
    
    Format example:
    {
        "instruction": "What is the Linux kernel scheduler?",
        "input": "",
        "output": "The Linux kernel scheduler manages CPU time allocation..."
    }
    
    Args:
        pairs: List of InstructionPair objects
        output_path: Where to save the JSONL file (default: ~/.pyrove/output.jsonl)
    
    Returns:
        Path to the created file
    """
    if output_path is None:
        output_path = Path.home() / ".pyrove" / "output.jsonl"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for pair in pairs:
            alpaca_entry = {
                "instruction": pair.instruction,
                "input": "",
                "output": pair.response
            }
            f.write(json.dumps(alpaca_entry, ensure_ascii=False) + "\n")
    
    print(f"✓ Exported {len(pairs)} pairs to {output_path}")
    return output_path
