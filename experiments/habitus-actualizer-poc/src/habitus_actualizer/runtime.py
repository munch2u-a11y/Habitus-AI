from __future__ import annotations

import asyncio
import hashlib
import json
import math
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

from .abilities import CORE_ABILITIES, AbilityDefinition, WorkspaceAbilities
from .activation import NaturalLanguageActivator
from .contracts import (
    AbilityId,
    AbilityReceipt,
    AbilityRequest,
    ActualizationBatch,
    Effect,
    SuppressedRequest,
)
from ._engine.async_workers import await_sync_call
from ._engine.embeddings import cosine_similarity
from ._engine.graph import INPUT_NODE_IDS, OUTPUT_NODE_IDS, SELF_ID
from ._engine.pipeline import BaseAgenticMemoryRAG
from ._engine.types import InputTrunk, OutputTrunk, RecordType
from .policy import PolicyDenied, WorkspacePolicy


_EFFECT_TRUNKS = {Effect.LOOK: OutputTrunk.LOOK, Effect.DO: OutputTrunk.DO}


class AbilityScheduler:
    """Per-ability FIFO with cross-ability concurrency and explicit ownership."""

    def __init__(self, *, workers: int = 4) -> None:
        if workers < 1:
            raise ValueError("workers must be positive")
        self._executor = ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="habitus-ability",
        )
        self._locks = {ability: threading.Lock() for ability in AbilityId}
        self._closed = False

    async def run(
        self,
        request: AbilityRequest,
        operation: Callable[[], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        if self._closed:
            raise RuntimeError("ability scheduler is closed")
        def ordered_operation() -> Mapping[str, Any]:
            with self._locks[request.ability_id]:
                return operation()

        return await await_sync_call(ordered_operation, executor=self._executor)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=False)


class Actualizer:
    """Schema-free adapter from ordinary assistant prose to verified abilities."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        state_path: str | Path | None = None,
        policy: WorkspacePolicy | None = None,
        confidence_threshold: float = 0.72,
        maximum_abilities: int = 3,
        workers: int = 4,
    ) -> None:
        self.policy = policy or WorkspacePolicy(workspace)
        if Path(workspace).resolve() != self.policy.root:
            raise ValueError("workspace and policy.root must identify the same directory")
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        self.confidence_threshold = confidence_threshold
        self.maximum_abilities = maximum_abilities
        resolved_state = (
            Path(state_path)
            if state_path is not None
            else self.policy.root / ".habitus" / "actualizer.sqlite"
        )
        resolved_state.parent.mkdir(parents=True, exist_ok=True)
        self.mind = BaseAgenticMemoryRAG(resolved_state)
        saved_cwd = self.mind.store.get_metadata("actualizer.cwd", ".") or "."
        try:
            self.workspace = WorkspaceAbilities(self.policy, initial_cwd=saved_cwd)
        except (FileNotFoundError, PolicyDenied):
            self.workspace = WorkspaceAbilities(self.policy)
        self.activator = NaturalLanguageActivator(maximum_abilities=maximum_abilities)
        self.scheduler = AbilityScheduler(workers=workers)
        self.definitions = {item.ability_id: item for item in CORE_ABILITIES}
        self._seed_abilities()
        self._observation_counts = self._seed_observation_counts()
        self._closed = False

    def __enter__(self) -> "Actualizer":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    async def __aenter__(self) -> "Actualizer":
        return self

    async def __aexit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.scheduler.close()
        self.mind.close()

    def _seed_abilities(self) -> None:
        for definition in CORE_ABILITIES:
            ability_id = f"ability:{definition.ability_id.value}"
            if self.mind.store.get_concept(ability_id) is None:
                self.mind.add_concept(
                    ability_id,
                    definition.label,
                    terms=definition.terms,
                    input_trunks=(InputTrunk.SEE,),
                    output_trunks=(_EFFECT_TRUNKS[definition.effect],),
                    kind="crown",
                )
            for status in ("success", "error"):
                return_id = f"{ability_id}:return:{status}"
                if self.mind.store.get_concept(return_id) is None:
                    self.mind.add_concept(
                        return_id,
                        return_id,
                        kind="ability_return",
                        semantic_embedding=False,
                    )
                if self.mind.store.find_edge(
                    side=self._input_side,
                    source_id=ability_id,
                    target_id=return_id,
                ) is None:
                    self.mind.add_relation(
                        ability_id,
                        return_id,
                        side=self._input_side,
                    )

    @staticmethod
    def _observation_signature(
        ability_id: str,
        arguments: Mapping[str, Any],
        output: Any,
    ) -> str:
        """Identify an equivalent verified observation without host-only noise."""

        def stable(value: Any) -> Any:
            if isinstance(value, Mapping):
                return {
                    str(key): stable(item)
                    for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
                    if str(key) not in {"duration_seconds", "elapsed_seconds"}
                }
            if isinstance(value, (list, tuple)):
                return [stable(item) for item in value]
            return value

        stable_arguments = dict(arguments)
        if "workspace_path" in stable_arguments:
            stable_arguments.pop("path", None)
        if "workspace_cwd" in stable_arguments:
            stable_arguments.pop("cwd", None)
        payload = json.dumps(
            {
                "ability": str(ability_id),
                "arguments": stable(stable_arguments),
                "output": stable(output),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _seed_observation_counts(self) -> dict[str, int]:
        """Reconstruct novelty counts from durable, verified action returns."""
        records = self.mind.store.list_records()
        by_id = {record.record_id: record for record in records}
        counts: dict[str, int] = {}
        for returned in records:
            if returned.record_type != RecordType.TOOL_RESULT:
                continue
            if not bool(returned.metadata.get("verified")):
                continue
            if str(returned.metadata.get("return_status")) != "success":
                continue
            called = by_id.get(str(returned.metadata.get("returns_to", "")))
            if called is None:
                continue
            try:
                call_payload = json.loads(called.text)
                return_payload = json.loads(returned.text)
                signature = self._observation_signature(
                    str(call_payload["ability"]),
                    dict(call_payload.get("arguments") or {}),
                    return_payload.get("output"),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            counts[signature] = counts.get(signature, 0) + 1
        return counts

    @property
    def _input_side(self):
        from ._engine.types import GraphSide

        return GraphSide.INPUT

    @property
    def _output_side(self):
        from ._engine.types import GraphSide

        return GraphSide.OUTPUT

    def ability_prior(self, ability_id: AbilityId | str) -> tuple[float, float]:
        """Return an ability's current local mass and its neutral baseline."""
        resolved = (
            ability_id
            if isinstance(ability_id, AbilityId)
            else AbilityId(ability_id)
        )
        definition = self.definitions[resolved]
        trunk = _EFFECT_TRUNKS[definition.effect]
        trunk_node = OUTPUT_NODE_IDS[trunk]
        edge = self.mind.store.find_edge(
            self._output_side,
            trunk_node,
            f"ability:{resolved.value}",
        )
        ability_nodes = {
            f"ability:{item.ability_id.value}"
            for item in self.definitions.values()
            if _EFFECT_TRUNKS[item.effect] == trunk
        }
        siblings = [
            item
            for item in self.mind.store.list_edges(self._output_side)
            if item.source_id == trunk_node and item.target_id in ability_nodes
        ]
        neutral = 1.0 / max(1, len(siblings))
        if edge is None or not siblings:
            return 0.0, neutral
        # Action admission must reflect learned outcome strength, not merely
        # that an edge was touched recently. The Y cipher may use recency while
        # traversing, but a recent verified failure must not become a stronger
        # future habit just because it was recent.
        logits = {
            item.edge_id: item.log_strength - item.conflict_penalty
            for item in siblings
        }
        maximum = max(logits.values())
        exponentials = {
            edge_id: math.exp(
                (value - maximum) / self.mind.graph.temperature
            )
            for edge_id, value in logits.items()
        }
        total = sum(exponentials.values()) or 1.0
        return exponentials[edge.edge_id] / total, neutral

    def _confidence(self, request: AbilityRequest) -> AbilityRequest:
        definition = self.definitions[request.ability_id]
        concept = self.mind.store.get_concept(f"ability:{request.ability_id.value}")
        semantic = 0.0
        if concept is not None:
            semantic = max(
                0.0,
                cosine_similarity(
                    self.mind.embedder.embed(request.phrase),
                    concept.embedding,
                ),
            )
        habit_prior, neutral_prior = self.ability_prior(request.ability_id)
        # Habits calibrate a candidate only after the explicit action grammar
        # has nominated it. They cannot make unrelated prose executable.
        ratio = max(1e-9, habit_prior) / max(1e-9, neutral_prior)
        habit_adjustment = 0.10 * math.tanh(math.log(ratio))
        combined = min(
            1.0,
            max(
                0.0,
                0.85 * request.confidence
                + 0.15 * semantic
                + habit_adjustment,
            ),
        )
        return replace(
            request,
            confidence=round(combined, 6),
            reasons=(
                *request.reasons,
                f"semantic:{semantic:.3f}",
                f"habit:{habit_prior:.3f}",
                f"habit-neutral:{neutral_prior:.3f}",
                f"effect:{definition.effect.value}",
            ),
        )

    def _open_ability_cycle(
        self,
        request: AbilityRequest,
        *,
        source_id: str,
        metadata: Mapping[str, Any] | None = None,
    ):
        definition = self.definitions[request.ability_id]
        ability_node = f"ability:{request.ability_id.value}"
        trunk = _EFFECT_TRUNKS[definition.effect]
        decision = self.mind.classify_output(
            request.phrase,
            target_concept_id=ability_node,
            required_output_trunk=trunk,
        )
        invocation = json.dumps(
            {
                "ability": request.ability_id.value,
                "arguments": dict(request.arguments),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        cycle = self.mind.begin_output_cycle(
            invocation,
            decision,
            source_id=source_id,
            record_type=RecordType.TOOL_CALL,
            metadata={
                "ability_id": request.ability_id.value,
                "request_id": request.request_id,
                "phrase": request.phrase,
                "developer_ledger": True,
                **dict(metadata or {}),
            },
        )
        return definition, ability_node, decision, cycle

    def _close_ability_cycle(
        self,
        request: AbilityRequest,
        *,
        definition: AbilityDefinition,
        ability_node: str,
        decision,
        cycle,
        status: str,
        verified: bool,
        output: Any,
        error: str,
        started: float,
        receipt_id: str | None = None,
        source_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AbilityReceipt:
        observation_signature = None
        observation_repeat_count = 0
        if status == "success" and verified:
            observation_signature = self._observation_signature(
                request.ability_id.value,
                request.arguments,
                output,
            )
            observation_repeat_count = self._observation_counts.get(
                observation_signature,
                0,
            )
            # A repeated unchanged observation remains weakly useful, but does
            # not reinforce a habit as much as the first informative result.
            reward = 0.20 / (observation_repeat_count + 1)
        elif verified:
            reward = -0.20
        else:
            reward = 0.0
        resolved_receipt_id = receipt_id or f"receipt:{uuid.uuid4().hex}"
        return_node = f"{ability_node}:return:{status}"
        returned = self.mind.record_cycle_return(
            cycle.cycle_id,
            json.dumps(
                {
                    "ability": request.ability_id.value,
                    "status": status,
                    "output": output,
                    "error": error,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ),
            input_trunk=InputTrunk.SEE,
            status=status,
            stability_delta=reward,
            verified=verified,
            terminal=True,
            source_id=source_id or request.ability_id.value,
            record_type=RecordType.TOOL_RESULT,
            record_id=resolved_receipt_id,
            event_id=f"event:{resolved_receipt_id}",
            return_concept_id=return_node,
            return_path_node_ids=(
                SELF_ID,
                INPUT_NODE_IDS[InputTrunk.SEE],
                ability_node,
                return_node,
            ),
            provenance={"ability_id": request.ability_id.value},
            metadata={
                "request_id": request.request_id,
                "developer_ledger": True,
                "observation_signature": observation_signature,
                "observation_repeat_count": observation_repeat_count,
                "stability_reward": reward,
                **dict(metadata or {}),
            },
            allow_growth=False,
        )
        if observation_signature is not None:
            self._observation_counts[observation_signature] = (
                observation_repeat_count + 1
            )
        return AbilityReceipt(
            request_id=request.request_id,
            ability_id=request.ability_id,
            effect=definition.effect,
            status=status,
            verified=verified,
            arguments=request.arguments,
            output=output,
            error=error,
            elapsed_seconds=round(time.perf_counter() - started, 6),
            cycle_id=cycle.cycle_id,
            output_record_id=cycle.output_record_id,
            return_record_id=returned.record.record_id,
            outcome_id=returned.outcome.outcome_id,
            trace_node_ids=decision.trace.path_node_ids if decision.trace else (),
        )

    async def _execute(self, request: AbilityRequest) -> AbilityReceipt:
        definition, ability_node, decision, cycle = self._open_ability_cycle(
            request,
            source_id="actualizer",
        )
        started = time.perf_counter()
        try:
            output = await self.scheduler.run(
                request,
                lambda: self.workspace.execute(request),
            )
            status = "success"
            error = ""
        except Exception as caught:
            output = None
            status = "error"
            error = self._error_text(caught)
        if request.ability_id == AbilityId.NAVIGATE and status == "success":
            self.mind.store.set_metadata(
                "actualizer.cwd",
                self.workspace.display_path(self.workspace.cwd),
            )
        return self._close_ability_cycle(
            request,
            definition=definition,
            ability_node=ability_node,
            decision=decision,
            cycle=cycle,
            status=status,
            verified=True,
            output=output,
            error=error,
            started=started,
        )

    def observe_ability_result(
        self,
        ability_id: AbilityId | str,
        *,
        status: str,
        verified: bool,
        arguments: Mapping[str, Any] | None = None,
        output: Any = None,
        error: str = "",
        phrase: str = "",
        source_id: str = "external-host",
        receipt_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AbilityReceipt:
        """Learn from an action already executed and observed by the host.

        This method performs no workspace effect. Unverified observations are
        persisted for auditability but cannot reinforce the action graph.
        """
        if self._closed:
            raise RuntimeError("actualizer is closed")
        resolved = (
            ability_id
            if isinstance(ability_id, AbilityId)
            else AbilityId(ability_id)
        )
        normalized_status = (
            "success" if str(status).casefold() == "success" else "error"
        )
        request = AbilityRequest(
            request_id=f"observed:{uuid.uuid4().hex}",
            ability_id=resolved,
            phrase=phrase or f"Observed {resolved.value}",
            arguments=dict(arguments or {}),
            confidence=1.0,
            reasons=("host-observed",),
        )
        started = time.perf_counter()
        host_metadata = {"host_observed": True, **dict(metadata or {})}
        definition, ability_node, decision, cycle = self._open_ability_cycle(
            request,
            source_id=source_id,
            metadata=host_metadata,
        )
        return self._close_ability_cycle(
            request,
            definition=definition,
            ability_node=ability_node,
            decision=decision,
            cycle=cycle,
            status=normalized_status,
            verified=bool(verified),
            output=output,
            error=str(error),
            started=started,
            receipt_id=receipt_id,
            source_id=source_id,
            metadata=host_metadata,
        )

    async def actualize(
        self,
        text: str,
        *,
        source_role: str = "assistant",
        dry_run: bool = False,
    ) -> ActualizationBatch:
        if self._closed:
            raise RuntimeError("actualizer is closed")
        parsed, parser_suppressed = self.activator.parse(
            text,
            source_role=source_role,
            apply_limit=False,
        )
        ready: list[AbilityRequest] = []
        suppressed = list(parser_suppressed)
        for request in parsed:
            scored = self._confidence(request)
            if scored.confidence < self.confidence_threshold:
                suppressed.append(
                    SuppressedRequest(
                        scored.phrase,
                        "activation confidence below threshold",
                        scored.ability_id,
                        scored.confidence,
                    )
                )
                continue
            try:
                prepared = self.workspace.prepare(scored)
            except (PolicyDenied, OSError, ValueError) as error:
                suppressed.append(
                    SuppressedRequest(
                        scored.phrase,
                        self._error_text(error),
                        scored.ability_id,
                        scored.confidence,
                    )
                )
                continue
            if prepared.ability_id != scored.ability_id:
                prepared = replace(
                    prepared,
                    reasons=(*prepared.reasons, f"resolved:{prepared.ability_id.value}"),
                )
            if len(ready) >= self.maximum_abilities:
                suppressed.append(
                    SuppressedRequest(
                        prepared.phrase,
                        "per-pulse ability limit reached",
                        prepared.ability_id,
                        prepared.confidence,
                    )
                )
                continue
            ready.append(prepared)
        receipts = () if dry_run else tuple(await asyncio.gather(*(self._execute(item) for item in ready)))
        return ActualizationBatch(
            source_role=source_role,
            source_text=str(text),
            requests=tuple(ready),
            receipts=receipts,
            suppressed=tuple(suppressed),
            metadata={
                "workspace": str(self.policy.root),
                "cwd": self.workspace.display_path(self.workspace.cwd),
                "dry_run": bool(dry_run),
                "maximum_abilities": self.maximum_abilities,
            },
        )

    @staticmethod
    def _error_text(error: Exception) -> str:
        if isinstance(error, FileNotFoundError):
            target = error.filename or (error.args[0] if error.args else "the target")
            return f"{target} does not exist"
        return str(error)

    def actualize_sync(
        self,
        text: str,
        *,
        source_role: str = "assistant",
        dry_run: bool = False,
    ) -> ActualizationBatch:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.actualize(text, source_role=source_role, dry_run=dry_run)
            )
        raise RuntimeError("actualize_sync cannot run inside an active event loop")

    def graph_health(self) -> Mapping[str, Any]:
        violations = self.mind.graph.validate_invariants()
        return {"healthy": not violations, "violations": tuple(violations)}
