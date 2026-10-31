"""The SQL seed loads into SQLite with foreign keys enforced."""
import sqlite3


def test_seed_sql_loads_with_foreign_keys(tiny_run):
    out, _ = tiny_run
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((out / "sql" / "schema.sql").read_text())
    con.executescript((out / "sql" / "seed.sql").read_text())
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    n = con.execute("SELECT COUNT(*) FROM purchase_order").fetchone()[0]
    with open(out / "input" / "purchase_order.csv") as fh:
        assert n == sum(1 for _ in fh) - 1
    # a join across the hierarchy works
    q = """SELECT COUNT(*) FROM purchase_order_line l JOIN purchase_order p ON p.po_id = l.po_id
           JOIN supplier s ON s.supplier_id = p.supplier_id JOIN sku k ON k.sku_id = l.sku_id"""
    assert con.execute(q).fetchone()[0] > 0
