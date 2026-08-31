from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


class GraphSide(str, enum.Enum):
    INPUT = "input"
    OUTPUT = "output"


class EventKind(str, enum.Enum):
    MESSAGE = "message"
    OBSERVATION = "observation"
    NOTIFICATION = "notification"


class InputTrunk(str, enum.Enum):
    HEAR = "HEAR"
    SEE = "SEE"
    NOTICE = "NOTICE"


class OutputTrunk(str, enum.Enum):
    SPEAK = "SPEAK"
    LOOK = "LOOK"
    DO = "DO"


class RecordType(str, enum.Enum):
    RAW_MEMORY = "raw_memory"
    INBOUND_MESSAGE = "inbound_message"
    OUTBOUND_MESSAGE = "outbound_message"
    OBSERVATION = "observation"
    NOTIFICATION = "notification"
    FACT = "fact"
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RECEIPT = "receipt"


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    kind: EventKind
    source_id: str
    timestamp: str
    content: str
    correlation_id: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    event_id: str | None
    record_type: RecordType
    source_id: str
    timestamp: str
    text: str
    embedding: tuple[float, ...]
    provenance: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    supersedes_id: str | None = None


@dataclass(frozen=True)
class ConceptNode:
    concept_id: str
    label: str
    kind: str
    embedding: tuple[float, ...]
    terms: tuple[str, ...]
    vault_id: str | None
    created_pulse: int
    last_active_pulse: int


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    side: GraphSide
    source_id: str
    target_id: str
    delta_y: float
    log_strength: float
    conflict_penalty: float
    last_active_time: float | None
    created_pulse: int
    archived: bool = False


@dataclass(frozen=True)
class ExperienceProjection:
    experience_id: str
    record_id: str
    node_id: str
    layer: int
    side: GraphSide
    activation: float
    preference: float
    confidence: float
    pulse: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperienceState:
    experience_id: str
    preference_mean: float
    preference_weight: float
    observation_count: int
    last_pulse: int


@dataclass(frozen=True)
class ExperienceCycle:
    """One self-originating output and the consequences observed after it."""

    cycle_id: str
    output_record_id: str
    output_pulse_id: str
    output_trunk: OutputTrunk
    credited_edge_ids: tuple[str, ...]
    opened_pulse: int
    status: str = "open"
    terminal_return_record_id: str | None = None
    closed_pulse: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperienceReturn:
    """An observed consequence causally attached to an output cycle."""

    cycle_id: str
    record_id: str
    input_trunk: InputTrunk
    status: str
    stability_delta: float
    verified: bool
    terminal: bool
    pulse: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OverlapCluster:
    cluster_id: str
    parent_node_id: str
    centroid: tuple[float, ...]
    record_ids: tuple[str, ...]
    experience_ids: tuple[str, ...]
    preference_mean: float
    confidence_mean: float
    first_pulse: int
    last_pulse: int
    child_node_id: str | None = None
    semantic_node_id: str | None = None


@dataclass(frozen=True)
class SurfaceCandidate:
    concept_id: str
    semantic_score: float
    lexical_score: float
    joint_score: float


@dataclass(frozen=True)
class TraversalTrace:
    trace_id: str
    side: GraphSide
    start_node_id: str
    target_node_id: str
    path_node_ids: tuple[str, ...]
    path_edge_ids: tuple[str, ...]
    total_travel_time: float
    endpoint_score: float
    evidence_record_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalHit:
    record: MemoryRecord
    lane: str
    dense_score: float
    lexical_score: float
    vault_id: str | None = None
    path_score: float = 0.0


@dataclass(frozen=True)
class RetrievalPacket:
    pulse_id: str
    input_trunk: InputTrunk
    surface_candidates: tuple[SurfaceCandidate, ...]
    y_paths: tuple[TraversalTrace, ...]
    direct_record_ids: tuple[str, ...]
    lexical_record_ids: tuple[str, ...]
    vault_record_ids: tuple[str, ...]
    selected_record_ids: tuple[str, ...]
    retained_record_ids: tuple[str, ...]
    contradictions: tuple[tuple[str, str], ...]
    context_budget_chars: int
    trace_hash: str


@dataclass(frozen=True)
class OutputDecision:
    pulse_id: str
    trunk: OutputTrunk | None
    confidence: float
    trace: TraversalTrace | None
    private: bool = False


@dataclass(frozen=True)
class OutcomePacket:
    outcome_id: str
    pulse_id: str
    output_trunk: OutputTrunk | None
    credited_edge_ids: tuple[str, ...]
    verified: bool
    stability_delta: float | None
    proposal_id: str | None = None
    receipt_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CycleReturnResult:
    cycle: ExperienceCycle
    observed_return: ExperienceReturn
    record: MemoryRecord
    outcome: OutcomePacket


@dataclass(frozen=True)
class ContextBundle:
    text: str
    record_ids: tuple[str, ...]
    omitted_record_ids: tuple[str, ...]
    char_count: int


def as_tuple(values: Sequence[float]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)
