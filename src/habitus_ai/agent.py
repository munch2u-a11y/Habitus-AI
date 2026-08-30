from __future__ import annotations

import uuid
from concurrent.futures import Executor
from dataclasses import dataclass
from typing import Sequence

from .async_workers import await_sync_call

from .gestation import GestationProfile, load_profile
from .models import ChatMessage, ChatModel
from .pipeline import BaseAgenticMemoryRAG, RecallResult
from .types import (
    EventKind,
    MemoryRecord,
    OutcomePacket,
    OutputDecision,
    OutputTrunk,
    RecordType,
)


@dataclass(frozen=True)
class AgentTurn:
    experience_id: str
    user_record_id: str
    response_record_id: str
    response: str
    recall: RecallResult
    output_decision: OutputDecision


@dataclass(frozen=True)
class PreparedAgentTurn:
    """A completed HEAR phase waiting for generation in the SPEAK lane."""

    content: str
    inbound: MemoryRecord
    recall: RecallResult
    messages: tuple[ChatMessage, ...]


class HatchedAgent:
    """Persistent conversational shell around one gestated memory substrate."""

    def __init__(
        self,
        mind: BaseAgenticMemoryRAG,
        model: ChatModel,
        *,
        history_messages: int = 8,
    ):
        profile = load_profile(mind)
        if profile is None:
            raise ValueError("this mind has not been gestated; run the setup adapter first")
        self.mind = mind
        self.model = model
        self.profile: GestationProfile = profile
        self.history_messages = max(0, int(history_messages))

    def _recent_messages(
        self,
        *,
        excluded_record_ids: Sequence[str],
    ) -> list[ChatMessage]:
        excluded = set(excluded_record_ids)
        conversation: list[MemoryRecord] = [
            record
            for record in self.mind.store.list_active_records()
            if record.record_id not in excluded
            and record.record_type
            in {RecordType.INBOUND_MESSAGE, RecordType.OUTBOUND_MESSAGE}
        ]
        selected = conversation[-self.history_messages :] if self.history_messages else []
        return [
            {
                "role": "user" if record.record_type == RecordType.INBOUND_MESSAGE else "assistant",
                "content": record.text,
            }
            for record in selected
        ]

    def _model_messages(
        self,
        text: str,
        recall: RecallResult,
        *,
        current_record_id: str,
    ) -> list[ChatMessage]:
        instruction = (
            "Reply naturally in first person as one participant in this conversation. "
            "Use the supplied first-person memories when relevant, and do not invent "
            "completed external actions."
        )
        memory_text = recall.context.strip()
        system_text = f"{instruction}\n{memory_text}" if memory_text else instruction
        excluded = (current_record_id, *recall.context_bundle.record_ids)
        messages: list[ChatMessage] = [{"role": "system", "content": system_text}]
        messages.extend(self._recent_messages(excluded_record_ids=excluded))
        messages.append({"role": "user", "content": text})
        return messages

    def prepare_turn(self, text: str) -> PreparedAgentTurn:
        """Finish the short HEAR-side memory and recall phase."""
        content = str(text).strip()
        if not content:
            raise ValueError("message cannot be empty")
        pending_speech = self.mind.open_experience_cycles(OutputTrunk.SPEAK)
        if pending_speech:
            previous = pending_speech[-1]
            returned = self.mind.record_cycle_return(
                previous.cycle_id,
                content,
                input_trunk="HEAR",
                status="response",
                stability_delta=0.0,
                verified=True,
                terminal=True,
                source_id=self.profile.human_name,
                record_type=RecordType.INBOUND_MESSAGE,
                preference_confidence=0.0,
                metadata={"conversation": True, "response_to_previous_output": True},
            )
            inbound = returned.record
        else:
            # The first heard message has no earlier self-output to return to.
            # It is retained as an explicitly exogenous bootstrap experience.
            inbound = self.mind.remember(
                content,
                kind=EventKind.MESSAGE,
                source_id=self.profile.human_name,
                record_type=RecordType.INBOUND_MESSAGE,
                metadata={
                    "conversation": True,
                    "experience_id": f"exogenous:{uuid.uuid4().hex}",
                    "cycle_role": "exogenous",
                },
            )
        recall = self.mind.recall(
            content,
            kind=EventKind.MESSAGE,
            source_id=self.profile.human_name,
            exclude_record_ids=(inbound.record_id,),
            include_current_input=False,
        )
        messages = tuple(
            self._model_messages(content, recall, current_record_id=inbound.record_id)
        )
        return PreparedAgentTurn(content, inbound, recall, messages)

    def complete_prepared_turn(
        self,
        prepared: PreparedAgentTurn,
        response: str,
    ) -> AgentTurn:
        """Commit an already-generated response through the SPEAK tree."""
        response = str(response).strip()
        if not response:
            raise ValueError("chat model returned an empty response")

        # The transport chose external conversation. Classification never grants
        # tool authority; it only routes this already-selected speech effect.
        decision = self.mind.classify_output(response, effect_hint=OutputTrunk.SPEAK)
        cycle = self.mind.begin_output_cycle(
            response,
            decision,
            source_id=self.profile.agent_name,
            record_type=RecordType.OUTBOUND_MESSAGE,
            provenance={"model": self.profile.model_name, "backend": self.profile.model_backend},
            metadata={
                "conversation": True,
                "reply_to": prepared.inbound.record_id,
            },
        )
        return AgentTurn(
            experience_id=cycle.cycle_id,
            user_record_id=prepared.inbound.record_id,
            response_record_id=cycle.output_record_id,
            response=response,
            recall=prepared.recall,
            output_decision=decision,
        )

    def turn(self, text: str) -> AgentTurn:
        prepared = self.prepare_turn(text)
        response = self.model.generate(prepared.messages)
        return self.complete_prepared_turn(prepared, response)

    async def generate_prepared_turn(
        self,
        prepared: PreparedAgentTurn,
        *,
        executor: Executor | None = None,
    ) -> AgentTurn:
        """Await model I/O without blocking unrelated runtime lanes."""
        response = await await_sync_call(
            self.model.generate,
            prepared.messages,
            executor=executor,
        )
        return self.complete_prepared_turn(prepared, response)

    def acknowledge_delivery(
        self,
        turn: AgentTurn,
        *,
        channel: str = "terminal",
        stability_delta: float = 0.02,
        receipt_id: str | None = None,
    ) -> OutcomePacket:
        receipt = receipt_id or f"receipt:{uuid.uuid4().hex}"
        existing = self.mind.store.get_record(receipt)
        if existing is not None:
            returns = self.mind.store.returns_for_experience_cycle(turn.experience_id)
            matched = next((item for item in returns if item.record_id == receipt), None)
            if matched is None:
                raise ValueError(f"receipt ID is already used outside this cycle: {receipt}")
            outcomes = self.mind.store.connection.execute(
                "SELECT payload_json FROM outcomes ORDER BY created_at, outcome_id"
            ).fetchall()
            for row in reversed(outcomes):
                import json

                payload = json.loads(row["payload_json"])
                if payload.get("receipt_id") == receipt:
                    return OutcomePacket(
                        outcome_id=payload["outcome_id"],
                        pulse_id=payload["pulse_id"],
                        output_trunk=(OutputTrunk(payload["output_trunk"]) if payload["output_trunk"] else None),
                        credited_edge_ids=tuple(payload["credited_edge_ids"]),
                        verified=bool(payload["verified"]),
                        stability_delta=payload["stability_delta"],
                        proposal_id=payload.get("proposal_id"),
                        receipt_id=payload.get("receipt_id"),
                        metadata=payload.get("metadata", {}),
                    )
            raise ValueError(f"cycle receipt has no outcome: {receipt}")
        result = self.mind.record_cycle_return(
            turn.experience_id,
            f"Delivered response {turn.response_record_id} through {channel}.",
            input_trunk="SEE",
            status="delivered",
            stability_delta=stability_delta,
            verified=True,
            terminal=False,
            source_id=channel,
            record_type=RecordType.RECEIPT,
            record_id=receipt,
            event_id=f"event:{receipt}",
            provenance={"channel": channel},
            metadata={
                "channel": channel,
                "effect": "speech_delivery",
                "delivered_record_id": turn.response_record_id,
            },
            # Transport confirmation is a nonverbal SEE consequence. Preserve
            # its lower projections without teaching random receipt IDs as
            # semantic concepts.
            allow_growth=False,
        )
        return result.outcome
