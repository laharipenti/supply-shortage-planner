-- Generated from src/ssp/schema.py. SQLite / PostgreSQL compatible.
CREATE TABLE sku (
  "sku_id" TEXT NOT NULL,
  "sku_name" TEXT NOT NULL,
  "sku_type" TEXT NOT NULL,
  "category" TEXT NOT NULL,
  "base_uom" TEXT NOT NULL,
  "case_uom" TEXT,
  "units_per_case" INTEGER,
  "unit_cost" REAL NOT NULL,
  "abc_class" TEXT NOT NULL,
  "lifecycle_status" TEXT NOT NULL,
  "introduced_date" TEXT NOT NULL,
  PRIMARY KEY (sku_id)
);

CREATE TABLE location (
  "location_id" TEXT NOT NULL,
  "location_name" TEXT NOT NULL,
  "location_type" TEXT NOT NULL,
  "region" TEXT NOT NULL,
  "status" TEXT NOT NULL,
  "effective_from" TEXT NOT NULL,
  PRIMARY KEY (location_id)
);

CREATE TABLE sku_location (
  "sku_location_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "safety_stock_qty" REAL NOT NULL,
  "stocking_status" TEXT NOT NULL,
  "effective_from" TEXT NOT NULL,
  PRIMARY KEY (sku_location_id),
  FOREIGN KEY ("sku_id") REFERENCES sku("sku_id"),
  FOREIGN KEY ("location_id") REFERENCES location("location_id")
);

CREATE TABLE sku_substitute (
  "substitute_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "substitute_sku_id" TEXT NOT NULL,
  "approval_status" TEXT NOT NULL,
  "conversion_factor" REAL NOT NULL,
  "priority" INTEGER NOT NULL,
  "effective_from" TEXT NOT NULL,
  "effective_to" TEXT,
  PRIMARY KEY (substitute_id),
  FOREIGN KEY ("sku_id") REFERENCES sku("sku_id"),
  FOREIGN KEY ("substitute_sku_id") REFERENCES sku("sku_id")
);

CREATE TABLE supplier (
  "supplier_id" TEXT NOT NULL,
  "supplier_name" TEXT NOT NULL,
  "country" TEXT NOT NULL,
  "reliability_score" REAL NOT NULL,
  "expedite_premium_pct" REAL NOT NULL,
  "supplier_status" TEXT NOT NULL,
  "effective_from" TEXT NOT NULL,
  PRIMARY KEY (supplier_id)
);

CREATE TABLE supplier_sku (
  "supplier_sku_id" TEXT NOT NULL,
  "supplier_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "is_primary" INTEGER NOT NULL,
  "order_uom" TEXT NOT NULL,
  "order_multiple_base" REAL NOT NULL,
  "min_order_qty_base" REAL NOT NULL,
  "unit_price" REAL NOT NULL,
  "sourcing_status" TEXT NOT NULL,
  "effective_from" TEXT NOT NULL,
  PRIMARY KEY (supplier_sku_id),
  FOREIGN KEY ("supplier_id") REFERENCES supplier("supplier_id"),
  FOREIGN KEY ("sku_id") REFERENCES sku("sku_id")
);

CREATE TABLE lead_time (
  "lead_time_id" TEXT NOT NULL,
  "supplier_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "version" INTEGER NOT NULL,
  "lead_time_days" INTEGER NOT NULL,
  "transit_days" INTEGER NOT NULL,
  "transport_mode" TEXT NOT NULL,
  "effective_from" TEXT NOT NULL,
  "effective_to" TEXT,
  PRIMARY KEY (lead_time_id),
  FOREIGN KEY ("supplier_id") REFERENCES supplier("supplier_id"),
  FOREIGN KEY ("sku_id") REFERENCES sku("sku_id")
);

CREATE TABLE supplier_capacity (
  "capacity_id" TEXT NOT NULL,
  "supplier_id" TEXT NOT NULL,
  "week_id" TEXT NOT NULL,
  "week_start_date" TEXT NOT NULL,
  "capacity_units" REAL NOT NULL,
  PRIMARY KEY (capacity_id),
  FOREIGN KEY ("supplier_id") REFERENCES supplier("supplier_id")
);

CREATE TABLE forecast_demand (
  "demand_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "week_id" TEXT NOT NULL,
  "week_start_date" TEXT NOT NULL,
  "forecast_qty" REAL NOT NULL,
  "uom" TEXT NOT NULL,
  "forecast_version" TEXT NOT NULL,
  PRIMARY KEY (demand_id),
  FOREIGN KEY ("sku_id") REFERENCES sku("sku_id"),
  FOREIGN KEY ("location_id") REFERENCES location("location_id")
);

