#!/usr/bin/env python3
"""Route a live Habitus pulse through a graph-structured 1024D language frame.

This experiment combines two signals at the shared semantic membrane:

* dense fields derived from the current graph, its selected Y paths, and the
  final SELF-originating conserved-flow snapshot; and
* geometry-only lexeme nodes reached through learned productive fibers.

The native model receives only ordered floating-point rows.  User text,
retrieved records, node labels, and rendered context never enter the packet.
The selected output trunk controls whether generated language is external
(`SPEAK`) or returns as a private self-originated signal (`LOOK`/`DO`).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.embeddings import cosine_similarity  # noqa: E402
from habitus_ai.graph import OUTPUT_NODE_IDS, SELF_ID, WeightSnapshot  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import (  # noqa: E402
    GraphSide,
    InputTrunk,
    OutputTrunk,
    TraversalTrace,
)
import accelerated_gestation as gestation  # noqa: E402
import nursery  # noqa: E402
import opaque_skeleton  # noqa: E402
import probe_hatched_mind  # noqa: E402


DIMENSION = 1024
MAXIMUM_NATIVE_ROWS = 8
DEFAULT_DATABASE = next(
    iter(
        sorted(
            (EXPERIMENT_ROOT / "accelerated_gestation_runs").glob("habitus-*.sqlite"),
            reverse=True,
        )
    ),
    Path("missing.sqlite"),
)
RUNNER = EXPERIMENT_ROOT / "native" / "graph_soft_generator"


@dataclass(frozen=True)
class SoftmaxReceipt:
    stage: str
    observed_at: float
    edge_count: int
    global_mass: float
    accounted_mass: float
    cumulative_edge_mass: float
    regional_mass: Mapping[str, float]
    layer_mass: Mapping[str, float]
    snapshot_sha256: str


@dataclass(frozen=True)
class LatentRowSource:
    kind: str
    node_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActivationFrame:
    pulse_id: str
    activated_concept_ids: tuple[str, ...]
    activation_scores: tuple[float, ...]
    input_traces: tuple[TraversalTrace, ...]
    output_traces: tuple[TraversalTrace, ...]
    rows: tuple[tuple[float, ...], ...]
    row_sources: tuple[LatentRowSource, ...]
    output_trunk: OutputTrunk | None
    action_gates: Mapping[str, float]
    destination: str
    recalibrations: tuple[SoftmaxReceipt, ...]
    final_path_edge_weights: Mapping[str, float]
    final_softmax_sha256: str


def normalize(vector: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(float(value) * float(value) for value in vector))
    if norm <= 0.0:
        raise ValueError("cannot place a zero vector in a latent frame")
    return tuple(float(value) / norm for value in vector)


def weighted_field(
    dimension: int,
    terms: Iterable[tuple[Sequence[float], float]],
) -> tuple[float, ...]:
    values = [0.0] * dimension
    used = False
    for vector, weight in terms:
        if len(vector) != dimension or not math.isfinite(float(weight)):
            raise ValueError("invalid graph field term")
        if weight == 0.0:
            continue
        used = True
        for index, value in enumerate(vector):
            values[index] += float(value) * float(weight)
    if not used:
        raise ValueError("graph field has no nonzero terms")
    return normalize(values)


def _snapshot_digest(snapshot: WeightSnapshot) -> str:
    digest = hashlib.sha256()
    for edge_id in sorted(snapshot.global_weights):
        digest.update(edge_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(format(snapshot.effective_logits[edge_id], ".17g").encode("ascii"))
        digest.update(b"\0")
        digest.update(format(snapshot.global_weights[edge_id], ".17g").encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def recalibrate(
    mind: BaseAgenticMemoryRAG,
    *,
    stage: str,
    now: float,
) -> tuple[WeightSnapshot, SoftmaxReceipt]:
    """Materialize and verify one post-mutation conserved-flow snapshot."""
    snapshot = mind.graph.weight_snapshot(now=now)
    if snapshot.global_weights and not math.isclose(
        snapshot.total, 1.0, rel_tol=0.0, abs_tol=1e-12
    ):
        raise RuntimeError(
            f"{stage} root flow mass is {snapshot.total!r}, expected 1.0"
        )
    receipt = SoftmaxReceipt(
        stage=stage,
        observed_at=now,
        edge_count=len(snapshot.global_weights),
        global_mass=snapshot.total,
        accounted_mass=snapshot.accounted_mass,
        cumulative_edge_mass=snapshot.cumulative_edge_mass,
        regional_mass=dict(snapshot.regional_weights),
        layer_mass=dict(snapshot.layer_weights),
        snapshot_sha256=_snapshot_digest(snapshot),
    )
    return snapshot, receipt


def _local_edge_probability(
    mind: BaseAgenticMemoryRAG,
    edge_id: str,
    snapshot: WeightSnapshot,
) -> float:
    edge = mind.store.get_edge(edge_id)
    if edge is None:
        return 0.0
    return mind.graph.local_probabilities(
        edge.source_id,
        edge.side,
        snapshot=snapshot,
    ).get(edge_id, 0.0)


def _route_field(
    mind: BaseAgenticMemoryRAG,
    traces: Sequence[TraversalTrace],
    activation_scores: Sequence[float],
    snapshot: WeightSnapshot,
) -> tuple[float, ...]:
    terms: list[tuple[Sequence[float], float]] = []
    for trace, activation in zip(traces, activation_scores):
        path_length = max(1, len(trace.path_node_ids) - 1)
        for depth, node_id in enumerate(trace.path_node_ids):
            node = mind.store.get_concept(node_id)
            if node is None or not any(node.embedding):
                continue
            if depth == 0:
                local_probability = 1.0
            else:
                local_probability = _local_edge_probability(
                    mind, trace.path_edge_ids[depth - 1], snapshot
                )
            # Asymmetric depth preserves direction in the summed route field.
            depth_weight = 0.25 + (depth / path_length)
            terms.append(
                (
                    node.embedding,
                    max(1e-9, activation)
                    * depth_weight
                    * (0.20 + local_probability),
                )
            )
    return weighted_field(mind.embedder.dimension, terms)


def _whole_mind_field(
    mind: BaseAgenticMemoryRAG,
    snapshot: WeightSnapshot,
) -> tuple[float, ...]:
    """Project effective SELF-originating flow over non-lexical structure."""
    terms: list[tuple[Sequence[float], float]] = []
    for edge in mind.store.list_edges():
        mass = snapshot.global_weights.get(edge.edge_id, 0.0)
        if mass <= 0.0:
            continue
        source = mind.store.get_concept(edge.source_id)
        target = mind.store.get_concept(edge.target_id)
        if source is not None and source.kind != "lexeme" and any(source.embedding):
            terms.append((source.embedding, mass * 0.35))
        if target is not None and target.kind != "lexeme" and any(target.embedding):
            terms.append((target.embedding, mass))
    return weighted_field(mind.embedder.dimension, terms)


def _activation_field(
    mind: BaseAgenticMemoryRAG,
    concept_ids: Sequence[str],
    activation_scores: Sequence[float],
) -> tuple[float, ...]:
    terms = []
    for concept_id, activation in zip(concept_ids, activation_scores):
        concept = mind.store.get_concept(concept_id)
        if concept is not None and any(concept.embedding):
            terms.append((concept.embedding, max(1e-9, activation)))
    return weighted_field(mind.embedder.dimension, terms)


def _ordered_membrane_rows(
    mind: BaseAgenticMemoryRAG,
    concept_id: str,
    snapshot: WeightSnapshot,
    *,
    maximum_rows: int,
) -> tuple[list[tuple[float, ...]], list[LatentRowSource]]:
    candidates: list[tuple[float, str, str]] = []
    for edge in mind.store.list_edges(GraphSide.OUTPUT):
        if edge.source_id != concept_id:
            continue
        target = mind.store.get_concept(edge.target_id)
        if target is None or target.kind != "lexeme" or not any(target.embedding):
            continue
        candidates.append(
            (
                _local_edge_probability(mind, edge.edge_id, snapshot),
                target.concept_id,
                edge.edge_id,
            )
        )
    candidates.sort(key=lambda item: (-item[0], item[1]))
    candidates = candidates[:maximum_rows]
    if not candidates:
        return [], []

    by_id = {node_id: (probability, edge_id) for probability, node_id, edge_id in candidates}
    ordered = [candidates[0][1]]
    remaining = set(by_id) - set(ordered)
    transition_by_target: dict[str, str | None] = {ordered[0]: None}
    while remaining:
        source = ordered[-1]
        ranked = []
        for target in remaining:
            edge = mind.store.find_edge(GraphSide.OUTPUT, source, target)
            transition_probability = (
                _local_edge_probability(mind, edge.edge_id, snapshot)
                if edge is not None
                else -1.0
            )
            ranked.append(
                (
                    edge is not None,
                    transition_probability,
                    by_id[target][0],
                    target,
                    edge.edge_id if edge is not None else None,
                )
            )
        _, _, _, target, transition_id = max(ranked)
        ordered.append(target)
        remaining.remove(target)
        transition_by_target[target] = transition_id

    rows = []
    sources = []
    for node_id in ordered:
        node = mind.store.get_concept(node_id)
        if node is None:
            continue
        fiber_id = by_id[node_id][1]
        transition_id = transition_by_target[node_id]
        edge_ids = (fiber_id,) if transition_id is None else (fiber_id, transition_id)
        rows.append(normalize(node.embedding))
        sources.append(
            LatentRowSource(
                kind="learned_membrane_geometry",
                node_ids=(node_id,),
                edge_ids=edge_ids,
            )
        )
    return rows, sources


def _action_gates(
    mind: BaseAgenticMemoryRAG,
    snapshot: WeightSnapshot,
) -> dict[str, float]:
    local = mind.graph.local_probabilities(
        SELF_ID, GraphSide.OUTPUT, snapshot=snapshot
    )
    gates = {}
    for trunk, node_id in OUTPUT_NODE_IDS.items():
        edge = mind.store.find_edge(GraphSide.OUTPUT, SELF_ID, node_id)
        gates[trunk.value] = local.get(edge.edge_id, 0.0) if edge is not None else 0.0
    if gates and not math.isclose(sum(gates.values()), 1.0, abs_tol=1e-12):
        raise RuntimeError("output action gates do not conserve local mass")
    return gates


def build_activation_frame(
    mind: BaseAgenticMemoryRAG,
    activations: Sequence[tuple[float, str]],
    *,
    now: float | None = None,
    input_stability: float | None = None,
    maximum_membrane_rows: int = 4,
) -> ActivationFrame:
    """Activate both cones and build from the final post-mutation snapshot."""
    if not activations:
        raise ValueError("an activation frame requires at least one concept")
    if mind.embedder.dimension != DIMENSION:
        raise ValueError(f"language frame requires {DIMENSION}D graph geometry")
    if maximum_membrane_rows < 0 or maximum_membrane_rows > 4:
        raise ValueError("maximum_membrane_rows must be between zero and four")

    observed_at = time.time() if now is None else float(now)
    pulse_number, pulse_id = mind._next_pulse()
    del pulse_number
    recalibrations: list[SoftmaxReceipt] = []
    _, receipt = recalibrate(mind, stage="before_activation", now=observed_at)
    recalibrations.append(receipt)

    scores = tuple(max(0.0, min(1.0, float(score))) for score, _ in activations)
    concept_ids = tuple(concept_id for _, concept_id in activations)
    input_traces = []
    for score, concept_id in zip(scores, concept_ids):
        trace = mind.graph.traverse(
            pulse_id=f"{pulse_id}:input",
            side=GraphSide.INPUT,
            target_id=concept_id,
            endpoint_score=score,
            required_input_trunk=InputTrunk.HEAR,
            now=observed_at,
            mark_active=True,
        )
        if trace is None:
            raise RuntimeError(f"input cone cannot reach {concept_id}")
        input_traces.append(trace)
    _, receipt = recalibrate(mind, stage="after_input_activation", now=observed_at)
    recalibrations.append(receipt)

    if input_stability is not None:
        mind.graph.reinforce_edges(
            (edge_id for trace in input_traces for edge_id in trace.path_edge_ids),
            stability_delta=input_stability,
            verified=True,
            evidence_quality=1.0,
        )
        _, receipt = recalibrate(
            mind, stage="after_input_stability", now=observed_at
        )
        recalibrations.append(receipt)

    output_traces = []
    for score, concept_id in zip(scores, concept_ids):
        trace = mind.graph.traverse(
            pulse_id=f"{pulse_id}:output",
            side=GraphSide.OUTPUT,
            target_id=concept_id,
            endpoint_score=score,
            now=observed_at,
            mark_active=True,
        )
        if trace is None:
            raise RuntimeError(f"output cone cannot reach {concept_id}")
        output_traces.append(trace)
    final_snapshot, receipt = recalibrate(
        mind, stage="after_output_activation_final", now=observed_at
    )
    recalibrations.append(receipt)

    action_gates = _action_gates(mind, final_snapshot)
    selected_trunk = (
        OutputTrunk(max(action_gates.items(), key=lambda item: (item[1], item[0]))[0])
        if action_gates
        else None
    )
    destination = "external" if selected_trunk == OutputTrunk.SPEAK else "internal"

    rows = [
        _whole_mind_field(mind, final_snapshot),
        _route_field(mind, input_traces, scores, final_snapshot),
        _activation_field(mind, concept_ids, scores),
        _route_field(mind, output_traces, scores, final_snapshot),
    ]
    row_sources = [
        LatentRowSource(
            # The string remains stable for old experiment receipts; its data
            # now carries propagated flow mass rather than a flat edge softmax.
            kind="whole_mind_softmax_field",
        ),
        LatentRowSource(
            kind="input_y_route_field",
            node_ids=tuple(
                dict.fromkeys(node for trace in input_traces for node in trace.path_node_ids)
            ),
            edge_ids=tuple(
                dict.fromkeys(edge for trace in input_traces for edge in trace.path_edge_ids)
            ),
        ),
        LatentRowSource(kind="activated_graphlets", node_ids=concept_ids),
        LatentRowSource(
            kind="output_y_route_field",
            node_ids=tuple(
                dict.fromkeys(node for trace in output_traces for node in trace.path_node_ids)
            ),
            edge_ids=tuple(
                dict.fromkeys(edge for trace in output_traces for edge in trace.path_edge_ids)
            ),
        ),
    ]
    membrane_rows, membrane_sources = _ordered_membrane_rows(
        mind,
        concept_ids[0],
        final_snapshot,
        maximum_rows=maximum_membrane_rows,
    )
    rows.extend(membrane_rows)
    row_sources.extend(membrane_sources)
    if len(rows) > MAXIMUM_NATIVE_ROWS:
        raise RuntimeError("activation frame exceeded the native row cap")

    path_edges = tuple(
        dict.fromkeys(
            edge_id
            for trace in (*input_traces, *output_traces)
            for edge_id in trace.path_edge_ids
        )
    )
    return ActivationFrame(
        pulse_id=pulse_id,
        activated_concept_ids=concept_ids,
        activation_scores=scores,
        input_traces=tuple(input_traces),
        output_traces=tuple(output_traces),
        rows=tuple(tuple(row) for row in rows),
        row_sources=tuple(row_sources),
        output_trunk=selected_trunk,
        action_gates=action_gates,
        destination=destination,
        recalibrations=tuple(recalibrations),
        final_path_edge_weights={
            edge_id: final_snapshot.global_weights.get(edge_id, 0.0)
            for edge_id in path_edges
        },
        final_softmax_sha256=receipt.snapshot_sha256,
    )


def apply_verified_output_feedback(
    mind: BaseAgenticMemoryRAG,
    frame: ActivationFrame,
    *,
    stability_delta: float,
    receipt_id: str,
    now: float | None = None,
) -> SoftmaxReceipt:
    """Reinforce the actual output route, then immediately recalibrate it."""
    if not receipt_id.strip():
        raise ValueError("verified output feedback requires a receipt ID")
    mind.graph.reinforce_edges(
        (
            edge_id
            for trace in frame.output_traces
            for edge_id in trace.path_edge_ids
        ),
        stability_delta=stability_delta,
        verified=True,
        evidence_quality=1.0,
    )
    _, receipt = recalibrate(
        mind,
        stage=f"verified_output_feedback:{receipt_id}",
        now=time.time() if now is None else float(now),
    )
    return receipt


def rank_productive_concepts(
    mind: BaseAgenticMemoryRAG,
    query_vector: Sequence[float],
    *,
    maximum: int = 3,
) -> tuple[tuple[float, str], ...]:
    candidates = []
    for concept_id in probe_hatched_mind.productive_concepts(mind):
        concept = mind.store.get_concept(concept_id)
        # Directed lexeme-transition edges make some membrane nodes appear to
        # be productive sources. X nomination belongs to the relational crown,
        # never to a surface label on the membrane itself.
        if concept is None or concept.kind != "crown":
            continue
        candidates.append((cosine_similarity(query_vector, concept.embedding), concept_id))
    ranked = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)
    if not ranked:
        raise RuntimeError("hatched mind has no productive concepts")
    # Relative endpoint activation preserves more than one overlapping concept
    # while keeping the X nomination separate from Y route resistance.
    selected = ranked[: max(1, maximum)]
    floor = selected[-1][0]
    shifted = [max(1e-6, score - floor + 0.05) for score, _ in selected]
    total = sum(shifted)
    return tuple((value / total, concept_id) for value, (_, concept_id) in zip(shifted, selected))


def frame_to_json(frame: ActivationFrame) -> dict[str, object]:
    return {
        "pulse_id": frame.pulse_id,
        "activated_concept_ids": list(frame.activated_concept_ids),
        "activation_scores": list(frame.activation_scores),
        "input_paths": [list(trace.path_node_ids) for trace in frame.input_traces],
        "output_paths": [list(trace.path_node_ids) for trace in frame.output_traces],
        "row_sources": [asdict(source) for source in frame.row_sources],
        "row_count": len(frame.rows),
        "dimension": len(frame.rows[0]),
        "output_trunk": frame.output_trunk.value if frame.output_trunk else None,
        "action_gates": dict(frame.action_gates),
        "destination": frame.destination,
        "recalibrations": [asdict(item) for item in frame.recalibrations],
        "final_path_edge_weights": dict(frame.final_path_edge_weights),
        "final_softmax_sha256": frame.final_softmax_sha256,
        "user_text_in_rows": False,
        "memory_text_in_rows": False,
        "semantic_codebook_used": False,
    }


def ablation_rows(
    frame: ActivationFrame,
    *,
    overlay_strength: float = 0.18,
) -> tuple[tuple[str, tuple[tuple[float, ...], ...]], ...]:
    """Return controls that hold one final graph snapshot and decoder fixed."""
    structural = frame.rows[:4]
    membrane = frame.rows[4:]
    target = contextual_overlay_rows(frame, strength=overlay_strength)
    cases = [
        ("target", target),
        ("separate_hybrid", frame.rows),
        ("structure_only", structural),
    ]
    if membrane:
        cases.append(("membrane_only", membrane))
    cases.extend(
        (
            ("reversed", tuple(reversed(target))),
            (
                "random",
                tuple(
                    tuple(
                        opaque_skeleton.opaque_unit_vector(
                            f"latent-language-random:{index}"
                        )
                    )
                    for index in range(len(target))
                ),
            ),
        )
    )
    return tuple(cases)


def contextual_overlay_rows(
    frame: ActivationFrame,
    *,
    strength: float = 0.18,
) -> tuple[tuple[float, ...], ...]:
    """Overlay the bicone state onto labels without inserting pseudo-words."""
    if not 0.0 <= strength <= 1.0:
        raise ValueError("overlay strength must be between zero and one")
    if len(frame.rows) < 5:
        return frame.rows
    global_field, input_field, activation_field, output_field = frame.rows[:4]
    membrane = frame.rows[4:]
    rows = []
    for index, lexeme in enumerate(membrane):
        position = (index + 1) / (len(membrane) + 1)
        # Position gradually shifts the conditioning field from perception to
        # intended output while the current concept remains central throughout.
        context = weighted_field(
            len(lexeme),
            (
                (global_field, 0.10),
                (activation_field, 0.45),
                (input_field, 0.45 * (1.0 - position)),
                (output_field, 0.45 * position),
            ),
        )
        rows.append(
            weighted_field(
                len(lexeme),
                ((lexeme, 1.0 - strength), (context, strength)),
            )
        )
    return tuple(rows)


def run_once(args: argparse.Namespace) -> dict[str, object]:
    args.run_directory.mkdir(parents=True, exist_ok=True)
    embedder = gestation.NativeMassEmbedder(args.model, args.codec)
    with BaseAgenticMemoryRAG(args.database, embedder=embedder) as mind:
        embedder.bootstrap = False
        query_vector = embedder.embed(args.once)
        activations = rank_productive_concepts(
            mind, query_vector, maximum=args.activated_concepts
        )
        frame = build_activation_frame(
            mind,
            activations,
            input_stability=args.input_stability,
            maximum_membrane_rows=args.membrane_rows,
        )
        target_rows = contextual_overlay_rows(
            frame, strength=args.overlay_strength
        )
        case_rows = (
            ablation_rows(frame, overlay_strength=args.overlay_strength)
            if args.ablations
            else (("target", target_rows),)
        )
        cases = []
        for case_id, rows in case_rows:
            packet_path = args.run_directory / f"{case_id}.packet"
            opaque_skeleton.write_packet(packet_path, rows)
            native = opaque_skeleton.run_native(
                args.model,
                args.runner,
                packet_path,
                maximum_tokens=args.max_tokens,
                seed=args.seed,
                skip_think=True,
            )
            cases.append(
                {
                    "case_id": case_id,
                    "packet": str(packet_path),
                    "packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
                    "rows": len(rows),
                    "native": native,
                }
            )
        target_case = cases[0]
        packet_path = Path(str(target_case["packet"]))
        native = target_case["native"]
        response = str(native["response"]).strip()
        feedback = None
        feedback_state = None
        if args.output_feedback is not None:
            feedback = apply_verified_output_feedback(
                mind,
                frame,
                stability_delta=args.output_feedback,
                receipt_id=args.feedback_receipt,
            )
            feedback_snapshot = mind.graph.weight_snapshot(now=feedback.observed_at)
            feedback_state = {
                "recalibration": asdict(feedback),
                "action_gates": _action_gates(mind, feedback_snapshot),
                "credited_edge_weights": {
                    edge_id: feedback_snapshot.global_weights.get(edge_id, 0.0)
                    for trace in frame.output_traces
                    for edge_id in trace.path_edge_ids
                },
            }

    result = {
        "schema": "habitus.graph-structured-language-pulse.v1",
        "created_ns": time.time_ns(),
        "database": str(args.database),
        "model": str(args.model),
        "input_sha256": hashlib.sha256(args.once.encode("utf-8")).hexdigest(),
        "input_text_crossed_native_boundary": False,
        "retrieved_memory_text_crossed_native_boundary": False,
        "frame": frame_to_json(frame),
        "adapter_projection": {
            "kind": "contextual_membrane_overlay_v1",
            "strength": args.overlay_strength,
            "rows": len(target_rows),
        },
        "packet": str(packet_path),
        "packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        "native": native,
        "cases": cases,
        "external_response": response if frame.destination == "external" else None,
        "internal_response": response if frame.destination == "internal" else None,
        "output_feedback_recalibration": feedback_state,
    }
    receipt_path = args.run_directory / "language-pulse.json"
    receipt_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    result["receipt_path"] = str(receipt_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--model", type=Path, default=nursery.MODEL)
    parser.add_argument("--codec", type=Path, default=nursery.CODEC)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument("--once", required=True)
    parser.add_argument("--activated-concepts", type=int, default=3)
    parser.add_argument("--membrane-rows", type=int, default=4)
    parser.add_argument("--overlay-strength", type=float, default=0.18)
    parser.add_argument("--input-stability", type=float)
    parser.add_argument("--output-feedback", type=float)
    parser.add_argument("--feedback-receipt", default="experimental-observation")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=EXPERIMENT_ROOT / "latent_language_runs" / str(time.time_ns()),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in (args.database, args.model, args.codec, args.runner):
        if not path.is_file():
            raise SystemExit(f"required file not found: {path}")
    result = run_once(args)
    destination = result["frame"]["destination"]
    response = result[f"{destination}_response"]
    print(f"[{destination}] {response}")
    print(json.dumps({
        "receipt": result["receipt_path"],
        "concepts": result["frame"]["activated_concept_ids"],
        "action_gates": result["frame"]["action_gates"],
        "final_softmax": result["frame"]["final_softmax_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
