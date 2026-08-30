# Architecture Contract

## Purpose

This package is a compact, inspectable agentic-memory substrate. It preserves the
useful parts of the bicone design without pretending that graph structure itself
is an LLM or a source of factual truth.

It combines four things:

1. a shared semantic surface for language-level endpoint nomination;
2. distinct input and output graph traversal from one `SELF` origin;
3. immutable canonical evidence with direct and graph-local retrieval;
4. verified outcome learning under conserved relative weights.

The graph is the learned routing structure. The SQLite records are the evidence
authority. An LLM, embedding model, and execution gateway are replaceable
adapters around that core.

## Topology

There is exactly one seed origin:

```text
                              shared semantic crown
                        concepts, vectors, and vaults
                         /                       \
             HEAR -- SEE -- NOTICE       SPEAK -- LOOK -- DO
                         \                       /
                                   SELF
```

The drawing is flattened. Operationally, every crown concept may have distinct
directional ports and paths on the two sides while sharing its meaning, vector,
and vault:

```text
input path -> concept identity + vault <- output path
```

The input trunks are based on causal event metadata, not guessed prose:

- `HEAR`: an immediate message or conversational input;
- `SEE`: an immediate, correlated observation or tool return;
- `NOTICE`: a delayed result, notification, or uncorrelated observation.

The output trunks are basal classes of external effect:

- `SPEAK`: communicate externally;
- `LOOK`: acquire information without changing external state;
- `DO`: execute or mutate external state.

Private model output can remain internal and activate no output trunk.

## Semantic surface and Y traversal

The surface uses vector and lexical overlap to nominate crown endpoints. It does
not decide the internal route. For each admitted endpoint, the Y cipher searches
from `SELF` through the relevant directional graph.

For edge `e` leaving node `v`:

```text
local_probability(e | v) = weight(e) / sum(weight(outgoing(v)))

travel_time(e) = delta_y(e) / (epsilon + local_probability(e | v))
                 + conflict_penalty(e)

path_time(path) = sum(travel_time(e) for e in path)
```

The winning path therefore depends on structural depth and learned familiarity,
not only hop count or surface cosine. Semantic score admits and disambiguates
endpoints; it never rewrites Y-edge travel time.

Associative expansion begins at nodes that the winning Y paths actually visited.
This makes graph retrieval dependent on learned routes instead of merely taking
more nearest neighbors from the language surface.

## Conserved fluid weights

Edges store log-strength rather than an accumulating authority score:

```text
effective_logit(e, t) = log_strength(e)
                        + fast_recency(e, t)
                        - conflict_penalty(e)

global_weight(e, t) = softmax(effective_logit(all live edges) / temperature)
```

All live global weights sum to `1.0`. Each outgoing frontier is normalized again
to `1.0` for the local decision available at that node. Increasing one route
therefore reduces competitors rather than creating unlimited confidence.

Recency is deliberately fast and temporary. Durable strength changes only after
a verified outcome. A claimed action cannot reinforce itself, and any verified
external outcome must carry a receipt identifier.

Graph familiarity expresses subjective routing relevance. It is never used as a
truth score for a memory record.

## Canonical memory and retrieval

SQLite is the single authority. Canonical record text, timestamp, source,
provenance, embedding, type, and metadata are immutable. A correction creates a
new record that supersedes the old record; it does not overwrite history.

Every recall pulse runs two independent lanes:

```text
query
  +-- global direct dense top 3       factual safety rail
  `-- semantic endpoints
        -> weighted Y paths
        -> visited-path expansion
        -> selected vaults
        -> dense + BM25 retrieval
