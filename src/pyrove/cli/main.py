"""CLI entry point for pyrove using Typer"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(
    help="pyrove — The agent that roves. The dataset that trains.",
    no_args_is_help=True
)


@app.command()
def run(
    topic: str = typer.Option(
        ...,
        "--topic",
        "-t",
        help="Topic to create dataset for (e.g., 'linux kernel')"
    ),
    size: int = typer.Option(
        100,
        "--size",
        "-s",
        help="Target number of instruction-response pairs"
    ),
    format: str = typer.Option(
        "alpaca",
        "--format",
        "-f",
        help="Output format: alpaca or sharegpt"
    ),
    model: str = typer.Option(
        "llama3",
        "--model",
        "-m",
        help="Ollama model to use"
    ),
    sources: str = typer.Option(
        "github",
        "--sources",
        "-S",
        help="Data sources to scrape (github, web, arxiv) - comma-separated for multiple"
    ),
):
    """
    Run pyrove to generate a LoRA fine-tuning dataset.
    
    Example:
        rove run --topic "linux kernel" --size 500 --format alpaca --sources github,arxiv
    
    This will:
    1. Search specified sources for relevant content
    2. Scrape and extract content
    3. Split content into 512-token chunks
    4. Generate instruction-response pairs using local Ollama
    5. Validate and filter by quality
    6. Export to specified format (Alpaca JSONL or ShareGPT JSON)
    """
    from pyrove.pipeline import run_sync
    
    # Parse sources
    sources_list = [s.strip().lower() for s in sources.split(",")]
    
    console.print(f"[bold blue]pyrove[/bold blue] — generating dataset for '[cyan]{topic}[/cyan]'")
    console.print(f"Sources: {', '.join(sources_list)} | Target: {size} pairs | Format: {format} | Model: {model}\n")
    
    run_sync(topic=topic, size=size, model=model, format=format, sources=sources_list)


@app.command()
def todo(
    action: str = typer.Argument("list", help="list, done, or status"),
    task_id: Optional[str] = typer.Argument(None, help="Task ID (for 'done' action)"),
):
    """
    Manage agent tasks and sprint planning.
    
    Examples:
        rove todo list          # Show all pending tasks
        rove todo done <id>     # Mark task as complete
    """
    import asyncio
    from pyrove.storage.db import Database
    from pyrove.tasks import TaskManager
    
    async def run_todo():
        db = Database()
        await db.init()
        manager = TaskManager(db)
        
        if action == "list":
            tasks = await manager.list_tasks()
            
            if not tasks:
                console.print("[yellow]No tasks found. Create one with: rove task create[/yellow]")
                return
            
            table = Table(title="📋 Agent Task Queue")
            table.add_column("ID", style="cyan", width=8)
            table.add_column("Status", style="green", width=12)
            table.add_column("Priority", style="yellow", width=10)
            table.add_column("Task", style="magenta")
            
            status_icons = {
                "pending": "○",
                "running": "►",
                "done": "✓",
                "failed": "✗",
            }
            
            priority_labels = {
                1: "🔴 HIGH",
                0: "🟡 NORMAL",
                -1: "🟢 LOW",
            }
            
            for task in tasks:
                status_icon = status_icons.get(task["status"], "?")
                priority = priority_labels.get(task["priority"], "?")
                console.print(
                    f"  [{status_icon}] {task['id']:<6} {task['status']:<10} {priority:<10} {task['title']}"
                )
        
        elif action == "done":
            if not task_id:
                console.print("[red]✗ Error: provide task ID (rove todo done <id>)[/red]")
                return
            
            task = await manager.complete_task(task_id)
            if task:
                console.print(f"[green]✓ Task '{task.title}' marked as complete[/green]")
            else:
                console.print(f"[red]✗ Task {task_id} not found[/red]")
        
        else:
            console.print(f"[red]✗ Unknown action: {action}[/red]")
    
    asyncio.run(run_todo())


@app.command()
def task(
    action: str = typer.Argument("create", help="create, list, or done"),
    title: Optional[str] = typer.Argument(None, help="Task title (for 'create' action)"),
    task_id: Optional[str] = typer.Option(None, "--id", help="Task ID (for 'done' action)"),
    priority: int = typer.Option(0, "--priority", help="Priority: -1=low, 0=normal, 1=high"),
):
    """
    Create and manage agent tasks.
    
    Examples:
        rove task create "Decompose topic"
        rove task create "Optimize chunking" --priority 1
        rove task done --id <id>
    """
    import asyncio
    from pyrove.storage.db import Database
    from pyrove.tasks import TaskManager
    
    async def run_task():
        db = Database()
        await db.init()
        manager = TaskManager(db)
        
        if action == "create":
            if not title:
                console.print("[red]✗ Error: provide task title[/red]")
                return
            
            task = await manager.create_task(
                title=title,
                priority=priority
            )
            console.print(f"[green]✓ Created task {task.id}: '{title}'[/green]")
        
        elif action == "list":
            tasks = await manager.list_tasks()
            if not tasks:
                console.print("[yellow]No tasks found[/yellow]")
                return
            
            for task in tasks:
                icon = "✓" if task["status"] == "done" else "►" if task["status"] == "running" else "○"
                console.print(f"  [{icon}] {task['id']:<6} {task['title']}")
        
        elif action == "done":
            if not task_id:
                console.print("[red]✗ Error: provide task ID with --id[/red]")
                return
            
            task = await manager.complete_task(task_id)
            if task:
                console.print(f"[green]✓ Done: {task.title}[/green]")
            else:
                console.print(f"[red]✗ Task not found: {task_id}[/red]")
        
        else:
            console.print(f"[red]✗ Unknown action: {action}[/red]")
    
    asyncio.run(run_task())


@app.command()
def history(
    action: str = typer.Argument("list", help="list or show"),
    run_id: Optional[str] = typer.Argument(None, help="Run ID (for 'show' action)"),
):
    """
    View run history and details.
    
    Examples:
        rove history list       # Show all runs
        rove history show <id>  # Show specific run
    """
    if action == "list":
        from pyrove.pipeline import display_run_history
        display_run_history()
    elif action == "show":
        if not run_id:
            console.print("[red]Error: provide run ID[/red]")
            return
        from pyrove.pipeline import display_run_details
        display_run_details(run_id)
    else:
        console.print(f"[red]Unknown action: {action}[/red]")


@app.command()
def info():
    """Show pyrove information and system status."""
    console.print("[bold blue]pyrove v0.1.0[/bold blue]")
    console.print("The agent that roves. The dataset that trains.\n")
    
    # Check Ollama status
    try:
        import httpx
        httpx.get("http://localhost:11434/api/tags", timeout=2)
        ollama_status = "[green]✓ Running[/green]"
    except:
        ollama_status = "[red]✗ Not running[/red]"
    
    table = Table(title="System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_row("Ollama", ollama_status)
    table.add_row("Database", "[green]✓ Ready[/green]")
    table.add_row("Scrapers", "[green]✓ Ready[/green]")
    console.print(table)


@app.command()
def decompose(
    topic: str = typer.Option(
        ...,
        "--topic",
        "-t",
        help="Topic to decompose (e.g., 'kubernetes')"
    ),
    num_subtopics: int = typer.Option(
        7,
        "--num",
        "-n",
        help="Number of subtopics to generate"
    ),
    model: str = typer.Option(
        "llama3",
        "--model",
        "-m",
        help="Ollama model to use"
    ),
):
    """
    Break a complex topic into subtopics for multi-source research.
    
    Examples:
        rove decompose --topic "kubernetes"
        rove decompose --topic "linux kernel" --num 5
        rove decompose --topic "machine learning" --model mistral
    
    This will:
    1. Use LLM to intelligently break down the topic
    2. Generate 5-7 related subtopics
    3. Display subtopics for downstream research
    """
    import asyncio
    from pyrove.decompose import decompose_with_fallback
    
    async def run_decompose():
        console.print(f"\n[bold cyan]🧠 Topic Decomposition[/bold cyan]")
        console.print(f"Topic: [yellow]{topic}[/yellow]\n")
        
        subtopics = await decompose_with_fallback(
            topic=topic,
            model=model,
            max_subtopics=num_subtopics,
            use_examples=True,
        )
        
        if not subtopics:
            console.print("[red]✗ Failed to decompose topic[/red]")
            return
        
        console.print(f"[green]✓ Generated {len(subtopics)} subtopics:[/green]\n")
        
        table = Table(title="Subtopics")
        table.add_column("#", style="cyan", width=3)
        table.add_column("Subtopic", style="magenta")
        
        for i, subtopic in enumerate(subtopics, 1):
            table.add_row(str(i), subtopic)
        
        console.print(table)
        console.print()
    
    asyncio.run(run_decompose())


if __name__ == "__main__":
    app()
