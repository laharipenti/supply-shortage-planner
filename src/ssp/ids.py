"""Deterministic, zero-padded, immutable ID builders.

Brief conventions: SKU-000001; DEM-<sku>-<location>-2026W01; PO-2026-000001;
SHORT-2026-000001; MIT-<shortage-id>-01. Other IDs follow the same style.
"""


def sku_id(n: int) -> str:
    return f"SKU-{n:06d}"


def loc_id(n: int) -> str:
    return f"LOC-{n:04d}"


def sup_id(n: int) -> str:
    return f"SUP-{n:04d}"


def po_id(n: int) -> str:
    return f"PO-2026-{n:06d}"


def po_line_id(po: str, line_no: int) -> str:
    return f"{po}-L{line_no:02d}"


def po_event_id(po: str, seq: int) -> str:
    return f"EVT-{po}-{seq:02d}"


def demand_id(sku: str, loc: str, week: str) -> str:
    return f"DEM-{sku}-{loc}-{week}"


def sku_location_id(sku: str, loc: str) -> str:
    return f"SL-{sku}-{loc}"


def inventory_id(sku: str, loc: str, snapshot_yyyymmdd: str) -> str:
    return f"INV-{sku}-{loc}-{snapshot_yyyymmdd}"


def substitute_id(sku: str, sub: str) -> str:
    return f"SUB-{sku}-{sub}"


def supplier_sku_id(sup: str, sku: str) -> str:
    return f"SS-{sup}-{sku}"


def lead_time_id(sup: str, sku: str, version: int) -> str:
    return f"LT-{sup}-{sku}-V{version}"


def capacity_id(sup: str, week: str) -> str:
    return f"CAP-{sup}-{week}"


def prod_capacity_id(loc: str, week: str) -> str:
    return f"PCAP-{loc}-{week}"


def production_plan_id(n: int) -> str:
    return f"PP-2026-{n:06d}"


def bom_id(parent: str, component: str) -> str:
    return f"BOM-{parent}-{component}"


def shortage_id(n: int) -> str:
    return f"SHORT-2026-{n:06d}"


def mitigation_id(short: str, seq: int) -> str:
    return f"MIT-{short}-{seq:02d}"


def shortage_event_id(short: str, seq: int) -> str:
    return f"SEV-{short}-{seq:02d}"


def exception_id(n: int) -> str:
    return f"EXC-2026-{n:06d}"


def projection_id(sku: str, loc: str, week: str) -> str:
    return f"PAB-{sku}-{loc}-{week}"


def requirement_id(pp: str, component: str) -> str:
    return f"CREQ-{pp}-{component}"


def gt_id(n: int) -> str:
    return f"GT-{n:06d}"
