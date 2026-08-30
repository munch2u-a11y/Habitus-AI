from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys

import pytest

from habitus_ai.graph import OUTPUT_NODE_IDS, SELF_ID
from habitus_ai.pipeline import BaseAgenticMemoryRAG
from habitus_ai.types import ConceptNode, GraphSide, InputTrunk, OutputTrunk, as_tuple


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "graph_native_live"
    / "latent_language_pulse.py"
)
SPEC = importlib.util.spec_from_file_location("latent_language_pulse", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
LATENT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LATENT
SPEC.loader.exec_module(LATENT)


def _mind_with_membrane(tmp_path: Path):
    mind = BaseAgenticMemoryRAG(
        tmp_path / "mind.sqlite",
        embedder=LATENT.opaque_skeleton.OpaqueIdentityEmbedder(),
    )
    mind.add_concept(
        "concept:speak",
        "opaque",
        input_trunks=(InputTrunk.HEAR,),
        output_trunks=(OutputTrunk.SPEAK,),
    )
    mind.add_concept(
        "concept:look",
        "opaque",
        input_trunks=(InputTrunk.HEAR,),
        output_trunks=(OutputTrunk.LOOK,),
    )
    lexemes = []
    for index in range(4):
        node_id = f"LXG:{index}"
        mind.store.add_concept(
            ConceptNode(
                concept_id=node_id,
                label=node_id,
                kind="lexeme",
                embedding=as_tuple(
                    LATENT.opaque_skeleton.opaque_unit_vector(f"lexeme:{index}")
                ),
                terms=(),
                vault_id=f"lexical-geometry:{node_id}",
                created_pulse=0,
                last_active_pulse=0,
            )
        )
        mind.add_relation("concept:speak", node_id, side=GraphSide.OUTPUT)
        if lexemes:
            mind.add_relation(lexemes[-1], node_id, side=GraphSide.OUTPUT)
        lexemes.append(node_id)
    return mind


def test_frame_uses_final_recalibrated_snapshot_and_conserves_mass(tmp_path: Path) -> None:
    with _mind_with_membrane(tmp_path) as mind:
        frame = LATENT.build_activation_frame(
            mind,
            ((1.0, "concept:speak"),),
            now=100.0,
            input_stability=0.8,
        )
        final, receipt = LATENT.recalibrate(mind, stage="readback", now=100.0)

        assert all(item.global_mass == pytest.approx(1.0) for item in frame.recalibrations)
        assert all(item.accounted_mass == pytest.approx(1.0) for item in frame.recalibrations)
        assert all(sum(item.regional_mass.values()) == pytest.approx(1.0) for item in frame.recalibrations)
        assert frame.final_softmax_sha256 == receipt.snapshot_sha256
        assert frame.recalibrations[-1].stage == "after_output_activation_final"
        assert frame.recalibrations[0].snapshot_sha256 != frame.final_softmax_sha256
        assert sum(frame.action_gates.values()) == pytest.approx(1.0)
        assert frame.final_path_edge_weights == {
            edge_id: final.global_weights[edge_id]
            for edge_id in frame.final_path_edge_weights
        }


def test_frame_combines_structure_and_membrane_without_text(tmp_path: Path) -> None:
    with _mind_with_membrane(tmp_path) as mind:
        frame = LATENT.build_activation_frame(
            mind,
            ((1.0, "concept:speak"),),
            now=200.0,
        )
        packet = tmp_path / "frame.packet"
        LATENT.opaque_skeleton.write_packet(packet, frame.rows)

        kinds = [source.kind for source in frame.row_sources]
        payload = packet.read_text(encoding="ascii")
        assert kinds[:4] == [
            "whole_mind_softmax_field",
            "input_y_route_field",
            "activated_graphlets",
            "output_y_route_field",
        ]
        assert kinds[4:] == ["learned_membrane_geometry"] * 4
        assert payload.startswith("HABITUS_OPAQUE_PACKET_V1\n1024 8\n")
        assert "opaque" not in payload
        assert "concept:speak" not in payload


def test_speak_path_externalizes_and_other_action_path_remains_internal(tmp_path: Path) -> None:
    with _mind_with_membrane(tmp_path) as mind:
        speak = LATENT.build_activation_frame(
            mind, ((1.0, "concept:speak"),), now=300.0
        )
        look = LATENT.build_activation_frame(
            mind,
            ((1.0, "concept:look"),),
            now=301.0,
            maximum_membrane_rows=0,
        )

        assert speak.output_trunk == OutputTrunk.SPEAK
        assert speak.destination == "external"
        assert look.output_trunk == OutputTrunk.LOOK
        assert look.destination == "internal"


def test_ablation_matrix_uses_one_frame_without_recomputing_state(tmp_path: Path) -> None:
    with _mind_with_membrane(tmp_path) as mind:
        frame = LATENT.build_activation_frame(
            mind, ((1.0, "concept:speak"),), now=350.0
        )
        cases = dict(LATENT.ablation_rows(frame))

        assert tuple(cases) == (
            "target",
            "separate_hybrid",
            "structure_only",
            "membrane_only",
            "reversed",
            "random",
        )
        assert len(cases["target"]) == len(frame.rows[4:])
        assert cases["target"] != frame.rows[4:]
        assert cases["separate_hybrid"] == frame.rows
        assert cases["structure_only"] == frame.rows[:4]
        assert cases["membrane_only"] == frame.rows[4:]
        assert cases["reversed"] == tuple(reversed(cases["target"]))
        assert len(cases["random"]) == len(cases["target"])


def test_zero_strength_overlay_is_exact_membrane_and_rejects_bad_strength(tmp_path: Path) -> None:
    with _mind_with_membrane(tmp_path) as mind:
        frame = LATENT.build_activation_frame(
            mind, ((1.0, "concept:speak"),), now=360.0
        )

        assert LATENT.contextual_overlay_rows(frame, strength=0.0) == frame.rows[4:]
        with pytest.raises(ValueError, match="strength"):
            LATENT.contextual_overlay_rows(frame, strength=1.1)


def test_verified_feedback_reallocates_conserved_flow_immediately(tmp_path: Path) -> None:
    with _mind_with_membrane(tmp_path) as mind:
        frame = LATENT.build_activation_frame(
            mind, ((1.0, "concept:speak"),), now=400.0
        )
        before, _ = LATENT.recalibrate(mind, stage="before_feedback", now=400.0)
        credited = set(frame.output_traces[0].path_edge_ids)
        unrelated = mind.store.find_edge(
            GraphSide.OUTPUT,
            SELF_ID,
            OUTPUT_NODE_IDS[OutputTrunk.DO],
        )
        assert unrelated is not None

        receipt = LATENT.apply_verified_output_feedback(
            mind,
            frame,
            stability_delta=1.0,
            receipt_id="receipt:test",
            now=400.0,
        )
        after, readback = LATENT.recalibrate(mind, stage="after_feedback", now=400.0)

        assert receipt.global_mass == pytest.approx(1.0)
        assert receipt.snapshot_sha256 == readback.snapshot_sha256
        assert all(after.global_weights[edge] > before.global_weights[edge] for edge in credited)
        assert after.global_weights[unrelated.edge_id] < before.global_weights[unrelated.edge_id]
        assert after.total == pytest.approx(1.0)
        assert after.accounted_mass == pytest.approx(1.0)


def test_verified_feedback_requires_receipt(tmp_path: Path) -> None:
    with _mind_with_membrane(tmp_path) as mind:
        frame = LATENT.build_activation_frame(
            mind, ((1.0, "concept:speak"),), now=500.0
        )
        with pytest.raises(ValueError, match="receipt"):
            LATENT.apply_verified_output_feedback(
                mind,
                frame,
                stability_delta=1.0,
                receipt_id="",
                now=500.0,
            )


def test_endpoint_ranking_never_promotes_a_membrane_label(tmp_path: Path) -> None:
    with _mind_with_membrane(tmp_path) as mind:
        query = mind.store.get_concept("LXG:0").embedding
        ranked = LATENT.rank_productive_concepts(mind, query, maximum=3)

        assert ranked
        assert all(
            mind.store.get_concept(concept_id).kind == "crown"
            for _, concept_id in ranked
        )
