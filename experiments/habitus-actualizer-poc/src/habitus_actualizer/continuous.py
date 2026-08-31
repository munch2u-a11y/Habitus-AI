from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Protocol

from .contracts import AbilityId
from .self_session import SelfFrame, SelfSession


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class AgentEvent:
    event_id: str
    kind: str
    source_id: str
    text: str
    stability_delta: float
    sensory_features: tuple[str, ...]
    status: str
    attempts: int
    created_at: float


@dataclass(frozen=True)
class AgentCycle:
    cycle_id: str
    event_id: str | None
    mode: str
    step: int
    status: str
    model_output: str
    spoken_text: str
    perception: str
    receipts: tuple[Mapping[str, Any], ...]
    created_at: float


@dataclass(frozen=True)
class AgentStep:
    mode: str
    event_id: str | None
    status: str
    cycles: tuple[AgentCycle, ...]
    spoken_text: str = ""
    error: str = ""


class LanguageDriver(Protocol):
    async def generate(self, frame: str, *, mode: str) -> str:
        """Return one ordinary language generation without a tool channel."""


class WorkspaceSensor:
    """Bounded, content-free workspace change perception."""

    def __init__(self, root: str | Path, *, maximum_entries: int = 256) -> None:
        self.root = Path(root).expanduser().resolve(strict=True)
        self.maximum_entries = max(1, int(maximum_entries))

    def _snapshot(self) -> dict[str, list[Any]]:
        items: dict[str, list[Any]] = {}
        blocked = {".git", ".habitus", ".env", "secrets.json", "credentials.json"}
        for current, directories, filenames in os.walk(self.root):
            current_path = Path(current)
            relative_directory = current_path.relative_to(self.root)
            if len(relative_directory.parts) >= 2:
                directories[:] = []
            directories[:] = sorted(
                name for name in directories if name.casefold() not in blocked
            )
            for name in sorted((*directories, *filenames)):
                if name.casefold() in blocked:
                    continue
                path = current_path / name
                relative = path.relative_to(self.root).as_posix()
                try:
                    stat = path.stat()
                except FileNotFoundError:
                    continue
                items[relative] = [
                    "directory" if path.is_dir() else "file",
                    int(stat.st_size) if path.is_file() else None,
                    int(stat.st_mtime_ns),
                ]
                if len(items) >= self.maximum_entries:
                    return items
        return items

    def poll(self, ledger: "AgentLedger") -> AgentEvent | None:
        current = self._snapshot()
        serialized = _json(current)
        signature = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        previous_signature = ledger.get_runtime("workspace_sensor.signature")
        previous_serialized = ledger.get_runtime("workspace_sensor.snapshot")
        ledger.set_runtime("workspace_sensor.signature", signature)
        ledger.set_runtime("workspace_sensor.snapshot", serialized)
        if previous_signature is None or previous_signature == signature:
            return None
        previous = json.loads(previous_serialized or "{}")
        added = sorted(set(current) - set(previous))
        removed = sorted(set(previous) - set(current))
        modified = sorted(
            path
            for path in set(current) & set(previous)
            if current[path] != previous[path]
        )
        descriptions = []
        if added:
            descriptions.append("appeared: " + ", ".join(added[:12]))
        if modified:
            descriptions.append("changed: " + ", ".join(modified[:12]))
        if removed:
            descriptions.append("disappeared: " + ", ".join(removed[:12]))
        if not descriptions:
            return None
        return ledger.enqueue(
            "Workspace change sensed; " + "; ".join(descriptions) + ".",
            kind="notice",
            source_id="workspace-sense",
            sensory_features=(
                "workspace:change",
                *(f"workspace:appeared:{path}" for path in added[:12]),
                *(f"workspace:changed:{path}" for path in modified[:12]),
                *(f"workspace:disappeared:{path}" for path in removed[:12]),
            ),
        )


