from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from .contracts import ActualizationBatch
from .perception import render_perception
from .runtime import Actualizer
from ._engine.embeddings import structured_feature_embedding
from ._engine.types import EventKind, InputTrunk, MemoryRecord, OutputTrunk, RecordType


@dataclass(frozen=True)
class SelfFrame:
    """One bounded language-facing view; IDs remain backend-only."""

    text: str
    current_record_id: str | None
    memory_record_ids: tuple[str, ...]
    rolling_record_ids: tuple[str, ...]
    char_count: int


@dataclass(frozen=True)
class SelfOutput:
    """The outward interpretation of one ordinary model generation."""

    batch: ActualizationBatch
    perception: str
    spoken_text: str


class SelfSession:
    """Bounded JIT-memory intake paired with schema-free actualization.

    This is deliberately not an LLM client or a timer. A host invokes
    ``prepare_input`` when an event arrives, asks any local model to generate,
    and passes that ordinary text to ``process_output``. Inputs arriving during
    generation can remain in the host's queue for the next atomic cycle.
    """

    def __init__(
        self,
        actualizer: Actualizer,
        *,
        session_id: str | None = None,
        rolling_records: int = 8,
        maximum_context_chars: int = 12_000,
        maximum_rolling_chars: int = 3_200,
    ) -> None:
        self.actualizer = actualizer
        self.session_id = session_id or f"session:{uuid.uuid4().hex}"
        self.rolling_records = max(0, int(rolling_records))
        self.maximum_context_chars = max(1024, int(maximum_context_chars))
        self.maximum_rolling_chars = max(0, int(maximum_rolling_chars))
        self._focus_metadata_key = f"self_session.focus:{self.session_id}"
        existing_records = self._session_records()
        self._rolling_events: list[tuple[str | None, str]] = [
            (record.record_id, self._rolling_line(record))
            for record in existing_records
        ]
        focus_records = [
            record for record in existing_records if record.metadata.get("session_focus")
        ]
        saved_focus = self.actualizer.mind.store.get_metadata(
            self._focus_metadata_key
        )
        if saved_focus is None:
            focus_record = focus_records[-1] if focus_records else None
        elif saved_focus:
            focus_record = next(
                (record for record in existing_records if record.record_id == saved_focus),
                None,
            )
        else:
            focus_record = None
        self._focus_event: tuple[str | None, str] | None = (
            (focus_record.record_id, self._rolling_line(focus_record))
            if focus_record is not None
            else None
        )

    def _session_records(self) -> list[MemoryRecord]:
        return [
            record
            for record in self.actualizer.mind.store.list_active_records()
            if record.metadata.get("session_id") == self.session_id
            and record.record_type
            in {RecordType.INBOUND_MESSAGE, RecordType.OUTBOUND_MESSAGE}
        ]

    @staticmethod
    def _rolling_line(record: MemoryRecord) -> str:
        if record.record_type == RecordType.OUTBOUND_MESSAGE:
            return f'I said, "{record.text.strip()}"'
        return f'{record.source_id} said, "{record.text.strip()}"'

    def _rolling(self, *, exclude_outbound: bool = False) -> tuple[list[str], str]:
        if self.rolling_records == 0 or self.maximum_rolling_chars == 0:
            return [], ""
        focus = self._focus_event
        if exclude_outbound and focus is not None and focus[1].startswith('I said, "'):
            focus = None
        candidates = [
            event
            for event in self._rolling_events
            if event != focus
            and not (exclude_outbound and event[1].startswith('I said, "'))
        ]
        selected: list[tuple[str | None, str]] = []
        used = 0
        reserved = len(focus[1]) + 1 if focus is not None else 0
        recent_limit = max(0, self.rolling_records - int(focus is not None))
        if recent_limit:
            for record_id, line in reversed(candidates):
                added = len(line) + (1 if selected else 0)
                if selected and used + added + reserved > self.maximum_rolling_chars:
                    break
                if not selected and added + reserved > self.maximum_rolling_chars:
                    continue
                selected.append((record_id, line))
                used += added
                if len(selected) >= recent_limit:
                    break
        selected.reverse()
        if focus is not None and len(focus[1]) <= self.maximum_rolling_chars:
            selected.insert(0, focus)
        return (
            [record_id for record_id, _ in selected if record_id is not None],
            "\n".join(line for _, line in selected),
        )

    def _append_rolling(self, line: str, record_id: str | None = None) -> None:
        self._rolling_events.append((record_id, str(line).strip()))
        # This is only short-term projection state. Durable language records
        # remain in SQLite and will be reloaded if the same session resumes.
        maximum_events = max(16, self.rolling_records * 4)
        if len(self._rolling_events) > maximum_events:
            self._rolling_events = self._rolling_events[-maximum_events:]

    @staticmethod
    def _current_line(text: str, source_id: str, *, observation: bool) -> str:
        cleaned = str(text).strip()
        if observation:
            return f"I now observe:\n{cleaned}"
        return f'{source_id} now says, "{cleaned}"'

    @staticmethod
    def _is_local_followup(text: str) -> bool:
        """Whether a short input points primarily to the preceding utterance."""
        cleaned = str(text).strip().casefold()
        if not cleaned or len(cleaned.split()) > 24:
            return False
        return bool(
            re.search(r"\b(?:repeat|rephrase|summarize|clarify)\b", cleaned)
            and re.search(
                r"\b(?:it|that|this|last|previous|answer|reply|statement)\b",
                cleaned,
            )
            or re.search(r"\bsay\b.{0,24}\bthat\b.{0,16}\bagain\b", cleaned)
        )

    def _latest_rolling_outbound(
        self, rolling_record_ids: list[str]
    ) -> tuple[str | None, str] | None:
        selected = set(rolling_record_ids)
        return next(
            (
                event
                for event in reversed(self._rolling_events)
                if event[0] in selected and event[1].startswith('I said, "')
            ),
            None,
        )

    def _frame(
        self,
        text: str,
        *,
        source_id: str,
        current_record_id: str | None,
        observation: bool,
        event_kind: EventKind | None = None,
    ) -> SelfFrame:
        action_evidence_query = self.actualizer.mind.retrieval.asks_for_action_evidence(
            text
        )
        rolling_record_ids, rolling_text = self._rolling(
            exclude_outbound=action_evidence_query
        )
        active_focus_text = ""
        if (
            observation
            and self._focus_event is not None
            and self._focus_event[0] in set(rolling_record_ids)
        ):
            active_focus_text = self._focus_event[1]
            if active_focus_text in rolling_text:
                rolling_text = rolling_text.replace(active_focus_text, "", 1).strip()
        local_outbound = (
            self._latest_rolling_outbound(rolling_record_ids)
            if self._is_local_followup(text) and not action_evidence_query
            else None
        )
        local_outbound_text = local_outbound[1] if local_outbound is not None else ""
        if local_outbound_text and local_outbound_text in rolling_text:
            before, _, after = rolling_text.rpartition(local_outbound_text)
            rolling_text = "\n".join(part for part in (before.strip(), after.strip()) if part)
        current_line = self._current_line(text, source_id, observation=observation)
        reserved = (
            len(current_line)
            + len(rolling_text)
            + len(local_outbound_text)
            + len(active_focus_text)
            + 4
        )
        memory_budget = max(512, self.maximum_context_chars - reserved)
        excluded = list(rolling_record_ids)
        if current_record_id is not None:
            excluded.append(current_record_id)
        recalled = self.actualizer.mind.recall(
            text,
            kind=event_kind or (
                EventKind.OBSERVATION if observation else EventKind.MESSAGE
            ),
            source_id=source_id,
            exclude_record_ids=excluded,
            include_current_input=False,
            maximum_context_chars=memory_budget,
        )
        memory_text = recalled.context.strip()
        if local_outbound_text:
            # The graph and working-memory update still happened above. For a
            # short deictic continuation, however, unrelated JIT memories are
            # language distractors: the immediately preceding reply is the
            # complete local referent.
            rolling_text = ""
            memory_text = ""
        # Keep conversational continuity first, then place current JIT evidence
        # immediately before the live input. This lets authoritative memory
        # correct an earlier mistaken utterance instead of being shadowed by it.
        parts = [
            part
            for part in (
                rolling_text,
                memory_text,
                local_outbound_text,
                active_focus_text,
                current_line,
            )
            if part
        ]
        rendered = "\n".join(parts)
        if len(rendered) > self.maximum_context_chars:
            # This trims only the transient projection. Canonical memory and
            # complete receipts remain unchanged in SQLite.
            overflow = len(rendered) - self.maximum_context_chars
            memory_text = memory_text.strip()
            if memory_text:
                memory_text = memory_text[min(len(memory_text), overflow) :].lstrip()
            parts = [
                part
                for part in (
                    rolling_text,
                    memory_text,
                    local_outbound_text,
                    active_focus_text,
                    current_line,
                )
                if part
            ]
            rendered = "\n".join(parts)[-self.maximum_context_chars :]
        return SelfFrame(
            text=rendered,
            current_record_id=current_record_id,
            memory_record_ids=recalled.context_bundle.record_ids,
            rolling_record_ids=tuple(rolling_record_ids),
            char_count=len(rendered),
        )

    def _open_speech_cycle_id(self) -> str | None:
        matching = [
            cycle
            for cycle in self.actualizer.mind.open_experience_cycles(OutputTrunk.SPEAK)
            if cycle.metadata.get("session_id") == self.session_id
        ]
        if not matching:
            return None
        return max(matching, key=lambda cycle: cycle.opened_pulse).cycle_id

    def prepare_input(
        self,
        text: str,
        *,
        source_id: str = "human",
        stability_delta: float = 0.0,
        preference_confidence: float = 1.0,
        set_focus: bool = True,
    ) -> SelfFrame:
        """Observe input and causally attach it to my preceding speech, if any.

        The host may provide a bounded stability signal when the message is
        known to be positive or negative feedback. Ordinary conversation is
        neutral by default: it remains experience, but is not invented reward.
        """
        metadata = {
            "session_id": self.session_id,
            "session_role": "input",
            "session_focus": bool(set_focus),
        }
        open_cycle_id = self._open_speech_cycle_id()
        if open_cycle_id is None:
            record = self.actualizer.mind.remember(
                text,
                kind=EventKind.MESSAGE,
                source_id=source_id,
                metadata={
                    **metadata,
                    "stability_delta": float(stability_delta),
                    "preference_confidence": float(preference_confidence),
                },
            )
        else:
            returned = self.actualizer.mind.record_cycle_return(
                open_cycle_id,
                text,
                input_trunk=InputTrunk.HEAR,
                status="observed",
                stability_delta=stability_delta,
                verified=True,
                source_id=source_id,
                record_type=RecordType.INBOUND_MESSAGE,
                preference_confidence=preference_confidence,
                metadata=metadata,
            )
            record = returned.record
        frame = self._frame(
            text,
            source_id=source_id,
            current_record_id=record.record_id,
            observation=False,
        )
        self._append_rolling(self._rolling_line(record), record.record_id)
        if set_focus:
            self._focus_event = (record.record_id, self._rolling_line(record))
            self.actualizer.mind.store.set_metadata(
                self._focus_metadata_key,
                record.record_id,
            )
        return frame

    def clear_focus(self) -> None:
        """Unpin a completed external request across process restarts."""
        self._focus_event = None
        self.actualizer.mind.store.set_metadata(self._focus_metadata_key, "")

    def prepare_notice(
        self,
        text: str,
        *,
        source_id: str = "environment",
        stability_delta: float = 0.0,
        preference_confidence: float = 1.0,
        sensory_features: tuple[str, ...] = (),
    ) -> SelfFrame:
        """Persist a non-conversational notification through the NOTICE lane."""
        record = self.actualizer.mind.remember(
            text,
            kind=EventKind.NOTIFICATION,
            source_id=source_id,
            record_type=RecordType.NOTIFICATION,
            input_trunk=InputTrunk.NOTICE,
            metadata={
                "session_id": self.session_id,
                "session_role": "notice",
                "stability_delta": float(stability_delta),
                "preference_confidence": float(preference_confidence),
                "sensory_features": tuple(sensory_features),
            },
            embedding=(
                structured_feature_embedding(
                    sensory_features,
                    self.actualizer.mind.embedder.dimension,
                    namespace="NOTICE",
                )
                if sensory_features
                else None
            ),
        )
        frame = self._frame(
            text,
            source_id=source_id,
            current_record_id=record.record_id,
            observation=True,
            event_kind=EventKind.NOTIFICATION,
        )
        self._append_rolling(f"I received a notice: {str(text).strip()}", record.record_id)
        return frame

    def prepare_idle(
        self,
        cue: str = (
            "Nothing new requires my attention. The most recent outward request, "
            "if any, is complete, so I do not repeat it without a new reason. I may "
            "briefly reconsider something useful or remain still."
        ),
    ) -> SelfFrame:
        """Build a private JIT frame without inventing an external stimulus."""
        rolling_record_ids, rolling_text = self._rolling()
        memory_budget = max(
            512,
            self.maximum_context_chars - len(rolling_text) - len(cue) - 2,
        )
        recalled = self.actualizer.mind.recall(
            cue,
            kind=EventKind.NOTIFICATION,
            source_id="self",
            exclude_record_ids=rolling_record_ids,
            include_current_input=False,
            maximum_context_chars=memory_budget,
        )
        parts = [
            part
            for part in (rolling_text, recalled.context.strip(), cue.strip())
            if part
        ]
        rendered = "\n".join(parts)[-self.maximum_context_chars :]
        return SelfFrame(
            text=rendered,
            current_record_id=None,
            memory_record_ids=recalled.context_bundle.record_ids,
            rolling_record_ids=tuple(rolling_record_ids),
            char_count=len(rendered),
        )

    def prepare_observation(self, perception: str) -> SelfFrame:
        """Prepare a derived view of a result already stored by Actualizer."""
        frame = self._frame(
            perception,
            source_id="environment",
            current_record_id=None,
            observation=True,
        )
        self._append_rolling(f"I observed, {str(perception).strip()}")
        return frame

    def remember_response(self, text: str) -> MemoryRecord:
        decision = self.actualizer.mind.classify_output(
            text,
            effect_hint=OutputTrunk.SPEAK,
            required_output_trunk=OutputTrunk.SPEAK,
        )
        cycle = self.actualizer.mind.begin_output_cycle(
            text,
            decision,
            source_id="self",
            record_type=RecordType.OUTBOUND_MESSAGE,
            metadata={"session_id": self.session_id, "session_role": "output"},
        )
        record = self.actualizer.mind.store.get_record(cycle.output_record_id)
        if record is None:  # Defensive: begin_output_cycle persists atomically.
            raise RuntimeError("spoken output was not persisted")
        self._append_rolling(self._rolling_line(record), record.record_id)
        return record

    def remember_thought(self, text: str) -> MemoryRecord:
        """Persist private ordinary output without opening an external cycle."""
        return self.actualizer.mind.remember(
            text,
            kind=EventKind.NOTIFICATION,
            source_id="self",
            record_type=RecordType.THOUGHT,
            input_trunk=InputTrunk.NOTICE,
            metadata={
                "session_id": self.session_id,
                "session_role": "private",
                "unverified": True,
            },
            allow_growth=False,
        )

    async def process_output(self, text: str) -> SelfOutput:
        batch = await self.actualizer.actualize(text, source_role="assistant")
        if batch.receipts or batch.suppressed:
            perception = render_perception(
                batch,
                workspace_root=self.actualizer.policy.root,
            )
            spoken = ""
        else:
            self.remember_response(text)
            perception = ""
            spoken = str(text).strip()
        return SelfOutput(batch=batch, perception=perception, spoken_text=spoken)

    async def process_private_output(
        self,
        text: str,
        *,
        allow_actions: bool = True,
    ) -> SelfOutput:
        """Route an idle generation without externalizing ordinary prose."""
        batch = (
            await self.actualizer.actualize(text, source_role="assistant")
            if allow_actions
            else ActualizationBatch(source_role="assistant", source_text=str(text))
        )
        if batch.receipts or batch.suppressed:
            perception = render_perception(
                batch,
                workspace_root=self.actualizer.policy.root,
            )
        else:
            self.remember_thought(text)
            perception = ""
        return SelfOutput(batch=batch, perception=perception, spoken_text="")
