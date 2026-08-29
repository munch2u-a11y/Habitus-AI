from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable


@dataclass
class WorkingEntry:
    record_id: str
    activation: float
    last_pulse: int


class WorkingMemory:
    """Bounded activation ledger; canonical content remains in long-term storage."""

    def __init__(
        self,
        *,
        decay: float = 0.60,
        minimum_activation: float = 0.12,
        maximum_records: int = 16,
    ):
        self.decay = max(0.0, min(1.0, decay))
        self.minimum_activation = max(0.0, minimum_activation)
        self.maximum_records = max(1, maximum_records)
        self.entries: OrderedDict[str, WorkingEntry] = OrderedDict()

    def advance(self, pulse: int, selected_record_ids: Iterable[str]) -> tuple[str, ...]:
        for record_id in list(self.entries):
            entry = self.entries[record_id]
            entry.activation *= self.decay
            if entry.activation < self.minimum_activation:
                del self.entries[record_id]
        selected = list(dict.fromkeys(selected_record_ids))
        retained = tuple(record_id for record_id in self.entries if record_id not in selected)
        for record_id in selected:
            self.entries.pop(record_id, None)
            self.entries[record_id] = WorkingEntry(record_id, 1.0, pulse)
        while len(self.entries) > self.maximum_records:
            weakest = min(
                self.entries.values(),
                key=lambda entry: (entry.activation, entry.last_pulse),
            )
            self.entries.pop(weakest.record_id, None)
        return retained

    def active_ids(self) -> tuple[str, ...]:
        ranked = sorted(
            self.entries.values(),
            key=lambda entry: (-entry.activation, -entry.last_pulse, entry.record_id),
        )
        return tuple(entry.record_id for entry in ranked)

