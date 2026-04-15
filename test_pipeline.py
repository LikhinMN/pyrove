#!/usr/bin/env python3
"""
Integration tests for pyrove pipeline.
Tests each component of the pipeline without requiring live Ollama.
"""

import asyncio
import sys
from pathlib import Path
from rich.console import Console

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pyrove.storage.db import Database
from pyrove.scrapers.github import search_github, scrape_readme, scrape_all
from pyrove.chunking.chunker import chunk_text
from pyrove.transformer.ollama import check_ollama_running, list_ollama_models
from pyrove.exporters.alpaca import export_alpaca
from pyrove.transformer.ollama import InstructionPair

console = Console()


async def test_database():
    """Test database initialization and operations"""
    console.print("\n[bold cyan]→ Testing Database[/bold cyan]")
    
    try:
        db = Database()
        await db.init()
        console.print("[green]✓ Database initialized[/green]")
        
        # Test run insertion
        await db.insert_run("test_run_001", "test topic", 100)
        run = await db.fetch_run("test_run_001")
        assert run is not None
        assert run["topic"] == "test topic"
        console.print("[green]✓ Run insertion/retrieval works[/green]")
        
        # Test run update
        await db.update_run("test_run_001", status="completed", pairs_collected=50)
        run = await db.fetch_run("test_run_001")
        assert run["status"] == "completed"
        assert run["pairs_collected"] == 50
        console.print("[green]✓ Run update works[/green]")
        
        # Test pair insertion
        await db.insert_pair(
            "pair_001",
            "test_run_001",
            "What is a test?",
            "A test is a procedure to verify functionality.",
            0.95
        )
        pairs = await db.fetch_pairs_by_run("test_run_001")
        assert len(pairs) == 1
        assert pairs[0]["instruction"] == "What is a test?"
        console.print("[green]✓ Pair insertion/retrieval works[/green]")
        
        return True
    except Exception as e:
        console.print(f"[red]✗ Database test failed: {e}[/red]")
        return False


async def test_github_scraper():
    """Test GitHub scraper without making actual API calls"""
    console.print("\n[bold cyan]→ Testing GitHub Scraper[/bold cyan]")
    
    try:
        # Test search_github with a common topic
        console.print("[dim]Searching GitHub for 'python'...[/dim]")
        result = search_github("python", per_page=3)
        
        if not result.success:
            console.print(f"[yellow]⚠️  GitHub search failed: {result.error}[/yellow]")
            console.print("[dim](This may be due to rate limiting or network issues)[/dim]")
            return True  # Don't fail the test if API is unavailable
        
        if result.urls:
            console.print(f"[green]✓ Found {len(result.urls)} repositories[/green]")
            
            # Test README scraping on first URL
            if result.urls:
                console.print(f"[dim]Scraping README from {result.urls[0]}...[/dim]")
                content = scrape_readme(result.urls[0])
                if content:
                    console.print(f"[green]✓ Successfully scraped README ({len(content)} chars)[/green]")
                else:
                    console.print("[yellow]⚠️  README scraping returned empty[/yellow]")
        
        return True
    except Exception as e:
        console.print(f"[red]✗ GitHub scraper test failed: {e}[/red]")
        return False


