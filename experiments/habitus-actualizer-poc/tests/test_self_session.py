import asyncio

from habitus_actualizer import Actualizer, SelfSession, WorkspacePolicy
from habitus_actualizer._engine.types import OutputTrunk, RecordType


def test_speech_then_input_forms_one_output_return_cycle(tmp_path):
    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            session = SelfSession(actualizer, session_id="session:test")
            session.prepare_input("My preferred color is teal.", source_id="Josh")
            reply = await session.process_output("I will remember that you prefer teal.")

            assert reply.spoken_text == "I will remember that you prefer teal."
            opened = actualizer.mind.open_experience_cycles(OutputTrunk.SPEAK)
            assert len(opened) == 1

            frame = session.prepare_input(
                "Yes, that is right.",
                source_id="Josh",
                stability_delta=0.8,
            )
            closed = actualizer.mind.experience_cycle(opened[0].cycle_id)

            assert closed is not None and closed.status == "closed"
            assert closed.terminal_return_record_id == frame.current_record_id
            record = actualizer.mind.store.get_record(frame.current_record_id)
            assert record is not None
            assert record.record_type == RecordType.INBOUND_MESSAGE
            assert record.metadata["returns_to"] == opened[0].output_record_id

    asyncio.run(scenario())


def test_action_result_is_clean_perception_and_session_remembers_final_speech(tmp_path):
    (tmp_path / "brief.txt").write_text("PROJECT-CODE=cedar-41", encoding="utf-8")

    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            session = SelfSession(
                actualizer,
                session_id="session:task",
                maximum_context_chars=1600,
            )
            initial = session.prepare_input(
                "Please read brief.txt and tell me the project code.",
                source_id="Josh",
            )
            assert "Please read brief.txt" in initial.text
            assert initial.text.count("Please read brief.txt") == 1
            assert "record:" not in initial.text

            action = await session.process_output("I'll read `brief.txt`.")
            assert action.spoken_text == ""
            assert "PROJECT-CODE=cedar-41" in action.perception
            assert "sha256" not in action.perception
            observation = session.prepare_observation(action.perception)
            assert "I now observe" in observation.text
            assert "PROJECT-CODE=cedar-41" in observation.text

            next_observation = session.prepare_observation("I found a second clue.")
            assert "PROJECT-CODE=cedar-41" in next_observation.text
            assert "I found a second clue." in next_observation.text

            final = await session.process_output("The project code is cedar-41.")
            assert final.spoken_text == "The project code is cedar-41."
            follow_up = session.prepare_input("What did you just find?", source_id="Josh")

            assert follow_up.char_count <= 1600
            assert "The project code is cedar-41." in follow_up.text

    asyncio.run(scenario())


def test_action_history_question_receives_verified_results_not_private_thoughts(tmp_path):
    (tmp_path / "object.txt").write_text("OBJECT=blue square", encoding="utf-8")
    (tmp_path / "status.py").write_text("print('STATUS=green')\n", encoding="utf-8")
    state = tmp_path / ".habitus" / "mind.sqlite"
    policy = WorkspacePolicy(tmp_path, allowed_commands=("python3",))

    async def create_history():
        async with Actualizer(tmp_path, state_path=state, policy=policy) as actualizer:
            session = SelfSession(actualizer, session_id="session:evidence")
            await session.process_output("I'll read `object.txt`.")
            await session.process_output("I'll run `python3 status.py`.")
            session.remember_thought("I have never inspected an object or run a program.")
            session.remember_response("I have not inspected or run anything yet.")

    asyncio.run(create_history())

    with Actualizer(tmp_path, state_path=state, policy=policy) as actualizer:
        actualizer.mind.recall(
            "What did I once consider about inspecting an object?",
            include_current_input=False,
        )
        session = SelfSession(actualizer, session_id="session:evidence")
        frame = session.prepare_input(
            "What object did I inspect, and what program did I successfully run?",
            source_id="Josh",
        )

        assert "I directly verified" in frame.text
        assert "OBJECT=blue square" in frame.text
        assert "python3 status.py" in frame.text
        assert "STATUS=green" in frame.text
        assert "I have never inspected" not in frame.text
        assert "I said, \"I have not inspected" not in frame.text
        assert frame.text.index("I directly verified") < frame.text.index(
            "Josh now says"
        )

        provenance = session.prepare_input(
            "Did you actually run `cat object.txt`, or did you read it without a shell command?",
            source_id="Josh",
        )
        assert "workspace read ability" in provenance.text
        assert "I did not run a shell command" in provenance.text
        assert "I have not inspected or run anything" not in provenance.text
        assert provenance.text.index("I directly verified") < provenance.text.index(
            "Josh now says"
        )


def test_active_human_task_stays_pinned_while_observations_roll(tmp_path):
    with Actualizer(tmp_path) as actualizer:
        session = SelfSession(
            actualizer,
            session_id="session:focus",
            rolling_records=3,
        )
        session.prepare_input("Find and run the health reporter.", source_id="Josh")
        for number in range(5):
            session.prepare_observation(f"Observation {number}")
        frame = session.prepare_observation("Latest observation")

        assert "Find and run the health reporter." in frame.text
        assert "Observation 4" in frame.text
        assert "Latest observation" in frame.text
        assert frame.text.index("Observation 4") < frame.text.index(
            "Find and run the health reporter."
        )
        assert frame.text.index("Find and run the health reporter.") < frame.text.index(
            "Latest observation"
        )


