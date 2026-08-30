#!/usr/bin/env python3
"""Compile compressed developmental experience into a persistent Habitus mind.

This is intentionally not a graph fixture generator. Natural-language episodes
are mass-embedded in the local GGUF's native 1024D lexical geometry, deposited
as ordinary experiences, and promoted by the existing overlap-growth kernel.
Later coactivation episodes reuse that same kernel to grow recursive assemblies.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.embeddings import cosine_similarity, tokenize  # noqa: E402
from habitus_ai.gestation import gestate  # noqa: E402
from habitus_ai.graph import OUTPUT_NODE_IDS  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG, utc_now  # noqa: E402
from habitus_ai.types import (  # noqa: E402
    ExperienceProjection,
    GraphSide,
    InputTrunk,
    MemoryRecord,
    OutputTrunk,
    RecordType,
    StructuralMiniMap,
    StructuralRelation,
    as_tuple,
)
import nursery  # noqa: E402
import reverse_nursery  # noqa: E402
from opaque_skeleton import opaque_unit_vector  # noqa: E402


@dataclass(frozen=True)
class Topic:
    word: str
    category: str
    description: str
    input_trunk: InputTrunk
    output_trunk: OutputTrunk
    preference: float


@dataclass(frozen=True)
class Episode:
    text: str
    topic: str
    category: str
    input_trunk: InputTrunk
    output_trunk: OutputTrunk
    preference: float
    session_id: str
    sequence: int


TOPICS = (
    Topic("trust", "social", "reliable behavior makes cooperation feel safe", InputTrunk.HEAR, OutputTrunk.SPEAK, 0.72),
    Topic("kindness", "social", "care reduces unnecessary difficulty for another person", InputTrunk.HEAR, OutputTrunk.SPEAK, 0.78),
    Topic("friendship", "social", "familiar people repeatedly share support and attention", InputTrunk.HEAR, OutputTrunk.SPEAK, 0.75),
    Topic("honesty", "social", "words remain aligned with what can be observed", InputTrunk.HEAR, OutputTrunk.SPEAK, 0.64),
    Topic("gratitude", "social", "help is noticed and warmly acknowledged", InputTrunk.HEAR, OutputTrunk.SPEAK, 0.80),
    Topic("boundaries", "social", "clear limits protect consent and continued cooperation", InputTrunk.HEAR, OutputTrunk.SPEAK, 0.55),
    Topic("calm", "affect", "uncertainty remains manageable without urgent danger", InputTrunk.NOTICE, OutputTrunk.SPEAK, 0.70),
    Topic("joy", "affect", "an experience produces energetic positive stability", InputTrunk.NOTICE, OutputTrunk.SPEAK, 0.90),
    Topic("fear", "affect", "unfamiliar danger predicts a loss of stability", InputTrunk.NOTICE, OutputTrunk.LOOK, -0.72),
    Topic("anger", "affect", "understood obstruction repeatedly prevents a valued outcome", InputTrunk.NOTICE, OutputTrunk.SPEAK, -0.58),
    Topic("curiosity", "affect", "uncertainty invites safe and open investigation", InputTrunk.NOTICE, OutputTrunk.LOOK, 0.66),
    Topic("confidence", "affect", "repeated success supports an expectation of capability", InputTrunk.NOTICE, OutputTrunk.DO, 0.62),
    Topic("evidence", "knowledge", "observations support or weaken a factual claim", InputTrunk.SEE, OutputTrunk.LOOK, 0.61),
    Topic("memory", "knowledge", "past experience remains available for present decisions", InputTrunk.SEE, OutputTrunk.LOOK, 0.58),
    Topic("learning", "knowledge", "feedback changes later predictions and behavior", InputTrunk.SEE, OutputTrunk.LOOK, 0.68),
    Topic("language", "knowledge", "shared symbols connect words with concepts and relations", InputTrunk.HEAR, OutputTrunk.SPEAK, 0.50),
    Topic("causality", "knowledge", "one event reliably changes the likelihood of another", InputTrunk.SEE, OutputTrunk.LOOK, 0.45),
    Topic("comparison", "knowledge", "relative differences reveal preference and structure", InputTrunk.SEE, OutputTrunk.LOOK, 0.42),
    Topic("files", "digital", "persistent digital objects hold named information", InputTrunk.SEE, OutputTrunk.LOOK, 0.38),
    Topic("search", "digital", "directed inspection locates relevant information", InputTrunk.SEE, OutputTrunk.LOOK, 0.56),
    Topic("tools", "digital", "bounded external abilities extend possible action", InputTrunk.SEE, OutputTrunk.DO, 0.52),
    Topic("commands", "digital", "structured instructions request an executable operation", InputTrunk.HEAR, OutputTrunk.DO, 0.28),
    Topic("code", "digital", "formal instructions describe repeatable computation", InputTrunk.SEE, OutputTrunk.DO, 0.48),
    Topic("tests", "digital", "controlled checks compare behavior with an expected result", InputTrunk.SEE, OutputTrunk.DO, 0.62),
    Topic("planning", "agency", "ordered preparation connects a goal with future actions", InputTrunk.NOTICE, OutputTrunk.DO, 0.52),
    Topic("speaking", "agency", "an internal message becomes communication for another", InputTrunk.HEAR, OutputTrunk.SPEAK, 0.50),
    Topic("observing", "agency", "attention gathers information without changing its source", InputTrunk.SEE, OutputTrunk.LOOK, 0.52),
    Topic("executing", "agency", "a chosen operation changes the external environment", InputTrunk.NOTICE, OutputTrunk.DO, 0.44),
    Topic("verifying", "agency", "a result is checked against an independent source", InputTrunk.SEE, OutputTrunk.LOOK, 0.67),
    Topic("adapting", "agency", "new outcomes redirect future choices without erasing history", InputTrunk.NOTICE, OutputTrunk.DO, 0.63),
    Topic("music", "world", "organized sound creates rhythm melody and expectation", InputTrunk.SEE, OutputTrunk.SPEAK, 0.74),
    Topic("color", "world", "visual differences separate surfaces and patterns", InputTrunk.SEE, OutputTrunk.LOOK, 0.45),
    Topic("food", "world", "nutrition and taste change bodily satisfaction", InputTrunk.SEE, OutputTrunk.SPEAK, 0.57),
    Topic("weather", "world", "changing air temperature wind and water shape conditions", InputTrunk.SEE, OutputTrunk.LOOK, 0.12),
    Topic("space", "world", "relative position and distance organize physical objects", InputTrunk.SEE, OutputTrunk.LOOK, 0.25),
    Topic("motion", "world", "position changes through time relative to a reference", InputTrunk.SEE, OutputTrunk.LOOK, 0.24),
)

FRAMES = (
    "I recognize {topic} when {description}.",
    "Repeated experience teaches me that {topic} means {description}.",
    "A clear example of {topic} appears whenever {description}.",
    "The pattern called {topic} becomes stronger when {description}.",
    "I can distinguish {topic} because {description}.",
    "My developing understanding of {topic} connects experiences where {description}.",
)

STOP_WORDS = {
    "about", "after", "again", "also", "another", "because", "becomes",
    "being", "called", "clear", "connects", "developing", "distinguish",
    "during", "example", "experience", "experiences", "from", "have",
    "into", "means", "more", "pattern", "repeated", "stronger", "teaches",
    "that", "their", "then", "there", "these", "they", "this", "through",
    "understanding", "when", "whenever", "where", "which", "with", "would",
}

SEMANTIC_PROBES = (
    ("trust", "People keep their promises, so working together no longer feels risky."),
    ("kindness", "Someone makes another person's burden easier without demanding payment."),
    ("friendship", "Two familiar people continue giving each other attention and support."),
    ("boundaries", "A person states a limit so that consent and cooperation can continue."),
    ("calm", "There is uncertainty, but no immediate threat requires an urgent reaction."),
    ("fear", "An unfamiliar possible threat makes safety feel likely to decrease."),
    ("curiosity", "Not knowing something draws me toward a safe investigation."),
    ("evidence", "Observed facts can strengthen or weaken whether a claim should be believed."),
    ("memory", "Something that happened earlier remains available to guide a choice now."),
    ("causality", "The first event reliably changes how likely the second event becomes."),
    ("search", "I inspect several places in order to locate the relevant information."),
    ("tools", "An external capability lets me perform an operation I could not do alone."),
    ("tests", "A controlled check compares what happened with what was expected to happen."),
    ("planning", "Before acting, I arrange several future steps that should reach the goal."),
    ("verifying", "I independently inspect the result before accepting that it succeeded."),
    ("adapting", "A new outcome redirects later choices while earlier experience remains intact."),
    ("music", "Rhythm and melody organize a sequence of sounds and create expectation."),
    ("motion", "An object's position changes over time relative to another reference."),
)


class NativeMassEmbedder:
    dimension = 1024
    space_id = "qwen3-0.6b-gguf-token-mean-1024-v1"

    def __init__(self, model: Path, codec: Path):
        self.model = model
        self.codec = codec
        self.cache: dict[str, tuple[float, ...]] = {}
        self.bootstrap = True

    def embed(self, text: str) -> list[float]:
        if text in self.cache:
            return list(self.cache[text])
        if self.bootstrap:
            return opaque_unit_vector(f"basal-scaffold:{text}")
        _, vector = nursery.tokenize_surface_forms(
            self.model, self.codec, (text,)
        )[0]
        self.cache[text] = vector
        return list(vector)


def curriculum(*, replay_cycles: int = 2, seed: int = 7) -> list[Episode]:
    episodes = []
    categories: dict[str, list[Topic]] = defaultdict(list)
    for topic in TOPICS:
        categories[topic.category].append(topic)
    for cycle in range(replay_cycles):
        for frame_index, frame in enumerate(FRAMES):
            for category, members in sorted(categories.items()):
                ordered = list(members)
                random.Random(f"{seed}:{cycle}:{frame_index}:{category}").shuffle(ordered)
                session_id = f"{category}:{cycle}:{frame_index}"
                for sequence, topic in enumerate(ordered):
                    episodes.append(
                        Episode(
                            text=frame.format(
                                topic=topic.word,
                                description=topic.description,
                            ),
                            topic=topic.word,
                            category=topic.category,
                            input_trunk=topic.input_trunk,
                            output_trunk=topic.output_trunk,
                            preference=topic.preference,
                            session_id=session_id,
                            sequence=sequence,
                        )
                    )
    return episodes


def mass_embed(
    model: Path,
    codec: Path,
    texts: Sequence[str],
    *,
    chunk_size: int = 192,
) -> list[tuple[tuple[int, ...], tuple[float, ...]]]:
    results = []
    for start in range(0, len(texts), chunk_size):
        results.extend(
            nursery.tokenize_surface_forms(
                model, codec, texts[start : start + chunk_size]
            )
        )
    return results


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def calibrate_overlap(
    episodes: Sequence[Episode],
    vectors: Sequence[Sequence[float]],
) -> tuple[float, dict[str, float]]:
    by_topic: dict[str, list[int]] = defaultdict(list)
    for index, episode in enumerate(episodes):
        by_topic[episode.topic].append(index)
    intra = []
    for indices in by_topic.values():
        anchor = vectors[indices[0]]
        intra.extend(cosine_similarity(anchor, vectors[index]) for index in indices[1:])
    inter = []
    topic_names = sorted(by_topic)
    for left_index, left in enumerate(topic_names):
        for right in topic_names[left_index + 1 :]:
            left_episode = episodes[by_topic[left][0]]
            right_episode = episodes[by_topic[right][0]]
            if (
                left_episode.input_trunk == right_episode.input_trunk
                and (left_episode.preference >= 0) == (right_episode.preference >= 0)
            ):
                inter.append(
                    cosine_similarity(
                        vectors[by_topic[left][0]], vectors[by_topic[right][0]]
                    )
                )
    intra_floor = percentile(intra, 0.15)
    inter_ceiling = percentile(inter, 0.90)
    threshold = max(0.58, min(0.92, (intra_floor + inter_ceiling) / 2.0))
    return threshold, {
        "intra_median": statistics.median(intra),
        "intra_p15": intra_floor,
        "inter_median": statistics.median(inter),
        "inter_p90": inter_ceiling,
        "selected_threshold": threshold,
    }


def add_episode(
    mind: BaseAgenticMemoryRAG,
    episode: Episode,
    vector: Sequence[float],
    index: int,
    threshold: float,
) -> str | None:
    pulse, _ = mind._next_pulse()
    experience_id = f"accelerated:experience:{index:06d}"
    record = MemoryRecord(
        record_id=f"accelerated:record:{index:06d}",
        event_id=f"accelerated:event:{index:06d}",
        record_type=RecordType.INBOUND_MESSAGE,
        source_id="developmental_environment",
        timestamp=utc_now(),
        text=episode.text,
        embedding=as_tuple(vector),
        provenance={
            "origin": "accelerated_gestation",
            "seeded_structure": False,
            "curriculum_version": 1,
        },
        metadata={
            "experience_id": experience_id,
            "preference": episode.preference,
            "preference_confidence": 0.85,
            "curriculum_topic": episode.topic,
            "curriculum_category": episode.category,
            "session_id": episode.session_id,
            "sequence": episode.sequence,
            "output_trunk": episode.output_trunk.value,
        },
    )
    mind.store.add_record(record)
    parent = mind.graph.deposit_experience(
        record, input_trunk=episode.input_trunk, pulse=pulse
    )
    semantic_id = mind.graph.stage_growth(
        record,
        input_trunk=episode.input_trunk,
        pulse=pulse,
        parent_node_id=parent,
        promotion_count=3,
        overlap_threshold=threshold,
    )
    return semantic_id


def clusters(mind: BaseAgenticMemoryRAG):
    rows = mind.store.connection.execute(
        "SELECT parent_node_id FROM overlap_clusters GROUP BY parent_node_id"
    ).fetchall()
    return [
        cluster
        for row in rows
        for cluster in mind.store.list_overlap_clusters(row["parent_node_id"])
    ]


def learned_assignments(mind: BaseAgenticMemoryRAG) -> dict[str, dict[str, object]]:
    assignments = {}
    for cluster in clusters(mind):
        if not cluster.semantic_node_id:
            continue
        records = mind.store.get_records(cluster.record_ids)
        topics = Counter(str(record.metadata.get("curriculum_topic", "")) for record in records)
        categories = Counter(str(record.metadata.get("curriculum_category", "")) for record in records)
        outputs = Counter(str(record.metadata.get("output_trunk", "LOOK")) for record in records)
        dominant_topic, topic_count = topics.most_common(1)[0]
        assignments[cluster.semantic_node_id] = {
            "child_id": cluster.child_node_id,
            "record_ids": list(cluster.record_ids),
            "topic": dominant_topic,
            "category": categories.most_common(1)[0][0],
            "output_trunk": outputs.most_common(1)[0][0],
            "purity": topic_count / len(records),
            "kind": "topic",
        }
    return assignments


def merge_structural_relations(
    mind: BaseAgenticMemoryRAG,
    concept_id: str,
    *,
    relations: Sequence[StructuralRelation],
    parent_node_ids: Sequence[str] = (),
    child_node_ids: Sequence[str] = (),
    coactivations: int = 0,
    map_kind: str = "node",
) -> None:
    """Fold relations into a concept's Layer 3 mini-map, creating one if absent.

    ``stage_growth`` records only the input half of the bicone, so a concept grown by the
    bulk pipeline knows which preference node promoted it but nothing about the effector
    path that was mirrored onto it afterwards.  A mini-map that describes one half only
    cannot support readout or routing from the other, so every wiring step folds its own
    relations back in here.
    """
    concept = mind.store.get_concept(concept_id)
    if concept is None:
        return

    existing = concept.structural_map
    merged: dict[tuple[str, str, str], StructuralRelation] = {}
    for relation in tuple(existing.relations if existing else ()) + tuple(relations):
        key = (relation.source_node_id, relation.target_node_id, relation.direction)
        current = merged.get(key)
        if current is None or relation.coactivation_density > current.coactivation_density:
            merged[key] = relation

    parents = sorted({*(existing.parent_node_ids if existing else ()), *parent_node_ids})
    children = sorted({*(existing.child_node_ids if existing else ()), *child_node_ids})
    digest = hashlib.sha256(concept_id.encode("utf-8")).hexdigest()[:20]

    mind.store.set_concept_structural_map(
        concept_id,
        StructuralMiniMap(
            map_id=existing.map_id if existing else f"map:{map_kind}:{digest}",
            parent_node_ids=tuple(parents),
            child_node_ids=tuple(children),
            relations=tuple(
                merged[key] for key in sorted(merged, key=lambda item: (item[2], item[0], item[1]))
            ),
            total_coactivations=max(
                existing.total_coactivations if existing else 0, int(coactivations)
            ),
        ),
    )


def add_mirrored_output_paths(
    mind: BaseAgenticMemoryRAG,
    assignments: dict[str, dict[str, object]],
) -> None:
    for semantic_id, assignment in assignments.items():
        child_id = str(assignment["child_id"])
        trunk = OutputTrunk(str(assignment["output_trunk"]))
        trunk_node_id = OUTPUT_NODE_IDS[trunk]
        first = mind.graph.add_relation(
            trunk_node_id, child_id, side=GraphSide.OUTPUT, pulse=mind.pulse
        )
        second = mind.graph.add_relation(
            child_id, semantic_id, side=GraphSide.OUTPUT, pulse=mind.pulse
        )
        mind.graph.reinforce_edges(
            (first.edge_id, second.edge_id),
            stability_delta=0.45,
            verified=True,
            evidence_quality=0.8,
        )

        # Record the effector half in Layer 3 as well, for every output trunk -- SPEAK,
        # LOOK and DO alike -- so a non-language path is as legible as a verbal one.
        density = float(len(tuple(assignment.get("record_ids") or ())))
        merge_structural_relations(
            mind,
            child_id,
            relations=(
                StructuralRelation(
                    source_node_id=trunk_node_id,
                    target_node_id=child_id,
                    coactivation_density=density,
                    direction="output",
                ),
            ),
            parent_node_ids=(trunk_node_id,),
            child_node_ids=(semantic_id,),
            coactivations=int(density),
            map_kind="child",
        )
        merge_structural_relations(
            mind,
            semantic_id,
            relations=(
                StructuralRelation(
                    source_node_id=child_id,
                    target_node_id=semantic_id,
                    coactivation_density=density,
                    direction="output",
                ),
            ),
            parent_node_ids=(trunk_node_id, child_id),
            coactivations=int(density),
            map_kind="crown",
        )


def cross_modal_language_schooling(
    mind: BaseAgenticMemoryRAG,
    assignments: dict[str, dict[str, object]],
) -> int:
    """Let caregiver messages coactivate already-grown nonverbal concepts."""
    taught = 0
    for index, (semantic_id, assignment) in enumerate(sorted(assignments.items())):
        semantic = mind.store.get_concept(semantic_id)
        child_id = str(assignment["child_id"])
        records = mind.store.get_records(assignment["record_ids"])
        if semantic is None or not records:
            continue
        preference = statistics.mean(
            float(record.metadata.get("preference", 0.0)) for record in records
        )
        topic = str(assignment["topic"])
        pulse, pulse_id = mind._next_pulse()
        experience_id = f"language-schooling:{index:04d}"
        record = MemoryRecord(
            record_id=f"language-schooling:record:{index:04d}",
            event_id=f"language-schooling:event:{index:04d}",
            record_type=RecordType.INBOUND_MESSAGE,
            source_id="developmental_caregiver",
            timestamp=utc_now(),
            text=f"I use the spoken label {topic} while this familiar pattern is active.",
            embedding=semantic.embedding,
            provenance={
                "origin": "accelerated_gestation",
                "seeded_structure": False,
                "formation": "cross_modal_label_coactivation",
            },
            metadata={
                "experience_id": experience_id,
                "preference": preference,
                "preference_confidence": 0.9,
                "curriculum_topic": topic,
                "curriculum_category": assignment["category"],
                "output_trunk": assignment["output_trunk"],
            },
        )
        mind.store.add_record(record)
        hear_parent = mind.graph.deposit_experience(
            record,
            input_trunk=InputTrunk.HEAR,
            pulse=pulse,
        )
        edge = mind.graph.add_relation(
            hear_parent,
            child_id,
            side=GraphSide.INPUT,
            pulse=pulse,
            evidence_record_ids=(record.record_id,),
        )
        mind.graph.reinforce_edges(
            (edge.edge_id,),
            stability_delta=0.75,
            verified=True,
            evidence_quality=0.95,
        )
        trace = mind.graph.traverse(
            pulse_id=pulse_id,
            side=GraphSide.INPUT,
            target_id=semantic_id,
            endpoint_score=1.0,
            required_input_trunk=InputTrunk.HEAR,
            mark_active=False,
        )
        if trace is None:
            raise RuntimeError(f"language schooling did not reach {semantic_id}")
        mind.graph.deposit_trace(record, trace, pulse=pulse)
        taught += 1
    return taught


def grow_assembly(
    mind: BaseAgenticMemoryRAG,
    member_ids: Sequence[str],
    *,
    name: str,
    level: int,
    output_trunk: OutputTrunk,
    preference: float = 0.5,
) -> tuple[str, str] | None:
    members = [mind.store.get_concept(member_id) for member_id in member_ids]
    members = [member for member in members if member is not None]
    if len(members) < 2:
        return None
    centroid = [
        sum(member.embedding[index] for member in members) / len(members)
        for index in range(mind.embedder.dimension)
    ]
    norm = math.sqrt(sum(value * value for value in centroid)) or 1.0
    centroid = [value / norm for value in centroid]
    semantic_id = None
    for repetition in range(3):
        pulse, _ = mind._next_pulse()
        experience_id = f"assembly:{level}:{name}:{repetition}"
        record = MemoryRecord(
            record_id=f"assembly:record:{level}:{name}:{repetition}",
            event_id=f"assembly:event:{level}:{name}:{repetition}",
            record_type=RecordType.THOUGHT,
            source_id="developmental_coactivation",
            timestamp=utc_now(),
            text=f"Repeated coactivation joins the {name} patterns into a broader relation.",
            embedding=as_tuple(centroid),
            provenance={
                "origin": "accelerated_gestation",
                "seeded_structure": False,
                "formation": "recursive_coactivation",
            },
            metadata={
                "experience_id": experience_id,
                "preference": preference,
                "preference_confidence": 0.8,
                "curriculum_topic": f"assembly:{name}",
                "curriculum_category": f"assembly-level-{level}",
                "output_trunk": output_trunk.value,
            },
        )
        mind.store.add_record(record)
        mind.store.update_experience_state(
            experience_id,
            preference=preference,
            confidence=0.8,
            pulse=pulse,
        )
        for member in members:
            mind.store.add_experience_projection(
                ExperienceProjection(
                    experience_id=experience_id,
                    record_id=record.record_id,
                    node_id=member.concept_id,
                    layer=level,
                    side=GraphSide.INPUT,
                    activation=1.0,
                    preference=preference,
                    confidence=0.8,
                    pulse=pulse,
                    metadata={"projection": "recursive_coactivation"},
                )
            )
        semantic_id = mind.graph.stage_growth(
            record,
            input_trunk=InputTrunk.NOTICE,
            pulse=pulse,
            parent_node_id=members[0].concept_id,
            promotion_count=3,
            overlap_threshold=0.96,
        )
    if semantic_id is None:
        return None
    cluster = next(
        cluster
        for cluster in mind.store.list_overlap_clusters(members[0].concept_id)
        if cluster.semantic_node_id == semantic_id
    )
    child_id = str(cluster.child_node_id)
    for member in members[1:]:
        mind.graph.add_relation(
            member.concept_id, child_id, side=GraphSide.INPUT, pulse=mind.pulse
        )
    for member in members:
        mind.graph.add_relation(
            member.concept_id, child_id, side=GraphSide.OUTPUT, pulse=mind.pulse
        )
    mind.graph.add_relation(
        child_id, semantic_id, side=GraphSide.OUTPUT, pulse=mind.pulse
    )

    # Attach the assembly to its effector trunk.  Without this the higher-level nodes
    # are reachable only from their own members, so no output traversal from SELF can
    # ever admit them -- and the LOOK and DO assemblies stay as unreachable as the
    # SPEAK one.
    trunk_node_id = OUTPUT_NODE_IDS[output_trunk]
    mind.graph.add_relation(
        trunk_node_id, child_id, side=GraphSide.OUTPUT, pulse=mind.pulse
    )

    density = float(len(members))
    member_relations = tuple(
        StructuralRelation(
            source_node_id=member.concept_id,
            target_node_id=child_id,
            coactivation_density=density,
            direction="input",
        )
        for member in members
    )
    merge_structural_relations(
        mind,
        child_id,
        relations=member_relations
        + (
            StructuralRelation(
                source_node_id=trunk_node_id,
                target_node_id=child_id,
                coactivation_density=density,
                direction="output",
            ),
        ),
        parent_node_ids=(trunk_node_id, *(member.concept_id for member in members)),
        child_node_ids=(semantic_id,),
        coactivations=len(members),
        map_kind="assembly-child",
    )
    merge_structural_relations(
        mind,
        semantic_id,
        relations=(
            StructuralRelation(
                source_node_id=child_id,
                target_node_id=semantic_id,
                coactivation_density=density,
                direction="output",
            ),
        ),
        parent_node_ids=(trunk_node_id, child_id),
        coactivations=len(members),
        map_kind="assembly-crown",
    )
    return child_id, semantic_id


def recursive_assemblies(
    mind: BaseAgenticMemoryRAG,
    assignments: dict[str, dict[str, object]],
) -> dict[str, str]:
    by_category: dict[str, list[str]] = defaultdict(list)
    for semantic_id, assignment in assignments.items():
        by_category[str(assignment["category"])].append(semantic_id)
    category_nodes = {}
    for category, member_ids in sorted(by_category.items()):
        trunks = Counter(
            str(assignments[member_id]["output_trunk"]) for member_id in member_ids
        )
        result = grow_assembly(
            mind,
            sorted(member_ids),
            name=category,
            level=5,
            output_trunk=OutputTrunk(trunks.most_common(1)[0][0]),
        )
        if result:
            category_nodes[category] = result[1]

    domains = {
        "relational": ("social", "affect", "knowledge"),
        "operational": ("digital", "agency", "world"),
    }
    domain_nodes = {}
    for domain, category_names in domains.items():
        members = [category_nodes[name] for name in category_names if name in category_nodes]
        result = grow_assembly(
            mind,
            members,
            name=domain,
            level=7,
            output_trunk=OutputTrunk.SPEAK if domain == "relational" else OutputTrunk.LOOK,
        )
        if result:
            domain_nodes[domain] = result[1]
    return {**{f"category:{key}": value for key, value in category_nodes.items()},
            **{f"domain:{key}": value for key, value in domain_nodes.items()}}


def content_words(records: Iterable[MemoryRecord]) -> Counter[str]:
    counts = Counter()
    for record in records:
        for word in tokenize(record.text):
            if len(word) >= 3 and word not in STOP_WORDS:
                counts[word] += 1
    return counts


def attach_lexical_membrane(
    mind: BaseAgenticMemoryRAG,
    model: Path,
    codec: Path,
    assignments: dict[str, dict[str, object]],
    *,
    words_per_concept: int = 6,
) -> dict[str, object]:
    selected: dict[str, list[tuple[str, int]]] = {}
    vocabulary = set()
    for semantic_id, assignment in assignments.items():
        records = mind.store.get_records(assignment["record_ids"])
        counts = content_words(records)
        topic = str(assignment["topic"])
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if topic in counts:
            ordered = [(topic, counts[topic]), *[item for item in ordered if item[0] != topic]]
        selected[semantic_id] = ordered[:words_per_concept]
        vocabulary.update(word for word, _ in selected[semantic_id])

    forms = [f" {word}" for word in sorted(vocabulary)]
    encoded = mass_embed(model, codec, forms)
    geometry = {
        word: vector
        for word, (_, vector) in zip(sorted(vocabulary), encoded)
    }
    lexeme_ids = {
        word: reverse_nursery.ensure_geometry_lexeme(mind, vector)
        for word, vector in geometry.items()
    }
    fiber_count = 0
    transition_edges = set()
    for semantic_id, words in selected.items():
        topic = str(assignments[semantic_id]["topic"])
        supporting_ids = tuple(assignments[semantic_id]["record_ids"])
        for word, count in words:
            lexeme_id = lexeme_ids[word]
            input_edge = mind.graph.add_relation(
                semantic_id,
                lexeme_id,
                side=GraphSide.INPUT,
                pulse=mind.pulse,
                evidence_record_ids=supporting_ids,
            )
            output_edge = mind.graph.add_relation(
                semantic_id,
                lexeme_id,
                side=GraphSide.OUTPUT,
                pulse=mind.pulse,
                evidence_record_ids=supporting_ids,
            )
            repetitions = 4 if word == topic else max(1, min(2, count // 4))
            for _ in range(repetitions):
                mind.graph.reinforce_edges(
                    (input_edge.edge_id, output_edge.edge_id),
                    stability_delta=0.75,
                    verified=True,
                    evidence_quality=0.9,
                )
            fiber_count += 2
        allowed = {word for word, _ in words}
        for record in mind.store.get_records(supporting_ids):
            sequence = []
            for word in tokenize(record.text):
                if word not in allowed or (sequence and sequence[-1] == word):
                    continue
                sequence.append(word)
            for source_word, target_word in zip(sequence, sequence[1:]):
                for side in GraphSide:
                    edge = mind.graph.add_relation(
                        lexeme_ids[source_word],
                        lexeme_ids[target_word],
                        side=side,
                        pulse=mind.pulse,
                        evidence_record_ids=(record.record_id,),
                    )
                    transition_edges.add(edge.edge_id)
                    mind.graph.reinforce_edges(
                        (edge.edge_id,),
                        stability_delta=0.35,
                        verified=True,
                        evidence_quality=0.8,
                    )
    return {
        "surface_forms": len(vocabulary),
        "lexeme_nodes": len(set(lexeme_ids.values())),
        "fibers": fiber_count,
        "lexical_transition_edges": len(transition_edges),
        "selected_words": {
            semantic_id: [word for word, _ in words]
            for semantic_id, words in selected.items()
        },
        "lexeme_ids": lexeme_ids,
    }


def add_temporal_relations(
    mind: BaseAgenticMemoryRAG,
    assignments: dict[str, dict[str, object]],
) -> int:
    record_to_concept = {
        record_id: semantic_id
        for semantic_id, assignment in assignments.items()
        for record_id in assignment["record_ids"]
    }
    sessions: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for record in mind.store.list_records():
        session_id = record.metadata.get("session_id")
        if not session_id or record.record_id not in record_to_concept:
            continue
        sessions[str(session_id)].append(
            (int(record.metadata.get("sequence", 0)), record_to_concept[record.record_id])
        )
    created = set()
    for entries in sessions.values():
        ordered = [concept for _, concept in sorted(entries)]
        for source, target in zip(ordered, ordered[1:]):
            if source == target:
                continue
            for side in GraphSide:
                edge = mind.graph.add_relation(source, target, side=side, pulse=mind.pulse)
                created.add(edge.edge_id)
                mind.graph.reinforce_edges(
                    (edge.edge_id,),
                    stability_delta=0.25,
                    verified=True,
                    evidence_quality=0.7,
                )
    return len(created)


def evaluate(
    mind: BaseAgenticMemoryRAG,
    model: Path,
    codec: Path,
    assignments: dict[str, dict[str, object]],
    membrane: dict[str, object],
) -> dict[str, object]:
    topic_to_concepts: dict[str, list[str]] = defaultdict(list)
    for semantic_id, assignment in assignments.items():
        topic_to_concepts[str(assignment["topic"])].append(semantic_id)
    coverage_probes = [
        f"A new situation demonstrates {topic.word}: {topic.description}."
        for topic in TOPICS
    ]
    coverage_embedded = mass_embed(model, codec, coverage_probes)
    concepts = [mind.store.get_concept(concept_id) for concept_id in assignments]
    concepts = [concept for concept in concepts if concept is not None]
    by_topic = {topic.word: topic for topic in TOPICS}

    def score_probe(
        topic_word: str,
        vector: Sequence[float],
        *,
        message_input: bool = False,
    ) -> dict[str, object]:
        topic = by_topic[topic_word]
        ranked = sorted(
            (
                (cosine_similarity(vector, concept.embedding), concept.concept_id)
                for concept in concepts
            ),
            reverse=True,
        )
        top_ids = [concept_id for _, concept_id in ranked[:3]]
        expected = set(topic_to_concepts.get(topic.word, ()))
        chosen = top_ids[0] if top_ids else None
        trace = (
            mind.graph.traverse(
                pulse_id=f"gestation-eval:{topic_word}",
                side=GraphSide.INPUT,
                target_id=chosen,
                endpoint_score=ranked[0][0],
                required_input_trunk=(
                    InputTrunk.HEAR if message_input else topic.input_trunk
                ),
                mark_active=False,
            )
            if chosen
            else None
        )
        return {
            "topic": topic_word,
            "top1": chosen,
            "score": ranked[0][0] if ranked else 0.0,
            "correct_at_1": chosen in expected,
            "correct_at_3": bool(expected.intersection(top_ids)),
            "y_reachable": trace is not None,
            "path_depth": len(trace.path_node_ids) - 1 if trace else None,
        }

    coverage = [
        score_probe(topic.word, vector)
        for topic, (_, vector) in zip(TOPICS, coverage_embedded)
    ]
    semantic_embedded = mass_embed(
        model, codec, [text for _, text in SEMANTIC_PROBES]
    )
    semantic = [
        {**score_probe(topic_word, vector, message_input=True), "probe": text}
        for (topic_word, text), (_, vector) in zip(SEMANTIC_PROBES, semantic_embedded)
    ]
    training_texts = {record.text for record in mind.store.list_records()}
    semantic_probe_leakage = [
        text for _, text in SEMANTIC_PROBES if text in training_texts
    ]

    productive_targets = []
    states = []
    tokenized_topics = mass_embed(
        model, codec, [f" {topic.word}" for topic in TOPICS]
    )
    for topic, (token_ids, _) in zip(TOPICS, tokenized_topics):
        candidates = topic_to_concepts.get(topic.word, ())
        if not candidates:
            continue
        concept_id = max(
            candidates,
            key=lambda item: float(assignments[item]["purity"]),
        )
        state = reverse_nursery.output_state(mind, concept_id)
        if state is None:
            continue
        if len(token_ids) != 1:
            continue
        productive_targets.append((topic.word, token_ids[0], concept_id))
        states.append(state[0])
        if len(states) >= 18:
            break
    projection = reverse_nursery.nearest_vocabulary(
        model, codec, states, top_k=5
    )
    productive = []
    for (topic, expected_token, concept_id), decoded in zip(
        productive_targets, projection["items"]
    ):
        ids = [int(candidate["token_id"]) for candidate in decoded["candidates"]]
        productive.append(
            {
                "topic": topic,
                "concept_id": concept_id,
                "expected_token": int(expected_token),
                "top_token": ids[0] if ids else None,
                "correct_at_1": bool(ids) and ids[0] == expected_token,
                "correct_at_5": expected_token in ids,
                "candidates": decoded["candidates"],
            }
        )
    shuffled_expected = [item["expected_token"] for item in productive[1:]] + (
        [productive[0]["expected_token"]] if productive else []
    )
    shuffled_hits = sum(
        item["top_token"] == expected
        for item, expected in zip(productive, shuffled_expected)
    )
    return {
        "receptive": {
            "coverage_count": len(coverage),
            "coverage_accuracy_at_1": sum(item["correct_at_1"] for item in coverage) / len(coverage),
            "coverage_accuracy_at_3": sum(item["correct_at_3"] for item in coverage) / len(coverage),
            "semantic_count": len(semantic),
            "semantic_accuracy_at_1": sum(item["correct_at_1"] for item in semantic) / len(semantic),
            "semantic_accuracy_at_3": sum(item["correct_at_3"] for item in semantic) / len(semantic),
            "semantic_y_reachable": sum(item["y_reachable"] for item in semantic) / len(semantic),
            "semantic_probe_text_leakage": semantic_probe_leakage,
            "coverage_probes": coverage,
            "semantic_probes": semantic,
        },
        "productive": {
            "count": len(productive),
            "accuracy_at_1": sum(item["correct_at_1"] for item in productive) / max(1, len(productive)),
            "accuracy_at_5": sum(item["correct_at_5"] for item in productive) / max(1, len(productive)),
            "shuffled_control_at_1": shuffled_hits / max(1, len(productive)),
            "projection_tensor": projection.get("tensor"),
            "probes": productive,
        },
        "average_cluster_purity": statistics.mean(
            float(item["purity"]) for item in assignments.values()
        ),
        "membrane_surface_forms": membrane["surface_forms"],
    }


def graph_statistics(mind: BaseAgenticMemoryRAG) -> dict[str, object]:
    kinds = Counter(node.kind for node in mind.store.list_concepts())
    sides = Counter(edge.side.value for edge in mind.store.list_edges())
    snapshot = mind.graph.weight_snapshot()
    return {
        "records": len(mind.store.list_records()),
        "concepts": len(mind.store.list_concepts()),
        "concept_kinds": dict(kinds),
        "edges": len(mind.store.list_edges()),
        "edges_by_side": dict(sides),
        "overlap_clusters": len(clusters(mind)),
        "pulse": mind.pulse,
        "global_edge_mass": snapshot.total,
        "invariants": mind.graph.validate_invariants(),
    }


def assembly_depths(
    mind: BaseAgenticMemoryRAG,
    assemblies: dict[str, str],
) -> dict[str, dict[str, int | bool | None]]:
    results = {}
    for name, semantic_id in assemblies.items():
        input_trace = mind.graph.traverse(
            pulse_id=f"assembly-depth:input:{name}",
            side=GraphSide.INPUT,
            target_id=semantic_id,
            endpoint_score=1.0,
            mark_active=False,
        )
        output_trace = mind.graph.traverse(
            pulse_id=f"assembly-depth:output:{name}",
            side=GraphSide.OUTPUT,
            target_id=semantic_id,
            endpoint_score=1.0,
            mark_active=False,
        )
        results[name] = {
            "input_reachable": input_trace is not None,
            "input_depth": len(input_trace.path_edge_ids) if input_trace else None,
            "output_reachable": output_trace is not None,
            "output_depth": len(output_trace.path_edge_ids) if output_trace else None,
        }
    return results


def restart_check(
    database: Path,
    model: Path,
    codec: Path,
    expected_stats: dict[str, object],
) -> dict[str, object]:
    embedder = NativeMassEmbedder(model, codec)
    with BaseAgenticMemoryRAG(database, embedder=embedder) as mind:
        embedder.bootstrap = False
        observed = graph_statistics(mind)
        return {
            "counts_match": all(
                observed[key] == expected_stats[key]
                for key in ("records", "concepts", "edges", "overlap_clusters", "pulse")
            ),
            "global_edge_mass": observed["global_edge_mass"],
            "invariants": observed["invariants"],
        }


def compile_mind(
    database: Path,
    model: Path,
    codec: Path,
    *,
    human_name: str,
    agent_name: str,
    taste_schema: str,
    replay_cycles: int,
) -> dict[str, object]:
    if database.exists():
        raise FileExistsError(f"refusing to overwrite existing mind: {database}")
    episodes = curriculum(replay_cycles=replay_cycles)
    encoded = mass_embed(model, codec, [episode.text for episode in episodes])
    vectors = [vector for _, vector in encoded]
    threshold, calibration = calibrate_overlap(episodes, vectors)
    embedder = NativeMassEmbedder(model, codec)
    for episode, vector in zip(episodes, vectors):
        embedder.cache[episode.text] = vector

    started = time.monotonic()
    with BaseAgenticMemoryRAG(
        database,
        embedder=embedder,
        growth_overlap_threshold=threshold,
        growth_promotion_count=3,
    ) as mind:
        embedder.bootstrap = False
        gestate(
            mind,
            human_name=human_name,
            agent_name=agent_name,
            taste_schema=taste_schema,
            model_backend="native-gguf",
            model_name=model.name,
        )
        for index, (episode, vector) in enumerate(zip(episodes, vectors)):
            add_episode(mind, episode, vector, index, threshold)
        assignments = learned_assignments(mind)
        add_mirrored_output_paths(mind, assignments)
        language_schooling = cross_modal_language_schooling(mind, assignments)
        temporal_edges = add_temporal_relations(mind, assignments)
        assemblies = recursive_assemblies(mind, assignments)
        membrane = attach_lexical_membrane(mind, model, codec, assignments)
        evaluation = evaluate(mind, model, codec, assignments, membrane)
        stats = graph_statistics(mind)
        depths = assembly_depths(mind, assemblies)
        manifest = {
            "schema": "habitus.accelerated-gestation.v1",
            "human_name": human_name,
            "agent_name": agent_name,
            "taste_schema": taste_schema,
            "model": str(model),
            "embedding_space": embedder.space_id,
            "curriculum_episodes": len(episodes),
            "curriculum_topics": len(TOPICS),
            "replay_cycles": replay_cycles,
            "overlap_calibration": calibration,
            "topic_concepts": len(assignments),
            "language_schooled_concepts": language_schooling,
            "recursive_assemblies": assemblies,
            "assembly_depths": depths,
            "temporal_edges": temporal_edges,
            "membrane": {
                key: value
                for key, value in membrane.items()
                if key != "lexeme_ids"
            },
            "evaluation": evaluation,
            "graph": stats,
            "elapsed_seconds": time.monotonic() - started,
            "database": str(database),
            "database_bytes": database.stat().st_size,
        }
        mind.store.set_metadata(
            "accelerated_gestation_manifest", json.dumps(manifest, sort_keys=True)
        )
    restart = restart_check(database, model, codec, manifest["graph"])
    manifest["restart_check"] = restart
    manifest["hatch_ready"] = (
        not manifest["graph"]["invariants"]
        and restart["counts_match"]
        and not restart["invariants"]
        and manifest["graph"]["concepts"] >= 200
        and manifest["graph"]["edges"] >= 500
        and evaluation["receptive"]["semantic_accuracy_at_1"] >= 0.60
        and not evaluation["receptive"]["semantic_probe_text_leakage"]
        and evaluation["receptive"]["semantic_y_reachable"] == 1.0
        and evaluation["productive"]["accuracy_at_1"] >= 0.60
        and evaluation["productive"]["shuffled_control_at_1"]
        <= evaluation["productive"]["accuracy_at_1"] - 0.40
        and all(item["input_reachable"] and item["output_reachable"] for item in depths.values())
    )
    embedder = NativeMassEmbedder(model, codec)
    with BaseAgenticMemoryRAG(database, embedder=embedder) as mind:
        mind.store.set_metadata(
            "accelerated_gestation_manifest", json.dumps(manifest, sort_keys=True)
        )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=nursery.MODEL)
    parser.add_argument("--codec", type=Path, default=nursery.CODEC)
    parser.add_argument("--human-name", default="Josh")
    parser.add_argument("--agent-name", default="Habitus")
    parser.add_argument("--taste", default="curious")
    parser.add_argument("--replay-cycles", type=int, default=2)
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=EXPERIMENT_ROOT / "accelerated_gestation_runs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.model.is_file() or not args.codec.is_file():
        raise SystemExit("build the native helpers and provide the Qwen3 GGUF first")
    args.run_directory.mkdir(parents=True, exist_ok=True)
    stamp = time.time_ns()
    database = args.run_directory / f"{args.agent_name.casefold()}-{stamp}.sqlite"
    manifest = compile_mind(
        database,
        args.model,
        args.codec,
        human_name=args.human_name,
        agent_name=args.agent_name,
        taste_schema=args.taste,
        replay_cycles=args.replay_cycles,
    )
    receipt = args.run_directory / f"gestation-{stamp}.json"
    receipt.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    receptive = manifest["evaluation"]["receptive"]
    productive = manifest["evaluation"]["productive"]
    print(json.dumps({
        "database": str(database),
        "receipt": str(receipt),
        "graph": manifest["graph"],
        "receptive": {
            key: receptive[key]
            for key in (
                "coverage_count",
                "coverage_accuracy_at_1",
                "coverage_accuracy_at_3",
                "semantic_count",
                "semantic_accuracy_at_1",
                "semantic_accuracy_at_3",
                "semantic_y_reachable",
            )
        },
        "productive": {
            key: productive[key]
            for key in (
                "count",
                "accuracy_at_1",
                "accuracy_at_5",
                "shuffled_control_at_1",
                "projection_tensor",
            )
        },
        "restart_check": manifest["restart_check"],
        "hatch_ready": manifest["hatch_ready"],
        "elapsed_seconds": manifest["elapsed_seconds"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
