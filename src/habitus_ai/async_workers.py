from __future__ import annotations

import asyncio
from concurrent.futures import Executor
from typing import Callable, TypeVar


T = TypeVar("T")


async def await_sync_call(
    function: Callable[..., T],
    *args: object,
    executor: Executor | None = None,
    poll_interval: float = 0.01,
) -> T:
    """Run synchronous external work without blocking the event-loop thread.

    An explicitly supplied executor is polled from the loop rather than wrapped
    with ``run_in_executor``. Some constrained runtimes can delay the selector
    wakeup emitted by a completed worker future until the loop's next timer.
    Bounded polling preserves independent-lane progress in those environments
    while retaining normal thread-pool execution.
    """
    if executor is None:
        return await asyncio.to_thread(function, *args)

    future = executor.submit(function, *args)
    try:
        while not future.done():
            await asyncio.sleep(poll_interval)
        return future.result()
    except asyncio.CancelledError:
        future.cancel()
        raise
