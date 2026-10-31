"""End-to-end orchestration: generate -> plan -> validate -> evaluate -> export."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .config import DEFAULT_SEED, ScaleConfig
from .engine import run_planning
from .evaluate import evaluate, to_markdown as eval_md
from .export import export_json, export_sql, write_manifest
from .generator import generate
from .io import read_layer, write_csv
from .schema import INPUT_TABLES
from .validate import to_markdown as val_md, validate


def log(msg: str):
    print(f"[ssp] {msg}", flush=True)


def run(cfg: ScaleConfig, seed: int = DEFAULT_SEED, out: Path | str = "output/starter",
        formats: tuple = ("csv", "json", "sql"), command: str = "", quiet: bool = False) -> dict:
    out = Path(out)
    say = (lambda m: None) if quiet else log
    if out.exists():
        shutil.rmtree(out)
    t0 = time.time()

    say(f"1/5 generating synthetic data (scale={cfg.name}, seed={seed})")
    tables, gt, notes = generate(cfg, seed)
    for name, df in tables.items():
        write_csv(df, name, out / "input" / f"{name}.csv")
    write_csv(gt, "ground_truth", out / "ground_truth" / "ground_truth.csv")

    say("2/5 planning: projection, shortages, mitigations (reads input/ only)")
    inputs = read_layer(out / "input", INPUT_TABLES)
    derived = run_planning(inputs, cfg.n_weeks)
    for name, df in derived.items():
        write_csv(df, name, out / "derived" / f"{name}.csv")

    say("3/5 validating")
    vres = validate(out)
    rep = out / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "validation_summary.json").write_text(json.dumps(vres, indent=2, default=str), newline="\n")
    (rep / "validation_summary.md").write_text(val_md(vres), newline="\n")

    say("4/5 evaluating against ground truth")
    eres = evaluate(out)
    (rep / "evaluation.json").write_text(json.dumps(eres, indent=2, default=str), newline="\n")
    (rep / "evaluation.md").write_text(eval_md(eres), newline="\n")

    say("5/5 exporting " + ", ".join(formats))
    if "json" in formats:
        export_json(out)
    if "sql" in formats:
        export_sql(out)
    man = write_manifest(out, cfg, seed, command, notes)
    secs = round(time.time() - t0, 1)
    summary = dict(out=str(out), seconds=secs, validation=vres["overall"], failed_checks=vres["n_failed"],
                   n_checks=vres["n_checks"], anomaly_micro=eres["anomaly_detection"]["micro"],
                   shortages=eres["planning"]["shortage_episodes"],
                   rows={f["path"]: f["rows"] for f in man["files"] if f["rows"] is not None})
    say(f"done in {secs}s - validation {vres['overall']} ({vres['n_checks']} checks, {vres['n_failed']} failed); "
        f"anomaly detection P/R/F1 = {eres['anomaly_detection']['micro']}")
    return summary


def reproduce(cfg: ScaleConfig, seed: int, workdir: Path | str, formats=("csv",)) -> dict:
    """Step 10: generate twice with the same seed (+ once with a different seed) and compare."""
    workdir = Path(workdir)
    runs = {}
    for tag, s in (("run_a", seed), ("run_b", seed), ("other_seed", seed + 1)):
        log(f"reproducibility: {tag} (seed={s})")
        run(cfg, s, workdir / tag, formats=formats, quiet=True)
        man = json.loads((workdir / tag / "manifest.json").read_text())
        runs[tag] = {f["path"]: (f["rows"], f["sha256"]) for f in man["files"]}
    a, b, c = runs["run_a"], runs["run_b"], runs["other_seed"]
    same = sorted(k for k in a if a[k] == b.get(k))
    diff = sorted(k for k in a if a[k] != b.get(k))
    differs_other = sorted(k for k in a if k in c and a[k][1] != c[k][1])
    res = dict(seed=seed, scale=cfg.to_dict(), files_compared=len(a), identical_files=len(same),
               different_files=diff, reproducible=not diff and set(a) == set(b),
               other_seed=seed + 1, files_changed_with_other_seed=len(differs_other),
               table=[dict(file=k, rows=a[k][0], sha256_run_a=a[k][1][:16], sha256_run_b=b[k][1][:16],
                           match=a[k] == b.get(k)) for k in sorted(a)])
    (workdir / "reproducibility.json").write_text(json.dumps(res, indent=2), newline="\n")
    md = [f"# Reproducibility check\n", f"Seed {seed}, scale `{cfg.name}`. Generated twice into `run_a/` and `run_b/`.\n",
          f"**Reproducible: {res['reproducible']}** - {len(same)}/{len(a)} files identical (row count + SHA-256).",
          f"Control: seed {seed + 1} changed {len(differs_other)} files, so the seed really drives the output.\n",
          "| file | rows | sha256 run A | sha256 run B | match |", "|---|---|---|---|---|"]
    md += [f"| {r['file']} | {r['rows']} | {r['sha256_run_a']}... | {r['sha256_run_b']}... | {r['match']} |" for r in res["table"]]
    (workdir / "reproducibility.md").write_text("\n".join(md) + "\n", newline="\n")
    log(f"reproducible={res['reproducible']} ({len(same)}/{len(a)} identical); other seed changed {len(differs_other)} files")
    return res
