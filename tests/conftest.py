import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

import tools  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Every test gets its own database built from the real schema and seed, plus empty in-memory state."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    for name in ("schema.sql", "seed.sql"):
        conn.executescript((ROOT / "db" / name).read_text(encoding="utf-8"))
    conn.commit()
    conn.close()

    monkeypatch.setattr(tools, "DB_PATH", db)
    # Tests shouldn't depend on the time of day they run at
    monkeypatch.setenv("ALLOW_ORDERS_WHEN_CLOSED", "1")
    tools._quotes.clear()
    tools._turns.clear()
    return db