from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .context import render_context
from .embeddings import DeterministicHashEmbedder, Embedder, cosine_similarity
from .graph import (
    INPUT_NODE_IDS,
    OUTPUT_NODE_IDS,
    SELF_ID,
    GraphRuntime,
)
from .retrieval import RetrievalEngine
from .store import MindStore
from .surface import SemanticSurface
from .types import (
    ContextBundle,
    EventEnvelope,
    EventKind,
    ExperienceProjection,
    ExperienceState,
    GraphSide,
    InputTrunk,
    MemoryRecord,
    OutcomePacket,
    OverlapCluster,
    OutputDecision,
    OutputTrunk,
    RecordType,
    RetrievalHit,
    RetrievalPacket,
    TraversalTrace,
    as_tuple,
)
from .working_memory import WorkingMemory


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass(frozen=True)
class RecallResult:
    packet: RetrievalPacket
    hits: tuple[RetrievalHit, ...]
    context_bundle: ContextBundle

    @property
    def context(self) -> str:
        return self.context_bundle.text


class BaseAgenticMemoryRAG:
    """End-to-end dual-cipher memory substrate.

    The class deliberately stops before LLM generation and external execution.
    Callers feed `RecallResult.context` to any model and can pass the model's
    ordinary output to `classify_output`.
    """

    def __init__(
        self,
        database_path: str | Path = "habitus_memory.sqlite",
        *,
        embedder: Embedder | None = None,
        direct_top_k: int = 3,
        direct_similarity_floor: float = 0.08,
        base_context_chars: int = 3200,
        maximum_context_chars: int = 6400,
        working_memory_records: int = 16,
        growth_overlap_threshold: float = 0.70,
        growth_promotion_count: int = 2,
        growth_preference_tolerance: float = 0.35,
    ):
        self.embedder = embedder or DeterministicHashEmbedder(1024)
        self.store = MindStore(
            database_path,
            space_id=self.embedder.space_id,
            dimension=self.embedder.dimension,
        )
        self.graph = GraphRuntime(
            self.store,
            self.embedder,
            growth_overlap_threshold=growth_overlap_threshold,
            growth_promotion_count=growth_promotion_count,
            growth_preference_tolerance=growth_preference_tolerance,
        )
        self.surface = SemanticSurface(self.store)
        self.retrieval = RetrievalEngine(
            self.store,
            self.graph,
            self.surface,
            direct_top_k=direct_top_k,
            direct_similarity_floor=direct_similarity_floor,
            base_context_chars=base_context_chars,
            maximum_context_chars=maximum_context_chars,
        )
        self.working_memory = WorkingMemory(maximum_records=working_memory_records)
        self.pulse = int(self.store.get_metadata("pulse_counter", "0") or 0)
        self._backfill_lower_memory()

    def __enter__(self) -> "BaseAgenticMemoryRAG":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.store.close()

    def _backfill_lower_memory(self) -> None:
        if int(self.store.get_metadata("lower_memory_schema_version", "0") or 0) >= 1:
            return
        for record in self.store.list_records():
            if record.record_type == RecordType.OUTBOUND_MESSAGE:
                continue
            if self.store.has_record_projections(record.record_id):
                continue
            if record.record_type == RecordType.NOTIFICATION:
                trunk = InputTrunk.NOTICE
            elif record.record_type in {
                RecordType.OBSERVATION,
                RecordType.TOOL_RESULT,
                RecordType.RECEIPT,
            }:
                trunk = InputTrunk.SEE
            else:
                trunk = InputTrunk.HEAR
            self.graph.deposit_experience(record, input_trunk=trunk, pulse=self.pulse)
        self.store.set_metadata("lower_memory_schema_version", "1")

    def _next_pulse(self) -> tuple[int, str]:
        self.pulse += 1
        self.store.set_metadata("pulse_counter", str(self.pulse))
        return self.pulse, f"pulse:{self.pulse}"

    @staticmethod
    def _record_type(kind: EventKind) -> RecordType:
        return {
            EventKind.MESSAGE: RecordType.INBOUND_MESSAGE,
            EventKind.OBSERVATION: RecordType.OBSERVATION,
            EventKind.NOTIFICATION: RecordType.NOTIFICATION,
        }[kind]

    @staticmethod
    def _input_trunks(values: Sequence[str | InputTrunk]) -> tuple[InputTrunk, ...]:
        return tuple(value if isinstance(value, InputTrunk) else InputTrunk(value) for value in values)

    @staticmethod
    def _output_trunks(values: Sequence[str | OutputTrunk]) -> tuple[OutputTrunk, ...]:
        return tuple(value if isinstance(value, OutputTrunk) else OutputTrunk(value) for value in values)

    # ---------------------------------------------------------- public topology

    def add_concept(
        self,
        concept_id: str,
        label: str,
        *,
        terms: Sequence[str] = (),
        input_trunks: Sequence[str | InputTrunk] = (),
        output_trunks: Sequence[str | OutputTrunk] = (),
        evidence_record_ids: Sequence[str] = (),
    ):
        return self.graph.add_concept(
            concept_id,
            label,
            terms=terms,
            input_trunks=self._input_trunks(input_trunks),
            output_trunks=self._output_trunks(output_trunks),
            pulse=self.pulse,
            evidence_record_ids=evidence_record_ids,
        )

    def add_relation(
        self,
        source_concept_id: str,
        target_concept_id: str,
        *,
        side: GraphSide | str = GraphSide.INPUT,
        delta_y: float = 1.0,
        evidence_record_ids: Sequence[str] = (),
    ):
        resolved_side = side if isinstance(side, GraphSide) else GraphSide(side)
        return self.graph.add_relation(
            source_concept_id,
            target_concept_id,
            side=resolved_side,
            delta_y=delta_y,
            pulse=self.pulse,
            evidence_record_ids=evidence_record_ids,
        )

    def set_core_record_ids(self, record_ids: Sequence[str]) -> None:
        """Pin a very small identity/continuity set into every recall context."""
        unique = list(dict.fromkeys(record_ids))
        missing = [record_id for record_id in unique if self.store.get_record(record_id) is None]
        if missing:
            raise KeyError(f"unknown core records: {', '.join(missing)}")
        self.store.set_metadata("core_record_ids", json.dumps(unique))

    def core_record_ids(self) -> tuple[str, ...]:
        encoded = self.store.get_metadata("core_record_ids", "[]") or "[]"
        try:
            values = json.loads(encoded)
        except json.JSONDecodeError:
            values = []
        return tuple(str(value) for value in values)

    def experience_state(self, experience_id: str) -> ExperienceState | None:
        return self.store.get_experience_state(experience_id)

    def experience_projections(self, experience_id: str) -> tuple[ExperienceProjection, ...]:
        return tuple(self.store.projections_for_experience(experience_id))

    def lower_vault_stats(self, node_id: str) -> Mapping[str, float | int]:
        return self.store.lower_vault_stats(node_id)

    def overlap_clusters(self, parent_node_id: str) -> tuple[OverlapCluster, ...]:
        return tuple(self.store.list_overlap_clusters(parent_node_id))

    # -------------------------------------------------------------- persistence

    def remember(
        self,
        text: str,
        *,
        kind: EventKind | str = EventKind.MESSAGE,
        source_id: str = "human",
        timestamp: str | None = None,
        event_id: str | None = None,
        record_id: str | None = None,
        correlation_id: str | None = None,
        record_type: RecordType | str | None = None,
        concept_ids: Sequence[str] = (),
        provenance: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        supersedes_id: str | None = None,
        allow_growth: bool = True,
    ) -> MemoryRecord:
        pulse_number, _ = self._next_pulse()
        resolved_kind = kind if isinstance(kind, EventKind) else EventKind(kind)
        resolved_record_type = (
            record_type
            if isinstance(record_type, RecordType)
            else RecordType(record_type)
            if record_type is not None
            else self._record_type(resolved_kind)
        )
        timestamp = timestamp or utc_now()
        event_id = event_id or f"event:{uuid.uuid4().hex}"
        record_id = record_id or f"record:{uuid.uuid4().hex}"
        vector = self.embedder.embed(text)
        record = MemoryRecord(
            record_id=record_id,
            event_id=event_id,
            record_type=resolved_record_type,
            source_id=source_id,
            timestamp=timestamp,
            text=text,
            embedding=as_tuple(vector),
            provenance=dict(provenance or {}),
            metadata=dict(metadata or {}),
            supersedes_id=supersedes_id,
        )
        self.store.add_record(record)
        assigned = []
        for concept_id in concept_ids:
            concept = self.store.get_concept(concept_id)
            if concept is None:
                raise KeyError(f"unknown concept: {concept_id}")
            if concept.vault_id:
                self.store.add_to_vault(concept.vault_id, record.record_id, concept_id)
                assigned.append(concept_id)

        envelope = EventEnvelope(
            event_id=event_id,
            kind=resolved_kind,
            source_id=source_id,
            timestamp=timestamp,
            content=text,
            correlation_id=correlation_id,
            provenance=dict(provenance or {}),
            metadata=dict(metadata or {}),
        )
        trunk = self.graph.route_event(envelope)
        preference_node_id = None
        if resolved_record_type != RecordType.OUTBOUND_MESSAGE:
            preference_node_id = self.graph.deposit_experience(
                record,
                input_trunk=trunk,
                pulse=pulse_number,
            )
        if (
            not assigned
            and allow_growth
            and resolved_record_type != RecordType.OUTBOUND_MESSAGE
        ):
            candidates = self.surface.project(
                text,
                vector,
                side=GraphSide.INPUT,
                event_kind=resolved_kind,
            )
            reachable = []
            for candidate in candidates:
                trace = self.graph.traverse(
                    pulse_id=f"ingest:{pulse_number}",
                    side=GraphSide.INPUT,
                    target_id=candidate.concept_id,
                    endpoint_score=candidate.joint_score,
                    required_input_trunk=trunk,
                    mark_active=False,
                )
                if trace is not None and candidate.joint_score >= 0.18:
                    reachable.append((candidate.concept_id, trace))
            for concept_id, trace in reachable[:2]:
                concept = self.store.get_concept(concept_id)
                if concept and concept.vault_id:
                    self.store.add_to_vault(concept.vault_id, record.record_id, concept_id)
                    self.graph.deposit_trace(record, trace, pulse=pulse_number)
                    assigned.append(concept_id)
            if not assigned:
                self.graph.stage_growth(
                    record,
                    input_trunk=trunk,
                    pulse=pulse_number,
                    parent_node_id=preference_node_id,
                )
        return record

    # ---------------------------------------------------------------- retrieval

    def recall(
        self,
        query: str,
        *,
        kind: EventKind | str = EventKind.MESSAGE,
        source_id: str = "human",
        correlation_id: str | None = None,
        exclude_record_ids: Iterable[str] = (),
        include_current_input: bool = True,
    ) -> RecallResult:
        pulse_number, pulse_id = self._next_pulse()
        resolved_kind = kind if isinstance(kind, EventKind) else EventKind(kind)
        envelope = EventEnvelope(
            event_id=f"query:{uuid.uuid4().hex}",
            kind=resolved_kind,
            source_id=source_id,
            timestamp=utc_now(),
            content=query,
            correlation_id=correlation_id,
        )
        trunk = self.graph.route_event(envelope)
        packet, hits = self.retrieval.retrieve(
            pulse_id=pulse_id,
            query=query,
            query_embedding=self.embedder.embed(query),
            event_kind=resolved_kind,
            trunk=trunk,
            exclude_record_ids=exclude_record_ids,
        )
        retained_ids = self.working_memory.advance(pulse_number, packet.selected_record_ids)
        retained_records = self.store.get_records(retained_ids)
        core_record_ids = self.core_record_ids()
        existing = {hit.record.record_id for hit in hits}
        context_records = [hit.record for hit in hits]
        for record in self.store.get_records(core_record_ids):
            if record.record_id not in existing:
                context_records.append(record)
                existing.add(record.record_id)
        context_records.extend(
            record for record in retained_records if record.record_id not in existing
        )
        bundle = render_context(
            context_records,
            retained_record_ids=retained_ids,
            current_input=query,
            source_id=source_id,
            maximum_chars=packet.context_budget_chars,
            include_current_input=include_current_input,
            protected_record_ids=(*packet.direct_record_ids, *core_record_ids),
        )
        packet = replace(
            packet,
            retained_record_ids=tuple(
                record_id for record_id in retained_ids if record_id in bundle.record_ids
            ),
            selected_record_ids=bundle.record_ids,
        )
        return RecallResult(packet, tuple(hits), bundle)

    # ---------------------------------------------------------- output traversal

    @staticmethod
    def _trunk_from_trace(trace: TraversalTrace) -> OutputTrunk | None:
        if len(trace.path_node_ids) < 2:
            return None
        first = trace.path_node_ids[1]
        for trunk, node_id in OUTPUT_NODE_IDS.items():
            if node_id == first:
                return trunk
        return None

    def classify_output(
        self,
        text: str,
        *,
        private: bool = False,
        effect_hint: OutputTrunk | str | None = None,
    ) -> OutputDecision:
        pulse_number, pulse_id = self._next_pulse()
        if private:
            return OutputDecision(pulse_id, None, 1.0, None, private=True)
        hint = (
            effect_hint
            if isinstance(effect_hint, OutputTrunk)
            else OutputTrunk(effect_hint)
            if effect_hint is not None
            else None
        )
        if hint is not None:
            trace = self.graph.traverse(
                pulse_id=pulse_id,
                side=GraphSide.OUTPUT,
                target_id=OUTPUT_NODE_IDS[hint],
                endpoint_score=1.0,
                mark_active=True,
            )
            return OutputDecision(pulse_id, hint, 1.0, trace)

        vector = self.embedder.embed(text)
        candidates = self.surface.project(
            text,
            vector,
            side=GraphSide.OUTPUT,
            event_kind=None,
        )
        if candidates:
            # X fixes the intended semantic endpoint. Y may choose only the
            # least-resistant route to that endpoint; an easier route to a
            # different action concept must not replace the intended effect.
            candidate = candidates[0]
            trace = self.graph.traverse(
                pulse_id=pulse_id,
                side=GraphSide.OUTPUT,
                target_id=candidate.concept_id,
                endpoint_score=candidate.joint_score,
                mark_active=False,
            )
            if trace is not None:
                trunk = self._trunk_from_trace(trace)
                if trunk is not None:
                    self.graph.activate_trace(pulse_id, trace)
                    return OutputDecision(
                        pulse_id,
                        trunk,
                        min(1.0, candidate.joint_score),
                        trace,
                    )

        # Basal fallback classifies against seeded trunk prototypes.
        scores = {
            trunk: max(
                0.0,
                cosine_similarity(vector, self.store.get_concept(node_id).embedding),
            )
            for trunk, node_id in OUTPUT_NODE_IDS.items()
            if self.store.get_concept(node_id) is not None
        }
        if not scores:
            return OutputDecision(pulse_id, None, 0.0, None)
        trunk, score = max(scores.items(), key=lambda item: (item[1], item[0].value))
        if score < 0.05:
            return OutputDecision(pulse_id, None, score, None)
        trace = self.graph.traverse(
            pulse_id=pulse_id,
            side=GraphSide.OUTPUT,
            target_id=OUTPUT_NODE_IDS[trunk],
            endpoint_score=score,
            mark_active=True,
        )
        return OutputDecision(pulse_id, trunk, score, trace)

    def record_outcome(
        self,
        decision: OutputDecision,
        *,
        stability_delta: float,
        verified: bool,
        proposal_id: str | None = None,
        receipt_id: str | None = None,
        evidence_quality: float = 1.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> OutcomePacket:
        if verified and decision.trunk is not None and not receipt_id:
            raise ValueError("verified external outcomes require a receipt ID")
        edge_ids = decision.trace.path_edge_ids if decision.trace else ()
        outcome = OutcomePacket(
            outcome_id=f"outcome:{uuid.uuid4().hex}",
            pulse_id=decision.pulse_id,
            output_trunk=decision.trunk,
            credited_edge_ids=edge_ids,
            verified=verified,
            stability_delta=float(stability_delta),
            proposal_id=proposal_id,
            receipt_id=receipt_id,
            metadata=dict(metadata or {}),
        )
        self.store.save_outcome(outcome)
        self.graph.reinforce_edges(
            edge_ids,
            stability_delta=stability_delta,
            verified=verified,
            evidence_quality=evidence_quality,
        )
        return outcome


HabitusAI = BaseAgenticMemoryRAG
HabitusMemory = BaseAgenticMemoryRAG
