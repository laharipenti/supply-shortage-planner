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

## Prompts 2-18 - Claude (claude.ai), 2026-10-31 (setup and publishing help)

Text exactly as I typed it. Where I sent a photo of my screen, it is described in [brackets].

**Prompt 2 (12:15)**
```text
Can I install the latest version of python ?
```

**Prompt 3 (12:17)**
```text
Can you give me the link to install python 3.13 version or 3.14
```

**Prompt 4 (12:44)** [photo: MSYS2 UCRT64 terminal open in my home folder]
```text
Create an empty public GitHub repo, then run git remote add origin <url> and git push -u origin main.
```

**Prompt 5 (12:45)** [photo: File Explorer showing the unzipped supply-shortage-planner folder]
```text
I unzipped the folder
```

**Prompt 6 (12:48)** [photo: terminal open inside the project folder, no command typed yet]
```text
(no text)
```

**Prompt 7 (12:49)**
```text
It's empty i don't see any thing whixh represents anything
```

**Prompt 8 (12:50)** [photo: output of `git log --oneline` (8 commits) and `git status` (manifest.json modified)]
```text
(no text)
```

**Prompt 9 (12:52)** [photo: `git add -A` and `git commit` succeeded]
```text
(no text)
```

**Prompt 10 (13:08)** [photo: "Authorize Git Credential Manager" page for my GitHub account]
```text
(no text)
```

**Prompt 11 (13:09)**
```text
Laharipenti is my account
```

**Prompt 12 (13:10)** [photo: `git push -u origin main` succeeded]
```text
(no text)
```

**Prompt 13 (13:20)** [photo: GitHub repo page showing commits authored by "madhukarmamidala"]
```text
Why is madhurmamidala here  it's laharipenti account right
```

**Prompt 14 (13:20)**
```text
No
It needs to have laharipenti there it should not be madhukarmamidala
```

**Prompt 15 (13:26)** [photo: GitHub Settings -> Emails page]
```text
(no text)
```

**Prompt 16 (13:28)** [photo: `git config user.name "Lahari Penti"` in Command Prompt]
```text
(no text)
```

**Prompt 17 (13:31)** [photo: `git log` showing all commits now authored by Lahari Penti]
```text
(no text)
```

**Prompt 18 (13:35)** (I pasted Claude's checklist of remaining steps and asked)
```text
Tell me about this what I need to do everything I updated will be according to you
```

---

## Prompts 19-36 - Claude (claude.ai), 2026-10-31 (running and verifying on my laptop)

**Prompt 19 (13:54)** [photo: commit + push of AI_USAGE.md and prompt history succeeded] - no text
**Prompt 20 (13:56)** [photo: `python -m ssp run --scale full` failed with "No module named ssp"] - no text
**Prompt 21 (13:59)** [photo: `pip install -e ".[test]"` succeeded] - no text
**Prompt 22 (13:59)** [photo: `pytest` - 29 passed] - no text
**Prompt 23 (14:05)** [photo: full-scale and starter runs, both validation PASS] - no text
**Prompt 24 (14:06)** [photo: `python -m ssp reproduce --scale starter` - reproducible=True] - no text
**Prompt 25 (14:08)** [photo: `git status` listing many modified files under output/starter] - no text
**Prompt 26 (14:14)** [photo: `git diff --ignore-cr-at-eol --stat` showing only line-ending warnings] - no text
**Prompt 27 (14:16)** [photo: `git restore output`, working tree clean] - no text

**Prompt 28 (14:17)**
```text
Any notepad file not opened
```

**Prompt 29 (14:24)** [photo: commit + push of the verification ticks] - no text

**Prompt 30 (14:26)**
```text
I didn't find any reproduce line
```

**Prompt 31 (14:27)** [photo: AI_USAGE.md open in Notepad with search for "reproduce"]
```text
Whixh line should I delete what steps shpuld I do next
```

**Prompt 32 (14:30)** [photo: commit + push removing the duplicate line] - no text

**Prompt 33 (14:40)**
```text
Should I paste this I'm cmd
python -m ssp query "SELECT week_id, opening_qty, receipts_po_qty, forecast_qty, closing_qty FROM projected_balance WHERE sku_id='SKU-000205' AND location_id='LOC-0010' AND week_id<='2026W05'"
```

**Prompt 34 (14:41)** [photo: projected balance query result]
```text
I got this

Next what to do
```

**Prompt 35 (14:43)** [photo: po_event query result for PO-2026-000030]
```text
Next what to do
```

**Prompt 36 (14:55)**
```text
No you please tell I don't know how to do
What to tick and explain what shpuld I do next for this assessment
```

---

## Prompt 37 onwards - _tool, date_

```text
(add every further prompt here)
```
