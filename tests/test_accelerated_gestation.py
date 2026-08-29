from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


EXPERIMENT = (
    Path(__file__).resolve().parents[1] / "experiments" / "graph_native_live"
)
for import_root in (Path(__file__).resolve().parents[1] / "src", EXPERIMENT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

MODULE_PATH = EXPERIMENT / "accelerated_gestation.py"
SPEC = importlib.util.spec_from_file_location("graph_accelerated_gestation", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
GESTATION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GESTATION
SPEC.loader.exec_module(GESTATION)

PROBE_PATH = EXPERIMENT / "probe_hatched_mind.py"
PROBE_SPEC = importlib.util.spec_from_file_location("graph_hatched_probe", PROBE_PATH)
assert PROBE_SPEC is not None and PROBE_SPEC.loader is not None
HATCH_PROBE = importlib.util.module_from_spec(PROBE_SPEC)
sys.modules[PROBE_SPEC.name] = HATCH_PROBE
PROBE_SPEC.loader.exec_module(HATCH_PROBE)

TRANSFORMER_PATH = EXPERIMENT / "transformer_hatch.py"
TRANSFORMER_SPEC = importlib.util.spec_from_file_location(
    "graph_transformer_hatch", TRANSFORMER_PATH
)
assert TRANSFORMER_SPEC is not None and TRANSFORMER_SPEC.loader is not None
TRANSFORMER = importlib.util.module_from_spec(TRANSFORMER_SPEC)
sys.modules[TRANSFORMER_SPEC.name] = TRANSFORMER
TRANSFORMER_SPEC.loader.exec_module(TRANSFORMER)


@pytest.mark.skipif(
    not GESTATION.nursery.MODEL.is_file() or not GESTATION.nursery.CODEC.is_file(),
    reason="local Qwen3 accelerated-gestation assets are unavailable",
)
def test_accelerated_gestation_grows_persistent_recursive_web(tmp_path: Path) -> None:
    database = tmp_path / "hatch.sqlite"
    manifest = GESTATION.compile_mind(
        database,
        GESTATION.nursery.MODEL,
        GESTATION.nursery.CODEC,
        human_name="Josh",
        agent_name="Testling",
        taste_schema="curious",
        replay_cycles=1,
    )

    assert manifest["hatch_ready"] is True
    assert manifest["graph"]["records"] >= 200
    assert manifest["graph"]["concepts"] >= 200
    assert manifest["graph"]["edges"] >= 500
    assert manifest["graph"]["global_edge_mass"] == pytest.approx(1.0)
    assert manifest["graph"]["invariants"] == []
    assert manifest["topic_concepts"] >= 30
    assert manifest["evaluation"]["average_cluster_purity"] >= 0.90
    assert manifest["evaluation"]["receptive"]["semantic_accuracy_at_1"] >= 0.75
    assert manifest["evaluation"]["receptive"]["semantic_y_reachable"] == 1.0
    assert manifest["evaluation"]["receptive"]["semantic_probe_text_leakage"] == []
    assert manifest["evaluation"]["productive"]["accuracy_at_1"] >= 0.75
    assert manifest["evaluation"]["productive"]["shuffled_control_at_1"] <= 0.20
    assert max(
        item["input_depth"] for item in manifest["assembly_depths"].values()
    ) >= 8
    assert manifest["restart_check"]["counts_match"] is True

    embedder = GESTATION.NativeMassEmbedder(
        GESTATION.nursery.MODEL, GESTATION.nursery.CODEC
    )
    with GESTATION.BaseAgenticMemoryRAG(database, embedder=embedder) as mind:
        assert all(node.terms == () for node in mind.store.list_concepts(kind="lexeme"))
        assert all(
            not any(node.embedding) for node in mind.store.list_concepts(kind="child")
        )
        stored = json.loads(mind.store.get_metadata("accelerated_gestation_manifest"))
        assert stored["hatch_ready"] is True

    live = HATCH_PROBE.probe(
        database,
        GESTATION.nursery.MODEL,
        GESTATION.nursery.CODEC,
        (
            ("trust", "People keep promises, making cooperation feel safe."),
            ("fear", "An unknown danger makes future safety uncertain."),
            ("music", "Melody and rhythm organize a sequence of sounds."),
        ),
    )
    assert live["hear_reachability"] == 1.0
    assert live["strict_output_accuracy"] == 1.0

    generated = TRANSFORMER.run_probe_matrix(
        database,
        GESTATION.nursery.MODEL,
        GESTATION.nursery.CODEC,
        TRANSFORMER.RUNNER,
        tmp_path / "transformer",
        (("trust", "People keep promises, making cooperation feel safe."),),
        maximum_tokens=64,
        seed=42,
    )
    assert generated["expected_word_rate"] == 1.0
    assert generated["target_beats_unrelated_rate"] == 1.0
    assert generated["target_beats_random_rate"] == 1.0
    assert generated["prompt_text_crossed_native_boundary"] is False
    assert generated["retrieved_memory_text_crossed_native_boundary"] is False
    assert generated["semantic_codebook_used"] is False
    assert generated["results"][0]["target_trace"]["missing_transition_count"] == 0
