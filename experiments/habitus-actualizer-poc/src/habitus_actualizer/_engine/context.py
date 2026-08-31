from __future__ import annotations

import json
from typing import Iterable, Sequence

from ..contracts import AbilityId
from ..perception import render_success_text
from .types import ContextBundle, MemoryRecord, RecordType


def render_verified_tool_result(record: MemoryRecord) -> str:
    """Render a receipt as compact evidence without making it a HEAR word node."""
    try:
        payload = json.loads(record.text)
        ability = AbilityId(str(payload["ability"]))
        status = str(payload.get("status", ""))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return record.text.strip()
    if status == "success" and bool(record.metadata.get("verified", False)):
        return render_success_text(ability, payload.get("output"))
    error = str(payload.get("error") or "the action did not produce a usable result")
    return f"The {ability.value} action failed: {error}"


def _render_record(
    record: MemoryRecord,
    *,
    retained: bool = False,
    include_timestamps: bool = False,
) -> str:
    text = record.text.strip()
    if record.record_type == RecordType.TOOL_RESULT:
        text = render_verified_tool_result(record)
        prefix = "I directly verified" if record.metadata.get("verified") else "I observed"
    elif record.record_type == RecordType.FACT:
        prefix = "I understand from recorded evidence"
    elif record.record_type in {RecordType.RECEIPT, RecordType.OBSERVATION}:
        verified = bool(record.metadata.get("verified", False))
        prefix = "I directly verified" if verified else "I observed"
    elif record.record_type == RecordType.INBOUND_MESSAGE:
        prefix = f"I remember {record.source_id} telling me"
    elif record.record_type == RecordType.OUTBOUND_MESSAGE:
        prefix = "I previously said"
    elif record.record_type == RecordType.THOUGHT:
        prefix = "I once considered, without treating it as verified"
    elif record.record_type == RecordType.NOTIFICATION:
        prefix = "I received a notification"
    else:
        prefix = "I remember"
    continuity = " Still relevant now," if retained else ""
    timestamp = f" ({record.timestamp})" if include_timestamps and record.timestamp else ""
    return f'{continuity} {prefix}, "{text}"{timestamp}'.strip()


def render_context(
    records: Sequence[MemoryRecord],
    *,
    retained_record_ids: Iterable[str],
    current_input: str,
    source_id: str,
    maximum_chars: int,
    include_current_input: bool = True,
    protected_record_ids: Iterable[str] = (),
    include_timestamps: bool = False,
) -> ContextBundle:
    retained = set(retained_record_ids)
    protected = set(protected_record_ids)
    lines: list[str] = []
    included: list[str] = []
    omitted: list[str] = []
    current_length = 0
    for record in records:
        line = _render_record(
            record,
            retained=record.record_id in retained,
            include_timestamps=include_timestamps,
        )
        additional = len(line) + (1 if lines else 0)
        # Never alter an exact record. The first record may exceed the soft budget.
        if (
            record.record_id not in protected
            and lines
            and current_length + additional > maximum_chars
        ):
            omitted.append(record.record_id)
            continue
        lines.append(line)
        included.append(record.record_id)
        current_length += additional
    if include_current_input:
        input_line = f'{source_id} now says, "{current_input.strip()}"'
        lines.append(input_line)
    text = "\n".join(lines)
    return ContextBundle(
        text=text,
        record_ids=tuple(included),
        omitted_record_ids=tuple(omitted),
        char_count=len(text),
    )
