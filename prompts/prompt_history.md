# Prompt history

All prompts submitted to AI tools for this project, in order. AI responses are not included (optional
per the FAQ). Add every further prompt you send (to any tool) below, with the date.

---

## Prompt 1 - Claude (claude.ai), 2026-10-31

Attachments: `YottaFlex_AI_Candidate_Project_Submission_Guidelines.pdf`, `YottaFlex_AI_Candidate_Project-FAQ.pdf`

```text
Business Context / Problem
Match forecast demand to inventory, supplier capacity, lead times and production
constraints to prioritize shortages.
Objective and Scope
Build a working solution for this end-to-end workflow: Match forecast demand to inventory,
supplier capacity, lead times and production constraints to prioritize shortages. The
solution should expose key decisions and exceptions, preserve traceability, and produce
measurable outputs. Medium complexity means multiple related entities, conditional rules,
at least one exception path and meaningful evaluation metrics.
Primary Actors / Systems
Supplier, planner, carrier/warehouse operator, logistics analyst and operations manager
Business Workflow and Rules
1. Generate/reference master data first: SKU, Location, ForecastDemand, Inventory,
Supplier.
2. Generate dependent transaction/event records using valid parent IDs.
3. Apply business logic: Create SKU-location demand by week; seed on-hand and inbound inventory; define supplier capacity, minimum quantities and lead times; create production
capacity and BOM requirements where applicable; calculate projected available balance;
generate shortages and candidate mitigations.
4. Persist state changes as explicit records/events where relevant; do not overwrite
history.
5. Generate outcomes and ground-truth labels from documented rules, not independent
random assignment
Entities and Relationships
Core entities: SKU, Location, ForecastDemand, Inventory, Supplier, SupplierCapacity,
LeadTime, PurchaseOrder, ProductionPlan, Shortage, MitigationOption. Define a primary
key for every entity and foreign keys for every relationship. Document cardinality (1:1, 1:N,
N:M), optional relationships, effective dates and lifecycle states. Use bridge tables for
many-to-many relationships; retain event history for state changes; validate alljoins. For
deliberate anomaly cases, keep an issue_type/ground_truth label rather than silently
corrupting unrelated rows
ID/ Nomenclature Conventions
SKU-000001; DEM-<sku>-<location>-2026W01; PO-2026-000001; SHORT-2026-000001;
MIT-<shortage-id>-01.

Synthetic Data Generation Instructions (Granular)
Step 1 - Write a data dictionary for: SKU, Location, ForecastDemand, Inventory, Supplier,
SupplierCapacity, LeadTime, PurchaseOrder, ProductionPlan, Shortage, MitigationOption
For each field specify type, required/optional, allowed values, units, uniqueness and
validation rule
Step 2- Create parent/master tables first, then child and event tables. Apply this domain-
specific generation logic: Create SKU-location demand by week; seed on-hand and inbound
inventory; define supplier capacity, minimum quantities and lead times; create production
capacity and BOM requirements where applicable; calculate projected available balance;
generate shortages and candidate mitigations
Step 3-- Apply deterministic IDs and naming: SKU-000001; DEM-<sku>-
<location>-2026W01; PO-2026-000001; SHORT-2026-000001; MIT-<shortage-id>-01. Keep
counters zero-padded, IDs immutable, and referenced IDs exactly consistent across files.
Step 4- Generate the baseline volume: Generate 3,000 SKUs, 50 locations, 52 weeks of
demand, 500 suppliers and 10,000 inbound orders. Include demand spikes, constrained
suppliers, substitute SKUs and transport delays. Use a fixed seed (e.g. 20261022) and
parameterize scale so starter and full datasets use the same generator.
Step 5 - Generate valid baseline records first, then inject labelled edge cases: Inbound
counted twice; substitute not approved; supplier capacity exceeded; shortage calculated
without lead time; units of measure mismatch
Step 6 - Calculate derived values (totals, balances, scores, statuses and dates) from
source records rather than generating them independently.
Step 7- Produce a separate ground_truth.csv/json for known anomalies, expected
decisions or labels; never leak it into input features.
Step 8- Run validation: primary-key uniqueness, foreign-key integrity, allowed enums,
date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks
Step 9- Export CSV/JSON/SQL seed data plus README, schema/data dictionary,
generator command, fixed seed, source manifest and validation summary.
Step 10- Regenerate twice with the same seed and compare row counts/checksums to
demonstrate reproducibility
Suggested Volume and Coverage
Generate 3,000 SKUs, 50 locations, 52 weeks of demand, 500 suppliers and 10,000
inbound orders. Include demand spikes, constrained suppliers, substitute SKUs and
transport delays
Required Edge Cases / Negative Scenarios
Inbound counted twice; substitute not approved; supplier capacity exceeded; shortage
calculated without lead time; units of measure mismatch
Validation Rules / Acceptance Criteria
Projected balance reconciles week by week; shortages have explainable causes; mitigation respects policy/capacity; alternatives show cost and service tradeoffs.
Evaluation Focus for Generated Data
Review: (a) realistic distributions and meaningful variation; (b) consistent IDs and valid
joins; (c) dependency/lifecycle consistency across entities; (d) correct derived values and
reconciliation; (e) normal, boundary, failure and exception coverage; (f) separate ground
truth; (g) fixed-seed reproducibility, documentation and lawful provenance.
Public Data Guidance / Lawful Use
External data is optional. If used, record source URL, dataset/version, retrieval date,
license/terms, attribution, transformations and fields discarded. Use only data you are
legally permitted to access and redistribute; do not bypass access controls or collect
confidential/personal information. If licensing or suitability is unclear, use synthetic data
and cite public reference data only for schema inspiration.

Before you submit make sure you have
Pushed your code to a Publix github repository
Added a Readme explainaninh how to run it
Included any tests the problem asks for
Candidate FAQ
Submission guidelines
Where attached

This is the problem statement and I need to build it and help me in building it and please cover every point mentioned here
I need step by step process in building this as I am a begineer
```

---

## Prompt 2 - _tool, date_

```text
(paste your next prompt here)
```
