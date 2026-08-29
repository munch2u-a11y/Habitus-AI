from __future__ import annotations

import pytest

from habitus_ai import BaseAgenticMemoryRAG, EventEnvelope, EventKind, GraphSide
from habitus_ai.graph import OUTPUT_NODE_IDS
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
        assert sum(mind.graph.weight_snapshot().global_weights.values()) == pytest.approx(1.0)


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
