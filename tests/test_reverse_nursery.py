from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


EXPERIMENT = (
    Path(__file__).resolve().parents[1] / "experiments" / "graph_native_live"
)
for import_root in (Path(__file__).resolve().parents[1] / "src", EXPERIMENT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

MODULE_PATH = EXPERIMENT / "reverse_nursery.py"
SPEC = importlib.util.spec_from_file_location("graph_reverse_nursery", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
REVERSE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REVERSE
SPEC.loader.exec_module(REVERSE)


@pytest.mark.skipif(
    not REVERSE.nursery.MODEL.is_file() or not REVERSE.nursery.CODEC.is_file(),
    reason="local Qwen3 reverse-nursery assets are unavailable",
)
def test_graph_states_decode_without_graph_token_ids(tmp_path: Path) -> None:
    primary = REVERSE.run_reverse_nursery(
        tmp_path / "primary.sqlite",
        REVERSE.nursery.MODEL,
        REVERSE.nursery.CODEC,
        ("I", " like", " Josh"),
        cycles=4,
    )
    shuffled = REVERSE.run_reverse_nursery(
        tmp_path / "shuffled.sqlite",
        REVERSE.nursery.MODEL,
        REVERSE.nursery.CODEC,
        ("I", " like", " Josh"),
        assignment=(2, 0, 1),
        cycles=4,
    )
    untrained = REVERSE.run_reverse_nursery(
        tmp_path / "untrained.sqlite",
        REVERSE.nursery.MODEL,
        REVERSE.nursery.CODEC,
        ("I", " like", " Josh"),
        cycles=0,
    )

    assert primary["complete_phrase_presented"] is False
    assert primary["lexical_nodes_store_token_ids"] is False
    assert primary["production_reads_token_ids_from_graph"] is False
    assert primary["speech"]["surface"] == "I like Josh"
    assert primary["speech"]["exact"] is True
    assert primary["speech"]["projection_tensor"] in {
        "output.weight",
        "token_embd.weight",
    }
    assert primary["hatch_ready"] is True
    assert shuffled["speech"]["surface"] == " JoshI like"
    assert shuffled["hatch_ready"] is False
    assert untrained["speech"]["surface"] == ""
    assert untrained["hatch_ready"] is False
