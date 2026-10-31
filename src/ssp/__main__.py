"""Command line interface.

  python -m ssp run --scale starter                 # generate + plan + validate + evaluate + export
  python -m ssp run --scale full --out output/full
  python -m ssp reproduce --scale starter           # Step 10: same seed twice -> identical checksums
  python -m ssp docs                                # regenerate docs/data_dictionary.md
  python -m ssp query "SELECT * FROM shortage LIMIT 5" # SQL over the exported seed (no sqlite tool needed)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_SEED, SCALES, get_scale


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m ssp", description="Supply shortage planner")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--scale", default="starter", choices=sorted(SCALES))
        p.add_argument("--seed", type=int, default=DEFAULT_SEED)
        p.add_argument("--skus", type=int, help="override number of SKUs")
        p.add_argument("--locations", type=int, help="override number of locations")
        p.add_argument("--weeks", type=int, help="override number of weeks (<=52)")
        p.add_argument("--suppliers", type=int, help="override number of suppliers")
        p.add_argument("--orders", type=int, help="override number of inbound orders")
        p.add_argument("--formats", default="csv,json,sql", help="comma list of csv,json,sql")

    r = sub.add_parser("run", help="generate data and run the planner")
    common(r)
    r.add_argument("--out", default=None, help="output folder (default output/<scale>)")
    rp = sub.add_parser("reproduce", help="regenerate twice and compare checksums")
    common(rp)
    rp.add_argument("--out", default=None, help="work folder (default output/reproducibility_<scale>)")
    sub.add_parser("docs", help="write docs/data_dictionary.md from the schema")
    q = sub.add_parser("query", help="run SQL against output/<scale>/sql/seed.sql in an in-memory SQLite db")
    q.add_argument("sql")
    q.add_argument("--dir", default="output/starter", help="run folder containing sql/ (default output/starter)")
    a = ap.parse_args(argv)

    if a.cmd == "docs":
        from .docs import write_data_dictionary
        p = write_data_dictionary(Path("docs/data_dictionary.md"))
        print(f"wrote {p}")
        return 0

    if a.cmd == "query":
        import sqlite3
        import pandas as pd
        con = sqlite3.connect(":memory:")
        con.executescript((Path(a.dir) / "sql" / "schema.sql").read_text())
        con.executescript((Path(a.dir) / "sql" / "seed.sql").read_text())
        with pd.option_context("display.max_columns", None, "display.width", 200, "display.max_colwidth", 80):
            print(pd.read_sql_query(a.sql, con).to_string(index=False))
        return 0

    cfg = get_scale(a.scale, n_skus=a.skus, n_locations=a.locations, n_weeks=a.weeks,
                    n_suppliers=a.suppliers, n_purchase_orders=a.orders)
    formats = tuple(x.strip() for x in a.formats.split(",") if x.strip())
    cmd = "python -m ssp " + " ".join(argv if argv is not None else sys.argv[1:])
    if a.cmd == "run":
        from .pipeline import run
        res = run(cfg, a.seed, a.out or f"output/{a.scale}", formats=formats, command=cmd)
        return 0 if res["validation"] == "PASS" else 1
    if a.cmd == "reproduce":
        from .pipeline import reproduce
        res = reproduce(cfg, a.seed, a.out or f"output/reproducibility_{a.scale}", formats=formats)
        return 0 if res["reproducible"] else 1


if __name__ == "__main__":
    sys.exit(main())
