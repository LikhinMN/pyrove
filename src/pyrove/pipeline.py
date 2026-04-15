"""Main pipeline orchestration — ties together all components"""
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import logging
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from pyrove.scrapers.github import search_github, scrape_all as scrape_github_all
from pyrove.scrapers.web import search_web_articles, extract_multiple_articles
from pyrove.scrapers.arxiv import fetch_arxiv_papers_async
from pyrove.chunking.chunker import chunk_text
from pyrove.transformer.ollama import transform_chunk, check_ollama_running, list_ollama_models
from pyrove.storage.db import Database
from pyrove.exporters.alpaca import export_alpaca
from pyrove.exporters.sharegpt import export_sharegpt
from pyrove.validator import validate_and_filter_dataset, print_validation_report

console = Console()
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def run_pipeline(
    topic: str,
    target_size: int = 100,
    model: str = "llama3",
    output_format: str = "alpaca",
    sources: List[str] = None
) -> Path:
    """
    Full pipeline with multi-source support.
    
    Flow:
    1. Search multiple sources (GitHub, Web, arXiv)
    2. Scrape and extract content
    3. Chunk content into 512-token pieces
    4. Transform chunks to instruction-response pairs using Ollama
    5. Validate and filter by quality
    6. Export to JSONL/JSON format
    
    Args:
        topic: Technical topic to create dataset for
        target_size: Target number of instruction-response pairs
        model: Ollama model to use
        output_format: Export format (alpaca or sharegpt)
        sources: List of sources to scrape (github, web, arxiv)
    
    Returns:
        Path to exported dataset
    
    Raises:
        RuntimeError: If Ollama is not running or no content found
    """
    if sources is None:
        sources = ["github"]  # Default to GitHub only
    
    run_id = str(uuid.uuid4())[:8]
    db = Database()
    
    try:
        # Initialize database
        await db.init()
        
        # Insert run record
        await db.insert_run(
            run_id=run_id,
            topic=topic,
            target_size=target_size,
        )
        logger.info(f"Started run {run_id} for topic: {topic} with sources: {sources}")
        
        all_contents = []
        
        # Step 1: GitHub Source
        if "github" in sources:
            console.print(f"\n[bold cyan]→ Step 1A: Searching GitHub for '{topic}'...[/bold cyan]")
            search_result = search_github(topic)
            
            if not search_result.success:
                console.print(f"[yellow]⚠️  GitHub search failed: {search_result.error}[/yellow]")
            elif search_result.urls:
                console.print(f"[green]✓ Found {len(search_result.urls)} repositories[/green]")
                
                console.print(f"[cyan]  Scraping README files...[/cyan]")
                with Progress() as progress:
                    task = progress.add_task("[cyan]  Scraping...", total=len(search_result.urls))
                    for url in search_result.urls:
                        content = scrape_github_all([url])
                        if content:
                            all_contents.extend(content)
                        progress.update(task, advance=1)
                
                console.print(f"[green]  ✓ Scraped {len(search_result.urls)} GitHub repositories[/green]")
        
        # Step 1B: Web Source
        if "web" in sources:
            console.print(f"\n[bold cyan]→ Step 1B: Searching web for '{topic}'...[/bold cyan]")
            web_urls = await search_web_articles(topic, num_results=5)
            
            if web_urls:
                console.print(f"[green]✓ Found {len(web_urls)} web articles[/green]")
                
                with Progress() as progress:
                    task = progress.add_task("[cyan]  Extracting...", total=len(web_urls))
                    web_contents = extract_multiple_articles(web_urls)
                    all_contents.extend(web_contents)
                    for _ in web_urls:
                        progress.update(task, advance=1)
                
                console.print(f"[green]  ✓ Extracted {len(web_contents)} articles[/green]")
        
        # Step 1C: arXiv Source
        if "arxiv" in sources:
            console.print(f"\n[bold cyan]→ Step 1C: Searching arXiv for '{topic}'...[/bold cyan]")
            arxiv_contents = await fetch_arxiv_papers_async(topic, max_results=10)
            
            if arxiv_contents:
                all_contents.extend(arxiv_contents)
                console.print(f"[green]✓ Found and extracted {len(arxiv_contents)} arXiv papers[/green]")
        
        # Validate we have content
        if not all_contents:
            console.print("[red]✗ No content could be scraped from any source[/red]")
            raise RuntimeError("Failed to scrape content from any source")
        
        console.print(f"\n[green]✓ Total content collected: {len(all_contents)} items[/green]")
        
        # Step 2: Chunk content
        console.print(f"\n[bold cyan]→ Step 2: Chunking content into 512-token pieces...[/bold cyan]")
        all_chunks = []
        for i, content in enumerate(all_contents):
            chunks = chunk_text(content, source=f"source_{i}")
            all_chunks.extend(chunks)
        
        console.print(f"[green]✓ Generated {len(all_chunks)} chunks[/green]")
        
        # Step 2.5: Check Ollama is running before transformation
        console.print(f"\n[bold cyan]→ Step 2.5: Checking Ollama availability...[/bold cyan]")
        ollama_ready = await check_ollama_running()
        if not ollama_ready:
            console.print("[red]✗ Ollama is not running[/red]")
            console.print("[yellow]To start Ollama:[/yellow]")
            console.print("  ollama serve")
            raise RuntimeError("Ollama is not accessible. Please start it with 'ollama serve'")
        
        available_models = await list_ollama_models()
        if not available_models:
            console.print("[yellow]⚠️  Could not verify available Ollama models[/yellow]")
        elif model not in available_models:
            console.print(f"[yellow]⚠️  Model '{model}' not confirmed in available models: {', '.join(available_models)}[/yellow]")
            console.print(f"[dim]Attempting to use {model} anyway...[/dim]")
        else:
            console.print(f"[green]✓ Ollama ready with model: {model}[/green]")
        
        # Step 3: Transform to instruction-response pairs
        console.print(f"\n[bold cyan]→ Step 3: Transforming to instruction-response pairs...[/bold cyan]")
        console.print(f"[dim]Using model: {model} | Target: {target_size} pairs[/dim]")
        
        pairs = []
        failed_chunks = 0
        total_quality = 0.0
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Transforming...", total=target_size)
            
            for i, chunk in enumerate(all_chunks):
                if len(pairs) >= target_size:
                    console.print(f"[green]✓ Reached target of {target_size} pairs[/green]")
                    break
                
                try:
                    pair = await transform_chunk(
                        chunk.text,
                        topic=topic,
                        source=chunk.source,
                        model=model
                    )
                    if pair:
                        pairs.append(pair)
                        total_quality += pair.quality_score
                        
                        # Save pair to database
                        pair_id = str(uuid.uuid4())[:12]
                        await db.insert_pair(
                            pair_id=pair_id,
                            run_id=run_id,
                            instruction=pair.instruction,
                            response=pair.response,
                            quality_score=pair.quality_score,
                        )
                        
                        progress.update(task, advance=1, description=f"[cyan]Quality: {pair.quality_score:.2f}[/cyan]")
                    else:
                        failed_chunks += 1
                        progress.update(task)
                except RuntimeError as e:
                    console.print(f"\n[red]{e}[/red]")
                    await db.update_run(run_id, status="failed")
                    raise
                except Exception as e:
                    console.print(f"\n[yellow]⚠️  Error on chunk {i}: {e}[/yellow]")
                    failed_chunks += 1
                    continue
        
        avg_quality = total_quality / len(pairs) if pairs else 0.0
        console.print(f"[green]✓ Generated {len(pairs)} instruction-response pairs[/green]")
        console.print(f"[dim]Average quality: {avg_quality:.2f} | Failed chunks: {failed_chunks}[/dim]")
        
        # Step 4: Validate and filter dataset
        console.print(f"\n[bold cyan]→ Step 4: Validating and filtering dataset...[/bold cyan]")
        validated_pairs, validation_stats = validate_and_filter_dataset(pairs, min_quality=0.4)
        
        console.print(f"[green]✓ Validation complete[/green]")
        print_validation_report(validation_stats)
        
        if not validated_pairs:
            console.print("[red]✗ No valid pairs after validation[/red]")
            raise RuntimeError("All pairs filtered out during validation")
        
        # Step 5: Export
        console.print(f"\n[bold cyan]→ Step 5: Exporting to {output_format.upper()} format...[/bold cyan]")
        
        if output_format.lower() == "alpaca":
            output_path = await export_alpaca(validated_pairs)
        elif output_format.lower() == "sharegpt":
            output_path = await export_sharegpt(validated_pairs)
        else:
            raise ValueError(f"Unsupported format: {output_format}")
        
        # Update run status to completed
        await db.update_run(
            run_id=run_id,
            status="completed",
            pairs_collected=len(validated_pairs),
            quality_score=avg_quality,
            completed_at=datetime.now().isoformat(),
        )
        
        logger.info(f"Run {run_id} completed: {len(validated_pairs)} valid pairs generated")
        return output_path
        
    except Exception as e:
        console.print(f"\n[red]✗ Pipeline failed: {e}[/red]")
        logger.error(f"Run {run_id} failed: {e}")
        try:
            await db.update_run(run_id, status="failed")
        except:
            pass
        raise


