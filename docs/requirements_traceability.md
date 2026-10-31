# Requirements traceability - every point of the brief, and where it is done

| # | requirement (from the problem statement) | where / how | evidence |
|---|---|---|---|
| 1 | Match forecast demand to inventory, supplier capacity, lead times and production constraints to prioritise shortages | `src/ssp/engine.py` (projection, shortages, priority, mitigations) | `derived/shortage.csv` sorted by `priority_rank` |
| 2 | Expose key decisions and exceptions | `inbound_effective.action/adjustments`, `exception_log`, `mitigation_option.decision_reason`, `is_recommended` | `derived/exception_log.csv` |
| 3 | Preserve traceability | every derived row carries source IDs: `exception_ids`, `cause_evidence` (PO / line / capacity IDs), `source_ref`, `production_plan_id` | `derived/*.csv` |
| 4 | Measurable outputs / meaningful evaluation metrics | `src/ssp/evaluate.py` | `reports/evaluation.md` |
| 5 | Multiple related entities, conditional rules, >=1 exception path | 16 input + 8 derived tables; rules R-INB/UOM/SUB/LT/CAP/MIT; escalation path | `docs/erd.md` |
| 6 | Actors: supplier, planner, carrier/warehouse, logistics analyst, ops manager | `po_event.actor` (PLANNER / SUPPLIER / CARRIER); delays by carrier; escalations to ops manager (`ESCALATE_TO_OPS_MANAGER`) | `input/po_event.csv` |
| 7 | Workflow 1: master data first (SKU, Location, ForecastDemand, Inventory, Supplier) | `generator.py` `run()` order | code |
| 8 | Workflow 2: dependent records use valid parent IDs | FK checks `V-FK`, `V-REF-*`; SQL loads with FK enforcement | `reports/validation_summary.md`, `tests/test_sql_export.py` |
| 9 | Workflow 3: demand by week; on-hand and inbound; supplier capacity, MOQ, lead times; production capacity + BOM; projected balance; shortages + candidate mitigations | `_demand`, `_purchase_orders`, `_supplier_sku` (MOQ), `_lead_times`, `_production`, `bom`; engine `_projection`, `_shortages`, `_mitigate` | input + derived CSVs |
| 10 | Workflow 4: state changes as explicit events; do not overwrite history | `po_event` (append-only, `expected_receipt_date` never changed), `shortage_event`; statuses derived from latest event | `V-LIFE-01..05`, `test_po_history_is_append_only` |
| 11 | Workflow 5: outcomes/labels from documented rules, not random | every label written at the moment the rule creates the situation; derived values computed | `generator.py` `label()` calls |
| 12 | Entities: SKU, Location, ForecastDemand, Inventory, Supplier, SupplierCapacity, LeadTime, PurchaseOrder, ProductionPlan, Shortage, MitigationOption | tables `sku, location, forecast_demand, inventory, supplier, supplier_capacity, lead_time, purchase_order(+_line), production_plan, shortage, mitigation_option` | `docs/data_dictionary.md` |
| 13 | PK for every entity, FK for every relationship | `schema.py` `pk` / `fks`; SQL DDL | `sql/schema.sql` |
| 14 | Cardinality, optional relationships, effective dates, lifecycle states | `docs/erd.md`; `effective_from/to` on lead_time, sku_substitute, bom; lifecycle diagrams | `docs/erd.md` |
| 15 | Bridge tables for N:M | `sku_location`, `supplier_sku`, `sku_substitute`, `bom` | |
| 16 | Retain event history; validate all joins | `po_event`, `shortage_event`; FK + composite FK checks | `V-FK`, `V-REF-06/07` |
| 17 | Anomalies keep an issue_type/ground_truth label; don't corrupt unrelated rows | `ground_truth.csv` with `issue_type`, `record_id`, `expected_decision`; injection touches only the labelled record, and touched POs are excluded from further injections | `V-GT-02`, `V-GT-03` |
| 18 | IDs: SKU-000001; DEM-<sku>-<location>-2026W01; PO-2026-000001; SHORT-2026-000001; MIT-<shortage-id>-01 | `src/ssp/ids.py` | `test_id_conventions` |
| S1 | Data dictionary: type, required, allowed values, units, uniqueness, validation rule | generated from `schema.py` | `docs/data_dictionary.md` |
| S2 | Parent tables first, then child/event tables, with the domain generation logic | `generator.py` | |
| S3 | Deterministic, zero-padded, immutable IDs consistent across files | `ids.py`; PO numbering sorted by order date | `V-ID`, `V-FK` |
| S4 | 3,000 SKUs, 50 locations, 52 weeks, 500 suppliers, 10,000 inbound orders; spikes, constrained suppliers, substitutes, transport delays; fixed seed 20261022; parameterised scale | `config.py` SCALES (`tiny`, `starter`, `full`) + CLI overrides `--skus --locations --weeks --suppliers --orders` | `output/starter/manifest.json`; `test_scale_is_parameterised` |
| S5 | Valid baseline first, then labelled edge cases: inbound counted twice; substitute not approved; capacity exceeded; shortage without lead time; UoM mismatch | `_inject_*` methods run after baseline generation | `reports/evaluation.md` section 1 |
| S6 | Derived values calculated from source records | safety stock, ABC, PO status, dependent demand, balances, utilisation, priority, cost | `V-ARITH-01..14` |
| S7 | Separate ground_truth.csv/json, never leaked into features | `output/<scale>/ground_truth/`; engine reads `input/` only | `tests/test_no_leakage.py`, `V-GT-01` |
| S8 | Validation: PK uniqueness, FK integrity, enums, date ordering, arithmetic reconciliation, lifecycle transitions, duplicate checks | `src/ssp/validate.py` (235 checks) | `reports/validation_summary.md` |
| S9 | Export CSV / JSON / SQL seed + README, schema/data dictionary, generator command, fixed seed, source manifest, validation summary | `export.py`, `manifest.json` (command, seed, versions, provenance, checksums) | `output/starter/` |
| S10 | Regenerate twice with same seed, compare row counts / checksums | `python -m ssp reproduce` | `docs/reproducibility.md` |
| AC1 | Projected balance reconciles week by week | `V-ARITH-01..07` | `test_projection_reconciles_week_by_week` |
| AC2 | Shortages have explainable causes | `primary_cause`, `contributing_causes`, `cause_evidence` | `V-SHORT-01`, evaluation section 2 |
| AC3 | Mitigation respects policy / capacity | policy_status, capacity consumption | `V-MIT-01..07`, `tests/test_mitigation_policy.py` |
| AC4 | Alternatives show cost and service trade-offs | `incremental_cost`, `cost_per_unit`, `service_coverage_pct`, `days_late`, `feasibility`, `score` per option | evaluation trade-off table |
| E-a..g | Realistic distributions; consistent IDs; lifecycle consistency; correct derived values; normal/boundary/failure/exception coverage; separate ground truth; reproducibility, docs, provenance | see `docs/design_decisions.md` section 5 and the checks above. Boundary cases: constrained suppliers at 100% utilisation (not exceeded), lead-time version changes, MOQ rounding, zero-demand components, PHASE_IN/PHASE_OUT | |
| L | Lawful public data use | no external data used; provenance recorded in `manifest.json` | `manifest.json -> provenance` |
| Sub-1 | Public GitHub repo, meaningful commits | see README "Publish to GitHub" | git history |
| Sub-2 | README explaining how to run | `README.md` | |
| Sub-3 | Tests | `tests/` (29 tests, `pytest`) | |
| Sub-4 | Prompt history + AI usage disclosure | `prompts/prompt_history.md`, `docs/AI_USAGE.md` | |
| Sub-5 | Reasoning visible: assumptions, decisions, trade-offs, testing, limitations | `docs/design_decisions.md` | |
