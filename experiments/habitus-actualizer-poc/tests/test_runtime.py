from pathlib import Path

from habitus_actualizer import AbilityId, Actualizer, WorkspacePolicy
from habitus_actualizer._engine.types import GraphSide


def test_read_and_list_produce_verified_causal_receipts(tmp_path):
    (tmp_path / "README.md").write_text("proof content", encoding="utf-8")

    with Actualizer(tmp_path) as actualizer:
        batch = actualizer.actualize_sync(
            "I'll read `README.md` and list `.`."
        )

        assert [item.status for item in batch.receipts] == ["success", "success"]
        assert batch.receipts[0].output["content"] == "proof content"
        assert batch.receipts[0].trace_node_ids == (
            "SELF",
            "OUT:LOOK",
            "ability:workspace.read",
        )
        assert all(item.verified for item in batch.receipts)
        assert all(item.cycle_id and item.return_record_id for item in batch.receipts)
        assert actualizer.graph_health()["healthy"] is True


def test_missing_file_is_an_observed_failure_not_false_success(tmp_path):
    with Actualizer(tmp_path) as actualizer:
        batch = actualizer.actualize_sync("I'll read `missing.txt`.")
        assert batch.acted is True
        assert batch.receipts[0].status == "error"
        assert batch.receipts[0].verified is True
        assert "missing.txt" in batch.receipts[0].error


def test_success_and_failure_change_the_exact_ability_path(tmp_path):
    (tmp_path / "present.txt").write_text("yes", encoding="utf-8")
    with Actualizer(tmp_path) as actualizer:
        edge = actualizer.mind.store.find_edge(
            GraphSide.OUTPUT,
            "OUT:LOOK",
            "ability:workspace.read",
        )
        assert edge is not None
        baseline = edge.log_strength

        actualizer.actualize_sync("I'll read `present.txt`.")
        after_success = actualizer.mind.store.get_edge(edge.edge_id).log_strength
        actualizer.actualize_sync("I'll read `missing.txt`.")
        after_failure = actualizer.mind.store.get_edge(edge.edge_id).log_strength

        assert after_success > baseline
        assert after_failure < after_success


def test_write_is_disabled_then_verifies_readback_when_enabled(tmp_path):
    with Actualizer(tmp_path) as actualizer:
        blocked = actualizer.actualize_sync(
            "I'll write \"hello\" to \"note.txt\"."
        )
        assert blocked.receipts == ()
        assert "writes are disabled" in blocked.suppressed[0].reason

    policy = WorkspacePolicy(tmp_path, allow_write=True)
    with Actualizer(tmp_path, policy=policy) as actualizer:
        written = actualizer.actualize_sync(
            "I'll write \"hello\" to \"note.txt\"."
        )
        assert written.receipts[0].status == "success"
        assert written.receipts[0].output["read_back_verified"] is True
        assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "hello"


def test_empty_write_is_suppressed_without_creating_or_reinforcing(tmp_path):
    policy = WorkspacePolicy(tmp_path, allow_write=True)
    with Actualizer(tmp_path, policy=policy) as actualizer:
        result = actualizer.actualize_sync("I'll create `empty.txt`.")

        assert result.receipts == ()
        assert result.suppressed[0].reason == "write content is empty"
        assert not (tmp_path / "empty.txt").exists()


def test_run_requires_allowlist_and_returns_process_evidence(tmp_path):
    with Actualizer(tmp_path) as actualizer:
        blocked = actualizer.actualize_sync("I'll run `python3 --version`.")
        assert blocked.receipts == ()
        assert "not allowlisted" in blocked.suppressed[0].reason

    policy = WorkspacePolicy(tmp_path, allowed_commands=("python3",))
    with Actualizer(tmp_path, policy=policy) as actualizer:
        executed = actualizer.actualize_sync("I'll run `python3 --version`.")
        receipt = executed.receipts[0]
        assert receipt.status == "success"
        assert receipt.output["returncode"] == 0
        assert "Python" in receipt.output["stdout"]


