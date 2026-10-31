import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ssp.config import DEFAULT_SEED, get_scale  # noqa: E402
from ssp.pipeline import run  # noqa: E402


@pytest.fixture(scope="session")
def tiny_cfg():
    return get_scale("tiny")


@pytest.fixture(scope="session")
def tiny_run(tmp_path_factory, tiny_cfg):
    """Run the whole pipeline once at tiny scale; tests read the produced files."""
    out = tmp_path_factory.mktemp("tiny") / "out"
    summary = run(tiny_cfg, DEFAULT_SEED, out, formats=("csv", "json", "sql"), quiet=True)
    return out, summary
