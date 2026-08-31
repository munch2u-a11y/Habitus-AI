import asyncio

from habitus_actualizer import (
    Actualizer,
    AgentLedger,
    ContinuousAgent,
    SelfSession,
    WorkspaceSensor,
)
from habitus_actualizer._engine.types import RecordType


class ScriptedDriver:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def generate(self, frame: str, *, mode: str) -> str:
        self.calls.append({"frame": frame, "mode": mode})
        if not self.outputs:
            raise RuntimeError("scripted driver exhausted")
        return self.outputs.pop(0)


def test_durable_message_queue_drives_action_then_outward_speech(tmp_path):
    (tmp_path / "README.md").write_text("durable proof", encoding="utf-8")
    state = tmp_path / "mind.sqlite"
    ledger_path = tmp_path / "loop.sqlite"

    with AgentLedger(ledger_path) as ledger:
        queued = ledger.enqueue("Please inspect this workspace.", source_id="Josh")
        assert queued.status == "queued"

    async def scenario():
        driver = ScriptedDriver(
            ["I'll list `.`.", "I found README.md in the workspace."]
        )
        with AgentLedger(ledger_path) as ledger:
            with Actualizer(tmp_path, state_path=state) as actualizer:
                session = SelfSession(actualizer, session_id="continuous:test")
                agent = ContinuousAgent(session, driver, ledger)
                result = await agent.step()

                assert result is not None
                assert result.status == "completed"
                assert result.spoken_text == "I found README.md in the workspace."
                assert [cycle.status for cycle in result.cycles] == ["action", "spoken"]
                assert result.cycles[0].receipts[0]["verified"] is True
                assert "README.md" in driver.calls[1]["frame"]
                assert ledger.list_events()[0]["status"] == "completed"
                assert ledger.outbox(undelivered_only=True)[0]["text"] == result.spoken_text
                assert actualizer.mind.store.get_metadata(
                    "self_session.focus:continuous:test"
                ) == ""

    asyncio.run(scenario())

    with Actualizer(tmp_path, state_path=state) as actualizer:
        resumed = SelfSession(actualizer, session_id="continuous:test")
        frame = resumed.prepare_input("What did you find?", source_id="Josh")
        assert "I found README.md in the workspace." in frame.text


def test_multiple_inputs_pile_up_and_are_claimed_in_order(tmp_path):
    ledger_path = tmp_path / "loop.sqlite"
    with AgentLedger(ledger_path) as ledger:
        first = ledger.enqueue("first", event_id="event:first")
        second = ledger.enqueue("second", event_id="event:second")
        claimed_first = ledger.claim_next()
        assert claimed_first is not None and claimed_first.event_id == first.event_id
        ledger.finish_event(first.event_id)
        claimed_second = ledger.claim_next()
        assert claimed_second is not None and claimed_second.event_id == second.event_id


def test_unrecognized_action_plan_is_not_externalized_as_completion(tmp_path):
    async def scenario():
        driver = ScriptedDriver(
            [
                "I will look inside the scripts directory.",
                "I'll list `.`.",
                "I found the workspace contents.",
            ]
        )
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            ledger.enqueue("Please inspect the workspace.")
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:guard")
                agent = ContinuousAgent(session, driver, ledger)
                result = await agent.step()

                assert result is not None and result.status == "completed"
                assert [cycle.status for cycle in result.cycles] == [
                    "unrecognized-action",
                    "action",
                    "spoken",
                ]
                assert len(ledger.outbox()) == 1
                assert ledger.outbox()[0]["text"] == "I found the workspace contents."
                assert not any(
                    record.text == "I will look inside the scripts directory."
                    for record in actualizer.mind.store.list_records()
                )

    asyncio.run(scenario())


def test_explicit_action_request_requires_receipt_before_completion(tmp_path):
    script = tmp_path / "status.py"
    script.write_text("print('green')\n", encoding="utf-8")

    async def scenario():
        driver = ScriptedDriver(
            [
                "I cannot run commands because I do not have terminal access.",
                "I'll run `python3 status.py`.",
                "The verified status is green.",
            ]
        )
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            ledger.enqueue("Please run status.py and report its output.")
            from habitus_actualizer import WorkspacePolicy

            policy = WorkspacePolicy(tmp_path, allowed_commands=("python3",))
            with Actualizer(
                tmp_path,
                state_path=tmp_path / "mind.sqlite",
                policy=policy,
            ) as actualizer:
                session = SelfSession(actualizer, session_id="continuous:receipt-gate")
                agent = ContinuousAgent(session, driver, ledger)
                result = await agent.step()

                assert result is not None and result.status == "completed"
                assert [cycle.status for cycle in result.cycles] == [
                    "completion-suppressed",
                    "action",
                    "spoken",
                ]
                assert result.cycles[1].receipts[0]["ability"] == "workspace.run"
                assert ledger.outbox()[0]["text"] == "The verified status is green."

    asyncio.run(scenario())


