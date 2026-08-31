from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import ActualizationBatch
from .perception import render_perception
from .runtime import Actualizer


@dataclass(frozen=True)
class MiddlewareResult:
    original_message: Mapping[str, Any]
    batch: ActualizationBatch
    observation: Mapping[str, Any]
    perception: str


class AgentOutputMiddleware:
    """Framework-neutral post-generation hook; it exposes no tool schemas."""

    def __init__(self, actualizer: Actualizer) -> None:
        self.actualizer = actualizer

    async def process(self, message: str | Mapping[str, Any]) -> MiddlewareResult:
        if isinstance(message, str):
            normalized: Mapping[str, Any] = {"role": "assistant", "content": message}
        else:
            normalized = dict(message)
        role = str(normalized.get("role", "assistant"))
        content = normalized.get("content", "")
        if isinstance(content, list):
            text = "\n".join(
                str(item.get("text", "")) if isinstance(item, Mapping) else str(item)
                for item in content
            )
        else:
            text = str(content)
        batch = await self.actualizer.actualize(text, source_role=role)
        return MiddlewareResult(
            normalized,
            batch,
            batch.observation(),
            render_perception(batch, workspace_root=self.actualizer.policy.root),
        )
