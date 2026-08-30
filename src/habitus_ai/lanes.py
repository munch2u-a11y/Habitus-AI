from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Generic, Mapping, TypeVar

from .async_workers import await_sync_call
from .agent import AgentTurn, HatchedAgent, PreparedAgentTurn
from .pipeline import BaseAgenticMemoryRAG
from .tools import ToolReceipt, ToolRegistry
from .types import EventKind, InputTrunk, MemoryRecord, OutputTrunk


T = TypeVar("T")
LaneOperation = Callable[[], T | Awaitable[T]]


class FlowLane(str, Enum):
    """The six independently scheduled roots of the two directional trees."""

    HEAR = "HEAR"
    SEE = "SEE"
    NOTICE = "NOTICE"
    SPEAK = "SPEAK"
    LOOK = "LOOK"
    DO = "DO"

    @classmethod
    def from_input(cls, trunk: InputTrunk) -> "FlowLane":
        return cls(trunk.value)

    @classmethod
    def from_output(cls, trunk: OutputTrunk) -> "FlowLane":
        return cls(trunk.value)

    @property
    def is_input(self) -> bool:
        return self.value in InputTrunk._value2member_map_

    @property
    def is_output(self) -> bool:
        return self.value in OutputTrunk._value2member_map_


@dataclass(frozen=True)
class LaneReceipt(Generic[T]):
    request_id: str
    lane: FlowLane
    sequence_id: int
    submitted_at: float
    started_at: float
    finished_at: float
    result: T

    @property
    def elapsed_seconds(self) -> float:
        return self.finished_at - self.started_at


@dataclass(frozen=True)
class ConversationLaneReceipt:
    """The independent HEAR and SPEAK receipts for one conversation cycle."""

    intake: LaneReceipt[PreparedAgentTurn]
    output: LaneReceipt[AgentTurn]

    @property
    def turn(self) -> AgentTurn:
        return self.output.result


@dataclass
class _LaneRequest(Generic[T]):
    request_id: str
    lane: FlowLane
    sequence_id: int
    submitted_at: float
    operation: LaneOperation[T]
    offload: bool
    future: asyncio.Future[LaneReceipt[T]]


_STOP = object()