```

The lanes meet only by canonical record ID. Graph candidates cannot evict the
direct safety rail. Exact record text is packed into context without paraphrasing,
so dates, numbers, names, paths, and negations survive retrieval.

Working memory retains recently injected record IDs under a bounded budget. A
new injection can displace older conversational material while preserving still
relevant evidence; it does not duplicate that evidence into a second authority.

## Multi-resolution experience memory

Every canonical record has an `experience_id`. For ordinary ingestion this is
the event ID; a conversational turn deliberately shares one ID across its inbound
message, outbound response, and delivery receipt.

The exact text and 1024D embedding remain stored once in the canonical record.
Lower vaults contain record references plus compact projections:

```text
layer 0  SELF             activation, preference, confidence, pulse
layer 1  stimulus trunk   activation, preference, confidence, pulse
layer 2  preference band  activation, preference, confidence, pulse
layer 3  emergent child   activation, preference, confidence, pulse
layer 4  semantic port    canonical record IDs, language, vector projection
```

The lower `experience_projections` table has no natural-language field. Each
projection stores the shared experience ID, canonical record ID, node, layer,
side, activation, preference, confidence, pulse, and structural metadata.

An experience can receive multiple stability or preference observations over
time. The store keeps their confidence-weighted mean and immediately updates all
lower projections carrying that experience ID. Thus later verified outcomes can
change how the same turn is remembered without rewriting its immutable language.

`SELF`, every basal trunk, every preference node, and every emergent child owns a
lower vault. Vault frequency and preference statistics are derived from the
projection ledger, so they survive restarts without storing duplicate prose.

## Evidence-backed growth

Every input experience is first deposited through `SELF`, its causal stimulus
trunk, and one `STABLE`, `NEUTRAL`, or `UNSTABLE` lower preference vault. A novel
experience starts an overlap cluster inside that parent vault. Later experiences
join only when their canonical embeddings exceed the overlap threshold and their
remembered preferences remain compatible.

Promotion requires distinct experience IDs. Its evidence threshold grows
logarithmically with the size of the parent vault, with a configurable minimum:

```text
required_support = max(base_support, ceil(log2(parent_experiences + 1)))
```

This allows early learning without letting a mature, busy vault turn every pair
of coincidences into a permanent branch.

Promotion creates two linked nodes rather than jumping directly into language:

```text
lower preference parent
  -> unlabeled child with zero semantic vector and a numeric lower vault
      -> crown semantic port with the evidence centroid and language vault
```

The shared supporting record IDs are the bridge. The child is justified by
overlap within the lower vault; its surface location and provisional terms are
derived afterward from those exact records. Semantic similarity therefore cannot
manufacture lower ancestry. Once promoted, later matching traversals continue to
grow the child vault and overlap cluster.

Potential duplicate branches should eventually be joined by reversible bridges
before any destructive merge. Destructive merging is not implemented in `0.2.0`;
canonical evidence must never be merged merely because two vectors are close.

## Structural mini-maps and the Layer 4 membrane

Two structures sit above the crown and below language.

A **Layer 3 structural mini-map** is a concept's local neighbourhood recorded as typed
relations and coactivation counts. `compute_structural_overlay(concept, store_or_graph,
dimension)` folds that neighbourhood into one deterministic L2 unit vector. The overlay is a
function of topology alone: same graph shape, same vector, regardless of what text created it.

The **Layer 4 membrane** is the global softmax over live edge logits. It is the same conserved
mass described above, read as a distribution rather than as individual weights: which routes
are currently admitted, and with what share. Ingress stimuli reweight it; traversal reads it.

Together they give the substrate two readable surfaces — structure (what is near what) and
admission (what is currently open) — without either surface holding natural-language payload.

A mini-map records both halves of the bicone: the preference node that promoted a concept and
the effector trunk mirrored onto it, with relations tagged `direction="input"` or `"output"`.
Recording one half only would leave the other unreadable, so every wiring step folds its own
relations back into the map. This matters measurably: with maps populated, a fitted projector
predicts a concept's vocabulary direction at 0.25 cosine from *position alone*, with the
concept's own vector zeroed out — support that a never-lexicalized concept can inherit from the
pathways below it.

## Experimental: the continuous soft-input seam

On `experimental/gguf-adapter` the substrate is coupled to a frozen local transformer through a
vector-only boundary. See `GGUF_EXPERIMENTAL_ADAPTER.md` for the empirical write-up.

A turn compiles to a `.packet` file in one of three modes:

- `lexical_membrane`: up to 8 rows of 1024D — concept centroid, Layer 3 overlay, the dominant
  preference-node vector, then membrane fibers;
- `opaque_topological`: 4 rows encoding input, edge, temporal and output state;
- `soft_basis`: named basis slots with bounded activations, resolved to token-embedding anchors
  by the native runner;
- `projected`: a single row predicted by a fitted graph-to-embedding map (see below).

The invariant across all three: **no user text, memory string, or persona token may appear in
the packet or in the model's context.** `verify_zero_prompt_leakage()` enforces it
schema-aware — validating packet grammar and float finiteness, rejecting protocol header
injection, and scanning for input words while whitelisting schema keywords so that a stimulus
containing the word "packet" is not mistaken for a leak.

### Preference valence readout

The substrate can learn a stance and be unable to say it. The valence slots close that gap:

```text
experience states (preference_mean x preference_weight, per source)
        +  PREF:*:STABLE / PREF:*:UNSTABLE edge statistics
        ->  valence in [-1, 1]
        ->  affinity | caution   (+ a tone companion: warm | uncertain)
        ->  withhold, when membrane conflict penalty exceeds 0.5 under negative valence
