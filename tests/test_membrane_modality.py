from __future__ import annotations

from habitus_ai import BaseAgenticMemoryRAG, EventKind, InputTrunk
from habitus_ai.graph import PREFERENCE_NODE_IDS


def test_only_hear_intake_can_form_language_membrane_memory():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        hear_records = []
        see_records = []
        notice_records = []
        for index in range(2):
            hear_records.append(
                mind.remember(
                    "Quasar orchard language pattern repeats.",
                    input_trunk=InputTrunk.HEAR,
                    event_id=f"hear-event-{index}",
                    record_id=f"hear-{index}",
                )
            )
            see_records.append(
                mind.remember(
                    "Visible scarlet sensor pattern repeats.",
                    kind=EventKind.OBSERVATION,
                    input_trunk=InputTrunk.SEE,
                    event_id=f"see-event-{index}",
                    record_id=f"see-{index}",
                )
            )
            notice_records.append(
                mind.remember(
                    "Deferred violet notification pattern repeats.",
                    kind=EventKind.NOTIFICATION,
                    input_trunk=InputTrunk.NOTICE,
                    event_id=f"notice-event-{index}",
                    record_id=f"notice-{index}",
                )
            )

        assert all(record.metadata["membrane_words"] for record in hear_records)
        assert all(not record.metadata["membrane_words"] for record in see_records)
        assert all(not record.metadata["membrane_words"] for record in notice_records)

        # HEAR uses lexical embedding; the other senses use stable opaque
        # payload directions even though their transport happened to be text.
        assert list(hear_records[0].embedding) == mind.embedder.embed(hear_records[0].text)
        assert list(see_records[0].embedding) != mind.embedder.embed(see_records[0].text)
        assert see_records[0].embedding == see_records[1].embedding
        assert notice_records[0].embedding == notice_records[1].embedding

        crown = mind.store.list_concepts(kind="crown")
        children = mind.store.list_concepts(kind="child")
        assert len(crown) == 1
        assert len(children) == 3
        assert set(mind.store.vault_record_ids(crown[0].vault_id)) == {
            "hear-0", "hear-1"
        }
        for child in children:
            cluster = mind.store.overlap_cluster_for_child(child.concept_id)
            assert cluster is not None
            if cluster.parent_node_id in {
                PREFERENCE_NODE_IDS[(InputTrunk.SEE, "NEUTRAL")],
                PREFERENCE_NODE_IDS[(InputTrunk.NOTICE, "NEUTRAL")],
            }:
                assert cluster.semantic_node_id is None

        # Raw transports remain inspectable in the immutable developer ledger.
        assert mind.store.get_record("see-0").text == see_records[0].text
        assert mind.store.get_record("notice-0").text == notice_records[0].text
        assert mind.graph.validate_invariants() == []


def test_non_hear_words_never_enter_crown_vault_or_language_recall():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept(
            "shared-label",
            "Shared label",
            terms=("scarlet", "password"),
            input_trunks=("HEAR", "SEE", "NOTICE"),
        )
        heard = mind.remember(
            "The spoken amber passphrase belongs to HEAR.",
            input_trunk=InputTrunk.HEAR,
            concept_ids=("shared-label",),
            record_id="heard-language",
            event_id="heard-language-event",
        )
        seen = mind.remember(
            "SCARLET_SENSOR_PASSWORD must remain developer-only.",
            kind=EventKind.OBSERVATION,
            input_trunk=InputTrunk.SEE,
            concept_ids=("shared-label",),
            record_id="seen-transport",
            event_id="seen-transport-event",
        )
        noticed = mind.remember(
            "VIOLET_NOTICE_PASSWORD must remain developer-only.",
            kind=EventKind.NOTIFICATION,
            input_trunk=InputTrunk.NOTICE,
            concept_ids=("shared-label",),
            record_id="notice-transport",
            event_id="notice-transport-event",
        )

        concept = mind.store.get_concept("shared-label")
        assert mind.store.vault_record_ids(concept.vault_id) == [heard.record_id]

        sensory_query = mind.recall(
            "What is SCARLET_SENSOR_PASSWORD or VIOLET_NOTICE_PASSWORD?",
            include_current_input=False,
        )
        assert seen.record_id not in sensory_query.packet.direct_record_ids
        assert seen.record_id not in sensory_query.packet.vault_record_ids
        assert noticed.record_id not in sensory_query.packet.direct_record_ids
        assert noticed.record_id not in sensory_query.packet.vault_record_ids
        assert "SCARLET_SENSOR_PASSWORD" not in sensory_query.context
        assert "VIOLET_NOTICE_PASSWORD" not in sensory_query.context

        language_query = mind.recall(
            "What spoken amber passphrase belongs to HEAR?",
            include_current_input=False,
        )
        assert heard.record_id in language_query.packet.selected_record_ids
        assert "spoken amber passphrase" in language_query.context
