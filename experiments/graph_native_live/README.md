# Graph-native live seam

This is the first narrow end-to-end assembly of:

```text
user input -> Habitus X nomination -> input Y traversal
           -> shared crown -> output Y traversal
           -> bounded graph activations -> continuous GGUF input rows
           -> ordinary generated response
```

The live user text enters Habitus and is persisted as an immutable input
record. It is **not** passed to llama.cpp. The native packet contains only
categorical basis IDs and scalar activations selected from the admitted graph
endpoints. Retrieved memory text and rendered RAG context are also excluded.

The native bridge uses an empty Qwen chat envelope and constructs one
continuous, non-token semantic slot for each activation by combining a small
fixed codebook of token-embedding anchors. Generated tokens then use the
ordinary llama.cpp path. This is a train-free bootstrap bridge, not the final
learned graph projector.

The preferred local model is `~/Downloads/Qwen3-0.6B-Q8_0.gguf`. Its native
input width is exactly 1024, so the graph boundary and decoder require no
dimension-changing projection. If that file is absent, the tester falls back
to the installed Qwen2.5 0.5B GGUF used by the original parity experiment.

## Run it

The build uses the llama.cpp revision matched to the installed Ollama runtime:

```bash
make -C experiments/graph_native_live build
make -C experiments/graph_native_live live
```

Or run one auditable turn:

```bash
PYTHONPATH=src python3 experiments/graph_native_live/live_tester.py \
  --once "hello there" \
  --show-trace
```

Each turn writes two artifacts under `experiments/graph_native_live/runs/`:

- `*.packet`: the exact bounded packet consumed by the native adapter;
- `*.json`: graph traces, packet assertions, native-run metadata, and output.

The persistent experimental mind defaults to
`experiments/graph_native_live/live_mind.sqlite`.

## What the current result establishes

- A real Habitus input pulse can nominate a shared crown endpoint and traverse
  both halves of the bicone.
- That graph result can become continuous model input without serializing the
  live input or recalled memories as a prompt.
- A frozen local Qwen GGUF can generate coherent continuations from those
  graph-derived soft slots.
- Different admitted concepts can cause different response categories.

## What it does not establish

- The codebook is not learned and covers only a few broad categories.
- Novel factual content does not cross the adapter yet.
- The model still requires fixed role-delimiter embeddings to enter assistant
  generation mode; those delimiters contain no user or memory content.
- This does not yet outperform prompt RAG or prove upper-layer injection.
- A response can be coherent but generic. That is acceptable for this seam
  test and is not counted as factual recall.

The next real gate is replacing the fixed codebook with a trained projector
from a canonical graph packet while holding this native input and receipt path
constant.

## Opaque, label-free baseline

`opaque_skeleton.py` removes the codebook entirely. It creates two opaque
layer-three branches below separate preference paths, pulses them with numeric
stability values, and then connects them through a third opaque node. Four
1024D rows are derived solely from:

- the active input path;
- current dynamic edge weights;
- recent pulse order and numeric stability;
- the active output path.

Node IDs are opaque, the embedder has no lexical-similarity behavior, and the
native packet contains no labels, words, or model embedding anchors. Run it
with:

```bash
make -C experiments/graph_native_live opaque
```

The matrix includes separate branches, their connected state, an exact repeat,
row reversal, sign inversion, and an unrelated opaque control. Coherent text
from these packets demonstrates only that Qwen maps arbitrary native-width
directions onto its language manifold. It does not give those directions
grounded meaning.

## Developmental lexical nursery

`nursery.py` tests a narrower version of early label formation. Internal
concept nodes remain opaque and nonverbal. A word exists as a separate lexical
surface node, using the exact tokenizer and 1024D token-embedding row from the
local Qwen GGUF. Ordinary input and output graph edges act as vertical fibers
between that surface and the lower concept active during the same pulse.

Run the deterministic curriculum and controls with:

```bash
make -C experiments/graph_native_live nursery
```

The primary curriculum presents `I`, ` like`, and ` Josh` separately. It never
presents `I like Josh` as a complete phrase. A held-out output traversal must
recover the ordered lower path, select the learned productive fibers, and emit
the complete token sequence. The run also includes a substitution curriculum,
a deliberately shuffled binding control, an untrained control, receptive
probes, one-pulse-delayed caregiver feedback, invariant checks, and a JSON
receipt under `nursery_runs/`.

