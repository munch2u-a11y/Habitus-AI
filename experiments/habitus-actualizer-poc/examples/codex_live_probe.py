#!/usr/bin/env python3
"""One-turn Codex App Server probe with Habitus event synchronization.

This is intentionally a probe rather than a replacement terminal UI. It keeps
Codex read-only by default, observes authoritative App Server items, runs the
schema-free post-generation actualizer, and injects any resulting receipts into
the same Codex thread before shutting down.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

from habitus_actualizer import (
    AbilityReceipt,
    Actualizer,
    CodexAppServerAdapter,
    WorkspacePolicy,
)


class AppServerProbe:
    def __init__(
        self,
        workspace: Path,
        adapter: CodexAppServerAdapter,
        *,
        timeout: float,
    ) -> None:
        self.workspace = workspace
        self.adapter = adapter
        self.timeout = timeout
        self.process: asyncio.subprocess.Process | None = None
        self.final_messages: list[str] = []
        self.native_receipts: list[Mapping[str, Any]] = []
        self.actualized_receipts: list[Mapping[str, Any]] = []
        self.injection_chars: list[int] = []
        self.warnings: list[str] = []
        self._turn_statuses: dict[str, str] = {}
        self._request_number = 0
        self._injection_ids: set[str] = set()
        self._injection_responses: set[str] = set()

    async def __aenter__(self) -> "AppServerProbe":
        executable = shutil.which("codex")
        if executable is None:
            raise RuntimeError("codex executable was not found on PATH")
        self.process = await asyncio.create_subprocess_exec(
            executable,
            "app-server",
            "--listen",
            "stdio://",
            cwd=str(self.workspace),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.process is None:
            return
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self.process.terminate()
            await self.process.wait()

    async def _send(self, message: Mapping[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("app-server is not running")
        self.process.stdin.write(
            (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        )
        await self.process.stdin.drain()

    async def _read(self) -> Mapping[str, Any]:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("app-server is not running")
        line = await asyncio.wait_for(self.process.stdout.readline(), self.timeout)
        if not line:
            stderr = ""
            if self.process.stderr is not None:
                stderr = (await self.process.stderr.read()).decode("utf-8", "replace")
            raise RuntimeError(
                f"app-server exited before completing the probe: {stderr.strip()}"
            )
        decoded = json.loads(line)
        if not isinstance(decoded, Mapping):
            raise RuntimeError("app-server emitted a non-object JSON message")
        return decoded

    def _next_id(self) -> int:
        self._request_number += 1
        return self._request_number

    async def _handle(self, message: Mapping[str, Any]) -> None:
        if "id" in message and not message.get("method"):
            request_id = str(message["id"])
            if request_id in self._injection_ids:
                self._injection_responses.add(request_id)
            return
        update = await self.adapter.consume(message)
        self.warnings.extend(update.warnings)
        self.native_receipts.extend(
            self._receipt_summary(receipt) for receipt in update.native_receipts
        )
        if update.actualization is not None:
            self.actualized_receipts.extend(
                self._receipt_summary(receipt)
                for receipt in update.actualization.receipts
            )
        for request in update.app_server_requests:
            request_id = str(request["id"])
            self._injection_ids.add(request_id)
            content = request["params"]["items"][0]["content"][0]["text"]
            self.injection_chars.append(len(str(content)))
            await self._send(request)
        if message.get("method") == "item/completed":
            params = message.get("params")
            item = params.get("item") if isinstance(params, Mapping) else None
            if (
                isinstance(item, Mapping)
                and item.get("type") == "agentMessage"
                and item.get("phase") in {None, "final_answer"}
                and item.get("text")
            ):
                self.final_messages.append(str(item["text"]))
        if message.get("method") == "turn/completed":
            params = message.get("params")
            turn = params.get("turn") if isinstance(params, Mapping) else None
            if isinstance(turn, Mapping) and turn.get("id"):
                self._turn_statuses[str(turn["id"])] = str(
                    turn.get("status") or ""
                )

    @staticmethod
    def _receipt_summary(receipt: AbilityReceipt) -> Mapping[str, Any]:
        output = receipt.output if isinstance(receipt.output, Mapping) else {}
        return {
            "ability": receipt.ability_id.value,
            "status": receipt.status,
            "verified": receipt.verified,
            "receipt_id": receipt.return_record_id,
            "path": output.get("path"),
            "sha256": output.get("sha256"),
            "error": receipt.error,
        }

    async def _request(self, method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        request_id = self._next_id()
        await self._send({"method": method, "id": request_id, "params": dict(params)})
        while True:
            message = await self._read()
            if message.get("id") == request_id and not message.get("method"):
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                result = message.get("result")
                return result if isinstance(result, Mapping) else {}
            await self._handle(message)

    async def run(self, prompt: str, *, model: str | None = None) -> Mapping[str, Any]:
        await self._request(
            "initialize",
            {
                "clientInfo": {
                    "name": "habitus_actualizer_probe",
                    "title": "Habitus Actualizer Probe",
                    "version": "0.1.0",
                }
            },
        )
        await self._send({"method": "initialized", "params": {}})
        thread_params: dict[str, Any] = {
            "cwd": str(self.workspace),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "serviceName": "habitus_actualizer_probe",
        }
        if model:
            thread_params["model"] = model
        started = await self._request("thread/start", thread_params)
        thread = started.get("thread")
        if not isinstance(thread, Mapping) or not thread.get("id"):
            raise RuntimeError("thread/start returned no thread id")
        thread_id = str(thread["id"])
        turn_started = await self._request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
                "cwd": str(self.workspace),
                "approvalPolicy": "never",
                "sandboxPolicy": {
                    "type": "readOnly",
                    "networkAccess": False,
                },
            },
        )
        turn = turn_started.get("turn")
        turn_id = str(turn.get("id") or "") if isinstance(turn, Mapping) else ""
        turn_status = self._turn_statuses.get(turn_id, "")
        while turn_status not in {"completed", "failed", "interrupted"}:
            message = await self._read()
            await self._handle(message)
            turn_status = self._turn_statuses.get(turn_id, "")
        while self._injection_responses != self._injection_ids:
            await self._handle(await self._read())
        return {
            "thread_id": thread_id,
            "turn_id": turn_id,
            "turn_status": turn_status,
            "final_messages": self.final_messages,
            "native_receipts": self.native_receipts,
            "actualized_receipts": self.actualized_receipts,
            "injection_chars": self.injection_chars,
            "injections_acknowledged": len(self._injection_responses),
            "warnings": self.warnings,
        }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("prompt")
    result.add_argument("--workspace", default=".")
    result.add_argument("--state")
    result.add_argument("--model")
    result.add_argument("--timeout", type=float, default=180.0)
    return result


async def async_main() -> int:
    args = parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve(strict=True)
    state = Path(args.state).expanduser() if args.state else None
    policy = WorkspacePolicy(workspace)
    with Actualizer(workspace, state_path=state, policy=policy) as actualizer:
        adapter = CodexAppServerAdapter(actualizer)
        async with AppServerProbe(
            workspace,
            adapter,
            timeout=args.timeout,
        ) as probe:
            result = await probe.run(args.prompt, model=args.model)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["turn_status"] == "completed" else 1


def main() -> int:
    try:
        return asyncio.run(async_main())
    except (asyncio.TimeoutError, OSError, RuntimeError, ValueError) as error:
        print(f"probe failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