CREATE TABLE inventory (
  "inventory_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "snapshot_date" TEXT NOT NULL,
  "on_hand_qty" REAL NOT NULL,
  "on_hold_qty" REAL NOT NULL,
  "uom" TEXT NOT NULL,
  PRIMARY KEY (inventory_id),
  FOREIGN KEY ("sku_id") REFERENCES sku("sku_id"),
  FOREIGN KEY ("location_id") REFERENCES location("location_id")
);

CREATE TABLE bom (
  "bom_id" TEXT NOT NULL,
  "parent_sku_id" TEXT NOT NULL,
  "component_sku_id" TEXT NOT NULL,
  "qty_per" REAL NOT NULL,
  "scrap_pct" REAL NOT NULL,
  "effective_from" TEXT NOT NULL,
  "effective_to" TEXT,
  PRIMARY KEY (bom_id),
  FOREIGN KEY ("parent_sku_id") REFERENCES sku("sku_id"),
  FOREIGN KEY ("component_sku_id") REFERENCES sku("sku_id")
);

CREATE TABLE production_capacity (
  "production_capacity_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "week_id" TEXT NOT NULL,
  "week_start_date" TEXT NOT NULL,
  "capacity_units" REAL NOT NULL,
  PRIMARY KEY (production_capacity_id),
  FOREIGN KEY ("location_id") REFERENCES location("location_id")
);

CREATE TABLE production_plan (
  "production_plan_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "week_id" TEXT NOT NULL,
  "week_start_date" TEXT NOT NULL,
  "planned_qty" REAL NOT NULL,
  "uom" TEXT NOT NULL,
  "plan_status" TEXT NOT NULL,
  PRIMARY KEY (production_plan_id),
  FOREIGN KEY ("sku_id") REFERENCES sku("sku_id"),
  FOREIGN KEY ("location_id") REFERENCES location("location_id")
);

CREATE TABLE purchase_order (
  "po_id" TEXT NOT NULL,
  "supplier_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "supplier_ref" TEXT NOT NULL,
  "order_date" TEXT NOT NULL,
  "expected_receipt_date" TEXT NOT NULL,
  "transport_mode" TEXT NOT NULL,
  "currency" TEXT NOT NULL,
  "po_status" TEXT NOT NULL,
  PRIMARY KEY (po_id),
  FOREIGN KEY ("supplier_id") REFERENCES supplier("supplier_id"),
  FOREIGN KEY ("location_id") REFERENCES location("location_id")
);

CREATE TABLE purchase_order_line (
  "po_line_id" TEXT NOT NULL,
  "po_id" TEXT NOT NULL,
  "line_no" INTEGER NOT NULL,
  "sku_id" TEXT NOT NULL,
  "substitute_for_sku_id" TEXT,
  "order_qty" REAL NOT NULL,
  "uom" TEXT NOT NULL,
  "unit_price" REAL NOT NULL,
  PRIMARY KEY (po_line_id),
  FOREIGN KEY ("po_id") REFERENCES purchase_order("po_id"),
  FOREIGN KEY ("sku_id") REFERENCES sku("sku_id")
);

CREATE TABLE po_event (
  "event_id" TEXT NOT NULL,
  "po_id" TEXT NOT NULL,
  "event_seq" INTEGER NOT NULL,
  "event_type" TEXT NOT NULL,
  "event_date" TEXT NOT NULL,
  "from_status" TEXT,
  "to_status" TEXT NOT NULL,
  "revised_eta" TEXT,
  "reason_code" TEXT,
  "actor" TEXT NOT NULL,
  PRIMARY KEY (event_id),
  FOREIGN KEY ("po_id") REFERENCES purchase_order("po_id")
);

CREATE TABLE inbound_effective (
  "po_line_id" TEXT NOT NULL,
  "po_id" TEXT NOT NULL,
  "supplier_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "credited_sku_id" TEXT,
  "base_qty" REAL,
  "effective_qty" REAL NOT NULL,
  "original_eta" TEXT NOT NULL,
  "effective_eta" TEXT NOT NULL,
  "effective_week_id" TEXT,
  "action" TEXT NOT NULL,
  "adjustments" TEXT,
  "exception_ids" TEXT,
  PRIMARY KEY (po_line_id),
  FOREIGN KEY ("po_line_id") REFERENCES purchase_order_line("po_line_id")
);

CREATE TABLE component_requirement (
  "requirement_id" TEXT NOT NULL,
  "production_plan_id" TEXT NOT NULL,
  "parent_sku_id" TEXT NOT NULL,
  "component_sku_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "week_id" TEXT NOT NULL,
  "required_qty" REAL NOT NULL,
  "uom" TEXT NOT NULL,
  PRIMARY KEY (requirement_id),
  FOREIGN KEY ("production_plan_id") REFERENCES production_plan("production_plan_id")
);

