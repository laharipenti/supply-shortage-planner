"""Mitigations respect policy, lead time and capacity; alternatives show cost/service trade-offs."""
import pandas as pd

AS_OF = pd.Timestamp("2025-12-29")


def load(out):
    r = lambda layer, t: pd.read_csv(out / layer / f"{t}.csv", keep_default_na=False)
    return r("derived", "mitigation_option"), r("derived", "shortage"), r


def test_recommended_options_are_policy_compliant(tiny_run):
    out, _ = tiny_run
    mo, sh, r = load(out)
    rec = mo[mo.is_recommended == "true"] if mo.is_recommended.dtype == object else mo[mo.is_recommended]
    assert len(rec) > 0
    assert (rec.policy_status == "OK").all()
    sub = r("input", "sku_substitute").set_index("substitute_id")
    s = rec[rec.option_type == "SUBSTITUTE"]
    assert (s.source_ref.map(sub.approval_status) == "APPROVED").all()
    sup = r("input", "supplier").set_index("supplier_id")
    n = rec[rec.option_type == "NEW_PO"]
    assert (n.supplier_id.map(sup.supplier_status) == "ACTIVE").all()


def test_new_po_respects_lead_time(tiny_run):
    out, _ = tiny_run
    mo, _, _ = load(out)
    n = mo[mo.option_type == "NEW_PO"]
    arrival = pd.to_datetime(n.arrival_date)
    lt = pd.to_numeric(n.lead_time_days)
    assert ((arrival - AS_OF).dt.days == lt).all()   # never earlier than the supplier lead time


def test_unapproved_substitutes_are_rejected_not_recommended(tiny_run):
    out, _ = tiny_run
    mo, _, r = load(out)
    sub = r("input", "sku_substitute").set_index("substitute_id")
    s = mo[mo.option_type == "SUBSTITUTE"]
    bad = s[s.source_ref.map(sub.approval_status) != "APPROVED"]
    assert (bad.policy_status == "REJECTED_SUBSTITUTE_NOT_APPROVED").all()
    assert (bad.is_recommended.astype(str).str.lower() != "true").all()


def test_allocation_never_exceeds_shortage(tiny_run):
    out, _ = tiny_run
    mo, sh, _ = load(out)
    alloc = pd.to_numeric(mo.allocated_qty).groupby(mo.shortage_id).sum()
    qty = pd.to_numeric(sh.set_index("shortage_id").shortage_qty)
    assert (alloc <= qty.reindex(alloc.index) + 1e-6).all()


def test_alternatives_show_cost_and_service(tiny_run):
    out, _ = tiny_run
    mo, sh, _ = load(out)
    for c in ("incremental_cost", "cost_per_unit", "service_coverage_pct", "days_late", "feasibility", "score"):
        assert (mo[c] != "").all(), c
    # several option types exist so there is a real trade-off to show
    assert mo.option_type.nunique() >= 3
