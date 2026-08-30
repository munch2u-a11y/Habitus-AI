from __future__ import annotations

import pytest

from habitus_ai import BaseAgenticMemoryRAG, EventEnvelope, EventKind, GraphSide
from habitus_ai.graph import INPUT_NODE_IDS, OUTPUT_NODE_IDS
from habitus_ai.types import InputTrunk, OutputTrunk, SurfaceCandidate


def _event(kind, correlation_id=None):
    return EventEnvelope(
        event_id="event",
        kind=kind,
        source_id="source",
        timestamp="2026-08-28T00:00:00+00:00",
        content="content",
        correlation_id=correlation_id,
    )


def test_input_trunks_follow_causal_event_metadata():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        assert mind.graph.route_event(_event(EventKind.MESSAGE)) == InputTrunk.HEAR
        assert mind.graph.route_event(_event(EventKind.OBSERVATION, "call-1")) == InputTrunk.SEE
        assert mind.graph.route_event(_event(EventKind.OBSERVATION)) == InputTrunk.NOTICE
        assert mind.graph.route_event(_event(EventKind.NOTIFICATION)) == InputTrunk.NOTICE


def test_semantic_endpoint_score_does_not_change_y_travel_time():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept(
            "topic",
            "Topic",
            input_trunks=("HEAR",),
        )
        low = mind.graph.traverse(
            pulse_id="p-low",
            side=GraphSide.INPUT,
            target_id="topic",
            endpoint_score=0.1,
            required_input_trunk=InputTrunk.HEAR,
            now=0.0,
            mark_active=False,
        )
        high = mind.graph.traverse(
            pulse_id="p-high",
            side=GraphSide.INPUT,
            target_id="topic",
            endpoint_score=0.9,
            required_input_trunk=InputTrunk.HEAR,
            now=0.0,
            mark_active=False,
        )
        assert low.total_travel_time == high.total_travel_time


def test_y_resistance_cannot_replace_x_selected_endpoint():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept(
            "x-selected",
            "X selected",
            input_trunks=("HEAR",),
        )
        mind.add_concept(
            "cheap-distractor",
            "Cheap distractor",
            input_trunks=("HEAR",),
        )
        selected_edge = mind.store.find_edge(
            GraphSide.INPUT,
            "IN:HEAR",
            "x-selected",
        )
        assert selected_edge is not None
        mind.store.update_edge_state(
            selected_edge.edge_id,
            conflict_penalty=100.0,
        )
        mind.retrieval.maximum_paths = 1

        traces = mind.retrieval._traces(
            "pulse-x-fixed",
            InputTrunk.HEAR,
            (
                SurfaceCandidate("x-selected", 0.9, 0.9, 0.9),
                SurfaceCandidate("cheap-distractor", 0.2, 0.2, 0.2),
            ),
        )

        assert [trace.target_node_id for trace in traces] == ["x-selected"]
        assert traces[0].total_travel_time > 100.0


def test_output_y_resistance_cannot_replace_x_selected_endpoint():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept(
            "intended-effect",
            "Intended effect",
            output_trunks=("DO",),
        )
        mind.add_concept(
            "cheap-effect",
            "Cheap effect",
            output_trunks=("LOOK",),
        )
        selected_edge = mind.store.find_edge(
            GraphSide.OUTPUT,
            "OUT:DO",
            "intended-effect",
        )
        assert selected_edge is not None
        mind.store.update_edge_state(
            selected_edge.edge_id,
            conflict_penalty=100.0,
        )
        mind.surface.project = lambda *_args, **_kwargs: [
            SurfaceCandidate("intended-effect", 0.9, 0.9, 0.9),
            SurfaceCandidate("cheap-effect", 0.2, 0.2, 0.2),
        ]

        decision = mind.classify_output("perform the intended effect")

        assert decision.trunk == OutputTrunk.DO
        assert decision.trace is not None
        assert decision.trace.target_node_id == "intended-effect"
        assert decision.trace.total_travel_time > 100.0


