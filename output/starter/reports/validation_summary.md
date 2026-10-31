# Validation summary

Overall: **PASS** - 235 checks, 0 failed

| check | category | table | description | status | violations |
|---|---|---|---|---|---|
| V-PK | primary_key | sku | sku_id unique and non-empty | PASS | 0 |
| V-REQ | required | sku | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | sku | values within allowed enums | PASS | 0 |
| V-ID | id_format | sku | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | sku | numeric values within min/max | PASS | 0 |
| V-DUP | duplicates | sku | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | location | location_id unique and non-empty | PASS | 0 |
| V-REQ | required | location | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | location | values within allowed enums | PASS | 0 |
| V-ID | id_format | location | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | location | numeric values within min/max | PASS | 0 |
| V-DUP | duplicates | location | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | sku_location | sku_location_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | sku_location | (sku_id, location_id) unique | PASS | 0 |
| V-REQ | required | sku_location | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | sku_location | values within allowed enums | PASS | 0 |
| V-ID | id_format | sku_location | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | sku_location | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | sku_location | sku_id -> sku.sku_id | PASS | 0 |
| V-FK | foreign_key | sku_location | location_id -> location.location_id | PASS | 0 |
| V-DUP | duplicates | sku_location | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | sku_substitute | substitute_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | sku_substitute | (sku_id, substitute_sku_id) unique | PASS | 0 |
| V-REQ | required | sku_substitute | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | sku_substitute | values within allowed enums | PASS | 0 |
| V-ID | id_format | sku_substitute | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | sku_substitute | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | sku_substitute | sku_id -> sku.sku_id | PASS | 0 |
| V-FK | foreign_key | sku_substitute | substitute_sku_id -> sku.sku_id | PASS | 0 |
| V-DUP | duplicates | sku_substitute | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | supplier | supplier_id unique and non-empty | PASS | 0 |
| V-REQ | required | supplier | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | supplier | values within allowed enums | PASS | 0 |
| V-ID | id_format | supplier | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | supplier | numeric values within min/max | PASS | 0 |
| V-DUP | duplicates | supplier | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | supplier_sku | supplier_sku_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | supplier_sku | (supplier_id, sku_id) unique | PASS | 0 |
| V-REQ | required | supplier_sku | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | supplier_sku | values within allowed enums | PASS | 0 |
| V-ID | id_format | supplier_sku | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | supplier_sku | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | supplier_sku | supplier_id -> supplier.supplier_id | PASS | 0 |
| V-FK | foreign_key | supplier_sku | sku_id -> sku.sku_id | PASS | 0 |
| V-DUP | duplicates | supplier_sku | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | lead_time | lead_time_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | lead_time | (supplier_id, sku_id, version) unique | PASS | 0 |
| V-REQ | required | lead_time | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | lead_time | values within allowed enums | PASS | 0 |
| V-ID | id_format | lead_time | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | lead_time | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | lead_time | supplier_id -> supplier.supplier_id | PASS | 0 |
| V-FK | foreign_key | lead_time | sku_id -> sku.sku_id | PASS | 0 |
| V-DUP | duplicates | lead_time | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | supplier_capacity | capacity_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | supplier_capacity | (supplier_id, week_id) unique | PASS | 0 |
| V-REQ | required | supplier_capacity | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | supplier_capacity | values within allowed enums | PASS | 0 |
| V-ID | id_format | supplier_capacity | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | supplier_capacity | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | supplier_capacity | supplier_id -> supplier.supplier_id | PASS | 0 |
| V-DUP | duplicates | supplier_capacity | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | forecast_demand | demand_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | forecast_demand | (sku_id, location_id, week_id) unique | PASS | 0 |
| V-REQ | required | forecast_demand | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | forecast_demand | values within allowed enums | PASS | 0 |
| V-ID | id_format | forecast_demand | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | forecast_demand | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | forecast_demand | sku_id -> sku.sku_id | PASS | 0 |
| V-FK | foreign_key | forecast_demand | location_id -> location.location_id | PASS | 0 |
| V-DUP | duplicates | forecast_demand | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | inventory | inventory_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | inventory | (sku_id, location_id, snapshot_date) unique | PASS | 0 |
| V-REQ | required | inventory | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | inventory | values within allowed enums | PASS | 0 |
| V-ID | id_format | inventory | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | inventory | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | inventory | sku_id -> sku.sku_id | PASS | 0 |
| V-FK | foreign_key | inventory | location_id -> location.location_id | PASS | 0 |
| V-DUP | duplicates | inventory | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | bom | bom_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | bom | (parent_sku_id, component_sku_id) unique | PASS | 0 |
| V-REQ | required | bom | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | bom | values within allowed enums | PASS | 0 |
| V-ID | id_format | bom | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | bom | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | bom | parent_sku_id -> sku.sku_id | PASS | 0 |
| V-FK | foreign_key | bom | component_sku_id -> sku.sku_id | PASS | 0 |
| V-DUP | duplicates | bom | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | production_capacity | production_capacity_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | production_capacity | (location_id, week_id) unique | PASS | 0 |
| V-REQ | required | production_capacity | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | production_capacity | values within allowed enums | PASS | 0 |
| V-ID | id_format | production_capacity | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | production_capacity | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | production_capacity | location_id -> location.location_id | PASS | 0 |
| V-DUP | duplicates | production_capacity | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | production_plan | production_plan_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | production_plan | (sku_id, location_id, week_id) unique | PASS | 0 |
| V-REQ | required | production_plan | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | production_plan | values within allowed enums | PASS | 0 |
| V-ID | id_format | production_plan | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | production_plan | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | production_plan | sku_id -> sku.sku_id | PASS | 0 |
| V-FK | foreign_key | production_plan | location_id -> location.location_id | PASS | 0 |
| V-DUP | duplicates | production_plan | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | purchase_order | po_id unique and non-empty | PASS | 0 |
| V-REQ | required | purchase_order | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | purchase_order | values within allowed enums | PASS | 0 |
| V-ID | id_format | purchase_order | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | purchase_order | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | purchase_order | supplier_id -> supplier.supplier_id | PASS | 0 |
| V-FK | foreign_key | purchase_order | location_id -> location.location_id | PASS | 0 |
| V-DUP | duplicates | purchase_order | duplicate inbound orders are all labelled anomalies | PASS | 0 |
| V-PK | primary_key | purchase_order_line | po_line_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | purchase_order_line | (po_id, line_no) unique | PASS | 0 |
| V-REQ | required | purchase_order_line | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | purchase_order_line | values within allowed enums | PASS | 0 |
| V-ID | id_format | purchase_order_line | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | purchase_order_line | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | purchase_order_line | po_id -> purchase_order.po_id | PASS | 0 |
| V-FK | foreign_key | purchase_order_line | sku_id -> sku.sku_id | PASS | 0 |
| V-DUP | duplicates | purchase_order_line | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | po_event | event_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | po_event | (po_id, event_seq) unique | PASS | 0 |
| V-REQ | required | po_event | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | po_event | values within allowed enums | PASS | 0 |
| V-ID | id_format | po_event | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | po_event | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | po_event | po_id -> purchase_order.po_id | PASS | 0 |
| V-DUP | duplicates | po_event | no duplicate business rows | PASS | 0 |
| V-PK | primary_key | inbound_effective | po_line_id unique and non-empty | PASS | 0 |
| V-REQ | required | inbound_effective | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | inbound_effective | values within allowed enums | PASS | 0 |
| V-ID | id_format | inbound_effective | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | inbound_effective | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | inbound_effective | po_line_id -> purchase_order_line.po_line_id | PASS | 0 |
| V-PK | primary_key | component_requirement | requirement_id unique and non-empty | PASS | 0 |
| V-REQ | required | component_requirement | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | component_requirement | values within allowed enums | PASS | 0 |
| V-ID | id_format | component_requirement | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | component_requirement | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | component_requirement | production_plan_id -> production_plan.production_plan_id | PASS | 0 |
| V-PK | primary_key | projected_balance | projection_id unique and non-empty | PASS | 0 |
| V-UNIQ | uniqueness | projected_balance | (sku_id, location_id, week_id) unique | PASS | 0 |
| V-REQ | required | projected_balance | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | projected_balance | values within allowed enums | PASS | 0 |
| V-ID | id_format | projected_balance | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | projected_balance | numeric values within min/max | PASS | 0 |
| V-PK | primary_key | supplier_load | capacity_id unique and non-empty | PASS | 0 |
| V-REQ | required | supplier_load | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | supplier_load | values within allowed enums | PASS | 0 |
| V-ID | id_format | supplier_load | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | supplier_load | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | supplier_load | capacity_id -> supplier_capacity.capacity_id | PASS | 0 |
| V-PK | primary_key | exception_log | exception_id unique and non-empty | PASS | 0 |
| V-REQ | required | exception_log | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | exception_log | values within allowed enums | PASS | 0 |
| V-ID | id_format | exception_log | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | exception_log | numeric values within min/max | PASS | 0 |
| V-PK | primary_key | shortage | shortage_id unique and non-empty | PASS | 0 |
| V-REQ | required | shortage | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | shortage | values within allowed enums | PASS | 0 |
| V-ID | id_format | shortage | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | shortage | numeric values within min/max | PASS | 0 |
| V-PK | primary_key | shortage_event | shortage_event_id unique and non-empty | PASS | 0 |
| V-REQ | required | shortage_event | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | shortage_event | values within allowed enums | PASS | 0 |
| V-ID | id_format | shortage_event | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | shortage_event | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | shortage_event | shortage_id -> shortage.shortage_id | PASS | 0 |
| V-PK | primary_key | mitigation_option | mitigation_id unique and non-empty | PASS | 0 |
| V-REQ | required | mitigation_option | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | mitigation_option | values within allowed enums | PASS | 0 |
| V-ID | id_format | mitigation_option | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | mitigation_option | numeric values within min/max | PASS | 0 |
| V-FK | foreign_key | mitigation_option | shortage_id -> shortage.shortage_id | PASS | 0 |
| V-PK | primary_key | ground_truth | gt_id unique and non-empty | PASS | 0 |
| V-REQ | required | ground_truth | required fields populated | PASS | 0 |
| V-ENUM | allowed_values | ground_truth | values within allowed enums | PASS | 0 |
| V-ID | id_format | ground_truth | IDs match naming convention | PASS | 0 |
| V-RANGE | ranges | ground_truth | numeric values within min/max | PASS | 0 |
| V-DATE-01 | date_order | purchase_order | order_date < expected_receipt_date | PASS | 0 |
| V-DATE-02 | date_order | lead_time | effective_from <= effective_to | PASS | 0 |
| V-DATE-03 | effective_dates | lead_time | versions contiguous, non-overlapping, latest open | PASS | 0 |
| V-DATE-04 | date_order | po_event | event dates non-decreasing and <= as-of date | PASS | 0 |
| V-DATE-05 | date_order | po_event | DELAYED events carry revised_eta > event_date | PASS | 0 |
| V-DATE-06 | calendar | * | week_start_date matches ISO week_id | PASS | 0 |
| V-DATE-07 | effective_dates | sku_substitute | effective_to after effective_from | PASS | 0 |
| V-LIFE-01 | lifecycle | po_event | event_seq contiguous from 1, starts with CREATED | PASS | 0 |
| V-LIFE-02 | lifecycle | po_event | only allowed PO status transitions, from_status chains | PASS | 0 |
| V-LIFE-03 | lifecycle | purchase_order | po_status = latest event to_status (derived) | PASS | 0 |
| V-LIFE-04 | lifecycle | shortage_event | only allowed shortage transitions | PASS | 0 |
| V-LIFE-05 | lifecycle | shortage | shortage_status = latest event to_status | PASS | 0 |
| V-REF-01 | dependency | bom | parent is MANUFACTURED, component is COMPONENT, no self-reference | PASS | 0 |
| V-REF-02 | dependency | production_plan | only MANUFACTURED SKUs at PLANT locations, stocked there | PASS | 0 |
| V-REF-03 | dependency | forecast_demand | forecast only for stocked FINISHED/MANUFACTURED, uom = base | PASS | 0 |
| V-REF-04 | dependency | inventory | exactly one snapshot per stocked SKU-location, uom = base | PASS | 0 |
| V-REF-05 | dependency | supplier_sku | exactly one primary supplier per purchased SKU | PASS | 0 |
| V-REF-06 | foreign_key | lead_time | (supplier_id, sku_id) -> supplier_sku | PASS | 0 |
| V-REF-07 | dependency | purchase_order_line | line SKU is sourced from the PO supplier; covered SKU is stocked at the PO location | PASS | 0 |
| V-QTY-01 | quantity | inventory | on_hold_qty <= on_hand_qty | PASS | 0 |
| V-QTY-02 | quantity | lead_time | transit_days <= lead_time_days | PASS | 0 |
| V-QTY-03 | capacity | production_plan | planned production <= plant capacity each week | PASS | 0 |
| V-REF-08 | dependency | sku_substitute | substitute differs from original and shares base uom | PASS | 0 |
| V-ARITH-01 | reconciliation | projected_balance | closing = opening + PO receipts + production - forecast - dependent demand (every week) | PASS | 0 |
| V-ARITH-02 | reconciliation | projected_balance | opening(week n) = closing(week n-1) | PASS | 0 |
| V-ARITH-03 | reconciliation | projected_balance | week-1 opening = on_hand - on_hold | PASS | 0 |
| V-ARITH-04 | reconciliation | projected_balance | PO receipts = sum of INCLUDED inbound_effective lines | PASS | 0 |
| V-ARITH-05 | reconciliation | projected_balance | production receipts = production_plan | PASS | 0 |
| V-ARITH-06 | reconciliation | projected_balance | forecast = forecast_demand | PASS | 0 |
| V-ARITH-07 | reconciliation | projected_balance | dependent demand = component_requirement | PASS | 0 |
| V-ARITH-08 | reconciliation | component_requirement | required_qty = planned_qty x qty_per x (1+scrap) | PASS | 0 |
| V-ARITH-09 | reconciliation | inbound_effective | base_qty = order_qty x units_per_case for CS lines | PASS | 0 |
| V-ARITH-10 | reconciliation | inbound_effective | effective_qty <= base_qty | PASS | 0 |
| V-ARITH-11 | reconciliation | supplier_load | utilisation = load / capacity; is_exceeded = load > capacity | PASS | 0 |
| V-ARITH-12 | reconciliation | shortage | shortage = maximal run of negative balance; qty = peak deficit; value and residual consistent | PASS | 0 |
| V-ARITH-13 | reconciliation | shortage | every stockout week belongs to a shortage episode | PASS | 0 |
| V-ARITH-14 | derived_value | sku | abc_class recomputed from demand value matches | PASS | 0 |
| V-SHORT-01 | explainability | shortage | every shortage has a primary cause and evidence | PASS | 0 |
| V-MIT-01 | policy | mitigation_option | recommended options are policy-compliant and feasible | PASS | 0 |
| V-MIT-02 | lead_time | mitigation_option | NEW_PO arrival = as-of + current supplier lead time | PASS | 0 |
| V-MIT-03 | policy | mitigation_option | substitute options marked OK use APPROVED pairs only | PASS | 0 |
| V-MIT-04 | policy | mitigation_option | no OK new PO to an ON_HOLD supplier | PASS | 0 |
| V-MIT-05 | capacity | mitigation_option | allocations <= coverable and total <= shortage qty | PASS | 0 |
| V-MIT-06 | capacity | mitigation_option | recommended new POs fit remaining supplier capacity | PASS | 0 |
| V-MIT-07 | capacity | mitigation_option | transfers/substitutions never exceed donor surplus above safety stock | PASS | 0 |
| V-MIT-08 | tradeoff | mitigation_option | every option shows cost and service figures | PASS | 0 |
| V-GT-01 | ground_truth | ground_truth | labels stored separately; no label columns in input/derived | PASS | 0 |
| V-GT-02 | ground_truth | ground_truth | every label points to an existing record | PASS | 0 |
| V-GT-03 | anomaly_reconciliation | INBOUND_COUNTED_TWICE | INBOUND_COUNTED_TWICE: 8 labelled, 8 found by independent rule; sets must match | PASS | 0 |
| V-GT-03 | anomaly_reconciliation | SUBSTITUTE_NOT_APPROVED | SUBSTITUTE_NOT_APPROVED: 8 labelled, 8 found by independent rule; sets must match | PASS | 0 |
| V-GT-03 | anomaly_reconciliation | SUPPLIER_CAPACITY_EXCEEDED | SUPPLIER_CAPACITY_EXCEEDED: 8 labelled, 8 found by independent rule; sets must match | PASS | 0 |
| V-GT-03 | anomaly_reconciliation | SHORTAGE_WITHOUT_LEAD_TIME | SHORTAGE_WITHOUT_LEAD_TIME: 8 labelled, 8 found by independent rule; sets must match | PASS | 0 |
| V-GT-03 | anomaly_reconciliation | UOM_MISMATCH | UOM_MISMATCH: 8 labelled, 8 found by independent rule; sets must match | PASS | 0 |
