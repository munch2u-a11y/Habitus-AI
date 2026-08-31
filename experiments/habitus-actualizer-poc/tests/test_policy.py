from pathlib import Path

import pytest

from habitus_actualizer.policy import PolicyDenied, WorkspacePolicy


def test_path_cannot_escape_workspace(tmp_path):
    policy = WorkspacePolicy(tmp_path)
    with pytest.raises(PolicyDenied, match="escapes"):
        policy.resolve_path("../outside.txt", cwd=tmp_path, require_exists=False)


def test_sensitive_paths_are_protected(tmp_path):
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    policy = WorkspacePolicy(tmp_path)
    with pytest.raises(PolicyDenied, match="protected"):
        policy.resolve_path(".env", cwd=tmp_path)


def test_commands_are_deny_by_default(tmp_path):
    policy = WorkspacePolicy(tmp_path)
    with pytest.raises(PolicyDenied, match="not allowlisted"):
        policy.parse_command("python3 --version", cwd=tmp_path)


def test_no_shell_or_inline_python_is_admitted(tmp_path):
    policy = WorkspacePolicy(tmp_path, allowed_commands=("python3",))
    with pytest.raises(PolicyDenied, match="inline Python"):
        policy.parse_command("python3 -c 'print(1)'", cwd=tmp_path)


def test_bare_python_interpreter_is_not_a_meaningful_action(tmp_path):
    policy = WorkspacePolicy(tmp_path, allowed_commands=("python3",))

    with pytest.raises(PolicyDenied, match="requires a workspace script"):
        policy.parse_command("python3", cwd=tmp_path)


def test_lookalike_executable_path_cannot_bypass_allowlist(tmp_path):
    fake = tmp_path / "python3"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    policy = WorkspacePolicy(tmp_path, allowed_commands=("python3",))
    with pytest.raises(PolicyDenied, match="does not match"):
        policy.parse_command(str(fake), cwd=tmp_path)


def test_allowlisted_python_module_is_narrow(tmp_path):
    policy = WorkspacePolicy(tmp_path, allowed_commands=("python3",))
    assert policy.parse_command("python3 -m pytest -q", cwd=tmp_path) == (
        "python3",
        "-m",
        "pytest",
        "-q",
    )
    with pytest.raises(PolicyDenied, match="module is not allowlisted"):
        policy.parse_command("python3 -m http.server", cwd=tmp_path)


def test_normalize_commands_keeps_only_basenames():
    assert WorkspacePolicy.normalize_allowed_commands(
        ("/usr/bin/python3", "python3", "pytest")
    ) == ("python3", "pytest")