class ConcurrentLaneRuntime:
    """Six FIFO lanes that may advance concurrently without sharing a turn lock.

    Each lane preserves its own causal order and sequence IDs. Graph/store work
    remains as short synchronous commits on the event-loop thread. Potentially
    slow external work must either be async or explicitly offloaded. This keeps
    the single SQLite connection safe while one waiting sense or action cannot
    stall any of the other five.
    """

    def __init__(
        self,
        mind: BaseAgenticMemoryRAG,
        *,
        external_workers: int = 6,
    ) -> None:
        if external_workers < 1:
            raise ValueError("external_workers must be at least 1")
        self.mind = mind
        self._queues: dict[FlowLane, asyncio.Queue[object]] = {
            lane: asyncio.Queue() for lane in FlowLane
        }
        self._tasks: dict[FlowLane, asyncio.Task[None]] = {}
        self._sequences: dict[FlowLane, int] = {lane: 0 for lane in FlowLane}
        self._started = False
        self._closed = False
        self._executor = ThreadPoolExecutor(
            max_workers=external_workers,
            thread_name_prefix="habitus-external",
        )

    @property
    def sequences(self) -> Mapping[FlowLane, int]:
        return dict(self._sequences)

    async def __aenter__(self) -> "ConcurrentLaneRuntime":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("lane runtime is closed")
        if self._started:
            return
        self._started = True
        for lane in FlowLane:
            self._tasks[lane] = asyncio.create_task(
                self._worker(lane),
                name=f"habitus-{lane.value.casefold()}-lane",
            )

    async def submit(
        self,
        lane: FlowLane | str,
        operation: LaneOperation[T],
        *,
        offload: bool = False,
    ) -> LaneReceipt[T]:
        """Schedule work in one lane and await only that lane's result.

        ``offload=True`` is for external synchronous work that does not access
        the mind/store. Short graph and memory mutations should use the default.
        """
        if self._closed:
            raise RuntimeError("lane runtime is closed")
        await self.start()
        resolved = lane if isinstance(lane, FlowLane) else FlowLane(lane)
        self._sequences[resolved] += 1
        loop = asyncio.get_running_loop()
        request: _LaneRequest[T] = _LaneRequest(
            request_id=f"lane:{resolved.value}:{uuid.uuid4().hex}",
            lane=resolved,
            sequence_id=self._sequences[resolved],
            submitted_at=time.perf_counter(),
            operation=operation,
            offload=bool(offload),
            future=loop.create_future(),
        )
        await self._queues[resolved].put(request)
        return await request.future

    async def ingest(
        self,
        text: str,
        *,
        trunk: InputTrunk | str,
        kind: EventKind | str | None = None,
        source_id: str = "environment",
        correlation_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        **remember_kwargs: Any,
    ) -> LaneReceipt[MemoryRecord]:
        """Deposit one sensory event through only its selected intake lane."""
        resolved = trunk if isinstance(trunk, InputTrunk) else InputTrunk(trunk)
        resolved_kind = kind or {
            InputTrunk.HEAR: EventKind.MESSAGE,
            InputTrunk.SEE: EventKind.OBSERVATION,
            InputTrunk.NOTICE: EventKind.NOTIFICATION,
        }[resolved]
        lane = FlowLane.from_input(resolved)
        combined_metadata = {
            **dict(metadata or {}),
            "flow_lane": lane.value,
        }
        return await self.submit(
            lane,
            lambda: self.mind.remember(
                text,
                kind=resolved_kind,
                source_id=source_id,
                correlation_id=correlation_id,
                input_trunk=resolved,
                metadata=combined_metadata,
                **remember_kwargs,
            ),
        )

    async def execute_tool(
        self,
        registry: ToolRegistry,
        tool_id: str,
        arguments: dict[str, Any],
        **execute_kwargs: Any,
    ) -> LaneReceipt[ToolReceipt]:
        """Execute an ability in its action lane; its return enters SEE."""
        tool = registry.get_tool(tool_id)
        trunk = tool.trunk if tool is not None else OutputTrunk.LOOK
        return await self.submit(
            FlowLane.from_output(trunk),
            lambda: registry.execute_async(
                tool_id,
                arguments,
                executor=self._executor,
                **execute_kwargs,
            ),
        )

    async def converse(
        self,
        agent: HatchedAgent,
        text: str,
    ) -> ConversationLaneReceipt:
        """Run HEAR preparation then model generation in the SPEAK lane.

        The causal dependency between these two phases is preserved, while the
        other four lanes remain free during potentially slow model inference.
        """
        intake = await self.submit(
            FlowLane.HEAR,
            lambda: agent.prepare_turn(text),
        )
        output = await self.submit(
            FlowLane.SPEAK,
            lambda: agent.generate_prepared_turn(
                intake.result,
                executor=self._executor,
            ),
        )
        return ConversationLaneReceipt(intake=intake, output=output)

    async def wait_idle(self) -> None:
        if not self._started:
            return
        await asyncio.gather(*(queue.join() for queue in self._queues.values()))

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._started:
                await self.wait_idle()
                for queue in self._queues.values():
                    await queue.put(_STOP)
                await asyncio.gather(*self._tasks.values())
                self._tasks.clear()
        finally:
            # Every submitted external operation has completed before this
            # point. Explicit ownership avoids leaving cleanup to asyncio's
            # process-wide default executor lifecycle.
            self._executor.shutdown(wait=True, cancel_futures=False)

    async def _worker(self, lane: FlowLane) -> None:
        queue = self._queues[lane]
        while True:
            item = await queue.get()
            try:
                if item is _STOP:
                    return
                request = item
                if not isinstance(request, _LaneRequest):
                    raise TypeError("invalid lane request")
                started_at = time.perf_counter()
                try:
                    if request.offload:
                        result = await await_sync_call(
                            request.operation,
                            executor=self._executor,
                        )
                    else:
                        result = request.operation()
                    if inspect.isawaitable(result):
                        result = await result
                    receipt = LaneReceipt(
                        request_id=request.request_id,
                        lane=lane,
                        sequence_id=request.sequence_id,
                        submitted_at=request.submitted_at,
                        started_at=started_at,
                        finished_at=time.perf_counter(),
                        result=result,
                    )
                    if not request.future.cancelled():
                        request.future.set_result(receipt)
                except Exception as error:
                    if not request.future.cancelled():
                        request.future.set_exception(error)
            finally:
                queue.task_done()
