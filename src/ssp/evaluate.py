"""Evaluation metrics: compares planner output with the separate ground truth.

1. Anomaly detection  : precision / recall / F1 / decision accuracy per issue type
2. Cause attribution  : for each labelled scenario that produced a shortage, did the
                        planner name the expected cause?
3. Planning KPIs      : shortages, value at risk, projected service level
4. Mitigation KPIs    : coverage, cost, escalations, policy violations, trade-off table
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .io import read_layer
from .schema import ANOMALY_TYPES, DERIVED_TABLES, INPUT_TABLES

SCENARIO_CAUSE = {
    "DEMAND_SPIKE": "DEMAND_SPIKE",
    "TRANSPORT_DELAY": "TRANSPORT_DELAY",
    "SUPPLIER_DELAY": "SUPPLIER_DELAY",
    "PRODUCTION_CONSTRAINED": "PRODUCTION_SHORTFALL",
    "SUPPLIER_CAPACITY_EXCEEDED": "SUPPLIER_CAPACITY",
    "SHORTAGE_WITHOUT_LEAD_TIME": "LEAD_TIME_CORRECTION",
    "SUBSTITUTE_NOT_APPROVED": "SUPPLY_EXCLUDED",
    "UOM_MISMATCH": "SUPPLY_EXCLUDED",
    "PO_CANCELLED": "SUPPLY_EXCLUDED",
    "UNDER_REPLENISHED": "INSUFFICIENT_REPLENISHMENT",
    "LOW_OPENING_STOCK": "INSUFFICIENT_OPENING_STOCK",
}


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 4), round(r, 4), round(f, 4)


def evaluate(out: Path) -> dict:
    out = Path(out)
    i = read_layer(out / "input", INPUT_TABLES)
    d = read_layer(out / "derived", DERIVED_TABLES)
    gt = read_layer(out / "ground_truth", ["ground_truth"])["ground_truth"]
    exc, sh, mo, p, ib = d["exception_log"], d["shortage"], d["mitigation_option"], d["projected_balance"], d["inbound_effective"]
    res: dict = {}

    # 1 ---- anomaly detection
    det = {}
    for t in ANOMALY_TYPES:
        lab = gt[gt["issue_type"] == t].set_index("record_id")["expected_decision"]
        found = exc[exc["exception_type"] == t].set_index("record_id")["decision"]
        tp = len(set(lab.index) & set(found.index))
        fp = len(set(found.index) - set(lab.index))
        fn = len(set(lab.index) - set(found.index))
        pr, rc, f1 = _prf(tp, fp, fn)
        both = sorted(set(lab.index) & set(found.index))
        acc = round(float(np.mean([lab[k] == found[k] for k in both])), 4) if both else None
        det[t] = dict(labelled=len(lab), detected=len(found), tp=tp, fp=fp, fn=fn, precision=pr, recall=rc, f1=f1,
                      decision_accuracy=acc)
    tot = {k: sum(v[k] for v in det.values()) for k in ("tp", "fp", "fn")}
    res["anomaly_detection"] = dict(by_type=det, micro=dict(zip(("precision", "recall", "f1"), _prf(**tot))), **tot)

    # 2 ---- cause attribution vs scenarios
    sh = sh.copy()
    sh["f"] = sh["first_short_week_id"].str[-2:].astype(int) - 1
    sh["l"] = sh["last_short_week_id"].str[-2:].astype(int) - 1
    sh["causes"] = sh["contributing_causes"].str.split(";")
    by_sl = {k: g for k, g in sh.groupby(["sku_id", "location_id"])}
    po = i["purchase_order"].set_index("po_id")
    attr = {}

    def episodes_for(sku, loc, week_lo=None, week_hi=None):
        g = by_sl.get((sku, loc))
        if g is None:
            return g
        if week_lo is not None:
            g = g[(g["l"] >= week_lo) & (g["f"] - 4 <= week_hi)]
        return g

    # build (scenario -> list of affected shortage frames)
    cases = {k: [] for k in SCENARIO_CAUSE}
    for r in gt.itertuples():
        if r.issue_type == "DEMAND_SPIKE":
            sku, loc = r.related_record_id.split("@")
            w = int(r.record_id[-2:]) - 1
            cases["DEMAND_SPIKE"].append((r.record_id, episodes_for(sku, loc, w, w)))
        elif r.issue_type in ("TRANSPORT_DELAY", "SUPPLIER_DELAY", "SHORTAGE_WITHOUT_LEAD_TIME"):
            lines = ib[(ib["po_id"] == r.record_id) & (ib["action"] == "INCLUDED")]
            for ln in lines.itertuples():
                ow = (ln.original_eta - pd.Timestamp("2025-12-29")).days // 7
                ew = (ln.effective_eta - pd.Timestamp("2025-12-29")).days // 7
                g = by_sl.get((ln.credited_sku_id, ln.location_id))
                if g is not None:
                    g = g[(g["f"] <= ew) & (g["l"] >= ow)]
                cases[r.issue_type].append((ln.po_line_id, g))
        elif r.issue_type == "PRODUCTION_CONSTRAINED":
            sku, loc = r.record_id[3:13], r.record_id[14:]
            cases[r.issue_type].append((r.record_id, by_sl.get((sku, loc))))
        elif r.issue_type == "SUPPLIER_CAPACITY_EXCEEDED":
            lines = ib[ib["adjustments"].str.contains("SCALED_CAPACITY")]
            wk = r.record_id[-7:]
            lines = lines[(lines["supplier_id"] == r.related_record_id) & (lines["effective_week_id"] == wk)]
            for ln in lines.itertuples():
                w = int(wk[-2:]) - 1
                g = by_sl.get((ln.credited_sku_id, ln.location_id))
                if g is not None:
                    g = g[g["l"] >= w]
                cases[r.issue_type].append((ln.po_line_id, g))
        elif r.issue_type == "PO_CANCELLED":
            pl = i["purchase_order_line"]
            for ln in ib[ib["po_id"] == r.record_id].itertuples():
                sf = pl.loc[pl["po_line_id"] == ln.po_line_id, "substitute_for_sku_id"].iloc[0]
                ow = (ln.original_eta - pd.Timestamp("2025-12-29")).days // 7
                g = by_sl.get((sf or ln.sku_id, ln.location_id))
                if g is not None:
                    g = g[g["l"] >= ow]
                cases[r.issue_type].append((ln.po_line_id, g))
        elif r.issue_type == "UNDER_REPLENISHED":
            cases[r.issue_type].append((r.record_id, by_sl.get((r.record_id[3:13], r.record_id[14:]))))
        elif r.issue_type == "LOW_OPENING_STOCK":
            sku, loc = r.record_id[4:14], r.record_id[15:23]
            first_rcpt = ib[(ib["credited_sku_id"] == sku) & (ib["location_id"] == loc) & (ib["effective_week_id"] != "")]
            fw = int(first_rcpt["effective_week_id"].min()[-2:]) - 1 if len(first_rcpt) else 52
            g = by_sl.get((sku, loc))
            if g is not None:
                g = g[g["f"] < fw]
            cases[r.issue_type].append((r.record_id, g))
        elif r.issue_type in ("SUBSTITUTE_NOT_APPROVED", "UOM_MISMATCH"):
            ln = ib[ib["po_line_id"] == r.record_id].iloc[0]
            intended = r.related_record_id if r.issue_type == "UOM_MISMATCH" else \
                i["purchase_order_line"].set_index("po_line_id").at[r.record_id, "substitute_for_sku_id"]
            ow = (ln.original_eta - pd.Timestamp("2025-12-29")).days // 7
            g = by_sl.get((intended, ln.location_id))
            if g is not None:
                g = g[g["l"] >= ow]
            cases[r.issue_type].append((r.record_id, g))
    explained_by = {}
    for sc, items in cases.items():
        cause = SCENARIO_CAUSE[sc]
        with_short = [(k, g) for k, g in items if g is not None and len(g)]
        hit = sum(any(cause in c for c in g["causes"]) for _, g in with_short)
        explained_by.setdefault(cause, set()).update(sid for _, g in with_short for sid in g["shortage_id"])
        attr[sc] = dict(expected_cause=cause, labelled=len(items), led_to_shortage=len(with_short),
                        cause_identified=hit,
                        cause_recall=round(hit / len(with_short), 4) if with_short else None)
    # precision: of the shortages where the planner named a cause, how many are backed by a label?
    prec = {}
    for cause, ok in sorted(explained_by.items()):
        named = set(sh.loc[sh["causes"].map(lambda c: cause in c), "shortage_id"])
        prec[cause] = dict(shortages_naming_cause=len(named), backed_by_label=len(named & ok),
                           cause_precision=round(len(named & ok) / len(named), 4) if named else None)
    res["cause_attribution"] = attr
    res["cause_precision"] = prec

    # 3 ---- planning KPIs
    n_sl = p.groupby(["sku_id", "location_id"]).ngroups
    req = (p["forecast_qty"] + p["dependent_demand_qty"]).sum()
    res["planning"] = dict(
        sku_locations=n_sl, sku_location_weeks=len(p),
        stockout_week_share=round(float(p["stockout"].mean()), 4),
        below_safety_stock_week_share=round(float(p["below_safety_stock"].mean()), 4),
        sku_locations_with_shortage=int(sh.groupby(["sku_id", "location_id"]).ngroups),
        shortage_episodes=len(sh), shortage_units=round(float(sh["shortage_qty"].sum()), 2),
        value_at_risk_usd=round(float(sh["value_at_risk"].sum()), 2),
        by_priority_band=sh["priority_band"].value_counts().sort_index().to_dict(),
        by_primary_cause=sh["primary_cause"].value_counts().to_dict(),
        inbound_lines=len(ib), inbound_actions=ib["action"].value_counts().to_dict(),
        total_requirement_units=round(float(req), 2))

    # 4 ---- mitigation KPIs
    rec = mo[mo["is_recommended"]]
    elig = mo[(mo["policy_status"] == "OK") & (mo["coverable_qty"] > 0)]
    tradeoff = (mo[mo["coverable_qty"] > 0].groupby("option_type")
                .agg(options=("mitigation_id", "count"), recommended=("is_recommended", "sum"),
                     avg_cost_per_unit=("cost_per_unit", "mean"), avg_on_time_pct=("service_coverage_pct", "mean"),
                     avg_days_late=("days_late", "mean")).round(2))
    res["mitigation"] = dict(
        options_generated=len(mo), options_policy_rejected=mo["policy_status"].ne("OK").sum().item(),
        rejected_by_reason=mo.loc[mo["policy_status"] != "OK", "policy_status"].value_counts().to_dict(),
        shortages_with_eligible_option=round(float(sh["shortage_id"].isin(elig["shortage_id"]).mean()), 4) if len(sh) else None,
        shortage_units_covered_on_time_pct=round(100 * float(sh["on_time_mitigated_qty"].sum() / max(sh["shortage_qty"].sum(), 1e-9)), 2),
        shortages_fully_mitigated=int((sh["residual_qty"] <= 0).sum()),
        shortages_escalated=int((sh["shortage_status"] == "ESCALATED").sum()),
        p1_fully_mitigated_pct=round(100 * float((sh.loc[sh["priority_band"] == "P1", "residual_qty"] <= 0).mean()), 2) if len(sh) else None,
        recommended_incremental_cost_usd=round(float((rec["cost_per_unit"] * rec["allocated_qty"]).sum()), 2),
        recommended_policy_violations=int((rec["policy_status"] != "OK").sum()),
        tradeoff_by_option_type=tradeoff.reset_index().to_dict(orient="records"))
    return res


def to_markdown(res: dict) -> str:
    L = ["# Evaluation report\n", "## 1. Anomaly detection (planner exceptions vs ground_truth)\n",
         "| issue type | labelled | detected | TP | FP | FN | precision | recall | F1 | decision accuracy |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["anomaly_detection"]["by_type"].items():
        L.append(f"| {k} | {v['labelled']} | {v['detected']} | {v['tp']} | {v['fp']} | {v['fn']} | {v['precision']} | "
                 f"{v['recall']} | {v['f1']} | {v['decision_accuracy']} |")
    m = res["anomaly_detection"]["micro"]
    L += [f"\nMicro average: precision {m['precision']}, recall {m['recall']}, F1 {m['f1']}\n",
          "## 2. Cause attribution (did the planner explain labelled scenarios correctly?)\n",
          "| scenario / anomaly | expected cause | labelled | led to shortage | cause identified | recall |",
          "|---|---|---|---|---|---|"]
    for k, v in res["cause_attribution"].items():
        L.append(f"| {k} | {v['expected_cause']} | {v['labelled']} | {v['led_to_shortage']} | {v['cause_identified']} | {v['cause_recall']} |")
    L += ["\nCause precision (shortages naming a cause that is backed by a ground-truth label; unlabelled causes are "
          "real data effects such as seasonal peaks, cancelled POs or natural noise):\n",
          "| cause | shortages naming it | backed by label | precision |", "|---|---|---|---|"]
    for k, v in res["cause_precision"].items():
        L.append(f"| {k} | {v['shortages_naming_cause']} | {v['backed_by_label']} | {v['cause_precision']} |")
    L += ["\n## 3. Planning KPIs\n"] + [f"- **{k}**: {v}" for k, v in res["planning"].items()]
    mit = dict(res["mitigation"])
    tr = mit.pop("tradeoff_by_option_type")
    L += ["\n## 4. Mitigation KPIs\n"] + [f"- **{k}**: {v}" for k, v in mit.items()]
    L += ["\n### Cost vs service trade-off by option type\n",
          "| option | options | recommended | avg cost/unit (USD) | avg on-time % | avg days late |", "|---|---|---|---|---|---|"]
    for r in tr:
        L.append(f"| {r['option_type']} | {r['options']} | {r['recommended']} | {r['avg_cost_per_unit']} | "
                 f"{r['avg_on_time_pct']} | {r['avg_days_late']} |")
    return "\n".join(L) + "\n"
