#!/usr/bin/env python3
"""Generate sentences from a hatched graph through native GGUF soft inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.embeddings import cosine_similarity  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import GraphSide, InputTrunk  # noqa: E402
import accelerated_gestation as gestation  # noqa: E402
import nursery  # noqa: E402
import opaque_skeleton  # noqa: E402
import probe_hatched_mind  # noqa: E402
import reverse_nursery  # noqa: E402


RUNNER = EXPERIMENT_ROOT / "native" / "graph_soft_generator"
DEFAULT_DATABASE = next(
    iter(
        sorted(
            (EXPERIMENT_ROOT / "accelerated_gestation_runs").glob("habitus-*.sqlite"),
            reverse=True,
        )
    ),
    Path("missing.sqlite"),
)

DEFAULT_PROBES = (
    ("trust", "People consistently keep promises, making cooperation feel safe."),
    ("fear", "A danger I do not understand makes future safety uncertain."),
    ("evidence", "Observed facts either support the claim or weaken it."),
    ("music", "Rhythm and melody create expectations across organized sounds."),
)


def normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(value) * float(value) for value in vector)) or 1.0
    return [float(value) / norm for value in vector]


def productive_concepts(mind: BaseAgenticMemoryRAG):
    return [
        mind.store.get_concept(concept_id)
        for concept_id in probe_hatched_mind.productive_concepts(mind)
    ]


def select_endpoint(
    mind: BaseAgenticMemoryRAG,
    query_vector: Sequence[float],
    *,
    most_relevant: bool,
):
    candidates = [concept for concept in productive_concepts(mind) if concept is not None]
    ranked = sorted(
        (
            (cosine_similarity(query_vector, concept.embedding), concept)
            for concept in candidates
        ),
        key=lambda item: (item[0], item[1].concept_id),
        reverse=True,
    )
    if not ranked:
        raise RuntimeError("hatched mind has no productive concepts")
    return ranked[0] if most_relevant else ranked[-1]


def graph_state_rows(
    mind: BaseAgenticMemoryRAG,
    concept_id: str,
    *,
    maximum_rows: int = 8,
) -> tuple[list[list[float]], dict[str, object]]:
    concept = mind.store.get_concept(concept_id)
    if concept is None:
        raise KeyError(concept_id)
    input_trace = mind.graph.traverse(
        pulse_id=f"transformer-hatch:input:{concept_id}",
        side=GraphSide.INPUT,
        target_id=concept_id,
        endpoint_score=1.0,
        required_input_trunk=InputTrunk.HEAR,
        mark_active=False,
    )
    output_trace = mind.graph.traverse(
        pulse_id=f"transformer-hatch:output:{concept_id}",
        side=GraphSide.OUTPUT,
        target_id=concept_id,
        endpoint_score=1.0,
        mark_active=False,
    )
    if input_trace is None or output_trace is None:
        raise RuntimeError(f"concept is not end-to-end reachable: {concept_id}")

    rows = [normalize(concept.embedding)]
    row_sources: list[dict[str, object]] = [
        {"kind": "concept_centroid", "node_id": concept_id}
    ]
    state = reverse_nursery.output_state(mind, concept_id)
    if state is not None:
        rows.append(normalize(state[0]))
        row_sources.append(
            {
                "kind": "weighted_productive_state",
                "fiber_count": len(state[1]),
                "fiber_edge_ids": list(state[1]),
            }
        )
    for probability, lexeme_id, edge_id in nursery.lexical_candidates(mind, concept_id):
        if len(rows) >= maximum_rows:
            break
        lexeme = mind.store.get_concept(lexeme_id)
        if lexeme is None:
            continue
        rows.append(normalize(lexeme.embedding))
        row_sources.append(
            {
                "kind": "productive_fiber",
                "node_id": lexeme_id,
                "edge_id": edge_id,
                "local_probability": probability,
            }
        )
    return rows, {
        "concept_id": concept_id,
        "input_path": list(input_trace.path_node_ids),
        "output_path": list(output_trace.path_node_ids),
        "row_sources": row_sources,
        "row_count": len(rows),
        "raw_language_strings_in_rows": False,
        "lexical_geometry_rows": True,
        "record_text_in_rows": False,
    }


def ordered_lexical_rows(
    mind: BaseAgenticMemoryRAG,
    concept_id: str,
    *,
    maximum_rows: int = 8,
) -> tuple[list[list[float]], dict[str, object]]:
    """Follow learned productive word transitions instead of strength order."""
    candidates = nursery.lexical_candidates(mind, concept_id)[:maximum_rows]
    if not candidates:
        raise RuntimeError(f"concept has no productive lexical fibers: {concept_id}")
    by_id = {
        lexeme_id: (probability, edge_id)
        for probability, lexeme_id, edge_id in candidates
    }
    remaining = set(by_id)
    ordered = [candidates[0][1]]
    remaining.remove(ordered[0])
    transition_ids = []
    while remaining:
        source = ordered[-1]
        ranked = []
        for target in remaining:
            transition = mind.store.find_edge(GraphSide.OUTPUT, source, target)
            ranked.append(
                (
                    transition is not None,
                    transition.log_strength if transition is not None else -math.inf,
                    by_id[target][0],
                    target,
                    transition.edge_id if transition is not None else None,
                )
            )
        _, _, _, target, transition_id = max(ranked)
        ordered.append(target)
        remaining.remove(target)
        transition_ids.append(transition_id)

    rows = []
    sources = []
    for lexeme_id in ordered:
        lexeme = mind.store.get_concept(lexeme_id)
        if lexeme is None:
            continue
        rows.append(normalize(lexeme.embedding))
        sources.append(
            {
                "node_id": lexeme_id,
                "productive_probability": by_id[lexeme_id][0],
                "fiber_edge_id": by_id[lexeme_id][1],
            }
        )
    return rows, {
        "concept_id": concept_id,
        "ordering": "learned_directed_lexeme_transitions",
        "row_sources": sources,
        "transition_edge_ids": transition_ids,
        "missing_transition_count": sum(item is None for item in transition_ids),
        "raw_language_strings_in_rows": False,
        "lexical_geometry_rows": True,
        "record_text_in_rows": False,
    }


def random_control_rows(rows: int) -> list[list[float]]:
    return [
        opaque_skeleton.opaque_unit_vector(f"transformer-random-control:{index}")
        for index in range(rows)
    ]


def run_case(
    case_id: str,
    rows: Sequence[Sequence[float]],
    *,
    model: Path,
    runner: Path,
    run_directory: Path,
    maximum_tokens: int,
    seed: int,
    skip_think: bool = True,
) -> dict[str, object]:
    packet = run_directory / f"{case_id}.packet"
    opaque_skeleton.write_packet(packet, rows)
    native = opaque_skeleton.run_native(
        model,
        runner,
        packet,
        maximum_tokens=maximum_tokens,
        seed=seed,
        skip_think=skip_think,
    )
    return {
        "case_id": case_id,
        "packet": str(packet),
        "packet_sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
        "rows": len(rows),
        "native": native,
    }


def response_scores(
    model: Path,
    codec: Path,
    responses: Sequence[str],
    target_vector: Sequence[float],
) -> list[float]:
    encoded = gestation.mass_embed(model, codec, responses)
    return [cosine_similarity(vector, target_vector) for _, vector in encoded]


def run_probe_matrix(
    database: Path,
    model: Path,
    codec: Path,
    runner: Path,
    run_directory: Path,
    probes: Sequence[tuple[str | None, str]],
    *,
    maximum_tokens: int,
    seed: int,
    include_ablations: bool = False,
) -> dict[str, object]:
    run_directory.mkdir(parents=True, exist_ok=True)
    embedder = gestation.NativeMassEmbedder(model, codec)
    results = []
    with BaseAgenticMemoryRAG(database, embedder=embedder) as mind:
        embedder.bootstrap = False
        for index, (expected, user_text) in enumerate(probes):
            query_vector = embedder.embed(user_text)
            selected_score, selected = select_endpoint(
                mind, query_vector, most_relevant=True
            )
            unrelated_score, unrelated = select_endpoint(
                mind, query_vector, most_relevant=False
            )
            full_target_rows, full_target_trace = graph_state_rows(
                mind, selected.concept_id
            )
            target_rows, target_trace = ordered_lexical_rows(
                mind, selected.concept_id
            )
            unrelated_rows, unrelated_trace = ordered_lexical_rows(
                mind, unrelated.concept_id
            )
            reversed_rows = list(reversed(target_rows))
            random_rows = random_control_rows(len(target_rows))
            case_rows = [("target", target_rows)]
            if include_ablations:
                case_rows.extend(
                    (
                        ("full_bundle", full_target_rows),
                        ("centroid_only", full_target_rows[:1]),
                        ("compact", full_target_rows[:2]),
                        ("productive_only", full_target_rows[1:2]),
                        ("strength_ordered_lexical", full_target_rows[2:]),
                    )
                )
            case_rows.extend(
                (
                    ("reversed", reversed_rows),
                    ("unrelated", unrelated_rows),
                    ("random", random_rows),
                )
            )
            cases = []
            for case_name, rows in case_rows:
                cases.append(
                    run_case(
                        f"probe-{index:02d}-{case_name}",
                        rows,
                        model=model,
                        runner=runner,
                        run_directory=run_directory,
                        maximum_tokens=maximum_tokens,
                        seed=seed,
                    )
                )
            responses = [str(case["native"]["response"]).strip() for case in cases]
            scores = response_scores(model, codec, responses, selected.embedding)
            for case, score in zip(cases, scores):
                case["response_similarity_to_selected_concept"] = score
            cases_by_name = {
                str(case["case_id"]).rsplit("-", 1)[-1]: case
                for case in cases
            }
            target_response = responses[0].casefold()
            target_similarity = float(
                cases_by_name["target"]["response_similarity_to_selected_concept"]
            )
            unrelated_similarity = float(
                cases_by_name["unrelated"]["response_similarity_to_selected_concept"]
            )
            random_similarity = float(
                cases_by_name["random"]["response_similarity_to_selected_concept"]
            )
            results.append(
                {
                    "expected": expected,
                    "input_sha256": hashlib.sha256(user_text.encode("utf-8")).hexdigest(),
                    "input_sent_to_model": False,
                    "memory_text_sent_to_model": False,
                    "selected_concept": selected.concept_id,
                    "selected_score": selected_score,
                    "unrelated_concept": unrelated.concept_id,
                    "unrelated_score": unrelated_score,
                    "target_trace": target_trace,
                    "full_target_trace": full_target_trace,
                    "unrelated_trace": unrelated_trace,
                    "target_contains_expected_word": (
                        expected is None or expected.casefold() in target_response
                    ),
                    "target_beats_unrelated": target_similarity > unrelated_similarity,
                    "target_beats_random": target_similarity > random_similarity,
                    "cases": cases,
                }
            )
    receipt = {
        "schema": "habitus.graph-to-transformer-hatch.v1",
        "created_ns": time.time_ns(),
        "database": str(database),
        "model": str(model),
        "prompt_text_crossed_native_boundary": False,
        "retrieved_memory_text_crossed_native_boundary": False,
        "semantic_codebook_used": False,
        "ablations_included": include_ablations,
        "probe_count": len(results),
        "expected_word_rate": sum(item["target_contains_expected_word"] for item in results) / max(1, len(results)),
        "target_beats_unrelated_rate": sum(item["target_beats_unrelated"] for item in results) / max(1, len(results)),
        "target_beats_random_rate": sum(item["target_beats_random"] for item in results) / max(1, len(results)),
        "results": results,
    }
    receipt_path = run_directory / "transformer-matrix.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--model", type=Path, default=nursery.MODEL)
    parser.add_argument("--codec", type=Path, default=nursery.CODEC)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument("--once")
    parser.add_argument("--expected")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=EXPERIMENT_ROOT / "transformer_hatch_runs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in (args.database, args.model, args.codec, args.runner):
        if not path.is_file():
            raise SystemExit(f"required file not found: {path}")
    stamp = time.time_ns()
    probes = ((args.expected, args.once),) if args.once else DEFAULT_PROBES
    receipt = run_probe_matrix(
        args.database,
        args.model,
        args.codec,
        args.runner,
        args.run_directory / str(stamp),
        probes,
        maximum_tokens=args.max_tokens,
        seed=args.seed,
        include_ablations=args.ablations,
    )
    for result in receipt["results"]:
        print(f"\n[{result['expected'] or 'custom'}]")
        for case in result["cases"]:
            print(
                f"{case['case_id'].rsplit('-', 1)[-1]:10} "
                f"sim={case['response_similarity_to_selected_concept']:.3f} "
                f"{case['native']['response']!r}"
            )
    print(f"\nreceipt> {receipt['receipt_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
