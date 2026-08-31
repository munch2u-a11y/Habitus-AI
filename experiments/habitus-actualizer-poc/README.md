# Habitus Actualizer

Habitus Actualizer is a proof-of-concept workspace ability runtime for existing
agents. It watches ordinary assistant output such as:

> I'll read `README.md` and list `src`.

It can execute the recognized abilities without giving the language model a
tool schema or requiring it to emit a JSON tool call. Full receipt-backed
observations remain available to the host, while the model receives only a
short first-person perception such as `I read README.md: ...`.

This is an alpha experiment, not a general natural-language shell.

## What ships

Five deliberately narrow abilities are included:

| Ability | Effect | Default authority |
| --- | --- | --- |
| `workspace.list` | Inspect a directory | Enabled |
| `workspace.read` | Read bounded UTF-8 text | Enabled |
| `workspace.navigate` | Change a virtual workspace directory | Enabled |
| `workspace.write` | Atomic write plus hash read-back | Disabled |
| `workspace.run` | Run an argv command without a shell | Denied until allowlisted |

Each ability has its own FIFO lock and abilities of different kinds may execute
concurrently. Graph and SQLite commits stay on the caller's event-loop thread;
only external work enters the bounded worker pool.

## Install

```bash
python -m pip install -e '.[test]'
python -m pytest
```

No database server, model service, embedding download, or agent framework is
required. The package uses Python's standard library and persistent SQLite.

MCP is an optional transport rather than a core dependency:

```bash
python -m pip install -e '.[mcp,test]'
```

## Use from an agent loop

```python
import asyncio

from habitus_actualizer import Actualizer, AgentOutputMiddleware, WorkspacePolicy


async def main():
    policy = WorkspacePolicy(
        "/path/to/project",
        allow_write=True,
        allowed_commands=("python3", "pytest"),
    )
    async with Actualizer("/path/to/project", policy=policy) as actualizer:
        middleware = AgentOutputMiddleware(actualizer)
        result = await middleware.process({
            "role": "assistant",
            "content": "I'll read `pyproject.toml` and run `python3 -m pytest -q`.",
        })

        # Feed only this natural projection back to the language model.
        print(result.perception)

        # Keep the complete receipt packet in the trusted host or evaluator.
        assert result.observation["results"][0]["verified"] is True


asyncio.run(main())
```

The model sees no callable tools in this integration. The post-generation hook
recognizes a conservative natural-language action grammar, enforces policy,
routes each accepted action through the persistent graph, executes it, observes
the return, and reinforces the exact path only from that receipt.

## Bounded memory plus actualization

`SelfSession` puts the model at the shared `SELF` boundary. Incoming language
is stored and recalled before generation; ordinary output either opens a
speaking cycle or is actualized as an action. A later message closes the prior
speaking cycle, so experience is recorded as output → return rather than as two
unrelated chat rows.

```python
import asyncio

from habitus_actualizer import Actualizer, SelfSession

with Actualizer("/path/to/project") as actualizer:
    session = SelfSession(actualizer, session_id="my-session")
    frame = session.prepare_input("Please inspect the project.", source_id="Josh")

    # Send frame.text to any ordinary chat model, with no tool catalog.
    generated_text = "I'll list `.`."
    output = asyncio.run(session.process_output(generated_text))

    if output.perception:
        next_frame = session.prepare_observation(output.perception)
```

The transient frame is deliberately plain first-person language. It combines:

- a fixed-budget memory projection;
- a small rolling session view with the active human task pinned;
- the current message or observed action result.

Record IDs, graph traces, hashes, timings, confidence scores, and tool-call
metadata stay out of that frame. Canonical records, full receipts, lower-layer
experience projections, and learned edge state remain persistent in SQLite.

Recall uses three bounded lanes. Pure cosine remains an independent top-three
candidate pool, global BM25 rescues literal facts in a cold mind, and graph
vault retrieval adds learned associations. Their records are interleaved only
when constructing the bounded language view, so one lane cannot consume the
whole projection before the others are considered.

