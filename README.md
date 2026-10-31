# Supply Shortage Planner

Matches weekly forecast demand to inventory, inbound purchase orders, supplier capacity, lead times and
production constraints, then **finds, explains, prioritises and mitigates shortages**. Because real
supply-chain data is confidential, the project also contains a **reproducible synthetic data generator**
that builds a realistic world with **labelled edge cases**, so the planner can be measured against a
known ground truth.

```
generate (fixed seed) ──> input/*.csv ──> planner ──> derived/*.csv ──> validate + evaluate ──> reports/
                     └──> ground_truth/*.csv (kept separate, never read by the planner)
```

| what you get | where |
|---|---|
| 16 input tables (SKU, location, forecast, inventory, suppliers, lead times, capacity, BOM, production, POs, PO events...) | `output/<scale>/input/` |
| Planner output: inbound decisions, projected balance, shortages, mitigation options, exceptions | `output/<scale>/derived/` |
| Ground truth labels for anomalies and scenarios | `output/<scale>/ground_truth/` |
| Same data as JSON and as a SQL seed (SQLite / PostgreSQL) | `output/<scale>/json/`, `output/<scale>/sql/` |
| Validation summary (235 checks) and evaluation report | `output/<scale>/reports/` |
| Manifest: command, seed, versions, provenance, row counts, SHA-256 of every file | `output/<scale>/manifest.json` |

A ready-made **starter dataset** (300 SKUs, 10 locations, 52 weeks, 50 suppliers, 1,000 POs) is committed
in `output/starter/` so you can look at results without running anything.

---

## 1. Requirements

* Python **3.10 or newer** (tested with 3.13) - check with `python --version`
* Git (only to clone / publish)
* ~400 MB free disk space for the full-scale run with JSON + SQL export (starter needs ~40 MB)

Dependencies are only `numpy`, `pandas` and `pytest`.

## 2. Install (about 1 minute)

```bash
git clone https://github.com/<your-user>/supply-shortage-planner.git
cd supply-shortage-planner

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -e ".[test]"
```

`pip install -e .` installs the `ssp` package from `src/` and a `ssp` command.

## 3. Run

```bash
# starter dataset (~10 s)
python -m ssp run --scale starter

# full brief volume: 3,000 SKUs, 50 locations, 52 weeks, 500 suppliers, 10,000 inbound orders (~80 s)
python -m ssp run --scale full

# custom scale - same generator, any size
python -m ssp run --scale starter --skus 800 --locations 20 --suppliers 120 --orders 2500 --out output/custom

# a different seed
python -m ssp run --scale starter --seed 12345 --out output/seed12345

# CSV only (skip JSON / SQL export, faster)
python -m ssp run --scale full --formats csv
```

Every run prints the five stages and ends with e.g.
`validation PASS (235 checks, 0 failed); anomaly detection P/R/F1 = {'precision': 1.0, 'recall': 1.0, 'f1': 1.0}`.
The exit code is non-zero if any validation check fails.

## 4. Verify

```bash
pytest                                   # 29 tests, ~10 s
python -m ssp reproduce --scale starter  # Step 10: generate twice, compare row counts + SHA-256
python -m ssp docs                       # regenerate docs/data_dictionary.md from the schema
```

`reproduce` writes `output/reproducibility_starter/reproducibility.md`. A copy of the result is in
[docs/reproducibility.md](docs/reproducibility.md).

To query the data with SQL (loads `sql/schema.sql` + `sql/seed.sql` into an in-memory SQLite database,
no extra tool needed):

```bash
python -m ssp query "SELECT shortage_id, sku_id, location_id, need_date, shortage_qty, primary_cause FROM shortage ORDER BY priority_rank LIMIT 10"
```

## 5. How to read the results

1. **`derived/shortage.csv`** - one row per shortage episode, sorted by urgency (`SHORT-2026-000001` is
   the top priority). `primary_cause` + `cause_evidence` say *why* with the record IDs behind it, e.g.
   `TRANSPORT_DELAY: PO-2026-000030 ETA 2025-12-29->2026-01-21 (CARRIER_DELAY)`.
2. **`derived/mitigation_option.csv`** - candidate fixes per shortage (`MIT-<shortage>-01..`), each with
   quantity, arrival date, days late, incremental cost, on-time coverage %, feasibility, policy status, score
   and whether it is recommended. Rejected options stay visible with the reason.
3. **`derived/projected_balance.csv`** - the week-by-week arithmetic
   (`closing = opening + PO receipts + production - forecast - dependent demand`).
