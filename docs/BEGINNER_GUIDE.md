# Beginner guide: how this project is built, step by step

Read this top to bottom once. It follows the order in which the solution was built, so each step only
uses what earlier steps created. For every step: **what** it does, **which file**, and **what to look at**.

---

## Part A - Get it running (30 minutes)

1. **Install Python 3.10+** from python.org (Windows: tick "Add Python to PATH"). Check: `python --version`.
2. **Install Git** from git-scm.com. Check: `git --version`.
3. **Unzip the project** and open a terminal in the `supply-shortage-planner` folder.
4. **Create a virtual environment** (an isolated place for the libraries):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # macOS / Linux
   ```
5. **Install**: `pip install -e ".[test]"`
6. **Run the tests**: `pytest` -> expect `29 passed`.
7. **Run the starter dataset**: `python -m ssp run --scale starter` -> expect `validation PASS`.
8. **Run the full dataset**: `python -m ssp run --scale full` (about 1-2 minutes).
9. **Prove reproducibility**: `python -m ssp reproduce --scale starter` -> `reproducible=True`.

## Part B - Publish to a public GitHub repository

1. On github.com: **New repository** -> name `supply-shortage-planner` -> **Public** -> do *not* add a README
   (we already have one) -> Create.
2. In the project folder (the zip already contains a git history with meaningful commits):
   ```bash
   git remote add origin https://github.com/<your-user>/supply-shortage-planner.git
   git branch -M main
   git push -u origin main
   ```
   GitHub will ask you to log in (use a personal access token or GitHub Desktop if a password is refused).
3. From now on, every change you make: `git add -A`, `git commit -m "what you changed and why"`, `git push`.
   Small, honest commits ("Add test for X", "Fix Y because Z") show the reviewers how your work evolved.
4. Before the deadline: fill in `docs/AI_USAGE.md` (what *you* reviewed) and add every further prompt to
   `prompts/prompt_history.md`. Send the repo link from the email you used during recruitment.

---

## Part C - How it was built (Steps 1-10 of the brief)

### Step 0 - Configuration and IDs (`config.py`, `ids.py`)
* `SCALES` holds `tiny` (tests), `starter` (committed), `full` (the brief's volume). Same code for all.
* `AS_OF = 2025-12-29`: Monday of ISO week 2026W01. Everything before is history, after is plan.
* `ids.py` builds every ID with zero padding: `SKU-000001`, `PO-2026-000001`, `DEM-<sku>-<loc>-2026W01`...
  **Look at:** how `demand_id` simply joins the parent IDs - that is what "IDs consistent across files" means.

### Step 1 - Data dictionary (`schema.py` -> `docs/data_dictionary.md`)
* One `Table(...)` per entity: fields with type, required, allowed values, unit, uniqueness, rule, plus PK,
  FKs, cardinality and lifecycle.
* The same definitions are used to load CSVs, validate, create SQL tables and write the dictionary - so
  documentation can never disagree with code. **Try:** `python -m ssp docs`.

### Step 2 - Parents first, then children (`generator.py`, method `run()`)
Read `run()` - it is the table of contents:
`_locations -> _suppliers -> _skus -> _sku_locations_and_bom -> _substitutes -> _supplier_sku -> _lead_times
-> _demand -> _production -> _gross_safety_abc -> _purchase_orders -> _demand_spikes -> ... injections ...
-> _supplier_capacity -> _inject_capacity`.
A child is only created from IDs that already exist (e.g. PO lines pick SKUs from `sku_location`).

### Step 3 - Deterministic IDs
POs are sorted by (order date, supplier, location, receipt date) **before** numbering, so `PO-2026-000001`
is the earliest order and the numbering never depends on random dictionary order.

### Step 4 - Volume and realism
* Demand: `_demand` - log-normal SKU size x location factor x seasonality x Poisson-Gamma noise.
* Constrained suppliers: 10% get capacity only 0-6% above their peak load.
* Substitutes: `sku_substitute` bridge with APPROVED / PENDING / REJECTED.
* Transport delays: `_events` adds `DELAYED` events with a `revised_eta` for 15% of shipped/confirmed POs.
* Demand spikes: `_demand_spikes` multiplies 1-3 weeks by 2.5-5x **after** POs were planned.
* Seed: one `numpy.random.default_rng(seed)` used for everything -> same seed, same data.

### Step 5 - Baseline first, then labelled edge cases
`_inject_lead_time`, `_inject_unapproved_substitutes`, `_inject_uom`, `_inject_duplicates`,
`_inject_capacity`. Each one changes only the chosen record, marks the PO as "touched" so two anomalies
never land on the same PO, and calls `self.label(...)` with the `issue_type` and `expected_decision`.

### Step 6 - Derived values are calculated
Safety stock (from average demand), ABC class (from demand value), PO status (= latest event), dependent
demand (= production x BOM), supplier capacity (sized from the real PO load). Nothing derived is random.

### Step 7 - Ground truth kept separate
Labels go to `output/<scale>/ground_truth/`. The planner (`engine.py`) only reads `input/`.
`tests/test_no_leakage.py` copies `input/` alone to a new folder and shows the planner gives the same answer.

### The planner (`engine.py`) - read in this order
1. `prepare_inbound` - for each PO line: status from events, latest ETA, duplicate check (same
   `supplier_ref`), UoM conversion (CS x units_per_case), lead-time check, substitute approval, final `action`.
2. `_capacity` - supplier load per week vs capacity; over capacity -> scale receipts.
3. `_component_requirements` - BOM explosion.
4. `_projection` - the core formula, vectorised with numpy `cumsum`:
   `closing = opening + receipts + production - forecast - dependent_demand`.
5. `_shortages` / `_explain` - find runs of negative balance; measure each cause; keep evidence IDs.
6. `_mitigate` - priority score, then for each shortage (most urgent first) build options, check policy,
   score them, recommend greedily and **consume** capacity so it is not promised twice.

### Step 8 - Validation (`validate.py`)
235 checks grouped as: primary key, required, enums, ID format, ranges, foreign keys, duplicates, dates,
effective dates, lifecycle transitions, dependencies, quantities, reconciliation, explainability, policy,
capacity, ground truth. **Look at** `V-GT-03`: it re-detects each anomaly with an independent rule and
requires an exact match with the labels.

### Step 9 - Export (`export.py`)
CSV (source of truth) -> JSON (typed records) -> SQL (`schema.sql` with PK/FK + `seed.sql` inserts; ground
truth in its own `ground_truth.sql`) -> `manifest.json` (command, seed, versions, provenance, SHA-256).

### Step 10 - Reproducibility (`pipeline.reproduce`)
Runs everything twice with the same seed and once with seed+1, compares row counts and SHA-256 per file.

---

## Part D - Exercise: trace one shortage by hand (do this before the interview)

```bash
python -m ssp query "SELECT shortage_id, sku_id, location_id, first_short_week_id, shortage_qty, cause_evidence FROM shortage WHERE primary_cause='TRANSPORT_DELAY' LIMIT 1"
```
Then, with that SKU and location:
1. `projected_balance` - find the first week where `closing_qty < 0`; check the arithmetic of 2 rows.
2. `inbound_effective` - find the delayed PO line; compare `original_eta` and `effective_eta`.
3. `po_event` - find the `DELAYED` event and its `reason_code`, `actor`.
4. `mitigation_option` - which option was recommended, and why the others were not (`decision_reason`).

## Part E - Questions reviewers are likely to ask (prepare your own answers)

* Why one shortage per *episode* instead of per week? (actionable, A5 in design_decisions)
* Why backlog instead of lost sales? What would change with lost sales?
* How do you make sure the planner cannot see the labels?
* Why are precision/recall 1.0 - is that suspicious? (rules vs rules; value is traceability + no false positives)
* Why is DEMAND_SPIKE cause precision low, and how would you improve it?
* What is the weakness of greedy mitigation? How would an optimiser do better?
* How does the lead-time edge case hide a shortage if you do not catch it?
* How would this run on 10x the data? (vectorised projection; the Python loops are per shortage / PO)
