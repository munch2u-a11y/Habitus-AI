#!/usr/bin/env python3
"""Target-free outbound Y traversal with modality-specific membranes.

Input X nomination is intentionally outside this module.  The caller supplies
only the transient concept activation left by perception.  Output begins at
SELF, enumerates legal Y trajectories from the live edge distribution, and
lets those trajectories select their own Layer 3 terminals.

The output distribution is hierarchical:

* a softmax across communication, navigation, and action membranes;
* a softmax across complete trajectories inside each membrane; and
* effective path mass equal to the product of those two probabilities.

The products conserve a single total output mass of 1.0 without forcing tool,
navigation, and language habits into one surface representation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import enum
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

from habitus_ai.graph import OUTPUT_NODE_IDS, SELF_ID, WeightSnapshot  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import (  # noqa: E402
    GraphSide,
    InputTrunk,
    OutputTrunk,
    TraversalTrace,
)
import accelerated_gestation as gestation  # noqa: E402
import latent_language_pulse as latent  # noqa: E402
import nursery  # noqa: E402
import opaque_skeleton  # noqa: E402


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


class InterfaceMembrane(str, enum.Enum):
    COMMUNICATION = "communication"
    NAVIGATION = "navigation"
    ACTION = "action"


TRUNK_MEMBRANE = {
    OutputTrunk.SPEAK: InterfaceMembrane.COMMUNICATION,
    OutputTrunk.LOOK: InterfaceMembrane.NAVIGATION,
    OutputTrunk.DO: InterfaceMembrane.ACTION,
}


@dataclass(frozen=True)
class TransientActivation:
    values: Mapping[str, float]

    @classmethod
    def from_input_traces(
        cls,
        traces: Sequence[TraversalTrace],
        scores: Sequence[float],
        *,
        previous: "TransientActivation | None" = None,
        previous_decay: float = 0.50,
    ) -> "TransientActivation":
        if len(traces) != len(scores):
            raise ValueError("each input trace requires one activation score")
        if not 0.0 <= previous_decay <= 1.0:
            raise ValueError("previous_decay must be between zero and one")
        values: dict[str, float] = {}
        if previous is not None:
            for node_id, value in previous.values.items():
                decayed = float(value) * previous_decay
                if decayed > 1e-12:
                    values[node_id] = decayed
        for trace, score in zip(traces, scores):
            bounded = max(0.0, min(1.0, float(score)))
            denominator = max(1, len(trace.path_node_ids) - 1)
            for depth, node_id in enumerate(trace.path_node_ids):
                # Upper shared concepts receive the strongest momentary pull.
                depth_weight = depth / denominator
                values[node_id] = values.get(node_id, 0.0) + bounded * depth_weight
        maximum = max(values.values(), default=1.0)
        if maximum > 1.0:
            values = {node_id: value / maximum for node_id, value in values.items()}
        return cls(values)

    def decayed(self, factor: float = 0.50) -> "TransientActivation":
        if not 0.0 <= factor <= 1.0:
            raise ValueError("decay factor must be between zero and one")
        return TransientActivation(
            {
                node_id: value * factor
                for node_id, value in self.values.items()
                if value * factor > 1e-12
            }
        )


@dataclass(frozen=True)
class OutputTrajectory:
    membrane: InterfaceMembrane
    trunk: OutputTrunk
    terminal_concept_id: str
    path_node_ids: tuple[str, ...]
    path_edge_ids: tuple[str, ...]
    path_score: float
    trunk_log_probability: float
    local_log_probability: float
    transient_pull: float
    y_distance: float
    within_membrane_probability: float = 0.0
    trunk_gate_probability: float = 0.0
    effective_probability: float = 0.0


@dataclass(frozen=True)
class MembranePacket:
    membrane: InterfaceMembrane
    trunk: OutputTrunk
    terminal_concept_id: str
    representation: str
    fields: Mapping[str, object]


@dataclass(frozen=True)
class OutputFocus:
    pulse_id: str
    transient_activation: Mapping[str, float]
    candidates: tuple[OutputTrajectory, ...]
    trunk_gates: Mapping[str, float]
    within_membrane_mass: Mapping[str, float]
    total_effective_mass: float
    selected: tuple[OutputTrajectory, ...]
    pre_activation_softmax: latent.SoftmaxReceipt
    final_softmax: latent.SoftmaxReceipt


@dataclass(frozen=True)
class _PartialPath:
    path_node_ids: tuple[str, ...]
    path_edge_ids: tuple[str, ...]
    accumulated_score: float
    trunk_log_probability: float
    local_log_probability: float
    transient_pull: float
    y_distance: float

    @property
    def normalized_score(self) -> float:
        length = max(1, len(self.path_edge_ids))
        return self.accumulated_score / (length ** 0.70)


def _softmax(values: Sequence[float], *, temperature: float) -> list[float]:
    if not values:
        return []
    bounded_temperature = max(0.05, float(temperature))
    maximum = max(values)
    exponentials = [
        math.exp((float(value) - maximum) / bounded_temperature)
        for value in values
    ]
    total = sum(exponentials) or 1.0
    return [value / total for value in exponentials]


def _log_mean_exp(values: Sequence[float]) -> float:
    if not values:
        return -math.inf
    maximum = max(values)
    return maximum + math.log(
        sum(math.exp(value - maximum) for value in values) / len(values)
    )


def _trunk_for_path(path_node_ids: Sequence[str]) -> OutputTrunk | None:
    if len(path_node_ids) < 2:
        return None
    first = path_node_ids[1]
    for trunk, node_id in OUTPUT_NODE_IDS.items():
        if node_id == first:
            return trunk
    return None


def _has_language_fiber(
    mind: BaseAgenticMemoryRAG,
    concept_id: str,
) -> bool:
    for edge in mind.store.list_edges(GraphSide.OUTPUT):
        if edge.source_id != concept_id:
            continue
        target = mind.store.get_concept(edge.target_id)
        if target is not None and target.kind == "lexeme":
            return True
    return False


def _is_terminal(
    mind: BaseAgenticMemoryRAG,
    node_id: str,
    trunk: OutputTrunk | None,
) -> bool:
    concept = mind.store.get_concept(node_id)
    if concept is None or trunk is None:
        return False
    if concept.kind == "ability":
        return True
    if concept.kind != "crown":
        return False
    if trunk == OutputTrunk.SPEAK:
        return _has_language_fiber(mind, node_id)
    productive_children = []
    for edge in mind.store.list_edges(GraphSide.OUTPUT):
        if edge.source_id != node_id:
            continue
        child = mind.store.get_concept(edge.target_id)
        if child is not None and child.kind != "lexeme":
            productive_children.append(child)
    return not productive_children


def enumerate_output_trajectories(
    mind: BaseAgenticMemoryRAG,
    transient: TransientActivation,
    snapshot: WeightSnapshot,
    *,
    maximum_depth: int = 8,
    beam_width: int = 128,
    gravity_strength: float = 1.5,
    distance_strength: float = 0.08,
) -> tuple[OutputTrajectory, ...]:
    """Discover productive terminals without accepting an X endpoint."""
    if maximum_depth < 2:
        raise ValueError("maximum_depth must allow a trunk and a concept")
    if beam_width < 1:
        raise ValueError("beam_width must be positive")
    outgoing: dict[str, list[object]] = {}
    for edge in mind.store.list_edges(GraphSide.OUTPUT):
        outgoing.setdefault(edge.source_id, []).append(edge)

    frontier = [
        _PartialPath(
            path_node_ids=(SELF_ID,),
            path_edge_ids=(),
            accumulated_score=0.0,
            trunk_log_probability=0.0,
            local_log_probability=0.0,
            transient_pull=0.0,
            y_distance=0.0,
        )
    ]
    best_by_terminal: dict[tuple[InterfaceMembrane, str], OutputTrajectory] = {}
    for _ in range(maximum_depth):
        next_frontier = []
        for partial in frontier:
            source_id = partial.path_node_ids[-1]
            local = mind.graph.local_probabilities(
                source_id,
                GraphSide.OUTPUT,
                snapshot=snapshot,
            )
            for edge in outgoing.get(source_id, ()):
                if edge.target_id in partial.path_node_ids:
                    continue
                target = mind.store.get_concept(edge.target_id)
                if target is None or target.kind == "lexeme":
                    continue
                probability = max(1e-12, local.get(edge.edge_id, 0.0))
                pull = max(0.0, min(1.0, transient.values.get(edge.target_id, 0.0)))
                local_log = math.log(probability)
                contribution = (
                    local_log
                    + gravity_strength * pull
                    - distance_strength * edge.delta_y
                )
                advanced = _PartialPath(
                    path_node_ids=(*partial.path_node_ids, edge.target_id),
                    path_edge_ids=(*partial.path_edge_ids, edge.edge_id),
                    accumulated_score=partial.accumulated_score + contribution,
                    trunk_log_probability=(
                        local_log
                        if len(partial.path_edge_ids) == 0
                        else partial.trunk_log_probability
                    ),
                    local_log_probability=partial.local_log_probability + local_log,
                    transient_pull=partial.transient_pull + pull,
                    y_distance=partial.y_distance + edge.delta_y,
                )
                trunk = _trunk_for_path(advanced.path_node_ids)
                if _is_terminal(mind, edge.target_id, trunk):
                    membrane = TRUNK_MEMBRANE[trunk]
                    trajectory = OutputTrajectory(
                        membrane=membrane,
                        trunk=trunk,
                        terminal_concept_id=edge.target_id,
                        path_node_ids=advanced.path_node_ids,
                        path_edge_ids=advanced.path_edge_ids,
                        path_score=advanced.normalized_score,
                        trunk_log_probability=advanced.trunk_log_probability,
                        local_log_probability=advanced.local_log_probability,
                        transient_pull=advanced.transient_pull,
                        y_distance=advanced.y_distance,
                    )
                    key = (membrane, edge.target_id)
                    previous = best_by_terminal.get(key)
                    if previous is None or trajectory.path_score > previous.path_score:
                        best_by_terminal[key] = trajectory
                if len(advanced.path_edge_ids) < maximum_depth:
                    next_frontier.append(advanced)
        frontier = sorted(
            next_frontier,
            key=lambda path: (
                path.normalized_score,
                path.path_node_ids,
            ),
            reverse=True,
        )[:beam_width]
        if not frontier:
            break
    return tuple(
        sorted(
            best_by_terminal.values(),
            key=lambda trajectory: (
                trajectory.path_score,
                trajectory.terminal_concept_id,
            ),
            reverse=True,
        )
    )


def normalize_trajectory_focus(
    candidates: Sequence[OutputTrajectory],
    *,
    temperature: float = 1.0,
    gate_gravity_strength: float = 1.5,
) -> tuple[tuple[OutputTrajectory, ...], dict[str, float], dict[str, float]]:
    if not candidates:
        raise RuntimeError("output graph has no productive Y trajectories")
    by_membrane: dict[InterfaceMembrane, list[OutputTrajectory]] = {}
    for candidate in candidates:
        by_membrane.setdefault(candidate.membrane, []).append(candidate)

    within: dict[tuple[InterfaceMembrane, str], float] = {}
    membrane_energy: dict[InterfaceMembrane, float] = {}
    for membrane, items in by_membrane.items():
        scores = [item.path_score for item in items]
        probabilities = _softmax(scores, temperature=temperature)
        for item, probability in zip(items, probabilities):
            within[(membrane, item.terminal_concept_id)] = probability
        # The membrane decision and the endpoint decision are deliberately
        # separate levels of the hierarchy. Comparing complete path
        # probabilities here would make a sparse trunk look stronger merely
        # because its local softmax divides mass among fewer children. The
        # learned SELF -> trunk edge supplies the durable prior. The strongest
        # transiently activated route supplies current relevance. Branch
        # probabilities still decide which endpoint wins inside the chosen
        # membrane above.
        trunk_priors = {item.trunk_log_probability for item in items}
        if len(trunk_priors) != 1:
            raise RuntimeError(f"{membrane.value} spans multiple trunk priors")
        membrane_energy[membrane] = (
            next(iter(trunk_priors))
            + gate_gravity_strength
            * max((item.transient_pull for item in items), default=0.0)
        )

    ordered_membranes = sorted(membrane_energy, key=lambda item: item.value)
    gate_values = _softmax(
        [membrane_energy[membrane] for membrane in ordered_membranes],
        temperature=1.0,
    )
    gates = {
        membrane: probability
        for membrane, probability in zip(ordered_membranes, gate_values)
    }
    normalized = []
    for candidate in candidates:
        local_probability = within[(candidate.membrane, candidate.terminal_concept_id)]
        gate_probability = gates[candidate.membrane]
        normalized.append(
            replace(
                candidate,
                within_membrane_probability=local_probability,
                trunk_gate_probability=gate_probability,
                effective_probability=local_probability * gate_probability,
            )
        )

    for membrane, items in by_membrane.items():
        total = sum(
            item.within_membrane_probability
            for item in normalized
            if item.membrane == membrane
        )
        if not math.isclose(total, 1.0, abs_tol=1e-12):
            raise RuntimeError(f"{membrane.value} trajectory mass is not conserved")
    if not math.isclose(sum(gates.values()), 1.0, abs_tol=1e-12):
        raise RuntimeError("trunk gate mass is not conserved")
    if not math.isclose(
        sum(item.effective_probability for item in normalized),
        1.0,
        abs_tol=1e-12,
    ):
        raise RuntimeError("effective output trajectory mass is not conserved")
    return (
        tuple(normalized),
        {membrane.value: probability for membrane, probability in gates.items()},
        {
            membrane.value: sum(
                item.within_membrane_probability
                for item in normalized
                if item.membrane == membrane
            )
            for membrane in by_membrane
        },
    )


def select_trajectories(
    candidates: Sequence[OutputTrajectory],
    trunk_gates: Mapping[str, float],
    *,
    maximum_membranes: int = 2,
    gate_floor: float = 0.15,
) -> tuple[OutputTrajectory, ...]:
    if maximum_membranes < 1:
        raise ValueError("maximum_membranes must be positive")
    admitted = [
        membrane
        for membrane, probability in sorted(
            trunk_gates.items(), key=lambda item: (item[1], item[0]), reverse=True
        )
        if probability >= gate_floor
    ][:maximum_membranes]
    if not admitted:
        admitted = [max(trunk_gates, key=trunk_gates.get)]
    selected = []
    for membrane in admitted:
        options = [item for item in candidates if item.membrane.value == membrane]
        if options:
            selected.append(
                max(
                    options,
                    key=lambda item: (
                        item.within_membrane_probability,
                        item.terminal_concept_id,
                    ),
                )
            )
    return tuple(
        sorted(
            selected,
            key=lambda item: (item.effective_probability, item.membrane.value),
            reverse=True,
        )
    )


def resolve_output_focus(
    mind: BaseAgenticMemoryRAG,
    transient: TransientActivation,
    *,
    now: float | None = None,
    maximum_depth: int = 8,
    beam_width: int = 128,
    gravity_strength: float = 1.5,
    distance_strength: float = 0.08,
    temperature: float = 1.0,
    maximum_membranes: int = 2,
    gate_floor: float = 0.15,
    mark_active: bool = True,
) -> OutputFocus:
    observed_at = time.time() if now is None else float(now)
    _, pulse_id = mind._next_pulse()
    snapshot, before = latent.recalibrate(
        mind,
        stage="outbound_before_trajectory",
        now=observed_at,
    )
    raw = enumerate_output_trajectories(
        mind,
        transient,
        snapshot,
        maximum_depth=maximum_depth,
        beam_width=beam_width,
        gravity_strength=gravity_strength,
        distance_strength=distance_strength,
    )
    candidates, gates, within = normalize_trajectory_focus(
        raw,
        temperature=temperature,
        gate_gravity_strength=gravity_strength,
    )
    selected = select_trajectories(
        candidates,
        gates,
        maximum_membranes=maximum_membranes,
        gate_floor=gate_floor,
    )
    if mark_active:
        for index, trajectory in enumerate(selected):
            trace = TraversalTrace(
                trace_id=f"trace:{pulse_id}:outbound:{index}:{trajectory.terminal_concept_id}",
                side=GraphSide.OUTPUT,
                start_node_id=SELF_ID,
                target_node_id=trajectory.terminal_concept_id,
                path_node_ids=trajectory.path_node_ids,
                path_edge_ids=trajectory.path_edge_ids,
                total_travel_time=trajectory.y_distance,
                endpoint_score=trajectory.effective_probability,
            )
            mind.graph.activate_trace(pulse_id, trace, now=observed_at)
    _, final = latent.recalibrate(
        mind,
        stage="outbound_after_selected_trajectory_final",
        now=observed_at,
    )
    return OutputFocus(
        pulse_id=pulse_id,
        transient_activation=dict(transient.values),
        candidates=candidates,
        trunk_gates=gates,
        within_membrane_mass=within,
        total_effective_mass=sum(item.effective_probability for item in candidates),
        selected=selected,
        pre_activation_softmax=before,
        final_softmax=final,
    )


def packets_for_focus(focus: OutputFocus) -> tuple[MembranePacket, ...]:
    packets = []
    for trajectory in focus.selected:
        if trajectory.membrane == InterfaceMembrane.COMMUNICATION:
            representation = "language_geometry"
            fields = {
                "concept_id": trajectory.terminal_concept_id,
                "adapter": "gguf_language",
                "external": True,
            }
        elif trajectory.membrane == InterfaceMembrane.NAVIGATION:
            representation = "navigation_affordance"
            fields = {
                "location_or_operation_id": trajectory.terminal_concept_id,
                "adapter": "structured_navigation",
                "external": False,
            }
        else:
            representation = "ability_invocation"
            fields = {
                "ability_id": trajectory.terminal_concept_id,
                "adapter": "structured_action",
                "external": False,
            }
        packets.append(
            MembranePacket(
                membrane=trajectory.membrane,
                trunk=trajectory.trunk,
                terminal_concept_id=trajectory.terminal_concept_id,
                representation=representation,
                fields=fields,
            )
        )
    return tuple(packets)


def recirculate_private_focus(
    previous: TransientActivation,
    focus: OutputFocus,
    *,
    attenuation: float = 0.50,
) -> TransientActivation:
    if not 0.0 <= attenuation <= 1.0:
        raise ValueError("attenuation must be between zero and one")
    values = dict(previous.decayed(attenuation).values)
    for trajectory in focus.selected:
        if trajectory.membrane == InterfaceMembrane.COMMUNICATION:
            continue
        denominator = max(1, len(trajectory.path_node_ids) - 1)
        for depth, node_id in enumerate(trajectory.path_node_ids):
            contribution = (
                attenuation
                * trajectory.effective_probability
                * (depth / denominator)
            )
            values[node_id] = min(1.0, values.get(node_id, 0.0) + contribution)
    return TransientActivation(values)


def _activate_input(
    mind: BaseAgenticMemoryRAG,
    activations: Sequence[tuple[float, str]],
    *,
    now: float,
) -> tuple[tuple[TraversalTrace, ...], TransientActivation]:
    _, pulse_id = mind._next_pulse()
    traces = []
    scores = []
    for score, concept_id in activations:
        trace = mind.graph.traverse(
            pulse_id=f"{pulse_id}:input",
            side=GraphSide.INPUT,
            target_id=concept_id,
            endpoint_score=score,
            required_input_trunk=InputTrunk.HEAR,
            now=now,
            mark_active=True,
        )
        if trace is None:
            raise RuntimeError(f"input cannot reach {concept_id}")
        traces.append(trace)
        scores.append(score)
    latent.recalibrate(mind, stage="input_activation_final", now=now)
    return tuple(traces), TransientActivation.from_input_traces(traces, scores)


def _communication_rows(
    mind: BaseAgenticMemoryRAG,
    input_traces: Sequence[TraversalTrace],
    input_scores: Sequence[float],
    trajectory: OutputTrajectory,
    *,
    now: float,
    overlay_strength: float,
) -> tuple[tuple[float, ...], ...]:
    snapshot = mind.graph.weight_snapshot(now=now)
    output_trace = TraversalTrace(
        trace_id=f"native:{trajectory.terminal_concept_id}",
        side=GraphSide.OUTPUT,
        start_node_id=SELF_ID,
        target_node_id=trajectory.terminal_concept_id,
        path_node_ids=trajectory.path_node_ids,
        path_edge_ids=trajectory.path_edge_ids,
        total_travel_time=trajectory.y_distance,
        endpoint_score=trajectory.effective_probability,
    )
    structural_rows = (
        latent._whole_mind_field(mind, snapshot),
        latent._route_field(mind, input_traces, input_scores, snapshot),
        latent._activation_field(
            mind,
            (trajectory.terminal_concept_id,),
            (1.0,),
        ),
        latent._route_field(mind, (output_trace,), (1.0,), snapshot),
    )
    membrane_rows, _ = latent._ordered_membrane_rows(
        mind,
        trajectory.terminal_concept_id,
        snapshot,
        maximum_rows=4,
    )
    if not membrane_rows:
        raise RuntimeError("selected communication concept has no learned labels")
    frame = latent.ActivationFrame(
        pulse_id="outbound-native-frame",
        activated_concept_ids=(trajectory.terminal_concept_id,),
        activation_scores=(1.0,),
        input_traces=tuple(input_traces),
        output_traces=(output_trace,),
        rows=tuple((*structural_rows, *membrane_rows)),
        row_sources=(),
        output_trunk=OutputTrunk.SPEAK,
        action_gates={},
        destination="external",
        recalibrations=(),
        final_path_edge_weights={},
        final_softmax_sha256=latent._snapshot_digest(snapshot),
    )
    return latent.contextual_overlay_rows(frame, strength=overlay_strength)


def run_once(args: argparse.Namespace) -> dict[str, object]:
    args.run_directory.mkdir(parents=True, exist_ok=True)
    embedder = gestation.NativeMassEmbedder(args.model, args.codec)
    observed_at = time.time()
    with BaseAgenticMemoryRAG(args.database, embedder=embedder) as mind:
        embedder.bootstrap = False
        input_activations = latent.rank_productive_concepts(
            mind,
            embedder.embed(args.once),
            maximum=args.input_concepts,
        )
        input_traces, transient = _activate_input(
            mind,
            input_activations,
            now=observed_at,
        )
        focus = resolve_output_focus(
            mind,
            transient,
            now=observed_at,
            gravity_strength=args.gravity,
            maximum_membranes=args.maximum_membranes,
            gate_floor=args.gate_floor,
        )
        packets = packets_for_focus(focus)
        outputs = []
        for index, packet in enumerate(packets):
            item: dict[str, object] = {
                "packet": asdict(packet),
                "native": None,
            }
            if packet.membrane == InterfaceMembrane.COMMUNICATION:
                trajectory = next(
                    selected
                    for selected in focus.selected
                    if selected.terminal_concept_id == packet.terminal_concept_id
                )
                rows = _communication_rows(
                    mind,
                    input_traces,
                    [score for score, _ in input_activations],
                    trajectory,
                    now=observed_at,
                    overlay_strength=args.overlay_strength,
                )
                native_packet = args.run_directory / f"communication-{index}.packet"
                opaque_skeleton.write_packet(native_packet, rows)
                native = opaque_skeleton.run_native(
                    args.model,
                    args.runner,
                    native_packet,
                    maximum_tokens=args.max_tokens,
                    seed=args.seed,
                    skip_think=True,
                )
                item["native_packet"] = str(native_packet)
                item["native_packet_sha256"] = hashlib.sha256(
                    native_packet.read_bytes()
                ).hexdigest()
                item["native"] = native
            outputs.append(item)
    receipt = {
        "schema": "habitus.target-free-outbound-focus.v1",
        "created_ns": time.time_ns(),
        "database": str(args.database),
        "input_sha256": hashlib.sha256(args.once.encode("utf-8")).hexdigest(),
        "input_text_crossed_response_boundary": False,
        "input_x_concepts": [concept_id for _, concept_id in input_activations],
        "transient_activation": dict(transient.values),
        "focus": {
            "pulse_id": focus.pulse_id,
            "trunk_gates": dict(focus.trunk_gates),
            "within_membrane_mass": dict(focus.within_membrane_mass),
            "total_effective_mass": focus.total_effective_mass,
            "selected": [asdict(item) for item in focus.selected],
            "top_candidates_by_membrane": {
                membrane.value: [
                    asdict(item)
                    for item in sorted(
                        (
                            candidate
                            for candidate in focus.candidates
                            if candidate.membrane == membrane
                        ),
                        key=lambda candidate: (
                            candidate.within_membrane_probability,
                            candidate.terminal_concept_id,
                        ),
                        reverse=True,
                    )[:3]
                ]
                for membrane in InterfaceMembrane
            },
            "candidate_count": len(focus.candidates),
            "pre_activation_softmax": asdict(focus.pre_activation_softmax),
            "final_softmax": asdict(focus.final_softmax),
        },
        "outputs": outputs,
    }
    receipt_path = args.run_directory / "outbound-focus.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--model", type=Path, default=nursery.MODEL)
    parser.add_argument("--codec", type=Path, default=nursery.CODEC)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument("--once", required=True)
    parser.add_argument("--input-concepts", type=int, default=3)
    parser.add_argument("--gravity", type=float, default=1.5)
    parser.add_argument("--maximum-membranes", type=int, default=2)
    parser.add_argument("--gate-floor", type=float, default=0.15)
    parser.add_argument("--overlay-strength", type=float, default=0.18)
    parser.add_argument("--max-tokens", type=int, default=48)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=EXPERIMENT_ROOT / "outbound_focus_runs" / str(time.time_ns()),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in (args.database, args.model, args.codec, args.runner):
        if not path.is_file():
            raise SystemExit(f"required file not found: {path}")
    receipt = run_once(args)
    print(json.dumps({
        "receipt": receipt["receipt_path"],
        "input_x_concepts": receipt["input_x_concepts"],
        "trunk_gates": receipt["focus"]["trunk_gates"],
        "selected": receipt["focus"]["selected"],
        "outputs": receipt["outputs"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
