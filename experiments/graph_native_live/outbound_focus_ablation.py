#!/usr/bin/env python3
"""Evaluate target-free output gates on the accelerated nursery topics.

This is a routing evaluation, not a language-quality benchmark.  It holds one
graph snapshot fixed, performs no trace activation or reinforcement, and asks
whether each topic's learned output modality is recovered from transient input
activation.  The legacy control intentionally reproduces the rejected
full-path gate whose score is confounded by branch fan-out.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import heapq
import json
import math
from pathlib import Path
import sys
import time
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.graph import INPUT_NODE_IDS, SELF_ID, WeightSnapshot  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import GraphSide, InputTrunk, TraversalTrace  # noqa: E402
import accelerated_gestation as gestation  # noqa: E402
import latent_language_pulse as latent  # noqa: E402
import nursery  # noqa: E402
import outbound_focus as outbound  # noqa: E402


DEFAULT_DATABASE = outbound.DEFAULT_DATABASE


def legacy_gates(
    candidates: Sequence[outbound.OutputTrajectory],
) -> dict[str, float]:
    """Reproduce the fan-out-sensitive gate used before the hierarchy fix."""
    grouped: dict[outbound.InterfaceMembrane, list[float]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.membrane].append(candidate.path_score)
    membranes = sorted(grouped, key=lambda item: item.value)
    energies = [outbound._log_mean_exp(grouped[membrane]) for membrane in membranes]
    probabilities = outbound._softmax(energies, temperature=1.0)
    return {
        membrane.value: probability
        for membrane, probability in zip(membranes, probabilities)
    }


def _input_activation(
    mind: BaseAgenticMemoryRAG,
    activations: Sequence[tuple[float, str]],
    *,
    snapshot: WeightSnapshot,
) -> outbound.TransientActivation:
    edges = mind.store.list_edges(GraphSide.INPUT)
    outgoing = defaultdict(list)
    for edge in edges:
        outgoing[edge.source_id].append(edge)

    def read_only_trace(
        concept_id: str,
        score: float,
        index: int,
    ) -> TraversalTrace | None:
        required_node = INPUT_NODE_IDS[InputTrunk.HEAR]
        distances = {SELF_ID: 0.0}
        previous: dict[str, tuple[str, str]] = {}
        queue = [(0.0, SELF_ID)]
        visited = set()
        while queue:
            distance, node_id = heapq.heappop(queue)
            if node_id in visited:
                continue
            visited.add(node_id)
            if node_id == concept_id:
                break
            local = mind.graph.local_probabilities(
                node_id,
                GraphSide.INPUT,
                snapshot=snapshot,
            )
            for edge in outgoing.get(node_id, ()):
                if node_id == SELF_ID and edge.target_id != required_node:
                    continue
                probability = local.get(edge.edge_id, 0.0)
                next_distance = (
                    distance
                    + edge.delta_y / (1e-6 + probability)
                    + edge.conflict_penalty
                )
                if next_distance < distances.get(edge.target_id, math.inf):
                    distances[edge.target_id] = next_distance
                    previous[edge.target_id] = (node_id, edge.edge_id)
                    heapq.heappush(queue, (next_distance, edge.target_id))
        if concept_id not in distances:
            return None
        nodes = [concept_id]
        edge_ids = []
        cursor = concept_id
        while cursor != SELF_ID:
            if cursor not in previous:
                return None
            parent, edge_id = previous[cursor]
            nodes.append(parent)
            edge_ids.append(edge_id)
            cursor = parent
        nodes.reverse()
        edge_ids.reverse()
        return TraversalTrace(
            trace_id=f"ablation:input:{index}:{concept_id}",
            side=GraphSide.INPUT,
            start_node_id=SELF_ID,
            target_node_id=concept_id,
            path_node_ids=tuple(nodes),
            path_edge_ids=tuple(edge_ids),
            total_travel_time=round(distances[concept_id], 8),
            endpoint_score=score,
        )

    traces = []
    scores = []
    for index, (score, concept_id) in enumerate(activations):
        trace = read_only_trace(concept_id, score, index)
        if trace is not None:
            traces.append(trace)
            scores.append(score)
    if not traces:
        raise RuntimeError("topic has no reachable input concept")
    return outbound.TransientActivation.from_input_traces(traces, scores)


def evaluate(args: argparse.Namespace) -> dict[str, object]:
    embedder = gestation.NativeMassEmbedder(args.model, args.codec)
    observed_at = float(args.now)
    rows = []
    with BaseAgenticMemoryRAG(args.database, embedder=embedder) as mind:
        embedder.bootstrap = False
        snapshot = mind.graph.weight_snapshot(now=observed_at)
        topics = gestation.TOPICS[: args.limit] if args.limit else gestation.TOPICS
        for topic in topics:
            query = topic.description
            activations = latent.rank_productive_concepts(
                mind,
                embedder.embed(query),
                maximum=args.input_concepts,
            )
            try:
                transient = _input_activation(
                    mind,
                    activations,
                    snapshot=snapshot,
                )
            except RuntimeError as error:
                rows.append(
                    {
                        "topic": topic.word,
                        "status": "unreachable_input",
                        "error": str(error),
                        "expected_membrane": outbound.TRUNK_MEMBRANE[
                            topic.output_trunk
                        ].value,
                        "input_x_concepts": [
                            concept_id for _, concept_id in activations
                        ],
                    }
                )
                continue
            raw = outbound.enumerate_output_trajectories(
                mind,
                transient,
                snapshot,
                gravity_strength=args.gravity,
            )
            normalized, gates, _ = outbound.normalize_trajectory_focus(
                raw,
                gate_gravity_strength=args.gravity,
            )
            legacy = legacy_gates(raw)
            expected = outbound.TRUNK_MEMBRANE[topic.output_trunk].value
            new_order = sorted(gates, key=lambda key: (gates[key], key), reverse=True)
            legacy_order = sorted(
                legacy,
                key=lambda key: (legacy[key], key),
                reverse=True,
            )
            top_candidate = max(
                (
                    candidate
                    for candidate in normalized
                    if candidate.membrane.value == new_order[0]
                ),
                key=lambda candidate: (
                    candidate.within_membrane_probability,
                    candidate.terminal_concept_id,
                ),
            )
            concept = mind.store.get_concept(top_candidate.terminal_concept_id)
            rows.append(
                {
                    "topic": topic.word,
                    "status": "evaluated",
                    "expected_membrane": expected,
                    "new_top1": new_order[0],
                    "new_top2": new_order[:2],
                    "legacy_top1": legacy_order[0],
                    "new_correct": new_order[0] == expected,
                    "legacy_correct": legacy_order[0] == expected,
                    "new_gates": gates,
                    "legacy_gates": legacy,
                    "input_x_concepts": [concept_id for _, concept_id in activations],
                    "top_terminal_id": top_candidate.terminal_concept_id,
                    "top_terminal_label": concept.label if concept is not None else None,
                }
            )

    count = len(rows)
    evaluated = [row for row in rows if row["status"] == "evaluated"]
    evaluated_count = len(evaluated)
    new_correct = sum(bool(row["new_correct"]) for row in evaluated)
    legacy_correct = sum(bool(row["legacy_correct"]) for row in evaluated)
    top2_correct = sum(
        str(row["expected_membrane"]) in row["new_top2"]
        for row in evaluated
    )
    return {
        "schema": "habitus.target-free-outbound-ablation.v1",
        "database": str(args.database),
        "fixed_snapshot_time": observed_at,
        "topic_count": count,
        "evaluated_count": evaluated_count,
        "input_coverage": evaluated_count / max(1, count),
        "new_top1_correct": new_correct,
        "new_top1_accuracy": new_correct / max(1, evaluated_count),
        "new_top1_overall": new_correct / max(1, count),
        "new_top2_correct": top2_correct,
        "new_top2_accuracy": top2_correct / max(1, evaluated_count),
        "new_top2_overall": top2_correct / max(1, count),
        "legacy_top1_correct": legacy_correct,
        "legacy_top1_accuracy": legacy_correct / max(1, evaluated_count),
        "legacy_top1_overall": legacy_correct / max(1, count),
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--model", type=Path, default=nursery.MODEL)
    parser.add_argument("--codec", type=Path, default=nursery.CODEC)
    parser.add_argument("--input-concepts", type=int, default=3)
    parser.add_argument("--gravity", type=float, default=1.5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--now", type=float, default=time.time())
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in (args.database, args.model, args.codec):
        if not path.is_file():
            raise SystemExit(f"required file not found: {path}")
    result = evaluate(args)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "topic_count",
                    "evaluated_count",
                    "input_coverage",
                    "new_top1_correct",
                    "new_top1_accuracy",
                    "new_top1_overall",
                    "new_top2_correct",
                    "new_top2_accuracy",
                    "new_top2_overall",
                    "legacy_top1_correct",
                    "legacy_top1_accuracy",
                    "legacy_top1_overall",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
