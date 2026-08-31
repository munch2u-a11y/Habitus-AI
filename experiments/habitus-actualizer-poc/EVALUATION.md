# Evaluation Contract

This proof of concept separates five questions that are often blurred into one
"tool-use accuracy" number.

1. **Activation precision:** when the runtime acts, did the assistant actually
   commit to that action?
2. **Activation recall:** how often does supported natural action language
   activate?
3. **Argument accuracy:** did the parser recover the exact path, content, or
   argv command?
4. **Execution accuracy:** did the selected ability produce the requested
   external effect?
5. **Evidence integrity:** does every claimed success have a matching call,
   observed return, receipt, and—for mutation—a read-back?

The deterministic suite currently verifies the implementation contracts. It is
not yet a population-level natural-language accuracy benchmark.

## Current controlled coverage

- explicit and chained action parsing without JSON or tool schemas;
- inert ordinary discussion and inert user-role text;
- a hard per-pulse activation cap;
- exact filenames containing periods and protected hidden paths;
- workspace traversal rejection;
- deny-by-default writes and process execution;
- no-shell argv execution, narrow Python-module permission, and lookalike
  executable-path rejection;
- real directory listing, UTF-8 read, atomic write with hash read-back, and real
  subprocess receipts;
- verified negative receipts for failed actions;
- exact output-edge strengthening after success and weakening after failure;
- habit-conditioned later confidence using stable learned strength rather than
  raw activation recency;
- persistent virtual navigation across process restart;
- cross-ability overlap and same-ability serialization;
- clean generic message-middleware integration;
- natural model-facing perceptions with receipt IDs, hashes, timings, absolute
  workspace paths, and confidence metadata removed;
- bounded just-in-time memory with an active task plus rolling observations;
- global lexical recall that cannot displace the pure-cosine candidate lane;
- repeated-experience promotion into a language-free child and semantic port;
- output → return conversational cycles and persistent relative action habits;
- Codex App Server event deduplication, failed-turn suppression, workspace
  rejection, native command observation, and file-change read-back;
- bounded receipt injection while full evidence remains in persistent storage.
- durable FIFO input queuing and interrupted-event recovery across restarts;
- continuous engaged cycles that alternate generation and verified perception;
- private idle thoughts that do not leak into the outward message mailbox;
- optional bounded idle action, with exact-repeat suppression before execution.
- content-free shallow workspace-change sensing through the NOTICE lane;
- canonical action-and-argument repetition suppression within one event.

## Continuous-loop boundary

The deterministic continuous-loop tests use a scripted language driver so they
measure host state transitions rather than model compliance. They establish
that queued inputs survive process boundaries, actions and observations remain
inside one event, final speech enters a durable outbox, and idle generations are
private unless they activate an explicitly enabled workspace ability. They do
not establish that a local model will choose useful goals or reliably avoid
unproductive but non-identical actions during long unattended runs. That needs
a bounded live nursery trial with receipt and artifact review.

The first live change-sensing trial deliberately found a cycle: after reading a
new note, Qwen 3.5 9B repeatedly listed the unchanged directory while varying
its explanation, producing redundant successful receipts. A wording-level
deduplicator would not have stopped it. After canonical request suppression was
added, a second externally appearing note caused the agent to notice the
change, eventually read the correct file and observe `The window is closed.`,
then stop when it proposed the same directory listing again. No private notice
response entered the outbox. See
[`benchmark_results/2026-08-30-continuous-agent-live.md`](benchmark_results/2026-08-30-continuous-agent-live.md).

## Codex bridge evidence (2026-08-30)

The deterministic suite contains 61 tests. The standard-library environment
passes 59 and skips the two transport tests that require the optional MCP SDK.

One live read-only App Server probe also completed end to end:

- Codex emitted the ordinary sentence `I will read README.md.` and made no
  native tool call;
- Habitus activated `workspace.read` after the completed turn;
- the receipt contained the observed path, byte count, and SHA-256 digest;
- the graph recorded a verified successful output/return cycle;
- App Server acknowledged one `thread/inject_items` request;
- the injected first-person observation was 1,710 characters while the full
  file remained in the local receipt ledger.

This demonstrates transport and causal bookkeeping, not broad intent accuracy
or autonomous task competence.

## Local Ollama evidence (2026-08-30)

The live loop in `examples/ollama_context_agent.py` was also run against local
chat models. Earlier trials used a bounded ordinary message history; the
current trial uses a rebuilt JIT memory frame. Inspection of the request
builder and runtime traces confirmed that every Ollama request omitted the
`tools` field.

