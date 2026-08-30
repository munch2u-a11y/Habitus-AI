#!/usr/bin/env python3
"""Grow lexical fibers downward, then decode outward states through GGUF geometry.

Unlike nursery.py's diagnostic decoder, production here never reads a token ID
from a lexical node. The active output fibers form one 1024D state per lower
concept and the native codec searches the model's complete vocabulary matrix.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import time
from typing import Sequence

from habitus_ai.pipeline import BaseAgenticMemoryRAG
from habitus_ai.types import ConceptNode, GraphSide, as_tuple

import nursery
from opaque_skeleton import OpaqueIdentityEmbedder


@dataclass(frozen=True)
class ReverseSpeechAttempt:
    pulse: int
    token_ids: tuple[int, ...]
    surface: str
    fiber_edge_ids: tuple[str, ...]
    construction_edge_ids: tuple[str, ...]
    states: tuple[tuple[float, ...], ...]
    decoded: tuple[dict[str, object], ...]
    projection_tensor: str | None


def embedding_identity(embedding: Sequence[float]) -> str:
    digest = hashlib.sha256()
    for value in embedding:
        digest.update(struct.pack("<f", float(value)))
    return f"LXG:{digest.hexdigest()[:16]}"


def ensure_geometry_lexeme(
    mind: BaseAgenticMemoryRAG,
    embedding: Sequence[float],
) -> str:
    """Create a surface node containing geometry but no word or token label."""
    node_id = embedding_identity(embedding)
    if mind.store.get_concept(node_id) is None:
        mind.store.add_concept(
            ConceptNode(
                concept_id=node_id,
                label=node_id,
                kind="lexeme",
                embedding=as_tuple(embedding),
                terms=(),
                vault_id=f"lexical-geometry:{node_id}",
                created_pulse=mind.pulse,
                last_active_pulse=mind.pulse,
            )
        )
    return node_id


def make_reverse_curriculum(
    mind: BaseAgenticMemoryRAG,
    model: Path,
    codec: Path,
    forms: Sequence[str],
    *,
    assignment: Sequence[int] = (0, 1, 2),
) -> tuple[nursery.LabelExposure, ...]:
    if len(forms) != len(nursery.LOWER_NODES) or sorted(assignment) != [0, 1, 2]:
        raise ValueError("reverse nursery v0 requires three forms and an assignment")
    tokenized = nursery.tokenize_surface_forms(model, codec, forms)
    exposures = []
    for lower_index, form_index in enumerate(assignment):
        token_ids, embedding = tokenized[form_index]
        exposures.append(
            nursery.LabelExposure(
                lower_node_id=nursery.LOWER_NODES[lower_index],
                surface_form=forms[form_index],
                token_ids=token_ids,
                lexeme_id=ensure_geometry_lexeme(mind, embedding),
            )
        )
    return tuple(exposures)


def output_state(
    mind: BaseAgenticMemoryRAG,
    lower_node_id: str,
) -> tuple[tuple[float, ...], tuple[str, ...]] | None:
    """Blend all productive fibers without consulting lexical token metadata."""
    candidates = nursery.lexical_candidates(mind, lower_node_id)
    if not candidates:
        return None
    state = [0.0] * mind.embedder.dimension
    fibers = []
    for probability, lexeme_id, edge_id in candidates:
        lexeme = mind.store.get_concept(lexeme_id)
        if lexeme is None or len(lexeme.embedding) != len(state):
            raise RuntimeError("invalid lexical geometry node")
        for index, value in enumerate(lexeme.embedding):
            state[index] += probability * value
        fibers.append(edge_id)
    return tuple(state), tuple(fibers)


def nearest_vocabulary(
    model: Path,
    codec: Path,
    states: Sequence[Sequence[float]],
    *,
    top_k: int = 5,
) -> dict[str, object]:
    if not states:
        return {"dimension": 1024, "tensor": None, "items": []}
    encoded = [",".join(format(float(value), ".9g") for value in state) for state in states]
    completed = subprocess.run(
        [str(codec), str(model), "nearest", str(top_k), *encoded],
        check=False,
        capture_output=True,
        text=True,
        env=nursery.codec_environment(),
        timeout=240,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())
    return json.loads(completed.stdout)


def attempt_reverse_speech(
    mind: BaseAgenticMemoryRAG,
    model: Path,
    codec: Path,
) -> ReverseSpeechAttempt:
    pulse, pulse_id = nursery.next_pulse(mind, "reverse-attempt")
    construction = mind.graph.traverse(
        pulse_id=pulse_id,
        side=GraphSide.OUTPUT,
        target_id=nursery.LOWER_NODES[-1],
        endpoint_score=1.0,
        mark_active=True,
    )
    if construction is None:
        raise RuntimeError("speech construction is unreachable")

    states = []
    fiber_edges = []
    for node_id in construction.path_node_ids:
        if node_id not in nursery.LOWER_NODES:
            continue
        result = output_state(mind, node_id)
        if result is None:
            continue
        state, fibers = result
        states.append(state)
        fiber_edges.extend(fibers)

    projection = nearest_vocabulary(model, codec, states)
    decoded = tuple(projection["items"])
    token_ids = tuple(
        int(item["candidates"][0]["token_id"])
        for item in decoded
        if item["candidates"]
    )
    surface = nursery.render_token_ids(model, codec, token_ids) if token_ids else ""
    return ReverseSpeechAttempt(
        pulse=pulse,
        token_ids=token_ids,
        surface=surface,
        fiber_edge_ids=tuple(fiber_edges),
        construction_edge_ids=construction.path_edge_ids,
        states=tuple(states),
        decoded=decoded,
        projection_tensor=projection.get("tensor"),
    )


def run_reverse_nursery(
    database: Path,
    model: Path,
    codec: Path,
    forms: Sequence[str],
    *,
    assignment: Sequence[int] = (0, 1, 2),
    cycles: int = 8,
) -> dict[str, object]:
    episodes = []
    with BaseAgenticMemoryRAG(database, embedder=OpaqueIdentityEmbedder()) as mind:
        nursery.seed_developmental_path(mind)
        curriculum = make_reverse_curriculum(
            mind, model, codec, forms, assignment=assignment
        )
        for _ in range(cycles):
            for exposure in curriculum:
                episodes.append(nursery.expose_label(mind, exposure))

        comprehension = [nursery.comprehension_probe(mind, item) for item in curriculum]
        attempt = attempt_reverse_speech(mind, model, codec)
        expected = tuple(
            token
            for token_ids, _ in nursery.tokenize_surface_forms(model, codec, forms)
            for token in token_ids
        )
        feedback = nursery.caregiver_feedback(mind, attempt, expected)
        episodes.append(feedback)
        invariants = mind.graph.validate_invariants()
        hatch_ready = (
            all(item["passed"] for item in comprehension)
            and attempt.token_ids == expected
            and feedback["exact"] is True
            and not invariants
        )
        lexical_nodes = [
            node for node in mind.store.list_concepts(kind="lexeme")
        ]
        return {
            "forms_presented_separately": list(forms),
            "complete_phrase_presented": False,
            "assignment": list(assignment),
            "cycles": cycles,
            "lexical_nodes_store_token_ids": any(node.terms for node in lexical_nodes),
            "production_reads_token_ids_from_graph": False,
            "comprehension": comprehension,
            "speech": {
                "token_ids": list(attempt.token_ids),
                "surface": attempt.surface,
                "expected_token_ids": list(expected),
                "exact": attempt.token_ids == expected,
                "projection_tensor": attempt.projection_tensor,
                "candidates": list(attempt.decoded),
                "state_hashes": [
                    embedding_identity(state) for state in attempt.states
                ],
            },
            "feedback": feedback,
            "hatch_ready": hatch_ready,
            "graph_invariants": invariants,
            "episodes": episodes,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=nursery.MODEL)
    parser.add_argument("--codec", type=Path, default=nursery.CODEC)
    parser.add_argument("--cycles", type=int, default=8)
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=Path(__file__).resolve().parent / "reverse_nursery_runs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.model.is_file() or not args.codec.is_file():
        raise SystemExit("build the native helpers and provide the Qwen3 GGUF first")
    args.run_directory.mkdir(parents=True, exist_ok=True)
    stamp = time.time_ns()
    cases = {
        "primary": (("I", " like", " Josh"), (0, 1, 2), args.cycles),
        "substitution": (("I", " prefer", " music"), (0, 1, 2), args.cycles),
        "shuffled_pairing_control": (("I", " like", " Josh"), (2, 0, 1), args.cycles),
        "untrained_control": (("I", " like", " Josh"), (0, 1, 2), 0),
    }
    results = {}
    for name, (forms, assignment, cycles) in cases.items():
        results[name] = run_reverse_nursery(
            args.run_directory / f"{name}-{stamp}.sqlite",
            args.model,
            args.codec,
            forms,
            assignment=assignment,
            cycles=cycles,
        )
    receipt = {
        "schema": "habitus.reverse-lexical-geometry.v1",
        "created_ns": stamp,
        "model": str(args.model),
        "production_decoder": "weighted graph fibers -> 1024D states -> full GGUF vocabulary",
        **results,
    }
    receipt_path = args.run_directory / f"reverse-nursery-{stamp}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    for name, result in results.items():
        print(
            f"{name:26} {result['speech']['surface']!r} "
            f"exact={result['speech']['exact']} hatch={result['hatch_ready']}"
        )
    print(f"receipt> {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
