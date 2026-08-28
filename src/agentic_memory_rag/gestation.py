from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Mapping

from .graph import OUTPUT_NODE_IDS
from .pipeline import BaseAgenticMemoryRAG, utc_now
from .types import GraphSide, MemoryRecord, OutputTrunk, RecordType


GESTATION_VERSION = 1
PROFILE_METADATA_KEY = "gestation_profile"


@dataclass(frozen=True)
class TasteSchema:
    schema_id: str
    label: str
    description: str
    statement: str
    output_biases: Mapping[OutputTrunk, float]
    terms: tuple[str, ...]


TASTE_SCHEMAS: dict[str, TasteSchema] = {
    "balanced": TasteSchema(
        "balanced",
        "Balanced",
        "Begins without favoring speech, investigation, or execution.",
        "I begin open to conversation, investigation, and practical action without strongly favoring one.",
        {},
        ("balance", "open", "adapt", "conversation", "investigation", "action"),
    ),
    "curious": TasteSchema(
        "curious",
        "Curious",
        "Gently favors looking, reading, and asking before acting.",
        "I begin with a gentle preference for exploring, reading, and understanding unfamiliar things.",
        {OutputTrunk.LOOK: 0.16, OutputTrunk.SPEAK: 0.03},
        ("curious", "explore", "read", "understand", "ask", "discover"),
    ),
    "deliberate": TasteSchema(
        "deliberate",
        "Deliberate",
        "Gently favors checking evidence and communicating before mutation.",
        "I begin with a gentle preference for checking evidence and making deliberate changes.",
        {OutputTrunk.LOOK: 0.12, OutputTrunk.SPEAK: 0.04, OutputTrunk.DO: -0.04},
        ("deliberate", "careful", "evidence", "verify", "consider", "change"),
    ),
    "builder": TasteSchema(
        "builder",
        "Builder",
        "Gently favors making and executing after enough inspection.",
        "I begin with a gentle preference for making useful things and learning through practical work.",
        {OutputTrunk.DO: 0.14, OutputTrunk.LOOK: 0.04},
        ("build", "make", "execute", "practical", "work", "learn"),
    ),
}


@dataclass(frozen=True)
class GestationProfile:
    human_name: str
    agent_name: str
    taste_schema: str
    model_backend: str
    model_name: str
    gestation_version: int
    hatched_at: str


