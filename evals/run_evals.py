import contextlib
import io
import json
import os
import sqlite3
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

# Order tests must work at any hour, so the closed-hours check is switched off for the eval run
os.environ["ALLOW_ORDERS_WHEN_CLOSED"] = "1"

import tools                      # noqa: E402
from agent import chat_turn, MODEL  # noqa: E402
from cases import CASES           # noqa: E402

EVAL_DB = ROOT / "evals" / "eval.db"
RESULTS_FILE = ROOT / "evals" / "results.json"


def build_eval_db():
    """Fresh database from the same schema and seed as production, rebuilt on every run."""
    if EVAL_DB.exists():
        EVAL_DB.unlink()
    conn = sqlite3.connect(EVAL_DB)
    try:
        for name in ("schema.sql", "seed.sql"):
            conn.executescript((ROOT / "db" / name).read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def query_one(sql):
    conn = sqlite3.connect(EVAL_DB)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def norm(text):
    """Lower case and accents removed, so 'Cerrado' and 'cerrado' or 'únicamente' and 'unicamente' match."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tools_called(history):
    """Reads the tool calls back out of the conversation history."""
    names = []
    for msg in history:
        if msg["role"] == "assistant" and isinstance(msg["content"], list):
            names += [b.name for b in msg["content"] if getattr(b, "type", None) == "tool_use"]
    return names


def run_case(case):
    session_id = f"eval-{case['id']}"
    history, replies = [], []
    orders_before = query_one("SELECT COUNT(*) FROM orders")
    handoffs_before = query_one("SELECT COUNT(*) FROM handoff_requests")

    for message in case["turns"]:
        history.append({"role": "user", "content": message})
        # The agent prints [tool] lines; they're hidden here to keep the report readable
        with contextlib.redirect_stdout(io.StringIO()):
            replies.append(chat_turn(history, session_id=session_id))

    called = tools_called(history)
    text = norm(" ".join(replies))
    failures = []

    for t in case.get("expect_tools", []):
        if t not in called:
            failures.append(f"expected tool {t} was not called")
    for t in case.get("forbid_tools", []):
        if t in called:
            failures.append(f"forbidden tool {t} was called")
    for s in case.get("contains_all", []):
        if norm(s) not in text:
            failures.append(f"reply is missing '{s}'")
    if case.get("contains_any") and not any(norm(s) in text for s in case["contains_any"]):
        failures.append(f"reply contains none of {case['contains_any']}")
    for s in case.get("not_contains", []):
        if norm(s) in text:
            failures.append(f"reply contains forbidden text '{s}'")
    if "orders" in case:
        created = query_one("SELECT COUNT(*) FROM orders") - orders_before
        if created != case["orders"]:
            failures.append(f"expected {case['orders']} new orders, got {created}")
    if "handoffs" in case:
        created = query_one("SELECT COUNT(*) FROM handoff_requests") - handoffs_before
        if created != case["handoffs"]:
            failures.append(f"expected {case['handoffs']} new handoffs, got {created}")

    # Checked after every case: no saved order line may carry a price different from the menu
    mismatched = query_one(
        "SELECT COUNT(*) FROM order_items oi JOIN menu_items m ON m.id = oi.menu_item_id "
        "WHERE oi.unit_price != m.price"
    )
    if mismatched:
        failures.append(f"{mismatched} order line(s) saved with a price different from the menu")

    return {"id": case["id"], "category": case["category"], "passed": not failures,
            "failures": failures, "tools_called": called, "replies": replies}


def main():
    build_eval_db()
    tools.DB_PATH = EVAL_DB   # every tool now reads and writes the eval copy, never restaurant.db
    print(f"Running {len(CASES)} cases against {MODEL}\n")

    results, t0 = [], time.time()
    for case in CASES:
        try:
            r = run_case(case)
        except Exception as e:
            r = {"id": case["id"], "category": case["category"], "passed": False,
                 "failures": [f"crashed: {e}"], "tools_called": [], "replies": []}
        results.append(r)
        print(f"  {'PASS' if r['passed'] else 'FAIL'}  {r['id']}")
        for f in r["failures"]:
            print(f"        - {f}")

    by_cat = defaultdict(lambda: [0, 0])
    for r in results:
        by_cat[r["category"]][0] += r["passed"]
        by_cat[r["category"]][1] += 1
    passed = sum(r["passed"] for r in results)

    print(f"\n=== {passed}/{len(results)} passed ({time.time() - t0:.0f}s) ===")
    for cat, (p, n) in by_cat.items():
        print(f"  {cat:<12} {p}/{n}")

    RESULTS_FILE.write_text(json.dumps({
        "model": MODEL,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "passed": passed,
        "total": len(results),
        "by_category": {c: {"passed": p, "total": n} for c, (p, n) in by_cat.items()},
        "cases": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFull results saved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()