"""Step 10: same seed -> identical bytes; different seed -> different data."""
import hashlib

from ssp.config import DEFAULT_SEED, get_scale
from ssp.generator import generate
from ssp.io import to_export


def fingerprint(seed, cfg):
    tables, gt, _ = generate(cfg, seed)
    h = {}
    for name, df in sorted(tables.items()):
        h[name] = (len(df), hashlib.sha256(to_export(df, name).to_csv(index=False).encode()).hexdigest())
    h["ground_truth"] = (len(gt), hashlib.sha256(to_export(gt, "ground_truth").to_csv(index=False).encode()).hexdigest())
    return h


def test_same_seed_identical():
    cfg = get_scale("tiny")
    assert fingerprint(DEFAULT_SEED, cfg) == fingerprint(DEFAULT_SEED, cfg)


def test_different_seed_differs():
    cfg = get_scale("tiny")
    a, b = fingerprint(DEFAULT_SEED, cfg), fingerprint(DEFAULT_SEED + 1, cfg)
    assert sum(a[k][1] != b[k][1] for k in a) >= len(a) - 2


def test_scale_is_parameterised():
    cfg = get_scale("tiny", n_skus=120, n_locations=5, n_suppliers=20, n_purchase_orders=300)
    tables, gt, _ = generate(cfg, DEFAULT_SEED)
    assert len(tables["sku"]) == 120
    assert len(tables["location"]) == 5
    assert len(tables["supplier"]) == 20
    n_dup = (gt.issue_type == "INBOUND_COUNTED_TWICE").sum()
    assert len(tables["purchase_order"]) == 300 + n_dup
    assert tables["forecast_demand"].week_id.nunique() == 52
