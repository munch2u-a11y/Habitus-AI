from __future__ import annotations

import os
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


class PolicyDenied(ValueError):
    """The requested effect is outside the configured authority boundary."""


_SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".git",
        ".gnupg",
        ".habitus",
        ".ssh",
        "credentials.json",
        "id_dsa",
        "id_ed25519",
        "id_rsa",
        "secrets.json",
    }
)


@dataclass(frozen=True)
class WorkspacePolicy:
    root: Path | str
    allow_write: bool = False
    allowed_commands: tuple[str, ...] = ()
    allowed_python_modules: tuple[str, ...] = ("pytest",)
    allow_workspace_programs: bool = False
    command_timeout_seconds: float = 30.0
    max_read_bytes: int = 256_000
    max_output_chars: int = 64_000
    blocked_names: frozenset[str] = field(default_factory=lambda: _SENSITIVE_NAMES)

    def __post_init__(self) -> None:
        root = Path(self.root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(root)
        if self.command_timeout_seconds <= 0:
            raise ValueError("command_timeout_seconds must be positive")
        if self.max_read_bytes < 1 or self.max_output_chars < 1:
            raise ValueError("read and output limits must be positive")
        object.__setattr__(self, "root", root)
        object.__setattr__(
            self,
            "allowed_commands",
            tuple(dict.fromkeys(str(item).strip() for item in self.allowed_commands if str(item).strip())),
        )

    def resolve_path(
        self,
        raw_path: str | Path,
        *,
        cwd: Path,
        require_exists: bool = True,
    ) -> Path:
        raw = str(raw_path).strip().strip("`\"'")
        if not raw:
            raw = "."
        if "\x00" in raw or "\n" in raw or "\r" in raw:
            raise PolicyDenied("path contains an invalid character")
        supplied = Path(raw).expanduser()
        candidate = supplied if supplied.is_absolute() else cwd / supplied
        resolved = candidate.resolve(strict=False)
        try:
            relative = resolved.relative_to(self.root)
        except ValueError as error:
            raise PolicyDenied("path escapes the configured workspace") from error
        blocked = {part.casefold() for part in relative.parts} & {
            item.casefold() for item in self.blocked_names
        }
        if blocked:
            raise PolicyDenied(f"path enters a protected location: {sorted(blocked)[0]}")
        if require_exists and not resolved.exists():
            raise FileNotFoundError(resolved)
        return resolved

    def parse_command(self, command: str, *, cwd: Path) -> tuple[str, ...]:
        try:
            argv = tuple(shlex.split(str(command), posix=True))
        except ValueError as error:
            raise PolicyDenied(f"invalid command quoting: {error}") from error
        if not argv:
            raise PolicyDenied("command is empty")
        executable = argv[0]
        basename = Path(executable).name
        if basename not in self.allowed_commands:
            if not self.allow_workspace_programs:
                raise PolicyDenied(f"command is not allowlisted: {basename}")
            resolved_program = self.resolve_path(executable, cwd=cwd)
            if not resolved_program.is_file() or not os.access(resolved_program, os.X_OK):
                raise PolicyDenied("workspace program is not executable")
            executable = str(resolved_program)
            argv = (executable, *argv[1:])
        elif os.sep in executable:
            discovered = Path(executable).resolve(strict=True)
            system_match = shutil.which(basename)
            if system_match is None or discovered != Path(system_match).resolve(strict=True):
                raise PolicyDenied(
                    "explicit executable path does not match the allowlisted program"
                )
        elif shutil.which(executable) is None:
            raise PolicyDenied(f"allowlisted command is unavailable: {executable}")

        if basename in {"python", "python3"}:
            if len(argv) == 1:
                raise PolicyDenied(
                    "Python execution requires a workspace script or allowed module"
                )
            if "-c" in argv:
                raise PolicyDenied("inline Python execution is disabled")
            if "-m" in argv:
                index = argv.index("-m")
                module = argv[index + 1] if index + 1 < len(argv) else ""
                if module not in self.allowed_python_modules:
                    raise PolicyDenied(f"Python module is not allowlisted: {module or '<missing>'}")
            for argument in argv[1:]:
                if argument.endswith(".py"):
                    self.resolve_path(argument, cwd=cwd)

        blocked_flags = {"--eval", "--exec", "-e"}
        if any(argument in blocked_flags for argument in argv[1:]):
            raise PolicyDenied("inline program evaluation is disabled")
        return argv

    def subprocess_environment(self) -> dict[str, str]:
        """Expose only basic process-discovery and locale state to child tools."""
        allowed = ("PATH", "LANG", "LC_ALL", "TERM", "SYSTEMROOT", "WINDIR")
        return {key: os.environ[key] for key in allowed if key in os.environ}

    def ensure_write_allowed(self) -> None:
        if not self.allow_write:
            raise PolicyDenied("workspace writes are disabled")

    def truncate(self, value: str) -> tuple[str, bool]:
        text = str(value)
        if len(text) <= self.max_output_chars:
            return text, False
        return text[: self.max_output_chars], True

    @staticmethod
    def normalize_allowed_commands(values: Iterable[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(Path(value).name for value in values if str(value).strip()))
