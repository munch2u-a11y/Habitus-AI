from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "graph_native_live"
    / "embodied_nursery.py"
)
SPEC = importlib.util.spec_from_file_location("embodied_nursery", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
NURSERY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = NURSERY
SPEC.loader.exec_module(NURSERY)


def test_embodied_nursery_learns_actions_and_closes_output_first_cycles(tmp_path: Path) -> None:
    report = NURSERY.run_embodied_nursery(
        tmp_path / "mind.sqlite",
        tmp_path / "world",
        epochs=5,
    )

    assert report["trained_accuracy"] == pytest.approx(1.0)
    assert report["trained_accuracy"] >= report["baseline_accuracy"]
    assert report["action_cycles"] > 0
    assert report["closed_cycles"] == report["action_cycles"]
    assert report["verified_successes"] == 25
    assert report["verified_errors"] > 0
    assert report["output_first_records"] is True
    assert report["global_edge_mass"] == pytest.approx(1.0)
    assert report["root_flow_mass"] == pytest.approx(1.0)
    assert report["accounted_flow_mass"] == pytest.approx(1.0)
    assert sum(report["regional_flow_mass"].values()) == pytest.approx(1.0)
    assert report["boundary_escape_blocked"] is True
    assert report["graph_invariants"] == []
