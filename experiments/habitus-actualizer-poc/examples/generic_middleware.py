from __future__ import annotations

import asyncio
from pathlib import Path

from habitus_actualizer import Actualizer, AgentOutputMiddleware, WorkspacePolicy


async def main() -> None:
    workspace = Path.cwd()
    policy = WorkspacePolicy(workspace, allowed_commands=("python3",))
    async with Actualizer(workspace, policy=policy) as actualizer:
        middleware = AgentOutputMiddleware(actualizer)
        result = await middleware.process(
            "I'll read `README.md` and run `python3 --version`."
        )
        print(result.batch.to_json())


if __name__ == "__main__":
    asyncio.run(main())