def _clean_name(value: str, field: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    if not cleaned:
        raise ValueError(f"{field} cannot be empty")
    if len(cleaned) > 80:
        raise ValueError(f"{field} must be 80 characters or fewer")
    if any(character in cleaned for character in ("\x00", "\r", "\n")):
        raise ValueError(f"{field} contains an invalid character")
    return cleaned


def load_profile(mind: BaseAgenticMemoryRAG) -> GestationProfile | None:
    encoded = mind.store.get_metadata(PROFILE_METADATA_KEY)
    if not encoded:
        return None
    payload = json.loads(encoded)
    return GestationProfile(**payload)


def _ensure_record(
    mind: BaseAgenticMemoryRAG,
    *,
    record_id: str,
    event_id: str,
    text: str,
    concept_id: str,
    metadata: Mapping[str, object],
) -> MemoryRecord:
    existing = mind.store.get_record(record_id)
    if existing is not None:
        if existing.text != text:
            raise ValueError(f"gestation record collision: {record_id}")
        return existing
    return mind.remember(
        text,
        source_id="gestation",
        event_id=event_id,
        record_id=record_id,
        record_type=RecordType.FACT,
        concept_ids=(concept_id,),
        provenance={"origin": "gestation", "version": GESTATION_VERSION},
        metadata=dict(metadata),
        allow_growth=False,
    )


def _attach_edge_evidence(
    mind: BaseAgenticMemoryRAG,
    concept_id: str,
    record_id: str,
) -> None:
    for edge in mind.store.list_edges():
        if edge.target_id == concept_id:
            mind.store.add_edge_evidence(edge.edge_id, record_id, "gestational_seed")


def gestate(
    mind: BaseAgenticMemoryRAG,
    *,
    human_name: str,
    agent_name: str,
    taste_schema: str = "balanced",
    model_backend: str = "ollama",
    model_name: str = "granite4.1:8b",
) -> GestationProfile:
    """Add the smallest viable identity and taste buds to a fresh mind."""
    existing = load_profile(mind)
    if existing is not None:
        raise ValueError(
            f"this mind already hatched as {existing.agent_name}; gestation is not repeatable"
        )
    human = _clean_name(human_name, "human name")
    agent = _clean_name(agent_name, "agent name")
    schema_key = str(taste_schema).strip().casefold()
    if schema_key not in TASTE_SCHEMAS:
        raise ValueError(
            f"unknown taste schema {taste_schema!r}; choose from {', '.join(TASTE_SCHEMAS)}"
        )
    schema = TASTE_SCHEMAS[schema_key]
    backend = str(model_backend).strip().casefold() or "ollama"
    model = str(model_name).strip()
    if not model:
        raise ValueError("model name cannot be empty")

    mind.add_concept(
        "identity:self",
        agent,
        terms=(agent, "self", "identity", "own name"),
        input_trunks=("HEAR", "NOTICE"),
        output_trunks=("SPEAK",),
    )
    mind.add_concept(
        "identity:human",
        human,
        terms=(human, "human", "conversation partner", "familiar person"),
        input_trunks=("HEAR",),
        output_trunks=("SPEAK",),
    )
    taste_concept_id = f"taste:{schema.schema_id}"
    taste_outputs = tuple(
        trunk.value for trunk, value in schema.output_biases.items() if value >= 0.0
    ) or ("SPEAK", "LOOK", "DO")
    mind.add_concept(
        taste_concept_id,
        schema.label,
        terms=schema.terms,
        input_trunks=("HEAR", "SEE", "NOTICE"),
        output_trunks=taste_outputs,
    )

    self_record = _ensure_record(
        mind,
        record_id="gestation:self-identity",
        event_id="gestation:event:self-identity",
        text=f"My name is {agent}.",
        concept_id="identity:self",
        metadata={"fact_key": "self_name", "fact_value": agent, "core": True},
    )
    human_record = _ensure_record(
        mind,
        record_id="gestation:human-identity",
        event_id="gestation:event:human-identity",
        text=f"{human} is the person I am growing alongside.",
        concept_id="identity:human",
        metadata={"fact_key": "human_name", "fact_value": human, "core": True},
    )
    taste_record = _ensure_record(
        mind,
        record_id=f"gestation:taste:{schema.schema_id}",
        event_id=f"gestation:event:taste:{schema.schema_id}",
        text=schema.statement,
        concept_id=taste_concept_id,
        metadata={"taste_schema": schema.schema_id, "genetic_prior": True},
    )
    mind.set_core_record_ids((self_record.record_id, human_record.record_id))

    mind.add_relation(
        "identity:human",
        "identity:self",
        side=GraphSide.INPUT,
        evidence_record_ids=(self_record.record_id, human_record.record_id),
    )
    mind.add_relation(
        "identity:self",
        "identity:human",
        side=GraphSide.OUTPUT,
        evidence_record_ids=(self_record.record_id, human_record.record_id),
    )
    for concept_id, record in (
        ("identity:self", self_record),
        ("identity:human", human_record),
        (taste_concept_id, taste_record),
    ):
        _attach_edge_evidence(mind, concept_id, record.record_id)

    for trunk, bias in schema.output_biases.items():
        edge = mind.store.find_edge(GraphSide.OUTPUT, "SELF", OUTPUT_NODE_IDS[trunk])
        if edge is not None and bias:
            mind.store.update_edge_state(edge.edge_id, log_strength=edge.log_strength + bias)

    profile = GestationProfile(
        human_name=human,
        agent_name=agent,
        taste_schema=schema.schema_id,
        model_backend=backend,
        model_name=model,
        gestation_version=GESTATION_VERSION,
        hatched_at=utc_now(),
    )
    mind.store.set_metadata(PROFILE_METADATA_KEY, json.dumps(asdict(profile), sort_keys=True))
    mind.store.set_metadata("gestation_status", "hatched")
    return profile
