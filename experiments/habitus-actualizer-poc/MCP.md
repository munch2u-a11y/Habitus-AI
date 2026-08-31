# MCP post-generation adapter

The optional MCP adapter is a transport around the existing middleware
boundary. It does not turn the five workspace abilities into five MCP tools.

```text
model produces ordinary assistant text
                 |
                 v
host post-generation callback
                 |
                 v
actualize_assistant_output(text)     one MCP bridge
                 |
                 v
graph route -> policy -> ability -> receipt -> observation
```

An MCP client sees exactly one tool with one argument, `text`, plus two
read-only resources. For a truly schema-free model integration, the host must
call this bridge automatically after generation and omit it from the model's
tool catalog. A conventional MCP host that advertises every connected tool to
its model will expose this one bridge schema; that remains useful for testing,
but it is a different integration claim.

## Install and probe

```bash
python -m pip install -e '.[mcp,test]'
habitus-actualizer-mcp --workspace /path/to/project
```

Probe mode is the default. The server recognizes proposed abilities and
returns routing decisions, but it neither executes them nor reinforces graph
paths. This is the safe mode for a short model sync-up or language-compatibility
session.

The included example runs the official MCP client and server in one process:

```bash
python examples/mcp_sync_probe.py --workspace .
python examples/mcp_sync_probe.py --workspace . \
  --sample "I'll read README.md and list src."
```

The sample text can come from Gemini, a local model, Codex, a frozen corpus, or
a human. The actualizer never needs the provider credential:

```python
assistant_text = await host_model.generate(user_input)
result = await mcp_client.call_tool(
    "actualize_assistant_output",
    {"text": assistant_text},
)
```

The model call stays in the host because MCP server-initiated sampling is not
part of this design. This also makes the experiment provider-neutral.

## Supervised live sync

Enable execution only when the workspace policy is ready:

```bash
habitus-actualizer-mcp \
  --workspace /path/to/sandbox \
  --execute
```

`--execute` is fixed when the server starts. It is not a bridge argument, so a
caller connected to a probe-only session cannot grant itself execution. Reads,
listings, and virtual navigation retain their safe defaults. Writes and
programs still require separate launch authority:

```bash
habitus-actualizer-mcp \
  --workspace /path/to/sandbox \
  --execute \
  --allow-write \
  --allow-command python3
```

Only verified returns alter the ability path. Synthetic probe outputs do not
become fabricated experience. A useful gestation run is therefore two-stage:

1. Probe a representative set of ordinary first-person outputs and inspect
   activations, suppressions, and false positives.
2. Run a small supervised live set inside a disposable workspace, allowing
   actual success or failure receipts to shape the graph.

## Resources

- `actualizer://status` reports probe/execute mode, configured authority,
  virtual current directory, and graph health.
- `actualizer://contract` describes the host-only post-generation boundary and
  the abilities hidden behind it.

## Transports

Stdio is the default and is appropriate for a local host. Streamable HTTP is
available for local testing:

```bash
habitus-actualizer-mcp \
  --workspace /path/to/sandbox \
  --transport streamable-http \
  --port 8000
```

The bundled command binds HTTP to `127.0.0.1` only. It does not provide remote
authentication. A remote deployment should mount `create_mcp_server(...)` in a
properly authenticated service rather than widening this command's bind
address.
