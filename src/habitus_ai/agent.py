from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

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

    def turn(self, text: str) -> AgentTurn:
        content = str(text).strip()
        if not content:
            raise ValueError("message cannot be empty")
        experience_id = f"experience:{uuid.uuid4().hex}"
        inbound = self.mind.remember(
            content,
            kind=EventKind.MESSAGE,
            source_id=self.profile.human_name,
            record_type=RecordType.INBOUND_MESSAGE,
            metadata={"conversation": True, "experience_id": experience_id},
        )
        recall = self.mind.recall(
            content,
            kind=EventKind.MESSAGE,
            source_id=self.profile.human_name,
            exclude_record_ids=(inbound.record_id,),
            include_current_input=False,
        )
        response = self.model.generate(
            self._model_messages(content, recall, current_record_id=inbound.record_id)
        ).strip()
        if not response:
            raise ValueError("chat model returned an empty response")

        # The transport chose external conversation. Classification never grants
        # tool authority; it only routes this already-selected speech effect.
        decision = self.mind.classify_output(response, effect_hint=OutputTrunk.SPEAK)
        outbound = self.mind.remember(
            response,
            kind=EventKind.MESSAGE,
            source_id=self.profile.agent_name,
            record_type=RecordType.OUTBOUND_MESSAGE,
            provenance={"model": self.profile.model_name, "backend": self.profile.model_backend},
            metadata={
                "conversation": True,
                "reply_to": inbound.record_id,
                "experience_id": experience_id,
            },
            allow_growth=False,
        )
        if decision.trace is not None:
            self.mind.graph.deposit_trace(outbound, decision.trace, pulse=self.mind.pulse)
        return AgentTurn(
            experience_id=experience_id,
            user_record_id=inbound.record_id,
            response_record_id=outbound.record_id,
            response=response,
            recall=recall,
            output_decision=decision,
        )

    def acknowledge_delivery(
        self,
        turn: AgentTurn,
        *,
        channel: str = "terminal",
        stability_delta: float = 0.02,
        receipt_id: str | None = None,
    ) -> OutcomePacket:
        receipt = receipt_id or f"receipt:{uuid.uuid4().hex}"
        if self.mind.store.get_record(receipt) is None:
            self.mind.remember(
                f"Delivered response {turn.response_record_id} through {channel}.",
                kind=EventKind.OBSERVATION,
                source_id=channel,
                correlation_id=turn.response_record_id,
                record_id=receipt,
                event_id=f"event:{receipt}",
                record_type=RecordType.RECEIPT,
                provenance={"channel": channel},
                metadata={
                    "verified": True,
                    "delivered_record_id": turn.response_record_id,
                    "experience_id": turn.experience_id,
                    "stability_delta": stability_delta,
                    "preference_confidence": 1.0,
                },
                allow_growth=False,
            )
        return self.mind.record_outcome(
            turn.output_decision,
            stability_delta=stability_delta,
            verified=True,
            proposal_id=turn.response_record_id,
            receipt_id=receipt,
            metadata={"channel": channel, "effect": "speech_delivery"},
        )
