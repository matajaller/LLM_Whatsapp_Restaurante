-- Menu: what customers can order
CREATE TABLE IF NOT EXISTS menu_items (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL,
    description TEXT,
    price       REAL NOT NULL CHECK (price >= 0),
    available   INTEGER NOT NULL DEFAULT 1      -- 0 = temporarily off the menu
);

-- Opening hours, 1 = lunes ... 7 = domingo; NULL times mean closed that day
CREATE TABLE IF NOT EXISTS opening_hours (
    day_of_week INTEGER PRIMARY KEY CHECK (day_of_week BETWEEN 1 AND 7),
    opens       TEXT,
    closes      TEXT
);

-- Free-form facts: address, payment methods, delivery terms
CREATE TABLE IF NOT EXISTS business_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Orders taken by the agent (used from step 3 onwards)
CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY,
    customer_name  TEXT,
    customer_phone TEXT,
    status         TEXT NOT NULL DEFAULT 'pending',
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Price is copied in at order time, so later menu changes don't rewrite old orders
CREATE TABLE IF NOT EXISTS order_items (
    order_id     INTEGER NOT NULL REFERENCES orders(id),
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    unit_price   REAL NOT NULL,
    PRIMARY KEY (order_id, menu_item_id)
);