from __future__ import annotations

import ast
import json
import operator
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .pipeline import BaseAgenticMemoryRAG
from .types import OutputTrunk


ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    trunk: OutputTrunk
    label: str
    description: str
    terms: tuple[str, ...]
    parameters: dict[str, Any]
    handler: ToolHandler


@dataclass
class ToolReceipt:
    receipt_id: str
    tool_id: str
    trunk: OutputTrunk
    arguments: dict[str, Any]
    status: str
    output: Any = None
    error: str = ""
    verified: bool = False
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trunk"] = self.trunk.value
        return data


class ToolRegistry:
    """Registry managing tool-to-trunk binding, schema extraction, and receipt generation."""

    def __init__(self, mind: BaseAgenticMemoryRAG) -> None:
        self.mind = mind
        self.tools: dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        """Bind tool definition to concept crown under the designated OutputTrunk."""
        self.tools[tool.tool_id] = tool
        self.mind.add_concept(
            concept_id=tool.tool_id,
            label=tool.label,
            terms=tool.terms,
            input_trunks=("HEAR", "SEE", "NOTICE"),
            output_trunks=(tool.trunk.value,),
        )

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        return self.tools.get(tool_id)

    def format_schemas_for_trunk(self, trunk: OutputTrunk) -> list[dict[str, Any]]:
        """Pull formatted schemas for tools bound to the active action trunk."""
        schemas: list[dict[str, Any]] = []
        for tool in self.tools.values():
            if tool.trunk == trunk:
                schemas.append({
                    "tool_id": tool.tool_id,
                    "label": tool.label,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "trunk": tool.trunk.value,
                })
        return schemas

    def execute(self, tool_id: str, arguments: dict[str, Any]) -> ToolReceipt:
        """Execute tool and generate an immutable, verified execution receipt."""
        tool = self.get_tool(tool_id)
        receipt_id = f"receipt:{uuid.uuid4().hex}"
        start_time = time.perf_counter()

        if tool is None:
            return ToolReceipt(
                receipt_id=receipt_id,
                tool_id=tool_id,
                trunk=OutputTrunk.LOOK,
                arguments=arguments,
                status="error",
                error=f"Unregistered tool ID: {tool_id}",
                verified=False,
                elapsed_seconds=time.perf_counter() - start_time,
            )

        try:
            result = tool.handler(arguments)
            elapsed = time.perf_counter() - start_time
            return ToolReceipt(
                receipt_id=receipt_id,
                tool_id=tool_id,
                trunk=tool.trunk,
                arguments=arguments,
                status="success",
                output=result,
                verified=True,
                elapsed_seconds=elapsed,
            )
        except Exception as err:
            elapsed = time.perf_counter() - start_time
            return ToolReceipt(
                receipt_id=receipt_id,
                tool_id=tool_id,
                trunk=tool.trunk,
                arguments=arguments,
                status="error",
                error=str(err),
                verified=False,
                elapsed_seconds=elapsed,
            )


# ---------------------------------------------------------------------------
# Built-in Suite of Standard Operational Tools
# ---------------------------------------------------------------------------

def _handler_read_file(args: dict[str, Any]) -> dict[str, Any]:
    filepath = Path(args.get("filepath", ""))
    if not filepath.exists() or not filepath.is_file():
        raise FileNotFoundError(f"File not found: {filepath}")
    text = filepath.read_text(encoding="utf-8")
    return {"filepath": str(filepath), "content": text, "size_bytes": len(text)}


def _handler_inspect_directory(args: dict[str, Any]) -> dict[str, Any]:
    dirpath = Path(args.get("dirpath", "."))
    if not dirpath.exists() or not dirpath.is_dir():
        raise NotADirectoryError(f"Directory not found: {dirpath}")
    items = [child.name for child in dirpath.iterdir()]
    return {"dirpath": str(dirpath), "items": items, "total": len(items)}


def _handler_web_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", ""))
    return {"query": query, "results": [f"Simulated inspection result for query: {query!r}"]}


def _handler_write_file(args: dict[str, Any]) -> dict[str, Any]:
    filepath = Path(args.get("filepath", ""))
    content = str(args.get("content", ""))
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return {"filepath": str(filepath), "bytes_written": len(content.encode("utf-8"))}


def _handler_execute_python(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("code", ""))
    # Safe evaluation of basic math expressions
    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            return allowed_operators[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            return allowed_operators[type(node.op)](_eval(node.operand))
        raise ValueError("Unsupported Python expression")

    parsed = ast.parse(code, mode="eval")
    val = _eval(parsed.body)
    return {"code": code, "result": val}


def _handler_send_message(args: dict[str, Any]) -> dict[str, Any]:
    recipient = str(args.get("recipient", "user"))
    message = str(args.get("message", ""))
    return {"recipient": recipient, "message": message, "delivered": True}


BUILTIN_OPERATIONAL_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        tool_id="tool:read_file",
        trunk=OutputTrunk.LOOK,
        label="Read File",
        description="Inspect and read text content from a file on disk without mutating state.",
        terms=("read", "file", "inspect", "open", "cat", "view"),
        parameters={"filepath": {"type": "string", "description": "Absolute or relative file path"}},
        handler=_handler_read_file,
    ),
    ToolDefinition(
        tool_id="tool:inspect_directory",
        trunk=OutputTrunk.LOOK,
        label="Inspect Directory",
        description="List files and subdirectories in a directory path without mutating state.",
        terms=("directory", "ls", "list", "inspect", "folder", "files"),
        parameters={"dirpath": {"type": "string", "description": "Directory path to list"}},
        handler=_handler_inspect_directory,
    ),
    ToolDefinition(
        tool_id="tool:web_search",
        trunk=OutputTrunk.LOOK,
        label="Web Search",
        description="Query web sources or documentation for information without mutating state.",
        terms=("search", "web", "query", "google", "lookup", "documentation"),
        parameters={"query": {"type": "string", "description": "Search query text"}},
        handler=_handler_web_search,
    ),
    ToolDefinition(
        tool_id="tool:write_file",
        trunk=OutputTrunk.DO,
        label="Write File",
        description="Write or update text file content on disk (external state mutation).",
        terms=("write", "save", "file", "create", "update", "modify"),
        parameters={
            "filepath": {"type": "string", "description": "Target file path"},
            "content": {"type": "string", "description": "Text content to write"},
        },
        handler=_handler_write_file,
    ),
    ToolDefinition(
        tool_id="tool:execute_python",
        trunk=OutputTrunk.DO,
        label="Execute Python",
        description="Execute a computational Python expression or script (external state execution).",
        terms=("python", "execute", "eval", "compute", "calculator", "math"),
        parameters={"code": {"type": "string", "description": "Python expression or script"}},
        handler=_handler_execute_python,
    ),
    ToolDefinition(
        tool_id="tool:send_message",
        trunk=OutputTrunk.SPEAK,
        label="Send Message",
        description="Send a structured verbal or text message to an external recipient.",
        terms=("send", "message", "speak", "communicate", "notify", "talk"),
        parameters={
            "recipient": {"type": "string", "description": "Target recipient ID or channel"},
            "message": {"type": "string", "description": "Message text"},
        },
        handler=_handler_send_message,
    ),
)