This establishes graph-native receptive/productive label binding and ordered
composition in a tiny controlled curriculum. It is not yet free language
generation: the graph currently chooses the strongest learned lexical fiber
at each point, and Qwen supplies its tokenizer and lexical embeddings rather
than transformer inference. The next gate is to turn fiber activations into
bounded candidate logits or hidden-state guidance and let the frozen model
perform token selection.

## Backwards lexical projection

`reverse_nursery.py` removes the diagnostic token lookup from the production
path. The caregiver still knows which token accompanied an experience, but the
graph stores neither that token ID nor its word as node metadata. Label
exposure anchors Qwen's 1024D lexical geometry to the co-active opaque concept.
On output, current fiber weights blend those geometries into one state per
point on the ordered lower path. The native codec compares each state with the
model's complete vocabulary projection and returns its nearest tokens.

```bash
make -C experiments/graph_native_live reverse-nursery
```

The same primary, substitution, shuffled, and untrained controls apply. This
is a stronger inverse-membrane test, but still not transformer inference: it
uses Qwen's vocabulary projection directly. A later experiment can inject
these graph states before or within the transformer so context and learned
language dynamics influence token selection too.

## Accelerated gestation

`accelerated_gestation.py` grows a larger persistent mind without waiting for
wall-clock childhood. It mass-embeds a controlled developmental curriculum in
the exact Qwen GGUF token geometry and replays those episodes through the
ordinary experience vault and overlap-growth kernel. Topic patterns promote
into opaque children and semantic ports. Session coactivation then invokes the
same kernel with those learned concepts as parents, producing category and
domain assemblies rather than a separately hard-coded hierarchy.

```bash
make -C experiments/graph_native_live gestate-fast
```

The compiler adds mirrored output paths, temporal coactivation edges, and an
opaque lexical membrane, then closes and reopens the database before applying
its hatch gate. Its controls include label-absent semantic paraphrases, direct
graph-to-vocabulary production, shuffled expected labels, global/local mass
invariants, recursive path reachability, exact holdout leakage checks, and
restart persistence.

The curriculum is controlled and its category sessions are teacher supplied.
Topic labels receive deliberate caregiver emphasis during productive-fiber
formation. Consequently, productive vocabulary accuracy measures whether the
grown graph preserves and reverses those bindings; it is not evidence that
language or the curriculum categories emerged without supervision. The mass
embedding pass uses averaged native token rows rather than contextual
transformer states in this first scalable build.

Probe a completed snapshot as a minimal graph-native conversational mind with:

```bash
PYTHONPATH=src python3 experiments/graph_native_live/probe_hatched_mind.py \
  --database experiments/graph_native_live/accelerated_gestation_runs/MIND.sqlite
```

Every probe enters through the ordinary `HEAR` trunk. X selects a semantic
endpoint from native geometry, Y must find a legal path from SELF, and the
selected concept's weighted output fibers are projected through the complete
GGUF vocabulary. No natural-language prompt is sent to the transformer. The
result is currently a single lexical response, not fluent conversation.

## Graph-to-transformer hatch

`transformer_hatch.py` takes the next step. A novel message is embedded and
resolved entirely by the hatched graph. The selected concept's productive
lexical fibers are ordered by directed word-transition edges learned from
developmental episodes. Up to eight 1024D lexical-geometry rows enter Qwen
inside a fixed empty-chat envelope, after which the ordinary transformer and
sampler generate a response.

```bash
PYTHONPATH=src python3 experiments/graph_native_live/transformer_hatch.py \
  --database experiments/graph_native_live/accelerated_gestation_runs/MIND.sqlite
```

The matrix holds model, seed, sampling, and structural delimiters constant. It
compares the selected state with reversed row order, the least-related learned
concept, and unrelated opaque rows. Receipts assert that no user string,
retrieved episode text, token ID sequence, or hand-authored semantic codebook
crosses the native boundary. `HABITUS_NATIVE_SKIP_THINK` preloads only Qwen's
empty reasoning delimiters so the bounded run reaches visible answer text.

This is native input-embedding guidance, not upper-layer activation injection.
The rows contain learned lexical geometry and therefore carry language
information even though they contain no serialized words. Current evidence is
limited to broad learned concepts; arbitrary episodic facts, grammar learned
outside the controlled curriculum, and open-ended action selection remain
separate gates.
