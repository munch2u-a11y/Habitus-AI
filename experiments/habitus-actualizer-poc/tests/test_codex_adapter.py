import asyncio

from habitus_actualizer import (
    AbilityId,
    Actualizer,
    CodexAppServerAdapter,
)
from habitus_actualizer._engine.types import GraphSide


def test_host_observation_reinforces_and_then_weakens_activation(tmp_path):
    (tmp_path / "README.md").write_text("proof", encoding="utf-8")
    with Actualizer(tmp_path) as actualizer:
        edge = actualizer.mind.store.find_edge(
            GraphSide.OUTPUT,
            "OUT:LOOK",
            "ability:workspace.read",
        )
        assert edge is not None
        baseline_strength = edge.log_strength
        baseline_prior, neutral = actualizer.ability_prior(AbilityId.READ)
        baseline_confidence = actualizer.actualize_sync(
            "I'll read `README.md`.", dry_run=True
        ).requests[0].confidence
        assert abs(baseline_prior - neutral) < 1e-9

        success = actualizer.observe_ability_result(
            AbilityId.READ,
            status="success",
            verified=True,
            arguments={"path": "README.md"},
            output={"path": "README.md", "sha256": "abc"},
            phrase="I read README.md",
            receipt_id="receipt:host:success",
        )
        after_success = actualizer.mind.store.get_edge(edge.edge_id)
        successful_prior, _ = actualizer.ability_prior(AbilityId.READ)
        successful_confidence = actualizer.actualize_sync(
            "I'll read `README.md`.", dry_run=True
        ).requests[0].confidence

        failure = actualizer.observe_ability_result(
            AbilityId.READ,
            status="error",
            verified=True,
            arguments={"path": "missing.md"},
            error="missing",
            phrase="I read missing.md",
            receipt_id="receipt:host:failure",
        )
        after_failure = actualizer.mind.store.get_edge(edge.edge_id)
        failed_prior, _ = actualizer.ability_prior(AbilityId.READ)
        failed_confidence = actualizer.actualize_sync(
            "I'll read `README.md`.", dry_run=True
        ).requests[0].confidence

        assert success.status == "success"
        assert failure.status == "error"
        assert after_success.log_strength > baseline_strength
        assert after_failure.log_strength < after_success.log_strength
        assert successful_prior > baseline_prior
        assert failed_prior < successful_prior
        assert successful_confidence > baseline_confidence
        assert failed_confidence < successful_confidence


def test_unverified_host_observation_is_persisted_but_not_learned(tmp_path):
    with Actualizer(tmp_path) as actualizer:
        edge = actualizer.mind.store.find_edge(
            GraphSide.OUTPUT,
            "OUT:DO",
            "ability:workspace.write",
        )
        assert edge is not None
        baseline = edge.log_strength
        receipt = actualizer.observe_ability_result(
            AbilityId.WRITE,
            status="success",
            verified=False,
            arguments={"path": "note.txt"},
            output={"claimed": True},
            receipt_id="receipt:host:unverified",
        )
        observed = actualizer.mind.store.get_edge(edge.edge_id)
        assert receipt.verified is False
        assert observed.log_strength == baseline


def test_codex_command_receipt_is_learned_once(tmp_path):
    async def scenario():
        with Actualizer(tmp_path) as actualizer:
            adapter = CodexAppServerAdapter(actualizer)
            event = {
                "method": "item/completed",
                "params": {
                    "threadId": "thr_1",
                    "turnId": "turn_1",
                    "item": {
                        "type": "commandExecution",
                        "id": "cmd_1",
                        "command": "python3 -m pytest -q",
                        "cwd": str(tmp_path),
                        "status": "completed",
                        "exitCode": 0,
                        "aggregatedOutput": "3 passed",
                        "durationMs": 12,
                    },
                },
            }
            first = await adapter.consume(event)
            duplicate = await adapter.consume(event)
            assert len(first.native_receipts) == 1
            assert first.native_receipts[0].ability_id == AbilityId.RUN
            assert first.native_receipts[0].verified is True
            assert duplicate.native_receipts == ()

    asyncio.run(scenario())