```

`preference_valence_activations(mind, source_id=...)` returns those activations plus
diagnostics. Every input is structural: persisted preference state and edge statistics. No
stimulus text participates, so an expressed stance is a property of habitual memory rather than
of the sentence that triggered it. `withhold` is how self-preservation reaches language —
sustained conflict penalty steers output toward declining rather than complying.

The C++ `BASIS` table in `native/graph_soft_generator.cpp` is the authoritative anchor map;
`RESERVED_BASIS_SLOTS` in `live_evaluator.py` must stay in sync with it, and the test suite
imports that set rather than duplicating it.

### Fitted projector

The codebook is authored: each slot averages three hand-picked token-embedding anchors. A fitted
alternative learns the map from the mind's own records — `projector.py` regresses structural
state features onto the model's embedding of the text each record deposited, closed-form ridge,
no training loop. On held-out states it aligns roughly three times better than the codebook
(cosine 0.43 vs 0.14). It is selectable as `packet_mode="projected"`.

Two target granularities exist. Against pooled record text the fit improves the representation but
not the generated language, because pooling blurs the target. Against **per-concept discriminative
vocabulary** — each concept's words scored by tf-idf over the concept corpus, with curriculum
template vocabulary dropped — a state decodes back through the model's vocabulary projection to
its own words for 91% of lexical concepts. Concepts stored with a zero embedding, which the
architecture requires of opaque children, have no lexical direction and decode to nothing. Both facts are recorded in
`GGUF_EXPERIMENTAL_ADAPTER.md`; neither changes any invariant, since the emitted rows are floats
calibrated to the same embedding-norm shell as every other packet.

### Closed-loop recirculation

An outbound activation trace is deposited as an `OUTBOUND_MESSAGE` record and re-enters the
next inbound pulse as a `THOUGHT` record with `source_id="self:thought"`. Ingress at the
membrane, traversal from `SELF` outward, then the trace folded back into the following pulse —
the loop continues without a human turn between iterations.

## Runtime flow

```text
typed event
  -> immutable canonical record
  -> HEAR / SEE / NOTICE
  -> semantic endpoint nomination
  -> input Y traversal
  -> direct top 3 + path-selected vault retrieval
  -> bounded first-person context
  -> external model (optional)
  -> private / SPEAK / LOOK / DO classification
  -> authority gateway (outside this package)
  -> observed receipt or result
  -> verified relative reinforcement
