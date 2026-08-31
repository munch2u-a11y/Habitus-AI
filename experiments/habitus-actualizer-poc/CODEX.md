# Codex host integration

This experiment does not copy or modify Codex model weights. Codex remains the
reasoning and language engine; Habitus becomes a persistent local action-memory
layer around the Codex host stream.

The supported boundary is Codex App Server. Its completed item notifications
are authoritative event records, and `thread/inject_items` can append Habitus
observations to the same model-visible thread without starting another user
turn.

```text
user input -> Codex turn -> completed App Server items
                              |                 |
                              |                 +-> learn from native receipts
                              v
                       final ordinary prose
                              |
                              v
                    Habitus action actualizer
                              |
                              v
                verified return -> graph update
                              |
                              v
                    thread/inject_items
```

`CodexAppServerAdapter.consume()` is intentionally transport-independent. A
client passes it decoded JSON-RPC notifications and sends the returned
`app_server_requests` on the same App Server connection.

It currently handles three paths:

- a completed `commandExecution` becomes a `workspace.run` experience when an
  exit code makes success or failure observable;
- a completed `fileChange` becomes a `workspace.write` experience only after
  workspace-confined filesystem read-back agrees with the reported change;
- the authoritative final `agentMessage` is passed through the ordinary prose
  actualizer only after its turn completes successfully.

Interrupted and failed turns do not actualize. Native receipt IDs and completed
turn markers make duplicate item and turn events idempotent across adapter
restarts. Final prose actualization uses an at-most-once marker: a host crash
leaves a reviewable `uncertain` turn instead of silently repeating a possible
mutation. Out-of-workspace receipts are rejected before graph learning.
Unverified observations may be kept in the ledger, but they cannot change
learned edge strength.

## Live one-turn probe

The repository includes a conservative App Server client. It uses the local
Codex login, starts a read-only Codex turn, lets the adapter observe its event
stream, actualizes any final natural-language commitment, and waits until the
resulting thread injection is acknowledged:

```bash
PYTHONPATH=src python examples/codex_live_probe.py \
  --workspace /path/to/project \
  "Without using a tool, say that you will read README.md."
```

The probe is a test harness, not a replacement terminal UI. It deliberately
declines to expose write or process authority through Habitus. Use the generic
middleware or build a supervised App Server client for a long-running agent.

## What synchronization means

Codex can initially use its native capabilities while Habitus observes the
authoritative completion events. Verified successes and failures alter the
same output edges used by the schema-free actualizer. Later activation
confidence therefore incorporates a local sibling-softmax habit prior based on
learned strength minus conflict penalty.

Recency still belongs to live Y-cipher traversal, but it is excluded from the
action-admission habit prior. This matters: a recent failed attempt must not
become more likely merely because the edge was just activated.

The explicit natural-language commitment grammar remains the execution gate.
A habit can calibrate a compatible candidate; it cannot turn unrelated prose,
quoted user text, or a failed turn into an action.

## Why MCP alone is insufficient

The MCP adapter remains useful for hosts that explicitly call one bridge tool.
It cannot invisibly observe every completed Codex reply by itself. App Server
is the deeper host boundary because it provides final item state, turn status,
native action receipts, and thread-history injection.

## Installing beside Codex

Do not copy hosted model weights into `~/.codex`; they are not available there.
A future personal installation can keep a launcher and state registry under a
user-selected Codex integration directory, while each workspace retains its
own authority policy and persistent SQLite mind. This repository does not
modify `~/.codex` automatically.
