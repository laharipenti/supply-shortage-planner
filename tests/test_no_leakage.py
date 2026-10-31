"""Ground truth must never reach the planner (Step 7)."""
import re
import shutil
from pathlib import Path

import pandas as pd

from ssp.engine import run_planning
from ssp.io import read_layer
from ssp.schema import INPUT_TABLES

SRC = Path(__file__).resolve().parents[1] / "src" / "ssp"


def test_engine_source_never_mentions_ground_truth():
    code = (SRC / "engine.py").read_text()
    assert "ground_truth" not in code.replace("never opens ground_truth", "")


def test_input_has_no_label_columns(tiny_run):
    out, _ = tiny_run
    for t in INPUT_TABLES:
        cols = pd.read_csv(out / "input" / f"{t}.csv", nrows=0).columns
        assert not [c for c in cols if re.search(r"truth|anomal|issue|label|is_spike|constrained", c)], t


def test_planner_output_identical_without_ground_truth(tiny_run, tmp_path, tiny_cfg):
    out, _ = tiny_run
    shutil.copytree(out / "input", tmp_path / "input")      # ground truth deliberately NOT copied
    derived = run_planning(read_layer(tmp_path / "input", INPUT_TABLES), tiny_cfg.n_weeks)
    ref = pd.read_csv(out / "derived" / "shortage.csv", keep_default_na=False)
    assert len(derived["shortage"]) == len(ref)
    assert list(derived["shortage"]["shortage_id"]) == list(ref["shortage_id"])
