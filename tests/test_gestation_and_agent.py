from __future__ import annotations

import pytest

from habitus_ai import (
    BaseAgenticMemoryRAG,
    HatchedAgent,
    OutputTrunk,
    gestate,
    load_profile,
)
from habitus_ai.graph import OUTPUT_NODE_IDS
from habitus_ai.types import GraphSide, RecordType


class ScriptedModel:
    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages):
        self.calls.append([dict(message) for message in messages])
        return self.responses.pop(0)


def test_gestation_seeds_identity_taste_and_persistent_core(tmp_path):
    database = tmp_path / "nova.sqlite"
    with BaseAgenticMemoryRAG(database) as mind:
        profile = gestate(
            mind,
            human_name="Josh",
            agent_name="Nova",
            taste_schema="curious",
            model_name="test-model",
        )
        assert profile.agent_name == "Nova"
        assert mind.store.get_concept("identity:self") is not None
        assert mind.store.get_concept("identity:human") is not None
        assert mind.store.get_concept("taste:curious") is not None
        assert mind.core_record_ids() == (
            "gestation:self-identity",
            "gestation:human-identity",
        )
        look = mind.store.find_edge(
            GraphSide.OUTPUT, "SELF", OUTPUT_NODE_IDS[OutputTrunk.LOOK]
        )
        do = mind.store.find_edge(
            GraphSide.OUTPUT, "SELF", OUTPUT_NODE_IDS[OutputTrunk.DO]
        )
        probabilities = mind.graph.local_probabilities("SELF", GraphSide.OUTPUT)
        assert probabilities[look.edge_id] > probabilities[do.edge_id]
        with pytest.raises(ValueError, match="already hatched"):
            gestate(mind, human_name="Josh", agent_name="Nova")

    with BaseAgenticMemoryRAG(database) as reloaded:
        assert load_profile(reloaded).agent_name == "Nova"
        recalled = reloaded.recall("Tell me something entirely unrelated.")
        assert "My name is Nova" in recalled.context
        assert "Josh is the person I am growing alongside" in recalled.context


def test_hatched_agent_talks_records_receipt_and_survives_restart(tmp_path):
    database = tmp_path / "sprout.sqlite"
    model = ScriptedModel("I remember you, and I am ready to explore this with you.")
    with BaseAgenticMemoryRAG(database) as mind:
        gestate(
            mind,
            human_name="Josh",
            agent_name="Sprout",
            taste_schema="balanced",
            model_name="scripted",
        )
        agent = HatchedAgent(mind, model)
        speech_edge = mind.store.find_edge(
            GraphSide.OUTPUT, "SELF", OUTPUT_NODE_IDS[OutputTrunk.SPEAK]
        )
        before = speech_edge.log_strength
        turn = agent.turn("Hello. What do you remember about us?")
        assert turn.output_decision.trunk == OutputTrunk.SPEAK
        assert model.calls[0][-1] == {
            "role": "user",
            "content": "Hello. What do you remember about us?",
        }
        assert "My name is Sprout" in model.calls[0][0]["content"]
        assert "Josh is the person I am growing alongside" in model.calls[0][0]["content"]
        assert mind.store.get_record(turn.user_record_id).record_type == RecordType.INBOUND_MESSAGE
        assert mind.store.get_record(turn.response_record_id).record_type == RecordType.OUTBOUND_MESSAGE

        outcome = agent.acknowledge_delivery(
            turn,
            receipt_id="receipt:first-terminal-delivery",
        )
        assert outcome.verified is True
        assert mind.store.get_record("receipt:first-terminal-delivery").record_type == RecordType.RECEIPT
        assert mind.store.get_edge(speech_edge.edge_id).log_strength > before
        experience = mind.store.get_experience_state(turn.experience_id)
        assert experience.preference_mean == pytest.approx(0.02)
        assert all(
            projection.preference == pytest.approx(0.02)
            for projection in mind.store.projections_for_experience(turn.experience_id)
        )

    resumed_model = ScriptedModel("Our earlier exchange is still part of my memory.")
    with BaseAgenticMemoryRAG(database) as mind:
        resumed = HatchedAgent(mind, resumed_model)
        resumed.turn("Do you still have our earlier exchange?")
        supplied = "\n".join(
            message["content"] for message in resumed_model.calls[0]
        )
        assert "I remember you, and I am ready to explore this with you." in supplied


def test_hatched_conversation_begins_growing_new_input_branches(tmp_path):
    database = tmp_path / "growth.sqlite"
    model = ScriptedModel(
        "I noticed that.",
        "The pattern is repeating.",
        "That repetition is becoming a stable concept.",
    )
    with BaseAgenticMemoryRAG(database) as mind:
        gestate(
            mind,
            human_name="Josh",
            agent_name="Bud",
            taste_schema="deliberate",
            model_name="scripted",
        )
        initial = {concept.concept_id for concept in mind.store.list_concepts(kind="crown")}
        agent = HatchedAgent(mind, model)
        first = agent.turn("Quasar orchard calibration protocol appeared.")
        agent.acknowledge_delivery(first, receipt_id="receipt:growth-one")
        second = agent.turn("Quasar orchard calibration protocol appeared again.")
        agent.acknowledge_delivery(second, receipt_id="receipt:growth-two")
        third = agent.turn("Quasar orchard calibration protocol appeared once more.")
        agent.acknowledge_delivery(third, receipt_id="receipt:growth-three")
        grown = {concept.concept_id for concept in mind.store.list_concepts(kind="crown")} - initial
        assert len(grown) == 1
        concept_id = next(iter(grown))
        concept = mind.store.get_concept(concept_id)
        assert concept_id.startswith("concept:auto:")
        assert set(mind.store.vault_record_ids(concept.vault_id)) == {
            first.user_record_id,
            second.user_record_id,
            third.user_record_id,
        }
