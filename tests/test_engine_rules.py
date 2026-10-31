"""Unit tests for individual planner rules on hand-modified copies of the tiny data."""
import pandas as pd
import pytest

from ssp.engine import prepare_inbound, run_planning
from ssp.io import read_layer
from ssp.schema import INPUT_TABLES


@pytest.fixture()
def inputs(tiny_run):
    out, _ = tiny_run
    return read_layer(out / "input", INPUT_TABLES)


def _clean_line(t):
    """a line on a live, untouched PO with an EA SKU ordered in EA/CS"""
    L = prepare_inbound(t, 52)
    ok = L[(L.action == "INCLUDED") & ~L.redated & ~L.delayed & (L.base_uom == "EA") & ~L.is_sub & L.in_horizon]
    return ok.iloc[0]


def test_uom_mismatch_is_quarantined(inputs):
    line = _clean_line(inputs)
    pol = inputs["purchase_order_line"]
    pol.loc[pol.po_line_id == line.po_line_id, "uom"] = "KG"
    L = prepare_inbound(inputs, 52)
    assert L.set_index("po_line_id").at[line.po_line_id, "action"] == "EXCLUDED_UOM_MISMATCH"


def test_case_quantities_are_converted(inputs):
    L = prepare_inbound(inputs, 52)
    cs = L[(L.uom == "CS") & L.uom_ok].iloc[0]
    assert cs.base_qty == cs.order_qty * cs.upc


def test_duplicate_supplier_ref_counted_once(inputs):
    line = _clean_line(inputs)
    po = inputs["purchase_order"]
    src = po[po.po_id == line.po_id].copy()
    src["po_id"] = "PO-2026-999999"
    inputs["purchase_order"] = pd.concat([po, src], ignore_index=True)
    pol = inputs["purchase_order_line"]
    ln = pol[pol.po_id == line.po_id].copy()
    ln["po_id"] = "PO-2026-999999"
    ln["po_line_id"] = "PO-2026-999999-" + ln.po_line_id.str[-3:]
    inputs["purchase_order_line"] = pd.concat([pol, ln], ignore_index=True)
    ev = inputs["po_event"]
    e = ev[ev.po_id == line.po_id].copy()
    e["po_id"] = "PO-2026-999999"
    e["event_id"] = "EVT-PO-2026-999999-" + e.event_id.str[-2:]
    inputs["po_event"] = pd.concat([ev, e], ignore_index=True)
    L = prepare_inbound(inputs, 52).set_index("po_line_id")
    assert (L.loc[ln.po_line_id, "action"] == "EXCLUDED_DUPLICATE").all()
    assert L.at[line.po_line_id, "action"] == "INCLUDED"


def test_receipt_redated_to_lead_time(inputs):
    line = _clean_line(inputs)
    po = inputs["purchase_order"]
    m = po.po_id == line.po_id
    po.loc[m, "order_date"] = po.loc[m, "expected_receipt_date"] - pd.Timedelta(days=1)
    L = prepare_inbound(inputs, 52).set_index("po_line_id")
    r = L.loc[line.po_line_id]
    assert r.lt_violation and r.redated
    assert r.effective_eta == r.order_date + pd.Timedelta(days=int(r.lead_time_days))


def test_capacity_breach_scales_receipts(inputs):
    line = _clean_line(inputs)
    cap = inputs["supplier_capacity"]
    wk = f"2026W{int(line.eff_week) + 1:02d}"
    m = (cap.supplier_id == line.supplier_id) & (cap.week_id == wk)
    cap.loc[m, "capacity_units"] = 1.0
    d = run_planning(inputs, 52)
    ib = d["inbound_effective"].set_index("po_line_id")
    assert "SCALED_CAPACITY" in ib.at[line.po_line_id, "adjustments"]
    assert ib.at[line.po_line_id, "effective_qty"] <= 1.0
    assert (d["exception_log"].exception_type == "SUPPLIER_CAPACITY_EXCEEDED").any()


def test_cancelled_po_not_counted(inputs):
    L = prepare_inbound(inputs, 52)
    c = L[L.derived_status == "CANCELLED"]
    assert len(c) > 0 and (c.action == "EXCLUDED_CANCELLED").all()
