from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping

from .continuous import AgentLedger, ContinuousAgent, WorkspaceSensor, step_to_dict
from .policy import WorkspacePolicy
from .runtime import Actualizer
from .self_session import SelfSession


ENGAGED_BEHAVIOR = """I work conversationally inside one bounded workspace.
I never invent file contents, command output, or completed work. When I need to
inspect or act, I state exactly one immediate action in a plain first-person
sentence and stop. To inspect a file I say: I'll read `path`. I do not replace
that sentence with `cat`, a bare command, or a code block. I put the exact path
or command in backticks. I continue from observed results. When the current
request is complete, I answer naturally. I have no tool-call syntax; correctly
phrased ordinary action statements are handled by my environment."""


IDLE_BEHAVIOR = """This is a private quiet cycle, not a message to another person.
I do not invent a new assignment, urgency, observation, or completed work. I may
state one grounded immediate workspace action in first person with its exact
path or command in backticks, then stop. Otherwise I produce one short private
thought about something genuinely present in my memory or current attention.
I never emit a bare command or a placeholder path. If I need orientation, the
grounded action is: I'll list `.`. I do not greet, ask a question, or pretend
someone is listening."""


class OllamaLanguageDriver:
    """Minimal no-tools Ollama driver for the continuous host."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 180.0,
        context_tokens: int = 8192,
        maximum_response_tokens: int = 256,
        seed: int = 7,
        trace_jsonl: str | Path | None = None,
    ) -> None:
        self.model = str(model)
        self.url = base_url.rstrip("/") + "/api/chat"
        self.timeout = float(timeout)
        self.context_tokens = int(context_tokens)
        self.maximum_response_tokens = int(maximum_response_tokens)
        self.seed = int(seed)
        self.trace_jsonl = (
            Path(trace_jsonl).expanduser() if trace_jsonl is not None else None
        )
        if self.trace_jsonl is not None:
            self.trace_jsonl.parent.mkdir(parents=True, exist_ok=True)
        self.request_count = 0
        self.sent_tool_fields = 0

    def _record_trace(
        self,
        *,
        call_index: int,
        mode: str,
        behavior: str,
        frame: str,
        response: str,
        decoded: Mapping[str, object],
        error: str = "",
    ) -> None:
        if self.trace_jsonl is None:
            return
        entry = {
            "timestamp": time.time(),
            "call_index": int(call_index),
            "model": self.model,
            "mode": str(mode),
            "system": str(behavior),
            "frame": str(frame),
            "frame_chars": len(str(frame)),
            "response": str(response),
            "prompt_eval_count": decoded.get("prompt_eval_count"),
            "eval_count": decoded.get("eval_count"),
            "tools_field_present": False,
            "error": str(error),
        }
        with self.trace_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True, default=str) + "\n")

    def _generate_sync(self, frame: str, mode: str) -> str:
        behavior = IDLE_BEHAVIOR if mode in {"idle", "notice"} else ENGAGED_BEHAVIOR
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": behavior},
                {"role": "user", "content": str(frame)},
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.1,
                "seed": self.seed,
                "num_ctx": self.context_tokens,
                "num_predict": self.maximum_response_tokens,
            },
        }
        self.request_count += 1
        call_index = self.request_count
        self.sent_tool_fields += int("tools" in payload)
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                decoded = json.loads(response.read())
        except Exception as caught:
            self._record_trace(
                call_index=call_index,
                mode=mode,
                behavior=behavior,
                frame=frame,
                response="",
                decoded={},
                error=f"{type(caught).__name__}: {caught}",
            )
            raise
        generated = str((decoded.get("message") or {}).get("content") or "").strip()
        self._record_trace(
            call_index=call_index,
            mode=mode,
            behavior=behavior,
            frame=frame,
            response=generated,
            decoded=decoded,
        )
        return generated

    async def generate(self, frame: str, *, mode: str) -> str:
        return await asyncio.to_thread(self._generate_sync, frame, mode)


def _workspace(value: str) -> Path:
    return Path(value).expanduser().resolve(strict=True)


def _ledger_path(workspace: Path, supplied: str | None) -> Path:
    return (
        Path(supplied).expanduser()
        if supplied
        else workspace / ".habitus" / "agent-loop.sqlite"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="habitus-agent",
        description="Run or communicate with one persistent Habitus agent loop.",
    )
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--ledger")
    subparsers = parser.add_subparsers(dest="command", required=True)

    send = subparsers.add_parser("send", help="queue a conversational message")
    send.add_argument("text")
    send.add_argument("--source", default="human")
    send.add_argument("--stability", type=float, default=0.0)

    notice = subparsers.add_parser("notice", help="queue a non-conversational notice")
    notice.add_argument("text")
    notice.add_argument("--source", default="environment")
    notice.add_argument("--stability", type=float, default=0.0)
    notice.add_argument(
        "--feature",
        action="append",
        default=[],
        help="add one shared non-language sensory feature",
    )

    subparsers.add_parser("status", help="show persistent queue and cycle counts")

    outbox = subparsers.add_parser("outbox", help="show outward speech")
    outbox.add_argument("--all", action="store_true")
    outbox.add_argument("--mark-delivered", action="store_true")

    run = subparsers.add_parser("run", help="run the persistent cognitive loop")
    run.add_argument("--state")
    run.add_argument("--model", default="qwen3.5:9b-q4_K_M")
    run.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    run.add_argument("--timeout", type=float, default=180.0)
    run.add_argument("--context-tokens", type=int, default=8192)
    run.add_argument("--max-response-tokens", type=int, default=256)
    run.add_argument("--seed", type=int, default=7)
    run.add_argument(
        "--trace-jsonl",
        help="append exact model-facing frames and responses to a diagnostic JSONL file",
    )
    run.add_argument("--session-id", default="continuous:self")
    run.add_argument("--maximum-context-chars", type=int, default=12_000)
    run.add_argument("--max-event-steps", type=int, default=8)
    run.add_argument("--max-idle-steps", type=int, default=2)
    run.add_argument("--idle-seconds", type=float, default=60.0)
    run.add_argument("--idle-action-budget", type=int, default=4)
    run.add_argument(
        "--autonomous-actions",
        action="store_true",
        help="allow idle generations to activate workspace abilities",
    )
    run.add_argument("--poll-seconds", type=float, default=0.5)
    run.add_argument("--max-cycles", type=int)
    run.add_argument("--allow-write", action="store_true")
    run.add_argument("--allow-command", action="append", default=[])
    run.add_argument("--recover-after-seconds", type=float, default=0.0)
    run.add_argument(
        "--no-workspace-sensor",
        action="store_true",
        help="disable bounded workspace-change notices",
    )
    return parser


async def _run(args: argparse.Namespace, workspace: Path, ledger_path: Path) -> int:
    policy = WorkspacePolicy(
        workspace,
        allow_write=args.allow_write,
        allowed_commands=WorkspacePolicy.normalize_allowed_commands(args.allow_command),
    )
    driver = OllamaLanguageDriver(
        args.model,
        base_url=args.ollama_url,
        timeout=args.timeout,
        context_tokens=args.context_tokens,
        maximum_response_tokens=args.max_response_tokens,
        seed=args.seed,
        trace_jsonl=args.trace_jsonl,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop.set)
        except NotImplementedError:
            pass

    state_path = Path(args.state).expanduser() if args.state else None
    with AgentLedger(ledger_path) as ledger:
        recovered = ledger.recover_processing(
            older_than_seconds=args.recover_after_seconds
        )
        if recovered:
            print(_json_line({"kind": "recovery", "events": recovered}), flush=True)
        with Actualizer(
            workspace,
            state_path=state_path,
            policy=policy,
            maximum_abilities=1,
        ) as actualizer:
            session = SelfSession(
                actualizer,
                session_id=args.session_id,
                maximum_context_chars=args.maximum_context_chars,
            )
            agent = ContinuousAgent(
                session,
                driver,
                ledger,
                maximum_event_steps=args.max_event_steps,
                maximum_idle_steps=args.max_idle_steps,
                idle_interval_seconds=args.idle_seconds,
                idle_action_budget=args.idle_action_budget,
                allow_idle_actions=args.autonomous_actions,
                workspace_sensor=(
                    None if args.no_workspace_sensor else WorkspaceSensor(workspace)
                ),
            )

            async def report(step) -> None:
                print(_json_line({"kind": "agent_step", **step_to_dict(step)}), flush=True)

            completed = await agent.run_forever(
                poll_seconds=args.poll_seconds,
                stop_event=stop,
                maximum_cycles=args.max_cycles,
                on_step=report,
            )
            print(
                _json_line(
                    {
                        "kind": "agent_stopped",
                        "cycles": completed,
                        "ollama_requests": driver.request_count,
                        "ollama_tool_fields_sent": driver.sent_tool_fields,
                        "graph_health": actualizer.graph_health(),
                    }
                ),
                flush=True,
            )
    return 0


def _json_line(value: Mapping[str, object]) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = _workspace(args.workspace)
    ledger_path = _ledger_path(workspace, args.ledger)
    try:
        if args.command in {"send", "notice"}:
            with AgentLedger(ledger_path) as ledger:
                event = ledger.enqueue(
                    args.text,
                    kind="message" if args.command == "send" else "notice",
                    source_id=args.source,
                    stability_delta=args.stability,
                    sensory_features=tuple(args.feature) if args.command == "notice" else (),
                )
            print(_json_line(asdict_event(event)))
            return 0
        if args.command == "status":
            with AgentLedger(ledger_path) as ledger:
                print(_json_line(ledger.status()))
            return 0
        if args.command == "outbox":
            with AgentLedger(ledger_path) as ledger:
                messages = ledger.outbox(undelivered_only=not args.all)
                if args.mark_delivered:
                    ledger.mark_delivered([str(item["message_id"]) for item in messages])
                print(json.dumps(messages, indent=2, sort_keys=True, default=str))
            return 0
        return asyncio.run(_run(args, workspace, ledger_path))
    except (OSError, RuntimeError, ValueError, sqlite3.Error, urllib.error.URLError) as error:
        print(f"habitus agent failed: {error}", file=sys.stderr)
        return 2


def asdict_event(event) -> Mapping[str, object]:
    return {
        "event_id": event.event_id,
        "kind": event.kind,
        "source_id": event.source_id,
        "text": event.text,
        "status": event.status,
        "sensory_features": event.sensory_features,
        "created_at": event.created_at,
    }


if __name__ == "__main__":
    raise SystemExit(main())