class AgentLedger:
    """Durable host queue, lifecycle ledger, and outward message mailbox."""

    def __init__(self, path: str | Path):
        self.path = str(Path(path).expanduser())
        Path(self.path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=15.0)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def __enter__(self) -> "AgentLedger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_events (
                    event_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    stability_delta REAL NOT NULL DEFAULT 0.0,
                    sensory_features_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    claimed_at REAL,
                    completed_at REAL,
                    error TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_agent_events_queue
                    ON agent_events(status, created_at, event_id);

                CREATE TABLE IF NOT EXISTS agent_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    event_id TEXT REFERENCES agent_events(event_id),
                    mode TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    frame_chars INTEGER NOT NULL,
                    model_output TEXT NOT NULL,
                    spoken_text TEXT NOT NULL DEFAULT '',
                    perception TEXT NOT NULL DEFAULT '',
                    receipts_json TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_agent_cycles_mode_time
                    ON agent_cycles(mode, created_at, cycle_id);

                CREATE TABLE IF NOT EXISTS agent_outbox (
                    message_id TEXT PRIMARY KEY,
                    cycle_id TEXT NOT NULL REFERENCES agent_cycles(cycle_id),
                    text TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS agent_runtime (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"]
                for row in self.connection.execute("PRAGMA table_info(agent_events)")
            }
            if "sensory_features_json" not in columns:
                self.connection.execute(
                    "ALTER TABLE agent_events ADD COLUMN sensory_features_json "
                    "TEXT NOT NULL DEFAULT '[]'"
                )

    @staticmethod
    def _event(row: sqlite3.Row) -> AgentEvent:
        return AgentEvent(
            event_id=row["event_id"],
            kind=row["kind"],
            source_id=row["source_id"],
            text=row["text"],
            stability_delta=float(row["stability_delta"]),
            sensory_features=tuple(json.loads(row["sensory_features_json"] or "[]")),
            status=row["status"],
            attempts=int(row["attempts"]),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _cycle(row: sqlite3.Row) -> AgentCycle:
        return AgentCycle(
            cycle_id=row["cycle_id"],
            event_id=row["event_id"],
            mode=row["mode"],
            step=int(row["step"]),
            status=row["status"],
            model_output=row["model_output"],
            spoken_text=row["spoken_text"],
            perception=row["perception"],
            receipts=tuple(json.loads(row["receipts_json"] or "[]")),
            created_at=float(row["created_at"]),
        )

    def enqueue(
        self,
        text: str,
        *,
        kind: str = "message",
        source_id: str = "human",
        stability_delta: float = 0.0,
        sensory_features: tuple[str, ...] = (),
        event_id: str | None = None,
    ) -> AgentEvent:
        if kind not in {"message", "notice"}:
            raise ValueError("event kind must be message or notice")
        cleaned = str(text).strip()
        if not cleaned:
            raise ValueError("event text is required")
        resolved_id = event_id or f"agent-event:{uuid.uuid4().hex}"
        created = time.time()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO agent_events(
                    event_id, kind, source_id, text, stability_delta, sensory_features_json,
                    status, attempts, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'queued', 0, ?)
                """,
                (
                    resolved_id,
                    kind,
                    str(source_id),
                    cleaned,
                    float(stability_delta),
                    _json(tuple(sensory_features)),
                    created,
                ),
            )
        return AgentEvent(
            resolved_id,
            kind,
            str(source_id),
            cleaned,
            float(stability_delta),
            tuple(sensory_features),
            "queued",
            0,
            created,
        )

    def recover_processing(self, *, older_than_seconds: float = 0.0) -> int:
        cutoff = time.time() - max(0.0, float(older_than_seconds))
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE agent_events
                SET status = 'queued', claimed_at = NULL,
                    error = 'recovered after interrupted processing'
                WHERE status = 'processing' AND COALESCE(claimed_at, 0) <= ?
                """,
                (cutoff,),
            )
        return int(cursor.rowcount)

    def claim_next(self) -> AgentEvent | None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                """
                SELECT * FROM agent_events
                WHERE status = 'queued'
                ORDER BY created_at, event_id
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                self.connection.commit()
                return None
            claimed = time.time()
            self.connection.execute(
                """
                UPDATE agent_events
                SET status = 'processing', claimed_at = ?, attempts = attempts + 1,
                    error = ''
                WHERE event_id = ? AND status = 'queued'
                """,
                (claimed, row["event_id"]),
            )
            updated = self.connection.execute(
                "SELECT * FROM agent_events WHERE event_id = ?",
                (row["event_id"],),
            ).fetchone()
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return self._event(updated)

    def finish_event(self, event_id: str, *, error: str = "") -> None:
        status = "failed" if error else "completed"
        with self.connection:
            self.connection.execute(
                """
                UPDATE agent_events
                SET status = ?, completed_at = ?, error = ?
                WHERE event_id = ?
                """,
                (status, time.time(), str(error), event_id),
            )

    def add_cycle(
        self,
        *,
        event_id: str | None,
        mode: str,
        step: int,
        status: str,
        frame_chars: int,
        model_output: str,
        spoken_text: str = "",
        perception: str = "",
        receipts: tuple[Mapping[str, Any], ...] = (),
    ) -> AgentCycle:
        cycle_id = f"agent-cycle:{uuid.uuid4().hex}"
        created = time.time()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO agent_cycles(
                    cycle_id, event_id, mode, step, status, frame_chars,
                    model_output, spoken_text, perception, receipts_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    event_id,
                    mode,
                    int(step),
                    status,
                    int(frame_chars),
                    str(model_output),
                    str(spoken_text),
                    str(perception),
                    _json(receipts),
                    created,
                ),
            )
        return AgentCycle(
            cycle_id,
            event_id,
            mode,
            int(step),
            status,
            str(model_output),
            str(spoken_text),
            str(perception),
            tuple(receipts),
            created,
        )

    def add_outbox(self, cycle_id: str, text: str) -> str:
        message_id = f"agent-message:{uuid.uuid4().hex}"
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO agent_outbox(message_id, cycle_id, text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (message_id, cycle_id, str(text).strip(), time.time()),
            )
        return message_id

    def outbox(self, *, undelivered_only: bool = False) -> list[Mapping[str, Any]]:
        where = "WHERE delivered = 0" if undelivered_only else ""
        rows = self.connection.execute(
            f"SELECT * FROM agent_outbox {where} ORDER BY created_at, message_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_delivered(self, message_ids: list[str]) -> None:
        with self.connection:
            self.connection.executemany(
                "UPDATE agent_outbox SET delivered = 1 WHERE message_id = ?",
                ((item,) for item in message_ids),
            )

    def list_events(self) -> list[Mapping[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM agent_events ORDER BY created_at, event_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def list_cycles(self) -> list[AgentCycle]:
        rows = self.connection.execute(
            "SELECT * FROM agent_cycles ORDER BY created_at, cycle_id"
        ).fetchall()
        return [self._cycle(row) for row in rows]

    def recent_idle_outputs(self, *, limit: int = 8) -> tuple[str, ...]:
        rows = self.connection.execute(
            """
            SELECT model_output FROM agent_cycles
            WHERE mode = 'idle' AND status != 'duplicate-suppressed'
            ORDER BY created_at DESC, cycle_id DESC LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return tuple(str(row["model_output"]).strip().casefold() for row in rows)

    def get_runtime(self, key: str, default: str | None = None) -> str | None:
        row = self.connection.execute(
            "SELECT value FROM agent_runtime WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_runtime(self, key: str, value: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO agent_runtime(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )

    def status(self) -> Mapping[str, Any]:
        counts = {
            row["status"]: int(row["count"])
            for row in self.connection.execute(
                "SELECT status, COUNT(*) AS count FROM agent_events GROUP BY status"
            )
        }
        return {
            "events": counts,
            "cycles": int(
                self.connection.execute("SELECT COUNT(*) FROM agent_cycles").fetchone()[0]
            ),
            "undelivered": int(
                self.connection.execute(
                    "SELECT COUNT(*) FROM agent_outbox WHERE delivered = 0"
                ).fetchone()[0]
            ),
            "last_idle_at": self.get_runtime("last_idle_at"),
        }


class ContinuousAgent:
    """Persistent input queue plus engaged and private idle cognitive cycles."""

    def __init__(
        self,
        session: SelfSession,
        driver: LanguageDriver,
        ledger: AgentLedger,
        *,
        maximum_event_steps: int = 8,
        maximum_idle_steps: int = 2,
        idle_interval_seconds: float = 60.0,
        idle_action_budget: int = 4,
        allow_idle_actions: bool = False,
        workspace_sensor: WorkspaceSensor | None = None,
    ) -> None:
        if maximum_event_steps < 1 or maximum_idle_steps < 1:
            raise ValueError("step limits must be positive")
        if idle_interval_seconds < 0:
            raise ValueError("idle interval cannot be negative")
        if idle_action_budget < 0:
            raise ValueError("idle action budget cannot be negative")
        self.session = session
        self.driver = driver
        self.ledger = ledger
        self.maximum_event_steps = int(maximum_event_steps)
        self.maximum_idle_steps = int(maximum_idle_steps)
        self.idle_interval_seconds = float(idle_interval_seconds)
        self.idle_action_budget = int(idle_action_budget)
        self.allow_idle_actions = bool(allow_idle_actions)
        self.workspace_sensor = workspace_sensor
        self._idle_actions_used = 0

    @staticmethod
    def _receipts(output) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            {
                "ability": receipt.ability_id.value,
                "status": receipt.status,
                "verified": receipt.verified,
                "output": receipt.output,
                "error": receipt.error,
                "receipt_id": receipt.return_record_id,
            }
            for receipt in output.batch.receipts
        )

    def _prepare_event(self, event: AgentEvent) -> SelfFrame:
        if event.kind == "notice":
            return self.session.prepare_notice(
                event.text,
                source_id=event.source_id,
                stability_delta=event.stability_delta,
                sensory_features=event.sensory_features,
            )
        return self.session.prepare_input(
            event.text,
            source_id=event.source_id,
            stability_delta=event.stability_delta,
        )

    def _action_signatures(self, requests) -> tuple[str, ...]:
        signatures = []
        for request in requests:
            try:
                prepared = self.session.actualizer.workspace.prepare(request)
            except (OSError, ValueError):
                continue
            arguments = dict(prepared.arguments)
            # Absolute paths are host detail. Workspace-relative identity is
            # stable across restarts and sufficient for loop suppression.
            arguments.pop("path", None)
            arguments.pop("cwd", None)
            signatures.append(
                _json(
                    {
                        "ability": prepared.ability_id.value,
                        "arguments": arguments,
                    }
                )
            )
        return tuple(signatures)

    @staticmethod
    def _looks_like_action_intent(text: str) -> bool:
        return bool(
            re.search(
                r"(?is)\b(?:i\s*(?:'ll|will|am\s+going\s+to)|let\s+me|"
                r"i\s+need\s+to)\s+"
                r"(?:(?:[a-z]+ly|now|next|first|again|then)\s+){0,2}"
                r"(?:look|list|read|open|inspect|find|search|"
                r"run|execute|launch|write|create|save|navigate|go|enter|check)\b",
                str(text).replace("’", "'"),
            )
        )

    @staticmethod
    def _looks_like_bare_command(text: str) -> bool:
        cleaned = str(text).strip()
        return bool(
            re.fullmatch(r"`[^`\n]+`", cleaned)
            or re.fullmatch(r"(?s)```(?:bash|sh|shell)?\s*\n?.+?```", cleaned)
            or re.fullmatch(
                r"(?:python3?|bash|sh|ls|pwd)\s+[^\n]+",
                cleaned,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _required_abilities(text: str) -> set[AbilityId]:
        lowered = str(text).casefold()
        rules = {
            AbilityId.RUN: r"\b(?:run|execute|launch)\b",
            AbilityId.WRITE: r"\b(?:write|create|save)\b",
            AbilityId.READ: r"\b(?:read|open)\b",
            AbilityId.LIST: r"\blist\b",
            AbilityId.NAVIGATE: r"\b(?:navigate|go\s+to|enter)\b",
        }
        request_marked = bool(
            re.search(
                r"\b(?:please|can\s+you|could\s+you|would\s+you|"
                r"i\s+(?:need|want)\s+you\s+to)\b",
                lowered,
            )
        )
        required: set[AbilityId] = set()
        for ability, pattern in rules.items():
            for match in re.finditer(pattern, lowered):
                prefix = lowered[max(0, match.start() - 36) : match.start()]
                if re.search(
                    r"(?:do\s+not|don't|never|without|how\s+to|whether\s+to)\s+$",
                    prefix,
                ):
                    continue
                leading = lowered[: match.start()].strip(" ,.;:!?")
                if request_marked or not leading or leading.endswith(("and", "then")):
                    required.add(ability)
                    break
        return required

    @staticmethod
    def _required_read_targets(
        text: str, required: set[AbilityId]
    ) -> set[str]:
        """Extract explicitly quoted paths governed by a positive read/open verb."""
        if AbilityId.READ not in required:
            return set()
        lowered = str(text).casefold().replace("’", "'")
        action_patterns = {
            AbilityId.READ: r"\b(?:read|open)\b",
            AbilityId.RUN: r"\b(?:run|execute|launch)\b",
            AbilityId.WRITE: r"\b(?:write|create|save)\b",
            AbilityId.LIST: r"\blist\b",
            AbilityId.NAVIGATE: r"\b(?:navigate|go\s+to|enter)\b",
        }
        mentions: list[tuple[int, int, AbilityId]] = []
        for ability, pattern in action_patterns.items():
            for match in re.finditer(pattern, lowered):
                prefix = lowered[max(0, match.start() - 36) : match.start()]
                if re.search(
                    r"(?:do\s+not|don't|never|without|how\s+to|whether\s+to)\s+$",
                    prefix,
                ):
                    continue
                mentions.append((match.start(), match.end(), ability))
        mentions.sort()
        targets: set[str] = set()
        for quoted in re.finditer(r"`([^`\n]+)`", str(text)):
            governing = [item for item in mentions if item[1] <= quoted.start()]
            if not governing or governing[-1][2] != AbilityId.READ:
                continue
            target = quoted.group(1).strip().replace("\\", "/")
            while target.startswith("./"):
                target = target[2:]
            if target:
                targets.add(target)
        return targets

    @staticmethod
    def _denies_observed_access(text: str) -> bool:
        lowered = str(text).casefold().replace("’", "'")
        denial = any(
            marker in lowered
            for marker in (
                "i cannot access",
                "i can't access",
                "i do not have access",
                "i don't have access",
                "my environment does not have access",
                "i cannot run commands",
                "i can't run commands",
            )
        )
        return denial and any(
            noun in lowered
            for noun in ("file", "workspace", "terminal", "command", "tool")
        )

    async def _process_event(self, event: AgentEvent) -> AgentStep:
        frame = self._prepare_event(event)
        cycles: list[AgentCycle] = []
        mode = "notice" if event.kind == "notice" else "engaged"
        required = self._required_abilities(event.text) if event.kind == "message" else set()
        required_read_targets = self._required_read_targets(event.text, required)
        successful: set[AbilityId] = set()
        successful_read_targets: set[str] = set()
        observed_action_signatures: set[str] = set()
        try:
            for step in range(1, self.maximum_event_steps + 1):
                generated = str(
                    await self.driver.generate(frame.text, mode=mode)
                ).strip()
                if not generated:
                    raise RuntimeError("language driver returned an empty generation")
                parsed, _ = self.session.actualizer.activator.parse(
                    generated,
                    source_role="assistant",
                    apply_limit=False,
                )
                if (
                    self._looks_like_action_intent(generated)
                    or self._looks_like_bare_command(generated)
                ) and not parsed:
                    perception = (
                        "I attempted to act, but no workspace action occurred. I must "
                        "state one exact immediate action as: I'll list `path`; I'll "
                        "read `path`; I'll go to `path`; or I'll run `exact command`."
                    )
                    cycle = self.ledger.add_cycle(
                        event_id=event.event_id,
                        mode=mode,
                        step=step,
                        status="unrecognized-action",
                        frame_chars=frame.char_count,
                        model_output=generated,
                        perception=perception,
                    )
                    cycles.append(cycle)
                    frame = self.session.prepare_observation(perception)
                    continue
                proposed_signatures = self._action_signatures(parsed)
                repeated = next(
                    (
                        signature
                        for signature in proposed_signatures
                        if signature in observed_action_signatures
                    ),
                    None,
                )
                if repeated is not None:
                    perception = (
                        "I already performed that exact action and observed its result. "
                        "The environment has not changed, so repeating it would add no "
                        "evidence."
                    )
                    cycle = self.ledger.add_cycle(
                        event_id=event.event_id,
                        mode=mode,
                        step=step,
                        status="repeated-action-suppressed",
                        frame_chars=frame.char_count,
                        model_output=generated,
                        perception=perception,
                    )
                    cycles.append(cycle)
                    if event.kind == "notice":
                        self.ledger.finish_event(event.event_id)
                        return AgentStep(
                            mode, event.event_id, "completed", tuple(cycles)
                        )
                    frame = self.session.prepare_observation(perception)
                    continue
                missing = sorted(
                    (ability.value for ability in required - successful)
                )
                missing_read_targets = sorted(
                    required_read_targets - successful_read_targets
                )
                contradicts_receipts = bool(successful) and self._denies_observed_access(
                    generated
                )
                if not parsed and (
                    missing or missing_read_targets or contradicts_receipts
                ):
                    if missing_read_targets:
                        reason = (
                            "The current request is not complete because I have not "
                            "directly read: "
                            + ", ".join(f"`{path}`" for path in missing_read_targets)
                            + "."
                        )
                    elif missing:
                        reason = (
                            "The current request is not complete because I have not "
                            "observed a verified result for: " + ", ".join(missing) + "."
                        )
                    else:
                        reason = (
                            "That answer contradicts actions I already performed and "
                            "observed successfully."
                        )
                    perception = (
                        reason
                        + " I must continue from my observed workspace evidence with "
                        "one exact immediate action, without claiming I lack access."
                    )
                    cycle = self.ledger.add_cycle(
                        event_id=event.event_id,
                        mode=mode,
                        step=step,
                        status="completion-suppressed",
                        frame_chars=frame.char_count,
                        model_output=generated,
                        perception=perception,
                    )
                    cycles.append(cycle)
                    frame = self.session.prepare_observation(perception)
                    continue
                output = (
                    await self.session.process_private_output(generated)
                    if event.kind == "notice"
                    else await self.session.process_output(generated)
                )
                if output.batch.receipts or output.batch.suppressed:
                    completed_read_targets_before = bool(required_read_targets) and (
                        required_read_targets <= successful_read_targets
                    )
                    successful.update(
                        receipt.ability_id
                        for receipt in output.batch.receipts
                        if receipt.status == "success" and receipt.verified
                    )
                    successful_read_targets.update(
                        str(receipt.output.get("path", "")).replace("\\", "/")
                        for receipt in output.batch.receipts
                        if receipt.ability_id == AbilityId.READ
                        and receipt.status == "success"
                        and receipt.verified
                        and isinstance(receipt.output, Mapping)
                        and receipt.output.get("path")
                    )
                    completed_read_targets_now = bool(required_read_targets) and (
                        required_read_targets <= successful_read_targets
                    )
                    perception = output.perception
                    if (
                        completed_read_targets_now
                        and not completed_read_targets_before
                    ):
                        perception = (
                            perception.rstrip()
                            + "\nI have now directly read every file requested in the "
                            "current task, so I can answer the original request from "
                            "those observations."
                        ).strip()
                    if any(
                        receipt.ability_id
                        in {AbilityId.WRITE, AbilityId.RUN, AbilityId.NAVIGATE}
                        for receipt in output.batch.receipts
                    ):
                        observed_action_signatures.clear()
                    executed_ids = {
                        receipt.request_id for receipt in output.batch.receipts
                    }
                    observed_action_signatures.update(
                        self._action_signatures(
                            tuple(
                                request
                                for request in output.batch.requests
                                if request.request_id in executed_ids
                            )
                        )
                    )
                    cycle = self.ledger.add_cycle(
                        event_id=event.event_id,
                        mode=mode,
                        step=step,
                        status="action",
                        frame_chars=frame.char_count,
                        model_output=generated,
                        perception=perception,
                        receipts=self._receipts(output),
                    )
                    cycles.append(cycle)
                    frame = self.session.prepare_observation(perception)
                    continue
                if event.kind == "notice":
                    cycle = self.ledger.add_cycle(
                        event_id=event.event_id,
                        mode=mode,
                        step=step,
                        status="thought",
                        frame_chars=frame.char_count,
                        model_output=generated,
                    )
                    cycles.append(cycle)
                    self.ledger.finish_event(event.event_id)
                    return AgentStep(mode, event.event_id, "completed", tuple(cycles))
                cycle = self.ledger.add_cycle(
                    event_id=event.event_id,
                    mode=mode,
                    step=step,
                    status="spoken",
                    frame_chars=frame.char_count,
                    model_output=generated,
                    spoken_text=output.spoken_text,
                )
                cycles.append(cycle)
                self.ledger.add_outbox(cycle.cycle_id, output.spoken_text)
                self.session.clear_focus()
                self.ledger.finish_event(event.event_id)
                return AgentStep(
                    mode,
                    event.event_id,
                    "completed",
                    tuple(cycles),
                    spoken_text=output.spoken_text,
                )
            error = f"event exceeded {self.maximum_event_steps} model steps"
        except Exception as caught:
            error = str(caught)
        self.ledger.finish_event(event.event_id, error=error)
        return AgentStep(
            mode,
            event.event_id,
            "failed",
            tuple(cycles),
            error=error,
        )

    def _idle_is_due(self) -> bool:
        if self.idle_interval_seconds == 0:
            return True
        previous = self.ledger.get_runtime("last_idle_at")
        if previous is None:
            return True
        return time.time() - float(previous) >= self.idle_interval_seconds

    async def _process_idle(self) -> AgentStep:
        frame = self.session.prepare_idle()
        cycles: list[AgentCycle] = []
        try:
            for step in range(1, self.maximum_idle_steps + 1):
                generated = str(
                    await self.driver.generate(frame.text, mode="idle")
                ).strip()
                if not generated:
                    raise RuntimeError("language driver returned an empty generation")
                normalized = generated.casefold()
                parsed, _ = self.session.actualizer.activator.parse(
                    generated,
                    source_role="assistant",
                    apply_limit=False,
                )
                actions_allowed = (
                    self.allow_idle_actions
                    and self._idle_actions_used < self.idle_action_budget
                )
                if normalized in self.ledger.recent_idle_outputs():
                    cycle = self.ledger.add_cycle(
                        event_id=None,
                        mode="idle",
                        step=step,
                        status="duplicate-suppressed",
                        frame_chars=frame.char_count,
                        model_output=generated,
                    )
                    cycles.append(cycle)
                    break
                if (
                    self._looks_like_action_intent(generated)
                    or self._looks_like_bare_command(generated)
                ) and not parsed:
                    perception = (
                        "That did not perform an action. If action is useful, I must "
                        "state exactly one first-person action with its path or command; "
                        "otherwise I should keep one short grounded private thought."
                    )
                    cycle = self.ledger.add_cycle(
                        event_id=None,
                        mode="idle",
                        step=step,
                        status="unrecognized-action",
                        frame_chars=frame.char_count,
                        model_output=generated,
                        perception=perception,
                    )
                    cycles.append(cycle)
                    frame = self.session.prepare_observation(perception)
                    continue
                if not actions_allowed:
                    if parsed:
                        cycle = self.ledger.add_cycle(
                            event_id=None,
                            mode="idle",
                            step=step,
                            status="autonomy-suppressed",
                            frame_chars=frame.char_count,
                            model_output=generated,
                        )
                        cycles.append(cycle)
                        break
                output = await self.session.process_private_output(
                    generated,
                    allow_actions=actions_allowed,
                )
                if output.batch.receipts or output.batch.suppressed:
                    self._idle_actions_used += len(output.batch.receipts)
                    cycle = self.ledger.add_cycle(
                        event_id=None,
                        mode="idle",
                        step=step,
                        status="action",
                        frame_chars=frame.char_count,
                        model_output=generated,
                        perception=output.perception,
                        receipts=self._receipts(output),
                    )
                    cycles.append(cycle)
                    frame = self.session.prepare_observation(output.perception)
                    continue
                cycle = self.ledger.add_cycle(
                    event_id=None,
                    mode="idle",
                    step=step,
                    status="thought",
                    frame_chars=frame.char_count,
                    model_output=generated,
                )
                cycles.append(cycle)
                break
            return AgentStep("idle", None, "completed", tuple(cycles))
        except Exception as caught:
            return AgentStep(
                "idle", None, "failed", tuple(cycles), error=str(caught)
            )
        finally:
            self.ledger.set_runtime("last_idle_at", str(time.time()))

    async def step(self, *, force_idle: bool = False) -> AgentStep | None:
        if self.workspace_sensor is not None:
            self.workspace_sensor.poll(self.ledger)
        event = self.ledger.claim_next()
        if event is not None:
            # New external experience begins a fresh, bounded autonomous period.
            if event.kind == "message":
                self._idle_actions_used = 0
            return await self._process_event(event)
        if force_idle or self._idle_is_due():
            return await self._process_idle()
        return None

    async def run_forever(
        self,
        *,
        poll_seconds: float = 0.5,
        stop_event: asyncio.Event | None = None,
        maximum_cycles: int | None = None,
        on_step: Callable[[AgentStep], Awaitable[None] | None] | None = None,
    ) -> int:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        completed = 0
        while stop_event is None or not stop_event.is_set():
            result = await self.step()
            if result is None:
                await asyncio.sleep(poll_seconds)
                continue
            completed += 1
            if on_step is not None:
                callback_result = on_step(result)
                if callback_result is not None:
                    await callback_result
            if maximum_cycles is not None and completed >= maximum_cycles:
                break
        return completed


def step_to_dict(step: AgentStep) -> Mapping[str, Any]:
    return asdict(step)
