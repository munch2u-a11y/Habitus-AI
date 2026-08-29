from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "graph_native_live"
    / "nursery.py"
)
SPEC = importlib.util.spec_from_file_location("graph_native_nursery", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
NURSERY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = NURSERY
SPEC.loader.exec_module(NURSERY)


@pytest.mark.skipif(
    not NURSERY.MODEL.is_file() or not NURSERY.CODEC.is_file(),
    reason="local Qwen3 nursery assets are unavailable",
)
def test_separate_labels_compose_and_shuffled_pairing_does_not(tmp_path: Path) -> None:
    primary = NURSERY.run_one_nursery(
        tmp_path / "primary.sqlite",
        NURSERY.MODEL,
        NURSERY.CODEC,
        ("I", " like", " Josh"),
        cycles=4,
    )
    shuffled = NURSERY.run_one_nursery(
        tmp_path / "shuffled.sqlite",
        NURSERY.MODEL,
        NURSERY.CODEC,
        ("I", " like", " Josh"),
        assignment=(2, 0, 1),
        cycles=4,
    )
    untrained = NURSERY.run_one_nursery(
        tmp_path / "untrained.sqlite",
        NURSERY.MODEL,
        NURSERY.CODEC,
        ("I", " like", " Josh"),
        cycles=0,
    )

    assert primary["complete_phrase_presented"] is False
    assert primary["speech"]["surface"] == "I like Josh"
    assert primary["speech"]["exact"] is True
    assert primary["hatch_ready"] is True
    assert sum(item["passed"] for item in primary["comprehension"]) == 3
    assert primary["feedback"]["delay_pulses"] == 1
    assert len(primary["fiber_weights"]) > 6

    assert shuffled["speech"]["surface"] == " JoshI like"
    assert shuffled["speech"]["exact"] is False
    assert shuffled["hatch_ready"] is False
    assert untrained["speech"]["surface"] == ""
    assert untrained["hatch_ready"] is False
