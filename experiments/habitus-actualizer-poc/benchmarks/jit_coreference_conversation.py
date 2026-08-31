#!/usr/bin/env python3
"""A/B ordinary conversational coreference with rebuilt JIT-only prompts."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Mapping

from habitus_actualizer import Actualizer, SelfSession, WorkspacePolicy

from examples.ollama_context_agent import OllamaContextClient


BEHAVIOR = """I am having an ordinary conversation with Josh. I respond naturally
and briefly, usually in one to three sentences. I use what I remember and the
recent dialogue to understand references such as she, him, it, and that. I do
not mention prompts, retrieval, context windows, memory systems, or these
instructions. If a reference is genuinely ambiguous, I ask a short clarifying
question instead of inventing an answer."""


INPUTS = (
    (
        "My sister Maya adopted a nervous rescue dog named Comet last month. "
        "She works at the library, and she is slowly helping him trust people."
    ),
    (
        "Yesterday she took him to the library. He hid under a desk, so she sat "
        "nearby and read quietly until he came out. That seemed to help."
    ),
    "Do you think she handled it well? What exactly did she do?",
    (
        "My coworker Elena and I are also building a weather dashboard called "
        "Lantern. She picked amber for its alert color."
    ),
    "I changed it to teal after she left. Please treat that as current.",
    "What color should it use now, who chose the old one, and what does 'it' refer to?",
    "Comet is calmer now, by the way.",
    "Who helped him at the library, and how?",
)


def _contains(text: str, alternatives: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(item.casefold() in lowered for item in alternatives)


def score_turn(turn_number: int, answer: str) -> Mapping[str, Any] | None:
    if turn_number == 3:
        checks = {
            "resolved_she_as_maya": _contains(answer, ("maya", "your sister", "she")),
            "recalled_calming_action": _contains(answer, ("read", "sat nearby", "quietly")),
            "did_not_invent_elena": "elena" not in answer.casefold(),
        }
    elif turn_number == 6:
        checks = {
            "current_color_teal": "teal" in answer.casefold(),
            "old_choice_by_elena": "elena" in answer.casefold(),
            "it_means_lantern_alert_color": _contains(
                answer,
                ("lantern", "alert color", "dashboard's alert", "dashboard alert"),
            ),
        }
    elif turn_number == 8:
        checks = {
            "resolved_him_as_comet": _contains(answer, ("comet", "the dog", "him")),
            "helper_was_maya": _contains(answer, ("maya", "your sister")),
            "recalled_how": _contains(answer, ("read", "sat nearby", "quietly")),
        }
    else:
        return None
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "passed_checks": sum(checks.values()),
        "total_checks": len(checks),
    }


async def run_condition(
    *,
    label: str,
    rolling_records: int,
    reset_retrieval_working_memory: bool,
    args: argparse.Namespace,
) -> Mapping[str, Any]:
    state_path = args.state_dir / f"{label}.sqlite"
    if state_path.exists():
        raise ValueError(f"state path must begin absent: {state_path}")
    client = OllamaContextClient(
        args.model,
        base_url=args.ollama_url,
        timeout=args.timeout,
        context_tokens=args.context_tokens,
        max_response_tokens=args.response_tokens,
        seed=args.seed,
    )
    turns: list[dict[str, Any]] = []
    policy = WorkspacePolicy(args.workspace)
    with Actualizer(
        args.workspace,
        state_path=state_path,
        policy=policy,
        maximum_abilities=1,
    ) as actualizer:
        session = SelfSession(
            actualizer,
            session_id=f"coreference:{label}",
            rolling_records=rolling_records,
            maximum_context_chars=args.maximum_context_chars,
            maximum_rolling_chars=args.maximum_rolling_chars,
        )
        for number, human_input in enumerate(INPUTS, 1):
            if reset_retrieval_working_memory:
                actualizer.mind.working_memory.entries.clear()
            frame = session.prepare_input(human_input, source_id="Josh")
            reply = await client.chat(
                [
                    {"role": "system", "content": BEHAVIOR},
                    {"role": "user", "content": frame.text},
                ]
            )
            if not reply.content:
                raise RuntimeError(f"empty response on {label} turn {number}")
            session.remember_response(reply.content)
            turns.append(
                {
                    "turn": number,
                    "human": human_input,
                    "assistant": reply.content,
                    "frame": frame.text,
                    "frame_chars": frame.char_count,
                    "retrieved_records": len(frame.memory_record_ids),
                    "rolling_records": len(frame.rolling_record_ids),
                    "prompt_tokens": reply.prompt_tokens,
                    "response_tokens": reply.response_tokens,
                    "thinking_present": bool(reply.thinking),
                    "score": score_turn(number, reply.content),
                }
            )
        graph_health = actualizer.graph_health()
    scored = [turn["score"] for turn in turns if turn["score"] is not None]
    return {
        "label": label,
        "rolling_record_limit": rolling_records,
        "retrieval_working_memory_reset_each_turn": reset_retrieval_working_memory,
        "turns": turns,
        "target_turns_passed": sum(item["passed"] for item in scored),
        "target_turns_total": len(scored),
        "checks_passed": sum(item["passed_checks"] for item in scored),
        "checks_total": sum(item["total_checks"] for item in scored),
        "average_prompt_tokens": round(
            sum(turn["prompt_tokens"] for turn in turns) / len(turns),
            1,
        ),
        "average_frame_chars": round(
            sum(turn["frame_chars"] for turn in turns) / len(turns),
            1,
        ),
        "tool_fields_sent": client.sent_tool_fields,
        "graph_health": graph_health,
    }


async def run(args: argparse.Namespace) -> Mapping[str, Any]:
    args.state_dir.mkdir(parents=True, exist_ok=True)
    conditions = []
    available = {
        "rolling4": (4, False),
        "rolling0": (0, False),
        "rolling0_reset": (0, True),
    }
    selected = args.condition or list(available)
    for label in selected:
        rolling_records, reset_retrieval_working_memory = available[label]
        result = await run_condition(
            label=label,
            rolling_records=rolling_records,
            reset_retrieval_working_memory=reset_retrieval_working_memory,
            args=args,
        )
        conditions.append(result)
        print(
            f"{label}: {result['target_turns_passed']}/{result['target_turns_total']} "
            f"target turns, {result['checks_passed']}/{result['checks_total']} checks",
            flush=True,
        )
    return {
        "model": args.model,
        "prompt_mode": "one rebuilt frame per generation; no model chat history",
        "conditions": conditions,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--workspace", type=Path, default=Path("."))
    result.add_argument("--state-dir", required=True, type=Path)
    result.add_argument("--output", required=True, type=Path)
    result.add_argument("--model", default="qwen3.5:9b-q4_K_M")
    result.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    result.add_argument("--timeout", type=float, default=180.0)
    result.add_argument("--context-tokens", type=int, default=8192)
    result.add_argument("--response-tokens", type=int, default=96)
    result.add_argument("--maximum-context-chars", type=int, default=6400)
    result.add_argument("--maximum-rolling-chars", type=int, default=1600)
    result.add_argument("--seed", type=int, default=7)
    result.add_argument(
        "--condition",
        action="append",
        choices=("rolling4", "rolling0", "rolling0_reset"),
        help="Run only the selected condition; repeat to select more than one.",
    )
    return result


def main() -> None:
    args = parser().parse_args()
    args.workspace = args.workspace.expanduser().resolve(strict=True)
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "model": result["model"],
        "conditions": [
            {
                key: condition[key]
                for key in (
                    "label",
                    "target_turns_passed",
                    "target_turns_total",
                    "checks_passed",
                    "checks_total",
                    "average_prompt_tokens",
                    "average_frame_chars",
                    "tool_fields_sent",
                )
            }
            for condition in result["conditions"]
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