CREATE TABLE projected_balance (
  "projection_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "week_id" TEXT NOT NULL,
  "week_start_date" TEXT NOT NULL,
  "opening_qty" REAL NOT NULL,
  "receipts_po_qty" REAL NOT NULL,
  "receipts_production_qty" REAL NOT NULL,
  "forecast_qty" REAL NOT NULL,
  "dependent_demand_qty" REAL NOT NULL,
  "closing_qty" REAL NOT NULL,
  "safety_stock_qty" REAL NOT NULL,
  "below_safety_stock" INTEGER NOT NULL,
  "stockout" INTEGER NOT NULL,
  PRIMARY KEY (projection_id)
);

CREATE TABLE supplier_load (
  "capacity_id" TEXT NOT NULL,
  "supplier_id" TEXT NOT NULL,
  "week_id" TEXT NOT NULL,
  "load_units" REAL NOT NULL,
  "capacity_units" REAL NOT NULL,
  "utilisation" REAL NOT NULL,
  "is_exceeded" INTEGER NOT NULL,
  "scale_factor" REAL NOT NULL,
  PRIMARY KEY (capacity_id),
  FOREIGN KEY ("capacity_id") REFERENCES supplier_capacity("capacity_id")
);

CREATE TABLE exception_log (
  "exception_id" TEXT NOT NULL,
  "exception_type" TEXT NOT NULL,
  "entity_type" TEXT NOT NULL,
  "record_id" TEXT NOT NULL,
  "related_record_id" TEXT,
  "rule_id" TEXT NOT NULL,
  "decision" TEXT NOT NULL,
  "details" TEXT NOT NULL,
  "detected_at" TEXT NOT NULL,
  PRIMARY KEY (exception_id)
);

CREATE TABLE shortage (
  "shortage_id" TEXT NOT NULL,
  "sku_id" TEXT NOT NULL,
  "location_id" TEXT NOT NULL,
  "first_short_week_id" TEXT NOT NULL,
  "last_short_week_id" TEXT NOT NULL,
  "need_date" TEXT NOT NULL,
  "weeks_short" INTEGER NOT NULL,
  "shortage_qty" REAL NOT NULL,
  "uom" TEXT NOT NULL,
  "unit_cost" REAL NOT NULL,
  "value_at_risk" REAL NOT NULL,
  "abc_class" TEXT NOT NULL,
  "priority_score" REAL NOT NULL,
  "priority_rank" INTEGER NOT NULL,
  "priority_band" TEXT NOT NULL,
  "primary_cause" TEXT NOT NULL,
  "contributing_causes" TEXT NOT NULL,
  "cause_evidence" TEXT NOT NULL,
  "detected_at" TEXT NOT NULL,
  "on_time_mitigated_qty" REAL NOT NULL,
  "residual_qty" REAL NOT NULL,
  "shortage_status" TEXT NOT NULL,
  PRIMARY KEY (shortage_id)
);

CREATE TABLE shortage_event (
  "shortage_event_id" TEXT NOT NULL,
  "shortage_id" TEXT NOT NULL,
  "event_seq" INTEGER NOT NULL,
  "event_type" TEXT NOT NULL,
  "event_date" TEXT NOT NULL,
  "from_status" TEXT,
  "to_status" TEXT NOT NULL,
  "details" TEXT NOT NULL,
  PRIMARY KEY (shortage_event_id),
  FOREIGN KEY ("shortage_id") REFERENCES shortage("shortage_id")
);

CREATE TABLE mitigation_option (
  "mitigation_id" TEXT NOT NULL,
  "shortage_id" TEXT NOT NULL,
  "option_seq" INTEGER NOT NULL,
  "option_type" TEXT NOT NULL,
  "source_ref" TEXT NOT NULL,
  "source_location_id" TEXT,
  "supplier_id" TEXT,
  "substitute_sku_id" TEXT,
  "lead_time_days" INTEGER,
  "proposed_qty" REAL NOT NULL,
  "coverable_qty" REAL NOT NULL,
  "arrival_date" TEXT NOT NULL,
  "need_date" TEXT NOT NULL,
  "days_late" INTEGER NOT NULL,
  "on_time_qty" REAL NOT NULL,
  "incremental_cost" REAL NOT NULL,
  "cost_per_unit" REAL NOT NULL,
  "service_coverage_pct" REAL NOT NULL,
  "feasibility" TEXT NOT NULL,
  "policy_status" TEXT NOT NULL,
  "score" REAL NOT NULL,
  "rank" INTEGER,
  "is_recommended" INTEGER NOT NULL,
  "allocated_qty" REAL NOT NULL,
  "decision_reason" TEXT NOT NULL,
  PRIMARY KEY (mitigation_id),
  FOREIGN KEY ("shortage_id") REFERENCES shortage("shortage_id")
);