def test_explicit_multi_file_read_requires_receipt_for_each_target(tmp_path):
    (tmp_path / "a.txt").write_text("A=stable", encoding="utf-8")
    (tmp_path / "b.txt").write_text("B=unstable", encoding="utf-8")

    async def scenario():
        driver = ScriptedDriver(
            [
                "I'll read `a.txt`.",
                "A is stable and B is unstable.",
                "I'll read `b.txt`.",
                "A is stable; B is unstable.",
            ]
        )
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            ledger.enqueue(
                "Please read both `a.txt` and `b.txt`, compare them, and report the result."
            )
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:multi-read")
                agent = ContinuousAgent(session, driver, ledger)
                result = await agent.step()

                assert result is not None and result.status == "completed"
                assert [cycle.status for cycle in result.cycles] == [
                    "action",
                    "completion-suppressed",
                    "action",
                    "spoken",
                ]
                read_paths = {
                    receipt["output"]["path"]
                    for cycle in result.cycles
                    for receipt in cycle.receipts
                    if receipt["ability"] == "workspace.read"
                }
                assert read_paths == {"a.txt", "b.txt"}
                assert "read every file requested" in driver.calls[3]["frame"]

    assert ContinuousAgent._looks_like_action_intent(
        "I will freshly read `a.txt` before answering."
    )

    asyncio.run(scenario())


def test_explanatory_or_negated_tool_words_do_not_create_completion_gate(tmp_path):
    async def scenario():
        driver = ScriptedDriver(
            ["I can explain that safely without executing anything."]
        )
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            ledger.enqueue(
                "Please explain how to run this later, but do not run anything now."
            )
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:negation")
                agent = ContinuousAgent(session, driver, ledger)
                result = await agent.step()

                assert result is not None and result.status == "completed"
                assert [item.status for item in result.cycles] == ["spoken"]

    asyncio.run(scenario())


def test_idle_action_is_observed_then_private_thought_is_not_spoken(tmp_path):
    (tmp_path / "toy.txt").write_text("a safe toy", encoding="utf-8")

    async def scenario():
        driver = ScriptedDriver(
            ["I'll list `.`.", "I notice that toy.txt is available to inspect later."]
        )
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:idle")
                agent = ContinuousAgent(
                    session,
                    driver,
                    ledger,
                    idle_interval_seconds=0,
                    allow_idle_actions=True,
                    idle_action_budget=1,
                )
                result = await agent.step(force_idle=True)

                assert result is not None and result.mode == "idle"
                assert [cycle.status for cycle in result.cycles] == ["action", "thought"]
                assert result.cycles[0].receipts[0]["ability"] == "workspace.list"
                assert ledger.outbox() == []
                thoughts = [
                    record
                    for record in actualizer.mind.store.list_records()
                    if record.record_type == RecordType.THOUGHT
                ]
                assert thoughts[-1].text.startswith("I notice")
                assert thoughts[-1].metadata["membrane_lane"] == "PRIVATE"
                assert thoughts[-1].metadata["membrane_words"] is True

    asyncio.run(scenario())


def test_repeated_idle_action_is_suppressed_before_second_execution(tmp_path):
    async def scenario():
        repeated = "I'll list `.`."
        driver = ScriptedDriver([repeated, "I can pause now.", repeated])
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:repeat")
                agent = ContinuousAgent(
                    session,
                    driver,
                    ledger,
                    idle_interval_seconds=0,
                    allow_idle_actions=True,
                    idle_action_budget=4,
                )
                first = await agent.step(force_idle=True)
                second = await agent.step(force_idle=True)

                assert first is not None and second is not None
                assert [item.status for item in first.cycles] == ["action", "thought"]
                assert [item.status for item in second.cycles] == ["duplicate-suppressed"]
                action_cycles = [
                    cycle for cycle in ledger.list_cycles() if cycle.status == "action"
                ]
                assert len(action_cycles) == 1

    asyncio.run(scenario())


def test_idle_action_is_not_remembered_as_thought_when_autonomy_is_disabled(tmp_path):
    async def scenario():
        driver = ScriptedDriver(["I'll list `.`."])
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:bounded")
                agent = ContinuousAgent(
                    session,
                    driver,
                    ledger,
                    idle_interval_seconds=0,
                    allow_idle_actions=False,
                )
                result = await agent.step(force_idle=True)

                assert result is not None
                assert result.cycles[0].status == "autonomy-suppressed"
                assert not any(
                    record.record_type == RecordType.THOUGHT
                    for record in actualizer.mind.store.list_records()
                )

    asyncio.run(scenario())


