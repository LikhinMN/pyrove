"""Quality validator for instruction-response pairs"""
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation check"""
    is_valid: bool
    score: float  # 0.0-1.0
    issues: List[str]


def validate_instruction_response_pair(instruction: str, response: str) -> ValidationResult:
    """
    Validate a single instruction-response pair.
    
    Checks:
    - Minimum length requirements
    - No truncation markers
    - Proper formatting
    - Content quality indicators
    
    Args:
        instruction: The question/instruction
        response: The answer/response
    
    Returns:
        ValidationResult with validity flag and quality score
    """
    issues = []
    score = 1.0
    
    # Check instruction
    if not instruction or not instruction.strip():
        issues.append("Empty instruction")
        score = 0.0
    elif len(instruction) < 5:
        issues.append(f"Instruction too short ({len(instruction)} chars, min 5)")
        score -= 0.3
    elif len(instruction) > 500:
        issues.append(f"Instruction too long ({len(instruction)} chars, max 500)")
        score -= 0.2
    
    # Check response
    if not response or not response.strip():
        issues.append("Empty response")
        score = 0.0
    elif len(response) < 20:
        issues.append(f"Response too short ({len(response)} chars, min 20)")
        score -= 0.4
    elif len(response) > 5000:
        issues.append(f"Response too long ({len(response)} chars, max 5000)")
        score -= 0.1
    
    # Check for truncation markers
    truncation_markers = ["...", "[truncated]", "etc.", "& so on", "and so on"]
    for marker in truncation_markers:
        if response.endswith(marker):
            issues.append(f"Response ends with truncation marker: '{marker}'")
            score -= 0.3
            break
    
    # Check for incomplete sentences
    if response.rstrip() and not response.rstrip().endswith((".", "?", "!", ")", ":", "\"", "'")):
        issues.append("Response doesn't end with proper punctuation")
        score -= 0.15
    
    # Check for repetition (simple check)
    lines = response.split("\n")
    if len(lines) > 1:
        if any(line == lines[0] for line in lines[1:]):
            issues.append("Response contains repeated lines")
            score -= 0.2
    
    # Check for placeholder text
    placeholders = ["[example]", "[citation]", "[source]", "TODO", "FIXME", "<placeholder>"]
    for placeholder in placeholders:
        if placeholder.lower() in response.lower():
            issues.append(f"Response contains placeholder: {placeholder}")
            score -= 0.25
            break
    
    # Bonus points for good quality indicators
    if instruction.rstrip().endswith("?"):
        score += 0.05  # Good question format
    
    if len(response) >= 50 and len(response) <= 500:
        score += 0.1  # Good length
    
    if any(word in response.lower() for word in ["because", "therefore", "as a result"]):
        score += 0.05  # Good explanatory content
    
    # Clamp score
    score = max(0.0, min(1.0, score))
    
    is_valid = len(issues) == 0 and score >= 0.5
    
    return ValidationResult(
        is_valid=is_valid,
        score=score,
        issues=issues
    )


def filter_pairs_by_quality(
    pairs: List,
    min_quality: float = 0.5
) -> tuple[List, List]:
    """
    Filter pairs by quality threshold.
    
    Args:
        pairs: List of InstructionPair objects
        min_quality: Minimum quality score (0.0-1.0)
    
    Returns:
        Tuple of (valid_pairs, filtered_pairs)
    """
    valid_pairs = []
    filtered_pairs = []
    
    for pair in pairs:
        result = validate_instruction_response_pair(pair.instruction, pair.response)
        
        # Use the pair's quality_score if available, otherwise use validation result
        quality = getattr(pair, 'quality_score', result.score)
        
        if quality >= min_quality:
            valid_pairs.append(pair)
        else:
            filtered_pairs.append({
                "pair": pair,
                "quality": quality,
                "issues": result.issues
            })
    
    logger.info(f"Quality filter: {len(valid_pairs)} valid, {len(filtered_pairs)} filtered")
    return valid_pairs, filtered_pairs


def remove_duplicate_pairs(pairs: List) -> tuple[List, int]:
    """
    Remove duplicate instruction-response pairs.
    
    Uses instruction similarity (exact match on normalized text).
    
    Args:
        pairs: List of InstructionPair objects
    
    Returns:
        Tuple of (unique_pairs, num_duplicates_removed)
    """
    seen_instructions = set()
    unique_pairs = []
    duplicates_removed = 0
    
    for pair in pairs:
        # Normalize instruction for comparison
        normalized = pair.instruction.lower().strip()
        
        if normalized not in seen_instructions:
            seen_instructions.add(normalized)
            unique_pairs.append(pair)
        else:
            duplicates_removed += 1
            logger.debug(f"Duplicate instruction removed: {pair.instruction[:50]}")
    
    if duplicates_removed > 0:
        logger.info(f"Removed {duplicates_removed} duplicate pairs")
    
    return unique_pairs, duplicates_removed


def validate_and_filter_dataset(
    pairs: List,
    min_quality: float = 0.5,
    remove_duplicates: bool = True
) -> tuple[List, dict]:
    """
    Complete validation pipeline for a dataset.
    
    Args:
        pairs: List of InstructionPair objects
        min_quality: Minimum quality threshold
        remove_duplicates: Whether to remove duplicates
    
    Returns:
        Tuple of (validated_pairs, statistics_dict)
    """
    stats = {
        "total_input": len(pairs),
        "duplicates_removed": 0,
        "low_quality_filtered": 0,
        "validation_issues": {},
    }
    
    # Step 1: Remove duplicates
    if remove_duplicates:
        pairs, stats["duplicates_removed"] = remove_duplicate_pairs(pairs)
    
    # Step 2: Filter by quality
    valid_pairs, filtered = filter_pairs_by_quality(pairs, min_quality)
    stats["low_quality_filtered"] = len(filtered)
    
    # Collect validation issues
    for item in filtered:
        issues_str = "; ".join(item["issues"])
        if issues_str not in stats["validation_issues"]:
            stats["validation_issues"][issues_str] = 0
        stats["validation_issues"][issues_str] += 1
    
    stats["total_valid"] = len(valid_pairs)
    stats["retention_rate"] = stats["total_valid"] / max(stats["total_input"], 1) * 100
    
    logger.info(f"Dataset validation complete: {stats['total_valid']}/{stats['total_input']} pairs valid ({stats['retention_rate']:.1f}%)")
    
    return valid_pairs, stats


def print_validation_report(stats: dict):
    """Print a formatted validation report"""
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    table = Table(title="Dataset Validation Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Input Pairs", str(stats["total_input"]))
    table.add_row("Duplicates Removed", str(stats["duplicates_removed"]))
    table.add_row("Low Quality Filtered", str(stats["low_quality_filtered"]))
    table.add_row("Valid Pairs", str(stats["total_valid"]))
    table.add_row("Retention Rate", f"{stats['retention_rate']:.1f}%")
    
    console.print(table)
    
    if stats["validation_issues"]:
        console.print("\n[bold]Validation Issues Breakdown:[/bold]")
        for issue, count in sorted(stats["validation_issues"].items(), key=lambda x: -x[1])[:5]:
            console.print(f"  • {issue}: {count} pairs")
