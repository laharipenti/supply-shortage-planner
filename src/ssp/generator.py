"""Synthetic data generator (Steps 2-7 of the brief).

Order of generation (parents before children, valid baseline before anomalies):
  master   : location, supplier, sku, sku_location, bom, sku_substitute, supplier_sku, lead_time
  plans    : forecast_demand (+ spikes), production_plan, production_capacity
  derived  : safety stock, ABC class (computed from the generated demand, never random)
  inbound  : inventory, purchase_order, purchase_order_line, po_event (+ delays, cancellations,
             legitimate substitute purchases)
  inject   : 5 labelled anomaly types (each written to ground_truth with expected decision)
  capacity : supplier_capacity sized from the (normalised) PO load, then capacity breaches injected

All randomness comes from ONE numpy Generator seeded with the run seed, and every
loop iterates in a deterministic order, so the same seed gives byte-identical files.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import ids
from .config import AS_OF, ScaleConfig, week_id, week_start
from .engine import prepare_inbound
from .io import coerce
from .schema import TABLES

REGIONS = ["WEST", "CENTRAL", "EAST", "SOUTH"]
COUNTRIES = ["US", "MX", "CN", "IN", "VN", "DE"]
COUNTRY_P = [0.35, 0.15, 0.20, 0.10, 0.10, 0.10]
# (min LT, max LT, transport mode, min transit, max transit)
COUNTRY_LT = {"US": (7, 21, "TRUCK", 2, 5), "MX": (14, 28, "TRUCK", 4, 8), "CN": (35, 70, "OCEAN", 21, 32),
              "IN": (35, 63, "OCEAN", 20, 30), "VN": (35, 63, "OCEAN", 20, 30), "DE": (21, 45, "RAIL", 10, 18)}
FIN_CATS = ["ELECTRONICS", "HOME", "GROCERY", "APPAREL", "INDUSTRIAL"]
FIN_P = [0.2, 0.25, 0.25, 0.15, 0.15]
COMP_CATS = ["RAW_MATERIAL", "PACKAGING", "SUBASSEMBLY"]
COMP_P = [0.4, 0.3, 0.3]
COST_MU = {"ELECTRONICS": 4.0, "HOME": 2.8, "GROCERY": 1.5, "APPAREL": 2.6, "INDUSTRIAL": 3.2,
           "RAW_MATERIAL": 1.0, "PACKAGING": 0.3, "SUBASSEMBLY": 2.5}
# seasonality: (amplitude, peak week index)
SEASON = {"ELECTRONICS": (0.25, 46), "HOME": (0.15, 20), "GROCERY": (0.10, 50), "APPAREL": (0.30, 14),
          "INDUSTRIAL": (0.05, 30)}
AS_OF_S = AS_OF.isoformat()


def d2s(d: date) -> str:
    return d.isoformat()


def s2d(s: str) -> date:
    return date.fromisoformat(s)


class SyntheticGenerator:
    def __init__(self, cfg: ScaleConfig, seed: int):
        self.cfg, self.seed = cfg, seed
        self.rng = np.random.default_rng(seed)
        self.W = cfg.n_weeks
        self.gt: list[dict] = []
        self.t: dict[str, pd.DataFrame] = {}
        self.notes: list[str] = []

    # ------------------------------------------------------------------ utils
    def label(self, category, issue, entity, record, related="", decision="", desc=""):
        self.gt.append(dict(label_category=category, issue_type=issue, entity_type=entity, record_id=record,
                            related_record_id=related, expected_decision=decision, description=desc))

    def u(self, a, b):
        return float(self.rng.uniform(a, b))

    def ri(self, a, b):
        """random int in [a, b] inclusive"""
        return int(self.rng.integers(a, b + 1))

    def q(self, x, uom, mode="round"):
        if uom == "KG":
            return round(float(x), 3)
        if mode == "ceil":
            return float(math.ceil(float(x) - 1e-9))
        return float(round(float(x)))

    # ------------------------------------------------------------------ run
    def run(self) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
        self._locations()
        self._suppliers()
        self._skus()
        self._sku_locations_and_bom()
        self._substitutes()
        self._supplier_sku()
        self._lead_times()
        self._demand()
        self._production()
        self._gross_safety_abc()
        self._purchase_orders()
        self._demand_spikes()
        self._legit_substitutions()
        self._inject_lead_time()
        self._inject_unapproved_substitutes()
        self._inject_uom()
        self._inject_duplicates()
        self._finalise_po_tables()
        self._supplier_capacity()
        self._inject_capacity()
        tables = {name: self._order(name, df) for name, df in self.t.items()}
        gt = pd.DataFrame(self.gt)
        gt = gt.sort_values(["label_category", "issue_type", "record_id"]).reset_index(drop=True)
        gt.insert(0, "gt_id", [ids.gt_id(i + 1) for i in range(len(gt))])
        return tables, gt

    def _order(self, name, df):
        t = TABLES[name]
        return df[t.columns].sort_values(list(t.pk)).reset_index(drop=True)

    # ------------------------------------------------------------------ master
    def _locations(self):
        n = self.cfg.n_locations
        n_pl = max(1, round(n * 0.1))
        types = np.array(["PLANT"] * n_pl + ["DC"] * (n - n_pl))[self.rng.permutation(n)]
        regions = self.rng.choice(REGIONS, n)
        rows = []
        for i in range(n):
            nm = "Plant" if types[i] == "PLANT" else "Distribution Center"
            rows.append(dict(location_id=ids.loc_id(i + 1), location_name=f"{nm} {regions[i].title()} {i + 1:02d}",
                             location_type=types[i], region=regions[i], status="ACTIVE", effective_from="2024-01-01"))
        self.loc = pd.DataFrame(rows)
        self.t["location"] = self.loc
        self.plants = self.loc.loc[self.loc.location_type == "PLANT", "location_id"].tolist()
        self.dcs = self.loc.loc[self.loc.location_type == "DC", "location_id"].tolist()

    def _suppliers(self):
        n = self.cfg.n_suppliers
        rows = []
        for i in range(n):
            sid = ids.sup_id(i + 1)
            status = "ON_HOLD" if self.rng.random() < 0.03 else "ACTIVE"
            rows.append(dict(supplier_id=sid, supplier_name=f"Supplier {i + 1:04d}",
                             country=str(self.rng.choice(COUNTRIES, p=COUNTRY_P)),
                             reliability_score=round(float(np.clip(self.rng.beta(9, 1.5), 0.6, 0.995)), 3),
                             expedite_premium_pct=round(self.u(0.10, 0.35), 2), supplier_status=status,
                             effective_from="2024-01-01"))
        self.sup = pd.DataFrame(rows)
        self.t["supplier"] = self.sup
        self.sup_country = dict(zip(self.sup.supplier_id, self.sup.country))
        self.sup_weight = self.rng.pareto(1.5, n) + 1.0
        constrained = self.rng.random(n) < 0.10
        self.sup_constrained = dict(zip(self.sup.supplier_id, constrained))
        for sid, c in self.sup_constrained.items():
            if c:
                self.label("SCENARIO", "CONSTRAINED_SUPPLIER", "supplier", sid,
                           desc="capacity sized at 100-106% of peak load (little headroom)")

    def _skus(self):
        n = self.cfg.n_skus
        n_comp = max(10, round(n * 0.10))
        n_mfg = max(5, round(n * 0.05))
        types = np.array(["COMPONENT"] * n_comp + ["MANUFACTURED"] * n_mfg + ["FINISHED"] * (n - n_comp - n_mfg))
        types = types[self.rng.permutation(n)]
        rows = []
        for i in range(n):
            t = types[i]
            cat = str(self.rng.choice(COMP_CATS, p=COMP_P)) if t == "COMPONENT" else str(self.rng.choice(FIN_CATS, p=FIN_P))
            base = "KG" if cat == "RAW_MATERIAL" else "EA"
            upc = int(self.rng.choice([6, 12, 24, 48])) if base == "EA" else np.nan
            cost = round(max(0.1, float(self.rng.lognormal(COST_MU[cat], 0.5))), 2)
            if t == "FINISHED":
                life = str(self.rng.choice(["ACTIVE", "PHASE_IN", "PHASE_OUT"], p=[0.94, 0.03, 0.03]))
            else:
                life = "ACTIVE"
            intro = date(2019, 1, 1) + timedelta(days=self.ri(0, 2400))
            if life == "PHASE_IN":
                intro = date(2025, 10, 1) + timedelta(days=self.ri(0, 80))
            rows.append(dict(sku_id=ids.sku_id(i + 1), sku_name=f"{cat.title().replace('_', ' ')} Item {i + 1:06d}",
                             sku_type=t, category=cat, base_uom=base, case_uom="CS" if base == "EA" else "",
                             units_per_case=upc, unit_cost=cost, abc_class="C", lifecycle_status=life,
                             introduced_date=d2s(intro)))
        self.sku = pd.DataFrame(rows).set_index("sku_id", drop=False)
        self.ids_by_type = {k: self.sku.index[self.sku.sku_type == k].tolist()
                            for k in ("FINISHED", "MANUFACTURED", "COMPONENT")}

    def _sku_locations_and_bom(self):
        pairs = []
        for s in self.ids_by_type["FINISHED"]:
            k = min(len(self.dcs), int(self.rng.choice([1, 2, 3, 4], p=[0.35, 0.35, 0.2, 0.1])))
            for l in sorted(self.rng.choice(self.dcs, k, replace=False)):
                pairs.append((s, str(l)))
        mfg_plant = {}
        for s in self.ids_by_type["MANUFACTURED"]:
            p = str(self.rng.choice(self.plants))
            mfg_plant[s] = p
            pairs.append((s, p))
        comp_at = defaultdict(list)
        for c in self.ids_by_type["COMPONENT"]:
            k = min(len(self.plants), self.ri(1, 2))
            for p in sorted(self.rng.choice(self.plants, k, replace=False)):
                comp_at[str(p)].append(c)
                pairs.append((c, str(p)))
        # BOM: 2-5 components located at the parent's plant (prefer least-used components)
        usage = defaultdict(int)
        bom_rows = []
        for s in self.ids_by_type["MANUFACTURED"]:
            p = mfg_plant[s]
            while len(comp_at[p]) < 2:  # guarantee enough components at the plant
                c = str(self.rng.choice(self.ids_by_type["COMPONENT"]))
                if c not in comp_at[p]:
                    comp_at[p].append(c)
                    pairs.append((c, p))
            avail = sorted(comp_at[p], key=lambda c: (usage[c], self.rng.random()))
            nc = min(len(avail), self.ri(2, 5))
            for c in sorted(avail[:nc]):
                usage[c] += 1
                uom = self.sku.at[c, "base_uom"]
                qty = float(self.rng.choice([1, 2, 3, 4])) if uom == "EA" else round(self.u(0.1, 2.5), 3)
                bom_rows.append(dict(bom_id=ids.bom_id(s, c), parent_sku_id=s, component_sku_id=c, qty_per=qty,
                                     scrap_pct=round(self.u(0, 0.05), 3), effective_from="2024-01-01",
                                     effective_to=""))
        self.t["bom"] = pd.DataFrame(bom_rows)
        self.mfg_plant = mfg_plant
        sl = pd.DataFrame(sorted(set(pairs)), columns=["sku_id", "location_id"])
        sl["sku_type"] = sl.sku_id.map(self.sku.sku_type)
        self.sl = sl.reset_index(drop=True)
        self.sl_idx = {(s, l): i for i, (s, l) in enumerate(zip(sl.sku_id, sl.location_id))}

    def _substitutes(self):
        fin = self.sku.loc[self.ids_by_type["FINISHED"]]
        by_cat = {c: g.index.tolist() for c, g in fin.groupby("category")}
        n_a = max(6, round(len(fin) * 0.10))
        originals = sorted(self.rng.choice(fin.index.to_numpy(), n_a, replace=False))
        pairs = []
        for a in originals:
            pool = [b for b in by_cat[fin.at[a, "category"]] if b != a]
            for b in sorted(self.rng.choice(pool, min(len(pool), self.ri(1, 2)), replace=False)):
                pairs.append((a, str(b)))
        n = len(pairs)
        status = self.rng.choice(["APPROVED", "PENDING", "REJECTED"], n, p=[0.65, 0.22, 0.13])
        min_bad = 2 * self.cfg.anomalies_per_type  # make sure the edge case can be injected
        bad_needed = max(0, min_bad - int((status != "APPROVED").sum()))
        for k in range(n):
            if bad_needed and status[k] == "APPROVED":
                status[k] = "PENDING"
                bad_needed -= 1
        rows, prio = [], defaultdict(int)
        for (a, b), st in zip(pairs, status):
            prio[a] += 1
            rows.append(dict(substitute_id=ids.substitute_id(a, b), sku_id=a, substitute_sku_id=b,
                             approval_status=str(st), conversion_factor=1.0, priority=prio[a],
                             effective_from=d2s(date(2025, 1, 1) + timedelta(days=self.ri(0, 300))),
                             effective_to=""))
        self.subs = pd.DataFrame(rows)
        self.t["sku_substitute"] = self.subs

    def _supplier_sku(self):
        w = self.sup_weight / self.sup_weight.sum()
        sup_ids = self.sup.supplier_id.to_numpy()
        rows = {}
        self.primary = {}
        purchased = sorted(self.ids_by_type["FINISHED"] + self.ids_by_type["COMPONENT"])
        for s in purchased:
            k = int(self.rng.choice([1, 2, 3], p=[0.5, 0.35, 0.15]))
            chosen = self.rng.choice(sup_ids, k, replace=False, p=w)
            for j, sp in enumerate(chosen):
                rows[(str(sp), s)] = self._ss_row(str(sp), s, j == 0)
            self.primary[s] = str(chosen[0])
        # the primary supplier of an original SKU can also supply its substitutes
        for r in self.subs.itertuples():
            key = (self.primary[r.sku_id], r.substitute_sku_id)
            if key not in rows:
                rows[key] = self._ss_row(key[0], key[1], False)
        self.ss = pd.DataFrame(list(rows.values()))
        self.ss_map = {(r.supplier_id, r.sku_id): r for r in self.ss.itertuples()}
        self.t["supplier_sku"] = self.ss

    def _ss_row(self, sp, s, primary):
        base = self.sku.at[s, "base_uom"]
        if base == "EA":
            ou = "CS" if self.rng.random() < 0.6 else "EA"
            mult = float(self.sku.at[s, "units_per_case"]) if ou == "CS" else 1.0
            moq = mult * float(self.rng.choice([1, 2, 5, 10]))
        else:
            ou, mult = "KG", 1.0
            moq = float(self.rng.choice([25, 50, 100]))
        cost = self.sku.at[s, "unit_cost"]
        price = cost * (self.u(0.85, 1.0) if primary else self.u(0.95, 1.2))
        return dict(supplier_sku_id=ids.supplier_sku_id(sp, s), supplier_id=sp, sku_id=s, is_primary=primary,
                    order_uom=ou, order_multiple_base=mult, min_order_qty_base=moq,
                    unit_price=round(max(0.01, price), 2), sourcing_status="APPROVED", effective_from="2024-01-01")

    def _lead_times(self):
        rows = []
        self.lt = defaultdict(list)  # (sup, sku) -> [(from, to|None, lt, transit, mode)]
        for r in self.ss.sort_values("supplier_sku_id").itertuples():
            lo, hi, mode, tlo, thi = COUNTRY_LT[self.sup_country[r.supplier_id]]
            lt1 = self.ri(lo, hi)
            tr = min(self.ri(tlo, thi), lt1 - 1)
            versions = [(date(2024, 1, 1), lt1, tr)]
            if self.rng.random() < 0.25:
                frm = date(2025, 7, 1) + timedelta(days=self.ri(0, 150))
                lt2 = max(tr + 2, int(round(lt1 * self.u(0.8, 1.3))))
                versions.append((frm, lt2, tr))
            for v, (frm, ltd, trd) in enumerate(versions, 1):
                to = versions[v][0] - timedelta(days=1) if v < len(versions) else None
                self.lt[(r.supplier_id, r.sku_id)].append((frm, to, ltd, trd, mode))
                rows.append(dict(lead_time_id=ids.lead_time_id(r.supplier_id, r.sku_id, v), supplier_id=r.supplier_id,
                                 sku_id=r.sku_id, version=v, lead_time_days=ltd, transit_days=trd,
                                 transport_mode=mode, effective_from=d2s(frm), effective_to=d2s(to) if to else ""))
        self.t["lead_time"] = pd.DataFrame(rows)

    def lt_at(self, sp, s, d: date):
        for frm, to, ltd, trd, mode in self.lt[(sp, s)]:
            if frm <= d and (to is None or d <= to):
                return ltd, trd, mode
        return self.lt[(sp, s)][-1][2:]

    def lt_max(self, sp, s):
        return max(v[2] for v in self.lt[(sp, s)])

    # ------------------------------------------------------------------ demand
    def _demand(self):
        n, W = len(self.sl), self.W
        F = np.zeros((n, W))
        fc_rows = [i for i, t in enumerate(self.sl.sku_type) if t in ("FINISHED", "MANUFACTURED")]
        sku_mean = {s: float(np.clip(self.rng.lognormal(2.8, 1.0), 1, 2000)) for s in self.sku.index}
        self.mu = np.zeros((n, W))
        wk = np.arange(W)
        for i in fc_rows:
            s = self.sl.at[i, "sku_id"]
            amp, peak = SEASON[self.sku.at[s, "category"]]
            mu = sku_mean[s] * self.u(0.5, 1.5) * (1 + amp * np.cos(2 * np.pi * (wk - peak) / 52))
            life = self.sku.at[s, "lifecycle_status"]
            if life == "PHASE_IN":
                mu = np.where(wk < 8, 0.0, mu)
            elif life == "PHASE_OUT":
                mu = mu * np.linspace(1.0, 0.2, W)
            self.mu[i] = mu
            lam = self.rng.gamma(8.0, np.maximum(mu, 1e-6) / 8.0)
            F[i] = np.where(mu > 0, self.rng.poisson(lam), 0)
        self.F = F
        self.fc_rows = fc_rows
        sl = self.sl.iloc[fc_rows]
        rows_sku = np.repeat(sl.sku_id.to_numpy(), W)
        rows_loc = np.repeat(sl.location_id.to_numpy(), W)
        weeks = np.tile(np.array([week_id(w) for w in range(W)]), len(sl))
        dates = np.tile(np.array([d2s(week_start(w)) for w in range(W)]), len(sl))
        df = pd.DataFrame({"sku_id": rows_sku, "location_id": rows_loc, "week_id": weeks, "week_start_date": dates,
                           "forecast_qty": F[fc_rows].ravel()})
        df.insert(0, "demand_id", "DEM-" + df.sku_id + "-" + df.location_id + "-" + df.week_id)
        df["uom"] = "EA"
        df["forecast_version"] = "FV-2025W52"
        self.t["forecast_demand"] = df


    def _demand_spikes(self):
        """Late forecast changes (promotions / one-off orders) added AFTER inbound was planned,
        so supply was not sized for them. Labelled as a scenario."""
        W, F = self.W, self.F
        n_spike = max(3, round(len(self.fc_rows) * 0.03))
        for i in sorted(self.rng.choice(self.fc_rows, n_spike, replace=False)):
            start, ln, mult = self.ri(0, W - 3), self.ri(1, 3), self.u(2.5, 5.0)
            s, l = self.sl.at[i, "sku_id"], self.sl.at[i, "location_id"]
            for w in range(start, min(W, start + ln)):
                F[i, w] = round(max(F[i, w], self.mu[i, w], 1.0) * mult)
                self.label("SCENARIO", "DEMAND_SPIKE", "forecast_demand", ids.demand_id(s, l, week_id(w)),
                           related=f"{s}@{l}", desc=f"x{mult:.1f} spike added after inbound was planned")
        self.t["forecast_demand"]["forecast_qty"] = F[self.fc_rows].ravel()
        self.G = self.F + self.DD
        self._abc()

    # ------------------------------------------------------------------ production
    def _production(self):
        n, W = len(self.sl), self.W
        P = np.zeros((n, W))
        self.prod_first = {}
        for i, t in enumerate(self.sl.sku_type):
            if t != "MANUFACTURED":
                continue
            k = int(self.rng.choice([1, 2, 4]))
            off = self.ri(0, k - 1)
            constrained = self.rng.random() < 0.15
            ratio = self.u(0.70, 0.90) if constrained else self.u(0.95, 1.10)
            for w in range(off, W, k):
                P[i, w] = round(self.F[i, w:w + k].sum() * ratio)
            self.prod_first[i] = off
            if constrained:
                s, l = self.sl.at[i, "sku_id"], self.sl.at[i, "location_id"]
                self.label("SCENARIO", "PRODUCTION_CONSTRAINED", "sku_location", ids.sku_location_id(s, l),
                           desc=f"production plan covers {ratio:.0%} of demand")
        self.P = P
        rows, n_pp = [], 0
        for w in range(W):
            for i in sorted(np.where(P[:, w] > 0)[0], key=lambda i: (self.sl.at[i, "location_id"], self.sl.at[i, "sku_id"])):
                n_pp += 1
                rows.append(dict(production_plan_id=ids.production_plan_id(n_pp), sku_id=self.sl.at[i, "sku_id"],
                                 location_id=self.sl.at[i, "location_id"], week_id=week_id(w),
                                 week_start_date=d2s(week_start(w)), planned_qty=float(P[i, w]), uom="EA",
                                 plan_status="FIRM" if w < 4 else "PLANNED"))
        self.t["production_plan"] = pd.DataFrame(rows, columns=TABLES["production_plan"].columns)
        cap_rows = []
        for p in self.plants:
            rows_p = [i for i in range(n) if self.sl.at[i, "location_id"] == p and self.sl.at[i, "sku_type"] == "MANUFACTURED"]
            load = P[rows_p].sum(axis=0) if rows_p else np.zeros(W)
            pc = max(500.0, load.max() * self.u(1.1, 1.5))
            for w in range(W):
                cap_rows.append(dict(production_capacity_id=ids.prod_capacity_id(p, week_id(w)), location_id=p,
                                     week_id=week_id(w), week_start_date=d2s(week_start(w)),
                                     capacity_units=float(max(load[w], round(pc * self.u(0.9, 1.0))))))
        self.t["production_capacity"] = pd.DataFrame(cap_rows)
        # dependent demand: identical formula to the engine (planned * qty_per * (1+scrap), EA rounded up)
        DD = np.zeros((n, W))
        for b in self.t["bom"].itertuples():
            ip = self.sl_idx[(b.parent_sku_id, self.mfg_plant[b.parent_sku_id])]
            ic = self.sl_idx[(b.component_sku_id, self.mfg_plant[b.parent_sku_id])]
            uom = self.sku.at[b.component_sku_id, "base_uom"]
            for w in np.where(P[ip] > 0)[0]:
                DD[ic, w] += self.q(P[ip, w] * b.qty_per * (1 + b.scrap_pct), uom, "ceil")
        self.DD = DD

    def _gross_safety_abc(self):
        self.G = self.F + self.DD
        ss = []
        for i in range(len(self.sl)):
            s = self.sl.at[i, "sku_id"]
            g = self.G[i]
            mean = g.mean() if g.sum() > 0 else 0.0
            ss.append(self.q(mean * self.u(0.5, 2.0), self.sku.at[s, "base_uom"], "ceil"))
        self.ss_qty = np.array(ss)
        sl = self.sl.copy()
        sl.insert(0, "sku_location_id", [ids.sku_location_id(a, b) for a, b in zip(sl.sku_id, sl.location_id)])
        sl["safety_stock_qty"] = self.ss_qty
        sl["stocking_status"] = "ACTIVE"
        sl["effective_from"] = "2024-01-01"
        self.t["sku_location"] = sl
        self._abc()

    def _abc(self):
        # ABC from annual requirement value (derived, Step 6)
        val = pd.Series(self.G.sum(axis=1), index=self.sl.sku_id).groupby(level=0).sum()
        val = (val * self.sku.unit_cost.reindex(val.index)).reindex(self.sku.index).fillna(0.0)
        order = val.sort_values(ascending=False, kind="mergesort")
        cum = order.cumsum() / max(order.sum(), 1e-9)
        abc = pd.Series(np.where(cum <= 0.8, "A", np.where(cum <= 0.95, "B", "C")), index=order.index)
        abc[order == 0] = "C"
        self.sku["abc_class"] = abc.reindex(self.sku.index).values
        self.t["sku"] = self.sku.reset_index(drop=True)

    # ------------------------------------------------------------------ inbound
    def _purchase_orders(self):
        W = self.W
        purch = [i for i, t in enumerate(self.sl.sku_type) if t in ("FINISHED", "COMPONENT")]
        groups = defaultdict(list)
        for i in purch:
            groups[(self.primary[self.sl.at[i, "sku_id"]], self.sl.at[i, "location_id"])].append(i)
        pair_keys = sorted(groups)
        dem = np.array([sum(self.G[i].sum() for i in groups[k]) for k in pair_keys])
        n_pos = self.cfg.n_purchase_orders
        P = len(pair_keys)
        k = np.zeros(P, dtype=int)
        if P > n_pos:
            top = np.argsort(-dem, kind="mergesort")[:n_pos]
            k[top] = 1
            self.notes.append(f"{P - n_pos} supplier-location pairs received no PO (more pairs than orders)")
        else:
            k[:] = 1
            wts = (dem + 1) ** 0.7
            k += self.rng.multinomial(n_pos - P, wts / wts.sum())
            cap = 26
            while (k > cap).any():  # redistribute overflow deterministically
                over = int((k[k > cap] - cap).sum())
                k = np.minimum(k, cap)
                room = np.where(k < cap)[0]
                k += np.bincount(self.rng.choice(room, over), minlength=P)
        headers, self.first_receipt = [], {}
        oh = np.zeros(len(self.sl))
        for p_i, key in enumerate(pair_keys):
            kk = int(k[p_i])
            sp, l = key
            if kk == 0:
                for i in groups[key]:
                    self.first_receipt[i] = W
                continue
            spacing = W / kk
            off = self.u(0, spacing)
            weeks = sorted(set(int(min(W - 1, math.floor(off + j * spacing))) for j in range(kk)))
            while len(weeks) < kk:  # only possible when kk > W
                weeks.append(weeks[-1])
            lines_by_hdr = [[] for _ in weeks]
            for i in groups[key]:
                s = self.sl.at[i, "sku_id"]
                uom = self.sku.at[s, "base_uom"]
                g = self.G[i]
                f = weeks[0]
                self.first_receipt[i] = f
                before = g[:f].sum()
                if self.rng.random() < 0.12 and before > 0:
                    oh[i] = self.q(before * self.u(0.4, 0.9), uom)
                    self.label("SCENARIO", "LOW_OPENING_STOCK", "inventory",
                               ids.inventory_id(s, l, AS_OF.strftime("%Y%m%d")),
                               desc="opening stock below demand until first receipt")
                else:
                    oh[i] = self.q(before * self.u(0.95, 1.35) + self.ss_qty[i] * self.u(0.5, 1.0), uom)
                if self.rng.random() < 0.12:
                    r = self.u(0.65, 0.90)
                    self.label("SCENARIO", "UNDER_REPLENISHED", "sku_location", ids.sku_location_id(s, l),
                               desc=f"planned inbound covers {r:.0%} of demand")
                else:
                    r = self.u(1.0, 1.12)
                need = r * g[f:].sum() + self.ss_qty[i] * self.u(0.5, 1.0)
                bounds = list(weeks) + [W]
                wins = np.array([g[bounds[j]:bounds[j + 1]].sum() for j in range(len(weeks))])
                if wins.sum() == 0:
                    wins = np.ones(len(weeks))
                ssr = self.ss_map[(sp, s)]
                mult, moq = ssr.order_multiple_base, ssr.min_order_qty_base
                catch_up = max(0.0, before - oh[i])  # a planner tops up the first receipt to clear backlog
                for j in range(len(weeks)):
                    base = need * wins[j] / wins.sum() + (catch_up if j == 0 else 0.0)
                    base = max(moq, math.ceil(base / mult - 1e-9) * mult)
                    base = round(base, 3)
                    oq = base / mult if ssr.order_uom == "CS" else base
                    lines_by_hdr[j].append(dict(sku_id=s, substitute_for_sku_id="", order_qty=round(oq, 3),
                                                uom=ssr.order_uom, unit_price=ssr.unit_price, _base=base))
            for j, w in enumerate(weeks):
                receipt = week_start(w) + timedelta(days=self.ri(0, 4))
                skus = [ln["sku_id"] for ln in lines_by_hdr[j]]
                mlt = max(self.lt_max(sp, s) for s in skus)
                order = receipt - timedelta(days=mlt + self.ri(0, 30))
                worst = max(skus, key=lambda s: (self.lt_max(sp, s), s))
                _, transit, mode = self.lt_at(sp, worst, order)
                transit = max(self.lt_at(sp, s, order)[1] for s in skus)
                headers.append(dict(supplier_id=sp, location_id=l, order_date=order, expected_receipt_date=receipt,
                                    transport_mode=mode, transit=transit, lines=lines_by_hdr[j]))
        # inventory (on-hand covers manufactured items until first production week)
        for i, t in enumerate(self.sl.sku_type):
            if t == "MANUFACTURED":
                f = self.prod_first[i]
                uom = "EA"
                oh[i] = self.q(self.G[i, :f].sum() * self.u(0.95, 1.35) + self.ss_qty[i] * self.u(0.5, 1.0), uom)
        inv = []
        snap = AS_OF.strftime("%Y%m%d")
        for i in range(len(self.sl)):
            s, l = self.sl.at[i, "sku_id"], self.sl.at[i, "location_id"]
            uom = self.sku.at[s, "base_uom"]
            hold = self.q(oh[i] * self.u(0.05, 0.2), uom) if self.rng.random() < 0.05 else 0.0
            inv.append(dict(inventory_id=ids.inventory_id(s, l, snap), sku_id=s, location_id=l, snapshot_date=AS_OF_S,
                            on_hand_qty=round(oh[i] + hold, 3), on_hold_qty=hold, uom=uom))
        self.t["inventory"] = pd.DataFrame(inv)
        # deterministic PO numbering: by order date, supplier, location, receipt
        headers.sort(key=lambda h: (h["order_date"], h["supplier_id"], h["location_id"], h["expected_receipt_date"]))
        perm = self.rng.permutation(len(headers) * 3)[: len(headers)]
        self.headers = []
        for n, (h, ref) in enumerate(zip(headers, perm), 1):
            h["po_id"] = ids.po_id(n)
            h["supplier_ref"] = f"SO-{int(ref) + 1000000:07d}"
            for ln_no, ln in enumerate(h["lines"], 1):
                ln["po_line_id"] = ids.po_line_id(h["po_id"], ln_no)
                ln["line_no"] = ln_no
            h["events"] = self._events(h)
            self.headers.append(h)
        self.n_baseline_pos = len(self.headers)
        self.touched: set[str] = set()

    def _events(self, h):
        ev = []

        def add(etype, d, frm, to, eta="", reason="", actor="SUPPLIER"):
            ev.append(dict(event_type=etype, event_date=d, from_status=frm, to_status=to, revised_eta=eta,
                           reason_code=reason, actor=actor))

        od, rc = h["order_date"], h["expected_receipt_date"]
        if od <= AS_OF:
            add("CREATED", od, "", "CREATED", actor="PLANNER")
            conf = od + timedelta(days=self.ri(1, 4))
            if conf <= AS_OF:
                add("CONFIRMED", conf, "CREATED", "CONFIRMED")
                ship = max(rc - timedelta(days=h["transit"]), conf + timedelta(days=1))
                if ship <= AS_OF:
                    add("SHIPPED", ship, "CONFIRMED", "IN_TRANSIT", actor="CARRIER")
        else:  # firm planned order, released on order_date
            add("CREATED", AS_OF - timedelta(days=self.ri(1, 45)), "", "CREATED", actor="PLANNER")
        status, last = ev[-1]["to_status"], ev[-1]["event_date"]
        if status != "IN_TRANSIT" and last < AS_OF and self.rng.random() < 0.015:
            add("CANCELLED", last + timedelta(days=self.ri(1, (AS_OF - last).days)), status, "CANCELLED",
                reason="BUYER_CANCELLED", actor="PLANNER")
        elif status in ("CONFIRMED", "IN_TRANSIT") and last < AS_OF and self.rng.random() < 0.15:
            eta = rc
            for _ in range(2 if self.rng.random() < 0.15 else 1):
                last = ev[-1]["event_date"]
                if last >= AS_OF:
                    break
                d = last + timedelta(days=self.ri(1, (AS_OF - last).days))
                eta = eta + timedelta(days=self.ri(7, 35))
                if status == "IN_TRANSIT":
                    reason, actor = str(self.rng.choice(["CARRIER_DELAY", "PORT_CONGESTION", "WEATHER"])), "CARRIER"
                else:
                    reason, actor = "SUPPLIER_DELAY", "SUPPLIER"
                add("DELAYED", d, ev[-1]["to_status"], "DELAYED", eta=eta, reason=reason, actor=actor)
            kind = "TRANSPORT_DELAY" if status == "IN_TRANSIT" else "SUPPLIER_DELAY"
            h["_delay_label"] = (kind, f"ETA {rc} -> {eta}")
        return ev

    def _sub_line_ok(self, h, ln, b):
        """Can line ln (for SKU A) be bought as substitute b from the same supplier without breaking lead time?"""
        key = (h["supplier_id"], b)
        if key not in self.ss_map:
            return False
        ltd = self.lt_at(h["supplier_id"], b, h["order_date"])[0]
        return (h["expected_receipt_date"] - h["order_date"]).days >= ltd

    def _swap_line(self, h, ln, a, b):
        base = ln["_base"]
        r = self.ss_map[(h["supplier_id"], b)]
        if r.order_uom == "CS":
            oq = math.ceil(base / r.order_multiple_base - 1e-9)
            base = oq * r.order_multiple_base
        else:
            oq = base
        ln.update(sku_id=b, substitute_for_sku_id=a, order_qty=round(float(oq), 3), uom=r.order_uom,
                  unit_price=r.unit_price, _base=round(float(base), 3))

    def _candidate_lines(self, sku_ids, require_live=True):
        out = []
        for h in self.headers:
            if h["po_id"] in self.touched:
                continue
            if require_live and h["events"][-1]["to_status"] == "CANCELLED":
                continue
            for ln in h["lines"]:
                if ln["sku_id"] in sku_ids and ln["substitute_for_sku_id"] == "" and h["supplier_id"] == self.primary.get(ln["sku_id"]):
                    out.append((h, ln))
        return out

    def _legit_substitutions(self):
        appr = self.subs[self.subs.approval_status == "APPROVED"]
        n = max(3, round(len(appr) * 0.3))
        done = 0
        for r in appr.iloc[self.rng.permutation(len(appr))].itertuples():
            if done >= n:
                break
            cands = [(h, ln) for h, ln in self._candidate_lines({r.sku_id})
                     if self._sub_line_ok(h, ln, r.substitute_sku_id) and s2d(r.effective_from) <= h["order_date"]]
            if not cands:
                continue
            h, ln = cands[self.ri(0, len(cands) - 1)]
            self._swap_line(h, ln, r.sku_id, r.substitute_sku_id)
            self.touched.add(h["po_id"])
            self.label("SCENARIO", "SUBSTITUTE_SKU", "purchase_order_line", ln["po_line_id"], related=r.substitute_id,
                       desc="approved substitute bought to cover original SKU")
            done += 1

    # ------------------------------------------------------------------ anomalies
    def _inject_lead_time(self):
        n = self.cfg.anomalies_per_type
        cands = []
        for h in self.headers:
            if h["po_id"] in self.touched or h["events"][-1]["to_status"] != "CREATED" or h["order_date"] <= AS_OF:
                continue
            min_lt = min(min(v[2] for v in self.lt[(h["supplier_id"], ln["sku_id"])]) for ln in h["lines"])
            if min_lt >= 7 and h["expected_receipt_date"] > AS_OF + timedelta(days=min_lt):
                cands.append((h, min_lt))
        for idx in sorted(self.rng.choice(len(cands), min(n, len(cands)), replace=False)):
            h, min_lt = cands[idx]
            x = self.ri(1, max(2, min_lt // 3))
            new_order = h["expected_receipt_date"] - timedelta(days=x)
            if new_order <= AS_OF:
                continue
            old = h["order_date"]
            h["order_date"] = new_order
            self.touched.add(h["po_id"])
            self.label("ANOMALY", "SHORTAGE_WITHOUT_LEAD_TIME", "purchase_order", h["po_id"],
                       decision="REDATE_RECEIPT_TO_LEAD_TIME",
                       desc=f"receipt date set {x}d after order (was ordered {old}); supplier lead time ignored")
        self._check_count("SHORTAGE_WITHOUT_LEAD_TIME")

    def _inject_unapproved_substitutes(self):
        n = self.cfg.anomalies_per_type
        bad = self.subs[self.subs.approval_status != "APPROVED"]
        done = 0
        for r in bad.iloc[self.rng.permutation(len(bad))].itertuples():
            if done >= n:
                break
            cands = [(h, ln) for h, ln in self._candidate_lines({r.sku_id}) if self._sub_line_ok(h, ln, r.substitute_sku_id)]
            if not cands:
                continue
            h, ln = cands[self.ri(0, len(cands) - 1)]
            self._swap_line(h, ln, r.sku_id, r.substitute_sku_id)
            self.touched.add(h["po_id"])
            self.label("ANOMALY", "SUBSTITUTE_NOT_APPROVED", "purchase_order_line", ln["po_line_id"],
                       related=r.substitute_id, decision="EXCLUDE_FROM_SUPPLY",
                       desc=f"{r.substitute_sku_id} bought for {r.sku_id} but pair is {r.approval_status}")
            done += 1
        self._check_count("SUBSTITUTE_NOT_APPROVED")

    def _inject_uom(self):
        n = self.cfg.anomalies_per_type
        cands = [(h, ln) for h in self.headers if h["po_id"] not in self.touched
                 and h["events"][-1]["to_status"] != "CANCELLED" for ln in h["lines"]]
        for idx in sorted(self.rng.choice(len(cands), min(n, len(cands)), replace=False)):
            h, ln = cands[idx]
            base = self.sku.at[ln["sku_id"], "base_uom"]
            wrong = "KG" if base == "EA" else "EA"
            old = ln["uom"]
            ln["uom"] = wrong
            self.touched.add(h["po_id"])
            self.label("ANOMALY", "UOM_MISMATCH", "purchase_order_line", ln["po_line_id"], related=ln["sku_id"],
                       decision="QUARANTINE_LINE", desc=f"line uom {wrong} (should be {old}) for {base} item")
        self._check_count("UOM_MISMATCH")

    def _inject_duplicates(self):
        n = self.cfg.anomalies_per_type
        cands = [h for h in self.headers if h["po_id"] not in self.touched and h["events"][-1]["to_status"] != "CANCELLED"]
        next_no = len(self.headers) + 1
        for idx in sorted(self.rng.choice(len(cands), min(n, len(cands)), replace=False)):
            src = cands[idx]
            dup = {k: (v.copy() if isinstance(v, dict) else v) for k, v in src.items() if k not in ("lines", "events")}
            dup["po_id"] = ids.po_id(next_no)
            next_no += 1
            dup["lines"] = []
            for ln in src["lines"]:
                c = dict(ln)
                c["po_line_id"] = ids.po_line_id(dup["po_id"], ln["line_no"])
                dup["lines"].append(c)
            dup["events"] = [dict(e) for e in src["events"]]
            dup.pop("_delay_label", None)
            self.headers.append(dup)
            self.touched.update({src["po_id"], dup["po_id"]})
            self.label("ANOMALY", "INBOUND_COUNTED_TWICE", "purchase_order", dup["po_id"], related=src["po_id"],
                       decision="EXCLUDE_DUPLICATE", desc=f"copy of {src['po_id']} with same supplier_ref {src['supplier_ref']}")
        self._check_count("INBOUND_COUNTED_TWICE")

    def _check_count(self, issue):
        got = sum(1 for g in self.gt if g["issue_type"] == issue)
        if got < self.cfg.anomalies_per_type:
            self.notes.append(f"{issue}: only {got} of {self.cfg.anomalies_per_type} could be injected")

    def _finalise_po_tables(self):
        po, pol, ev = [], [], []
        for h in self.headers:
            po.append(dict(po_id=h["po_id"], supplier_id=h["supplier_id"], location_id=h["location_id"],
                           supplier_ref=h["supplier_ref"], order_date=d2s(h["order_date"]),
                           expected_receipt_date=d2s(h["expected_receipt_date"]), transport_mode=h["transport_mode"],
                           currency="USD", po_status=h["events"][-1]["to_status"]))
            for ln in h["lines"]:
                pol.append(dict(po_line_id=ln["po_line_id"], po_id=h["po_id"], line_no=ln["line_no"], sku_id=ln["sku_id"],
                                substitute_for_sku_id=ln["substitute_for_sku_id"], order_qty=ln["order_qty"],
                                uom=ln["uom"], unit_price=ln["unit_price"]))
            for seq, e in enumerate(h["events"], 1):
                ev.append(dict(event_id=ids.po_event_id(h["po_id"], seq), po_id=h["po_id"], event_seq=seq,
                               event_type=e["event_type"], event_date=d2s(e["event_date"]), from_status=e["from_status"],
                               to_status=e["to_status"], revised_eta=d2s(e["revised_eta"]) if e["revised_eta"] else "",
                               reason_code=e["reason_code"], actor=e["actor"]))
            if h["events"][-1]["to_status"] == "CANCELLED":
                self.label("SCENARIO", "PO_CANCELLED", "purchase_order", h["po_id"],
                           desc="cancelled by buyer before shipment (normal exception path)")
            if "_delay_label" in h:
                kind, desc = h["_delay_label"]
                self.label("SCENARIO", kind, "purchase_order", h["po_id"], desc=desc)
        self.t["purchase_order"] = pd.DataFrame(po)
        self.t["purchase_order_line"] = pd.DataFrame(pol)
        self.t["po_event"] = pd.DataFrame(ev)

    # ------------------------------------------------------------------ capacity
    def _typed(self, names):
        return {n: coerce(self.t[n], n) for n in names}

    def _supplier_capacity(self):
        typed = self._typed(["purchase_order", "purchase_order_line", "po_event", "sku", "lead_time", "sku_substitute"])
        L = prepare_inbound(typed, self.W)
        x = L[L["counts_for_load"] & L["in_horizon"]]
        load = x.groupby(["supplier_id", "eff_week"])["base_qty"].sum()
        rows = []
        self.load = {}
        for sp in self.sup.supplier_id:
            lw = np.array([float(load.get((sp, w), 0.0)) for w in range(self.W)])
            hr = self.u(1.0, 1.06) if self.sup_constrained[sp] else self.u(1.15, 1.6)
            base = max(100.0, lw.max() * hr)
            for w in range(self.W):
                self.load[(sp, w)] = lw[w]
                cap = max(math.ceil(lw[w] - 1e-9), round(base * self.u(0.92, 1.0)))
                rows.append(dict(capacity_id=ids.capacity_id(sp, week_id(w)), supplier_id=sp, week_id=week_id(w),
                                 week_start_date=d2s(week_start(w)), capacity_units=float(cap)))
        self.t["supplier_capacity"] = pd.DataFrame(rows)

    def _inject_capacity(self):
        n = self.cfg.anomalies_per_type
        cap = self.t["supplier_capacity"]
        cands = sorted([k for k, v in self.load.items() if v >= 10])
        picked, used = [], set()
        for j in self.rng.permutation(len(cands)):
            sp, w = cands[j]
            if sp in used:
                continue
            picked.append((sp, w))
            used.add(sp)
            if len(picked) >= n:
                break
        for sp, w in sorted(picked):
            cid = ids.capacity_id(sp, week_id(w))
            new = float(math.floor(self.load[(sp, w)] * self.u(0.55, 0.85)))
            cap.loc[cap.capacity_id == cid, "capacity_units"] = new
            self.label("ANOMALY", "SUPPLIER_CAPACITY_EXCEEDED", "supplier_capacity", cid, related=sp,
                       decision="CONSTRAIN_RECEIPTS_TO_CAPACITY",
                       desc=f"capacity {new:g} below scheduled load {self.load[(sp, w)]:g}")
        self._check_count("SUPPLIER_CAPACITY_EXCEEDED")


def generate(cfg: ScaleConfig, seed: int):
    g = SyntheticGenerator(cfg, seed)
    tables, gt = g.run()
    return tables, gt, g.notes