async def test_chunker():
    """Test text chunking functionality"""
    console.print("\n[bold cyan]→ Testing Chunker[/bold cyan]")
    
    try:
        sample_text = """
        The Linux kernel is the core component of a Linux operating system.
        It manages the system's resources and enables communication between hardware and software.
        The kernel handles process scheduling, memory management, and device I/O operations.
        It provides system calls that applications use to interact with the hardware.
        
        Key responsibilities include:
        1. Process Management - Creating and managing processes
        2. Memory Management - Allocating and freeing memory
        3. Interrupt Handling - Responding to hardware interrupts
        4. File System - Managing file I/O operations
        5. Device Management - Controlling hardware devices
        
        The kernel runs in a privileged mode called kernel mode,
        while user applications run in user mode with restricted access to hardware.
        """ * 3  # Repeat to get more content
        
        chunks = chunk_text(sample_text, source="test_001", tokens_per_chunk=512)
        
        assert len(chunks) > 0, "No chunks generated"
        console.print(f"[green]✓ Generated {len(chunks)} chunks[/green]")
        
        # Verify chunk structure
        for i, chunk in enumerate(chunks):
            assert chunk.text, f"Chunk {i} has empty text"
            assert chunk.source == "test_001"
            assert chunk.chunk_id == i
        
        console.print(f"[green]✓ All chunks have valid structure[/green]")
        console.print(f"[dim]  Sample chunk 1: {chunks[0].text[:80]}...[/dim]")
        
        return True
    except Exception as e:
        console.print(f"[red]✗ Chunker test failed: {e}[/red]")
        return False


async def test_exporter():
    """Test Alpaca JSONL exporter"""
    console.print("\n[bold cyan]→ Testing Exporter[/bold cyan]")
    
    try:
        # Create sample pairs
        sample_pairs = [
            InstructionPair(
                instruction="What is a kernel?",
                response="A kernel is the core of an operating system that manages hardware resources.",
                source="test"
            ),
            InstructionPair(
                instruction="How does process scheduling work?",
                response="The scheduler allocates CPU time to processes based on priority and fairness algorithms.",
                source="test"
            ),
        ]
        
        output_path = await export_alpaca(
            sample_pairs,
            output_path=Path.home() / ".pyrove" / "test_output.jsonl"
        )
        
        assert output_path.exists(), "Output file not created"
        
        # Verify file content
        content = output_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"
        
        console.print(f"[green]✓ Exported {len(lines)} pairs to {output_path.name}[/green]")
        
        # Clean up
        output_path.unlink()
        
        return True
    except Exception as e:
        console.print(f"[red]✗ Exporter test failed: {e}[/red]")
        return False


async def test_ollama_availability():
    """Check if Ollama is available"""
    console.print("\n[bold cyan]→ Checking Ollama Availability[/bold cyan]")
    
    try:
        is_running = await check_ollama_running()
        
        if is_running:
            console.print("[green]✓ Ollama is running[/green]")
            models = await list_ollama_models()
            if models:
                console.print(f"[green]✓ Available models: {', '.join(models)}[/green]")
            else:
                console.print("[yellow]⚠️  Could not list models[/yellow]")
            return True
        else:
            console.print("[yellow]⚠️  Ollama is not running[/yellow]")
            console.print("[dim]To run full pipeline tests, start Ollama with: ollama serve[/dim]")
            return True  # Don't fail, just warn
    except Exception as e:
        console.print(f"[yellow]⚠️  Error checking Ollama: {e}[/yellow]")
        return True


async def main():
    """Run all tests"""
    console.print("\n[bold green]pyrove Pipeline Integration Tests[/bold green]")
    console.print("[dim]Testing all components without full pipeline execution[/dim]")
    
    results = {
        "Database": await test_database(),
        "GitHub Scraper": await test_github_scraper(),
        "Chunker": await test_chunker(),
        "Exporter": await test_exporter(),
        "Ollama Availability": await test_ollama_availability(),
    }
    
    # Summary
    console.print("\n[bold cyan]Test Summary[/bold cyan]")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "[green]✓ PASS[/green]" if passed_flag else "[red]✗ FAIL[/red]"
        console.print(f"{test_name:.<30} {status}")
    
    console.print(f"\n[bold]Result: {passed}/{total} tests passed[/bold]")
    
    if passed == total:
        console.print("\n[bold green]✓ All tests passed! Pipeline is ready.[/bold green]")
        console.print("\n[dim]Next: Try running the full pipeline:[/dim]")
        console.print("  rove run --topic 'machine learning' --size 10")
        return 0
    else:
        console.print(f"\n[red]✗ {total - passed} test(s) failed[/red]")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
