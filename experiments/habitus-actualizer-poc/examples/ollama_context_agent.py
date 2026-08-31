#!/usr/bin/env python3
"""Bounded context-only Ollama loop backed by Habitus workspace abilities."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from habitus_actualizer import AbilityId, Actualizer, SelfSession, WorkspacePolicy


DEFAULT_BEHAVIOR = """I work conversationally inside one bounded workspace.
I never invent file contents, command output, or completed work. When I need to
inspect or act on the workspace, I state exactly one immediate action in a
plain first-person sentence and then stop. I do not add a plan, code block,
predicted result, or explanation to an action sentence. I put the exact path or
command in backticks, for example: I'll list `.`. If I do not know a path or
filename, I list the current directory instead of guessing it. I read available
project guidance before choosing a specialized script. After I receive an
observed result, I continue from that evidence. When the request is complete, I
answer naturally without announcing another action. Code fences and predicted
shell transcripts do not perform actions. Correctly phrased first-person actions
are carried out by my workspace, so I never claim that I lack workspace access.
The available interpreter for Python programs is `python3`."""


@dataclass(frozen=True)
class OllamaReply:
    content: str
    thinking: str
    prompt_tokens: int
    response_tokens: int


class OllamaContextClient:
    """Minimal chat client that deliberately has no tool parameter."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 180.0,
        context_tokens: int = 8192,
        max_response_tokens: int = 256,
        seed: int = 7,
    ) -> None:
        self.model = model
        self.url = base_url.rstrip("/") + "/api/chat"
        self.timeout = float(timeout)
        self.context_tokens = int(context_tokens)
        self.max_response_tokens = int(max_response_tokens)
        self.seed = int(seed)
        self.request_count = 0
        self.sent_tool_fields = 0

    def _chat_sync(self, messages: list[Mapping[str, str]]) -> OllamaReply:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.1,
                "seed": self.seed,
                "num_ctx": self.context_tokens,
                "num_predict": self.max_response_tokens,
            },
        }
        self.request_count += 1
        self.sent_tool_fields += int("tools" in payload)
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            decoded = json.loads(response.read())
        message = decoded.get("message") or {}
        return OllamaReply(
            content=str(message.get("content") or "").strip(),
            thinking=str(message.get("thinking") or "").strip(),
            prompt_tokens=int(decoded.get("prompt_eval_count") or 0),
            response_tokens=int(decoded.get("eval_count") or 0),
        )

    async def chat(self, messages: list[Mapping[str, str]]) -> OllamaReply:
        return await asyncio.to_thread(self._chat_sync, list(messages))


def looks_like_unexecuted_action(text: str) -> bool:
    lowered = str(text).casefold().replace("’", "'")
    commitments = ("i'll ", "i will ", "let me ", "i need to ", "i am going to ")
    return "```" in lowered or any(marker in lowered for marker in commitments)


