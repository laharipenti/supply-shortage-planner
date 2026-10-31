# Design decisions, assumptions and trade-offs

## 1. The problem in one paragraph

A planner has a weekly forecast for every SKU at every location, stock on hand, purchase orders on the
way, suppliers with limited capacity and lead times, and plants that turn components into finished
goods. The job is to work out **where and when stock will run out**, **why**, **which shortages matter
most**, and **what can be done about each one** (move stock, use a substitute, expedite, place a new
order, produce more), without breaking policy (unapproved substitutes, suppliers on hold) or physics
(lead times, capacity). Because real data is not available, the project also has to **generate a
realistic synthetic world** in which the right answers are known (ground truth), so the planner can be
measured.

## 2. Architecture

```
generator.py  ->  output/<scale>/input/*.csv          (what a planning system would receive)
              ->  output/<scale>/ground_truth/*.csv   (labels; never read by the planner)
engine.py     <-  input/ only
              ->  output/<scale>/derived/*.csv        (inbound decisions, projection, shortages, mitigations, exceptions)
validate.py   ->  reports/validation_summary.*        (Step 8, 235 checks)
evaluate.py   ->  reports/evaluation.*                (planner vs ground truth)
export.py     ->  json/, sql/, manifest.json          (Step 9)
pipeline.py   ->  orchestration + reproduce()         (Step 10)
schema.py     ->  one definition of every table used by loader, validator, SQL DDL and data dictionary
```

Why this split: the generator and the planner are **separate programs that only talk through CSV
files**. That proves (and a test enforces) that the planner cannot peek at the labels, and it mirrors a
real setup where a planning engine receives data from ERP extracts.

## 3. Key assumptions (made where the brief was open)

| # | assumption | why |
|---|---|---|
| A1 | Planning as-of date = Monday 2025-12-29 (start of ISO week 2026W01). Horizon = 52 weeks. | Brief uses `2026W01`; ISO weeks give unambiguous IDs. |
| A2 | Demand is generated for each **stocked SKU-location pair** (an assortment), not the full 3,000 x 50 cross product. Full scale = 5,941 pairs x 52 weeks = 285k forecast rows. | A 7.8M-row cross product where most SKUs are not sold at most DCs is unrealistic and slow. Each finished SKU is stocked at 1-4 DCs. |
| A3 | "10,000 inbound orders" = 10,000 PO **headers** (one supplier -> one location), each with 1+ lines. Labelled duplicate POs are added on top (10,040 at full scale). | Header/line split is how ERPs store POs and lets one delay affect several SKUs. |
| A4 | Unmet demand is **backlogged** (balance may go negative and carries forward). | Standard MRP projected-available-balance convention; makes the reconciliation exact. |
| A5 | A shortage = one **episode**: consecutive weeks with projected balance < 0 for one SKU-location. Shortage qty = peak deficit = units needed by the first short week. | One actionable record per problem instead of 52 noisy week rows. Safety-stock breaches are flagged on the projection (`below_safety_stock`) but are not shortages. |
| A6 | Supplier capacity is in "units/week" across SKUs (EA and KG both count 1). Load is counted in the week the goods arrive. | Keeps capacity one number per supplier-week; documented simplification. |
| A7 | Lead time is per supplier-SKU (not per destination) and effective-dated. The version effective on the **order date** is used to check a PO; the version effective **today** is used for new orders. | Shows effective-dating without exploding the table. |
| A8 | Manufactured SKUs are produced and sold at their plant. Components are only consumed through the BOM (dependent demand). | "BOM requirements where applicable" with one level of BOM. |
| A9 | Delays/cancellations are only known up to the as-of date: every event is dated <= 2025-12-29; future POs are `CREATED` firm planned orders. | Keeps history honest; nothing "from the future" is in the event log. |
| A10 | Names are placeholders (`Supplier 0001`, `Distribution Center West 03`). No external data. | Lawful provenance; no personal data. |

## 4. Business rules implemented (with the reason for each)

**Inbound normalisation (`inbound_effective`)** - every PO line gets exactly one action:

| rule | id | decision | why |
|---|---|---|---|
| PO's latest event is CANCELLED | - | EXCLUDED_CANCELLED | cancelled supply cannot arrive |
| same `supplier_ref` as a lower PO id | R-INB-01 | EXCLUDED_DUPLICATE | **inbound counted twice** |
| line UoM not convertible to SKU base UoM (EA<-EA/CS, KG<-KG) | R-UOM-01 | EXCLUDED_UOM_MISMATCH (quarantine) | **UoM mismatch**: quantity is meaningless until fixed |
| line buys a substitute whose pair is not APPROVED at order date | R-SUB-01 | EXCLUDED_UNAPPROVED_SUBSTITUTE | **substitute not approved** |
| expected receipt < order date + lead time | R-LT-01 | receipt re-dated to order date + lead time | **shortage calculated without lead time**: trusting the early date would hide a shortage |
| supplier-week load > capacity | R-CAP-01 | receipts that week scaled pro-rata to capacity | **supplier capacity exceeded** |
| DELAYED event | - | use latest `revised_eta` | transport / supplier delays |

**Projection**: `closing = opening + PO receipts + production - forecast - dependent demand`; week-1
opening = on-hand - on-hold; dependent demand = production plan x BOM qty x (1 + scrap).

**Root cause** (explainable): for each episode the engine measures how many units each mechanism took
away (capacity cut, delayed or re-dated receipts, excluded lines, forecast > 2.5 x local median, planned
production below requirement). The biggest one is the `primary_cause`; all are listed in
`contributing_causes` with record IDs in `cause_evidence`. If nothing specific applies the cause is
`INSUFFICIENT_OPENING_STOCK` (runs out before the first receipt) or `INSUFFICIENT_REPLENISHMENT`.

