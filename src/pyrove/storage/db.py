"""database module of the pyrove package"""
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    topic           TEXT NOT NULL,
    status          TEXT DEFAULT 'running',
    target_size     INTEGER,
    pairs_collected INTEGER DEFAULT 0,
    quality_score   REAL DEFAULT 0.0,
    iterations      INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pairs (
    id            TEXT PRIMARY KEY,
    run_id        TEXT REFERENCES runs(id),
    instruction   TEXT,
    response      TEXT,
    quality_score REAL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    description   TEXT,
    status        TEXT DEFAULT 'pending',
    priority      INTEGER DEFAULT 0,
    run_id        TEXT REFERENCES runs(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at  TIMESTAMP
);

"""
DB_PATH = Path.home() / ".pyrove" / "pyrove.db"


@dataclass
class Database:
    path: Path = field(default=DB_PATH)

    async def init(self):
        async with await self.connect() as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()


    def __post_init__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        return aiosqlite.connect(self.path)

    # ==================== RUN OPERATIONS ====================

    async def insert_run(
        self,
        run_id: str,
        topic: str,
        target_size: int,
    ) -> None:
        """Insert a new run record."""
        async with await self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO runs (id, topic, target_size, status)
                VALUES (?, ?, ?, 'running')
                """,
                (run_id, topic, target_size),
            )
            await conn.commit()

    async def update_run(
        self,
        run_id: str,
        status: Optional[str] = None,
        pairs_collected: Optional[int] = None,
        quality_score: Optional[float] = None,
        iterations: Optional[int] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        """Update run record with new values."""
        updates = []
        params = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if pairs_collected is not None:
            updates.append("pairs_collected = ?")
            params.append(pairs_collected)
        if quality_score is not None:
            updates.append("quality_score = ?")
            params.append(quality_score)
        if iterations is not None:
            updates.append("iterations = ?")
            params.append(iterations)
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)

        if not updates:
            return

        params.append(run_id)
        query = f"UPDATE runs SET {', '.join(updates)} WHERE id = ?"

        async with await self.connect() as conn:
            await conn.execute(query, params)
            await conn.commit()

    async def fetch_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single run by ID."""
        async with await self.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM runs WHERE id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch all runs, most recent first."""
        async with await self.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ==================== PAIR OPERATIONS ====================

    async def insert_pair(
        self,
        pair_id: str,
        run_id: str,
        instruction: str,
        response: str,
        quality_score: float = 0.0,
    ) -> None:
        """Insert a new instruction-response pair."""
        async with await self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO pairs (id, run_id, instruction, response, quality_score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (pair_id, run_id, instruction, response, quality_score),
            )
            await conn.commit()

    async def fetch_pairs_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetch all instruction-response pairs for a run."""
        async with await self.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM pairs WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetch_pairs_by_quality(
        self,
        run_id: str,
        min_quality: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Fetch pairs above a quality threshold."""
        async with await self.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT * FROM pairs 
                WHERE run_id = ? AND quality_score >= ?
                ORDER BY quality_score DESC
                """,
                (run_id, min_quality),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def count_pairs_by_run(self, run_id: str) -> int:
        """Count total pairs for a run."""
        async with await self.connect() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) as count FROM pairs WHERE run_id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ==================== TASK OPERATIONS ====================

    async def insert_task(
        self,
        task,
    ) -> None:
        """Insert a new task."""
        async with await self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (id, title, description, status, priority, run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task.id, task.title, task.description, task.status, task.priority, task.run_id, task.created_at),
            )
            await conn.commit()

    async def fetch_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single task by ID."""
        async with await self.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_tasks(
        self,
        status: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch tasks with optional filtering."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)

        query += " ORDER BY priority DESC, created_at ASC"

        async with await self.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        """Update a task."""
        updates = []
        params = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)

        if not updates:
            return

        params.append(task_id)
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"

        async with await self.connect() as conn:
            await conn.execute(query, params)
            await conn.commit()

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        async with await self.connect() as conn:
            cursor = await conn.execute(
                "DELETE FROM tasks WHERE id = ?",
                (task_id,),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def delete_tasks_by_status(self, status: str) -> int:
        """Delete all tasks with a specific status."""
        async with await self.connect() as conn:
            cursor = await conn.execute(
                "DELETE FROM tasks WHERE status = ?",
                (status,),
            )
            await conn.commit()
            return cursor.rowcount
