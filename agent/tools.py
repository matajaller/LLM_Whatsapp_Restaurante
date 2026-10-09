import json
import sqlite3
import uuid
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


# ---- read-only tools: each returns plain data the model can read ----

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


# ---- ordering: quote first, then place only after the customer replies ----

# In-memory state, kept separate per conversation (session)
_quotes = {}   # quote_id -> {"session", "lines", "total", "turn"}
_turns = {}    # session_id -> number of messages that customer has sent


def new_customer_turn(session_id):
    """Called by the agent each time a customer sends a message."""
    _turns[session_id] = _turns.get(session_id, 0) + 1


def quote_order(items, session_id):
    """Validates items against the database and prices them. Saves nothing."""
    conn = _connect()
    try:
        # Same dish listed twice becomes one line with the quantities added
        wanted = {}
        for it in items:
            key = it["name"].strip().lower()
            wanted[key] = wanted.get(key, 0) + int(it["quantity"])

        lines, problems = [], []
        for key, qty in wanted.items():
            row = conn.execute(
                "SELECT id, name, price, available FROM menu_items WHERE LOWER(name) = ?", (key,)
            ).fetchone()
            if row is None:
                problems.append(f"'{key}' no está en el menú")
            elif not row["available"]:
                problems.append(f"'{row['name']}' no está disponible hoy")
            elif not 1 <= qty <= 50:
                problems.append(f"cantidad inválida para '{row['name']}'")
            else:
                lines.append({"menu_item_id": row["id"], "name": row["name"], "quantity": qty,
                              "unit_price": row["price"], "subtotal": row["price"] * qty})
    finally:
        conn.close()

    if problems:
        return {"error": "No se pudo cotizar el pedido", "problemas": problems}

    quote_id = uuid.uuid4().hex[:8]
    total = sum(l["subtotal"] for l in lines)
    _quotes[quote_id] = {"session": session_id, "lines": lines, "total": total,
                         "turn": _turns.get(session_id, 0)}
    return {"quote_id": quote_id, "lineas": lines, "total": total,
            "siguiente_paso": "Show this summary to the customer and ask them to confirm."}


def place_order(quote_id, customer_name, session_id):
    """Saves a quoted order, but only from the same conversation and only after the customer replied."""
    quote = _quotes.get(quote_id)
    # A quote from someone else's conversation is treated as if it didn't exist
    if quote is None or quote["session"] != session_id:
        return {"error": "Quote not found. Create a new quote with quote_order."}
    if quote["turn"] == _turns.get(session_id, 0):
        # Quote and placement in the same customer turn means nobody confirmed it
        return {"error": "The customer has not confirmed yet. Show the summary and wait for their reply."}

    conn = _connect()
    try:
        with conn:  # one transaction: the order and all its lines are saved together or not at all
            cur = conn.execute("INSERT INTO orders (customer_name) VALUES (?)", (customer_name,))
            order_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                [(order_id, l["menu_item_id"], l["quantity"], l["unit_price"]) for l in quote["lines"]],
            )
    finally:
        conn.close()

    del _quotes[quote_id]
    return {"order_id": order_id, "total": quote["total"], "estado": "pending"}


# ---- escalation to a human ----

def request_staff_handoff(question, session_id, customer_name=None, contact=None):
    """Saves a question for a staff member to answer; the agent can only promise a handoff if this succeeds."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO handoff_requests (session_id, customer_name, contact, question) VALUES (?, ?, ?, ?)",
                (session_id, customer_name, contact, question),
            )
            ticket_id = cur.lastrowid
    finally:
        conn.close()
    return {"ticket_id": ticket_id, "estado": "open"}


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
    {
        "name": "quote_order",
        "description": "Validates and prices an order using exact menu item names. Saves nothing. "
                       "Always call this before place_order and show the customer the returned summary and total.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Exact menu item name, e.g. 'Taco al pastor'"},
                            "quantity": {"type": "integer", "minimum": 1},
                        },
                        "required": ["name", "quantity"],
                    },
                }
            },
            "required": ["items"],
        },
    },
    {
        "name": "place_order",
        "description": "Saves a quoted order. Only call it after the customer has explicitly confirmed "
                       "the summary from quote_order in their latest message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "quote_id": {"type": "string"},
                "customer_name": {"type": "string"},
            },
            "required": ["quote_id", "customer_name"],
        },
    },
    {
        "name": "request_staff_handoff",
        "description": "Passes a question to a human staff member. Use it when the customer agrees to escalate a question "
                       "you cannot answer from the other tools (allergies, unlisted ingredients, special or large orders).",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The customer's question, summarised clearly for staff."},
                "customer_name": {"type": "string"},
                "contact": {"type": "string", "description": "Phone number or other way for staff to reply."},
            },
            "required": ["question"],
        },
    },
]

# Maps a tool name from the model to the Python function that runs it
TOOL_FUNCTIONS = {
    "get_menu": get_menu,
    "get_opening_hours": get_opening_hours,
    "get_business_info": get_business_info,
    "quote_order": quote_order,
    "place_order": place_order,
    "request_staff_handoff": request_staff_handoff,
}

# Tools that need to know which conversation they belong to; the agent passes session_id to these
SESSION_TOOLS = {"quote_order", "place_order", "request_staff_handoff"}


if __name__ == "__main__":
    # Quick manual check of the read-only tools, no LLM involved
    print(json.dumps(get_menu("Tacos"), ensure_ascii=False, indent=2))
    print(json.dumps(get_opening_hours(), ensure_ascii=False, indent=2))
    print(json.dumps(get_business_info(), ensure_ascii=False, indent=2))