async def main_async(
    topic: str,
    size: int = 100,
    model: str = "llama3",
    format: str = "alpaca",
    sources: List[str] = None
):
    """Entry point for async pipeline"""
    try:
        if sources is None:
            sources = ["github"]
        
        output_path = await run_pipeline(
            topic=topic,
            target_size=size,
            model=model,
            output_format=format,
            sources=sources
        )
        
        # Display final summary
        console.print(f"\n[bold green]✓ Dataset complete![/bold green]")
        table = Table(title="Pipeline Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Topic", topic)
        table.add_row("Dataset Size", str(size))
        table.add_row("Model", model)
        table.add_row("Format", format.upper())
        table.add_row("Output File", str(output_path))
        console.print(table)
        
        # File size info
        if output_path.exists():
            file_size = output_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            console.print(f"[dim]File size: {file_size_mb:.2f} MB[/dim]")
        
        console.print(f"\n[bold]Next steps:[/bold]")
        console.print(f"  1. Copy dataset to your project: cp {output_path} ./data/")
        console.print(f"  2. Fine-tune with LoRA: python finetune.py --data {output_path}")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Pipeline interrupted by user[/yellow]")
        logger.warning("Pipeline interrupted by user")
    except Exception as e:
        console.print(f"\n[red]✗ Fatal error: {e}[/red]")
        logger.error(f"Pipeline fatal error: {e}")
        raise


