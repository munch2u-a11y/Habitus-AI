#!/usr/bin/env python3
"""Probe a gestated mind from ordinary message input to graph-native speech."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.embeddings import cosine_similarity  # noqa: E402
from habitus_ai.types import GraphSide, InputTrunk  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
import accelerated_gestation as gestation  # noqa: E402
import nursery  # noqa: E402
import reverse_nursery  # noqa: E402


DEFAULT_PROBES = (
    ("trust", "People consistently keep promises, making cooperation feel safe."),
    ("fear", "A danger I do not understand makes future safety uncertain."),
    ("evidence", "What I observed either supports the claim or weakens it."),
    ("memory", "An earlier event is still available to influence my present choice."),
    ("search", "I need to inspect several locations to find the relevant information."),
    ("tools", "An external capability lets me perform a new operation."),
    ("planning", "I arrange several future steps before beginning the task."),
    ("verifying", "Check the result independently before believing it worked."),
    ("music", "Rhythm and melody create expectations across a sequence of sounds."),
    ("motion", "The object changes position relative to a reference over time."),
)


def productive_concepts(mind: BaseAgenticMemoryRAG) -> list[str]:
    result = set()
    for edge in mind.store.list_edges(GraphSide.OUTPUT):
        target = mind.store.get_concept(edge.target_id)
        source = mind.store.get_concept(edge.source_id)
        if target is not None and target.kind == "lexeme" and source is not None:
            result.add(source.concept_id)
    return sorted(result)


def probe(
    database: Path,
    model: Path,
    codec: Path,
    prompts: Sequence[tuple[str | None, str]],
) -> dict[str, object]:
    embedder = gestation.NativeMassEmbedder(model, codec)
    results = []
    with BaseAgenticMemoryRAG(database, embedder=embedder) as mind:
        embedder.bootstrap = False
        candidates = [
            mind.store.get_concept(concept_id)
            for concept_id in productive_concepts(mind)
        ]
        candidates = [candidate for candidate in candidates if candidate is not None]
        states = []
        pending = []
        for index, (expected, text) in enumerate(prompts):
            vector = embedder.embed(text)
            ranked = sorted(
                (
                    (cosine_similarity(vector, concept.embedding), concept.concept_id)
                    for concept in candidates
                ),
                reverse=True,
            )
            chosen = ranked[0][1] if ranked else None
            trace = (
                mind.graph.traverse(
                    pulse_id=f"hatched-message-probe:{index}",
                    side=GraphSide.INPUT,
                    target_id=chosen,
                    endpoint_score=ranked[0][0],
                    required_input_trunk=InputTrunk.HEAR,
                    mark_active=False,
                )
                if chosen
                else None
            )
            state = (
                reverse_nursery.output_state(mind, chosen)
                if chosen and trace is not None
                else None
            )
            result = {
                "expected": expected,
                "input": text,
                "selected_concept": chosen,
                "semantic_score": ranked[0][0] if ranked else 0.0,
                "hear_reachable": trace is not None,
                "input_path": list(trace.path_node_ids) if trace else [],
                "output": None,
                "output_candidates": [],
            }
            results.append(result)
            if state is not None:
                states.append(state[0])
                pending.append(result)

        projection = reverse_nursery.nearest_vocabulary(
            model, codec, states, top_k=5
        )
        for result, decoded in zip(pending, projection["items"]):
            result["output_candidates"] = decoded["candidates"]
            if decoded["candidates"]:
                result["output"] = decoded["candidates"][0]["piece"].strip()
        for result in results:
            result["strict_correct"] = (
                result["expected"] is None
                or result["output"] == result["expected"]
            )
        scored = [result for result in results if result["expected"] is not None]
        return {
            "schema": "habitus.hatched-message-probe.v1",
            "database": str(database),
            "model": str(model),
            "input_trunk": "HEAR",
            "count": len(results),
            "hear_reachability": sum(item["hear_reachable"] for item in results) / max(1, len(results)),
            "strict_output_accuracy": sum(item["strict_correct"] for item in scored) / max(1, len(scored)),
            "results": results,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--model", type=Path, default=nursery.MODEL)
    parser.add_argument("--codec", type=Path, default=nursery.CODEC)
    parser.add_argument("--once")
    parser.add_argument("--receipt", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompts = ((None, args.once),) if args.once else DEFAULT_PROBES
    result = probe(args.database, args.model, args.codec, prompts)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