def test_invalid_candidate_does_not_consume_per_pulse_ability_slot(tmp_path):
    (tmp_path / "visible.txt").write_text("proof", encoding="utf-8")
    with Actualizer(tmp_path, maximum_abilities=1) as actualizer:
        batch = actualizer.actualize_sync(
            "I'll run `invented-command`, then list `.`."
        )

    assert [request.ability_id for request in batch.requests] == [AbilityId.LIST]
    assert batch.receipts[0].verified is True
    assert any("not allowlisted" in item.reason for item in batch.suppressed)
    assert not any(
        item.ability_id == AbilityId.LIST
        and item.reason == "per-pulse ability limit reached"
        for item in batch.suppressed
    )


def test_path_escape_and_secret_read_are_suppressed_before_graph_activation(tmp_path):
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    with Actualizer(tmp_path) as actualizer:
        pulse_before = actualizer.mind.pulse
        escaped = actualizer.actualize_sync("I'll read `../outside.txt`.")
        secret = actualizer.actualize_sync("I'll read `.env`.")
        assert escaped.receipts == ()
        assert secret.receipts == ()
        assert actualizer.mind.pulse == pulse_before


def test_virtual_navigation_persists_across_restart(tmp_path):
    folder = tmp_path / "nested"
    folder.mkdir()
    (folder / "item.txt").write_text("nested evidence", encoding="utf-8")

    with Actualizer(tmp_path) as actualizer:
        moved = actualizer.actualize_sync("I'll go to `nested`.")
        assert moved.receipts[0].output["current"] == "nested"

    with Actualizer(tmp_path) as actualizer:
        read = actualizer.actualize_sync("I'll read `item.txt`.")
        assert read.receipts[0].output["content"] == "nested evidence"


def test_state_and_sensitive_files_are_hidden_from_listing(tmp_path):
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    with Actualizer(tmp_path) as actualizer:
        listed = actualizer.actualize_sync("I'll list `.`.")
        names = {item["name"] for item in listed.receipts[0].output["items"]}
        assert ".env" not in names
        assert ".habitus" not in names


def test_repeated_verified_use_forms_a_persistent_relative_habit(tmp_path):
    (tmp_path / "practice.txt").write_text("practice", encoding="utf-8")
    state = tmp_path / "mind.sqlite"

    with Actualizer(tmp_path, state_path=state) as actualizer:
        baseline, _ = actualizer.ability_prior(AbilityId.READ)
        for _ in range(6):
            result = actualizer.actualize_sync("I'll read `practice.txt`.")
            assert result.receipts[0].verified is True
        learned, _ = actualizer.ability_prior(AbilityId.READ)
        list_prior, _ = actualizer.ability_prior(AbilityId.LIST)

        assert learned > baseline
        assert learned > list_prior

    with Actualizer(tmp_path, state_path=state) as restarted:
        persisted, _ = restarted.ability_prior(AbilityId.READ)
        look_mass = sum(
            restarted.ability_prior(ability)[0]
            for ability in (AbilityId.LIST, AbilityId.READ, AbilityId.NAVIGATE)
        )

        assert persisted == learned
        assert abs(look_mass - 1.0) < 1e-9


def test_unchanged_observation_reward_diminishes_and_survives_restart(tmp_path):
    with Actualizer(tmp_path) as actualizer:
        first = actualizer.actualize_sync("I'll list `.`.").receipts[0]
        second = actualizer.actualize_sync("I'll list `.`.").receipts[0]
        first_record = actualizer.mind.store.get_record(first.return_record_id)
        second_record = actualizer.mind.store.get_record(second.return_record_id)

        assert first_record is not None and second_record is not None
        assert first_record.metadata["stability_reward"] == 0.20
        assert second_record.metadata["stability_reward"] == 0.10
        assert second_record.metadata["observation_repeat_count"] == 1

    with Actualizer(tmp_path) as restarted:
        third = restarted.actualize_sync("I'll list `.`.").receipts[0]
        third_record = restarted.mind.store.get_record(third.return_record_id)

        assert third_record is not None
        assert third_record.metadata["observation_repeat_count"] == 2
        assert 0.06 < third_record.metadata["stability_reward"] < 0.07
