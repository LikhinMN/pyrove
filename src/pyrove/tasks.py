"""Task management system for pyrove agent planning"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Task:
    """Represents a task in the agent brain"""
    id: str
    title: str
    status: str = TaskStatus.PENDING.value
    priority: int = 0  # 0=normal, 1=high, -1=low
    description: Optional[str] = None
    run_id: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def mark_done(self):
        """Mark task as completed"""
        self.status = TaskStatus.DONE.value
        self.completed_at = datetime.utcnow().isoformat()
        logger.info(f"✓ Task '{self.title}' marked as done")

    def mark_running(self):
        """Mark task as running"""
        self.status = TaskStatus.RUNNING.value
        logger.info(f"► Task '{self.title}' started")

    def mark_failed(self):
        """Mark task as failed"""
        self.status = TaskStatus.FAILED.value
        self.completed_at = datetime.utcnow().isoformat()
        logger.warning(f"✗ Task '{self.title}' failed")


class TaskManager:
    """Manager for task operations"""

    def __init__(self, db):
        """
        Initialize TaskManager with database connection.
        
        Args:
            db: Database instance
        """
        self.db = db

    async def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: int = 0,
        run_id: Optional[str] = None,
    ) -> Task:
        """
        Create a new task.
        
        Args:
            title: Task title/description
            description: Detailed task description
            priority: 0=normal, 1=high, -1=low
            run_id: Associated run ID (optional)
        
        Returns:
            Created Task object
        """
        task = Task(
            id=str(uuid4())[:8],
            title=title,
            description=description,
            priority=priority,
            run_id=run_id
        )
        
        await self.db.insert_task(task)
        logger.info(f"Created task: {title}")
        return task

    async def list_tasks(
        self,
        status: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> List[Task]:
        """
        List all tasks with optional filtering.
        
        Args:
            status: Filter by status (pending, running, done)
            run_id: Filter by run ID
        
        Returns:
            List of Task objects
        """
        return await self.db.fetch_tasks(status=status, run_id=run_id)

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a specific task by ID.
        
        Args:
            task_id: Task ID
        
        Returns:
            Task object or None
        """
        return await self.db.fetch_task(task_id)

    async def update_task_status(
        self,
        task_id: str,
        status: str
    ) -> Optional[Task]:
        """
        Update task status.
        
        Args:
            task_id: Task ID
            status: New status (pending, running, done, failed)
        
        Returns:
            Updated Task object
        """
        if status not in [s.value for s in TaskStatus]:
            raise ValueError(f"Invalid status: {status}")
        
        await self.db.update_task(task_id, status=status)
        task = await self.get_task(task_id)
        
        status_msg = {"done": "✓", "running": "►", "failed": "✗", "pending": "○"}
        icon = status_msg.get(status, "•")
        logger.info(f"{icon} Task {task_id}: {task.title} → {status}")
        
        return task

    async def complete_task(self, task_id: str) -> Optional[Task]:
        """
        Mark task as done.
        
        Args:
            task_id: Task ID
        
        Returns:
            Updated Task object
        """
        return await self.update_task_status(task_id, TaskStatus.DONE.value)

    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task.
        
        Args:
            task_id: Task ID
        
        Returns:
            True if deleted, False if not found
        """
        return await self.db.delete_task(task_id)

    async def clear_completed_tasks(self) -> int:
        """
        Delete all completed tasks.
        
        Returns:
            Number of tasks deleted
        """
        return await self.db.delete_tasks_by_status(TaskStatus.DONE.value)


def format_task_for_display(task: Task) -> dict:
    """
    Format task for CLI display.
    
    Args:
        task: Task object
    
    Returns:
        Dictionary with formatted fields
    """
    status_icons = {
        TaskStatus.PENDING.value: "○",
        TaskStatus.RUNNING.value: "►",
        TaskStatus.DONE.value: "✓",
        TaskStatus.FAILED.value: "✗",
    }
    
    priority_labels = {
        1: "HIGH",
        0: "NORMAL",
        -1: "LOW",
    }
    
    return {
        "id": task.id,
        "status": f"{status_icons.get(task.status, '?')} {task.status.upper()}",
        "priority": priority_labels.get(task.priority, "?"),
        "title": task.title,
        "created": task.created_at[:10] if task.created_at else "N/A",
    }
