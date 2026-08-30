from __future__ import annotations

import asyncio
import threading

from habitus_ai import (
    BaseAgenticMemoryRAG,
    ConcurrentLaneRuntime,
    FlowLane,
    GraphSide,
    HatchedAgent,
    InputTrunk,
    OutputTrunk,
    gestate,
)
from habitus_ai.tools import ToolDefinition, ToolRegistry


def test_all_six_lanes_can_be_in_flight_together(tmp_path):
    async def scenario() -> None:
        with BaseAgenticMemoryRAG(tmp_path / "six-in-flight.sqlite") as mind:
            release = asyncio.Event()
            started = {lane: asyncio.Event() for lane in FlowLane}

            def operation_for(lane: FlowLane):
                async def operation() -> str:
                    started[lane].set()
                    await release.wait()
                    return lane.value

                return operation

            async with ConcurrentLaneRuntime(mind) as runtime:
                tasks = {
                    lane: asyncio.create_task(runtime.submit(lane, operation_for(lane)))
                    for lane in FlowLane
                }
                await asyncio.wait_for(
                    asyncio.gather(*(event.wait() for event in started.values())),
                    timeout=1.0,
                )
                assert all(not task.done() for task in tasks.values())
                release.set()
                receipts = await asyncio.gather(*tasks.values())
                assert {receipt.result for receipt in receipts} == {
                    lane.value for lane in FlowLane
                }
                assert all(receipt.sequence_id == 1 for receipt in receipts)

    asyncio.run(scenario())


def test_waiting_lanes_do_not_block_other_senses_or_actions(tmp_path):
    async def scenario() -> None:
        with BaseAgenticMemoryRAG(tmp_path / "parallel.sqlite") as mind:
            registry = ToolRegistry(mind)
            registry.register_tool(
                ToolDefinition(
                    tool_id="tool:move_toy",
                    trunk=OutputTrunk.DO,
                    label="Move toy",
                    description="Move one nursery toy.",
                    terms=("move", "toy"),
                    parameters={},
                    handler=lambda _arguments: {"moved": True},
                )
            )
            hear_release = asyncio.Event()
            hear_started = asyncio.Event()
            speech_release = asyncio.Event()
            speech_started = asyncio.Event()

            async def waiting_hear() -> str:
                hear_started.set()
                await hear_release.wait()
                return "heard"

            async def waiting_speech() -> str:
                speech_started.set()
                await speech_release.wait()
                return "spoken"

            async with ConcurrentLaneRuntime(mind) as runtime:
                hear_task = asyncio.create_task(
                    runtime.submit(FlowLane.HEAR, waiting_hear)
                )
                speech_task = asyncio.create_task(
                    runtime.submit(FlowLane.SPEAK, waiting_speech)
                )
                await hear_started.wait()
                await speech_started.wait()

                seen = await asyncio.wait_for(
                    runtime.ingest(
                        "the toy is blue",
                        trunk=InputTrunk.SEE,
                        correlation_id="look:1",
                    ),
                    timeout=1.0,
                )
                moved = await asyncio.wait_for(
                    runtime.execute_tool(registry, "tool:move_toy", {}),
                    timeout=1.0,
                )

                assert seen.lane == FlowLane.SEE
                assert seen.sequence_id == 1
                assert moved.lane == FlowLane.DO
                assert moved.sequence_id == 1
                assert moved.result.verified is True
                assert not hear_task.done()
                assert not speech_task.done()

                projections = mind.experience_projections(moved.result.cycle_id)
                assert any(
                    projection.side == GraphSide.INPUT
                    and projection.node_id == "IN:SEE"
                    for projection in projections
                )
                assert mind.experience_cycle(moved.result.cycle_id).status == "closed"

                hear_release.set()
                speech_release.set()
                heard, spoken = await asyncio.gather(hear_task, speech_task)
                assert heard.sequence_id == 1
                assert spoken.sequence_id == 1

    asyncio.run(scenario())