## Local Ollama no-tools demo

The included bounded agent loop sends only `model`, `messages`, generation
options, and `stream` to Ollama. It never sends a `tools` field and does not
preserve a separate conventional chat history. `SelfSession` rebuilds each
bounded just-in-time frame from persistent memory, short-term observations, and
the active task:

```bash
PYTHONPATH=src python3 examples/ollama_context_agent.py \
  --workspace examples/ollama_workspace \
  --state /tmp/habitus-ollama-demo.sqlite \
  --model qwen3.5:4b \
  --allow-command python3 \
  --require-ability workspace.read \
  --require-ability workspace.run \
  'Read the available project guidance, locate and run the appropriate status reporter with python3, and report its actual output.'
```

The `--require-ability` options are evaluator gates, not capabilities exposed to
the model. They prevent an unsupported final answer from being scored complete.
The sample workspace contains a decoy reporter so the model must read, discover,
choose, execute, and use observed stdout rather than merely guess a filename.

## Persistent continuous agent

`habitus-agent` adds the missing heartbeat around the same mind and ability
runtime. Messages and notifications enter a durable SQLite queue, so inputs that
arrive during generation wait for the next atomic cycle and survive a restart.
The graph, memories, learned ability weights, virtual working directory, active
conversation, lifecycle receipts, and outward messages are also persistent.
One bounded, content-free workspace sensor records shallow file appearance,
change, and disappearance as NOTICE input. It ignores the private `.habitus`
state, protected names, and file contents; disable it with
`--no-workspace-sensor`.

Queue a message before or while the agent is running:

```bash
habitus-agent --workspace /path/to/nursery send \
  --source Josh 'Please look around and tell me what is here.'
```

Then run one continuous local model process:

```bash
habitus-agent --workspace /path/to/nursery run \
  --model qwen3.5:9b-q4_K_M \
  --allow-command python3 \
  --idle-seconds 60 \
  --autonomous-actions \
  --idle-action-budget 4
```

Ordinary event cycles may inspect or act repeatedly until the model produces an
outward answer. Quiet cycles are different: ordinary prose is stored as a
private, explicitly unverified thought and never enters the outbox. A grounded
action can still be actualized during quiet time when `--autonomous-actions` is
enabled. The action budget is bounded between external inputs, and an exact
repeat of a recent idle action is suppressed before execution so a successful
loop cannot reinforce itself indefinitely. Inside one active event, repetition
is matched by canonical ability and arguments rather than model wording. A
paraphrased re-list of the same unchanged directory is therefore stopped before
execution and cannot collect another success reward.

Observe the runtime without exposing its internal ledger to the model:

```bash
habitus-agent --workspace /path/to/nursery status
habitus-agent --workspace /path/to/nursery outbox --mark-delivered
```

Only one running daemon should own a given loop ledger. After an interrupted
single-daemon run, `run` requeues an in-progress event by default. Use a positive
`--recover-after-seconds` lease if another process may still be finishing it.
Idle autonomy does not broaden authority: reads remain workspace-confined,
writes remain disabled unless enabled, and commands remain denied unless their
executable is explicitly allowlisted. This is a host lifecycle, not a claim
that idle model generations are conscious or intrinsically goal-directed.

## MCP adapter

The optional MCP server exposes one host-facing post-generation bridge—not five
ability tools. It starts in probe-only mode:

```bash
habitus-actualizer-mcp --workspace /path/to/project
python examples/mcp_sync_probe.py --workspace .
```

Add `--execute` only for a supervised live workspace. For schema-free use, the
agent host invokes the MCP bridge after normal text generation instead of
advertising it to the model as a selectable tool. See [MCP.md](MCP.md) for the
sync-up workflow, the exact integration boundary, and transport guidance.

For a deeper Codex integration, [CODEX.md](CODEX.md) describes the App Server
event adapter and the included read-only live probe. That path can learn from
Codex's authoritative native command/file receipts and actualize completed
ordinary prose without relying on a model-selected MCP call.

