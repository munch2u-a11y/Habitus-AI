from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import AbilityId, ActualizationBatch


def _bounded(text: str, maximum_chars: int) -> str:
    if len(text) <= maximum_chars:
        return text
    marker = "\n[The observed result was shortened; the complete result remains internal.]"
    return text[: max(0, maximum_chars - len(marker))].rstrip() + marker


def _clean_error(value: str, workspace_root: str | Path | None) -> str:
    text = str(value).strip()
    if workspace_root is not None:
        root = str(Path(workspace_root).resolve())
        text = text.replace(root + "/", "").replace(root, ".")
    return text or "the action did not produce a usable result"


def render_success_text(ability: AbilityId, output: Any) -> str:
    result: Mapping[str, Any] = output if isinstance(output, Mapping) else {}
    if ability == AbilityId.LIST:
        rendered = [
            f"{item.get('name')}/" if item.get("kind") == "directory" else str(item.get("name"))
            for item in result.get("items", ())
            if isinstance(item, Mapping) and item.get("name")
        ]
        contents = ", ".join(rendered) if rendered else "nothing"
        return f"I looked in {result.get('path', '.')} and found: {contents}."
    if ability == AbilityId.READ:
        path = result.get("path", "the file")
        content = str(result.get("content", ""))
        suffix = "\n[Only part of the file was visible.]" if result.get("truncated") else ""
        return (
            f"I directly read {path} through the workspace read ability; "
            f"I did not run a shell command:\n{content.rstrip()}{suffix}"
        ).rstrip()
    if ability == AbilityId.NAVIGATE:
        return f"I am now in {result.get('current', '.')}"
    if ability == AbilityId.WRITE:
        return f"I wrote {result.get('path', 'the file')} and confirmed the saved contents."
    if ability == AbilityId.RUN:
        argv = result.get("argv", ())
        command = " ".join(str(item) for item in argv) if argv else "the program"
        stdout = str(result.get("stdout", "")).rstrip()
        stderr = str(result.get("stderr", "")).rstrip()
        visible = stdout or stderr
        if not visible:
            return f"I ran `{command}` successfully without visible output."
        suffix = "\n[Only part of the program output was visible.]" if (
            result.get("stdout_truncated") or result.get("stderr_truncated")
        ) else ""
        return f"I ran `{command}` successfully. The program returned:\n{visible}{suffix}"
    return "The action completed successfully."


def render_perception(
    batch: ActualizationBatch,
    *,
    workspace_root: str | Path | None = None,
    maximum_chars: int = 5000,
) -> str:
    """Project authoritative action results into minimal model-facing experience.

    The complete receipt remains in the ledger. This view intentionally omits
    IDs, hashes, timings, graph state, confidence, and duplicated call metadata.
    """
    statements: list[str] = []
    for receipt in batch.receipts:
        if receipt.status == "success" and receipt.verified:
            statements.append(render_success_text(receipt.ability_id, receipt.output))
        else:
            statements.append(
                "That action failed: "
                + _clean_error(receipt.error, workspace_root)
            )
    for suppressed in batch.suppressed:
        statements.append(
            "I could not perform that action: "
            + _clean_error(suppressed.reason, workspace_root)
        )
    return _bounded("\n".join(statements).strip(), max(128, int(maximum_chars)))
