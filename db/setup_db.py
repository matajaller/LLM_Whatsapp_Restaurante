import sqlite3
from pathlib import Path

# Database sits at the project root; *.db is in .gitignore, so only the SQL files are committed
DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR.parent / "restaurant.db"


def setup():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript((DB_DIR / "schema.sql").read_text(encoding="utf-8"))
        conn.executescript((DB_DIR / "seed.sql").read_text(encoding="utf-8"))
        conn.commit()

        for table in ("menu_items", "opening_hours", "business_info", "orders"):
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {n} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    setup()
    print(f"Database ready at {DB_PATH}")