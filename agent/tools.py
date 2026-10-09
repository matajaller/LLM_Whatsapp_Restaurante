import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DB_PATH = Path(__file__).resolve().parent.parent / "restaurant.db"
TIMEZONE = ZoneInfo("America/Monterrey")
DAY_NAMES = {1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 7: "domingo"}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---- tool functions: each returns plain data the model can read ----

def get_menu(category=None):
    """Full menu, or one category. Unavailable items are included but flagged."""
    conn = _connect()
    try:
        sql = "SELECT name, category, description, price, available FROM menu_items"
        params = ()
        if category:
            sql += " WHERE category = ?"
            params = (category,)
        rows = conn.execute(sql + " ORDER BY category, name", params).fetchall()
        return [
            {**dict(r), "available": bool(r["available"])}
            for r in rows
        ]
    finally:
        conn.close()


def get_opening_hours():
    """Weekly schedule plus whether the restaurant is open at this moment."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT day_of_week, opens, closes FROM opening_hours ORDER BY day_of_week").fetchall()
    finally:
        conn.close()

    now = datetime.now(TIMEZONE)
    today = now.isoweekday()          # 1 = Monday, matching the table
    current = now.strftime("%H:%M")   # "HH:MM" strings compare correctly as text

    schedule, open_now = [], False
    for r in rows:
        closed = r["opens"] is None
        schedule.append({
            "dia": DAY_NAMES[r["day_of_week"]],
            "horario": "cerrado" if closed else f"{r['opens']} a {r['closes']}",
        })
        if r["day_of_week"] == today and not closed:
            open_now = r["opens"] <= current < r["closes"]

    return {
        "hoy": DAY_NAMES[today],
        "hora_actual": current,
        "abierto_ahora": open_now,
        "horario_semanal": schedule,
    }


def get_business_info():
    """Address, payment methods, delivery terms and similar facts."""
    conn = _connect()
    try:
        return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM business_info")}
    finally:
        conn.close()


# ---- descriptions the model reads to decide which tool to call ----

TOOLS = [
    {
        "name": "get_menu",
        "description": "Returns menu items with name, category, description, price in MXN and availability. "
                       "Use it for any question about dishes, drinks or prices. Never quote a price without calling it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["Tacos", "Antojitos", "Extras", "Bebidas", "Postres"],
                    "description": "Optional: limit the menu to one category.",
                }
            },
        },
    },
    {
        "name": "get_opening_hours",
        "description": "Returns the weekly schedule, today's day, the current local time and whether the restaurant is open right now.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_business_info",
        "description": "Returns address, accepted payment methods, delivery area, delivery cost and delivery time.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Maps a tool name from the model to the Python function that runs it
TOOL_FUNCTIONS = {
    "get_menu": get_menu,
    "get_opening_hours": get_opening_hours,
    "get_business_info": get_business_info,
}


if __name__ == "__main__":
    # Quick manual check of every tool, no LLM involved
    print(json.dumps(get_menu("Tacos"), ensure_ascii=False, indent=2))
    print(json.dumps(get_opening_hours(), ensure_ascii=False, indent=2))
    print(json.dumps(get_business_info(), ensure_ascii=False, indent=2))
    