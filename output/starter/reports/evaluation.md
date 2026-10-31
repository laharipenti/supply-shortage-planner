# Evaluation report

## 1. Anomaly detection (planner exceptions vs ground_truth)

| issue type | labelled | detected | TP | FP | FN | precision | recall | F1 | decision accuracy |
|---|---|---|---|---|---|---|---|---|---|
| INBOUND_COUNTED_TWICE | 8 | 8 | 8 | 0 | 0 | 1.0 | 1.0 | 1.0 | 1.0 |
| SUBSTITUTE_NOT_APPROVED | 8 | 8 | 8 | 0 | 0 | 1.0 | 1.0 | 1.0 | 1.0 |
| SUPPLIER_CAPACITY_EXCEEDED | 8 | 8 | 8 | 0 | 0 | 1.0 | 1.0 | 1.0 | 1.0 |
| SHORTAGE_WITHOUT_LEAD_TIME | 8 | 8 | 8 | 0 | 0 | 1.0 | 1.0 | 1.0 | 1.0 |
| UOM_MISMATCH | 8 | 8 | 8 | 0 | 0 | 1.0 | 1.0 | 1.0 | 1.0 |

Micro average: precision 1.0, recall 1.0, F1 1.0

## 2. Cause attribution (did the planner explain labelled scenarios correctly?)

| scenario / anomaly | expected cause | labelled | led to shortage | cause identified | recall |
|---|---|---|---|---|---|
| DEMAND_SPIKE | DEMAND_SPIKE | 27 | 15 | 15 | 1.0 |
| TRANSPORT_DELAY | TRANSPORT_DELAY | 21 | 18 | 18 | 1.0 |
| SUPPLIER_DELAY | SUPPLIER_DELAY | 46 | 26 | 26 | 1.0 |
| PRODUCTION_CONSTRAINED | PRODUCTION_SHORTFALL | 5 | 5 | 5 | 1.0 |
| SUPPLIER_CAPACITY_EXCEEDED | SUPPLIER_CAPACITY | 16 | 6 | 6 | 1.0 |
| SHORTAGE_WITHOUT_LEAD_TIME | LEAD_TIME_CORRECTION | 14 | 6 | 6 | 1.0 |
| SUBSTITUTE_NOT_APPROVED | SUPPLY_EXCLUDED | 8 | 7 | 7 | 1.0 |
| UOM_MISMATCH | SUPPLY_EXCLUDED | 8 | 6 | 6 | 1.0 |
| PO_CANCELLED | SUPPLY_EXCLUDED | 23 | 15 | 15 | 1.0 |
| UNDER_REPLENISHED | INSUFFICIENT_REPLENISHMENT | 62 | 47 | 41 | 0.8723 |
| LOW_OPENING_STOCK | INSUFFICIENT_OPENING_STOCK | 64 | 64 | 51 | 0.7969 |

Cause precision (shortages naming a cause that is backed by a ground-truth label; unlabelled causes are real data effects such as seasonal peaks, cancelled POs or natural noise):

| cause | shortages naming it | backed by label | precision |
|---|---|---|---|
| DEMAND_SPIKE | 37 | 8 | 0.2162 |
| INSUFFICIENT_OPENING_STOCK | 53 | 51 | 0.9623 |
| INSUFFICIENT_REPLENISHMENT | 118 | 109 | 0.9237 |
| LEAD_TIME_CORRECTION | 6 | 6 | 1.0 |
| PRODUCTION_SHORTFALL | 22 | 13 | 0.5909 |
| SUPPLIER_CAPACITY | 8 | 8 | 1.0 |
| SUPPLIER_DELAY | 26 | 26 | 1.0 |
| SUPPLY_EXCLUDED | 60 | 60 | 1.0 |
| TRANSPORT_DELAY | 18 | 18 | 1.0 |

## 3. Planning KPIs

- **sku_locations**: 565
- **sku_location_weeks**: 29380
- **stockout_week_share**: 0.0664
- **below_safety_stock_week_share**: 0.0957
- **sku_locations_with_shortage**: 182
- **shortage_episodes**: 337
- **shortage_units**: 43518.46
- **value_at_risk_usd**: 940753.49
- **by_priority_band**: {'P1': 34, 'P2': 101, 'P3': 202}
- **by_primary_cause**: {'INSUFFICIENT_REPLENISHMENT': 118, 'SUPPLY_EXCLUDED': 59, 'INSUFFICIENT_OPENING_STOCK': 53, 'DEMAND_SPIKE': 28, 'SUPPLIER_DELAY': 26, 'PRODUCTION_SHORTFALL': 21, 'TRANSPORT_DELAY': 18, 'SUPPLIER_CAPACITY': 8, 'LEAD_TIME_CORRECTION': 6}
- **inbound_lines**: 2312
- **inbound_actions**: {'INCLUDED': 2261, 'EXCLUDED_CANCELLED': 23, 'EXCLUDED_DUPLICATE': 12, 'EXCLUDED_UOM_MISMATCH': 8, 'EXCLUDED_UNAPPROVED_SUBSTITUTE': 8}
- **total_requirement_units**: 831888.86

## 4. Mitigation KPIs

- **options_generated**: 1011
- **options_policy_rejected**: 39
- **rejected_by_reason**: {'REJECTED_SUPPLIER_ON_HOLD': 38, 'REJECTED_SUBSTITUTE_NOT_APPROVED': 1}
- **shortages_with_eligible_option**: 0.9347
- **shortage_units_covered_on_time_pct**: 83.46
- **shortages_fully_mitigated**: 257
- **shortages_escalated**: 80
- **p1_fully_mitigated_pct**: 47.06
- **recommended_incremental_cost_usd**: 88650.08
- **recommended_policy_violations**: 0

### Cost vs service trade-off by option type

| option | options | recommended | avg cost/unit (USD) | avg on-time % | avg days late |
|---|---|---|---|---|---|
| EXPEDITE_PO | 278 | 93 | 4.99 | 20.14 | 13.48 |
| NEW_PO | 535 | 199 | 44.11 | 80.23 | 4.31 |
| SUBSTITUTE | 3 | 2 | 0.72 | 67.82 | 0.0 |
| TRANSFER | 156 | 29 | 23.51 | 47.39 | 0.67 |
