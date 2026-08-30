#!/usr/bin/env python3
"""Deterministic post-gestation nursery for graph-native lexical fibers.

The nursery never writes a word onto an internal node. A caregiver episode
co-activates one opaque lower concept and one model-token lexeme at the top
surface. Ordinary graph edges become the receptive and productive fibers.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.graph import (  # noqa: E402
    OUTPUT_NODE_IDS,
    PREFERENCE_NODE_IDS,
    SELF_ID,
)
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import (  # noqa: E402
    ConceptNode,
    GraphSide,
    InputTrunk,
    OutputTrunk,
    as_tuple,
)
from opaque_skeleton import OpaqueIdentityEmbedder, opaque_unit_vector  # noqa: E402


MODEL = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")
CODEC = Path(__file__).resolve().parent / "native" / "lexeme_codec"
LOWER_NODES = ("D3:00000000", "D3:00000001", "D3:00000002")


@dataclass(frozen=True)
class LabelExposure:
    lower_node_id: str
    surface_form: str
    token_ids: tuple[int, ...]
    lexeme_id: str


@dataclass(frozen=True)
class SpeechAttempt:
    pulse: int
    token_ids: tuple[int, ...]
    surface: str
    fiber_edge_ids: tuple[str, ...]
    construction_edge_ids: tuple[str, ...]


def decode_native(stream: bytes) -> str:
    """Decode native adapter output leniently.

    A generated token piece can be a partial UTF-8 sequence, and strict decoding would
    abort an entire run over one BPE fragment.
    """
    return stream.decode("utf-8", "replace").strip()


def codec_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["OLLAMA_LIB_DIR"] = "/usr/local/lib/ollama"
    environment["LD_LIBRARY_PATH"] = "/usr/local/lib/ollama"
    return environment


def tokenize_surface_forms(
    model: Path,
    codec: Path,
    forms: Sequence[str],
) -> list[tuple[tuple[int, ...], tuple[float, ...]]]:
    completed = subprocess.run(
        [str(codec), str(model), "tokenize", *forms],
        check=False,
        capture_output=True,
        env=codec_environment(),
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(decode_native(completed.stderr))
    result = json.loads(decode_native(completed.stdout))
    if int(result["dimension"]) != 1024:
        raise RuntimeError("nursery requires a native 1024D language model")
    return [
        (
            tuple(int(token) for token in item["token_ids"]),
            tuple(float(value) for value in item["embedding"]),
        )
        for item in result["items"]
    ]


def render_token_ids(model: Path, codec: Path, token_ids: Sequence[int]) -> str:
    completed = subprocess.run(
        [str(codec), str(model), "detokenize", *(str(token) for token in token_ids)],
        check=False,
        capture_output=True,
        env=codec_environment(),
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(decode_native(completed.stderr))
    return str(json.loads(decode_native(completed.stdout))["text"])


def next_pulse(mind: BaseAgenticMemoryRAG, prefix: str) -> tuple[int, str]:
    mind.pulse += 1
    mind.store.set_metadata("pulse_counter", str(mind.pulse))
    return mind.pulse, f"nursery:{prefix}:{mind.pulse}"


def ensure_internal_node(mind: BaseAgenticMemoryRAG, node_id: str) -> None:
    if mind.store.get_concept(node_id) is not None:
        return
    mind.graph.add_concept(
        node_id,
        node_id,
        terms=(),
        embedding=opaque_unit_vector(f"developmental-node:{node_id}"),
        pulse=mind.pulse,
    )


def ensure_relation(
    mind: BaseAgenticMemoryRAG,
    source: str,
    target: str,
    side: GraphSide,
    *,
    delta_y: float = 1.0,
):
    existing = mind.store.find_edge(side, source, target)
    if existing is not None:
        return existing
    return mind.graph.add_relation(
        source,
        target,
        side=side,
        delta_y=delta_y,
        pulse=mind.pulse,
    )


def seed_developmental_path(mind: BaseAgenticMemoryRAG) -> None:
    """Create one ordered, nonverbal three-concept construction path."""
    for node_id in LOWER_NODES:
        ensure_internal_node(mind, node_id)

    preference = PREFERENCE_NODE_IDS[(InputTrunk.HEAR, "STABLE")]
    ensure_relation(mind, preference, LOWER_NODES[0], GraphSide.INPUT)
    ensure_relation(mind, LOWER_NODES[0], LOWER_NODES[1], GraphSide.INPUT)
    ensure_relation(mind, LOWER_NODES[1], LOWER_NODES[2], GraphSide.INPUT)

    ensure_relation(
        mind,
        OUTPUT_NODE_IDS[OutputTrunk.SPEAK],
        LOWER_NODES[0],
        GraphSide.OUTPUT,
    )
    ensure_relation(mind, LOWER_NODES[0], LOWER_NODES[1], GraphSide.OUTPUT)
    ensure_relation(mind, LOWER_NODES[1], LOWER_NODES[2], GraphSide.OUTPUT)


def lexeme_id(token_ids: Sequence[int]) -> str:
    material = ",".join(str(token) for token in token_ids)
    digest = hashlib.sha256(material.encode("ascii")).hexdigest()[:16]
    return f"LX:{digest}"


def ensure_lexeme(
    mind: BaseAgenticMemoryRAG,
    token_ids: Sequence[int],
    embedding: Sequence[float],
) -> str:
    node_id = lexeme_id(token_ids)
    if mind.store.get_concept(node_id) is not None:
        return node_id
    token_terms = tuple(f"token:{int(token)}" for token in token_ids)
    mind.store.add_concept(
        ConceptNode(
            concept_id=node_id,
            label=node_id,
            kind="lexeme",
            embedding=as_tuple(embedding),
            terms=token_terms,
            vault_id=f"lexical-vault:{node_id}",
            created_pulse=mind.pulse,
            last_active_pulse=mind.pulse,
        )
    )
    return node_id


def make_curriculum(
    mind: BaseAgenticMemoryRAG,
    model: Path,
    codec: Path,
    forms: Sequence[str],
    *,
    assignment: Sequence[int] = (0, 1, 2),
) -> tuple[LabelExposure, ...]:
    if len(forms) != len(LOWER_NODES) or sorted(assignment) != [0, 1, 2]:
        raise ValueError("nursery v0 requires three forms and a three-way assignment")
    tokenized = tokenize_surface_forms(model, codec, forms)
    labels = []
    for lower_index, form_index in enumerate(assignment):
        token_ids, embedding = tokenized[form_index]
        labels.append(
            LabelExposure(
                lower_node_id=LOWER_NODES[lower_index],
                surface_form=forms[form_index],
                token_ids=token_ids,
                lexeme_id=ensure_lexeme(mind, token_ids, embedding),
            )
        )
    return tuple(labels)


def expose_label(
    mind: BaseAgenticMemoryRAG,
    exposure: LabelExposure,
    *,
    caregiver_stability: float = 0.8,
) -> dict[str, object]:
    """Co-activate a lower concept and lexeme, forming vertical fibers."""
    pulse, pulse_id = next_pulse(mind, "exposure")
    input_fiber = ensure_relation(
        mind,
        exposure.lower_node_id,
        exposure.lexeme_id,
        GraphSide.INPUT,
        delta_y=1.0,
    )
    output_fiber = ensure_relation(
        mind,
        exposure.lower_node_id,
        exposure.lexeme_id,
        GraphSide.OUTPUT,
        delta_y=1.0,
    )
    trace = mind.graph.traverse(
        pulse_id=pulse_id,
        side=GraphSide.INPUT,
        target_id=exposure.lexeme_id,
        endpoint_score=1.0,
        required_input_trunk=InputTrunk.HEAR,
        mark_active=True,
    )
    if trace is None or exposure.lower_node_id not in trace.path_node_ids:
        raise RuntimeError("caregiver label did not traverse its co-active lower concept")
    mind.graph.reinforce_edges(
        trace.path_edge_ids,
        stability_delta=caregiver_stability,
        verified=True,
        evidence_quality=1.0,
    )
    # Comprehension normally precedes production. The mirrored output fiber
    # receives only weak provisional credit until the agent successfully speaks.
    mind.graph.reinforce_edges(
        (output_fiber.edge_id,),
        stability_delta=caregiver_stability * 0.20,
        verified=True,
        evidence_quality=1.0,
    )
    incidental_output_fibers = []
    # Earlier concepts on the same active construction also receive provisional
    # productive fibers. They are not rewarded merely for co-occurring, so
    # repeated contingent feedback must separate the intended association.
    for coactive_node in trace.path_node_ids:
        if coactive_node not in LOWER_NODES or coactive_node == exposure.lower_node_id:
            continue
        incidental = ensure_relation(
            mind,
            coactive_node,
            exposure.lexeme_id,
            GraphSide.OUTPUT,
            delta_y=2.0,
        )
        incidental_output_fibers.append(incidental.edge_id)
    return {
        "pulse": pulse,
        "event": "caregiver_label",
        "lower_node": exposure.lower_node_id,
        "lexeme_id": exposure.lexeme_id,
        "token_ids": list(exposure.token_ids),
        "input_path": list(trace.path_node_ids),
        "input_fiber": input_fiber.edge_id,
        "output_fiber": output_fiber.edge_id,
        "incidental_output_fibers": incidental_output_fibers,
        "stability": caregiver_stability,
    }


def lexical_candidates(
    mind: BaseAgenticMemoryRAG,
    lower_node_id: str,
) -> list[tuple[float, str, str]]:
    snapshot = mind.graph.weight_snapshot()
    candidates = []
    for edge in mind.store.list_edges(GraphSide.OUTPUT):
        if edge.source_id != lower_node_id:
            continue
        target = mind.store.get_concept(edge.target_id)
        if target is None or target.kind != "lexeme":
            continue
        candidates.append(
            (snapshot.global_weights.get(edge.edge_id, 0.0), target.concept_id, edge.edge_id)
        )
    total = sum(score for score, _, _ in candidates) or 1.0
    return sorted(
        ((score / total, lexeme, edge_id) for score, lexeme, edge_id in candidates),
        key=lambda item: (-item[0], item[1]),
    )


def token_ids_for_lexeme(mind: BaseAgenticMemoryRAG, node_id: str) -> tuple[int, ...]:
    node = mind.store.get_concept(node_id)
    if node is None or node.kind != "lexeme":
        raise KeyError(node_id)
    return tuple(int(term.rsplit(":", 1)[-1]) for term in node.terms)


def attempt_speech(
    mind: BaseAgenticMemoryRAG,
    model: Path,
    codec: Path,
) -> SpeechAttempt:
    pulse, pulse_id = next_pulse(mind, "attempt")
    construction = mind.graph.traverse(
        pulse_id=pulse_id,
        side=GraphSide.OUTPUT,
        target_id=LOWER_NODES[-1],
        endpoint_score=1.0,
        mark_active=True,
    )
    if construction is None:
        raise RuntimeError("speech construction is unreachable")
    token_ids: list[int] = []
    fiber_edges = []
    for node_id in construction.path_node_ids:
        if node_id not in LOWER_NODES:
            continue
        candidates = lexical_candidates(mind, node_id)
        if not candidates:
            continue
        _, selected_lexeme, fiber_edge = candidates[0]
        token_ids.extend(token_ids_for_lexeme(mind, selected_lexeme))
        fiber_edges.append(fiber_edge)
    surface = render_token_ids(model, codec, token_ids) if token_ids else ""
    return SpeechAttempt(
        pulse=pulse,
        token_ids=tuple(token_ids),
        surface=surface,
        fiber_edge_ids=tuple(fiber_edges),
        construction_edge_ids=construction.path_edge_ids,
    )


def caregiver_feedback(
    mind: BaseAgenticMemoryRAG,
    attempt: SpeechAttempt,
    expected_token_ids: Sequence[int],
) -> dict[str, object]:
    """Apply a controlled response one pulse after the speech attempt."""
    pulse, _ = next_pulse(mind, "feedback")
    exact = tuple(expected_token_ids) == attempt.token_ids
    stability = 1.0 if exact else (-0.35 if attempt.token_ids else 0.0)
    credited = (*attempt.fiber_edge_ids, *attempt.construction_edge_ids)
    mind.graph.reinforce_edges(
        credited,
        stability_delta=stability,
        verified=True,
        evidence_quality=1.0,
    )
    return {
        "pulse": pulse,
        "event": "caregiver_feedback",
        "credits_attempt_pulse": attempt.pulse,
        "delay_pulses": pulse - attempt.pulse,
        "exact": exact,
        "stability": stability,
        "emitted_token_ids": list(attempt.token_ids),
        "expected_token_ids": list(expected_token_ids),
    }


def comprehension_probe(
    mind: BaseAgenticMemoryRAG,
    exposure: LabelExposure,
) -> dict[str, object]:
    _, pulse_id = next_pulse(mind, "comprehension")
    trace = mind.graph.traverse(
        pulse_id=pulse_id,
        side=GraphSide.INPUT,
        target_id=exposure.lexeme_id,
        endpoint_score=1.0,
        required_input_trunk=InputTrunk.HEAR,
        mark_active=False,
    )
    if trace is None:
        return {"lexeme_id": exposure.lexeme_id, "resolved": None, "passed": False}
    lower_path = [node for node in trace.path_node_ids if node in LOWER_NODES]
    resolved = lower_path[-1] if lower_path else None
    return {
        "lexeme_id": exposure.lexeme_id,
        "token_ids": list(exposure.token_ids),
        "resolved": resolved,
        "expected": exposure.lower_node_id,
        "path": list(trace.path_node_ids),
        "passed": resolved == exposure.lower_node_id,
    }


def run_one_nursery(
    database: Path,
    model: Path,
    codec: Path,
    forms: Sequence[str],
    *,
    assignment: Sequence[int] = (0, 1, 2),
    cycles: int = 8,
) -> dict[str, object]:
    episodes: list[dict[str, object]] = []
    with BaseAgenticMemoryRAG(database, embedder=OpaqueIdentityEmbedder()) as mind:
        seed_developmental_path(mind)
        curriculum = make_curriculum(
            mind,
            model,
            codec,
            forms,
            assignment=assignment,
        )
        for _ in range(cycles):
            for exposure in curriculum:
                episodes.append(expose_label(mind, exposure))

        comprehension = [comprehension_probe(mind, exposure) for exposure in curriculum]
        attempt = attempt_speech(mind, model, codec)
        canonical_tokenization = tokenize_surface_forms(model, codec, forms)
        expected = tuple(
            token
            for token_ids, _ in canonical_tokenization
            for token in token_ids
        )
        feedback = caregiver_feedback(mind, attempt, expected)
        episodes.append(feedback)
        snapshot = mind.graph.weight_snapshot()
        hatch_ready = (
            all(item["passed"] for item in comprehension)
            and attempt.token_ids == expected
            and feedback["exact"] is True
            and mind.graph.validate_invariants() == []
        )
        return {
            "forms_presented_separately": list(forms),
            "complete_phrase_presented": False,
            "assignment": list(assignment),
            "cycles": cycles,
            "curriculum": [
                {
                    "lower_node": exposure.lower_node_id,
                    "lexeme_id": exposure.lexeme_id,
                    "token_ids": list(exposure.token_ids),
                }
                for exposure in curriculum
            ],
            "comprehension": comprehension,
            "speech": {
                "token_ids": list(attempt.token_ids),
                "surface": attempt.surface,
                "expected_token_ids": list(expected),
                "exact": attempt.token_ids == expected,
            },
            "feedback": feedback,
            "hatch_ready": hatch_ready,
            "fiber_weights": {
                edge.edge_id: snapshot.global_weights.get(edge.edge_id, 0.0)
                for edge in mind.store.list_edges()
                if mind.store.get_concept(edge.target_id) is not None
                and mind.store.get_concept(edge.target_id).kind == "lexeme"
            },
            "graph_invariants": mind.graph.validate_invariants(),
            "episodes": episodes,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--codec", type=Path, default=CODEC)
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=Path(__file__).resolve().parent / "nursery_runs",
    )
    parser.add_argument("--cycles", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.model.is_file() or not args.codec.is_file():
        raise SystemExit("build the native helpers and provide the Qwen3 GGUF first")
    args.run_directory.mkdir(parents=True, exist_ok=True)
    stamp = time.time_ns()
    primary = run_one_nursery(
        args.run_directory / f"primary-{stamp}.sqlite",
        args.model,
        args.codec,
        ("I", " like", " Josh"),
        cycles=args.cycles,
    )
    substitution = run_one_nursery(
        args.run_directory / f"substitution-{stamp}.sqlite",
        args.model,
        args.codec,
        ("I", " prefer", " music"),
        cycles=args.cycles,
    )
    shuffled = run_one_nursery(
        args.run_directory / f"shuffled-{stamp}.sqlite",
        args.model,
        args.codec,
        ("I", " like", " Josh"),
        assignment=(2, 0, 1),
        cycles=args.cycles,
    )
    untrained = run_one_nursery(
        args.run_directory / f"untrained-{stamp}.sqlite",
        args.model,
        args.codec,
        ("I", " like", " Josh"),
        cycles=0,
    )
    receipt = {
        "schema": "habitus.nursery-label-formation.v1",
        "created_ns": stamp,
        "model": str(args.model),
        "lower_nodes_have_language_labels": False,
        "lexical_fibers_are_graph_edges": True,
        "caregiver_is_deterministic": True,
        "hatch_rule": (
            "all receptive probes pass, held-out production is exact, "
            "delayed feedback verifies it, and graph invariants hold"
        ),
        "primary": primary,
        "substitution": substitution,
        "shuffled_pairing_control": shuffled,
        "untrained_control": untrained,
    }
    receipt_path = args.run_directory / f"nursery-{stamp}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    for label, result in (
        ("primary", primary),
        ("substitution", substitution),
        ("shuffled", shuffled),
        ("untrained", untrained),
    ):
        print(f"{label:12} {result['speech']['surface']!r} exact={result['speech']['exact']}")
        print(
            " " * 13
            + f"comprehension={sum(item['passed'] for item in result['comprehension'])}/3"
        )
    print(f"receipt> {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
