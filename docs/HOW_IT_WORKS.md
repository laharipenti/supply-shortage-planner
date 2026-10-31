# How it works - plain-language study sheet

Read this once, then open the code at each "find" hint (Ctrl+F in Notepad or VS Code) and look at it.
When you can say each **bold one-liner** in your own words, you understand the project.

---

## Part 1 - The planner (`src/ssp/engine.py`)

The planner reads only the `input/` CSV files and answers four questions: *how much stock will I have
each week, where will I run out, why, and what can I do about it?*

### 1. Clean the incoming orders - find `def prepare_inbound`
For every purchase-order line it decides **"do I count this delivery, and when will it really arrive?"**

| situation in the data | what the planner does |
|---|---|
| order was cancelled (last event = CANCELLED) | ignore it |
| two orders have the same `supplier_ref` (same supplier confirmation number) | count it **once** (edge case: inbound counted twice) |
| unit doesn't fit the item (e.g. an "EA" item ordered in "KG") | put the line aside (edge case: UoM mismatch) |
| it buys a substitute item whose pair is not APPROVED | don't count it (edge case: substitute not approved) |
| promised arrival is earlier than order date + supplier lead time | move it to the earliest realistic date (edge case: shortage calculated without lead time) |
| carrier/supplier sent a DELAYED event | use the new date (`revised_eta`) |

Cases are converted to units: `CS` x units_per_case = `EA`.

### 2. Check supplier capacity - find `def _capacity`
**Adds up how much each supplier must deliver each week; if it is more than the supplier can make, every
delivery that week is cut by the same percentage** (edge case: supplier capacity exceeded).

### 3. Components needed for production - find `def _component_requirements`
**Planned production x bill of materials = how many components each plant needs each week.**

### 4. The stock projection - find `closing = np.round`
**closing stock = opening stock + deliveries + production - forecast - components used.**
Next week's opening = this week's closing. Negative = units owed to customers (backlog).
You traced this yourself: 60 -> -42 -> -149 -> -202 -> 333.

### 5. Find and explain shortages - find `def _shortages` and `def _explain`
**A shortage is a run of weeks where the projected stock is below zero; its size is the deepest point.**
To explain it, the planner measures how many units each problem took away (late delivery, capacity cut,
excluded line, demand spike, too little production) and names the biggest as `primary_cause`, with the
record IDs as evidence. If nothing specific applies: not enough opening stock / not enough ordered.

### 6. Rank shortages - find `priority_score`
**Priority = money at risk x importance (A=3, B=2, C=1) / how far away it is.**
Big, valuable, soon = top. `SHORT-2026-000001` is the most urgent.

### 7. Suggest fixes - find `def _mitigate`
For each shortage, most urgent first, it builds options:

| option | idea | key rule |
|---|---|---|
| TRANSFER | move spare stock from another location | only stock above that location's safety stock |
| SUBSTITUTE | use a similar item at the same location | only APPROVED substitutes |
| EXPEDITE_PO | pull an existing order in earlier | costs a premium |
| NEW_PO | order now | arrives only after the supplier lead time; MOQ; supplier must have spare capacity; not suppliers ON_HOLD |
| PRODUCTION_INCREASE | make more at the plant | plant spare capacity + enough components |

**Each option gets a score: rewarded for arriving on time, penalised for cost and lateness. The best ones
are recommended until the shortage is covered, and the capacity they use is reserved so the next shortage
cannot use it twice.** Anything that cannot be covered in time is ESCALATED to the operations manager.

---

## Part 2 - The data generator (`src/ssp/generator.py`)

**It builds a fake but realistic company from one random seed (20261022), so the same seed always gives
the same data.** Order: locations -> suppliers -> SKUs -> where each SKU is stocked -> suppliers per SKU ->
lead times -> weekly demand -> production -> purchase orders and their events -> edge cases -> capacity.

### The 5 edge cases - find `def _inject_`

| function | what it breaks on purpose | label written to ground truth |
|---|---|---|
| `_inject_duplicates` | copies a PO under a new number, same `supplier_ref` | INBOUND_COUNTED_TWICE -> EXCLUDE_DUPLICATE |
| `_inject_unapproved_substitutes` | changes a line to buy a substitute whose pair is PENDING/REJECTED | SUBSTITUTE_NOT_APPROVED -> EXCLUDE_FROM_SUPPLY |
| `_inject_capacity` | lowers one supplier-week's capacity below its load | SUPPLIER_CAPACITY_EXCEEDED -> CONSTRAIN_RECEIPTS_TO_CAPACITY |
| `_inject_lead_time` | moves the order date to 1-few days before arrival, ignoring lead time | SHORTAGE_WITHOUT_LEAD_TIME -> REDATE_RECEIPT_TO_LEAD_TIME |
| `_inject_uom` | gives a line the wrong unit (EA item in KG) | UOM_MISMATCH -> QUARANTINE_LINE |

**Every broken record is written to `ground_truth.csv` with the expected decision. The planner never reads
that file; the evaluator compares the planner's exceptions with it - 100% found, 0 false alarms.**

---

## Part 3 - Likely interview questions (practise answering out loud)

1. *What does your project do?* - Generates a realistic supply-chain dataset with known problems, then
   plans stock week by week, finds shortages, explains them and recommends fixes within policy and capacity.
2. *How do you know it works?* - 235 automatic checks, 29 tests, planner results compared with the ground
   truth, and the same seed produces identical files (I checked this on my own laptop).
3. *How do you stop the planner from cheating with the labels?* - It only reads `input/`; a test runs it on a
   copy without the ground truth and gets the same answer.
4. *Why is anomaly detection 100%?* - The problems are injected by rules and found by rules, so 100% is
   expected. The value is that every problem leads to a visible, traceable decision and nothing else is flagged.
5. *What is weak?* - The fix selection is greedy (not globally optimal); demand-spike explanations also fire on
   natural noise; one-level BOM; forecast is treated as exact.
6. *Where did you use AI?* - Claude wrote the code and docs; I installed, ran and verified everything on my
   laptop, traced a shortage by hand, and published the repo. Details in `docs/AI_USAGE.md`.
