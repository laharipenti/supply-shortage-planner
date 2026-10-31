"""Step 9: JSON + SQL seed export, manifest with checksums and provenance."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd

from .config import AS_OF, GENERATOR_VERSION, ScaleConfig
from .schema import DERIVED_TABLES, INPUT_TABLES, TABLES

SQL_TYPES = {"string": "TEXT", "int": "INTEGER", "decimal": "REAL", "date": "TEXT", "bool": "INTEGER"}


def _typed_records(path: Path, table: str) -> list[dict]:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    t = TABLES[table]
    recs = []
    conv = []
    for f in t.fields:
        if f.type == "int":
            conv.append((f.name, lambda v: int(v) if v != "" else None))
        elif f.type == "decimal":
            conv.append((f.name, lambda v: (int(float(v)) if float(v).is_integer() else float(v)) if v != "" else None))
        elif f.type == "bool":
            conv.append((f.name, lambda v: v == "true"))
        else:
            conv.append((f.name, lambda v: v if v != "" else None))
    for row in raw.itertuples(index=False):
        d = row._asdict()
        recs.append({k: fn(d[k]) for k, fn in conv})
    return recs


def export_json(out: Path):
    for layer, tables in (("input", INPUT_TABLES), ("derived", DERIVED_TABLES), ("ground_truth", ["ground_truth"])):
        for t in tables:
            dst = out / "json" / layer / f"{t}.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "w", newline="\n") as fh:
                json.dump(_typed_records(out / layer / f"{t}.csv", t), fh, separators=(",", ":"))
    # ground truth also next to its CSV (brief asks for ground_truth.csv/json)
    gt = out / "ground_truth" / "ground_truth.json"
    with open(gt, "w", newline="\n") as fh:
        json.dump(_typed_records(out / "ground_truth" / "ground_truth.csv", "ground_truth"), fh, indent=1)


def create_table_sql(table: str) -> str:
    t = TABLES[table]
    cols = [f'  "{f.name}" {SQL_TYPES[f.type]}{" NOT NULL" if f.required else ""}' for f in t.fields]
    cols.append(f"  PRIMARY KEY ({', '.join(t.pk)})")
    for c, ref, rc in t.fks:
        cols.append(f'  FOREIGN KEY ("{c}") REFERENCES {ref}("{rc}")')
    return f"CREATE TABLE {table} (\n" + ",\n".join(cols) + "\n);\n"


def _sql_value(v: str, typ: str) -> str:
    if v == "":
        return "NULL"
    if typ in ("int", "decimal"):
        return v
    if typ == "bool":
        return "1" if v == "true" else "0"
    return "'" + v.replace("'", "''") + "'"


def _inserts(path: Path, table: str, fh, chunk=500):
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    t = TABLES[table]
    types = [f.type for f in t.fields]
    cols = ", ".join(f'"{f.name}"' for f in t.fields)
    rows = raw[t.columns].to_numpy()
    for s in range(0, len(rows), chunk):
        vals = ",\n".join("(" + ", ".join(_sql_value(v, ty) for v, ty in zip(r, types)) + ")" for r in rows[s:s + chunk])
        fh.write(f"INSERT INTO {table} ({cols}) VALUES\n{vals};\n")


def export_sql(out: Path):
    d = out / "sql"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "schema.sql", "w", newline="\n") as fh:
        fh.write("-- Generated from src/ssp/schema.py. SQLite / PostgreSQL compatible.\n")
        for t in INPUT_TABLES + DERIVED_TABLES:
            fh.write(create_table_sql(t) + "\n")
    with open(d / "seed.sql", "w", newline="\n") as fh:
        fh.write("-- Seed data (input + derived layers). Load after schema.sql.\nBEGIN;\n")
        for t in INPUT_TABLES:
            _inserts(out / "input" / f"{t}.csv", t, fh)
        for t in DERIVED_TABLES:
            _inserts(out / "derived" / f"{t}.csv", t, fh)
        fh.write("COMMIT;\n")
    with open(d / "ground_truth.sql", "w", newline="\n") as fh:
        fh.write("-- Ground truth labels: keep OUT of any feature/training table.\n")
        fh.write(create_table_sql("ground_truth"))
        _inserts(out / "ground_truth" / "ground_truth.csv", "ground_truth", fh)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def data_files(out: Path) -> list[Path]:
    files = []
    for sub in ("input", "derived", "ground_truth", "json", "sql"):
        files += sorted((out / sub).rglob("*.*")) if (out / sub).exists() else []
    return files


def write_manifest(out: Path, cfg: ScaleConfig, seed: int, command: str, notes: list[str]) -> dict:
    files = []
    for p in data_files(out):
        rows = None
        if p.suffix == ".csv":
            with open(p, "rb") as fh:
                rows = sum(1 for _ in fh) - 1
        files.append(dict(path=str(p.relative_to(out)).replace("\\", "/"), rows=rows, bytes=p.stat().st_size,
                          sha256=sha256(p)))
    man = dict(
        generator_version=GENERATOR_VERSION, seed=seed, scale=cfg.to_dict(), as_of_date=AS_OF.isoformat(),
        generator_command=command,
        environment=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__),
        provenance=dict(
            data_origin="100% synthetic, produced by src/ssp/generator.py from a fixed seed",
            external_data_used=False,
            external_sources=[],
            schema_inspiration=["ISO 8601 week-date calendar (public standard) for week IDs",
                                "Generic MRP / projected-available-balance logic (textbook supply planning)"],
            personal_data="none - names are generated placeholders (e.g. 'Supplier 0001')",
            license="Generated data released with the repository (MIT)"),
        generator_notes=notes,
        files=files)
    with open(out / "manifest.json", "w", newline="\n") as fh:
        json.dump(man, fh, indent=2)
    return man
