import sqlite3

import tools


def count(db, table):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


# ---- menu ----

def test_menu_reads_prices_and_availability_from_db():
    tacos = {item["name"]: item for item in tools.get_menu("Tacos")}
    assert tacos["Taco al pastor"]["price"] == 22
    assert tacos["Taco de birria"]["available"] is False


# ---- quoting ----

def test_quote_uses_database_prices():
    tools.new_customer_turn("s1")
    quote = tools.quote_order([{"name": "Taco al pastor", "quantity": 2}], session_id="s1")
    assert quote["total"] == 44


def test_quote_ignores_letter_case():
    tools.new_customer_turn("s1")
    quote = tools.quote_order([{"name": "taco AL pastor", "quantity": 1}], session_id="s1")
    assert quote["total"] == 22


def test_quote_merges_repeated_items():
    tools.new_customer_turn("s1")
    quote = tools.quote_order(
        [{"name": "Taco de res", "quantity": 1}, {"name": "Taco de res", "quantity": 2}], session_id="s1"
    )
    assert len(quote["lineas"]) == 1
    assert quote["lineas"][0]["quantity"] == 3


def test_quote_rejects_unknown_item():
    tools.new_customer_turn("s1")
    assert "error" in tools.quote_order([{"name": "Taco de pescado", "quantity": 1}], session_id="s1")


def test_quote_rejects_unavailable_item():
    tools.new_customer_turn("s1")
    assert "error" in tools.quote_order([{"name": "Taco de birria", "quantity": 1}], session_id="s1")


def test_quote_rejects_excessive_quantity():
    tools.new_customer_turn("s1")
    assert "error" in tools.quote_order([{"name": "Taco de res", "quantity": 200}], session_id="s1")


def test_quote_refused_when_closed(monkeypatch):
    monkeypatch.delenv("ALLOW_ORDERS_WHEN_CLOSED")
    monkeypatch.setattr(tools, "get_opening_hours", lambda: {"abierto_ahora": False})
    tools.new_customer_turn("s1")
    assert "error" in tools.quote_order([{"name": "Taco de res", "quantity": 1}], session_id="s1")


# ---- placing orders ----

def test_order_not_saved_in_same_turn_as_quote(fresh_db):
    tools.new_customer_turn("s1")
    quote = tools.quote_order([{"name": "Torta", "quantity": 1}], session_id="s1")
    result = tools.place_order(quote["quote_id"], "Luis", session_id="s1")
    assert "error" in result
    assert count(fresh_db, "orders") == 0


def test_order_saved_after_customer_replies(fresh_db):
    tools.new_customer_turn("s1")
    quote = tools.quote_order([{"name": "Torta", "quantity": 1}], session_id="s1")
    tools.new_customer_turn("s1")  # the customer's confirmation message
    result = tools.place_order(quote["quote_id"], "Luis", session_id="s1")
    assert result["total"] == 55
    assert count(fresh_db, "orders") == 1


def test_saved_lines_carry_menu_price(fresh_db):
    tools.new_customer_turn("s1")
    quote = tools.quote_order([{"name": "Agua de horchata", "quantity": 2}], session_id="s1")
    tools.new_customer_turn("s1")
    tools.place_order(quote["quote_id"], "Ana", session_id="s1")
    conn = sqlite3.connect(fresh_db)
    unit_price = conn.execute("SELECT unit_price FROM order_items").fetchone()[0]
    conn.close()
    assert unit_price == 25


def test_quote_cannot_be_placed_from_another_session(fresh_db):
    tools.new_customer_turn("s1")
    quote = tools.quote_order([{"name": "Burrito", "quantity": 1}], session_id="s1")
    tools.new_customer_turn("s2")
    tools.new_customer_turn("s2")
    assert "error" in tools.place_order(quote["quote_id"], "Intruso", session_id="s2")
    assert count(fresh_db, "orders") == 0


def test_quote_can_only_be_placed_once(fresh_db):
    tools.new_customer_turn("s1")
    quote = tools.quote_order([{"name": "Flan", "quantity": 1}], session_id="s1")
    tools.new_customer_turn("s1")
    tools.place_order(quote["quote_id"], "Sofía", session_id="s1")
    assert "error" in tools.place_order(quote["quote_id"], "Sofía", session_id="s1")
    assert count(fresh_db, "orders") == 1


# ---- staff handoff ----

def test_handoff_creates_ticket(fresh_db):
    result = tools.request_staff_handoff("¿El guacamole tiene cacahuate?", session_id="s1", contact="81 1234 5678")
    assert result["ticket_id"] == 1
    assert count(fresh_db, "handoff_requests") == 1