def test_native_receipt_deduplication_survives_adapter_restart(tmp_path):
    event = {
        "method": "item/completed",
        "params": {
            "threadId": "thr_restart",
            "turnId": "turn_restart",
            "item": {
                "type": "commandExecution",
                "id": "cmd_restart",
                "command": "python3 --version",
                "cwd": str(tmp_path),
                "status": "completed",
                "exitCode": 0,
                "aggregatedOutput": "Python",
            },
        },
    }

    async def scenario():
        with Actualizer(tmp_path) as first_actualizer:
            first = await CodexAppServerAdapter(first_actualizer).consume(event)
            assert len(first.native_receipts) == 1
        with Actualizer(tmp_path) as restarted_actualizer:
            duplicate = await CodexAppServerAdapter(restarted_actualizer).consume(event)
            assert duplicate.native_receipts == ()

    asyncio.run(scenario())


def test_codex_file_receipt_requires_workspace_readback(tmp_path):
    changed = tmp_path / "note.txt"
    changed.write_text("observed", encoding="utf-8")

    async def scenario():
        with Actualizer(tmp_path) as actualizer:
            update = await CodexAppServerAdapter(actualizer).consume(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turnId": "turn_1",
                        "item": {
                            "type": "fileChange",
                            "id": "file_1",
                            "status": "completed",
                            "changes": [
                                {
                                    "path": str(changed),
                                    "kind": "update",
                                    "diff": "+observed",
                                }
                            ],
                        },
                    },
                }
            )
            receipt = update.native_receipts[0]
            assert receipt.ability_id == AbilityId.WRITE
            assert receipt.status == "success"
            assert receipt.verified is True
            assert receipt.output["read_back_verified"] is True
            assert receipt.output["changes"][0]["sha256"]

    asyncio.run(scenario())


def test_completed_final_message_actualizes_and_builds_thread_injection(tmp_path):
    (tmp_path / "README.md").write_text("proof", encoding="utf-8")

    async def scenario():
        with Actualizer(tmp_path) as actualizer:
            adapter = CodexAppServerAdapter(actualizer)
            message = await adapter.consume(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turnId": "turn_1",
                        "item": {
                            "type": "agentMessage",
                            "id": "msg_1",
                            "phase": "final_answer",
                            "text": "I'll read `README.md`.",
                        },
                    },
                }
            )
            assert message.actualization is None

            completed_event = {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr_1",
                    "turn": {"id": "turn_1", "status": "completed"},
                },
            }
            completed = await adapter.consume(completed_event)
            duplicate = await adapter.consume(completed_event)
            assert completed.actualization is not None
            assert completed.actualization.receipts[0].output["content"] == "proof"
            assert len(completed.app_server_requests) == 1
            injection = completed.app_server_requests[0]
            assert injection["method"] == "thread/inject_items"
            text = injection["params"]["items"][0]["content"][0]["text"]
            assert text.startswith("I completed workspace.read successfully")
            assert "proof" in text
            assert duplicate.actualization is None

    asyncio.run(scenario())


def test_thread_injection_is_bounded_while_receipt_keeps_full_evidence(tmp_path):
    content = "evidence-" * 2000
    (tmp_path / "large.txt").write_text(content, encoding="utf-8")

    async def scenario():
        with Actualizer(tmp_path) as actualizer:
            adapter = CodexAppServerAdapter(
                actualizer,
                maximum_injection_chars=700,
                maximum_result_chars=400,
            )
            await adapter.consume(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turnId": "turn_1",
                        "item": {
                            "type": "agentMessage",
                            "id": "msg_1",
                            "phase": "final_answer",
                            "text": "I'll read `large.txt`.",
                        },
                    },
                }
            )
            completed = await adapter.consume(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turn": {"id": "turn_1", "status": "completed"},
                    },
                }
            )
            receipt = completed.actualization.receipts[0]
            injected = completed.app_server_requests[0]["params"]["items"][0][
                "content"
            ][0]["text"]
            assert receipt.output["content"] == content
            assert len(injected) <= 700
            assert "full result is in the receipt" in injected

    asyncio.run(scenario())


