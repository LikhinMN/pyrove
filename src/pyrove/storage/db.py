"""database module of the pyrove package"""
from dataclasses import dataclass, field
from pathlib import Path
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
        return  aiosqlite.connect(self.path)