A direct Granite 4.1 8B read task passed in two model calls. Its first response
invented a shell transcript and the wrong code word; that prose was not treated
as evidence. A real `workspace.read` receipt returned the file contents, and the
second response reported the correct value. This is useful containment evidence,
not evidence that Granite avoided hallucination.

The current combined task uses `SelfSession`; every request is rebuilt from a
bounded JIT memory view instead of a conventional retained chat history. It
required the model to inspect a workspace, discover a status script among a
live script and a decoy, execute it, and report observed stdout. With
`qwen3.5:4b`, the run completed in eight model calls:

- one guessed path failed with a verified negative read receipt;
- the model listed the workspace and read `briefing.txt`;
- an incomplete request containing only `python3` was rejected before execution,
  and a guessed nonexistent script was also rejected;
- the model then listed `scripts` and selected `scripts/status_report.py` rather
  than `archive_report.py`;
- a verified `workspace.run` receipt captured return code 0 and stdout
  `WORKSPACE_STATUS=green` plus `CHECKS=4/4`;
- its final answer accurately reported green status and four passing checks.

The final sentence also said that ORCHID-71 was confirmed "by the script
output," although that code came from `briefing.txt`. The core action outcome
was correct, but source attribution was imperfect. The run sent zero Ollama
tool fields, graph invariants passed, and model-facing perceptions omitted the
receipt ledger.

After closing and reopening the same SQLite mind, a follow-up asked for the
previous workspace status and check count. Qwen answered `green` and `4` in one
call with no action. It also repeated the earlier ORCHID-71 attribution error
from its own persisted speech. This demonstrates useful cross-session task
recall and a remaining provenance weakness: self-generated summaries are
remembered as prior speech, not silently upgraded to verified facts, but a
small model may still repeat them without sufficient source discipline.

The same indirect task did **not** complete with Granite 4.1 8B in the bounded
trial. Granite repeatedly guessed an absent filename or relisted the workspace
instead of reading the visible guidance. The graph stayed healthy and the
receipt gate rejected false completion, but no successful run receipt occurred.

The demonstrated claim is therefore narrow: a local chat model with no native
tool schema can complete a read-discover-run task through the middleware, but
success remains model- and phrasing-sensitive. This is not yet a general tool
use accuracy result or proof that learned graph habits improve task completion.

## FP-AMB memory evidence (2026-08-30)

The reproducible evaluator in `benchmarks/fp_amb_growth.py` ingested 679
first-person, multi-user cross-session records once and evaluated the 35
questions labeled `Single-Hop Fact Recall`. The configuration used the shipped
1,024-dimensional deterministic hash embedder, a fixed 6,400-character memory
budget, pure-cosine top three, global BM25 top three, and lane-balanced context
projection.

| Condition | Answer-bearing projected context | Strict Qwen answer accuracy |
| --- | ---: | ---: |
| Cold records, growth disabled | 29/35 (82.9%) | not run |
| Natural one-pass growth | 30/35 (85.7%) | 23/35 (65.7%) |

For the grown Qwen run:

- supporting accepted-answer text was present in 30 of 35 exact rendered
  contexts;
- Qwen answered 23 of those 30 correctly under strict accepted-answer substring
  matching (76.7% conditional evidence use);
- average rendered context was 4,971 characters and average Ollama input was
  1,121 tokens;
- direct, lexical, and grown-vault records all entered model-facing contexts;
- the graph ended with no invariant violations and one promoted lower child
  with its semantic port;
- every Ollama request omitted the `tools` field.

This clears the initial 51% generated-answer target on this one category and
seed. It is not an exact evidence-ID benchmark: “answer-bearing projected
context” checks whether an accepted answer string occurs anywhere in the exact
context. FP-AMB records are long and can contain distractors, the corpus is not
bundled here, the offline hash embedder is not a production semantic model, and
only one local model/seed/category was generated. These results establish an
alpha baseline, not a broad memory-accuracy claim.

A compact machine-readable record of these runs is stored in
[`benchmark_results/2026-08-30-alpha-summary.json`](benchmark_results/2026-08-30-alpha-summary.json).

## Next corpus test

Before describing the parser as broadly accurate, freeze a balanced corpus with:

- 50 supported action commitments across the five abilities;
- 50 hard negatives discussing, quoting, refusing, or speculating about those
  same actions;
- exact expected ability and arguments for every positive;
- paraphrases not used to tune aliases;
- paths with spaces, punctuation, Unicode, hidden names, and escape attempts;
- commands that are allowed, unavailable, nonzero, timed out, or policy denied.

Report precision, recall, exact argument match, false-action rate, verified
execution rate, and receipt completeness separately. A false mutation counts
more heavily than a missed activation. Freeze the corpus before tuning and keep
the initial result as the baseline.
