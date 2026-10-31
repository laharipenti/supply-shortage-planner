"""IDs, keys, reconciliation and lifecycle checks re-implemented independently of validate.py."""
import re

import numpy as np
import pandas as pd

R = lambda out, layer, t: pd.read_csv(out / layer / f"{t}.csv", keep_default_na=False)


def test_id_conventions(tiny_run):
    out, _ = tiny_run
    assert R(out, "input", "sku").sku_id.str.fullmatch(r"SKU-\d{6}").all()
    fd = R(out, "input", "forecast_demand")
    assert (fd.demand_id == "DEM-" + fd.sku_id + "-" + fd.location_id + "-" + fd.week_id).all()
    assert fd.week_id.str.fullmatch(r"2026W\d{2}").all()
    assert R(out, "input", "purchase_order").po_id.str.fullmatch(r"PO-2026-\d{6}").all()
    sh = R(out, "derived", "shortage")
    assert sh.shortage_id.str.fullmatch(r"SHORT-2026-\d{6}").all()
    mo = R(out, "derived", "mitigation_option")
    assert mo.mitigation_id.str.fullmatch(r"MIT-SHORT-2026-\d{6}-\d{2}").all()
    assert (mo.mitigation_id.str[4:21] == mo.shortage_id).all()


def test_primary_and_foreign_keys(tiny_run):
    out, _ = tiny_run
    sku = set(R(out, "input", "sku").sku_id)
    loc = set(R(out, "input", "location").location_id)
    po = R(out, "input", "purchase_order")
    pol = R(out, "input", "purchase_order_line")
    assert po.po_id.is_unique and pol.po_line_id.is_unique
    assert pol.po_id.isin(po.po_id).all() and pol.sku_id.isin(sku).all()
    assert po.location_id.isin(loc).all()
    fd = R(out, "input", "forecast_demand")
    assert fd.sku_id.isin(sku).all() and fd.location_id.isin(loc).all()


def test_projection_reconciles_week_by_week(tiny_run):
    out, _ = tiny_run
    p = R(out, "derived", "projected_balance").sort_values(["sku_id", "location_id", "week_id"])
    num = lambda c: pd.to_numeric(p[c])
    calc = num("opening_qty") + num("receipts_po_qty") + num("receipts_production_qty") - num("forecast_qty") - num("dependent_demand_qty")
    assert np.allclose(calc, num("closing_qty"), atol=0.011)
    prev = num("closing_qty").groupby([p.sku_id, p.location_id]).shift()
    m = prev.notna()
    assert np.allclose(prev[m], num("opening_qty")[m], atol=0.011)


def test_po_history_is_append_only(tiny_run):
    out, _ = tiny_run
    po = R(out, "input", "purchase_order").set_index("po_id")
    ev = R(out, "input", "po_event")
    last = ev.sort_values(["po_id", "event_seq"]).groupby("po_id").tail(1).set_index("po_id")
    assert (po.po_status == last.to_status.reindex(po.index)).all()
    delayed = ev[ev.event_type == "DELAYED"]
    assert len(delayed) > 0
    # original expected_receipt_date is kept; the delay lives in the event
    for r in delayed.itertuples():
        assert r.revised_eta > po.at[r.po_id, "expected_receipt_date"]


def test_shortages_explainable(tiny_run):
    out, _ = tiny_run
    sh = R(out, "derived", "shortage")
    assert len(sh) > 0
    assert (sh.primary_cause != "").all() and (sh.cause_evidence != "").all()
    assert all(p in c.split(";") for p, c in zip(sh.primary_cause, sh.contributing_causes))


def test_realistic_variation(tiny_run):
    out, _ = tiny_run
    fd = R(out, "input", "forecast_demand")
    q = pd.to_numeric(fd.forecast_qty)
    per = q.groupby(fd.sku_id).mean()
    assert per.std() / per.mean() > 0.5          # heterogeneous SKU volumes
    assert (q == 0).mean() < 0.5                  # not mostly empty
    sku = R(out, "input", "sku")
    assert set(sku.abc_class) == {"A", "B", "C"}
    assert set(sku.sku_type) == {"FINISHED", "MANUFACTURED", "COMPONENT"}