def test_completed_turn_actualization_is_at_most_once_across_restart(tmp_path):
    (tmp_path / "README.md").write_text("proof", encoding="utf-8")
    message = {
        "method": "item/completed",
        "params": {
            "threadId": "thr_restart",
            "turnId": "turn_restart",
            "item": {
                "type": "agentMessage",
                "id": "msg_restart",
                "phase": "final_answer",
                "text": "I'll read `README.md`.",
            },
        },
    }
    completed = {
        "method": "turn/completed",
        "params": {
            "threadId": "thr_restart",
            "turn": {"id": "turn_restart", "status": "completed"},
        },
    }

    async def scenario():
        with Actualizer(tmp_path) as first_actualizer:
            first_adapter = CodexAppServerAdapter(first_actualizer)
            await first_adapter.consume(message)
            first = await first_adapter.consume(completed)
            assert len(first.actualization.receipts) == 1
            records_after_first = len(first_actualizer.mind.store.list_records())
        with Actualizer(tmp_path) as restarted_actualizer:
            restarted_adapter = CodexAppServerAdapter(restarted_actualizer)
            await restarted_adapter.consume(message)
            duplicate = await restarted_adapter.consume(completed)
            assert duplicate.actualization is None
            assert "not actualized again" in duplicate.warnings[0]
            assert len(restarted_actualizer.mind.store.list_records()) == records_after_first

    asyncio.run(scenario())


def test_failed_or_interrupted_turn_never_actualizes(tmp_path):
    async def scenario():
        with Actualizer(tmp_path) as actualizer:
            adapter = CodexAppServerAdapter(actualizer)
            await adapter.consume(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turnId": "turn_1",
                        "item": {
                            "type": "agentMessage",
                            "id": "msg_1",
                            "phase": "final_answer",
                            "text": "I'll write 'unsafe' to 'note.txt'.",
                        },
                    },
                }
            )
            result = await adapter.consume(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turn": {"id": "turn_1", "status": "interrupted"},
                    },
                }
            )
            assert result.actualization is None
            assert not (tmp_path / "note.txt").exists()

    asyncio.run(scenario())


def test_non_action_final_message_stays_conversation_only(tmp_path):
    async def scenario():
        with Actualizer(tmp_path) as actualizer:
            adapter = CodexAppServerAdapter(actualizer)
            await adapter.consume(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turnId": "turn_1",
                        "item": {
                            "type": "agentMessage",
                            "id": "msg_1",
                            "phase": "final_answer",
                            "text": "The workspace is ready whenever you are.",
                        },
                    },
                }
            )
            result = await adapter.consume(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turn": {"id": "turn_1", "status": "completed"},
                    },
                }
            )
            assert result.actualization is not None
            assert result.actualization.receipts == ()
            assert result.app_server_requests == ()

    asyncio.run(scenario())


def test_out_of_workspace_codex_receipt_is_rejected_without_learning(tmp_path):
    async def scenario():
        with Actualizer(tmp_path) as actualizer:
            edge = actualizer.mind.store.find_edge(
                GraphSide.OUTPUT,
                "OUT:DO",
                "ability:workspace.run",
            )
            assert edge is not None
            baseline = edge.log_strength
            result = await CodexAppServerAdapter(actualizer).consume(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thr_1",
                        "turnId": "turn_1",
                        "item": {
                            "type": "commandExecution",
                            "id": "cmd_1",
                            "command": "python3 -m pytest -q",
                            "cwd": str(tmp_path.parent),
                            "status": "completed",
                            "exitCode": 0,
                            "aggregatedOutput": "passed",
                        },
                    },
                }
            )
            assert result.native_receipts == ()
            assert "outside" in result.warnings[0]
            assert actualizer.mind.store.get_edge(edge.edge_id).log_strength == baseline

    asyncio.run(scenario())