def test_short_deictic_followup_keeps_immediate_reply_closest_to_input(tmp_path):
    (tmp_path / "object.txt").write_text("OBJECT=blue square", encoding="utf-8")
    with Actualizer(tmp_path) as actualizer:
        session = SelfSession(actualizer, session_id="session:deictic")
        asyncio.run(session.process_output("I'll read `object.txt`."))
        actualizer.mind.recall(
            "What file did I actually read?",
            include_current_input=False,
        )
        session.remember_response("I read it directly without a shell command.")

        frame = session.prepare_input(
            "Can you repeat that in one short sentence?",
            source_id="Josh",
        )

        assert "I directly verified" not in frame.text
        assert "OBJECT=blue square" not in frame.text
        assert frame.text.index(
            'I said, "I read it directly without a shell command."'
        ) < frame.text.index("Josh now says")

    assert SelfSession._is_local_followup(
        "Can you repeat that in one short sentence?"
    )
    assert not SelfSession._is_local_followup("What is her birthday?")


def test_cleared_focus_stays_unpinned_after_restart(tmp_path):
    state = tmp_path / "mind.sqlite"
    with Actualizer(tmp_path, state_path=state) as actualizer:
        session = SelfSession(actualizer, session_id="session:clear", rolling_records=1)
        session.prepare_input("A completed old task", source_id="Josh")
        session.clear_focus()

    with Actualizer(tmp_path, state_path=state) as actualizer:
        resumed = SelfSession(actualizer, session_id="session:clear", rolling_records=1)
        assert resumed._focus_event is None
        assert actualizer.mind.store.get_metadata(
            "self_session.focus:session:clear"
        ) == ""


def test_shared_nonverbal_notice_features_grow_a_child_without_semantic_words(tmp_path):
    features = ("object:blue-square", "shape:square", "fit:matched")
    with Actualizer(tmp_path) as actualizer:
        session = SelfSession(actualizer, session_id="session:sensory-growth")
        first = session.prepare_notice(
            "The blue object fit the opening.",
            stability_delta=0.5,
            sensory_features=features,
        )
        second = session.prepare_notice(
            "The matching object settled cleanly.",
            stability_delta=0.7,
            sensory_features=features,
        )

        children = actualizer.mind.store.list_concepts(kind="child")
        promoted = [
            cluster
            for parent in actualizer.mind.store.list_concepts(kind="lower_preference")
            for cluster in actualizer.mind.overlap_clusters(parent.concept_id)
            if cluster.child_node_id is not None
        ]
        records = [
            actualizer.mind.store.get_record(first.current_record_id),
            actualizer.mind.store.get_record(second.current_record_id),
        ]

        assert len(children) == 1
        assert len(promoted) == 1
        assert promoted[0].semantic_node_id is None
        assert all(record is not None for record in records)
        assert all(record.metadata["membrane_words"] is False for record in records)
        assert actualizer.graph_health()["healthy"] is True


def test_repeated_nonverbal_pattern_applies_the_same_growth_kernel_recursively(tmp_path):
    features = ("object:blue-square", "shape:square", "fit:matched")
    with Actualizer(tmp_path) as actualizer:
        session = SelfSession(actualizer, session_id="session:recursive-growth")
        for number in range(5):
            session.prepare_notice(
                f"Blue pattern exposure {number}.",
                stability_delta=0.6,
                sensory_features=features,
            )

        children = actualizer.mind.store.list_concepts(kind="child")
        child_ids = {item.concept_id for item in children}
        recursive_edges = [
            edge
            for edge in actualizer.mind.store.list_edges()
            if edge.source_id in child_ids and edge.target_id in child_ids
        ]
        layer_four = actualizer.mind.store.connection.execute(
            "SELECT COUNT(*) FROM experience_projections WHERE layer = 4"
        ).fetchone()[0]

        assert len(children) == 2
        assert len(recursive_edges) == 1
        assert layer_four >= 3
        assert actualizer.graph_health()["healthy"] is True


def test_coactivated_nonverbal_branches_grow_one_multi_parent_child(tmp_path):
    first_features = ("object:blue", "shape:square", "fit:matched")
    second_features = ("device:lamp", "sense:status", "state:available")
    combined_features = (*first_features, *second_features)
    with Actualizer(tmp_path) as actualizer:
        session = SelfSession(actualizer, session_id="session:branch-collision")
        for number in range(2):
            session.prepare_notice(
                f"Blue exposure {number}.",
                stability_delta=0.5,
                sensory_features=first_features,
            )
        for number in range(3):
            session.prepare_notice(
                f"Lamp exposure {number}.",
                stability_delta=0.5,
                sensory_features=second_features,
            )
        base_children = {
            item.concept_id
            for item in actualizer.mind.store.list_concepts(kind="child")
        }
        assert len(base_children) == 2

        for number in range(3):
            session.prepare_notice(
                f"Blue and lamp coactivation {number}.",
                stability_delta=0.5,
                sensory_features=combined_features,
            )

        final_children = {
            item.concept_id
            for item in actualizer.mind.store.list_concepts(kind="child")
        }
        composite = tuple(final_children - base_children)
        incoming = {
            edge.source_id
            for edge in actualizer.mind.store.list_edges()
            if composite and edge.target_id == composite[0]
        }

        assert len(composite) == 1
        assert incoming == base_children

        for number in range(3, 6):
            session.prepare_notice(
                f"Blue and lamp coactivation {number}.",
                stability_delta=0.5,
                sensory_features=combined_features,
            )

        deepest = {
            item.concept_id
            for item in actualizer.mind.store.list_concepts(kind="child")
        } - final_children
        deepest_incoming = {
            edge.source_id
            for edge in actualizer.mind.store.list_edges()
            if deepest and edge.target_id == next(iter(deepest))
        }

        assert len(deepest) == 1
        assert deepest_incoming == {composite[0]}
        assert actualizer.graph_health()["healthy"] is True