def test_same_lane_is_fifo_while_different_lanes_advance(tmp_path):
    async def scenario() -> None:
        with BaseAgenticMemoryRAG(tmp_path / "fifo.sqlite") as mind:
            order: list[str] = []
            release = asyncio.Event()

            async def first() -> str:
                order.append("first-start")
                await release.wait()
                order.append("first-end")
                return "first"

            def second() -> str:
                order.append("second")
                return "second"

            async with ConcurrentLaneRuntime(mind) as runtime:
                first_task = asyncio.create_task(runtime.submit(FlowLane.NOTICE, first))
                await asyncio.sleep(0)
                second_task = asyncio.create_task(runtime.submit(FlowLane.NOTICE, second))
                look = await runtime.submit(FlowLane.LOOK, lambda: "looked")
                assert look.result == "looked"
                assert not second_task.done()
                release.set()
                first_receipt, second_receipt = await asyncio.gather(
                    first_task, second_task
                )
                assert order == ["first-start", "first-end", "second"]
                assert (first_receipt.sequence_id, second_receipt.sequence_id) == (1, 2)

    asyncio.run(scenario())


def test_intake_ciphers_can_cross_at_one_shared_concept(tmp_path):
    async def scenario() -> None:
        with BaseAgenticMemoryRAG(tmp_path / "crossing.sqlite") as mind:
            mind.add_concept(
                "shared-object",
                "Shared object",
                input_trunks=("HEAR", "SEE"),
            )
            async with ConcurrentLaneRuntime(mind) as runtime:
                heard, seen = await asyncio.gather(
                    runtime.submit(
                        FlowLane.HEAR,
                        lambda: mind.graph.traverse(
                            pulse_id="heard-shared",
                            side=GraphSide.INPUT,
                            target_id="shared-object",
                            endpoint_score=1.0,
                            required_input_trunk=InputTrunk.HEAR,
                            mark_active=False,
                        ),
                    ),
                    runtime.submit(
                        FlowLane.SEE,
                        lambda: mind.graph.traverse(
                            pulse_id="seen-shared",
                            side=GraphSide.INPUT,
                            target_id="shared-object",
                            endpoint_score=1.0,
                            required_input_trunk=InputTrunk.SEE,
                            mark_active=False,
                        ),
                    ),
                )
                assert heard.result.path_node_ids == (
                    "SELF", "IN:HEAR", "shared-object"
                )
                assert seen.result.path_node_ids == (
                    "SELF", "IN:SEE", "shared-object"
                )
                assert heard.result.path_edge_ids != seen.result.path_edge_ids

    asyncio.run(scenario())


def test_real_model_generation_in_speak_does_not_pause_do(tmp_path):
    class WaitingModel:
        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()

        def generate(self, _messages) -> str:
            self.started.set()
            if not self.release.wait(timeout=2.0):
                raise TimeoutError("test did not release model generation")
            return "I can speak after the movement finishes."

    async def scenario() -> None:
        with BaseAgenticMemoryRAG(tmp_path / "conversation.sqlite") as mind:
            gestate(
                mind,
                human_name="Josh",
                agent_name="Sprout",
                model_name="waiting-model",
            )
            model = WaitingModel()
            agent = HatchedAgent(mind, model)
            registry = ToolRegistry(mind)
            registry.register_tool(
                ToolDefinition(
                    tool_id="tool:move_during_speech",
                    trunk=OutputTrunk.DO,
                    label="Move during speech",
                    description="Move while language generation is pending.",
                    terms=("move",),
                    parameters={},
                    handler=lambda _arguments: {"moved": True},
                )
            )

            async with ConcurrentLaneRuntime(mind) as runtime:
                conversation = asyncio.create_task(
                    runtime.converse(agent, "Can you speak while moving?")
                )
                while not model.started.is_set():
                    await asyncio.sleep(0)

                moved = await asyncio.wait_for(
                    runtime.execute_tool(registry, "tool:move_during_speech", {}),
                    timeout=1.0,
                )
                assert moved.result.status == "success"
                assert not conversation.done()

                model.release.set()
                spoken = await asyncio.wait_for(conversation, timeout=1.0)
                assert spoken.intake.lane == FlowLane.HEAR
                assert spoken.output.lane == FlowLane.SPEAK
                assert spoken.turn.response == "I can speak after the movement finishes."

    asyncio.run(scenario())
