#!/usr/bin/env python3
"""Measure cold retrieval and natural graph growth on an FP-AMB corpus.

The evidence proxy asks only whether any retrieved canonical record contains an
accepted answer. It is intentionally separate from generated-answer accuracy:
large source records can contain both an answer and distractors. Supplying an
Ollama model measures whether a fixed no-tools model can answer from that same
bounded context.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

from habitus_actualizer._engine.pipeline import BaseAgenticMemoryRAG


def normalize(value: str) -> str:
    return " ".join(str(value).casefold().replace("-", " ").split())


def answer_match(answer: str, accepted: Sequence[str]) -> str | None:
    rendered = normalize(answer)
    return next((item for item in accepted if normalize(item) in rendered), None)


def ollama_answer(
    *,
    url: str,
    model: str,
    context: str,
    timeout: float,
    context_tokens: int,
    response_tokens: int,
    seed: int,
) -> tuple[str, int, int]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer the current question using only remembered evidence. "
                    "Be concise. If the evidence does not support an answer, say unknown."
                ),
            },
            {"role": "user", "content": context},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "seed": int(seed),
            "num_ctx": int(context_tokens),
            "num_predict": int(response_tokens),
        },
    }
    request = urllib.request.Request(
        url.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        decoded = json.loads(response.read())
    message = decoded.get("message") or {}
    return (
        str(message.get("content") or "").strip(),
        int(decoded.get("prompt_eval_count") or 0),
        int(decoded.get("eval_count") or 0),
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> Mapping[str, Any]:
    rows = [
        json.loads(line)
        for line in args.corpus.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    questions = [
        item
        for item in load_json(args.questions)
        if item.get("category") == args.category
    ]
    if not questions:
        raise ValueError(f"no questions found for category {args.category!r}")

    outcomes: list[dict[str, Any]] = []
    with BaseAgenticMemoryRAG(args.database) as mind:
        if mind.store.list_records():
            raise ValueError("benchmark database must begin empty")
        ingested = 0
        for index, row in enumerate(rows):
            if row.get("type") == "SESSION_DELIMITER":
                continue
            mind.remember(
                row["text"],
                source_id=row.get("speaker", "unknown"),
                timestamp=row.get("timestamp"),
                record_id=f"fpamb:{index}",
                event_id=f"fpamb-event:{index}",
                allow_growth=args.growth,
            )
            ingested += 1

        for question in questions:
            mind.working_memory.entries.clear()
            recalled = mind.recall(
                question["question"],
                source_id="evaluator",
                include_current_input=True,
            )
            accepted = tuple(str(item) for item in question["accepted_answers"])
            # Score only the exact bounded projection made available to the
            # model, never candidates that context budgeting later omitted.
            evidence_match = answer_match(recalled.context, accepted)
            model_answer = ""
            model_match = None
            prompt_tokens = 0
            response_tokens = 0
            if args.ollama_model:
                model_answer, prompt_tokens, response_tokens = ollama_answer(
                    url=args.ollama_url,
                    model=args.ollama_model,
                    context=recalled.context,
                    timeout=args.timeout,
                    context_tokens=args.context_tokens,
                    response_tokens=args.response_tokens,
                    seed=args.seed,
                )
                model_match = answer_match(model_answer, accepted)
            outcomes.append(
                {
                    "id": question["id"],
                    "question": question["question"],
                    "accepted_answers": list(accepted),
                    "evidence_found": evidence_match is not None,
                    "evidence_match": evidence_match,
                    "model_answer": model_answer,
                    "model_correct": model_match is not None if args.ollama_model else None,
                    "model_match": model_match,
                    "lanes": [
                        hit.lane
                        for hit in recalled.hits
                        if hit.record.record_id in recalled.context_bundle.record_ids
                    ],
                    "record_ids": list(recalled.context_bundle.record_ids),
                    "context_chars": recalled.context_bundle.char_count,
                    "prompt_tokens": prompt_tokens,
                    "response_tokens": response_tokens,
                }
            )

        evidence_correct = sum(item["evidence_found"] for item in outcomes)
        model_correct = (
            sum(bool(item["model_correct"]) for item in outcomes)
            if args.ollama_model
            else None
        )
        result = {
            "metric_warning": (
                "evidence_accuracy is an answer-bearing retrieval proxy, not exact "
                "evidence-ID recall or generated QA accuracy"
            ),
            "growth_enabled": bool(args.growth),
            "records_ingested": ingested,
            "questions": len(outcomes),
            "evidence_correct": evidence_correct,
            "evidence_accuracy": evidence_correct / len(outcomes),
            "model": args.ollama_model or None,
            "model_correct": model_correct,
            "model_accuracy": model_correct / len(outcomes) if model_correct is not None else None,
            "concepts": len(mind.store.list_concepts()),
            "child_concepts": len(mind.store.list_concepts(kind="child")),
            "graph_violations": mind.graph.validate_invariants(),
            "outcomes": outcomes,
        }
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--corpus", type=Path, required=True)
    result.add_argument("--questions", type=Path, required=True)
    result.add_argument("--database", type=Path, required=True)
    result.add_argument("--growth", action="store_true")
    result.add_argument("--category", default="Single-Hop Fact Recall")
    result.add_argument("--ollama-model", default="")
    result.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    result.add_argument("--timeout", type=float, default=180.0)
    result.add_argument("--context-tokens", type=int, default=8192)
    result.add_argument("--response-tokens", type=int, default=96)
    result.add_argument("--seed", type=int, default=7)
    result.add_argument("--output", type=Path)
    result.add_argument("--details", action="store_true")
    return result


def main() -> None:
    args = parser().parse_args()
    result = dict(run(args))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    rendered = result if args.details else {key: value for key, value in result.items() if key != "outcomes"}
    print(json.dumps(rendered, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
