from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import AbilityId, AbilityReceipt, ActualizationBatch
from .middleware import AgentOutputMiddleware
from .policy import PolicyDenied
from .runtime import Actualizer


@dataclass(frozen=True)
class CodexHostUpdate:
    """Effects produced by consuming one authoritative App Server event."""

    native_receipts: tuple[AbilityReceipt, ...] = ()
    actualization: ActualizationBatch | None = None
    app_server_requests: tuple[Mapping[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()


class CodexAppServerAdapter:
    """Pure event adapter between Codex App Server and Habitus.

    The host owns the App Server transport. It forwards notifications here and
    sends any returned ``app_server_requests`` back over that same connection.
    Habitus is therefore not a model-selectable tool and is never exposed in
    the model's tool schema.
    """

    def __init__(
        self,
        actualizer: Actualizer,
        *,
        maximum_injection_chars: int = 4000,
        maximum_result_chars: int = 1600,
    ) -> None:
        if maximum_injection_chars < 256 or maximum_result_chars < 128:
            raise ValueError("Codex injection limits are too small")
        self.actualizer = actualizer
        self.middleware = AgentOutputMiddleware(actualizer)
        self.maximum_injection_chars = int(maximum_injection_chars)
        self.maximum_result_chars = min(
            int(maximum_result_chars),
            self.maximum_injection_chars,
        )
        self._messages: dict[tuple[str, str], tuple[str, bool]] = {}
        self._seen_items: set[tuple[str, str, str]] = set()
        self._seen_turns: set[tuple[str, str]] = set()

    @staticmethod
    def _event_scope(params: Mapping[str, Any]) -> tuple[str, str]:
        thread_id = str(params.get("threadId") or "")
        turn_id = str(params.get("turnId") or "")
        return thread_id, turn_id

    @staticmethod
    def _receipt_id(thread_id: str, turn_id: str, item_id: str) -> str:
        digest = hashlib.sha256(
            f"{thread_id}\0{turn_id}\0{item_id}".encode("utf-8")
        ).hexdigest()[:24]
        return f"receipt:codex:{digest}"

    @staticmethod
    def _turn_marker(thread_id: str, turn_id: str) -> str:
        digest = hashlib.sha256(
            f"{thread_id}\0{turn_id}".encode("utf-8")
        ).hexdigest()[:24]
        return f"codex.processed_turn.{digest}"

    def _workspace_cwd(self, raw: Any) -> str:
        path = Path(str(raw or self.actualizer.policy.root)).expanduser().resolve()
        try:
            relative = path.relative_to(self.actualizer.policy.root)
        except ValueError as error:
            raise PolicyDenied("Codex receipt cwd is outside the configured workspace") from error
        return "." if not relative.parts else relative.as_posix()

    def _observe_command(
        self,
        item: Mapping[str, Any],
        *,
        thread_id: str,
        turn_id: str,
    ) -> AbilityReceipt | None:
        item_id = str(item.get("id") or "")
        status = str(item.get("status") or "").casefold()
        if not item_id or status not in {"completed", "failed"}:
            return None
        receipt_id = self._receipt_id(thread_id, turn_id, item_id)
        if self.actualizer.mind.store.get_record(receipt_id) is not None:
            return None
        workspace_cwd = self._workspace_cwd(item.get("cwd"))
        exit_code = item.get("exitCode")
        succeeded = status == "completed" and exit_code == 0
        # A missing exit code is not enough evidence for positive learning.
        verified = status == "failed" or exit_code is not None
        raw_output = str(item.get("aggregatedOutput") or "")
        observed_output, truncated = self.actualizer.policy.truncate(raw_output)
        command = item.get("command")
        if isinstance(command, list):
            command_text = " ".join(str(part) for part in command)
        else:
            command_text = str(command or "")
        output = {
            "command": command_text,
            "cwd": workspace_cwd,
            "exit_code": exit_code,
            "output": observed_output,
            "output_truncated": truncated,
            "duration_ms": item.get("durationMs"),
            "codex_item_id": item_id,
        }
        error = "" if succeeded else (
            observed_output or f"Codex command status was {status}"
        )
        return self.actualizer.observe_ability_result(
            AbilityId.RUN,
            status="success" if succeeded else "error",
            verified=verified,
            arguments={"command": command_text, "cwd": workspace_cwd},
            output=output,
            error=error,
            phrase=f"I ran {command_text}".strip(),
            source_id="codex-app-server",
            receipt_id=receipt_id,
            metadata={
                "codex_thread_id": thread_id,
                "codex_turn_id": turn_id,
                "codex_item_id": item_id,
                "codex_item_type": "commandExecution",
            },
        )

    @staticmethod
    def _file_digest(path: Path) -> str | None:
        if not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _observe_file_change(
        self,
        item: Mapping[str, Any],
        *,
        thread_id: str,
        turn_id: str,
    ) -> AbilityReceipt | None:
        item_id = str(item.get("id") or "")
        status = str(item.get("status") or "").casefold()
        if not item_id or status not in {"completed", "failed"}:
            return None
        receipt_id = self._receipt_id(thread_id, turn_id, item_id)
        if self.actualizer.mind.store.get_record(receipt_id) is not None:
            return None
        changes = item.get("changes")
        if not isinstance(changes, list) or not changes:
            return None
        observations: list[dict[str, Any]] = []
        read_back_verified = status == "completed"
        for raw_change in changes:
            if not isinstance(raw_change, Mapping):
                read_back_verified = False
                continue
            raw_path = str(raw_change.get("path") or "")
            resolved = self.actualizer.policy.resolve_path(
                raw_path,
                cwd=self.actualizer.policy.root,
                require_exists=False,
            )
            kind = str(raw_change.get("kind") or "update").casefold()
            exists = resolved.exists()
            expected_exists = kind not in {"delete", "deleted", "remove", "removed"}
            state_matches = exists == expected_exists
            read_back_verified = read_back_verified and state_matches
            observations.append(
                {
                    "path": self.actualizer.workspace.display_path(resolved),
                    "kind": kind,
                    "exists": exists,
                    "sha256": self._file_digest(resolved),
                    "state_matches": state_matches,
                }
            )
        succeeded = status == "completed" and read_back_verified
        output = {
            "changes": observations,
            "read_back_verified": read_back_verified,
            "codex_item_id": item_id,
        }
        error = "" if succeeded else (
            "Codex file change did not match the observed workspace state"
            if status == "completed"
            else f"Codex file change status was {status}"
        )
        return self.actualizer.observe_ability_result(
            AbilityId.WRITE,
            status="success" if succeeded else "error",
            verified=(status == "failed" or read_back_verified),
            arguments={"changes": observations},
            output=output,
            error=error,
            phrase="I changed workspace files",
            source_id="codex-app-server",
            receipt_id=receipt_id,
            metadata={
                "codex_thread_id": thread_id,
                "codex_turn_id": turn_id,
                "codex_item_id": item_id,
                "codex_item_type": "fileChange",
            },
        )

    def _observe_native_item(
        self,
        item: Mapping[str, Any],
        *,
        thread_id: str,
        turn_id: str,
    ) -> AbilityReceipt | None:
        item_type = str(item.get("type") or "")
        if item_type == "commandExecution":
            return self._observe_command(
                item,
                thread_id=thread_id,
                turn_id=turn_id,
            )
        if item_type == "fileChange":
            return self._observe_file_change(
                item,
                thread_id=thread_id,
                turn_id=turn_id,
            )
        return None

    def _render_observation(self, batch: ActualizationBatch) -> str:
        sentences: list[str] = []
        for receipt in batch.receipts:
            if receipt.status == "success" and receipt.verified:
                rendered = json.dumps(
                    receipt.output,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
                if len(rendered) > self.maximum_result_chars:
                    suffix = "...[evidence omitted; full result is in the receipt]"
                    rendered = rendered[: self.maximum_result_chars - len(suffix)] + suffix
                sentences.append(
                    f"I completed {receipt.ability_id.value} successfully and observed {rendered}. "
                    f"My receipt is {receipt.return_record_id}."
                )
            else:
                sentences.append(
                    f"I attempted {receipt.ability_id.value}, but it failed with {receipt.error}. "
                    f"My receipt is {receipt.return_record_id}."
                )
        combined = " ".join(sentences)
        if len(combined) <= self.maximum_injection_chars:
            return combined
        suffix = "...[more results omitted; full results remain in receipts]"
        return combined[: self.maximum_injection_chars - len(suffix)] + suffix

    def _injection_request(
        self,
        thread_id: str,
        batch: ActualizationBatch,
    ) -> Mapping[str, Any]:
        return {
            "method": "thread/inject_items",
            "id": f"habitus:{uuid.uuid4().hex}",
            "params": {
                "threadId": thread_id,
                "items": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": self._render_observation(batch),
                            }
                        ],
                    }
                ],
            },
        }

    async def consume(self, event: Mapping[str, Any]) -> CodexHostUpdate:
        """Consume one decoded App Server JSON-RPC message."""
        method = str(event.get("method") or "")
        params = event.get("params")
        if not isinstance(params, Mapping):
            return CodexHostUpdate()
        thread_id, turn_id = self._event_scope(params)

        if method == "item/completed":
            item = params.get("item")
            if not isinstance(item, Mapping):
                return CodexHostUpdate()
            item_id = str(item.get("id") or "")
            dedupe_key = (thread_id, turn_id, item_id)
            if item_id and dedupe_key in self._seen_items:
                return CodexHostUpdate()
            if item_id:
                self._seen_items.add(dedupe_key)

            if str(item.get("type") or "") == "agentMessage":
                text = str(item.get("text") or "")
                phase = str(item.get("phase") or "")
                if text and (phase in {"", "final_answer"}):
                    current = self._messages.get((thread_id, turn_id))
                    authoritative = phase == "final_answer"
                    if current is None or authoritative or not current[1]:
                        self._messages[(thread_id, turn_id)] = (text, authoritative)
                return CodexHostUpdate()

            try:
                receipt = self._observe_native_item(
                    item,
                    thread_id=thread_id,
                    turn_id=turn_id,
                )
            except (OSError, PolicyDenied, ValueError) as error:
                return CodexHostUpdate(warnings=(str(error),))
            return CodexHostUpdate(
                native_receipts=((receipt,) if receipt is not None else ()),
            )

        if method != "turn/completed":
            return CodexHostUpdate()
        turn = params.get("turn")
        if not isinstance(turn, Mapping):
            return CodexHostUpdate()
        turn_id = str(turn.get("id") or turn_id)
        scope = (thread_id, turn_id)
        if scope in self._seen_turns:
            return CodexHostUpdate()
        self._seen_turns.add(scope)
        if str(turn.get("status") or "").casefold() != "completed":
            self._messages.pop(scope, None)
            return CodexHostUpdate()
        stored = self._messages.pop(scope, None)
        if stored is None or not stored[0]:
            return CodexHostUpdate()
        marker = self._turn_marker(thread_id, turn_id)
        marker_state = self.actualizer.mind.store.get_metadata(marker)
        if marker_state:
            return CodexHostUpdate(
                warnings=(
                    f"Codex turn was already {marker_state}; it was not actualized again",
                )
            )
        # At-most-once externalization: a crash after this write leaves a
        # reviewable 'processing' marker instead of repeating a mutation.
        self.actualizer.mind.store.set_metadata(marker, "processing")
        try:
            result = await self.middleware.process(
                {"role": "assistant", "content": stored[0]}
            )
        except Exception:
            self.actualizer.mind.store.set_metadata(marker, "uncertain")
            raise
        self.actualizer.mind.store.set_metadata(marker, "complete")
        requests = (
            (self._injection_request(thread_id, result.batch),)
            if result.batch.receipts
            else ()
        )
        return CodexHostUpdate(
            actualization=result.batch,
            app_server_requests=requests,
        )
