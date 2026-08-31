from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


class Effect(str, enum.Enum):
    LOOK = "LOOK"
    DO = "DO"


class AbilityId(str, enum.Enum):
    LIST = "workspace.list"
    READ = "workspace.read"
    NAVIGATE = "workspace.navigate"
    WRITE = "workspace.write"
    RUN = "workspace.run"


@dataclass(frozen=True)
class AbilityRequest:
    request_id: str
    ability_id: AbilityId
    phrase: str
    arguments: Mapping[str, Any]
    confidence: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SuppressedRequest:
    phrase: str
    reason: str
    ability_id: AbilityId | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class AbilityReceipt:
    request_id: str
    ability_id: AbilityId
    effect: Effect
    status: str
    verified: bool
    arguments: Mapping[str, Any]
    output: Any = None
    error: str = ""
    elapsed_seconds: float = 0.0
    cycle_id: str | None = None
    output_record_id: str | None = None
    return_record_id: str | None = None
    outcome_id: str | None = None
    trace_node_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActualizationBatch:
    source_role: str
    source_text: str
    requests: tuple[AbilityRequest, ...] = ()
    receipts: tuple[AbilityReceipt, ...] = ()
    suppressed: tuple[SuppressedRequest, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def acted(self) -> bool:
        return bool(self.receipts)

    @property
    def successful(self) -> bool:
        return bool(self.receipts) and all(
            receipt.status == "success" and receipt.verified
            for receipt in self.receipts
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)

    def observation(self) -> dict[str, Any]:
        """Return the compact evidence packet an agent framework can re-ingest."""
        return {
            "kind": "ability_results",
            "acted": self.acted,
            "results": [
                {
                    "ability": receipt.ability_id.value,
                    "status": receipt.status,
                    "verified": receipt.verified,
                    "output": receipt.output,
                    "error": receipt.error,
                    "receipt_id": receipt.return_record_id,
                }
                for receipt in self.receipts
            ],
            "suppressed": [
                {
                    "ability": item.ability_id.value if item.ability_id else None,
                    "reason": item.reason,
                }
                for item in self.suppressed
            ],
        }