4. **`derived/inbound_effective.csv`** - what the planner did with every PO line
   (INCLUDED / EXCLUDED_DUPLICATE / EXCLUDED_UOM_MISMATCH / ... plus DELAYED, REDATED_LEAD_TIME, SCALED_CAPACITY).
5. **`derived/exception_log.csv`** - all exceptions with rule ID and decision.
6. **`reports/evaluation.md`** - planner vs ground truth, KPIs, cost-vs-service table.

## 6. Results (seed 20261022)

| metric | starter | full |
|---|---|---|
| SKU-locations / forecast rows | 565 / 27,820 | 5,941 / 285,168 |
| PO headers / lines (incl. labelled duplicates) | 1,008 / 2,312 | 10,040 / 23,408 |
| validation checks passed | 235 / 235 | 235 / 235 |
| anomaly detection precision / recall (5 types) | 1.0 / 1.0 | 1.0 / 1.0 |
| shortage episodes (P1 / P2 / P3) | 337 (34 / 101 / 202) | 3,044 (305 / 913 / 1,826) |
| shortage units covered on time by recommendations | 83.5% | 83.6% |
| shortages escalated (cannot be fixed by need date) | 80 | 566 |
| recommended options violating policy | 0 | 0 |

See `output/starter/reports/evaluation.md` for the full report, including where the planner is weaker
(e.g. low precision of the DEMAND_SPIKE cause because natural noise also produces spikes).

## 7. Edge cases (labelled in ground truth, all detected)

| edge case | how it is injected | planner decision |
|---|---|---|
| Inbound counted twice | copy of a PO with a new PO number but the same supplier confirmation `supplier_ref` | `EXCLUDE_DUPLICATE` |
| Substitute not approved | PO line buys substitute SKU B for SKU A while the A->B pair is PENDING/REJECTED | `EXCLUDE_FROM_SUPPLY`; unapproved substitutes are also rejected as mitigation options |
| Supplier capacity exceeded | supplier-week capacity set to 55-85% of its scheduled load | `CONSTRAIN_RECEIPTS_TO_CAPACITY` (pro-rata) |
| Shortage calculated without lead time | receipt date only 1-N days after order date, less than the supplier lead time | `REDATE_RECEIPT_TO_LEAD_TIME` |
| Units of measure mismatch | line UoM not convertible to the SKU base UoM (EA item in KG, KG item in EA) | `QUARANTINE_LINE` |

Normal scenarios also generated: demand spikes, constrained suppliers, suppliers on hold, substitute
SKUs, transport and supplier delays, cancellations, low opening stock, under-replenishment, production
constraints, lead-time version changes.

## 8. Repository layout

```
src/ssp/
  config.py      scales, seed, calendar            ids.py       ID conventions
  schema.py      every table: fields/types/keys    io.py        typed CSV read/write
  generator.py   synthetic data + anomalies + GT   engine.py    planner
  validate.py    Step 8 checks                     evaluate.py  metrics vs ground truth
  export.py      JSON / SQL / manifest             pipeline.py  orchestration + reproduce
  docs.py        data dictionary generator         __main__.py  CLI
tests/           29 pytest tests
docs/            data dictionary, ERD, design decisions, traceability, reproducibility, AI usage
prompts/         prompt history (LLM use disclosure)
output/starter/  committed starter dataset + reports
```

## 9. Documentation

* [docs/BEGINNER_GUIDE.md](docs/BEGINNER_GUIDE.md) - step-by-step: run, publish, and how each part was built
* [docs/design_decisions.md](docs/design_decisions.md) - problem, assumptions, rules, trade-offs, limitations, next steps
* [docs/requirements_traceability.md](docs/requirements_traceability.md) - every requirement of the brief -> code -> evidence
* [docs/data_dictionary.md](docs/data_dictionary.md) - every field: type, required, allowed values, unit, uniqueness, rule
* [docs/erd.md](docs/erd.md) - entity-relationship diagram, cardinalities, lifecycles
* [docs/reproducibility.md](docs/reproducibility.md) - same-seed checksum comparison
* [docs/AI_USAGE.md](docs/AI_USAGE.md) and [prompts/prompt_history.md](prompts/prompt_history.md) - how AI was used

## 10. Data provenance

All data is synthetic and generated by this code from a fixed seed. No external datasets, personal
data or credentials are used. Week IDs follow the public ISO 8601 week-date standard. Provenance and
checksums are recorded in every `manifest.json`.

## License

MIT
