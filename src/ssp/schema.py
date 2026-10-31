"""Single source of truth for every table: fields, types, enums, keys, rules.

Used by: the CSV loader (type coercion), the validator (Step 8), the SQL
exporter (CREATE TABLE) and the data-dictionary generator (Step 1).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class F:
    name: str
    type: str                      # string | int | decimal | date | bool
    required: bool = True
    allowed: tuple | None = None   # enum values
    unit: str = ""
    unique: bool = False
    rule: str = ""
    pattern: str | None = None     # regex for IDs
    min: float | None = None
    max: float | None = None


@dataclass(frozen=True)
class Table:
    name: str
    layer: str                     # input | derived | ground_truth
    description: str
    pk: tuple
    fields: tuple
    fks: tuple = ()                # (column, ref_table, ref_column)
    unique_together: tuple = ()    # tuples of columns
    cardinality: tuple = ()        # human-readable relationship notes
    lifecycle: str = ""

    def col(self, name: str) -> F:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(name)

    @property
    def columns(self) -> list[str]:
        return [f.name for f in self.fields]


WEEK = r"^2026W(0[1-9]|[1-4][0-9]|5[0-2])$"
SKU = r"^SKU-\d{6}$"
LOC = r"^LOC-\d{4}$"
SUP = r"^SUP-\d{4}$"
PO = r"^PO-2026-\d{6}$"
SHORT = r"^SHORT-2026-\d{6}$"
UOMS = ("EA", "CS", "KG")
PO_STATUS = ("CREATED", "CONFIRMED", "IN_TRANSIT", "DELAYED", "CANCELLED")

TABLES: dict[str, Table] = {}


def _t(t: Table):
    TABLES[t.name] = t


# ---------------------------------------------------------------- master data
_t(Table(
    "sku", "input", "Stock keeping unit master. One row per item.",
    pk=("sku_id",),
    fields=(
        F("sku_id", "string", unique=True, pattern=SKU, rule="SKU-NNNNNN, immutable"),
        F("sku_name", "string"),
        F("sku_type", "string", allowed=("FINISHED", "MANUFACTURED", "COMPONENT"),
          rule="FINISHED=bought finished good stocked at DCs; MANUFACTURED=made at a plant from a BOM; COMPONENT=bought input for production"),
        F("category", "string", allowed=("ELECTRONICS", "HOME", "GROCERY", "APPAREL", "INDUSTRIAL",
                                         "RAW_MATERIAL", "PACKAGING", "SUBASSEMBLY")),
        F("base_uom", "string", allowed=("EA", "KG"), rule="all quantities in planning are expressed in base_uom"),
        F("case_uom", "string", required=False, allowed=("CS", ""), rule="CS only when base_uom=EA"),
        F("units_per_case", "int", required=False, unit="EA per CS", min=1, rule="required when case_uom=CS"),
        F("unit_cost", "decimal", unit="USD per base unit", min=0.01),
        F("abc_class", "string", allowed=("A", "B", "C"),
          rule="DERIVED: A = top 80% of annual demand value, B = next 15%, C = rest"),
        F("lifecycle_status", "string", allowed=("ACTIVE", "PHASE_IN", "PHASE_OUT")),
        F("introduced_date", "date"),
    ),
    lifecycle="PHASE_IN -> ACTIVE -> PHASE_OUT",
))

_t(Table(
    "location", "input", "Plants and distribution centres.",
    pk=("location_id",),
    fields=(
        F("location_id", "string", unique=True, pattern=LOC),
        F("location_name", "string"),
        F("location_type", "string", allowed=("PLANT", "DC")),
        F("region", "string", allowed=("WEST", "CENTRAL", "EAST", "SOUTH")),
        F("status", "string", allowed=("ACTIVE",)),
        F("effective_from", "date"),
    ),
))

_t(Table(
    "sku_location", "input",
    "Bridge SKU<->Location (N:M): which SKU is stocked where, with its safety stock.",
    pk=("sku_location_id",),
    fields=(
        F("sku_location_id", "string", unique=True, pattern=r"^SL-SKU-\d{6}-LOC-\d{4}$"),
        F("sku_id", "string", pattern=SKU),
        F("location_id", "string", pattern=LOC),
        F("safety_stock_qty", "decimal", unit="base_uom", min=0,
          rule="DERIVED: 0.5-2.0 weeks of average gross requirement"),
        F("stocking_status", "string", allowed=("ACTIVE",)),
        F("effective_from", "date"),
    ),
    fks=(("sku_id", "sku", "sku_id"), ("location_id", "location", "location_id")),
    unique_together=(("sku_id", "location_id"),),
    cardinality=("SKU 1:N sku_location", "Location 1:N sku_location", "=> SKU N:M Location"),
))

_t(Table(
    "sku_substitute", "input",
    "Bridge SKU<->SKU (N:M): approved/unapproved substitutes. Only APPROVED pairs may be used.",
    pk=("substitute_id",),
    fields=(
        F("substitute_id", "string", unique=True, pattern=r"^SUB-SKU-\d{6}-SKU-\d{6}$"),
        F("sku_id", "string", pattern=SKU, rule="the original SKU"),
        F("substitute_sku_id", "string", pattern=SKU, rule="must differ from sku_id, same base_uom"),
        F("approval_status", "string", allowed=("APPROVED", "PENDING", "REJECTED")),
        F("conversion_factor", "decimal", min=0.01, rule="substitute units per original unit"),
        F("priority", "int", min=1),
        F("effective_from", "date"),
        F("effective_to", "date", required=False, rule="blank = open-ended; must be > effective_from"),
    ),
    fks=(("sku_id", "sku", "sku_id"), ("substitute_sku_id", "sku", "sku_id")),
    unique_together=(("sku_id", "substitute_sku_id"),),
    cardinality=("SKU N:M SKU (self-referencing bridge)",),
    lifecycle="PENDING -> APPROVED | REJECTED",
))

_t(Table(
    "supplier", "input", "Supplier master.",
    pk=("supplier_id",),
    fields=(
        F("supplier_id", "string", unique=True, pattern=SUP),
        F("supplier_name", "string"),
        F("country", "string", allowed=("US", "MX", "CN", "IN", "VN", "DE")),
        F("reliability_score", "decimal", min=0, max=1, rule="historic on-time ratio"),
        F("expedite_premium_pct", "decimal", min=0, max=1, rule="extra cost share when expediting"),
        F("supplier_status", "string", allowed=("ACTIVE", "ON_HOLD"),
          rule="ON_HOLD suppliers may not receive new POs (policy)"),
        F("effective_from", "date"),
    ),
    lifecycle="ACTIVE <-> ON_HOLD",
))

_t(Table(
    "supplier_sku", "input",
    "Bridge Supplier<->SKU (N:M): approved sources with MOQ, order multiple, order UoM and price.",
    pk=("supplier_sku_id",),
    fields=(
        F("supplier_sku_id", "string", unique=True, pattern=r"^SS-SUP-\d{4}-SKU-\d{6}$"),
        F("supplier_id", "string", pattern=SUP),
        F("sku_id", "string", pattern=SKU),
        F("is_primary", "bool", rule="exactly one primary per purchased SKU"),
        F("order_uom", "string", allowed=UOMS),
        F("order_multiple_base", "decimal", unit="base_uom", min=0.001),
        F("min_order_qty_base", "decimal", unit="base_uom", min=0.001, rule="MOQ; multiple of order_multiple_base"),
        F("unit_price", "decimal", unit="USD per base unit", min=0.01),
        F("sourcing_status", "string", allowed=("APPROVED",)),
        F("effective_from", "date"),
    ),
    fks=(("supplier_id", "supplier", "supplier_id"), ("sku_id", "sku", "sku_id")),
    unique_together=(("supplier_id", "sku_id"),),
    cardinality=("Supplier N:M SKU",),
))

_t(Table(
    "lead_time", "input",
    "Effective-dated lead time per supplier-SKU. Versions must not overlap.",
    pk=("lead_time_id",),
    fields=(
        F("lead_time_id", "string", unique=True, pattern=r"^LT-SUP-\d{4}-SKU-\d{6}-V\d+$"),
        F("supplier_id", "string", pattern=SUP),
        F("sku_id", "string", pattern=SKU),
        F("version", "int", min=1),
        F("lead_time_days", "int", unit="days", min=1, rule="order date -> receipt date"),
        F("transit_days", "int", unit="days", min=1, rule="<= lead_time_days"),
        F("transport_mode", "string", allowed=("TRUCK", "OCEAN", "AIR", "RAIL")),
        F("effective_from", "date"),
        F("effective_to", "date", required=False, rule="blank = current version"),
    ),
    fks=(("supplier_id", "supplier", "supplier_id"), ("sku_id", "sku", "sku_id")),
    unique_together=(("supplier_id", "sku_id", "version"),),
    cardinality=("supplier_sku 1:N lead_time (versions over time)",),
))

_t(Table(
    "supplier_capacity", "input",
    "Weekly supplier capacity in delivered units (EA and KG both count as 1 unit).",
    pk=("capacity_id",),
    fields=(
        F("capacity_id", "string", unique=True, pattern=r"^CAP-SUP-\d{4}-2026W\d{2}$"),
        F("supplier_id", "string", pattern=SUP),
        F("week_id", "string", pattern=WEEK),
        F("week_start_date", "date"),
        F("capacity_units", "decimal", unit="units/week", min=0),
    ),
    fks=(("supplier_id", "supplier", "supplier_id"),),
    unique_together=(("supplier_id", "week_id"),),
    cardinality=("Supplier 1:N supplier_capacity (one per week)",),
))

_t(Table(
    "forecast_demand", "input", "Weekly forecast per SKU-location (finished and manufactured SKUs).",
    pk=("demand_id",),
    fields=(
        F("demand_id", "string", unique=True, pattern=r"^DEM-SKU-\d{6}-LOC-\d{4}-2026W\d{2}$"),
        F("sku_id", "string", pattern=SKU),
        F("location_id", "string", pattern=LOC),
        F("week_id", "string", pattern=WEEK),
        F("week_start_date", "date"),
        F("forecast_qty", "decimal", unit="base_uom", min=0),
        F("uom", "string", allowed=("EA", "KG"), rule="= sku.base_uom"),
        F("forecast_version", "string"),
    ),
    fks=(("sku_id", "sku", "sku_id"), ("location_id", "location", "location_id")),
    unique_together=(("sku_id", "location_id", "week_id"),),
    cardinality=("sku_location 1:N forecast_demand (52 weeks)",),
))

_t(Table(
    "inventory", "input", "On-hand snapshot at the as-of date (2025-12-29).",
    pk=("inventory_id",),
    fields=(
        F("inventory_id", "string", unique=True, pattern=r"^INV-SKU-\d{6}-LOC-\d{4}-\d{8}$"),
        F("sku_id", "string", pattern=SKU),
        F("location_id", "string", pattern=LOC),
        F("snapshot_date", "date"),
        F("on_hand_qty", "decimal", unit="base_uom", min=0),
        F("on_hold_qty", "decimal", unit="base_uom", min=0, rule="<= on_hand_qty; not available"),
        F("uom", "string", allowed=("EA", "KG")),
    ),
    fks=(("sku_id", "sku", "sku_id"), ("location_id", "location", "location_id")),
    unique_together=(("sku_id", "location_id", "snapshot_date"),),
    cardinality=("sku_location 1:1 inventory (per snapshot date)",),
))

_t(Table(
    "bom", "input", "Bill of materials (SKU N:M SKU): components per manufactured unit.",
    pk=("bom_id",),
    fields=(
        F("bom_id", "string", unique=True, pattern=r"^BOM-SKU-\d{6}-SKU-\d{6}$"),
        F("parent_sku_id", "string", pattern=SKU, rule="sku_type=MANUFACTURED"),
        F("component_sku_id", "string", pattern=SKU, rule="sku_type=COMPONENT"),
        F("qty_per", "decimal", unit="component base_uom per parent EA", min=0.001),
        F("scrap_pct", "decimal", min=0, max=0.2),
        F("effective_from", "date"),
        F("effective_to", "date", required=False),
    ),
    fks=(("parent_sku_id", "sku", "sku_id"), ("component_sku_id", "sku", "sku_id")),
    unique_together=(("parent_sku_id", "component_sku_id"),),
    cardinality=("SKU(parent) N:M SKU(component)",),
))

_t(Table(
    "production_capacity", "input", "Weekly production capacity per plant (finished units).",
    pk=("production_capacity_id",),
    fields=(
        F("production_capacity_id", "string", unique=True, pattern=r"^PCAP-LOC-\d{4}-2026W\d{2}$"),
        F("location_id", "string", pattern=LOC, rule="location_type=PLANT"),
        F("week_id", "string", pattern=WEEK),
        F("week_start_date", "date"),
        F("capacity_units", "decimal", unit="EA/week", min=0),
    ),
    fks=(("location_id", "location", "location_id"),),
    unique_together=(("location_id", "week_id"),),
))

_t(Table(
    "production_plan", "input", "Planned production of manufactured SKUs by plant-week.",
    pk=("production_plan_id",),
    fields=(
        F("production_plan_id", "string", unique=True, pattern=r"^PP-2026-\d{6}$"),
        F("sku_id", "string", pattern=SKU),
        F("location_id", "string", pattern=LOC),
        F("week_id", "string", pattern=WEEK),
        F("week_start_date", "date"),
        F("planned_qty", "decimal", unit="EA", min=0.001),
        F("uom", "string", allowed=("EA",)),
        F("plan_status", "string", allowed=("FIRM", "PLANNED"), rule="FIRM inside the 4-week frozen fence"),
    ),
    fks=(("sku_id", "sku", "sku_id"), ("location_id", "location", "location_id")),
    unique_together=(("sku_id", "location_id", "week_id"),),
    lifecycle="PLANNED -> FIRM (as week enters frozen fence)",
))

_t(Table(
    "purchase_order", "input",
    "Inbound order header (one supplier -> one location). Status is DERIVED from po_event.",
    pk=("po_id",),
    fields=(
        F("po_id", "string", unique=True, pattern=PO),
        F("supplier_id", "string", pattern=SUP),
        F("location_id", "string", pattern=LOC),
        F("supplier_ref", "string", rule="supplier order confirmation number; should be unique"),
        F("order_date", "date", rule="order_date + lead_time <= expected_receipt_date"),
        F("expected_receipt_date", "date", rule="> order_date; never overwritten (delays live in po_event)"),
        F("transport_mode", "string", allowed=("TRUCK", "OCEAN", "AIR", "RAIL")),
        F("currency", "string", allowed=("USD",)),
        F("po_status", "string", allowed=PO_STATUS, rule="DERIVED = to_status of latest po_event"),
    ),
    fks=(("supplier_id", "supplier", "supplier_id"), ("location_id", "location", "location_id")),
    cardinality=("Supplier 1:N purchase_order", "Location 1:N purchase_order"),
    lifecycle="CREATED -> CONFIRMED -> IN_TRANSIT -> (DELAYED) ; CREATED|CONFIRMED -> CANCELLED",
))

_t(Table(
    "purchase_order_line", "input", "Inbound order lines.",
    pk=("po_line_id",),
    fields=(
        F("po_line_id", "string", unique=True, pattern=r"^PO-2026-\d{6}-L\d{2}$"),
        F("po_id", "string", pattern=PO),
        F("line_no", "int", min=1),
        F("sku_id", "string", pattern=SKU),
        F("substitute_for_sku_id", "string", required=False,
          rule="if set, this line buys a substitute to cover that SKU; pair must be APPROVED"),
        F("order_qty", "decimal", unit="uom", min=0.001),
        F("uom", "string", allowed=UOMS, rule="must be convertible to sku.base_uom (EA<-EA/CS, KG<-KG)"),
        F("unit_price", "decimal", unit="USD per base unit", min=0.01),
    ),
    fks=(("po_id", "purchase_order", "po_id"), ("sku_id", "sku", "sku_id")),
    unique_together=(("po_id", "line_no"),),
    cardinality=("purchase_order 1:N purchase_order_line",),
))

_t(Table(
    "po_event", "input", "Append-only PO lifecycle history (state changes are never overwritten).",
    pk=("event_id",),
    fields=(
        F("event_id", "string", unique=True, pattern=r"^EVT-PO-2026-\d{6}-\d{2}$"),
        F("po_id", "string", pattern=PO),
        F("event_seq", "int", min=1, rule="contiguous 1..n per PO"),
        F("event_type", "string", allowed=("CREATED", "CONFIRMED", "SHIPPED", "DELAYED", "CANCELLED")),
        F("event_date", "date", rule="non-decreasing within a PO; <= as-of date"),
        F("from_status", "string", required=False, allowed=PO_STATUS + ("",)),
        F("to_status", "string", allowed=PO_STATUS),
        F("revised_eta", "date", required=False, rule="required for DELAYED; > event_date"),
        F("reason_code", "string", required=False,
          allowed=("CARRIER_DELAY", "PORT_CONGESTION", "WEATHER", "SUPPLIER_DELAY", "BUYER_CANCELLED", "")),
        F("actor", "string", allowed=("PLANNER", "SUPPLIER", "CARRIER")),
    ),
    fks=(("po_id", "purchase_order", "po_id"),),
    unique_together=(("po_id", "event_seq"),),
    cardinality=("purchase_order 1:N po_event",),
))

# ---------------------------------------------------------------- derived
_t(Table(
    "inbound_effective", "derived",
    "Planner decision per PO line: what quantity and date is counted in the projection, and why.",
    pk=("po_line_id",),
    fields=(
        F("po_line_id", "string", unique=True),
        F("po_id", "string", pattern=PO),
        F("supplier_id", "string", pattern=SUP),
        F("location_id", "string", pattern=LOC),
        F("sku_id", "string", pattern=SKU),
        F("credited_sku_id", "string", required=False, rule="SKU whose balance receives the qty"),
        F("base_qty", "decimal", required=False, unit="base_uom", rule="blank when UoM not convertible"),
        F("effective_qty", "decimal", unit="base_uom", min=0),
        F("original_eta", "date"),
        F("effective_eta", "date"),
        F("effective_week_id", "string", required=False, rule="blank when beyond horizon or excluded"),
        F("action", "string", allowed=("INCLUDED", "EXCLUDED_CANCELLED", "EXCLUDED_DUPLICATE",
                                       "EXCLUDED_UOM_MISMATCH", "EXCLUDED_UNAPPROVED_SUBSTITUTE")),
        F("adjustments", "string", required=False, rule="semicolon list: DELAYED;REDATED_LEAD_TIME;SCALED_CAPACITY;BEYOND_HORIZON"),
        F("exception_ids", "string", required=False),
    ),
    fks=(("po_line_id", "purchase_order_line", "po_line_id"),),
))

_t(Table(
    "component_requirement", "derived", "Dependent demand = production_plan x BOM.",
    pk=("requirement_id",),
    fields=(
        F("requirement_id", "string", unique=True),
        F("production_plan_id", "string"),
        F("parent_sku_id", "string", pattern=SKU),
        F("component_sku_id", "string", pattern=SKU),
        F("location_id", "string", pattern=LOC),
        F("week_id", "string", pattern=WEEK),
        F("required_qty", "decimal", min=0, rule="planned_qty * qty_per * (1+scrap_pct); EA rounded up"),
        F("uom", "string", allowed=("EA", "KG")),
    ),
    fks=(("production_plan_id", "production_plan", "production_plan_id"),),
))

_t(Table(
    "projected_balance", "derived",
    "Projected available balance by SKU-location-week. closing = opening + receipts - gross requirement.",
    pk=("projection_id",),
    fields=(
        F("projection_id", "string", unique=True),
        F("sku_id", "string", pattern=SKU),
        F("location_id", "string", pattern=LOC),
        F("week_id", "string", pattern=WEEK),
        F("week_start_date", "date"),
        F("opening_qty", "decimal", rule="week1 = on_hand - on_hold; else previous closing"),
        F("receipts_po_qty", "decimal", min=0),
        F("receipts_production_qty", "decimal", min=0),
        F("forecast_qty", "decimal", min=0),
        F("dependent_demand_qty", "decimal", min=0),
        F("closing_qty", "decimal", rule="may be negative = backlog (unmet demand carried forward)"),
        F("safety_stock_qty", "decimal", min=0),
        F("below_safety_stock", "bool"),
        F("stockout", "bool", rule="closing_qty < 0"),
    ),
    unique_together=(("sku_id", "location_id", "week_id"),),
))

_t(Table(
    "supplier_load", "derived", "Supplier weekly load vs capacity.",
    pk=("capacity_id",),
    fields=(
        F("capacity_id", "string", unique=True),
        F("supplier_id", "string", pattern=SUP),
        F("week_id", "string", pattern=WEEK),
        F("load_units", "decimal", min=0),
        F("capacity_units", "decimal", min=0),
        F("utilisation", "decimal", min=0),
        F("is_exceeded", "bool"),
        F("scale_factor", "decimal", min=0, max=1, rule="capacity/load when exceeded, else 1"),
    ),
    fks=(("capacity_id", "supplier_capacity", "capacity_id"),),
))

_t(Table(
    "exception_log", "derived", "Every data or business exception the planner raised, with its decision.",
    pk=("exception_id",),
    fields=(
        F("exception_id", "string", unique=True, pattern=r"^EXC-2026-\d{6}$"),
        F("exception_type", "string", allowed=(
            "INBOUND_COUNTED_TWICE", "SUBSTITUTE_NOT_APPROVED", "SUPPLIER_CAPACITY_EXCEEDED",
            "SHORTAGE_WITHOUT_LEAD_TIME", "UOM_MISMATCH", "SHORTAGE_ESCALATED")),
        F("entity_type", "string"),
        F("record_id", "string"),
        F("related_record_id", "string", required=False),
        F("rule_id", "string"),
        F("decision", "string"),
        F("details", "string"),
        F("detected_at", "date"),
    ),
))

_t(Table(
    "shortage", "derived",
    "One row per shortage episode (consecutive weeks with projected balance < 0) per SKU-location.",
    pk=("shortage_id",),
    fields=(
        F("shortage_id", "string", unique=True, pattern=SHORT, rule="numbered by priority rank"),
        F("sku_id", "string", pattern=SKU),
        F("location_id", "string", pattern=LOC),
        F("first_short_week_id", "string", pattern=WEEK),
        F("last_short_week_id", "string", pattern=WEEK),
        F("need_date", "date", rule="Monday of first short week"),
        F("weeks_short", "int", min=1),
        F("shortage_qty", "decimal", min=0, rule="peak negative balance in the episode = qty needed by need_date"),
        F("uom", "string", allowed=("EA", "KG")),
        F("unit_cost", "decimal"),
        F("value_at_risk", "decimal", unit="USD"),
        F("abc_class", "string", allowed=("A", "B", "C")),
        F("priority_score", "decimal", rule="value_at_risk * ABC weight(A3,B2,C1) / (1 + weeks_until_need/4)"),
        F("priority_rank", "int", min=1),
        F("priority_band", "string", allowed=("P1", "P2", "P3"), rule="P1 top 10%, P2 next 30%"),
        F("primary_cause", "string", allowed=(
            "SUPPLIER_CAPACITY", "TRANSPORT_DELAY", "SUPPLIER_DELAY", "LEAD_TIME_CORRECTION",
            "SUPPLY_EXCLUDED", "DEMAND_SPIKE", "PRODUCTION_SHORTFALL",
            "INSUFFICIENT_OPENING_STOCK", "INSUFFICIENT_REPLENISHMENT")),
        F("contributing_causes", "string"),
        F("cause_evidence", "string", rule="references to the records that explain the cause"),
        F("detected_at", "date"),
        F("on_time_mitigated_qty", "decimal", min=0),
        F("residual_qty", "decimal", min=0),
        F("shortage_status", "string", allowed=("DETECTED", "PRIORITIZED", "MITIGATION_PROPOSED", "ESCALATED"),
          rule="DERIVED = to_status of latest shortage_event"),
    ),
    lifecycle="DETECTED -> PRIORITIZED -> MITIGATION_PROPOSED -> (ESCALATED if residual > 0)",
))

_t(Table(
    "shortage_event", "derived", "Append-only shortage lifecycle history.",
    pk=("shortage_event_id",),
    fields=(
        F("shortage_event_id", "string", unique=True),
        F("shortage_id", "string", pattern=SHORT),
        F("event_seq", "int", min=1),
        F("event_type", "string", allowed=("DETECTED", "PRIORITIZED", "MITIGATION_PROPOSED", "ESCALATED")),
        F("event_date", "date"),
        F("from_status", "string", required=False),
        F("to_status", "string"),
        F("details", "string"),
    ),
    fks=(("shortage_id", "shortage", "shortage_id"),),
))

_t(Table(
    "mitigation_option", "derived",
    "Candidate mitigations per shortage with cost/service trade-off, policy check and recommendation.",
    pk=("mitigation_id",),
    fields=(
        F("mitigation_id", "string", unique=True, pattern=r"^MIT-SHORT-2026-\d{6}-\d{2}$"),
        F("shortage_id", "string", pattern=SHORT),
        F("option_seq", "int", min=1),
        F("option_type", "string", allowed=("TRANSFER", "SUBSTITUTE", "EXPEDITE_PO", "NEW_PO", "PRODUCTION_INCREASE")),
        F("source_ref", "string", rule="record the option relies on (location / PO line / supplier_sku / substitute / plant)"),
        F("source_location_id", "string", required=False),
        F("supplier_id", "string", required=False),
        F("substitute_sku_id", "string", required=False),
        F("lead_time_days", "int", required=False),
        F("proposed_qty", "decimal", min=0),
        F("coverable_qty", "decimal", min=0),
        F("arrival_date", "date"),
        F("need_date", "date"),
        F("days_late", "int", min=0),
        F("on_time_qty", "decimal", min=0),
        F("incremental_cost", "decimal", unit="USD", min=0),
        F("cost_per_unit", "decimal", unit="USD", min=0),
        F("service_coverage_pct", "decimal", min=0, max=100, rule="on_time_qty / shortage_qty"),
        F("feasibility", "string", allowed=("ON_TIME", "PARTIAL", "LATE", "INFEASIBLE")),
        F("policy_status", "string", allowed=("OK", "REJECTED_SUBSTITUTE_NOT_APPROVED",
                                              "REJECTED_SUPPLIER_ON_HOLD", "REJECTED_BEYOND_HORIZON")),
        F("score", "decimal"),
        F("rank", "int", required=False),
        F("is_recommended", "bool"),
        F("allocated_qty", "decimal", min=0),
        F("decision_reason", "string"),
    ),
    fks=(("shortage_id", "shortage", "shortage_id"),),
    cardinality=("shortage 1:N mitigation_option",),
))

# ---------------------------------------------------------------- ground truth
_t(Table(
    "ground_truth", "ground_truth",
    "Labels written by the generator. NEVER read by the planner (no leakage).",
    pk=("gt_id",),
    fields=(
        F("gt_id", "string", unique=True),
        F("label_category", "string", allowed=("ANOMALY", "SCENARIO")),
        F("issue_type", "string"),
        F("entity_type", "string"),
        F("record_id", "string"),
        F("related_record_id", "string", required=False),
        F("expected_decision", "string", required=False),
        F("description", "string"),
    ),
))

INPUT_TABLES = [n for n, t in TABLES.items() if t.layer == "input"]
DERIVED_TABLES = [n for n, t in TABLES.items() if t.layer == "derived"]
ANOMALY_TYPES = ("INBOUND_COUNTED_TWICE", "SUBSTITUTE_NOT_APPROVED", "SUPPLIER_CAPACITY_EXCEEDED",
                 "SHORTAGE_WITHOUT_LEAD_TIME", "UOM_MISMATCH")
