# Six-Lane Causal Membrane Experiment

This branch isolates the runtime experiment in which six independent causal
lanes share one persistent Habitus graph without sharing one global turn lock.
It is based on `main` at `f93b770` and is intentionally separate from the GGUF
adapter experiment.

## Why this branch exists

The experiment tests a narrow architectural claim: language, nonverbal sensory
returns, notifications, speech, inspection, and action can develop through the
same graph while retaining different causal and memory contracts.

The six lanes are:

| Direction | Lane | Role |
| --- | --- | --- |
| Input | `HEAR` | Immediate communication and the only word-learning intake |
| Input | `SEE` | Immediate tool or environmental return |
| Input | `NOTICE` | Deferred notification or background event |
| Output | `SPEAK` | Externalized communication |
| Output | `LOOK` | Non-mutating inspection or navigation |
| Output | `DO` | State-changing execution |

Each lane owns a FIFO queue and monotonic sequence. Independent lanes may wait
concurrently, while the short graph and SQLite mutations remain serialized on
the event-loop thread. Synchronous model and tool handlers run in a bounded
executor owned and explicitly closed by the lane runtime. This is concurrent
causal scheduling, not six threads mutating SQLite in parallel.

## The causal language boundary

Only an inbound `HEAR` event may create word-derived membrane evidence. A
`SEE` or `NOTICE` payload remains available in the immutable developer record,
but its cognitive projection uses an opaque or explicitly supplied sensory
vector. It may affect lower preference memory, habit formation, and nonverbal
child concepts; it cannot enter language-facing retrieval or acquire a semantic
word port merely because its transport happened to contain text.

This distinction prevents filenames, JSON, receipt identifiers, status prose,
and tool errors from becoming accidental vocabulary. Tool returns still matter:
they close the output-to-input causal cycle and can reinforce or discourage the
path that produced them.

## Graph behavior under test

- Every selected lane begins below its trunk with its own mass budget of `1.0`.
- The `SELF -> trunk` connector remains visible in the trace but does not force
  unrelated lanes to compete in one softmax.
- Each active node distributes only its received mass across its own outgoing
  siblings.
- Input X geometry nominates relevant endpoints; the Y cipher chooses legal
  paths by learned travel time rather than replacing path cost with cosine.
- Multiple lanes may converge on a shared concept without losing their distinct
  trunk-prefixed causal receipts.
- A native experience cycle is stored from an output through its observed
  return and back to `SELF`, so later consequences train the earlier action.

The implementation lives primarily in
[`src/habitus_ai/lanes.py`](src/habitus_ai/lanes.py),
[`src/habitus_ai/graph.py`](src/habitus_ai/graph.py), and
[`src/habitus_ai/pipeline.py`](src/habitus_ai/pipeline.py). The membrane contract
is exercised directly by
[`tests/test_membrane_modality.py`](tests/test_membrane_modality.py), and lane
isolation by
[`tests/test_concurrent_lanes.py`](tests/test_concurrent_lanes.py).

## Run it

Install and run the clean-clone suite:

```bash
python -m pip install -e '.[test]'
python -m pytest -q -ra
python -m habitus_ai.demo
```

The current clean-tree result is **71 passed, 3 skipped**. The three skips are
the tests that require a local Qwen GGUF model plus compiled llama.cpp helper
binaries. Those generated binaries, model files, SQLite minds, and run receipts
are intentionally not committed.

The LLM-free embodied action nursery remains runnable without those assets:

```bash
make -C experiments/graph_native_live embodied-nursery
```

To run the optional native experiments, provide local paths explicitly:

```bash
make -C experiments/graph_native_live build \
  LLAMA_CPP_SOURCE=/path/to/llama.cpp \
  OLLAMA_LIB_DIR=/path/to/ollama/libs

make -C experiments/graph_native_live nursery \
  MODEL=/path/to/model.gguf \
  LLAMA_CPP_SOURCE=/path/to/llama.cpp \
  OLLAMA_LIB_DIR=/path/to/ollama/libs
```

## Evidence boundary

This branch demonstrates deterministic modality isolation, independent lane
scheduling, persistent causal records, conserved local flow, and controlled
developmental experiments. It does not establish consciousness, general
intelligence, fluent graph-native speech, or universal autonomous tool use.
Native GGUF results also still depend on pretrained model geometry even when
ordinary natural-language prompt injection is absent.

The broader research history and limitations are recorded in
[`WHITEPAPER.md`](WHITEPAPER.md) and
[`GRAPH_NATIVE_LANGUAGE_HANDOFF.md`](GRAPH_NATIVE_LANGUAGE_HANDOFF.md).