def test_verified_receipt_reinforces_but_unverified_claim_does_not():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        decision = mind.classify_output("search inspect read", effect_hint=OutputTrunk.LOOK)
        edge_id = decision.trace.path_edge_ids[0]
        initial = mind.store.get_edge(edge_id).log_strength
        mind.record_outcome(decision, stability_delta=0.8, verified=False)
        assert mind.store.get_edge(edge_id).log_strength == initial
        with pytest.raises(ValueError, match="receipt"):
            mind.record_outcome(decision, stability_delta=0.8, verified=True)
        mind.record_outcome(
            decision,
            stability_delta=0.8,
            verified=True,
            proposal_id="proposal-1",
            receipt_id="receipt-1",
        )
        assert mind.store.get_edge(edge_id).log_strength > initial
        snapshot = mind.graph.weight_snapshot()
        assert snapshot.total == pytest.approx(1.0)
        assert snapshot.accounted_mass == pytest.approx(1.0)


def test_reinforcement_redirects_local_choice_without_breaking_cap():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        look_edge = mind.store.find_edge(GraphSide.OUTPUT, "SELF", OUTPUT_NODE_IDS[OutputTrunk.LOOK])
        do_edge = mind.store.find_edge(GraphSide.OUTPUT, "SELF", OUTPUT_NODE_IDS[OutputTrunk.DO])
        before = mind.graph.local_probabilities("SELF", GraphSide.OUTPUT)
        mind.graph.reinforce_edges(
            (look_edge.edge_id,), stability_delta=1.0, verified=True
        )
        after = mind.graph.local_probabilities("SELF", GraphSide.OUTPUT)
        assert after[look_edge.edge_id] > before[look_edge.edge_id]
        assert after[do_edge.edge_id] < before[do_edge.edge_id]
        assert sum(after.values()) == pytest.approx(1.0)


def test_unrelated_regional_growth_cannot_dilute_a_local_habit():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept("look-habit", "Look habit", output_trunks=("LOOK",))
        habit_edge = mind.store.find_edge(
            GraphSide.OUTPUT,
            OUTPUT_NODE_IDS[OutputTrunk.LOOK],
            "look-habit",
        )
        assert habit_edge is not None
        for _ in range(5):
            mind.graph.reinforce_edges(
                (habit_edge.edge_id,), stability_delta=1.0, verified=True
            )
        before_local = mind.graph.local_probabilities(
            OUTPUT_NODE_IDS[OutputTrunk.LOOK], GraphSide.OUTPUT
        )[habit_edge.edge_id]
        before_flow = mind.graph.weight_snapshot(
            side=GraphSide.OUTPUT, now=0.0
        ).global_weights[habit_edge.edge_id]

        for index in range(40):
            mind.add_concept(
                f"unrelated-do-{index}",
                f"Unrelated {index}",
                output_trunks=("DO",),
            )

        after_local = mind.graph.local_probabilities(
            OUTPUT_NODE_IDS[OutputTrunk.LOOK], GraphSide.OUTPUT
        )[habit_edge.edge_id]
        after_flow = mind.graph.weight_snapshot(
            side=GraphSide.OUTPUT, now=0.0
        ).global_weights[habit_edge.edge_id]
        assert after_local == pytest.approx(before_local)
        assert after_flow == pytest.approx(before_flow)

        mind.add_concept("look-sibling", "Look sibling", output_trunks=("LOOK",))
        with_sibling = mind.graph.local_probabilities(
            OUTPUT_NODE_IDS[OutputTrunk.LOOK], GraphSide.OUTPUT
        )[habit_edge.edge_id]
        assert with_sibling < after_local


