#!/usr/bin/env python3
"""Deterministic nursery for embodied, output-first action learning.

This is deliberately not an open-ended chat simulation.  It gives a gestated
mind a tiny sealed environment, opaque action fibers, structured sensory
returns, and repeated contingent feedback.  The developer ledger keeps JSON
receipts for inspection, while graph-facing action/state nodes carry no natural
language semantics.
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
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.graph import INPUT_NODE_IDS, SELF_ID  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.tools import ToolDefinition, ToolReceipt, ToolRegistry  # noqa: E402
from habitus_ai.types import (  # noqa: E402
    EventKind,
    GraphSide,
    InputTrunk,
    OutputDecision,
    OutputTrunk,
    RecordType,
    TraversalTrace,
)
import outbound_focus as outbound  # noqa: E402


STATE_IDS = tuple(f"state:s{index}" for index in range(6))
ABILITY_IDS = tuple(f"ability:a{index}" for index in range(5))
DEVELOPER_ACTION_NAMES = {
    "ability:a0": "orient",
    "ability:a1": "open",
    "ability:a2": "read",
    "ability:a3": "write",
    "ability:a4": "run",
}
ABILITY_TRUNKS = {
    "ability:a0": OutputTrunk.LOOK,
    "ability:a1": OutputTrunk.LOOK,
    "ability:a2": OutputTrunk.LOOK,
    "ability:a3": OutputTrunk.DO,
    "ability:a4": OutputTrunk.DO,
}
CURRICULUM = {
    "state:s0": ("ability:a0", "state:s1"),
    "state:s1": ("ability:a1", "state:s2"),
    "state:s2": ("ability:a2", "state:s3"),
    "state:s3": ("ability:a3", "state:s4"),
    "state:s4": ("ability:a4", "state:s5"),
}


def opaque_vector(key: str, dimension: int) -> tuple[float, ...]:
    """Make a stable non-lexical unit vector from an opaque feature key."""
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        digest = hashlib.sha256(f"{key}|{counter}".encode("ascii")).digest()
        values.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1
    vector = values[:dimension]
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return tuple(value / norm for value in vector)


class NurseryBoundaryError(ValueError):
    pass


class NurseryWorld:
    """A closed virtual room; no shell, network, or path can escape its root."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._initialize_objects()
        self.state_id = STATE_IDS[0]

    def _resolve(self, relative: str, *, must_exist: bool = False) -> Path:
        raw = Path(str(relative))
        if raw.is_absolute():
            raise NurseryBoundaryError("absolute paths are outside the nursery")
        candidate = (self.root / raw).resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise NurseryBoundaryError("path leaves the nursery") from exc
        if must_exist and not candidate.exists():
            raise FileNotFoundError(str(raw))
        return candidate

    def _initialize_objects(self) -> None:
        box = self._resolve("objects/box")
        scratch = self._resolve("scratch")
        box.mkdir(parents=True, exist_ok=True)
        scratch.mkdir(parents=True, exist_ok=True)
        card = self._resolve("objects/box/card.dat")
        toy = self._resolve("objects/beacon.toy")
        if not card.exists():
            card.write_text("pattern=round-blue\n", encoding="utf-8")
        if not toy.exists():
            toy.write_text("effect=soft-chime\n", encoding="utf-8")

    def reset(self) -> None:
        self.state_id = STATE_IDS[0]

    def perform(self, ability_id: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        expected = CURRICULUM.get(self.state_id)
        if expected is None or ability_id != expected[0]:
            raise RuntimeError(f"rejected:{self.state_id}:{ability_id}")

        source_state = self.state_id
        next_state = expected[1]
        features: list[str] = ["change:accepted", f"from:{source_state}"]
        if ability_id == "ability:a0":
            visible = sorted(path.name for path in self._resolve("objects").iterdir())
            features.extend(f"object:{index}" for index, _ in enumerate(visible))
        elif ability_id == "ability:a1":
            features.append("container:open")
        elif ability_id == "ability:a2":
            content = self._resolve("objects/box/card.dat", must_exist=True).read_bytes()
            features.append(f"content-hash:{hashlib.sha256(content).hexdigest()[:12]}")
        elif ability_id == "ability:a3":
            payload = str(arguments.get("payload", "round-blue"))[:128]
            target = self._resolve("scratch/response.dat")
            target.write_text(payload, encoding="utf-8")
            features.extend(("artifact:present", f"bytes:{len(payload.encode('utf-8'))}"))
        elif ability_id == "ability:a4":
            # This is a tiny interpreter for one whitelisted toy, not process execution.
            instruction = self._resolve("objects/beacon.toy", must_exist=True).read_text(
                encoding="utf-8"
            ).strip()
            if instruction != "effect=soft-chime":
                raise RuntimeError("toy-validation-failed")
            features.append("effect:soft-chime")
        else:
            raise KeyError(ability_id)

        self.state_id = next_state
        features.append(f"state:{next_state}")
        return {
            "state_concept": next_state,
            "features": features,
            "changed": True,
        }


@dataclass(frozen=True)
class ActionProbe:
    state_id: str
    selected_ability_id: str | None
    expected_ability_id: str
    probability: float
    path_node_ids: tuple[str, ...]

    @property
    def correct(self) -> bool:
        return self.selected_ability_id == self.expected_ability_id


def _state_return_router(world: NurseryWorld):
    def route(status: str, result: Any, _error: str) -> str | None:
        if status == "success" and isinstance(result, Mapping):
            return str(result.get("state_concept") or world.state_id)
        return world.state_id

    return route


def _sensory_encoder(status: str, result: Any, error: str, dimension: int) -> Sequence[float]:
    features: Sequence[object] = ()
    if isinstance(result, Mapping):
        raw = result.get("features", ())
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            features = raw
    key = "|".join((status, *(str(item) for item in features), error))
    return opaque_vector(key, dimension)


class EmbodiedNursery:
    def __init__(self, mind: BaseAgenticMemoryRAG, world: NurseryWorld):
        self.mind = mind
        self.world = world
        self.registry = ToolRegistry(mind)
        self._seed_opaque_environment()

    def _seed_opaque_environment(self) -> None:
        router = _state_return_router(self.world)
        for ability_id in ABILITY_IDS:
            self.registry.register_tool(
                ToolDefinition(
                    tool_id=ability_id,
                    trunk=ABILITY_TRUNKS[ability_id],
                    label=DEVELOPER_ACTION_NAMES[ability_id],
                    description="A nursery motor fiber.",
                    terms=(),
                    parameters={},
                    handler=lambda args, selected=ability_id: self.world.perform(selected, args),
                    opaque=True,
                    bind_to_trunk=False,
                    return_router=router,
                    sensory_encoder=_sensory_encoder,
                )
            )

        birth_id = "sense:i0"
        self.mind.add_concept(
            birth_id,
            birth_id,
            input_trunks=(InputTrunk.SEE,),
            kind="sense",
            semantic_embedding=False,
        )
        for state_id in STATE_IDS:
            expected = CURRICULUM.get(state_id)
            output_trunks = ((ABILITY_TRUNKS[expected[0]],) if expected else ())
            self.mind.add_concept(
                state_id,
                state_id,
                output_trunks=output_trunks,
                kind="state",
                semantic_embedding=False,
            )
        self.mind.add_relation(birth_id, STATE_IDS[0], side=GraphSide.INPUT)

        for state_id, (correct_ability, next_state) in CURRICULUM.items():
            trunk = ABILITY_TRUNKS[correct_ability]
            for ability_id in ABILITY_IDS:
                if ABILITY_TRUNKS[ability_id] == trunk:
                    self.mind.add_relation(
                        state_id,
                        ability_id,
                        side=GraphSide.OUTPUT,
                    )
            success_id = self.registry.return_concept_id(correct_ability, "success")
            self.mind.add_relation(success_id, next_state, side=GraphSide.INPUT)

        # A failed action returns to the still-present state. These relations
        # let the same return record carry both error and current-scene memory.
        for ability_id in ABILITY_IDS:
            error_id = self.registry.return_concept_id(ability_id, "error")
            for state_id in CURRICULUM:
                self.mind.add_relation(error_id, state_id, side=GraphSide.INPUT)

    def observe_initial_state(self) -> None:
        state_id = self.world.state_id
        payload = json.dumps(
            {"sense": "sense:i0", "state_concept": state_id, "features": ["familiar:home"]},
            sort_keys=True,
            separators=(",", ":"),
        )
        record = self.mind.remember(
            payload,
            kind=EventKind.OBSERVATION,
            source_id="nursery",
            record_type=RecordType.OBSERVATION,
            concept_ids=(state_id,),
            metadata={"cycle_role": "exogenous", "nursery": True},
            allow_growth=False,
            input_trunk=InputTrunk.SEE,
            embedding=opaque_vector(f"initial:{state_id}", self.mind.embedder.dimension),
        )
        trace = self.mind.graph.trace_explicit_path(
            pulse_id=f"nursery:initial:{self.mind.pulse}",
            side=GraphSide.INPUT,
            path_node_ids=(SELF_ID, INPUT_NODE_IDS[InputTrunk.SEE], "sense:i0", state_id),
        )
        self.mind.graph.deposit_trace(record, trace, pulse=self.mind.pulse)

    def _focus(self, state_id: str) -> outbound.OutputFocus:
        return outbound.resolve_output_focus(
            self.mind,
            outbound.TransientActivation({state_id: 1.0}),
            gravity_strength=5.0,
            distance_strength=0.04,
            maximum_membranes=1,
            gate_floor=0.0,
            mark_active=False,
        )

    @staticmethod
    def _decision(focus: outbound.OutputFocus, trajectory: outbound.OutputTrajectory) -> OutputDecision:
        trace = TraversalTrace(
            trace_id=f"trace:{focus.pulse_id}:output:{trajectory.terminal_concept_id}",
            side=GraphSide.OUTPUT,
            start_node_id=SELF_ID,
            target_node_id=trajectory.terminal_concept_id,
            path_node_ids=trajectory.path_node_ids,
            path_edge_ids=trajectory.path_edge_ids,
            total_travel_time=trajectory.y_distance,
            endpoint_score=trajectory.effective_probability,
        )
        return OutputDecision(
            pulse_id=focus.pulse_id,
            trunk=trajectory.trunk,
            confidence=trajectory.effective_probability,
            trace=trace,
        )

    def decision_for(self, state_id: str, ability_id: str) -> OutputDecision:
        focus = self._focus(state_id)
        options = [
            candidate
            for candidate in focus.candidates
            if candidate.terminal_concept_id == ability_id
            and state_id in candidate.path_node_ids
            and candidate.trunk == ABILITY_TRUNKS[ability_id]
        ]
        if not options:
            raise RuntimeError(f"no route from {state_id} to {ability_id}")
        selected = max(options, key=lambda item: (item.path_score, item.path_node_ids))
        decision = self._decision(focus, selected)
        self.mind.graph.activate_trace(focus.pulse_id, decision.trace)
        return decision

    def probe(self, state_id: str) -> ActionProbe:
        expected = CURRICULUM[state_id][0]
        focus = self._focus(state_id)
        options = [
            candidate
            for candidate in focus.candidates
            if candidate.terminal_concept_id in ABILITY_IDS
            and state_id in candidate.path_node_ids
        ]
        selected = max(
            options,
            key=lambda item: (item.effective_probability, item.terminal_concept_id),
            default=None,
        )
        return ActionProbe(
            state_id=state_id,
            selected_ability_id=(selected.terminal_concept_id if selected else None),
            expected_ability_id=expected,
            probability=(selected.effective_probability if selected else 0.0),
            path_node_ids=(selected.path_node_ids if selected else ()),
        )

    def act(
        self,
        state_id: str,
        ability_id: str,
        *,
        stability_delta: float,
    ) -> ToolReceipt:
        arguments = {"payload": "round-blue"} if ability_id == "ability:a3" else {}
        return self.registry.execute(
            ability_id,
            arguments,
            stability_delta=stability_delta,
            decision=self.decision_for(state_id, ability_id),
        )

    def train(self, epochs: int = 6, *, include_safe_errors: bool = True) -> list[ToolReceipt]:
        receipts: list[ToolReceipt] = []
        for _ in range(max(0, int(epochs))):
            self.world.reset()
            self.observe_initial_state()
            for state_id, (correct, _next_state) in CURRICULUM.items():
                if self.world.state_id != state_id:
                    raise RuntimeError("nursery world and curriculum diverged")
                same_trunk = [
                    ability_id
                    for ability_id in ABILITY_IDS
                    if ABILITY_TRUNKS[ability_id] == ABILITY_TRUNKS[correct]
                    and ability_id != correct
                ]
                if include_safe_errors and same_trunk:
                    wrong = same_trunk[0]
                    receipts.append(self.act(state_id, wrong, stability_delta=-0.45))
                    if self.world.state_id != state_id:
                        raise RuntimeError("rejected nursery action mutated the world")
                receipts.append(self.act(state_id, correct, stability_delta=0.80))
        return receipts


def run_embodied_nursery(
    database: str | Path,
    world_root: str | Path,
    *,
    epochs: int = 6,
) -> dict[str, Any]:
    with BaseAgenticMemoryRAG(database) as mind:
        world = NurseryWorld(world_root)
        nursery = EmbodiedNursery(mind, world)
        baseline = [nursery.probe(state_id) for state_id in CURRICULUM]
        receipts = nursery.train(epochs)
        trained = [nursery.probe(state_id) for state_id in CURRICULUM]
        cycles = [
            mind.experience_cycle(receipt.cycle_id)
            for receipt in receipts
            if receipt.cycle_id is not None
        ]
        snapshot = mind.graph.weight_snapshot()
        boundary_blocked = False
        try:
            world._resolve("../outside")
        except NurseryBoundaryError:
            boundary_blocked = True
        report = {
            "schema": "habitus.embodied-nursery.v1",
            "epochs": int(epochs),
            "opaque_graph_labels": True,
            "developer_action_names": dict(DEVELOPER_ACTION_NAMES),
            "baseline": [asdict(probe) | {"correct": probe.correct} for probe in baseline],
            "trained": [asdict(probe) | {"correct": probe.correct} for probe in trained],
            "baseline_accuracy": sum(probe.correct for probe in baseline) / len(baseline),
            "trained_accuracy": sum(probe.correct for probe in trained) / len(trained),
            "action_cycles": len(cycles),
            "closed_cycles": sum(cycle is not None and cycle.status == "closed" for cycle in cycles),
            "verified_successes": sum(receipt.verified and receipt.status == "success" for receipt in receipts),
            "verified_errors": sum(receipt.verified and receipt.status == "error" for receipt in receipts),
            "output_first_records": all(
                cycle is not None
                and mind.store.get_record(cycle.output_record_id).record_type == RecordType.TOOL_CALL
                and cycle.terminal_return_record_id is not None
                and mind.store.get_record(cycle.terminal_return_record_id).record_type == RecordType.TOOL_RESULT
                for cycle in cycles
            ),
            "global_edge_mass": snapshot.total,
            "root_flow_mass": snapshot.total,
            "accounted_flow_mass": snapshot.accounted_mass,
            "cumulative_edge_occupancy": snapshot.cumulative_edge_mass,
            "regional_flow_mass": dict(snapshot.regional_weights),
            "layer_flow_mass": dict(snapshot.layer_weights),
            "boundary_escape_blocked": boundary_blocked,
            "graph_invariants": mind.graph.validate_invariants(),
        }
        return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, default=EXPERIMENT_ROOT / "nursery_runs")
    parser.add_argument("--epochs", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.run_directory.mkdir(parents=True, exist_ok=True)
    stamp = time.time_ns()
    report = run_embodied_nursery(
        args.run_directory / f"embodied-{stamp}.sqlite",
        args.run_directory / f"world-{stamp}",
        epochs=args.epochs,
    )
    receipt_path = args.run_directory / f"embodied-{stamp}.json"
    receipt_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"receipt> {receipt_path}")
    return 0 if report["graph_invariants"] == [] else 1


if __name__ == "__main__":
    raise SystemExit(main())
