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

## Continuous cognitive evaluator

`live_evaluator.py` runs the seam as an ongoing loop rather than a single turn. One `step()`
carries a stimulus through ingress, traversal, packet compilation, native generation, and
outcome reinforcement, then deposits the outbound trace so it re-enters the next pulse as an
internal thought record.

```text
IN:HEAR/SEE/NOTICE  ->  Layer 3 mini-maps  ->  Layer 4 softmax membrane
        ^                                              |
        |                                              v
  THOUGHT record  <-  OUTBOUND_MESSAGE  <-  SELF -> OUT:SPEAK/LOOK/DO -> crown
```

```bash
PYTHONPATH=src:experiments/graph_native_live python3 \
  experiments/graph_native_live/live_evaluator.py \
  --model ~/Downloads/Qwen3-0.6B-Q8_0.gguf \
  --mode once --stimulus-text "hello there" --source-id Josh --show-trace
```

Three packet modes are selectable with `--packet-mode`: `lexical_membrane` (concept centroid,
Layer 3 overlay, preference vector, membrane fibers), `opaque_topological` (four state rows),
and `soft_basis` (named slots with bounded activations). Receipts land in `evaluator_runs/`
under schemas `habitus.cognitive-eval-turn.v1` and `habitus.cognitive-eval-session.v1`.

Only `soft_basis` decodes into consistently coherent language. The raw 1024D modes are
off-distribution for a frozen Qwen3 and produce unrelated text; they remain useful as transport
and zero-leakage tests, not as a language path.

## Preference valence readout

The substrate could learn a stance long before it could say one. The basis vocabulary carried no
valence dimension, so preference state never reached the decoder. Three slots close that gap —
`affinity`, `caution`, `withhold` — activated only from:

- per-source experience states (`preference_mean` weighted by `preference_weight`);
- the ingress membrane's `PREF:*:STABLE` / `PREF:*:UNSTABLE` edge statistics;
- accumulated conflict penalty, which opens `withhold` under sustained negative outcomes.

No stimulus text participates, so an expressed stance is a property of habitual memory rather
than of the sentence that triggered it.

### What this establishes

- Habitual preference formed by experience changes what a frozen transformer says, with no
  prompt text crossing the boundary.
- The same stimulus from a source the substrate has learned to trust and from one associated
  with destabilization decodes to oppositely valenced language.
- Self-preservation reaches language: sustained conflict penalty steers output toward declining
  rather than complying.

### What it does not establish

- Fluency. The stance is reliably valenced, but the codebook-anchor projector sometimes leads
  the model to comment on the anchor semantics instead of speaking from them.
- Open-ended affect. A valence slot is a measured property of stored preference state projected
  into a decoder, not a feeling.
- Generalization beyond the gestated curriculum, which remains the same gate as above.

The next gate is unchanged: replace the fixed codebook with a trained projector while holding
this native input and receipt path constant.

## Fitted continuous projector

The codebook is authored: `BASIS` maps each slot to three hand-picked anchor words and averages
their token embeddings. `projector.py` replaces it with a map fitted from the mind's own records.

```bash
PYTHONPATH=src:experiments/graph_native_live python3 \
  experiments/graph_native_live/projector.py --database MIND.sqlite
```

Features are structural: concept centroid, Layer 3 overlay, dominant preference-node vector, and
the six valence diagnostics (3078D). Targets are the model's token-embedding row for whatever text
each record deposited, mined from `vault_membership`. The fit is closed-form ridge — dual form
while the mind has fewer experiences than feature dimensions — so there is no training loop and
no dependency beyond numpy. Fitting a 71-pair corpus takes seconds, with one `lexeme_codec`
invocation for the whole corpus.

Use it in the loop with `--packet-mode projected --projector projector_runs/projector.json`.

### What this establishes

- A map learned from experience represents the state substantially better than the authored one:
  held-out cosine against the true text embedding is 0.43 versus 0.14 for the codebook, winning
  94% of held-out states, stable from lambda 0.1 to 10.
- The improvement needs no gradient descent, no GPU, and no new runtime dependency in `src/`.

### What it does not establish

- Better generated language. `projected` turns still decode to the same generic output as the
  other raw-vector modes, so the fit is a representation win, not yet a language win.
- The cause is the target, not the fit: `lexeme_codec` returns a mean-pooled embedding, and
  pooling a seven-token sentence collapses the row norm from ~0.9 to ~0.36 — a blurred centroid
  is a weak steering signal, and one row is thin beside the 3-8 anchor-snapped slots `soft_basis`
  emits.

The next gate is per-token targets: predict k rows against the actual token-embedding sequence
instead of its mean. That stays closed-form ridge with a wider Y, and it needs a per-token output
mode in `lexeme_codec`.

## Per-concept vocabulary projection

Regressing onto pooled sentence embeddings caps out, because pooling blurs the target. The
per-concept form uses the granularity the substrate actually has — one row per crown concept —
and learns each concept's anchors instead of authoring them.

```bash
PYTHONPATH=src:experiments/graph_native_live python3 \
  experiments/graph_native_live/projector.py --mode concept --embedder native \
  --database accelerated_gestation_runs/MIND.sqlite
```

Records are grouped by crown concept, scored by tf-idf, and any word appearing in more than 10%
of concepts is dropped before scoring — a developmental curriculum is templated, so frame
vocabulary describes the curriculum rather than any concept. The survivors are embedded with a
leading space and averaged into one direction per concept; the fit maps structural state onto
that direction; `lexeme_codec nearest` decodes predictions back to words.

### What this establishes

