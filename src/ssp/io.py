"""CSV read/write with schema-driven typing. Dates are ISO strings on disk."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .schema import TABLES


def coerce(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Convert columns to the types declared in the schema (in a copy)."""
    t = TABLES[table]
    out = df.copy()
    for f in t.fields:
        if f.name not in out.columns:
            continue
        s = out[f.name]
        if f.type in ("int", "decimal"):
            s = pd.to_numeric(s.replace("", np.nan), errors="coerce")
            out[f.name] = s.astype("float64")
        elif f.type == "date":
            out[f.name] = pd.to_datetime(s.replace("", None), errors="coerce")
        elif f.type == "bool":
            out[f.name] = s.map(lambda v: v if isinstance(v, (bool, np.bool_)) else str(v).strip().lower() == "true").astype(bool)
        else:
            out[f.name] = s.fillna("").astype(str)
    return out


def to_export(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Format a typed frame for CSV/JSON: ISO dates, rounded decimals, ints as ints."""
    t = TABLES[table]
    out = pd.DataFrame(index=df.index)
    for f in t.fields:
        s = df[f.name]
        if f.type == "date":
            s = pd.to_datetime(s, errors="coerce")
            out[f.name] = s.dt.strftime("%Y-%m-%d").fillna("")
        elif f.type == "int":
            s = pd.to_numeric(s, errors="coerce")
            out[f.name] = s.map(lambda v: "" if pd.isna(v) else str(int(round(v))))
        elif f.type == "decimal":
            s = pd.to_numeric(s, errors="coerce").round(3)
            out[f.name] = s.map(lambda v: "" if pd.isna(v) else _fmt(v))
        elif f.type == "bool":
            out[f.name] = s.map(lambda v: "true" if bool(v) else "false")
        else:
            out[f.name] = s.fillna("").astype(str)
    return out.reset_index(drop=True)


def _fmt(v: float) -> str:
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.3f}".rstrip("0").rstrip(".")


def write_csv(df: pd.DataFrame, table: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    to_export(df, table).to_csv(path, index=False, lineterminator="\n")
    return path


def read_csv(path: Path, table: str) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    return coerce(raw, table)


def read_layer(folder: Path, tables: list[str]) -> dict[str, pd.DataFrame]:
    return {t: read_csv(folder / f"{t}.csv", t) for t in tables}
