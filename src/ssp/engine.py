"""Planning engine: reads ONLY the input layer and produces the derived layer.

Pipeline
  1. normalise inbound PO lines (status from events, delays, UoM, duplicates,
     substitutes, lead-time check)                           -> inbound_effective
  2. supplier load vs capacity, pro-rata constrain           -> supplier_load
  3. dependent demand from production plan x BOM            -> component_requirement
  4. projected available balance per SKU-location-week      -> projected_balance
  5. shortage episodes + explainable causes + priority      -> shortage
  6. candidate mitigations, policy/capacity checks, greedy
     recommendation in priority order                        -> mitigation_option
  7. lifecycle events + exception log                        -> shortage_event, exception_log

The engine never opens ground_truth (see tests/test_no_leakage.py).
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import timedelta

import numpy as np
import pandas as pd

from . import ids
from .config import AS_OF, week_id, week_start
from .schema import TABLES

AS_OF_TS = pd.Timestamp(AS_OF)
TRANSPORT_REASONS = {"CARRIER_DELAY", "PORT_CONGESTION", "WEATHER"}
ABC_WEIGHT = {"A": 3.0, "B": 2.0, "C": 1.0}
FROZEN_WEEKS = 2               # production cannot be changed inside this fence
EXPEDITE_WINDOW_DAYS = 56      # only POs due within 8 weeks after need date can be pulled in
MAX_RECOMMENDED = 3
SPIKE_RATIO = 2.5              # forecast > 2.5 x local median ...
SPIKE_MIN_EXCESS = 3           # ... and at least 3 units above it => demand spike


def _round_qty(x: float, uom: str, mode: str = "round") -> float:
    if uom == "KG":
        return round(float(x), 3)
    if mode == "ceil":
        return float(math.ceil(float(x) - 1e-9))
    if mode == "floor":
        return float(math.floor(float(x) + 1e-9))
    return float(round(float(x)))


def week_index(ts: pd.Series) -> pd.Series:
    return ((pd.to_datetime(ts) - AS_OF_TS).dt.days // 7).astype("Int64")


# --------------------------------------------------------------------------- 1
def prepare_inbound(t: dict[str, pd.DataFrame], n_weeks: int) -> pd.DataFrame:
    """Line-level normalisation WITHOUT capacity constraint.

    Shared with the generator (which uses it to size supplier capacity) so both
    sides agree on what counts as supplier load.
    """
    po = t["purchase_order"].copy()
    pol = t["purchase_order_line"].copy()
    ev = t["po_event"].sort_values(["po_id", "event_seq"])

    last = ev.groupby("po_id").tail(1).set_index("po_id")
    po["derived_status"] = po["po_id"].map(last["to_status"])
    dly = ev[ev["event_type"] == "DELAYED"].groupby("po_id").tail(1).set_index("po_id")
    po["latest_eta"] = po["po_id"].map(dly["revised_eta"])
    po["delay_reason"] = po["po_id"].map(dly["reason_code"]).fillna("")
    po["latest_eta"] = po["latest_eta"].fillna(po["expected_receipt_date"])
    po["shipped"] = po["po_id"].isin(ev.loc[ev["event_type"] == "SHIPPED", "po_id"])

    # duplicate inbound: same supplier confirmation number => keep lowest PO id
    po = po.sort_values("po_id")
    first_by_ref = po.groupby("supplier_ref")["po_id"].transform("first")
    po["duplicate_of"] = np.where(first_by_ref != po["po_id"], first_by_ref, "")

    hcols = ["po_id", "supplier_id", "location_id", "order_date", "expected_receipt_date",
             "latest_eta", "delay_reason", "derived_status", "duplicate_of", "shipped"]
    L = pol.merge(po[hcols], on="po_id", how="left")

    sku = t["sku"].set_index("sku_id")
    L["base_uom"] = L["sku_id"].map(sku["base_uom"])
    L["upc"] = L["sku_id"].map(sku["units_per_case"])
    uom_ok = (((L["base_uom"] == "EA") & L["uom"].isin(["EA", "CS"]))
              | ((L["base_uom"] == "KG") & (L["uom"] == "KG")))
    L["uom_ok"] = uom_ok
    base = np.where(L["uom"] == "CS", L["order_qty"] * L["upc"], L["order_qty"])
    L["base_qty"] = np.where(uom_ok, np.round(base.astype(float), 3), np.nan)

    # lead time version effective at order date
    lt = t["lead_time"]
    m = L[["po_line_id", "supplier_id", "sku_id", "order_date"]].merge(lt, on=["supplier_id", "sku_id"], how="left")
    ok = (m["effective_from"] <= m["order_date"]) & (m["effective_to"].isna() | (m["order_date"] <= m["effective_to"]))
    m = m[ok].drop_duplicates("po_line_id")
    L = L.merge(m[["po_line_id", "lead_time_id", "lead_time_days"]], on="po_line_id", how="left")
    L["lead_time_days"] = L["lead_time_days"].fillna(0)
    L["lt_required_eta"] = L["order_date"] + pd.to_timedelta(L["lead_time_days"], unit="D")
    L["lt_violation"] = L["expected_receipt_date"] < L["lt_required_eta"]
    L["effective_eta"] = L[["latest_eta", "lt_required_eta"]].max(axis=1)
    L["delayed"] = L["latest_eta"] > L["expected_receipt_date"]
    L["redated"] = L["effective_eta"] > L["latest_eta"]

    # substitutes: line buys sku_id to cover substitute_for_sku_id
    sub = t["sku_substitute"]
    L["is_sub"] = L["substitute_for_sku_id"] != ""
    sm = L.loc[L["is_sub"], ["po_line_id", "sku_id", "substitute_for_sku_id", "order_date"]].merge(
        sub, left_on=["substitute_for_sku_id", "sku_id"], right_on=["sku_id", "substitute_sku_id"],
        how="left", suffixes=("", "_sub"))
    approved = ((sm["approval_status"] == "APPROVED") & (sm["effective_from"] <= sm["order_date"])
                & (sm["effective_to"].isna() | (sm["order_date"] <= sm["effective_to"])))
    sm = sm.assign(sub_ok=approved.values)
    L["sub_ok"] = L["po_line_id"].map(sm.set_index("po_line_id")["sub_ok"]).fillna(False).astype(bool)
    L["sub_status"] = L["po_line_id"].map(sm.set_index("po_line_id")["approval_status"]).fillna("")
    L["sub_pair_id"] = L["po_line_id"].map(sm.set_index("po_line_id")["substitute_id"]).fillna("")
    L.loc[~L["is_sub"], "sub_ok"] = True

    cancelled = L["derived_status"] == "CANCELLED"
    dup = L["duplicate_of"] != ""
    L["action"] = np.select(
        [cancelled, dup, ~uom_ok, ~L["sub_ok"]],
        ["EXCLUDED_CANCELLED", "EXCLUDED_DUPLICATE", "EXCLUDED_UOM_MISMATCH", "EXCLUDED_UNAPPROVED_SUBSTITUTE"],
        "INCLUDED")
    L["intended_sku_id"] = np.where(L["is_sub"], L["substitute_for_sku_id"], L["sku_id"])
    L["credited_sku_id"] = np.where(L["action"] == "INCLUDED", L["intended_sku_id"], "")
    # physical supplier load: everything that will actually ship
    L["counts_for_load"] = (~cancelled) & (~dup) & uom_ok
    L["orig_week"] = week_index(L["expected_receipt_date"])
    L["eff_week"] = week_index(L["effective_eta"])
    L["in_horizon"] = (L["eff_week"] >= 0) & (L["eff_week"] < n_weeks)
    return L.sort_values("po_line_id").reset_index(drop=True)


def supplier_load(L: pd.DataFrame, n_weeks: int) -> pd.DataFrame:
    x = L[L["counts_for_load"] & L["in_horizon"]]
    g = x.groupby(["supplier_id", "eff_week"])["base_qty"].sum().reset_index()
    g["week_id"] = g["eff_week"].astype(int).map(week_id)
    return g.rename(columns={"base_qty": "load_units"})[["supplier_id", "week_id", "load_units"]]


# --------------------------------------------------------------------------- planner
class Planner:
    def __init__(self, t: dict[str, pd.DataFrame], n_weeks: int):
        self.t = t
        self.W = n_weeks
        self.exc: list[dict] = []
        self.sku = t["sku"].set_index("sku_id")
        self.weeks_ts = [pd.Timestamp(week_start(i)) for i in range(n_weeks)]

    # ---- helpers
    def _exception(self, etype, entity, record, related, rule, decision, details):
        self.exc.append(dict(exception_type=etype, entity_type=entity, record_id=record,
                             related_record_id=related, rule_id=rule, decision=decision,
                             details=details, detected_at=AS_OF_TS))

    # ---- main
    def run(self) -> dict[str, pd.DataFrame]:
        L = prepare_inbound(self.t, self.W)
        L, load = self._capacity(L)
        self._inbound_exceptions(L)
        creq = self._component_requirements()
        proj = self._projection(L, creq)
        short = self._shortages(L, proj)
        short, mit, sev = self._mitigate(L, proj, short, load)
        exc = self._finalise_exceptions()
        inbound = self._inbound_table(L, exc)
        return dict(inbound_effective=inbound, component_requirement=creq, projected_balance=proj["table"],
                    supplier_load=load, exception_log=exc, shortage=short, shortage_event=sev,
                    mitigation_option=mit)

    # ---- 2. capacity
    def _capacity(self, L):
        cap = self.t["supplier_capacity"]
        ld = supplier_load(L, self.W)
        load = cap.merge(ld, on=["supplier_id", "week_id"], how="left")
        load["load_units"] = load["load_units"].fillna(0.0).round(3)
        load["utilisation"] = np.where(load["capacity_units"] > 0, load["load_units"] / load["capacity_units"],
                                       np.where(load["load_units"] > 0, 99.0, 0.0)).round(4)
        load["is_exceeded"] = load["load_units"] > load["capacity_units"] + 1e-9
        load["scale_factor"] = np.where(load["is_exceeded"],
                                        load["capacity_units"] / load["load_units"].where(load["load_units"] > 0, 1),
                                        1.0).round(6)
        L["week_id_eff"] = L["eff_week"].map(lambda w: week_id(int(w)) if pd.notna(w) and 0 <= w < self.W else "")
        sf = load.set_index(["supplier_id", "week_id"])["scale_factor"]
        capid = load.set_index(["supplier_id", "week_id"])["capacity_id"]
        keys = list(zip(L["supplier_id"], L["week_id_eff"]))
        L["scale"] = [float(sf.get(k, 1.0)) for k in keys]
        L["capacity_id"] = [capid.get(k, "") if s < 1 else "" for k, s in zip(keys, L["scale"])]
        inc = L["action"] == "INCLUDED"
        eff = []
        for q, s, u, a in zip(L["base_qty"], L["scale"], L["base_uom"], inc):
            if not a:
                eff.append(0.0)
            elif s < 1:
                eff.append(_round_qty(q * s, u, "floor"))
            else:
                eff.append(float(q))
        L["effective_qty"] = eff
        L["scaled"] = inc & (L["scale"] < 1)
        for r in load[load["is_exceeded"]].itertuples():
            self._exception("SUPPLIER_CAPACITY_EXCEEDED", "supplier_capacity", r.capacity_id, r.supplier_id,
                            "R-CAP-01", "CONSTRAIN_RECEIPTS_TO_CAPACITY",
                            f"load {r.load_units:g} > capacity {r.capacity_units:g}; receipts scaled x{r.scale_factor:.3f}")
        cols = ["capacity_id", "supplier_id", "week_id", "load_units", "capacity_units", "utilisation",
                "is_exceeded", "scale_factor"]
        return L, load[cols].sort_values("capacity_id").reset_index(drop=True)

    def _inbound_exceptions(self, L):
        hdr = L.drop_duplicates("po_id")
        for r in hdr[hdr["duplicate_of"] != ""].itertuples():
            self._exception("INBOUND_COUNTED_TWICE", "purchase_order", r.po_id, r.duplicate_of, "R-INB-01",
                            "EXCLUDE_DUPLICATE", f"same supplier_ref as {r.duplicate_of}; inbound counted once")
        for r in L[L["action"] == "EXCLUDED_UOM_MISMATCH"].itertuples():
            self._exception("UOM_MISMATCH", "purchase_order_line", r.po_line_id, r.sku_id, "R-UOM-01",
                            "QUARANTINE_LINE", f"line uom {r.uom} not convertible to base uom {r.base_uom}")
        for r in L[L["action"] == "EXCLUDED_UNAPPROVED_SUBSTITUTE"].itertuples():
            st = r.sub_status or "NO_PAIR"
            self._exception("SUBSTITUTE_NOT_APPROVED", "purchase_order_line", r.po_line_id,
                            r.sub_pair_id or r.substitute_for_sku_id, "R-SUB-01", "EXCLUDE_FROM_SUPPLY",
                            f"{r.sku_id} bought as substitute for {r.substitute_for_sku_id}; pair status {st}")
        live = L[(L["action"] != "EXCLUDED_CANCELLED") & (L["action"] != "EXCLUDED_DUPLICATE")]
        viol = live[live["lt_violation"]]
        for po_id, g in viol.groupby("po_id"):
            r = g.iloc[0]
            gap = (r.expected_receipt_date - r.order_date).days
            self._exception("SHORTAGE_WITHOUT_LEAD_TIME", "purchase_order", po_id, ",".join(g["lead_time_id"].astype(str)),
                            "R-LT-01", "REDATE_RECEIPT_TO_LEAD_TIME",
                            f"receipt {gap}d after order but lead time is {int(g['lead_time_days'].max())}d; "
                            f"receipt re-dated to {g['effective_eta'].max().date()}")

    # ---- 3. BOM explosion
    def _component_requirements(self):
        pp = self.t["production_plan"]
        bom = self.t["bom"]
        m = pp.merge(bom, left_on="sku_id", right_on="parent_sku_id")
        m = m[(m["effective_from"] <= m["week_start_date"])
              & (m["effective_to"].isna() | (m["week_start_date"] <= m["effective_to"]))]
        m["uom"] = m["component_sku_id"].map(self.sku["base_uom"])
        raw = m["planned_qty"] * m["qty_per"] * (1 + m["scrap_pct"])
        m["required_qty"] = [_round_qty(x, u, "ceil") for x, u in zip(raw, m["uom"])]
        m["requirement_id"] = [ids.requirement_id(a, b) for a, b in zip(m["production_plan_id"], m["component_sku_id"])]
        out = m[["requirement_id", "production_plan_id", "parent_sku_id", "component_sku_id", "location_id",
                 "week_id", "required_qty", "uom"]]
        return out.sort_values("requirement_id").reset_index(drop=True)

    # ---- 4. projection
    def _projection(self, L, creq):
        sl = self.t["sku_location"].sort_values(["sku_id", "location_id"]).reset_index(drop=True)
        n, W = len(sl), self.W
        idx = {(s, l): i for i, (s, l) in enumerate(zip(sl["sku_id"], sl["location_id"]))}
        wk = {week_id(i): i for i in range(W)}

        def grid(df, scol, lcol, wcol, qcol):
            a = np.zeros((n, W))
            if len(df):
                g = df.groupby([scol, lcol, wcol])[qcol].sum()
                for (s, l, w), q in g.items():
                    if (s, l) in idx and w in wk:
                        a[idx[(s, l)], wk[w]] += q
            return a

        fc = grid(self.t["forecast_demand"], "sku_id", "location_id", "week_id", "forecast_qty")
        dep = grid(creq, "component_sku_id", "location_id", "week_id", "required_qty")
        prod = grid(self.t["production_plan"], "sku_id", "location_id", "week_id", "planned_qty")
        inc = L[(L["action"] == "INCLUDED") & L["in_horizon"]]
        rpo = grid(inc, "credited_sku_id", "location_id", "week_id_eff", "effective_qty")

        inv = self.t["inventory"].groupby(["sku_id", "location_id"])[["on_hand_qty", "on_hold_qty"]].sum()
        open0 = np.array([float(inv.loc[k, "on_hand_qty"] - inv.loc[k, "on_hold_qty"]) if k in inv.index else 0.0
                          for k in zip(sl["sku_id"], sl["location_id"])])
        gross = fc + dep
        closing = np.round(open0[:, None] + np.cumsum(rpo + prod - gross, axis=1), 3)
        opening = np.concatenate([open0[:, None], closing[:, :-1]], axis=1)
        ss = sl["safety_stock_qty"].to_numpy()

        rep = lambda a: np.repeat(a, W)
        tile = lambda a: np.tile(a, n)
        weeks = [week_id(i) for i in range(W)]
        tab = pd.DataFrame({
            "sku_id": rep(sl["sku_id"].to_numpy()), "location_id": rep(sl["location_id"].to_numpy()),
            "week_id": tile(np.array(weeks)), "week_start_date": tile(np.array(self.weeks_ts)),
            "opening_qty": opening.ravel().round(3), "receipts_po_qty": rpo.ravel().round(3),
            "receipts_production_qty": prod.ravel().round(3), "forecast_qty": fc.ravel().round(3),
            "dependent_demand_qty": dep.ravel().round(3), "closing_qty": closing.ravel(),
            "safety_stock_qty": rep(ss)})
        tab["below_safety_stock"] = tab["closing_qty"] < tab["safety_stock_qty"]
        tab["stockout"] = tab["closing_qty"] < 0
        tab.insert(0, "projection_id", "PAB-" + tab["sku_id"] + "-" + tab["location_id"] + "-" + tab["week_id"])
        return dict(table=tab, sl=sl, idx=idx, closing=closing, gross=gross, prod=prod, fc=fc,
                    rpo=rpo, open0=open0, ss=ss)

    # ---- 5. shortages + causes
    def _shortages(self, L, P):
        sl, closing, gross = P["sl"], P["closing"], P["gross"]
        by_sl = defaultdict(list)
        for r in L.itertuples():
            by_sl[(r.intended_sku_id, r.location_id)].append(r)
        rows = []
        for i in np.where((closing < 0).any(axis=1))[0]:
            s, l = sl.at[i, "sku_id"], sl.at[i, "location_id"]
            neg = closing[i] < 0
            w = 0
            while w < self.W:
                if not neg[w]:
                    w += 1
                    continue
                f = w
                while w < self.W and neg[w]:
                    w += 1
                last = w - 1
                rows.append(self._explain(i, s, l, f, last, closing, gross, P, by_sl.get((s, l), [])))
        cols = ["sku_id", "location_id", "f", "l", "shortage_qty", "primary_cause", "contributing_causes",
                "cause_evidence"]
        return pd.DataFrame(rows, columns=cols)

    def _explain(self, i, s, l, f, last, closing, gross, P, lines):
        uom = self.sku.at[s, "base_uom"]
        qty = _round_qty(-closing[i, f:last + 1].min(), uom, "ceil")
        contrib: dict[str, float] = defaultdict(float)
        ev: dict[str, list] = defaultdict(list)
        receipt_weeks = []
        for r in lines:
            ow = r.orig_week
            ew = r.eff_week
            q = float(r.base_qty) if not pd.isna(r.base_qty) else float(r.order_qty)
            if r.action == "INCLUDED":
                if r.in_horizon:
                    receipt_weeks.append(int(ew))
                if r.scaled and ew <= last:
                    contrib["SUPPLIER_CAPACITY"] += q - r.effective_qty
                    ev["SUPPLIER_CAPACITY"].append(f"{r.po_line_id} cut {q:g}->{r.effective_qty:g} by {r.capacity_id}")
                if ow <= last and ew >= f and ew > ow:
                    if r.delayed:
                        c = "TRANSPORT_DELAY" if r.delay_reason in TRANSPORT_REASONS else "SUPPLIER_DELAY"
                        contrib[c] += r.effective_qty
                        ev[c].append(f"{r.po_id} ETA {r.expected_receipt_date.date()}->{r.latest_eta.date()} ({r.delay_reason})")
                    if r.redated:
                        contrib["LEAD_TIME_CORRECTION"] += r.effective_qty
                        ev["LEAD_TIME_CORRECTION"].append(f"{r.po_id} re-dated to {r.effective_eta.date()} ({r.lead_time_id})")
            elif r.action != "EXCLUDED_DUPLICATE" and ow <= last:
                contrib["SUPPLY_EXCLUDED"] += q
                ev["SUPPLY_EXCLUDED"].append(f"{r.po_line_id} {r.action}")
        g = gross[i]
        fc = P["fc"][i]  # spikes are judged on independent (forecast) demand; lumpy BOM demand is normal
        for w in range(max(0, f - 4), last + 1):
            # local baseline = median of the surrounding +/-6 weeks (robust to seasonality)
            nb = np.concatenate([fc[max(0, w - 6):w], fc[w + 1:w + 7]])
            med = float(np.median(nb)) if len(nb) else 0.0
            if fc[w] > SPIKE_RATIO * max(med, 1.0) and fc[w] - med >= SPIKE_MIN_EXCESS:
                contrib["DEMAND_SPIKE"] += fc[w] - med
                ev["DEMAND_SPIKE"].append(f"{week_id(w)} forecast {fc[w]:g} vs local median {med:g}")
        if self.sku.at[s, "sku_type"] == "MANUFACTURED":
            deficit = g[: last + 1].sum() - P["prod"][i, : last + 1].sum() - P["open0"][i]
            if deficit > 0:
                contrib["PRODUCTION_SHORTFALL"] += deficit
                ev["PRODUCTION_SHORTFALL"].append(
                    f"planned production {P['prod'][i, :last + 1].sum():g} < requirement {g[:last + 1].sum():g} through {week_id(last)}")
        if contrib:
            primary = max(contrib, key=lambda k: (contrib[k], k))
        else:
            first_rcpt = min(receipt_weeks) if receipt_weeks else None
            if first_rcpt is None or f < first_rcpt:
                primary = "INSUFFICIENT_OPENING_STOCK"
                ev[primary].append(f"opening available {P['open0'][i]:g} runs out in {week_id(f)}; first receipt "
                                   f"{week_id(first_rcpt) if first_rcpt is not None else 'none in horizon'}")
            else:
                primary = "INSUFFICIENT_REPLENISHMENT"
                ev[primary].append(f"receipts {P['rpo'][i, :last + 1].sum():g} + opening {P['open0'][i]:g} "
                                   f"< requirement {g[:last + 1].sum():g} through {week_id(last)}")
            contrib[primary] = qty
        causes = sorted(contrib, key=lambda k: (-contrib[k], k))
        evidence = " | ".join(f"{c}: " + "; ".join(ev[c][:3]) for c in causes)
        return dict(sku_id=s, location_id=l, f=f, l=last, shortage_qty=qty, primary_cause=primary,
                    contributing_causes=";".join(causes), cause_evidence=evidence)

    # ---- 6. mitigation
    def _mitigate(self, L, P, short, load):
        if short.empty:
            empty = lambda name: pd.DataFrame(columns=TABLES[name].columns)
            return empty("shortage"), empty("mitigation_option"), empty("shortage_event")
        sl, closing, idx = P["sl"], P["closing"], P["idx"]
        sku, W = self.sku, self.W
        short = short.copy()
        short["uom"] = short["sku_id"].map(sku["base_uom"])
        short["unit_cost"] = short["sku_id"].map(sku["unit_cost"])
        short["abc_class"] = short["sku_id"].map(sku["abc_class"])
        short["value_at_risk"] = (short["shortage_qty"] * short["unit_cost"]).round(2)
        short["priority_score"] = (short["value_at_risk"] * short["abc_class"].map(ABC_WEIGHT)
                                   / (1 + short["f"] / 4)).round(2)
        short = short.sort_values(["priority_score", "f", "sku_id", "location_id"],
                                  ascending=[False, True, True, True]).reset_index(drop=True)
        n = len(short)
        short["priority_rank"] = np.arange(1, n + 1)
        short["priority_band"] = np.where(short["priority_rank"] <= max(1, math.ceil(0.1 * n)), "P1",
                                          np.where(short["priority_rank"] <= math.ceil(0.4 * n), "P2", "P3"))
        short["shortage_id"] = [ids.shortage_id(k) for k in short["priority_rank"]]

        # ---- shared, consumable resources
        surplus = np.maximum(0.0, (closing - P["ss"][:, None]).min(axis=1))
        locs_by_sku = defaultdict(list)
        for i, (s, l) in enumerate(zip(sl["sku_id"], sl["location_id"])):
            locs_by_sku[s].append(i)
        loc = self.t["location"].set_index("location_id")
        subs = defaultdict(list)
        for r in self.t["sku_substitute"].itertuples():
            subs[r.sku_id].append(r)
        sup = self.t["supplier"].set_index("supplier_id")
        ss_by_sku = defaultdict(list)
        for r in self.t["supplier_sku"].itertuples():
            ss_by_sku[r.sku_id].append(r)
        lt = self.t["lead_time"]
        lt_now = lt[(lt["effective_from"] <= AS_OF_TS) & (lt["effective_to"].isna() | (AS_OF_TS <= lt["effective_to"]))]
        lt_now = lt_now.set_index(["supplier_id", "sku_id"])
        sup_rem = {(r.supplier_id, r.week_id): max(0.0, r.capacity_units - r.load_units) for r in load.itertuples()}
        pcap = self.t["production_capacity"].set_index(["location_id", "week_id"])["capacity_units"]
        pp_load = self.t["production_plan"].groupby(["location_id", "week_id"])["planned_qty"].sum()
        plant_rem = {k: float(v - pp_load.get(k, 0.0)) for k, v in pcap.items()}
        bom = defaultdict(list)
        for r in self.t["bom"].itertuples():
            bom[r.parent_sku_id].append(r)
        exp_lines = defaultdict(list)
        inc = L[(L["action"] == "INCLUDED") & (L["derived_status"] != "CANCELLED")]
        for r in inc.itertuples():
            exp_lines[(r.credited_sku_id, r.location_id)].append(r)
        expedited: set[str] = set()

        mit_rows, sev_rows, mit_on_time, residual, status = [], [], [], [], []
        for s in short.itertuples():
            need = self.weeks_ts[s.f]
            req = float(s.shortage_qty)
            uom, cost = s.uom, float(s.unit_cost)
            i_short = idx[(s.sku_id, s.location_id)]
            opts = []

            def add(otype, ref, qty_prop, cover, arrival, inc_cost, policy="OK", **kw):
                cover = max(0.0, min(cover, req))
                on_time = cover if arrival <= need else 0.0
                days_late = max(0, (arrival - need).days)
                if cover <= 0:
                    feas = "INFEASIBLE"
                elif arrival > need:
                    feas = "LATE"
                elif cover + 1e-9 < req:
                    feas = "PARTIAL"
                else:
                    feas = "ON_TIME"
                cpu = inc_cost / cover if cover > 0 else 0.0
                late_pen = min(1.0, days_late / EXPEDITE_WINDOW_DAYS)
                score = (100 * on_time / req + 40 * (cover - on_time) / req * (1 - late_pen)
                         - 30 * min(1.0, cpu / max(cost, 0.01)))
                opts.append(dict(option_type=otype, source_ref=ref, proposed_qty=qty_prop, coverable_qty=cover,
                                 arrival_date=arrival, need_date=need, days_late=days_late, on_time_qty=on_time,
                                 incremental_cost=round(inc_cost, 2), cost_per_unit=round(cpu, 4),
                                 service_coverage_pct=round(100 * on_time / req, 2), feasibility=feas,
                                 policy_status=policy, score=round(score, 2), **kw))

            # TRANSFER from another location with surplus
            donors = sorted([j for j in locs_by_sku[s.sku_id] if j != i_short and surplus[j] > 0],
                            key=lambda j: (-surplus[j], j))[:3]
            for j in donors:
                dl = sl.at[j, "location_id"]
                same = loc.at[dl, "region"] == loc.at[s.location_id, "region"]
                q = _round_qty(min(surplus[j], req), uom, "floor")
                arr = AS_OF_TS + pd.Timedelta(days=7 if same else 14)
                add("TRANSFER", dl, q, q, arr, 150 + q * cost * (0.03 if same else 0.06),
                    source_location_id=dl, _res=("surplus", j))
            # SUBSTITUTE stocked at the same location
            for r in sorted(subs.get(s.sku_id, []), key=lambda r: (r.priority, r.substitute_sku_id))[:3]:
                j = idx.get((r.substitute_sku_id, s.location_id))
                if j is None or surplus[j] <= 0:
                    continue
                approved = (r.approval_status == "APPROVED" and r.effective_from <= AS_OF_TS
                            and (pd.isna(r.effective_to) or AS_OF_TS <= r.effective_to))
                q = _round_qty(min(surplus[j] / r.conversion_factor, req), uom, "floor")
                c2 = float(sku.at[r.substitute_sku_id, "unit_cost"])
                add("SUBSTITUTE", r.substitute_id, q, q, AS_OF_TS, q * max(0.0, c2 - cost) + q * cost * 0.01,
                    policy="OK" if approved else "REJECTED_SUBSTITUTE_NOT_APPROVED",
                    substitute_sku_id=r.substitute_sku_id, _res=("surplus_sub", j, r.conversion_factor))
            # EXPEDITE an existing PO line due after the need date
            cand = [r for r in exp_lines.get((s.sku_id, s.location_id), [])
                    if r.po_line_id not in expedited and r.effective_eta > need
                    and r.effective_eta <= need + pd.Timedelta(days=EXPEDITE_WINDOW_DAYS) and r.effective_qty > 0]
            for r in sorted(cand, key=lambda r: (r.effective_eta, r.po_line_id))[:3]:
                if r.shipped:
                    new_eta = max(r.effective_eta - pd.Timedelta(days=7), AS_OF_TS + pd.Timedelta(days=2))
                    prem = 0.35
                else:
                    tr = lt_now["transit_days"].get((r.supplier_id, r.sku_id), 7)
                    new_eta = max(r.effective_eta - pd.Timedelta(days=14), AS_OF_TS + pd.Timedelta(days=int(tr)))
                    prem = float(sup.at[r.supplier_id, "expedite_premium_pct"])
                q = min(float(r.effective_qty), req)
                add("EXPEDITE_PO", r.po_line_id, q, q, new_eta, q * cost * prem,
                    supplier_id=r.supplier_id, _res=("expedite", r.po_line_id))
            # NEW_PO from each approved source, respecting lead time, MOQ and remaining capacity
            for r in sorted(ss_by_sku.get(s.sku_id, []), key=lambda r: (not r.is_primary, r.supplier_id)):
                key = (r.supplier_id, s.sku_id)
                if key not in lt_now.index:
                    continue
                ltd = int(lt_now.at[key, "lead_time_days"])
                arr = AS_OF_TS + pd.Timedelta(days=ltd)
                wk = (arr - AS_OF_TS).days // 7
                policy = "OK"
                if sup.at[r.supplier_id, "supplier_status"] != "ACTIVE":
                    policy = "REJECTED_SUPPLIER_ON_HOLD"
                elif wk >= W:
                    policy = "REJECTED_BEYOND_HORIZON"
                mult, moq = float(r.order_multiple_base), float(r.min_order_qty_base)
                q_order = max(moq, math.ceil(req / mult - 1e-9) * mult)
                rem = sup_rem.get((r.supplier_id, week_id(wk)), 0.0) if wk < W else 0.0
                if q_order > rem:
                    q_order = math.floor(rem / mult + 1e-9) * mult
                    if q_order < moq:
                        q_order = 0.0
                q_order = round(q_order, 3)
                cover = min(q_order, req)
                extra = max(0.0, q_order - req)
                inc_cost = (250 + q_order * max(0.0, float(r.unit_price) - cost) + extra * cost * 0.25) if q_order else 0.0
                add("NEW_PO", r.supplier_sku_id, q_order, cover, arr, inc_cost, policy=policy,
                    supplier_id=r.supplier_id, lead_time_days=ltd,
                    _res=("capacity", (r.supplier_id, week_id(wk)) if wk < W else None, mult, moq))
            # PRODUCTION_INCREASE at the plant (manufactured SKUs)
            if sku.at[s.sku_id, "sku_type"] == "MANUFACTURED":
                wk = next((w for w in range(FROZEN_WEEKS, W) if plant_rem.get((s.location_id, week_id(w)), 0) > 0), None)
                if wk is not None:
                    head = plant_rem[(s.location_id, week_id(wk))]
                    lim = head
                    for b in bom[s.sku_id]:
                        j = idx.get((b.component_sku_id, s.location_id))
                        per = b.qty_per * (1 + b.scrap_pct)
                        lim = min(lim, (surplus[j] / per) if j is not None else 0.0)
                    q = _round_qty(min(lim, req), "EA", "floor")
                    add("PRODUCTION_INCREASE", s.location_id, q, q, self.weeks_ts[wk], q * cost * 0.12,
                        source_location_id=s.location_id, _res=("plant", (s.location_id, week_id(wk))))

            # ---- rank + greedy recommendation (consumes shared resources)
            eligible = [k for k, o in enumerate(opts) if o["policy_status"] == "OK" and o["coverable_qty"] > 0]
            eligible.sort(key=lambda k: (-opts[k]["score"], k))
            for rnk, k in enumerate(eligible, 1):
                opts[k]["rank"] = rnk
            remaining, on_time_total, picks = req, 0.0, 0
            for k in eligible:
                if remaining <= 1e-9 or picks >= MAX_RECOMMENDED:
                    break
                o = opts[k]
                alloc = self._consume(o, remaining, uom, surplus, sup_rem, plant_rem, bom, idx, s, expedited)
                if alloc <= 0:
                    o["decision_reason"] = "capacity already allocated to higher-priority shortages"
                    continue
                o["is_recommended"], o["allocated_qty"] = True, alloc
                remaining -= alloc
                if o["arrival_date"] <= need:
                    on_time_total += alloc
                picks += 1
                timing = "on time" if o["arrival_date"] <= need else "%dd late" % o["days_late"]
                o["decision_reason"] = "rank %d: covers %g %s at %.2f/unit" % (o["rank"], alloc, timing,
                                                                              o["cost_per_unit"])
            for o in opts:
                o.setdefault("is_recommended", False)
                o.setdefault("allocated_qty", 0.0)
                o.setdefault("rank", np.nan)
                if "decision_reason" not in o:
                    if o["policy_status"] != "OK":
                        o["decision_reason"] = f"blocked by policy: {o['policy_status']}"
                    elif o["coverable_qty"] <= 0:
                        o["decision_reason"] = "no capacity / quantity available"
                    else:
                        o["decision_reason"] = "not needed: shortage qty already allocated to higher-ranked options"
            for seq, o in enumerate(opts, 1):
                o.pop("_res", None)
                o.update(mitigation_id=ids.mitigation_id(s.shortage_id, seq), shortage_id=s.shortage_id, option_seq=seq)
                mit_rows.append(o)
            res = _round_qty(max(0.0, req - on_time_total), uom)
            mit_on_time.append(_round_qty(on_time_total, uom))
            residual.append(res)
            # lifecycle events (append-only)
            evs = [("DETECTED", "", "DETECTED", f"projected balance < 0 from {week_id(s.f)}; qty {req:g}"),
                   ("PRIORITIZED", "DETECTED", "PRIORITIZED", f"rank {s.priority_rank} band {s.priority_band}")]
            if any(o["is_recommended"] for o in opts):
                evs.append(("MITIGATION_PROPOSED", "PRIORITIZED", "MITIGATION_PROPOSED",
                            f"{sum(o['is_recommended'] for o in opts)} option(s), on-time {on_time_total:g}"))
            if res > 0:
                evs.append(("ESCALATED", evs[-1][2], "ESCALATED", f"residual {res:g} {uom} not covered on time"))
                self._exception("SHORTAGE_ESCALATED", "shortage", s.shortage_id, f"{s.sku_id}@{s.location_id}",
                                "R-MIT-01", "ESCALATE_TO_OPS_MANAGER",
                                f"residual {res:g} of {req:g} cannot be covered by need date {need.date()}")
            for seq, (et, fr, to, d) in enumerate(evs, 1):
                sev_rows.append(dict(shortage_event_id=ids.shortage_event_id(s.shortage_id, seq),
                                     shortage_id=s.shortage_id, event_seq=seq, event_type=et, event_date=AS_OF_TS,
                                     from_status=fr, to_status=to, details=d))
            status.append(evs[-1][2])

        short["on_time_mitigated_qty"] = mit_on_time
        short["residual_qty"] = residual
        short["shortage_status"] = status
        short["first_short_week_id"] = short["f"].map(week_id)
        short["last_short_week_id"] = short["l"].map(week_id)
        short["need_date"] = short["f"].map(lambda f: self.weeks_ts[f])
        short["weeks_short"] = short["l"] - short["f"] + 1
        short["detected_at"] = AS_OF_TS
        short = short[TABLES["shortage"].columns]
        mit = pd.DataFrame(mit_rows)
        for c in TABLES["mitigation_option"].columns:
            if c not in mit.columns:
                mit[c] = ""
        mit = mit[TABLES["mitigation_option"].columns].fillna({"source_location_id": "", "supplier_id": "",
                                                               "substitute_sku_id": ""})
        return short, mit, pd.DataFrame(sev_rows)

    def _consume(self, o, remaining, uom, surplus, sup_rem, plant_rem, bom, idx, s, expedited):
        res = o["_res"]
        want = min(o["coverable_qty"], remaining)
        kind = res[0]
        if kind == "surplus":
            alloc = _round_qty(min(want, surplus[res[1]]), uom, "floor")
            surplus[res[1]] -= alloc
        elif kind == "surplus_sub":
            j, cf = res[1], res[2]
            alloc = _round_qty(min(want, surplus[j] / cf), uom, "floor")
            surplus[j] -= alloc * cf
        elif kind == "expedite":
            alloc = want
            expedited.add(res[1])
        elif kind == "capacity":
            key, mult, moq = res[1], res[2], res[3]
            q = max(moq, math.ceil(want / mult - 1e-9) * mult)
            if key is None or q > sup_rem.get(key, 0.0) + 1e-9:
                return 0.0
            sup_rem[key] -= q
            alloc = want
        elif kind == "plant":
            key = res[1]
            alloc = _round_qty(min(want, plant_rem.get(key, 0.0)), "EA", "floor")
            for b in bom[s.sku_id]:
                j = idx.get((b.component_sku_id, s.location_id))
                per = b.qty_per * (1 + b.scrap_pct)
                if j is None:
                    return 0.0
                alloc = min(alloc, _round_qty(surplus[j] / per, "EA", "floor"))
            plant_rem[key] -= alloc
            for b in bom[s.sku_id]:
                surplus[idx[(b.component_sku_id, s.location_id)]] -= alloc * b.qty_per * (1 + b.scrap_pct)
        else:
            alloc = 0.0
        return max(0.0, alloc)

    # ---- 7. outputs
    def _finalise_exceptions(self):
        df = pd.DataFrame(self.exc, columns=["exception_type", "entity_type", "record_id", "related_record_id",
                                             "rule_id", "decision", "details", "detected_at"])
        df = df.sort_values(["exception_type", "record_id"]).reset_index(drop=True)
        df.insert(0, "exception_id", [ids.exception_id(k + 1) for k in range(len(df))])
        return df

    def _inbound_table(self, L, exc):
        by_rec = defaultdict(list)
        for r in exc.itertuples():
            by_rec[r.record_id].append(r.exception_id)
        adj = []
        excs = []
        for r in L.itertuples():
            a = []
            if r.delayed:
                a.append("DELAYED")
            if r.redated:
                a.append("REDATED_LEAD_TIME")
            if r.scaled:
                a.append("SCALED_CAPACITY")
            if not r.in_horizon:
                a.append("BEYOND_HORIZON")
            adj.append(";".join(a))
            e = by_rec.get(r.po_line_id, []) + by_rec.get(r.po_id, []) + (by_rec.get(r.capacity_id, []) if r.scaled else [])
            excs.append(";".join(e))
        out = pd.DataFrame({
            "po_line_id": L["po_line_id"], "po_id": L["po_id"], "supplier_id": L["supplier_id"],
            "location_id": L["location_id"], "sku_id": L["sku_id"], "credited_sku_id": L["credited_sku_id"],
            "base_qty": L["base_qty"], "effective_qty": L["effective_qty"],
            "original_eta": L["expected_receipt_date"], "effective_eta": L["effective_eta"],
            "effective_week_id": np.where(L["action"] == "INCLUDED", L["week_id_eff"], ""),
            "action": L["action"], "adjustments": adj, "exception_ids": excs})
        return out


def run_planning(t: dict[str, pd.DataFrame], n_weeks: int) -> dict[str, pd.DataFrame]:
    return Planner(t, n_weeks).run()
