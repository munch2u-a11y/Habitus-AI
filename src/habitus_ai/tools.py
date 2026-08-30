from __future__ import annotations

import ast
import inspect
import json
import operator
import os
import time
import uuid
from concurrent.futures import Executor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .async_workers import await_sync_call
from .graph import INPUT_NODE_IDS, SELF_ID
from .pipeline import BaseAgenticMemoryRAG
from .types import ExperienceCycle, InputTrunk, OutputDecision, OutputTrunk, RecordType


ToolHandler = Callable[[dict[str, Any]], Any]
ReturnRouter = Callable[[str, Any, str], str | None]
SensoryEncoder = Callable[[str, Any, str, int], Sequence[float] | None]


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    trunk: OutputTrunk
    label: str
    description: str
    terms: tuple[str, ...]
    parameters: dict[str, Any]
    handler: ToolHandler
    opaque: bool = False
    bind_to_trunk: bool = True
    return_router: ReturnRouter | None = None
    sensory_encoder: SensoryEncoder | None = None


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
    cycle_id: str | None = None
    output_record_id: str | None = None
    return_record_id: str | None = None
    outcome_id: str | None = None

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
        """Bind one motor fiber to its action trunk and sensory return fibers."""
        self.tools[tool.tool_id] = tool
        self.mind.add_concept(
            concept_id=tool.tool_id,
            label=(tool.tool_id if tool.opaque else tool.label),
            terms=(() if tool.opaque else tool.terms),
            input_trunks=(InputTrunk.SEE,),
            output_trunks=((tool.trunk.value,) if tool.bind_to_trunk else ()),
            kind="ability",
            semantic_embedding=not tool.opaque,
        )
        for status in ("success", "error"):
            return_id = self.return_concept_id(tool.tool_id, status)
            self.mind.add_concept(
                concept_id=return_id,
                label=(return_id if tool.opaque else f"{tool.label} {status}"),
                terms=(() if tool.opaque else (tool.label, status, "result")),
                kind="ability_return",
                semantic_embedding=not tool.opaque,
            )
            self.mind.add_relation(
                tool.tool_id,
                return_id,
                side="input",
                delta_y=1.0,
            )

    @staticmethod
    def return_concept_id(tool_id: str, status: str) -> str:
        return f"{tool_id}:return:{status}"

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

    def execute(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        stability_delta: float | None = None,
        evidence_quality: float = 1.0,
        decision: OutputDecision | None = None,
    ) -> ToolReceipt:
        """Execute one ability as output, observe its return, and close the cycle."""
        prepared = self._prepare_execution(tool_id, arguments, decision=decision)
        if isinstance(prepared, ToolReceipt):
            return prepared
        tool, receipt_id, start_time, cycle = prepared
        try:
            if inspect.iscoroutinefunction(tool.handler):
                raise TypeError("an async tool handler requires execute_async()")
            result = tool.handler(arguments)
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise TypeError("an async tool handler requires execute_async()")
            status = "success"
            error = ""
        except Exception as err:
            result = None
            status = "error"
            error = str(err)
        return self._finish_execution(
            tool,
            receipt_id,
            arguments,
            cycle,
            start_time,
            result=result,
            status=status,
            error=error,
            stability_delta=stability_delta,
            evidence_quality=evidence_quality,
        )

    async def execute_async(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        stability_delta: float | None = None,
        evidence_quality: float = 1.0,
        decision: OutputDecision | None = None,
        executor: Executor | None = None,
    ) -> ToolReceipt:
        """Run external work without blocking other cognitive flow lanes.

        Graph and memory commits occur on the calling event-loop thread. A
        synchronous handler alone is moved to a worker thread; async handlers
        are awaited directly. Tool handlers therefore must not access the
        registry's ``MindStore`` connection themselves.
        """
        prepared = self._prepare_execution(tool_id, arguments, decision=decision)
        if isinstance(prepared, ToolReceipt):
            return prepared
        tool, receipt_id, start_time, cycle = prepared
        try:
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(arguments)
            else:
                result = await await_sync_call(
                    tool.handler,
                    arguments,
                    executor=executor,
                )
                if inspect.isawaitable(result):
                    result = await result
            status = "success"
            error = ""
        except Exception as err:
            result = None
            status = "error"
            error = str(err)
        return self._finish_execution(
            tool,
            receipt_id,
            arguments,
            cycle,
            start_time,
            result=result,
            status=status,
            error=error,
            stability_delta=stability_delta,
            evidence_quality=evidence_quality,
        )

    def _prepare_execution(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        decision: OutputDecision | None,
    ) -> tuple[ToolDefinition, str, float, ExperienceCycle] | ToolReceipt:
        """Persist the motor action before handing control to the environment."""
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

        if decision is None:
            decision = self.mind.classify_output(
                tool.label,
                target_concept_id=tool.tool_id,
                required_output_trunk=tool.trunk,
            )
        if (
            decision.trunk != tool.trunk
            or decision.trace is None
            or decision.trace.target_node_id != tool.tool_id
        ):
            raise ValueError("the supplied output decision does not terminate at this ability")
        invocation = json.dumps(
            {"ability": tool.tool_id, "arguments": arguments},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        cycle = self.mind.begin_output_cycle(
            invocation,
            decision,
            source_id="self",
            record_type=RecordType.TOOL_CALL,
            metadata={
                "ability_id": tool.tool_id,
                "arguments": dict(arguments),
                "developer_ledger": True,
            },
        )
        return tool, receipt_id, start_time, cycle

    def _finish_execution(
        self,
        tool: ToolDefinition,
        receipt_id: str,
        arguments: dict[str, Any],
        cycle: ExperienceCycle,
        start_time: float,
        *,
        result: Any,
        status: str,
        error: str,
        stability_delta: float | None,
        evidence_quality: float,
    ) -> ToolReceipt:
        """Commit the observed sensory consequence and close the cycle."""
        elapsed = time.perf_counter() - start_time
        verified = True
        default_reward = 0.20 if status == "success" else -0.20
        reward = default_reward if stability_delta is None else float(stability_delta)

        sensory_payload = {
            "ability": tool.tool_id,
            "status": status,
            "output": result,
            "error": error,
            "elapsed_seconds": elapsed,
        }
        return_concept_id = (
            tool.return_router(status, result, error)
            if tool.return_router is not None
            else None
        ) or self.return_concept_id(tool.tool_id, status)
        status_concept_id = self.return_concept_id(tool.tool_id, status)
        return_path = [
            SELF_ID,
            INPUT_NODE_IDS[InputTrunk.SEE],
            tool.tool_id,
            status_concept_id,
        ]
        if return_concept_id != status_concept_id:
            return_path.append(return_concept_id)
        sensory_embedding = (
            tool.sensory_encoder(
                status,
                result,
                error,
                self.mind.embedder.dimension,
            )
            if tool.sensory_encoder is not None
            else None
        )
        returned = self.mind.record_cycle_return(
            cycle.cycle_id,
            json.dumps(sensory_payload, sort_keys=True, separators=(",", ":"), default=str),
            input_trunk=InputTrunk.SEE,
            status=status,
            stability_delta=reward,
            verified=verified,
            terminal=True,
            source_id=tool.tool_id,
            record_type=RecordType.TOOL_RESULT,
            record_id=receipt_id,
            event_id=f"event:{receipt_id}",
            return_concept_id=return_concept_id,
            return_path_node_ids=return_path,
            evidence_quality=evidence_quality,
            provenance={"ability_id": tool.tool_id},
            metadata={
                "ability_id": tool.tool_id,
                "arguments": dict(arguments),
                "developer_ledger": True,
            },
            embedding=sensory_embedding,
        )
        return ToolReceipt(
                receipt_id=receipt_id,
                tool_id=tool.tool_id,
                trunk=tool.trunk,
                arguments=arguments,
                status=status,
                output=result,
                error=error,
                verified=verified,
                elapsed_seconds=elapsed,
                cycle_id=cycle.cycle_id,
                output_record_id=cycle.output_record_id,
                return_record_id=returned.record.record_id,
                outcome_id=returned.outcome.outcome_id,
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