def test_bare_idle_command_is_corrected_and_not_remembered_as_thought(tmp_path):
    async def scenario():
        driver = ScriptedDriver(
            ["`python3 status.py`", "I can wait for a grounded reason to act."]
        )
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:bare")
                agent = ContinuousAgent(
                    session,
                    driver,
                    ledger,
                    idle_interval_seconds=0,
                    allow_idle_actions=True,
                )
                result = await agent.step(force_idle=True)

                assert result is not None
                assert [item.status for item in result.cycles] == [
                    "unrecognized-action",
                    "thought",
                ]
                thoughts = [
                    record.text
                    for record in actualizer.mind.store.list_records()
                    if record.record_type == RecordType.THOUGHT
                ]
                assert thoughts == ["I can wait for a grounded reason to act."]

    asyncio.run(scenario())


def test_unwrapped_bare_command_in_notice_is_not_remembered_as_thought(tmp_path):
    async def scenario():
        driver = ScriptedDriver(
            ["python3 scripts/status.py", "I can remain still until something changes."]
        )
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            ledger.enqueue("A status reporter is available.", kind="notice")
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:bare-notice")
                agent = ContinuousAgent(session, driver, ledger)
                result = await agent.step()

                assert result is not None
                assert [item.status for item in result.cycles] == [
                    "unrecognized-action",
                    "thought",
                ]
                thoughts = [
                    record.text
                    for record in actualizer.mind.store.list_records()
                    if record.record_type == RecordType.THOUGHT
                ]
                assert thoughts == ["I can remain still until something changes."]

    asyncio.run(scenario())


def test_interrupted_event_can_be_recovered_after_restart(tmp_path):
    ledger_path = tmp_path / "loop.sqlite"
    with AgentLedger(ledger_path) as ledger:
        ledger.enqueue("recover me", event_id="event:recover")
        assert ledger.claim_next() is not None

    with AgentLedger(ledger_path) as restarted:
        assert restarted.recover_processing(older_than_seconds=0) == 1
        claimed = restarted.claim_next()
        assert claimed is not None
        assert claimed.event_id == "event:recover"
        assert claimed.attempts == 2


def test_workspace_change_becomes_private_notice_not_unsolicited_speech(tmp_path):
    sensor = WorkspaceSensor(tmp_path)
    ledger_path = tmp_path / "loop.sqlite"
    with AgentLedger(ledger_path) as ledger:
        assert sensor.poll(ledger) is None
        (tmp_path / "new-toy.txt").write_text("hello", encoding="utf-8")
        notice = sensor.poll(ledger)
        assert notice is not None and notice.kind == "notice"
        assert "new-toy.txt" in notice.text

    async def scenario():
        driver = ScriptedDriver(["I notice that a new workspace item appeared."])
        with AgentLedger(ledger_path) as ledger:
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:sense")
                agent = ContinuousAgent(
                    session,
                    driver,
                    ledger,
                    workspace_sensor=sensor,
                )
                result = await agent.step()

                assert result is not None and result.mode == "notice"
                assert result.cycles[-1].status == "thought"
                assert ledger.outbox() == []
                notices = [
                    record
                    for record in actualizer.mind.store.list_records()
                    if record.record_type == RecordType.NOTIFICATION
                ]
                assert notices[-1].metadata["membrane_words"] is False

    asyncio.run(scenario())


def test_notice_stops_paraphrased_repeat_of_same_observed_action(tmp_path):
    async def scenario():
        driver = ScriptedDriver(
            [
                "I'll list `.`.",
                "I will list the current directory to confirm it again.",
            ]
        )
        with AgentLedger(tmp_path / "loop.sqlite") as ledger:
            ledger.enqueue("Workspace state changed.", kind="notice")
            with Actualizer(tmp_path, state_path=tmp_path / "mind.sqlite") as actualizer:
                session = SelfSession(actualizer, session_id="continuous:no-cycle")
                agent = ContinuousAgent(session, driver, ledger)
                result = await agent.step()

                assert result is not None and result.status == "completed"
                assert [item.status for item in result.cycles] == [
                    "action",
                    "repeated-action-suppressed",
                ]
                receipts = [
                    receipt
                    for cycle in result.cycles
                    for receipt in cycle.receipts
                ]
                assert len(receipts) == 1

    asyncio.run(scenario())