async def run_agent(args: argparse.Namespace) -> Mapping[str, Any]:
    workspace = Path(args.workspace).expanduser().resolve(strict=True)
    policy = WorkspacePolicy(
        workspace,
        allow_write=args.allow_write,
        allowed_commands=WorkspacePolicy.normalize_allowed_commands(args.allow_command),
    )
    client = OllamaContextClient(
        args.model,
        base_url=args.ollama_url,
        timeout=args.timeout,
        context_tokens=args.context_tokens,
        max_response_tokens=args.max_response_tokens,
        seed=args.seed,
    )
    pulses: list[dict[str, Any]] = []
    final_answer = ""
    required_abilities = set(args.require_ability)
    successful_abilities: set[str] = set()
    with Actualizer(
        workspace,
        state_path=args.state,
        policy=policy,
        maximum_abilities=1,
    ) as actualizer:
        session = SelfSession(
            actualizer,
            session_id=args.session_id,
            maximum_context_chars=args.maximum_context_chars,
        )
        frame = session.prepare_input(args.task, source_id="human")
        for pulse in range(1, args.max_pulses + 1):
            messages: list[Mapping[str, str]] = [
                {"role": "system", "content": DEFAULT_BEHAVIOR},
                {"role": "user", "content": frame.text},
            ]
            reply = await client.chat(messages)
            if not reply.content:
                raise RuntimeError("Ollama returned an empty assistant message")
            processed = await session.process_output(reply.content)
            pulse_record = {
                "pulse": pulse,
                "context_chars": frame.char_count,
                "assistant": reply.content,
                "thinking_present": bool(reply.thinking),
                "prompt_tokens": reply.prompt_tokens,
                "response_tokens": reply.response_tokens,
                "requests": [
                    {
                        "ability": request.ability_id.value,
                        "arguments": dict(request.arguments),
                        "confidence": request.confidence,
                    }
                    for request in processed.batch.requests
                ],
                "receipts": [
                    {
                        "ability": receipt.ability_id.value,
                        "status": receipt.status,
                        "verified": receipt.verified,
                        "output": receipt.output,
                        "error": receipt.error,
                        "receipt_id": receipt.return_record_id,
                    }
                    for receipt in processed.batch.receipts
                ],
                "suppressed": [
                    {
                        "ability": item.ability_id.value if item.ability_id else None,
                        "reason": item.reason,
                    }
                    for item in processed.batch.suppressed
                ],
                "perception": processed.perception,
            }
            pulses.append(pulse_record)
            successful_abilities.update(
                receipt.ability_id.value
                for receipt in processed.batch.receipts
                if receipt.status == "success" and receipt.verified
            )
            if processed.batch.receipts or processed.batch.suppressed:
                frame = session.prepare_observation(processed.perception)
                continue
            if looks_like_unexecuted_action(reply.content):
                frame = session.prepare_input(
                    "No workspace action was recognized or performed. Do not treat the "
                    "plan or code block as a result. If action is still needed, restate "
                    "exactly one immediate action on one line in this form: I'll list "
                    "`path`; I'll read `path`; or I'll run `exact command`.",
                    source_id="evaluator",
                    stability_delta=-0.2,
                    set_focus=False,
                )
                continue
            missing = sorted(required_abilities - successful_abilities)
            if missing:
                frame = session.prepare_input(
                    "The task is not verified complete. No successful result has been "
                    f"observed for: {', '.join(missing)}. Continue from the workspace "
                    "evidence with one exact immediate action; do not ask me for a path "
                    "that can be discovered inside the workspace.",
                    source_id="evaluator",
                    stability_delta=-0.2,
                    set_focus=False,
                )
                continue
            final_answer = reply.content
            break
        graph_health = actualizer.graph_health()
    result = {
        "model": args.model,
        "task": args.task,
        "workspace": str(workspace),
        "completed": bool(final_answer),
        "final_answer": final_answer,
        "pulse_count": len(pulses),
        "pulses": pulses,
        "ollama_request_count": client.request_count,
        "ollama_tool_fields_sent": client.sent_tool_fields,
        "context_mode": "bounded-jit-memory",
        "required_abilities": sorted(required_abilities),
        "successful_abilities": sorted(successful_abilities),
        "graph_health": graph_health,
    }
    if args.trace:
        trace_path = Path(args.trace).expanduser()
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(
            json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("task")
    result.add_argument("--workspace", default=".")
    result.add_argument("--state")
    result.add_argument("--trace")
    result.add_argument("--model", default="granite4.1:8b")
    result.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    result.add_argument("--timeout", type=float, default=180.0)
    result.add_argument("--context-tokens", type=int, default=8192)
    result.add_argument("--max-response-tokens", type=int, default=256)
    result.add_argument("--session-id", default="ollama-live-demo")
    result.add_argument(
        "--maximum-context-chars",
        "--maximum-history-chars",
        dest="maximum_context_chars",
        type=int,
        default=12_000,
    )
    result.add_argument("--seed", type=int, default=7)
    result.add_argument("--max-pulses", type=int, default=6)
    result.add_argument("--allow-write", action="store_true")
    result.add_argument("--allow-command", action="append", default=[])
    result.add_argument(
        "--require-ability",
        action="append",
        choices=[item.value for item in AbilityId],
        default=[],
        help="Require a verified receipt before accepting the model's final answer.",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        result = asyncio.run(run_agent(args))
    except (OSError, RuntimeError, ValueError, urllib.error.URLError) as error:
        print(f"agent probe failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