## Command line

Read and list are safe defaults:

```bash
habitus-actualize --workspace . "I'll read README.md and list src."
```

Mutating and process abilities require explicit authority:

```bash
habitus-actualize \
  --workspace . \
  --allow-write \
  --allow-command python3 \
  "I'll write 'hello' to 'note.txt' and run 'python3 --version'."
```

Use `--dry-run` to inspect activations and policy decisions without execution.

## Activation contract

The initial parser intentionally favors false negatives over accidental action.
It recognizes explicit assistant commitments such as `I'll`, `I will`,
`I'm going to`, and `let me`, followed by a supported action verb. A committed
single-line shell block may refine the exact command named by a run statement;
an uncommitted code block stays inert. Chained actions are bounded after policy
validation to three per pulse. User messages are never executable by default.

This grammar is replaceable. Frameworks may keep the graph, scheduler, policy,
and receipt contracts while substituting a classifier that is appropriate for
their environment.

## What the graph contributes

The private engine is extracted from Habitus's dual-cipher runtime:

- each ability is an output concept under `LOOK` or `DO`;
- the conservative micro-grammar nominates an ability and semantic geometry
  calibrates its activation confidence;
- the Y cipher records the learned path through the action tree;
- a call is persisted before execution;
- its observed success or failure returns through `SEE` to the same cycle;
- verified success strengthens that path and verified failure weakens it;
- local sibling softmax keeps ability preferences relative rather than allowing
  unbounded accumulated scores.

Repeated verified use therefore forms a persistent relative action habit.
Policy denial and unverified claims cannot train that habit. A bare interpreter
such as `python3` is rejected as incomplete; a workspace script or explicitly
allowed module is required.

Language memory uses the same persistent substrate. Every incoming experience
is projected into language-free `SELF`, stimulus, and preference vaults. Similar
experiences can promote a lower child pattern and, only for `HEAR` language,
attach a semantic port. Later nonverbal experience is routed through its deepest
matching learned child and applies the same overlap kernel recursively. When two
terminal branches co-activate, their promoted child is connected to both without
adding ancestor shortcuts that flatten later depth. The kernel remains
intentionally conservative: one-pass fact dumps depend primarily on cold
cosine/BM25 access, while repeated experience gives the graph evidence from
which associations can grow.

## Reproducible memory probe

The repository includes an FP-AMB evaluator but does not bundle that external
corpus:

```bash
PYTHONPATH=src python3 benchmarks/fp_amb_growth.py \
  --corpus /path/to/fp_amb_500k_cross_session.jsonl \
  --questions /path/to/fp_amb_cross_session_questions.json \
  --database /tmp/habitus-fpamb.sqlite \
  --growth \
  --ollama-model qwen3.5:4b \
  --output /tmp/habitus-fpamb-result.json
```

The evaluator labels answer-bearing context recall separately from generated
answer accuracy. See [`EVALUATION.md`](EVALUATION.md) for the current frozen
results and their limitations.

The graph does not make an unsafe request safe. Policy is checked before a path
is activated.

## Security boundary

Read [SECURITY.md](SECURITY.md) before enabling execution, writes, or programs.
The default policy confines path resolution to one workspace, hides common
secret locations, limits reads and outputs, disables shell execution, strips
most environment variables, and denies every program until its basename is
allowlisted.

This is not an operating-system sandbox. An allowlisted program may still read
or modify anything permitted to the current operating-system user. Use a
container or restricted OS account for untrusted models, repositories, or code.

## Evidence claims

This repository is meant to demonstrate deployable, schema-free action routing,
cross-ability concurrency, causal receipts, persistence, and bounded habit
updates. It does not claim perfect intent understanding, arbitrary task
completion, consciousness, or secure execution of hostile code.

[`EVALUATION.md`](EVALUATION.md) defines the behavioral metrics and the frozen
positive/negative corpus needed before making a broader accuracy claim.