def test_selected_input_trunk_has_an_independent_cipher_budget():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept("heard-topic", "Heard topic", input_trunks=("HEAR",))
        before = mind.graph.traverse(
            pulse_id="hear-before",
            side=GraphSide.INPUT,
            target_id="heard-topic",
            endpoint_score=1.0,
            required_input_trunk=InputTrunk.HEAR,
            now=0.0,
            mark_active=False,
        )
        see_connector = mind.store.find_edge(
            GraphSide.INPUT, "SELF", INPUT_NODE_IDS[InputTrunk.SEE]
        )
        assert see_connector is not None
        for _ in range(20):
            mind.graph.reinforce_edges(
                (see_connector.edge_id,), stability_delta=1.0, verified=True
            )
        for index in range(30):
            mind.add_concept(
                f"seen-{index}",
                f"Seen {index}",
                input_trunks=("SEE",),
            )
        after = mind.graph.traverse(
            pulse_id="hear-after",
            side=GraphSide.INPUT,
            target_id="heard-topic",
            endpoint_score=1.0,
            required_input_trunk=InputTrunk.HEAR,
            now=0.0,
            mark_active=False,
        )
        assert before is not None and after is not None
        assert before.path_node_ids == ("SELF", "IN:HEAR", "heard-topic")
        assert after.total_travel_time == pytest.approx(before.total_travel_time)

        snapshot = mind.graph.weight_snapshot(
            side=GraphSide.INPUT,
            root_node_id="IN:HEAR",
            now=0.0,
        )
        assert snapshot.total == pytest.approx(1.0)
        assert snapshot.accounted_mass == pytest.approx(1.0)
        assert snapshot.starting_node_ids == {"input": "IN:HEAR"}
        assert all(key.startswith("input:PREF:HEAR:") or key == "input:heard-topic"
                   for key in snapshot.regional_weights)


def test_selected_output_trunk_has_an_independent_cipher_budget():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept("move", "Move", output_trunks=("DO",))
        before = mind.graph.traverse(
            pulse_id="do-before",
            side=GraphSide.OUTPUT,
            target_id="move",
            endpoint_score=1.0,
            required_output_trunk=OutputTrunk.DO,
            now=0.0,
            mark_active=False,
        )
        speak_connector = mind.store.find_edge(
            GraphSide.OUTPUT, "SELF", OUTPUT_NODE_IDS[OutputTrunk.SPEAK]
        )
        assert speak_connector is not None
        for _ in range(20):
            mind.graph.reinforce_edges(
                (speak_connector.edge_id,), stability_delta=1.0, verified=True
            )
        after = mind.graph.traverse(
            pulse_id="do-after",
            side=GraphSide.OUTPUT,
            target_id="move",
            endpoint_score=1.0,
            required_output_trunk=OutputTrunk.DO,
            now=0.0,
            mark_active=False,
        )
        assert before is not None and after is not None
        assert before.path_node_ids == ("SELF", "OUT:DO", "move")
        assert after.total_travel_time == pytest.approx(before.total_travel_time)


def test_self_originating_flow_conserves_frontiers_and_merges_mass():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept("branch-a", "Branch A", output_trunks=("LOOK",))
        mind.add_concept("branch-b", "Branch B", output_trunks=("LOOK",))
        mind.add_concept("merged", "Merged")
        edge_a = mind.add_relation("branch-a", "merged", side=GraphSide.OUTPUT)
        edge_b = mind.add_relation("branch-b", "merged", side=GraphSide.OUTPUT)

        snapshot = mind.graph.weight_snapshot(
            side=GraphSide.OUTPUT,
            now=0.0,
            maximum_depth=8,
        )
        assert snapshot.total == pytest.approx(1.0)
        assert snapshot.accounted_mass == pytest.approx(1.0)
        assert snapshot.layer_weights["output:0"] == pytest.approx(1.0)
        ordered_layers = [
            mass
            for key, mass in sorted(
                snapshot.layer_weights.items(),
                key=lambda item: int(item[0].rsplit(":", 1)[-1]),
            )
        ]
        assert all(
            later <= earlier + 1e-12
            for earlier, later in zip(ordered_layers, ordered_layers[1:])
        )
        assert snapshot.node_weights["output:merged"] == pytest.approx(
            snapshot.global_weights[edge_a.edge_id]
            + snapshot.global_weights[edge_b.edge_id]
        )


def test_multihop_expansion_starts_from_visited_y_path():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept("project", "Project", terms=("project",), input_trunks=("HEAR",))
        mind.add_concept("logs", "Logs", terms=("logs",))
        mind.add_relation("project", "logs", side=GraphSide.INPUT)
        trace = mind.graph.traverse(
            pulse_id="pulse-x",
            side=GraphSide.INPUT,
            target_id="project",
            endpoint_score=1.0,
            required_input_trunk=InputTrunk.HEAR,
            mark_active=False,
        )
        assert mind.graph.expanded_concept_ids(
            (trace,), side=GraphSide.INPUT, maximum=3
        ) == ["logs"]
