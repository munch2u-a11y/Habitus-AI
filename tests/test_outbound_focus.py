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
    / "outbound_focus.py"
)
SPEC = importlib.util.spec_from_file_location("outbound_focus", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
OUTBOUND = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OUTBOUND
SPEC.loader.exec_module(OUTBOUND)

ABLATION_PATH = MODULE_PATH.with_name("outbound_focus_ablation.py")
ABLATION_SPEC = importlib.util.spec_from_file_location(
    "outbound_focus_ablation",
    ABLATION_PATH,
)
assert ABLATION_SPEC is not None and ABLATION_SPEC.loader is not None
ABLATION = importlib.util.module_from_spec(ABLATION_SPEC)
sys.modules[ABLATION_SPEC.name] = ABLATION
ABLATION_SPEC.loader.exec_module(ABLATION)


def _add_lexeme(mind: BaseAgenticMemoryRAG, concept_id: str, suffix: str) -> None:
    node_id = f"LXG:{suffix}"
    mind.store.add_concept(
        ConceptNode(
            concept_id=node_id,
            label=node_id,
            kind="lexeme",
            embedding=as_tuple(
                OUTBOUND.opaque_skeleton.opaque_unit_vector(f"lexeme:{suffix}")
            ),
            terms=(),
            vault_id=f"lexical-geometry:{node_id}",
            created_pulse=0,
            last_active_pulse=0,
        )
    )
    mind.add_relation(concept_id, node_id, side=GraphSide.OUTPUT)


def _mind(tmp_path: Path, *, two_speech: bool = False) -> BaseAgenticMemoryRAG:
    mind = BaseAgenticMemoryRAG(
        tmp_path / "mind.sqlite",
        embedder=OUTBOUND.opaque_skeleton.OpaqueIdentityEmbedder(),
    )
    mind.add_concept(
        "concept:speak-a",
        "opaque-a",
        input_trunks=(InputTrunk.HEAR,),
        output_trunks=(OutputTrunk.SPEAK,),
    )
    _add_lexeme(mind, "concept:speak-a", "a")
    if two_speech:
        mind.add_concept(
            "concept:speak-b",
            "opaque-b",
            input_trunks=(InputTrunk.HEAR,),
            output_trunks=(OutputTrunk.SPEAK,),
        )
        _add_lexeme(mind, "concept:speak-b", "b")
    mind.add_concept(
        "concept:look",
        "opaque-look",
        input_trunks=(InputTrunk.HEAR,),
        output_trunks=(OutputTrunk.LOOK,),
    )
    mind.add_concept(
        "concept:do",
        "opaque-do",
        input_trunks=(InputTrunk.HEAR,),
        output_trunks=(OutputTrunk.DO,),
    )
    return mind


def _input_field(
    mind: BaseAgenticMemoryRAG,
    concept_id: str,
    *,
    now: float,
) -> OUTBOUND.TransientActivation:
    trace = mind.graph.traverse(
        pulse_id=f"input:{concept_id}",
        side=GraphSide.INPUT,
        target_id=concept_id,
        endpoint_score=1.0,
        required_input_trunk=InputTrunk.HEAR,
        now=now,
        mark_active=False,
    )
    assert trace is not None
    return OUTBOUND.TransientActivation.from_input_traces((trace,), (1.0,))


def _candidate(focus: OUTBOUND.OutputFocus, concept_id: str):
    return next(item for item in focus.candidates if item.terminal_concept_id == concept_id)


def test_target_free_focus_conserves_hierarchical_mass(tmp_path: Path) -> None:
    with _mind(tmp_path) as mind:
        transient = _input_field(mind, "concept:speak-a", now=100.0)
        focus = OUTBOUND.resolve_output_focus(
            mind,
            transient,
            now=100.0,
            maximum_membranes=1,
            mark_active=False,
        )

        assert set(focus.trunk_gates) == {"communication", "navigation", "action"}
        assert sum(focus.trunk_gates.values()) == pytest.approx(1.0)
        assert all(value == pytest.approx(1.0) for value in focus.within_membrane_mass.values())
        assert focus.total_effective_mass == pytest.approx(1.0)
        assert focus.selected[0].terminal_concept_id == "concept:speak-a"
        assert focus.selected[0].membrane == OUTBOUND.InterfaceMembrane.COMMUNICATION
        assert focus.pre_activation_softmax.global_mass == pytest.approx(1.0)
        assert focus.final_softmax.global_mass == pytest.approx(1.0)


def test_output_y_can_defeat_the_input_endpoint_when_habit_is_stronger(tmp_path: Path) -> None:
    with _mind(tmp_path) as mind:
        transient = _input_field(mind, "concept:speak-a", now=200.0)
        do_root = mind.store.find_edge(
            GraphSide.OUTPUT,
            SELF_ID,
            OUTPUT_NODE_IDS[OutputTrunk.DO],
        )
        do_concept = mind.store.find_edge(
            GraphSide.OUTPUT,
            OUTPUT_NODE_IDS[OutputTrunk.DO],
            "concept:do",
        )
        assert do_root is not None and do_concept is not None
        for _ in range(30):
            mind.graph.reinforce_edges(
                (do_root.edge_id, do_concept.edge_id),
                stability_delta=1.0,
                verified=True,
            )

        focus = OUTBOUND.resolve_output_focus(
            mind,
            transient,
            now=200.0,
            gravity_strength=0.60,
            maximum_membranes=1,
            mark_active=False,
        )

        assert focus.selected[0].terminal_concept_id == "concept:do"
        assert focus.selected[0].terminal_concept_id != "concept:speak-a"
        assert focus.selected[0].membrane == OUTBOUND.InterfaceMembrane.ACTION


def test_transient_gravity_redirects_within_membrane_without_learning(tmp_path: Path) -> None:
    with _mind(tmp_path, two_speech=True) as mind:
        before = {
            edge.edge_id: edge.log_strength
            for edge in mind.store.list_edges(GraphSide.OUTPUT)
        }
        focus_a = OUTBOUND.resolve_output_focus(
            mind,
            _input_field(mind, "concept:speak-a", now=300.0),
            now=300.0,
            maximum_membranes=1,
            mark_active=False,
        )
        focus_b = OUTBOUND.resolve_output_focus(
            mind,
            _input_field(mind, "concept:speak-b", now=300.0),
            now=300.0,
            maximum_membranes=1,
            mark_active=False,
        )
        after = {
            edge.edge_id: edge.log_strength
            for edge in mind.store.list_edges(GraphSide.OUTPUT)
        }

        assert _candidate(focus_a, "concept:speak-a").within_membrane_probability > _candidate(
            focus_a, "concept:speak-b"
        ).within_membrane_probability
        assert _candidate(focus_b, "concept:speak-b").within_membrane_probability > _candidate(
            focus_b, "concept:speak-a"
        ).within_membrane_probability
        assert before == after


def test_action_learning_does_not_rewrite_communication_distribution(tmp_path: Path) -> None:
    with _mind(tmp_path, two_speech=True) as mind:
        empty = OUTBOUND.TransientActivation({})
        before = OUTBOUND.resolve_output_focus(
            mind, empty, now=400.0, mark_active=False
        )
        speech_before = {
            item.terminal_concept_id: item.within_membrane_probability
            for item in before.candidates
            if item.membrane == OUTBOUND.InterfaceMembrane.COMMUNICATION
        }
        do_root = mind.store.find_edge(
            GraphSide.OUTPUT, SELF_ID, OUTPUT_NODE_IDS[OutputTrunk.DO]
        )
        do_concept = mind.store.find_edge(
            GraphSide.OUTPUT, OUTPUT_NODE_IDS[OutputTrunk.DO], "concept:do"
        )
        assert do_root is not None and do_concept is not None
        mind.graph.reinforce_edges(
            (do_root.edge_id, do_concept.edge_id),
            stability_delta=1.0,
            verified=True,
        )
        after = OUTBOUND.resolve_output_focus(
            mind, empty, now=400.0, mark_active=False
        )
        speech_after = {
            item.terminal_concept_id: item.within_membrane_probability
            for item in after.candidates
            if item.membrane == OUTBOUND.InterfaceMembrane.COMMUNICATION
        }

        assert speech_before == pytest.approx(speech_after)
        assert after.trunk_gates["action"] > before.trunk_gates["action"]


def test_rich_membrane_is_not_penalized_for_having_more_endpoints(tmp_path: Path) -> None:
    with _mind(tmp_path) as mind:
        for index in range(12):
            concept_id = f"concept:speak-extra-{index}"
            mind.add_concept(
                concept_id,
                f"opaque-extra-{index}",
                input_trunks=(InputTrunk.HEAR,),
                output_trunks=(OutputTrunk.SPEAK,),
            )
            _add_lexeme(mind, concept_id, f"extra-{index}")

        focus = OUTBOUND.resolve_output_focus(
            mind,
            _input_field(mind, "concept:speak-a", now=450.0),
            now=450.0,
            maximum_membranes=1,
            mark_active=False,
        )

        assert focus.trunk_gates["communication"] > focus.trunk_gates["action"]
        assert focus.selected[0].terminal_concept_id == "concept:speak-a"

        legacy_by_membrane = {}
        for membrane in OUTBOUND.InterfaceMembrane:
            scores = [
                item.path_score
                for item in focus.candidates
                if item.membrane == membrane
            ]
            legacy_by_membrane[membrane.value] = OUTBOUND._log_mean_exp(scores)
        assert legacy_by_membrane["action"] > legacy_by_membrane["communication"]


def test_nonverbal_membranes_emit_structured_packets_without_language(tmp_path: Path) -> None:
    with _mind(tmp_path) as mind:
        do_focus = OUTBOUND.resolve_output_focus(
            mind,
            OUTBOUND.TransientActivation({"concept:do": 1.0}),
            now=500.0,
            gravity_strength=3.0,
            maximum_membranes=1,
            mark_active=False,
        )
        packet = OUTBOUND.packets_for_focus(do_focus)[0]

        assert packet.membrane == OUTBOUND.InterfaceMembrane.ACTION
        assert packet.representation == "ability_invocation"
        assert packet.fields["ability_id"] == "concept:do"
        assert "language" not in packet.fields["adapter"]


def test_private_focus_recirculates_with_attenuation_not_reinforcement(tmp_path: Path) -> None:
    with _mind(tmp_path) as mind:
        before = {
            edge.edge_id: edge.log_strength
            for edge in mind.store.list_edges(GraphSide.OUTPUT)
        }
        focus = OUTBOUND.resolve_output_focus(
            mind,
            OUTBOUND.TransientActivation({"concept:look": 1.0}),
            now=600.0,
            gravity_strength=3.0,
            maximum_membranes=1,
            mark_active=False,
        )
        recirculated = OUTBOUND.recirculate_private_focus(
            OUTBOUND.TransientActivation({"concept:look": 1.0}),
            focus,
            attenuation=0.5,
        )
        after = {
            edge.edge_id: edge.log_strength
            for edge in mind.store.list_edges(GraphSide.OUTPUT)
        }

        assert focus.selected[0].membrane == OUTBOUND.InterfaceMembrane.NAVIGATION
        assert 0.0 < recirculated.values["concept:look"] < 1.0
        assert before == after


def test_selected_output_route_forces_final_recalibration(tmp_path: Path) -> None:
    with _mind(tmp_path) as mind:
        focus = OUTBOUND.resolve_output_focus(
            mind,
            OUTBOUND.TransientActivation({"concept:speak-a": 1.0}),
            now=700.0,
            gravity_strength=3.0,
            maximum_membranes=1,
            mark_active=True,
        )

        assert focus.pre_activation_softmax.global_mass == pytest.approx(1.0)
        assert focus.final_softmax.global_mass == pytest.approx(1.0)
        assert (
            focus.pre_activation_softmax.snapshot_sha256
            != focus.final_softmax.snapshot_sha256
        )


def test_decay_is_bounded_and_monotonic() -> None:
    activation = OUTBOUND.TransientActivation({"node": 1.0})
    half = activation.decayed(0.5)
    quarter = half.decayed(0.5)

    assert half.values["node"] == pytest.approx(0.5)
    assert quarter.values["node"] == pytest.approx(0.25)
    assert math.isclose(sum(quarter.values.values()), 0.25)


def test_ablation_input_pathfinder_does_not_persist_trace(tmp_path: Path) -> None:
    with _mind(tmp_path) as mind:
        before = mind.store.connection.execute(
            "SELECT COUNT(*) FROM traces"
        ).fetchone()[0]
        activation = ABLATION._input_activation(
            mind,
            ((1.0, "concept:speak-a"),),
            snapshot=mind.graph.weight_snapshot(now=800.0),
        )
        after = mind.store.connection.execute(
            "SELECT COUNT(*) FROM traces"
        ).fetchone()[0]

        assert activation.values["concept:speak-a"] > 0.0
        assert after == before
