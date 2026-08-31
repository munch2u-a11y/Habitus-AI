"""Optional MCP transport for the post-generation actualizer boundary.

The core package does not import the MCP SDK.  Only ``create_mcp_server`` and
the console entry point load it, so the backend-free middleware remains usable
with the Python standard library alone.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .policy import WorkspacePolicy
from .runtime import Actualizer


class MCPActualizerBridge:
    """Host-facing bridge around one ordinary assistant-output boundary.

    ``execution_enabled`` is fixed by the host at construction time.  It is
    deliberately not an MCP argument: a caller connected to a probe-only
    gestation session cannot promote its own authority.
    """

    def __init__(
        self,
        actualizer: Actualizer,
        *,
        execution_enabled: bool = False,
    ) -> None:
        self.actualizer = actualizer
        self.execution_enabled = bool(execution_enabled)

    @property
    def mode(self) -> str:
        return "execute" if self.execution_enabled else "probe"

    async def process_assistant_output(self, text: str) -> dict[str, Any]:
        """Route one completed assistant message and return evidence."""
        normalized = str(text).strip()
        if not normalized:
            raise ValueError("assistant output must not be empty")
        batch = await self.actualizer.actualize(
            normalized,
            source_role="assistant",
            dry_run=not self.execution_enabled,
        )
        return {
            "mode": self.mode,
            "batch": batch.to_dict(),
            "observation": batch.observation(),
        }

    def status(self) -> dict[str, Any]:
        """Return non-secret runtime state suitable for an MCP resource."""
        return {
            "mode": self.mode,
            "workspace": str(self.actualizer.policy.root),
            "cwd": self.actualizer.workspace.display_path(self.actualizer.workspace.cwd),
            "maximum_abilities": self.actualizer.activator.maximum_abilities,
            "confidence_threshold": self.actualizer.confidence_threshold,
            "graph": dict(self.actualizer.graph_health()),
            "authority": {
                "write": self.actualizer.policy.allow_write,
                "commands": list(self.actualizer.policy.allowed_commands),
            },
        }

    @staticmethod
    def contract() -> Mapping[str, Any]:
        """Describe the integration boundary without advertising five tools."""
        return {
            "boundary": "post_generation",
            "bridge_tool": "actualize_assistant_output",
            "model_tool_catalog_required": False,
            "source_role": "assistant",
            "abilities": [
                "workspace.list",
                "workspace.read",
                "workspace.navigate",
                "workspace.write",
                "workspace.run",
            ],
            "integration": (
                "The host calls the bridge automatically after ordinary assistant "
                "text is generated; it should not ask the model to select this tool."
            ),
        }


def _mcp_server_class():
    try:
        from mcp.server import MCPServer
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "MCP support is optional; install with "
            "`python -m pip install 'habitus-actualizer[mcp]'`"
        ) from error
    return MCPServer


def create_mcp_server(
    actualizer: Actualizer,
    *,
    execution_enabled: bool = False,
):
    """Create an MCP v2 server containing one post-generation bridge tool."""
    MCPServer = _mcp_server_class()
    bridge = MCPActualizerBridge(
        actualizer,
        execution_enabled=execution_enabled,
    )
    server = MCPServer("Habitus Actualizer")

    @server.tool(
        name="actualize_assistant_output",
        description=(
            "Host post-generation hook for one completed assistant message. "
            "Pass ordinary prose unchanged; the server controls whether this "
            "session probes or executes."
        ),
    )
    async def actualize_assistant_output(text: str) -> dict[str, Any]:
        return await bridge.process_assistant_output(text)

    @server.resource("actualizer://status")
    async def actualizer_status() -> str:
        """Current mode, authority, and graph health."""
        return json.dumps(bridge.status(), sort_keys=True)

    @server.resource("actualizer://contract")
    async def actualizer_contract() -> str:
        """The host integration contract for this adapter."""
        return json.dumps(bridge.contract(), sort_keys=True)

    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="habitus-actualizer-mcp",
        description="Serve the Habitus post-generation bridge over MCP.",
    )
    parser.add_argument("--workspace", default=".", help="workspace authority root")
    parser.add_argument("--state", help="persistent SQLite state path")
    parser.add_argument("--allow-write", action="store_true", help="enable atomic writes")
    parser.add_argument(
        "--allow-command",
        action="append",
        default=[],
        metavar="NAME",
        help="allow one executable basename; may be repeated",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="execute accepted abilities; the default is probe-only sync mode",
    )
    parser.add_argument("--threshold", type=float, default=0.72)
    parser.add_argument("--max-abilities", type=int, default=3)
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    parser.add_argument("--port", type=int, default=8000, help="HTTP bind port")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Fail before creating state when the optional transport is unavailable.
    _mcp_server_class()
    workspace = Path(args.workspace).expanduser().resolve(strict=True)
    policy = WorkspacePolicy(
        workspace,
        allow_write=args.allow_write,
        allowed_commands=WorkspacePolicy.normalize_allowed_commands(
            args.allow_command
        ),
    )
    with Actualizer(
        workspace,
        state_path=args.state,
        policy=policy,
        confidence_threshold=args.threshold,
        maximum_abilities=args.max_abilities,
    ) as actualizer:
        server = create_mcp_server(
            actualizer,
            execution_enabled=args.execute,
        )
        try:
            if args.transport == "stdio":
                server.run("stdio")
            else:
                server.run(
                    "streamable-http",
                    host="127.0.0.1",
                    port=args.port,
                )
        except KeyboardInterrupt:  # normal local-server shutdown
            return 130
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
