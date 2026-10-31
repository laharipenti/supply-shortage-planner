"""End-to-end: the pipeline runs, validation passes, every anomaly is caught."""
import json

import pandas as pd

from ssp.schema import ANOMALY_TYPES, DERIVED_TABLES, INPUT_TABLES


def test_validation_passes(tiny_run):
    out, summary = tiny_run
    res = json.loads((out / "reports" / "validation_summary.json").read_text())
    failed = [c for c in res["checks"] if c["status"] != "PASS"]
    assert res["overall"] == "PASS", failed
    ids = {c["check_id"] for c in res["checks"]}
    # the categories demanded by Step 8 are all present
    for needed in ("V-PK", "V-FK", "V-ENUM", "V-DATE-01", "V-ARITH-01", "V-LIFE-02", "V-DUP", "V-GT-03"):
        assert needed in ids


def test_all_files_exported(tiny_run):
    out, _ = tiny_run
    for t in INPUT_TABLES:
        assert (out / "input" / f"{t}.csv").exists()
        assert (out / "json" / "input" / f"{t}.json").exists()
    for t in DERIVED_TABLES:
        assert (out / "derived" / f"{t}.csv").exists()
    for f in ("ground_truth/ground_truth.csv", "ground_truth/ground_truth.json", "sql/schema.sql", "sql/seed.sql",
              "manifest.json", "reports/evaluation.md", "reports/validation_summary.md"):
        assert (out / f).exists(), f


def test_every_anomaly_type_injected_and_detected(tiny_run, tiny_cfg):
    out, _ = tiny_run
    ev = json.loads((out / "reports" / "evaluation.json").read_text())
    for t in ANOMALY_TYPES:
        m = ev["anomaly_detection"]["by_type"][t]
        assert m["labelled"] == tiny_cfg.anomalies_per_type, t
        assert m["precision"] == 1.0 and m["recall"] == 1.0, (t, m)
        assert m["decision_accuracy"] == 1.0, (t, m)


def test_edge_cases_change_the_plan(tiny_run):
    """Each anomaly leads to a visible planner decision in inbound_effective / supplier_load."""
    out, _ = tiny_run
    ib = pd.read_csv(out / "derived" / "inbound_effective.csv", keep_default_na=False)
    gt = pd.read_csv(out / "ground_truth" / "ground_truth.csv", keep_default_na=False)
    lab = lambda t: set(gt.loc[gt.issue_type == t, "record_id"])
    assert set(ib.loc[ib.action == "EXCLUDED_DUPLICATE", "po_id"]) == lab("INBOUND_COUNTED_TWICE")
    assert set(ib.loc[ib.action == "EXCLUDED_UOM_MISMATCH", "po_line_id"]) == lab("UOM_MISMATCH")
    assert set(ib.loc[ib.action == "EXCLUDED_UNAPPROVED_SUBSTITUTE", "po_line_id"]) == lab("SUBSTITUTE_NOT_APPROVED")
    assert set(ib.loc[ib.adjustments.str.contains("REDATED_LEAD_TIME"), "po_id"]) == lab("SHORTAGE_WITHOUT_LEAD_TIME")
    sl = pd.read_csv(out / "derived" / "supplier_load.csv")
    assert set(sl.loc[sl.is_exceeded, "capacity_id"]) == lab("SUPPLIER_CAPACITY_EXCEEDED")


def test_required_scenarios_present(tiny_run):
    out, _ = tiny_run
    gt = pd.read_csv(out / "ground_truth" / "ground_truth.csv")
    for s in ("DEMAND_SPIKE", "CONSTRAINED_SUPPLIER", "SUBSTITUTE_SKU", "TRANSPORT_DELAY"):
        assert (gt.issue_type == s).sum() > 0, s
