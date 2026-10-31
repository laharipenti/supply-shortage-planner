"""Step 8: validation suite. Reads the exported CSVs (what a reviewer would see).

Each check -> {check_id, category, table, description, status, violations, sample}.
status: PASS | FAIL. Anomaly-related checks PASS only when every rule violation
is a labelled anomaly in ground_truth AND every labelled anomaly is a real violation.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .config import AS_OF, week_id, week_start
from .io import read_layer
from .schema import ANOMALY_TYPES, DERIVED_TABLES, INPUT_TABLES, TABLES

AS_OF_TS = pd.Timestamp(AS_OF)
PO_TRANSITIONS = {("", "CREATED"), ("CREATED", "CONFIRMED"), ("CREATED", "CANCELLED"), ("CONFIRMED", "IN_TRANSIT"),
                  ("CONFIRMED", "DELAYED"), ("CONFIRMED", "CANCELLED"), ("IN_TRANSIT", "DELAYED"),
                  ("DELAYED", "DELAYED"), ("DELAYED", "IN_TRANSIT")}
SHORT_TRANSITIONS = {("", "DETECTED"), ("DETECTED", "PRIORITIZED"), ("PRIORITIZED", "MITIGATION_PROPOSED"),
                     ("PRIORITIZED", "ESCALATED"), ("MITIGATION_PROPOSED", "ESCALATED")}
TOL = 0.011


class Validator:
    def __init__(self, out: Path):
        self.out = Path(out)
        self.i = read_layer(self.out / "input", INPUT_TABLES)
        self.d = read_layer(self.out / "derived", DERIVED_TABLES)
        self.g = read_layer(self.out / "ground_truth", ["ground_truth"])["ground_truth"]
        self.all = {**self.i, **self.d, "ground_truth": self.g}
        self.checks: list[dict] = []
        self.W = self.i["forecast_demand"]["week_id"].nunique() or 52

    def add(self, cid, cat, table, desc, bad, labelled_ok=False):
        bad = list(bad)
        self.checks.append(dict(check_id=cid, category=cat, table=table, description=desc,
                                status="PASS" if not bad else "FAIL", violations=len(bad),
                                sample=[str(b) for b in bad[:5]], labelled_ok=labelled_ok))

    def gt_ids(self, issue):
        return set(self.g.loc[self.g["issue_type"] == issue, "record_id"])

    # ------------------------------------------------------------------ run
    def run(self) -> dict:
        self.schema_checks()
        self.date_checks()
        self.lifecycle_checks()
        self.reference_checks()
        self.arithmetic_checks()
        self.shortage_mitigation_checks()
        self.ground_truth_checks()
        n_fail = sum(c["status"] == "FAIL" for c in self.checks)
        return dict(overall="PASS" if n_fail == 0 else "FAIL", n_checks=len(self.checks), n_failed=n_fail,
                    checks=self.checks)

    # ------------------------------------------------------------------ generic schema checks
    def schema_checks(self):
        for name, df in self.all.items():
            t = TABLES[name]
            pk = list(t.pk)
            self.add("V-PK", "primary_key", name, f"{'+'.join(pk)} unique and non-empty",
                     df.loc[df.duplicated(pk, keep=False) | (df[pk[0]] == ""), pk[0]])
            for cols in t.unique_together:
                self.add("V-UNIQ", "uniqueness", name, f"({', '.join(cols)}) unique",
                         df.loc[df.duplicated(list(cols), keep=False), pk[0]])
            req_bad, enum_bad, pat_bad, rng_bad = [], [], [], []
            for f in t.fields:
                s = df[f.name]
                empty = s.isna() if f.type in ("int", "decimal", "date") else (s == "")
                if f.required:
                    req_bad += [f"{r}.{f.name}" for r in df.loc[empty, pk[0]]]
                if f.allowed is not None:
                    bad = ~s.isin(f.allowed) & ~empty
                    enum_bad += [f"{r}.{f.name}={v}" for r, v in zip(df.loc[bad, pk[0]], s[bad])]
                if f.pattern:
                    rx = re.compile(f.pattern)
                    bad = ~empty & ~s.astype(str).map(lambda v: bool(rx.match(v)))
                    pat_bad += [f"{r}.{f.name}" for r in df.loc[bad, pk[0]]]
                if f.min is not None:
                    bad = s.notna() & (s < f.min - 1e-9)
                    rng_bad += [f"{r}.{f.name}<{f.min}" for r in df.loc[bad, pk[0]]]
                if f.max is not None:
                    bad = s.notna() & (s > f.max + 1e-9)
                    rng_bad += [f"{r}.{f.name}>{f.max}" for r in df.loc[bad, pk[0]]]
            self.add("V-REQ", "required", name, "required fields populated", req_bad)
            self.add("V-ENUM", "allowed_values", name, "values within allowed enums", enum_bad)
            self.add("V-ID", "id_format", name, "IDs match naming convention", pat_bad)
            self.add("V-RANGE", "ranges", name, "numeric values within min/max", rng_bad)
            for col, ref, rcol in t.fks:
                vals = df[col]
                ok = vals.isin(set(self.all[ref][rcol])) | (vals == "")
                self.add("V-FK", "foreign_key", name, f"{col} -> {ref}.{rcol}", df.loc[~ok, pk[0]])
            # duplicate rows ignoring the PK (business duplicates)
            other = [c for c in t.columns if c not in pk]
            if name == "purchase_order":
                key = ["supplier_id", "location_id", "supplier_ref", "order_date", "expected_receipt_date"]
                d = df[df.duplicated(key, keep="first")]["po_id"]
                lab = self.gt_ids("INBOUND_COUNTED_TWICE")
                self.add("V-DUP", "duplicates", name, "duplicate inbound orders are all labelled anomalies",
                         sorted(set(d) ^ lab), labelled_ok=True)
            elif t.layer == "input":
                self.add("V-DUP", "duplicates", name, "no duplicate business rows", df.loc[df.duplicated(other, keep=False), pk[0]])

    # ------------------------------------------------------------------ dates
    def date_checks(self):
        po, lt, ev, fd = self.i["purchase_order"], self.i["lead_time"], self.i["po_event"], self.i["forecast_demand"]
        self.add("V-DATE-01", "date_order", "purchase_order", "order_date < expected_receipt_date",
                 po.loc[po["order_date"] >= po["expected_receipt_date"], "po_id"])
        self.add("V-DATE-02", "date_order", "lead_time", "effective_from <= effective_to",
                 lt.loc[lt["effective_to"].notna() & (lt["effective_to"] < lt["effective_from"]), "lead_time_id"])
        bad = []
        for (s, k), g in lt.sort_values("version").groupby(["supplier_id", "sku_id"]):
            for a, b in zip(g.itertuples(), list(g.itertuples())[1:]):
                if pd.isna(a.effective_to) or a.effective_to + pd.Timedelta(days=1) != b.effective_from:
                    bad.append(b.lead_time_id)
            if pd.notna(g.iloc[-1]["effective_to"]):
                bad.append(g.iloc[-1]["lead_time_id"])
        self.add("V-DATE-03", "effective_dates", "lead_time", "versions contiguous, non-overlapping, latest open", bad)
        e = ev.sort_values(["po_id", "event_seq"])
        prev = e.groupby("po_id")["event_date"].shift()
        self.add("V-DATE-04", "date_order", "po_event", "event dates non-decreasing and <= as-of date",
                 e.loc[(prev.notna() & (e["event_date"] < prev)) | (e["event_date"] > AS_OF_TS), "event_id"])
        dl = e[e["event_type"] == "DELAYED"]
        self.add("V-DATE-05", "date_order", "po_event", "DELAYED events carry revised_eta > event_date",
                 dl.loc[dl["revised_eta"].isna() | (dl["revised_eta"] <= dl["event_date"]), "event_id"])
        wk = {week_id(i): pd.Timestamp(week_start(i)) for i in range(52)}
        bad = []
        for name in ("forecast_demand", "supplier_capacity", "production_plan", "production_capacity"):
            df = self.i[name]
            m = df["week_id"].map(wk) != df["week_start_date"]
            bad += list(df.loc[m, TABLES[name].pk[0]])
        self.add("V-DATE-06", "calendar", "*", "week_start_date matches ISO week_id", bad)
        sub = self.i["sku_substitute"]
        self.add("V-DATE-07", "effective_dates", "sku_substitute", "effective_to after effective_from",
                 sub.loc[sub["effective_to"].notna() & (sub["effective_to"] <= sub["effective_from"]), "substitute_id"])

    # ------------------------------------------------------------------ lifecycle
    def lifecycle_checks(self):
        e = self.i["po_event"].sort_values(["po_id", "event_seq"])
        bad_seq, bad_tr = [], []
        for po, g in e.groupby("po_id"):
            if list(g["event_seq"].astype(int)) != list(range(1, len(g) + 1)) or g.iloc[0]["event_type"] != "CREATED":
                bad_seq.append(po)
            prev = ""
            for r in g.itertuples():
                if r.from_status != prev or (r.from_status, r.to_status) not in PO_TRANSITIONS:
                    bad_tr.append(r.event_id)
                prev = r.to_status
        self.add("V-LIFE-01", "lifecycle", "po_event", "event_seq contiguous from 1, starts with CREATED", bad_seq)
        self.add("V-LIFE-02", "lifecycle", "po_event", "only allowed PO status transitions, from_status chains", bad_tr)
        last = e.groupby("po_id").tail(1).set_index("po_id")["to_status"]
        po = self.i["purchase_order"]
        self.add("V-LIFE-03", "lifecycle", "purchase_order", "po_status = latest event to_status (derived)",
                 po.loc[po["po_id"].map(last) != po["po_status"], "po_id"])
        se = self.d["shortage_event"].sort_values(["shortage_id", "event_seq"])
        bad = [r.shortage_event_id for r in se.itertuples() if (r.from_status, r.to_status) not in SHORT_TRANSITIONS]
        self.add("V-LIFE-04", "lifecycle", "shortage_event", "only allowed shortage transitions", bad)
        last = se.groupby("shortage_id").tail(1).set_index("shortage_id")["to_status"]
        sh = self.d["shortage"]
        self.add("V-LIFE-05", "lifecycle", "shortage", "shortage_status = latest event to_status",
                 sh.loc[sh["shortage_id"].map(last) != sh["shortage_status"], "shortage_id"])

    # ------------------------------------------------------------------ cross-entity references
    def reference_checks(self):
        sku = self.i["sku"].set_index("sku_id")
        loc = self.i["location"].set_index("location_id")
        sl = set(zip(self.i["sku_location"]["sku_id"], self.i["sku_location"]["location_id"]))
        bom = self.i["bom"]
        self.add("V-REF-01", "dependency", "bom", "parent is MANUFACTURED, component is COMPONENT, no self-reference",
                 bom.loc[(bom["parent_sku_id"].map(sku["sku_type"]) != "MANUFACTURED")
                         | (bom["component_sku_id"].map(sku["sku_type"]) != "COMPONENT"), "bom_id"])
        pp = self.i["production_plan"]
        self.add("V-REF-02", "dependency", "production_plan", "only MANUFACTURED SKUs at PLANT locations, stocked there",
                 pp.loc[(pp["sku_id"].map(sku["sku_type"]) != "MANUFACTURED")
                        | (pp["location_id"].map(loc["location_type"]) != "PLANT")
                        | ~pd.Series(list(zip(pp["sku_id"], pp["location_id"])), index=pp.index).isin(sl),
                        "production_plan_id"])
        fd = self.i["forecast_demand"]
        self.add("V-REF-03", "dependency", "forecast_demand", "forecast only for stocked FINISHED/MANUFACTURED, uom = base",
                 fd.loc[~fd["sku_id"].map(sku["sku_type"]).isin(["FINISHED", "MANUFACTURED"])
                        | (fd["uom"] != fd["sku_id"].map(sku["base_uom"]))
                        | ~pd.Series(list(zip(fd["sku_id"], fd["location_id"])), index=fd.index).isin(sl), "demand_id"])
        inv = self.i["inventory"]
        inv_keys = set(zip(inv["sku_id"], inv["location_id"]))
        self.add("V-REF-04", "dependency", "inventory", "exactly one snapshot per stocked SKU-location, uom = base",
                 [f"{a}@{b}" for a, b in sl ^ inv_keys] + list(inv.loc[inv["uom"] != inv["sku_id"].map(sku["base_uom"]), "inventory_id"]))
        ss = self.i["supplier_sku"]
        prim = ss[ss["is_primary"]].groupby("sku_id").size()
        purchased = sku.index[sku["sku_type"].isin(["FINISHED", "COMPONENT"])]
        self.add("V-REF-05", "dependency", "supplier_sku", "exactly one primary supplier per purchased SKU",
                 [s for s in purchased if prim.get(s, 0) != 1])
        lt = self.i["lead_time"]
        sskeys = set(zip(ss["supplier_id"], ss["sku_id"]))
        self.add("V-REF-06", "foreign_key", "lead_time", "(supplier_id, sku_id) -> supplier_sku",
                 lt.loc[~pd.Series(list(zip(lt["supplier_id"], lt["sku_id"])), index=lt.index).isin(sskeys), "lead_time_id"])
        lines = self.i["purchase_order_line"].merge(self.i["purchase_order"][["po_id", "supplier_id", "location_id"]], on="po_id")
        intended = np.where(lines["substitute_for_sku_id"] != "", lines["substitute_for_sku_id"], lines["sku_id"])
        self.add("V-REF-07", "dependency", "purchase_order_line",
                 "line SKU is sourced from the PO supplier; covered SKU is stocked at the PO location",
                 lines.loc[~pd.Series(list(zip(lines["supplier_id"], lines["sku_id"])), index=lines.index).isin(sskeys)
                           | ~pd.Series(list(zip(intended, lines["location_id"])), index=lines.index).isin(sl), "po_line_id"])
        self.add("V-QTY-01", "quantity", "inventory", "on_hold_qty <= on_hand_qty",
                 inv.loc[inv["on_hold_qty"] > inv["on_hand_qty"], "inventory_id"])
        self.add("V-QTY-02", "quantity", "lead_time", "transit_days <= lead_time_days",
                 lt.loc[lt["transit_days"] > lt["lead_time_days"], "lead_time_id"])
        pc = self.i["production_capacity"].set_index(["location_id", "week_id"])["capacity_units"]
        ld = pp.groupby(["location_id", "week_id"])["planned_qty"].sum()
        self.add("V-QTY-03", "capacity", "production_plan", "planned production <= plant capacity each week",
                 [f"{k}" for k, v in ld.items() if v > pc.get(k, 0) + 1e-9])
        sub = self.i["sku_substitute"]
        self.add("V-REF-08", "dependency", "sku_substitute", "substitute differs from original and shares base uom",
                 sub.loc[(sub["sku_id"] == sub["substitute_sku_id"])
                         | (sub["sku_id"].map(sku["base_uom"]) != sub["substitute_sku_id"].map(sku["base_uom"])), "substitute_id"])

    # ------------------------------------------------------------------ arithmetic reconciliation
    def arithmetic_checks(self):
        p = self.d["projected_balance"].sort_values(["sku_id", "location_id", "week_id"]).reset_index(drop=True)
        calc = p["opening_qty"] + p["receipts_po_qty"] + p["receipts_production_qty"] - p["forecast_qty"] - p["dependent_demand_qty"]
        self.add("V-ARITH-01", "reconciliation", "projected_balance",
                 "closing = opening + PO receipts + production - forecast - dependent demand (every week)",
                 p.loc[(calc - p["closing_qty"]).abs() > TOL, "projection_id"])
        prev = p.groupby(["sku_id", "location_id"])["closing_qty"].shift()
        self.add("V-ARITH-02", "reconciliation", "projected_balance", "opening(week n) = closing(week n-1)",
                 p.loc[prev.notna() & ((prev - p["opening_qty"]).abs() > TOL), "projection_id"])
        inv = self.i["inventory"].set_index(["sku_id", "location_id"])
        first = p[p["week_id"] == week_id(0)]
        exp = [inv.at[(s, l), "on_hand_qty"] - inv.at[(s, l), "on_hold_qty"] for s, l in zip(first["sku_id"], first["location_id"])]
        self.add("V-ARITH-03", "reconciliation", "projected_balance", "week-1 opening = on_hand - on_hold",
                 first.loc[(np.array(exp) - first["opening_qty"]).abs() > TOL, "projection_id"])
        key = ["sku_id", "location_id", "week_id"]
        pi = p.set_index(key)

        def compare(series, col, cid, desc):
            s = series.reindex(pi.index).fillna(0.0)
            bad = pi.index[(s - pi[col]).abs() > TOL]
            extra = set(series.index) - set(pi.index)
            self.add(cid, "reconciliation", "projected_balance", desc, [f"{a}|{b}|{c}" for a, b, c in bad] + list(extra))

        ib = self.d["inbound_effective"]
        inc = ib[(ib["action"] == "INCLUDED") & (ib["effective_week_id"] != "")]
        compare(inc.groupby(["credited_sku_id", "location_id", "effective_week_id"])["effective_qty"].sum()
                .rename_axis(key), "receipts_po_qty", "V-ARITH-04", "PO receipts = sum of INCLUDED inbound_effective lines")
        compare(self.i["production_plan"].groupby(key)["planned_qty"].sum(), "receipts_production_qty", "V-ARITH-05",
                "production receipts = production_plan")
        compare(self.i["forecast_demand"].groupby(key)["forecast_qty"].sum(), "forecast_qty", "V-ARITH-06",
                "forecast = forecast_demand")
        cr = self.d["component_requirement"]
        compare(cr.groupby(["component_sku_id", "location_id", "week_id"])["required_qty"].sum().rename_axis(key),
                "dependent_demand_qty", "V-ARITH-07", "dependent demand = component_requirement")
        # BOM explosion
        sku = self.i["sku"].set_index("sku_id")
        m = cr.merge(self.i["production_plan"][["production_plan_id", "planned_qty"]], on="production_plan_id") \
              .merge(self.i["bom"], on=["parent_sku_id", "component_sku_id"])
        raw = m["planned_qty"] * m["qty_per"] * (1 + m["scrap_pct"])
        expq = np.where(m["uom"] == "KG", raw.round(3), np.ceil(raw - 1e-9))
        self.add("V-ARITH-08", "reconciliation", "component_requirement",
                 "required_qty = planned_qty x qty_per x (1+scrap)", m.loc[(expq - m["required_qty"]).abs() > TOL, "requirement_id"])
        # UoM conversion of included lines
        lines = self.i["purchase_order_line"].set_index("po_line_id")
        x = ib[ib["action"] == "INCLUDED"].copy()
        upc = x["sku_id"].map(sku["units_per_case"])
        oq = x["po_line_id"].map(lines["order_qty"])
        u = x["po_line_id"].map(lines["uom"])
        expb = np.where(u == "CS", oq * upc, oq)
        self.add("V-ARITH-09", "reconciliation", "inbound_effective", "base_qty = order_qty x units_per_case for CS lines",
                 x.loc[(expb - x["base_qty"]).abs() > TOL, "po_line_id"])
        self.add("V-ARITH-10", "reconciliation", "inbound_effective", "effective_qty <= base_qty",
                 x.loc[x["effective_qty"] > x["base_qty"] + TOL, "po_line_id"])
        # supplier load
        sl = self.d["supplier_load"]
        util = np.where(sl["capacity_units"] > 0, sl["load_units"] / sl["capacity_units"], np.where(sl["load_units"] > 0, 99, 0))
        self.add("V-ARITH-11", "reconciliation", "supplier_load", "utilisation = load / capacity; is_exceeded = load > capacity",
                 sl.loc[(np.abs(util - sl["utilisation"]) > 1e-3) | ((sl["load_units"] > sl["capacity_units"] + 1e-9) != sl["is_exceeded"]), "capacity_id"])
        # shortages vs projection
        sh = self.d["shortage"]
        bad = []
        pg = {k: g for k, g in p.groupby(["sku_id", "location_id"])}
        covered = set()
        for r in sh.itertuples():
            g = pg[(r.sku_id, r.location_id)]
            w = g[(g["week_id"] >= r.first_short_week_id) & (g["week_id"] <= r.last_short_week_id)]
            before = g[g["week_id"] < r.first_short_week_id].tail(1)
            after = g[g["week_id"] > r.last_short_week_id].head(1)
            qty = math.ceil(-w["closing_qty"].min() - 1e-9) if r.uom == "EA" else round(-w["closing_qty"].min(), 3)
            if ((w["closing_qty"] >= 0).any() or len(w) != r.weeks_short or abs(qty - r.shortage_qty) > TOL
                    or (len(before) and before["closing_qty"].iloc[0] < 0) or (len(after) and after["closing_qty"].iloc[0] < 0)
                    or abs(r.value_at_risk - round(r.shortage_qty * r.unit_cost, 2)) > 0.011
                    or abs(r.residual_qty - max(0.0, r.shortage_qty - r.on_time_mitigated_qty)) > TOL):
                bad.append(r.shortage_id)
            covered.update(w["projection_id"])
        self.add("V-ARITH-12", "reconciliation", "shortage",
                 "shortage = maximal run of negative balance; qty = peak deficit; value and residual consistent", bad)
        so = set(p.loc[p["stockout"], "projection_id"])
        self.add("V-ARITH-13", "reconciliation", "shortage", "every stockout week belongs to a shortage episode",
                 sorted(so - covered))
        # ABC derived from data
        cr_val = cr.groupby("component_sku_id")["required_qty"].sum()
        fd_val = self.i["forecast_demand"].groupby("sku_id")["forecast_qty"].sum()
        val = (fd_val.add(cr_val, fill_value=0) * sku["unit_cost"]).reindex(sku.index).fillna(0.0)
        order = val.sort_values(ascending=False, kind="mergesort")
        cum = order.cumsum() / max(order.sum(), 1e-9)
        abc = pd.Series(np.where(cum <= 0.8, "A", np.where(cum <= 0.95, "B", "C")), index=order.index)
        abc[order == 0] = "C"
        self.add("V-ARITH-14", "derived_value", "sku", "abc_class recomputed from demand value matches",
                 [s for s in sku.index if abc[s] != sku.at[s, "abc_class"]])

    # ------------------------------------------------------------------ shortages & mitigations
    def shortage_mitigation_checks(self):
        sh, mo = self.d["shortage"], self.d["mitigation_option"]
        self.add("V-SHORT-01", "explainability", "shortage", "every shortage has a primary cause and evidence",
                 sh.loc[(sh["primary_cause"] == "") | (sh["cause_evidence"] == "")
                        | ~sh.apply(lambda r: r["primary_cause"] in r["contributing_causes"].split(";"), axis=1), "shortage_id"])
        rec = mo[mo["is_recommended"]]
        self.add("V-MIT-01", "policy", "mitigation_option", "recommended options are policy-compliant and feasible",
                 rec.loc[(rec["policy_status"] != "OK") | (rec["coverable_qty"] <= 0), "mitigation_id"])
        lt = self.i["lead_time"]
        cur = lt[(lt["effective_from"] <= AS_OF_TS) & (lt["effective_to"].isna() | (AS_OF_TS <= lt["effective_to"]))]
        cur = cur.set_index(["supplier_id", "sku_id"])["lead_time_days"]
        ss = self.i["supplier_sku"].set_index("supplier_sku_id")
        npo = mo[mo["option_type"] == "NEW_PO"]
        bad = []
        for r in npo.itertuples():
            ltd = cur.get((ss.at[r.source_ref, "supplier_id"], ss.at[r.source_ref, "sku_id"]))
            if ltd is None or r.lead_time_days != ltd or r.arrival_date != AS_OF_TS + pd.Timedelta(days=int(ltd)):
                bad.append(r.mitigation_id)
        self.add("V-MIT-02", "lead_time", "mitigation_option", "NEW_PO arrival = as-of + current supplier lead time", bad)
        sub = self.i["sku_substitute"].set_index("substitute_id")
        sb = mo[(mo["option_type"] == "SUBSTITUTE") & (mo["policy_status"] == "OK")]
        self.add("V-MIT-03", "policy", "mitigation_option", "substitute options marked OK use APPROVED pairs only",
                 sb.loc[sb["source_ref"].map(sub["approval_status"]) != "APPROVED", "mitigation_id"])
        sup = self.i["supplier"].set_index("supplier_id")
        np_ok = npo[npo["policy_status"] == "OK"]
        self.add("V-MIT-04", "policy", "mitigation_option", "no OK new PO to an ON_HOLD supplier",
                 np_ok.loc[np_ok["supplier_id"].map(sup["supplier_status"]) != "ACTIVE", "mitigation_id"])
        alloc = mo.groupby("shortage_id")["allocated_qty"].sum()
        qty = sh.set_index("shortage_id")["shortage_qty"]
        self.add("V-MIT-05", "capacity", "mitigation_option", "allocations <= coverable and total <= shortage qty",
                 list(mo.loc[mo["allocated_qty"] > mo["coverable_qty"] + TOL, "mitigation_id"])
                 + [s for s, a in alloc.items() if a > qty[s] + TOL])
        # supplier capacity respected by recommended new POs
        load = self.d["supplier_load"].set_index(["supplier_id", "week_id"])
        used = defaultdict(float)
        for r in npo[npo["is_recommended"]].itertuples():
            m = ss.loc[r.source_ref]
            wk = week_id((r.arrival_date - AS_OF_TS).days // 7)
            q = max(m["min_order_qty_base"], math.ceil(r.allocated_qty / m["order_multiple_base"] - 1e-9) * m["order_multiple_base"])
            used[(r.supplier_id, wk)] += q
        bad = [f"{k}" for k, v in used.items()
               if v > max(0.0, load.at[k, "capacity_units"] - load.at[k, "load_units"]) + TOL]
        self.add("V-MIT-06", "capacity", "mitigation_option", "recommended new POs fit remaining supplier capacity", bad)
        # transfers / substitutes do not exceed donor surplus
        p = self.d["projected_balance"]
        surplus = (p["closing_qty"] - p["safety_stock_qty"]).groupby([p["sku_id"], p["location_id"]]).min().clip(lower=0)
        don = defaultdict(float)
        sh_i = sh.set_index("shortage_id")
        for r in mo[mo["is_recommended"] & (mo["option_type"] == "TRANSFER")].itertuples():
            don[(sh_i.at[r.shortage_id, "sku_id"], r.source_location_id)] += r.allocated_qty
        for r in mo[mo["is_recommended"] & (mo["option_type"] == "SUBSTITUTE")].itertuples():
            don[(r.substitute_sku_id, sh_i.at[r.shortage_id, "location_id"])] += r.allocated_qty
        self.add("V-MIT-07", "capacity", "mitigation_option", "transfers/substitutions never exceed donor surplus above safety stock",
                 [f"{k}" for k, v in don.items() if v > surplus.get(k, 0) + TOL])
        self.add("V-MIT-08", "tradeoff", "mitigation_option", "every option shows cost and service figures",
                 mo.loc[mo["incremental_cost"].isna() | mo["service_coverage_pct"].isna() | mo["days_late"].isna(), "mitigation_id"])

    # ------------------------------------------------------------------ ground truth
    def ground_truth_checks(self):
        g = self.g
        leaks = []
        for name, df in {**self.i, **self.d}.items():
            leaks += [f"{name}.{c}" for c in df.columns if re.search(r"ground|truth|anomal|issue_type|label", c)]
        leaks += [p.name for p in (self.out / "input").glob("*") if "truth" in p.name]
        self.add("V-GT-01", "ground_truth", "ground_truth", "labels stored separately; no label columns in input/derived", leaks)
        missing = []
        ent_pk = {n: set(self.all[n][TABLES[n].pk[0]]) for n in INPUT_TABLES}
        for r in g.itertuples():
            if r.entity_type in ent_pk and r.record_id not in ent_pk[r.entity_type]:
                missing.append(r.gt_id)
        self.add("V-GT-02", "ground_truth", "ground_truth", "every label points to an existing record", missing)
        # independent re-detection of each anomaly type
        po, pol = self.i["purchase_order"], self.i["purchase_order_line"]
        sku = self.i["sku"].set_index("sku_id")
        found = {}
        found["INBOUND_COUNTED_TWICE"] = set(po.sort_values("po_id").loc[lambda d: d.duplicated("supplier_ref"), "po_id"])
        base = pol["sku_id"].map(sku["base_uom"])
        okuom = ((base == "EA") & pol["uom"].isin(["EA", "CS"])) | ((base == "KG") & (pol["uom"] == "KG"))
        found["UOM_MISMATCH"] = set(pol.loc[~okuom, "po_line_id"])
        sub = self.i["sku_substitute"]
        appr = set(zip(sub.loc[sub["approval_status"] == "APPROVED", "sku_id"], sub.loc[sub["approval_status"] == "APPROVED", "substitute_sku_id"]))
        s = pol[pol["substitute_for_sku_id"] != ""]
        found["SUBSTITUTE_NOT_APPROVED"] = set(s.loc[[(a, b) not in appr for a, b in zip(s["substitute_for_sku_id"], s["sku_id"])], "po_line_id"])
        lt = self.i["lead_time"]
        m = pol.merge(po, on="po_id").merge(lt, on=["supplier_id", "sku_id"])
        m = m[(m["effective_from"] <= m["order_date"]) & (m["effective_to"].isna() | (m["order_date"] <= m["effective_to"]))]
        v = m[(m["expected_receipt_date"] - m["order_date"]).dt.days < m["lead_time_days"]]
        dups = found["INBOUND_COUNTED_TWICE"]
        cancelled = set(po.loc[po["po_status"] == "CANCELLED", "po_id"])
        found["SHORTAGE_WITHOUT_LEAD_TIME"] = set(v["po_id"]) - dups - cancelled
        sl = self.d["supplier_load"]
        found["SUPPLIER_CAPACITY_EXCEEDED"] = set(sl.loc[sl["is_exceeded"], "capacity_id"])
        for issue in ANOMALY_TYPES:
            lab = self.gt_ids(issue)
            diff = sorted(found[issue] ^ lab)
            self.add("V-GT-03", "anomaly_reconciliation", issue,
                     f"{issue}: {len(lab)} labelled, {len(found[issue])} found by independent rule; sets must match",
                     diff, labelled_ok=True)


def validate(out: Path) -> dict:
    return Validator(out).run()


def to_markdown(res: dict) -> str:
    lines = [f"# Validation summary\n", f"Overall: **{res['overall']}** - {res['n_checks']} checks, {res['n_failed']} failed\n",
             "| check | category | table | description | status | violations |", "|---|---|---|---|---|---|"]
    for c in res["checks"]:
        lines.append(f"| {c['check_id']} | {c['category']} | {c['table']} | {c['description']} | {c['status']} | {c['violations']} |")
    return "\n".join(lines) + "\n"
