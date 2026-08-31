from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping

from .contracts import AbilityId, AbilityRequest, Effect
from .policy import WorkspacePolicy


class AbilityFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class AbilityDefinition:
    ability_id: AbilityId
    effect: Effect
    label: str
    description: str
    terms: tuple[str, ...]


CORE_ABILITIES: tuple[AbilityDefinition, ...] = (
    AbilityDefinition(
        AbilityId.LIST,
        Effect.LOOK,
        "List workspace",
        "Inspect the immediate contents of one workspace directory.",
        ("list", "inspect", "show", "directory", "folder", "files"),
    ),
    AbilityDefinition(
        AbilityId.READ,
        Effect.LOOK,
        "Read workspace file",
        "Read a bounded UTF-8 text file inside the workspace.",
        ("read", "open", "view", "inspect", "file", "content"),
    ),
    AbilityDefinition(
        AbilityId.NAVIGATE,
        Effect.LOOK,
        "Navigate workspace",
        "Move the runtime's virtual working directory inside its workspace.",
        ("navigate", "go", "enter", "change", "directory", "folder"),
    ),
    AbilityDefinition(
        AbilityId.WRITE,
        Effect.DO,
        "Write workspace file",
        "Atomically write and read back a UTF-8 file inside the workspace.",
        ("write", "create", "save", "update", "file", "content"),
    ),
    AbilityDefinition(
        AbilityId.RUN,
        Effect.DO,
        "Run allowlisted program",
        "Run one allowlisted argv command without a shell inside the workspace.",
        ("run", "execute", "launch", "program", "command", "tests"),
    ),
)


class WorkspaceAbilities:
    """Validated implementations for the five proof-of-concept abilities."""

    def __init__(self, policy: WorkspacePolicy, *, initial_cwd: str | Path = ".") -> None:
        self.policy = policy
        self._lock = threading.RLock()
        self._cwd = self.policy.resolve_path(initial_cwd, cwd=self.policy.root)
        if not self._cwd.is_dir():
            self._cwd = self.policy.root

    @property
    def cwd(self) -> Path:
        with self._lock:
            return self._cwd

    def display_path(self, path: Path) -> str:
        relative = path.relative_to(self.policy.root)
        return "." if not relative.parts else relative.as_posix()

    def prepare(self, request: AbilityRequest) -> AbilityRequest:
        cwd = self.cwd
        arguments = dict(request.arguments)
        ability = request.ability_id
        if ability in {AbilityId.LIST, AbilityId.READ, AbilityId.NAVIGATE}:
            resolved = self.policy.resolve_path(
                arguments.get("path", "."),
                cwd=cwd,
                require_exists=False,
            )
            if ability == AbilityId.READ and resolved.is_dir():
                ability = AbilityId.LIST
            arguments = {
                "path": str(resolved),
                "workspace_path": self.display_path(resolved),
            }
        elif ability == AbilityId.WRITE:
            self.policy.ensure_write_allowed()
            content = str(arguments.get("content", ""))
            if not content:
                raise ValueError("write content is empty")
            resolved = self.policy.resolve_path(
                arguments.get("path", ""),
                cwd=cwd,
                require_exists=False,
            )
            if not resolved.parent.exists() or not resolved.parent.is_dir():
                raise FileNotFoundError(resolved.parent)
            arguments = {
                "path": str(resolved),
                "workspace_path": self.display_path(resolved),
                "content": content,
            }
        elif ability == AbilityId.RUN:
            command = str(arguments.get("command", ""))
            argv = self.policy.parse_command(command, cwd=cwd)
            arguments = {
                "command": command,
                "argv": argv,
                "cwd": str(cwd),
                "workspace_cwd": self.display_path(cwd),
            }
        return replace(request, ability_id=ability, arguments=arguments)

    def execute(self, request: AbilityRequest) -> Mapping[str, Any]:
        handlers: dict[AbilityId, Callable[[Mapping[str, Any]], Mapping[str, Any]]] = {
            AbilityId.LIST: self._list,
            AbilityId.READ: self._read,
            AbilityId.NAVIGATE: self._navigate,
            AbilityId.WRITE: self._write,
            AbilityId.RUN: self._run,
        }
        return handlers[request.ability_id](request.arguments)

    def _list(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        path = Path(str(arguments["path"]))
        if not path.is_dir():
            raise NotADirectoryError(path)
        items = [
            {
                "name": child.name,
                "kind": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            }
            for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
            if child.name.casefold() not in {item.casefold() for item in self.policy.blocked_names}
        ]
        return {
            "path": arguments["workspace_path"],
            "items": items,
            "count": len(items),
        }

    def _read(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        path = Path(str(arguments["path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        if size > self.policy.max_read_bytes:
            raise AbilityFailed(
                f"file exceeds the {self.policy.max_read_bytes}-byte read limit"
            )
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise AbilityFailed("file is not valid UTF-8 text") from error
        rendered, truncated = self.policy.truncate(text)
        return {
            "path": arguments["workspace_path"],
            "content": rendered,
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "truncated": truncated,
        }

    def _navigate(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        path = Path(str(arguments["path"]))
        if not path.is_dir():
            raise NotADirectoryError(path)
        with self._lock:
            previous = self.display_path(self._cwd)
            self._cwd = path
        return {
            "previous": previous,
            "current": arguments["workspace_path"],
        }

    def _write(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        path = Path(str(arguments["path"]))
        content = str(arguments.get("content", ""))
        encoded = content.encode("utf-8")
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_name = handle.name
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
            temporary_name = None
        finally:
            if temporary_name and Path(temporary_name).exists():
                Path(temporary_name).unlink()
        observed = path.read_bytes()
        expected_hash = hashlib.sha256(encoded).hexdigest()
        observed_hash = hashlib.sha256(observed).hexdigest()
        if expected_hash != observed_hash:
            raise AbilityFailed("write read-back hash did not match")
        return {
            "path": arguments["workspace_path"],
            "bytes_written": len(encoded),
            "sha256": observed_hash,
            "read_back_verified": True,
        }

    def _run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        argv = tuple(str(item) for item in arguments["argv"])
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                argv,
                cwd=str(arguments["cwd"]),
                env=self.policy.subprocess_environment(),
                shell=False,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self.policy.command_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise AbilityFailed(
                f"command exceeded {self.policy.command_timeout_seconds:g} seconds"
            ) from error
        stdout, stdout_truncated = self.policy.truncate(completed.stdout)
        stderr, stderr_truncated = self.policy.truncate(completed.stderr)
        evidence = {
            "argv": list(argv),
            "cwd": arguments["workspace_cwd"],
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "duration_seconds": round(time.perf_counter() - started, 6),
        }
        if completed.returncode != 0:
            raise AbilityFailed(
                f"command exited {completed.returncode}; stderr={stderr[:500]!r}"
            )
        return evidence