**Priority**: `value_at_risk x ABC weight (A=3, B=2, C=1) / (1 + weeks_until_need / 4)`. Bands: P1 = top
10%, P2 = next 30%, P3 = rest. Shortage IDs are numbered by rank so `SHORT-2026-000001` is the most urgent.

**Mitigation options** (generated per shortage, in priority order so the most urgent shortage gets
scarce capacity first):

| option | feasibility rule | cost model |
|---|---|---|
| TRANSFER | donor location surplus = min over horizon of (balance - safety stock); 7 days same region, 14 otherwise | 150 + 3% (6% cross-region) of value |
| SUBSTITUTE | approved pair, substitute stocked at same location with surplus; unapproved -> listed but `REJECTED_SUBSTITUTE_NOT_APPROVED` | cost difference + 1% handling |
| EXPEDITE_PO | open line due within 8 weeks after need date; in-transit -7 days, else -14 days but never earlier than transit time | supplier expedite premium (10-35%), 35% for in-transit |
| NEW_PO | arrival = today + current lead time; MOQ and order multiple; must fit supplier's **remaining** capacity that week; ON_HOLD supplier -> rejected | 250 order cost + price premium + holding cost of MOQ excess |
| PRODUCTION_INCREASE | outside 2-week frozen fence, plant headroom, enough component surplus for the BOM | 12% overtime premium |

Score = `100 x on-time coverage + 40 x late coverage x (1 - lateness) - 30 x cost index`. Up to three
eligible options are recommended greedily until the shortage is covered; each one **consumes** the
resource (donor surplus, supplier capacity, plant headroom, component stock) so later shortages cannot
double-book it. Anything not covered on time is escalated (`SHORTAGE_ESCALATED` exception, owner =
operations manager).

## 5. How the synthetic data is made realistic

* SKU volumes: log-normal (few fast movers, long tail) -> ABC classes derived from data.
* Weekly demand: Poisson-Gamma (over-dispersed counts) with category seasonality; PHASE_IN / PHASE_OUT ramps.
* Demand spikes (3% of SKU-locations, x2.5-5 for 1-3 weeks) are added **after** POs were planned, like a late promotion.
* Supplier weights are Pareto distributed (a few large suppliers); lead times depend on country (truck vs ocean).
* 10% constrained suppliers (capacity 100-106% of peak load), 3% suppliers on hold.
* PO receipts are spaced through the year; quantities sized from demand x replenishment ratio, rounded to MOQ / case.
* 12% under-replenished SKU-locations, 12% low opening stock, 15% of confirmed/in-transit POs delayed, 1.5% cancelled.
* Derived values (safety stock, ABC, PO status, dependent demand, balances, capacity utilisation) are **computed**, never drawn at random.
* Supplier capacity is sized from the PO load using the planner's own normalisation function, so the
  **only** capacity breaches are the labelled ones (validated by `V-GT-03`).

## 6. How I know it works

1. **235 validation checks** (PK/FK, enums, ID formats, date order, effective-date overlap, lifecycle
   transitions, week-by-week reconciliation, BOM explosion, UoM conversion, shortage episodes, mitigation
   policy/capacity, ground-truth separation) - all PASS on tiny, starter and full scale.
2. **Independent re-detection**: the validator re-finds each anomaly type with its own simple rule and
   requires the set to equal the labelled set (no unlabelled anomalies, no fake labels).
3. **Evaluation vs ground truth**: anomaly detection precision/recall/F1 = 1.0 for all five types with
   100% correct decisions; cause attribution recall per scenario.
4. **29 automated tests** including rule unit tests on hand-modified data (e.g. set capacity to 1 and the
   receipts must be scaled; make receipt = order date + 1 and it must be re-dated).
5. **Reproducibility**: generating twice with seed 20261022 gives byte-identical files (SHA-256); seed
   20261023 changes them.
6. **SQL seed loads into SQLite with `PRAGMA foreign_keys=ON`** and `foreign_key_check` is empty.

## 7. Trade-offs and known limitations (honest list)

* **Anomaly detection scores of 1.0 are expected, not impressive**: the anomalies are injected by rules
  and detected by matching rules. The value is that every edge case flows through to a visible, traceable
  decision, and that nothing *else* is flagged (no false positives on 10,000 POs).
* **Cause precision for DEMAND_SPIKE is low (~0.2)**: natural noise also produces weeks > 2.5 x local
  median. They are real spikes in the data, just not labelled ones. A stricter threshold would miss small
  injected spikes; I chose recall.
* Greedy single-pass mitigation is not a global optimum (an LP/MIP could allocate scarce supplier capacity
  better). It is transparent and fast (the planner runs in about 6 s at full scale; the whole pipeline incl. validation and export in about 80 s).
* Transfers do not re-run the donor's projection; the donor surplus rule (min over the whole horizon of
  balance - safety stock) is conservative to compensate.
* One-level BOM; no component substitution; no transport capacity; no shelf life; single currency.
* Supplier capacity mixes EA and KG as "units" (A6).
* Forecast = demand (no forecast error simulation); the planner plans against the forecast.

## 8. Next steps if I had more time

* Optimisation-based allocation (PuLP / OR-Tools) and comparison against the greedy baseline.
* Rolling re-plan: apply recommended mitigations as new events and re-project (closed loop).
* Forecast error and service-level-based safety stock.
* A small Streamlit dashboard over `derived/` for planners.