```

The package stops at classification. It never treats generated prose as execution.
An integrating harness must authorize a proposal, execute it, read back the
result, and return a receipt before durable action learning can occur.

## Gestation and hatching

The optional nursery adapter begins from the same minimal seed topology rather
than installing a manufactured biography or skill catalog. Gestation adds:

- one self-identity concept and immutable name record;
- one familiar-human concept and immutable relationship record;
- one small taste branch;
- gentle relative output priors associated with that taste;
- a persistent model/backend profile.

The identity records are the only pinned core memories. A taste statement lives
in an ordinary vault and the taste's edge priors remain subject to the same global
and local normalization as every later edge. The preset can therefore influence
early exploration without becoming a permanent personality command.

The hatch shell uses the replaceable `ChatModel` protocol. Its included Ollama
adapter sends the recalled first-person memory, a bounded selection of persisted
dialogue, and the current message to a local chat model. There is no separate
identity prompt. The model sees the agent's name through its own pinned identity
record.

Incoming and outgoing messages become immutable records. Repeated novel inputs
can begin forming evidence-backed branches immediately. A terminal reply is
reinforced only after the shell prints it and writes a canonical delivery receipt.
This receipt verifies delivery, not the truth or quality of the reply.

## Persisted state

The database contains:

- immutable canonical records and supersession links;
- shared crown concepts and their vectors;
- directional input and output edges;
- edge-to-record evidence links;
- vault membership by canonical ID;
- confidence-weighted experience preference state;
- language-free projections in lower node vaults;
- persistent overlap clusters and their child/semantic ports;
- traversal traces and outcome packets;
- embedding-space identity and the pulse counter.

The default runtime database is `agentic_memory.sqlite` in the current
workspace. Passing `:memory:` is an explicit opt-in for tests and disposable
experiments; it is never the durable runtime default.

The included deterministic hash embedder is an offline test adapter. A production
embedder must implement `Embedder`, preserve a stable `space_id`, and use the same
dimension for both records and concepts. Opening an existing mind with a different
space or dimension fails rather than silently corrupting retrieval.

## Required invariants

1. One `SELF` origin exists.
2. Its input frontier is exactly `HEAR`, `SEE`, and `NOTICE`.
3. Its output frontier is exactly `SPEAK`, `LOOK`, and `DO`.
4. Input and output paths are directional but share crown concepts and vaults.
5. Global live edge mass sums to `1.0`.
6. Every non-empty local outgoing frontier sums to `1.0`.
7. Endpoint semantic score cannot alter Y travel time.
8. Multi-hop expansion starts from visited Y-path nodes.
9. Direct dense evidence cannot be evicted by graph retrieval.
10. Canonical records are immutable and corrections are explicit supersessions.
11. Unverified output cannot durably reinforce a path.
12. Persisted embedding identity cannot change silently.
13. Lower projections contain no natural-language payload.
14. A promoted child retains every canonical experience that justified it.
15. Opposing preference bands cannot collapse into the same overlap cluster.
16. A Layer 3 structural overlay is a function of topology alone and is L2 unit-norm.
17. No user text, memory string, or persona token may reach a `.packet` or the model context.
18. Only slots in `RESERVED_BASIS_SLOTS` may be emitted, with activations in `(0.0, 1.0]`.
19. Valence activations derive from preference state and edge statistics, never from stimulus text.

`GraphRuntime.validate_invariants()` checks the structural and conservation
invariants at runtime. The behavioral suite separately checks routing, evidence
preservation, supersession, persistence, growth, output classification, and the
receipt gate.

## Honest boundaries

The base does not yet provide:

- a production semantic embedding model or vector index;
- destructive branch merging or reversible alias-bridge management;
- automatic skill or tool discovery;
- tool execution or an authority policy;
- model adapters beyond the small local Ollama boundary;
- a trained upper-layer activation projector: the experimental seam maps activations onto
  token-embedding anchors, which yields a reliably valenced but not always fluent stance, and
  only `soft_basis` packets decode into consistently coherent language;
- affect, simulated qualia, or developmental claims. A valence slot is a measured property of
  stored preference state projected into a decoder, not a feeling.

Those are optional layers. None should be allowed to hide direct evidence, mutate
canonical history, bypass receipt verification, or turn a graph edge into a fact.