def run_sync(
    topic: str,
    size: int = 100,
    model: str = "llama3",
    format: str = "alpaca",
    sources: List[str] = None
):
    """Synchronous wrapper for CLI"""
    asyncio.run(main_async(topic, size, model, format, sources))


# ===== Utility Functions for Run History =====

async def get_run_history(limit: int = 50) -> Optional[List[dict]]:
    """
    Retrieve run history from database.
    
    Args:
        limit: Maximum number of runs to retrieve
    
    Returns:
        List of run records or None if DB unavailable
    """
    try:
        db = Database()
        await db.init()
        runs = await db.fetch_all_runs(limit=limit)
        return runs
    except Exception as e:
        logger.error(f"Failed to retrieve run history: {e}")
        return None


async def get_run_details(run_id: str) -> Optional[dict]:
    """
    Get details for a specific run including all generated pairs.
    
    Args:
        run_id: Run ID to retrieve
    
    Returns:
        Dict with run metadata and pairs, or None if not found
    """
    try:
        db = Database()
        await db.init()
        run = await db.fetch_run(run_id)
        if not run:
            return None
        
        pairs = await db.fetch_pairs_by_run(run_id)
        run["pairs"] = pairs
        run["pair_count"] = len(pairs)
        
        return run
    except Exception as e:
        logger.error(f"Failed to retrieve run details: {e}")
        return None


def display_run_history():
    """Display run history in a formatted table"""
    runs = asyncio.run(get_run_history())
    
    if not runs:
        console.print("[yellow]No runs found in history[/yellow]")
        return
    
    table = Table(title="Run History")
    table.add_column("Run ID", style="cyan")
    table.add_column("Topic", style="magenta")
    table.add_column("Pairs", style="green")
    table.add_column("Quality", style="yellow")
    table.add_column("Status", style="blue")
    table.add_column("Created", style="dim")
    
    for run in runs[:50]:
        status_color = "green" if run["status"] == "completed" else "red" if run["status"] == "failed" else "yellow"
        table.add_row(
            run["id"],
            run["topic"],
            str(run["pairs_collected"]),
            f"{run['quality_score']:.2f}",
            f"[{status_color}]{run['status']}[/{status_color}]",
            str(run["created_at"])[:19] if run["created_at"] else "N/A"
        )
    
    console.print(table)


def display_run_details(run_id: str):
    """Display details for a specific run"""
    run = asyncio.run(get_run_details(run_id))
    
    if not run:
        console.print(f"[red]Run {run_id} not found[/red]")
        return
    
    # Run metadata
    table = Table(title=f"Run Details: {run_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    
    table.add_row("Topic", run["topic"])
    table.add_row("Status", f"[green]{run['status']}[/green]" if run["status"] == "completed" else f"[red]{run['status']}[/red]")
    table.add_row("Pairs Generated", str(run["pairs_collected"]))
    table.add_row("Target Size", str(run["target_size"]))
    table.add_row("Quality Score", f"{run['quality_score']:.2f}")
    table.add_row("Created", str(run["created_at"])[:19] if run["created_at"] else "N/A")
    table.add_row("Completed", str(run["completed_at"])[:19] if run["completed_at"] else "N/A")
    
    console.print(table)
    
    # Show sample pairs
    if run.get("pairs"):
        pairs_table = Table(title="Sample Instruction-Response Pairs (first 5)")
        pairs_table.add_column("Instruction", style="cyan", width=40)
        pairs_table.add_column("Response", style="green", width=50)
        pairs_table.add_column("Quality", style="yellow")
        
        for pair in run["pairs"][:5]:
            pairs_table.add_row(
                pair["instruction"][:40],
                pair["response"][:50],
                f"{pair['quality_score']:.2f}"
            )
        
        console.print(pairs_table)
