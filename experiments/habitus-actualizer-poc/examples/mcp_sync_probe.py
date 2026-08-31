"""Probe ordinary model outputs through the real MCP protocol in-process."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp import Client

from habitus_actualizer import Actualizer
from habitus_actualizer.mcp_adapter import create_mcp_server


DEFAULT_SAMPLES = (
    "I'll read `README.md` and list `src`.",
    "I read `README.md` yesterday, so I won't open it now.",
    "Let me go to `examples`.",
)


async def probe(workspace: Path, samples: tuple[str, ...]) -> None:
    async with Actualizer(workspace) as actualizer:
        server = create_mcp_server(actualizer, execution_enabled=False)
        async with Client(server) as client:
            tools = await client.list_tools()
            print(json.dumps({"mcp_tools": [item.name for item in tools.tools]}))
            for text in samples:
                result = await client.call_tool(
                    "actualize_assistant_output",
                    {"text": text},
                )
                print(json.dumps(result.structured_content, sort_keys=True, default=str))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--sample", action="append", default=[])
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve(strict=True)
    samples = tuple(args.sample) if args.sample else DEFAULT_SAMPLES
    asyncio.run(probe(workspace, samples))


if __name__ == "__main__":
    main()