- **A graph state reads out as its own vocabulary.** On a gestated mind, 39 of 43 lexical
  concepts (91%) decode to one of their own discriminative words, most to all three:
  `[files, hold, named]`, `[confidence, capability, success]`, `[curiosity, investigation, invites]`.
- The anchors are learned, not authored. Nobody wrote "files/hold/named" for that node; tf-idf
  over its own experiences did.
- Dropping the ubiquity cutoff from 0.25 to 0.10 removes all 16 template-contaminated concepts
  and lifts accuracy from 81% to 91%, saturating below that.

### What it does not establish

- **Half the crown is unreachable this way.** Of 86 crown concepts, 43 are `child:auto:*` nodes
  stored with a zero embedding by design. Their predictions land at the origin and decode to
  nothing. That is the architecture's own invariant working as specified, not a projector bug.
- **Unseen concepts do not generalize.** Held out as whole concepts, predicted directions reach
  only 0.14-0.18 cosine: 86 samples in 3078 dimensions cannot learn to lexicalize a concept the
  mind never lexicalized.
- Decoding to the right words is not the same as generating fluent speech from them. This shows
  the direction is correct, not that the sentence will be.

## Layer 3 population across all six trunks

Promotion recorded only the ingress half of the bicone: every mini-map relation carried
`direction="input"`, and `grow_assembly` accepted an `output_trunk` argument it never used, so a
category or domain assembly was reachable only from its own members — no output traversal from
`SELF` could admit it, and the LOOK and DO assemblies were as unreachable as the SPEAK one.

`merge_structural_relations()` now folds each wiring step's relations back into the concept's
map, and assemblies attach to their effector trunk like any other promoted pair. After
`make gestate-fast`:

- maps describing both halves: **86 / 86** (was 0 / 86)
- relations: input 119, output 86 (was input 86, output 0)
- effector trunks referenced: `OUT:LOOK` 18, `OUT:SPEAK` 16, `OUT:DO` 9

Ingress coverage was already complete, so the map now spans all six trunks rather than the
verbal pair alone.

### What this establishes

- **Position carries meaning on its own.** Zero out a concept's own vector, leaving only its
  structural overlay and preference block, and a fitted projector still predicts its vocabulary
  direction at 0.25 cosine — close to the 0.30 it reaches with the centroid included. Before the
  maps were populated that number was necessarily zero: there was no structure to read.
- Readout of known concepts goes from 91% to **100%**, train cosine 0.905 to 0.998.
- Unseen-concept prediction roughly doubles, 0.14-0.18 to 0.28-0.30.
- All 86 concepts now carry a non-zero overlay, including the 43 opaque children that previously
  had no features at all.

### What it does not establish

- Opaque children still have no lexical centroid, so they decode to nothing directly. Whether
  their overlay lets them inherit their parents' vocabulary is the obvious next experiment.
- 0.30 on unseen concepts is real signal but not a working readout. Predicting the vocabulary of
  a concept the mind has never lexicalized remains open.

**Artifacts generated before the Layer 3 commit carry no maps.** Re-run `gestate-fast` rather
than analyzing an old `.sqlite` under `accelerated_gestation_runs/`.

## Grounding the curriculum in the mind

**What the opaque children represent.** All 43 `child:auto:*` nodes share a cluster, and so a
record set, with their `concept:auto:*` twin, and their discriminative vocabulary is identical in
all 43 cases. A child is not a separate idea — it is the same concept held in nonverbal form,
with the crown twin as its lexical port.

**Is every taught word recoverable from the mind?** Of 36 topic labels, four were absent from
every concept's vocabulary. Three distinct causes, all in the environment:

- `joy` — three characters, below the scoring length floor, never eligible.
- `evidence`, `learning` — their labels were reused inside *other* topics' descriptions
  (`honesty` and `verifying` both described evidence), raising document frequency to 6 so the
  label lost its own concept's ranking to rarer description words: share 1.00 / score 2.66
  against share 0.92 / score 3.47.
- `tests` — a genuine merge. Its 25-record concept co-hosts `evidence` (12) and `verifying` (13),
  and only 48% of its records contain the word.

The first two were fixed at the source: three descriptions rewritten so no topic borrows
another's label, and the length floor dropped to 3. Recovery went from 32/36 to **35/36**.
`tests` stays absent because three related topics genuinely crystallized into one node — a
curriculum question, not a scoring one.

Word selection also moved from raw token frequency to document share x idf, so a word is ranked
by how much of a concept it covers rather than how often it repeats.

### What this establishes

- The mind's concepts are grounded in taught vocabulary, and where they are not, the reason is
  identifiable and usually a curriculum defect rather than a substrate failure.
- A label that appears in another topic's description is measurably harder for the mind to learn
  as its own. Curriculum vocabulary should be disjoint across topics.

### What it does not establish

- That merged topics can be separated. Three related topics collapsing into one node with one
  surviving name is unresolved, and is the clearest remaining developmental limitation.

## GPU offload

The adapter loads every ggml backend it finds, including the accelerator subdirectories that ship
with Ollama, and honours `HABITUS_NATIVE_GPU_LAYERS`:

```bash
HABITUS_NATIVE_GPU_LAYERS=99 make -C experiments/graph_native_live live
```

On a Radeon 780M (RADV Phoenix, uma, fp16, KHR_coopmat, 23 GB visible) all 28 layers offload
through Vulkan for about 25% — 50 tok/s CPU against 63 tok/s Vulkan on this 0.6B model, where
load time dominates. ROCm loads but detects no capable device: gfx1103 needs
`HSA_OVERRIDE_GFX_VERSION` and a userspace the shipped build does not provide.

The default stays CPU. Backend choice changes float ordering and therefore generated text, and
byte-reproducibility is worth more than 25% here.
