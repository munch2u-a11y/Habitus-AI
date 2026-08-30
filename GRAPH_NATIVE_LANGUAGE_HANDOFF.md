# Graph-Native Language: Progress, Next Steps, and Test Plan

Date: 2026-08-29

This is the continuation artifact for the graph-native language and GGUF
adapter work. It records what is implemented, what the evidence currently
supports, what remains hypothetical, and how to continue without confusing a
small skeletal or accelerated mind with a mature agent.

## North-star goal

The long-term goal is an agent whose active cognitive state is the growing
graph itself. Memory, preferences, habits, concepts, language, and actions
should be different resolutions of the same evolving structure rather than a
collection of sidecars joined by prompts.

The desired live path is:

```text
stimulus
  -> input semantic nomination
  -> input Y traversal through the current mind
  -> activated relational concepts and current stability state
  -> output Y traversal
  -> learned semantic membrane
  -> graph-conditioned language/action adapter
  -> SPEAK, LOOK, DO, or private self-output
  -> observed outcome
  -> immediate relative edge recalibration
```

No retrieved prose should be required for ordinary cognition. Raw episodic
records may remain as an immutable sensory/provenance archive, but the live
language path should operate from the graph state those experiences produced.

## Architectural commitments

These are the current design invariants. A branch should not casually replace
them with a conventional prompt or RAG pipeline just to make a demonstration
look better.

### One center, two cones

- `SELF` begins at the shared center.
- The input cone begins with `HEAR`, `SEE`, and `NOTICE`.
- The output cone begins with `SPEAK`, `LOOK`, and `DO`.
- Input and output branches are distinct at lower levels and increasingly
  overlap as relational concepts become more abstract.
- They share one semantic membrane at the language boundary.

### Layer interpretation

The layer numbers are conceptual resolutions, not rigid physical coordinates:

1. `SELF` and stability versus instability.
2. Core stimulus/action trunks and nonverbal preference gradients.
3. Recursive relational concepts, patterns, habits, and skills formed from
   overlapping experience.
4. Learned word, sound, or symbol forms on the shared semantic membrane.

The intended Layer 3 payload is ultimately a relational graphlet plus its
derived dense signature—not a text summary stored for later prompt injection.

### X and Y remain separate

- X nominates the semantically relevant endpoint or endpoints.
- Y finds the least-resistant legal route to those fixed endpoints.
- An easier Y path must not silently replace X's intended endpoint.
- Multi-hop expansion should originate from the visited Y route.

That rule describes perception only. Production must deliberately reverse the
causal direction.

### Critical correction: input is X-led; output must be Y-led

The current experimental language pulse is still too symmetrical. It uses the
input embedding to nominate several crown concepts and then traces the output
cone back to those same concepts. That is useful for proving the adapter seam,
but it makes production partly an echo or reranking of the input.

The intended asymmetry is:

```text
INPUT
incoming membrane pattern (X)
  -> fixes perceptual endpoint candidates
  -> input Y resolves legal paths through the current mind
  -> those paths leave a transient internal activation pattern

CENTER
transient activation + durable habits + current stability/recency
  -> immediate softmax recalibration

OUTPUT
Y begins from the current internal state
  -> competing output trajectories are formed from live edge state
  -> the strongest trajectory chooses its own Layer 3 destination
  -> that destination reaches learned labels on the membrane (X)
  -> the winning root edge determines SPEAK, LOOK, or DO
```

No input cosine endpoint should be copied into the output cone. Input meaning
may attract the output trajectory through transient activation of shared
concepts, but it must not prescribe the terminal output concept.

This is the mechanism that can produce continuous internal focus:

- input activation changes the momentary internal field;
- recent paths gain temporary influence;
- established successful routes retain durable log-strength;
- competing branches remain relative under softmax;
- the emerging output path further changes recency;
- private output can return as an attenuated self-originated stimulus;
- the next pulse therefore begins from a slightly changed mind.

#### Conserved-flow correction

The earlier graph computed one flat edge softmax and then renormalized each
source for traversal. That redundant global denominator canceled locally and
allowed unrelated graph growth to dilute diagnostic edge mass. The core now
softmaxes only genuine outgoing siblings and propagates one bounded mass budget
from `SELF`. Root trunks compete globally, descendants compete regionally, and
unrelated branches remain unchanged unless they share an ancestor gate.

Outbound selection therefore needs an explicit trajectory competition rather
than another endpoint-constrained Dijkstra call:

1. Begin at `SELF` with the final post-input edge snapshot.
2. Enumerate a bounded, acyclic beam of legal output paths to productive Layer
   3 terminals. Do not supply a semantic target.
3. Score each full path from its edge softmax probabilities, Y distance,
   conflict penalties, durable stability, and transient activation of the
   nodes it crosses.
4. Apply a softmax across complete candidate trajectories so their total focus
   is `1.0`.
5. Select or softly blend the leading path or paths.
6. Mark the selected output route active and perform the final edge
   recalibration.
7. Let the terminal graphlets activate their learned membrane labels.

A suitable initial path score is conceptually:

```text
path_score =
    sum(log(local_edge_probability))
  - distance_penalty
  - conflict_penalty
  + transient_internal_activation
  + durable_stability_bias
```

The exact coefficients should remain experimental. All terms must be bounded,
and candidate path scores must be normalized together. Using a complete-path
softmax prevents one high-weight edge from being mistaken for a coherent
thought trajectory.

The transient activation field is not durable learning. It should decay
quickly. Only verified outcomes alter durable habit logits. This preserves
micro-adaptation without allowing internally generated loops to permanently
train themselves.

### Second correction: one conceptual crown, several interface membranes

The outer surface should not be treated as one universal language membrane.
That forces `SPEAK`, `LOOK`, and `DO` to become word-generation problems even
when their natural outputs are nonverbal.

The better geometry is a shared relational crown with several partially
overlapping interface regions:

```text
                         communication membrane
                         HEAR <-> SPEAK
                                |
                                |
navigation/observation ---- shared Layer 3 ---- action/ability membrane
      SEE <-> LOOK          graphlets          DO <-> receipt/error
                                |
                                |
                       NOTICE / delayed outcomes
```

These are not separate minds. They are different surfaces reached from the
same relational concepts:

- The communication membrane contains learned linguistic or symbolic forms.
- The navigation/observation membrane contains resource locations, views,
  object handles, search/open/read affordances, and returned observations.
- The action/ability membrane contains tool identities, structured argument
  roles, execution affordances, receipts, and error states.
- `NOTICE` carries delayed or asynchronous changes back toward the relevant
  concepts without requiring immediate verbalization.

A concept may connect to any subset of these membranes. There should be no
requirement that every action, observation, receipt, or error acquire a word
representation before it can affect behavior.

For example:

```text
heard request
  -> communication membrane
  -> shared goal graphlet
  -> output Y trajectory selects DO
  -> action membrane emits tool identity + structured arguments
  -> tool executes without an intermediate natural-language tool call
  -> receipt enters the action/outcome surface
  -> related concept and stability paths update
  -> an independent SPEAK trajectory may later verbalize the result
```

Likewise, `LOOK` can move through a workspace or read an object without first
constructing a sentence saying that it intends to look. The returned content
enters through `SEE`; language is activated only if the mind subsequently needs
to communicate or internally verbalize what was observed.

#### Hierarchical conserved softmax

Separate membranes should not mean unconstrained independent weights. A
hierarchical distribution retains the global `1.0` budget while preventing
unrelated modalities from rewriting each other's internal habits.

For output membrane `m` and one of its edges `e`:

```text
trunk_gate[m] = softmax(current trunk energies)
within_membrane[m, e] = softmax(edge energies inside membrane m)
effective_mass[e] = trunk_gate[m] * within_membrane[m, e]

sum(trunk_gate) = 1.0
sum(within_membrane[m, *]) = 1.0 for each active membrane
sum(effective_mass across all output edges) = 1.0
```

This gives two distinct kinds of competition:

- Momentary focus competes across `SPEAK`, `LOOK`, and `DO` through the trunk
  gates.
- Durable speech habits compete with other speech habits, tool habits with
  other tool habits, and navigation habits with other navigation habits.

Learning a better tool invocation therefore redistributes weight primarily
inside the action membrane. It does not directly weaken unrelated vocabulary
fibers. Cross-modal influence occurs through shared concept activation and the
momentary trunk gates, where it belongs.

The gates need not impose exactly one action. A bounded top-k output can permit
`DO` plus `SPEAK`, or `LOOK` followed by `DO`, while retaining a conserved
attention budget. Each selected membrane receives its own native packet and
adapter; one membrane's surface representation must never be smuggled through
another membrane as a fake language sequence.

### Conserved, live edge state

- The current implementation computes a softmax independently over every
  non-empty outgoing sibling set.
- Each directional phase propagates mass `1.0` outward from `SELF`; the combined
  diagnostic view assigns `0.5` to input and `0.5` to output.
- Root-region mass sums to `1.0`, each successive layer can only preserve or
  absorb mass, and terminal plus depth-truncated mass accounts for the full
  starting budget.
- Persistent logits, conflict penalties, and recency change the distribution;
  normalized weights are derived state rather than stale stored values.
- Every activation or reinforcement stage must be followed by a fresh snapshot
  before another traversal or adapter frame uses the graph.
- A successful path gains relative mass against actual siblings and changes
  downstream regional flow. Unrelated paths do not move merely because the
  graph grew elsewhere.
- Mere self-activation is not verification. Stability reinforcement requires
  an environmental signal or a receipt-backed outcome.

This inspectable, continuously redistributed state is the important
"open-weight-like" property. It does not mean the frozen GGUF model weights are
being edited on every pulse.

### Language is a learned boundary

- A word is a learned surface label attached to an existing relational state.
- The same word may connect to multiple concepts; the active graph context
  determines which route is preferred.
- Exact label geometry and the wider high-dimensional graph field should work
  together.
- If a GGUF remains the speech organ, it still emits model tokens internally.
  What disappears is the need to serialize the mind as a natural-language
  prompt.

### Output gating

- Language can be generated without automatically being externalized.
- The strongest current root output gate decides the destination.
- `SPEAK` makes the language externally visible.
- `LOOK` or `DO` leaves language private/self-originated while the relevant
  action branch proceeds.
- Private output must never be reinforced as externally verified fact merely
  because the system generated it.

## What is implemented now

### Base graph and memory substrate

`src/habitus_ai/graph.py` currently provides:

- the centered bicone topology;
- three input and three output trunks;
- globally conserved softmax weights;
- recency-sensitive Dijkstra-style Y traversal;
- endpoint-preserving X/Y separation;
- stability reinforcement and conflict penalties;
- lower preference vaults;
- overlap-based child and semantic-port growth;
- recursive path and conservation invariants.

The base package still contains conventional memory retrieval and rendered
context support. That remains useful as a control and compatibility path, but
it is not the target graph-native language path.

### Developmental experiments

`experiments/graph_native_live/` contains several increasingly strong seams:

- `opaque_skeleton.py`: arbitrary opaque graph directions reach the frozen
  transformer. It proves transport, not grounding.
- `nursery.py`: separately taught labels compose through learned graph fibers.
- `reverse_nursery.py`: graph states project back through the model vocabulary
  without storing token IDs as graph payload.
- `accelerated_gestation.py`: builds a persistent, broader developmental
  fixture through controlled replay and overlap growth.
- `transformer_hatch.py`: learned membrane rows enter the frozen transformer
  without user or memory text.
- `latent_language_pulse.py`: combines the current whole-mind field, input and
  output Y routes, activated Layer 3 concepts, learned membrane geometry,
  dynamic output gating, and post-feedback recalibration.

### Native boundary

`native/graph_soft_generator.cpp` accepts native-width floating-point rows
through `llama_batch.embd`. It adds only fixed empty-chat role delimiters. The
response model receives no user-message tokens and no retrieved memory text.

This is input-embedding guidance. It is not yet an upper-layer adapter, prefix
KV injection, or trained residual-stream projector.

### Current developmental snapshot

The snapshot used for the latest controlled trial was:

```text
accelerated_gestation_runs/habitus-1787966680339559785.sqlite
```

At inspection time it contained:

```text
46 crown concepts
43 lower child nodes
171 lexeme geometry nodes
1,379 edges
pulse 494
```

This is an accelerated developmental fixture—not a fully formed or broadly
educated mind.

## Evidence ledger

### Established

- A frozen local GGUF can consume graph-produced 1024D rows without receiving
  user or RAG text.
- Separately learned label fibers can be projected back into model vocabulary
  geometry.
- Learned membrane sequences produce topic-directed language for a narrow
  controlled curriculum.
- The contextual graph/membrane overlay can alter the transformer response.
- The random opaque control is substantially less related to the selected
  concepts than the learned conditions.
- Traversal recency and verified reinforcement redistribute edge mass in the
  same live pulse while total global mass remains exactly `1.0`.
- Dynamic action-gate selection distinguishes external `SPEAK` output from
  private `LOOK`/`DO` output.
- Endpoint nomination now excludes lexeme nodes; membrane transitions cannot
  masquerade as Layer 3 concepts.

### Latest four-domain result

The comparison held the gestated database, Qwen3 0.6B Q8 model, seed 42,
48-token limit, and native envelope constant. Each condition began from its own
copy of the same frozen mind.

| Condition | Mean response similarity to selected concept |
| --- | ---: |
| contextual graph/membrane overlay | 0.473 |
| membrane labels only | 0.461 |
| reversed contextual rows | 0.461 |
| graph fields inserted as separate rows | 0.342 |
| graph structure only | 0.343 |
| unrelated opaque rows | 0.210 |

Trust, fear, and evidence produced useful topic-directed language. Music still
produced an unhelpful clarification response. The overlay's gain over
membrane-only is small and preliminary.

One verified positive trust outcome changed the live root gates as follows:

```text
SPEAK  0.5134 -> 0.5248
LOOK   0.2627 -> 0.2566
DO     0.2239 -> 0.2186
root flow mass 1.0 -> 1.0
```

Every credited output edge increased and competing root mass decreased. Deeper
unrelated regions are now isolated by their local sibling partitions.

### Not established

- A mature graph-native mind has not been built or tested.
- The current system has not learned broad language naturally from infancy.
- The contextual overlay has not demonstrated reliable grammar or word order.
- The graph has not demonstrated arbitrary factual recall without RAG.
- The response model has not been conditioned in an upper transformer layer.
- No current result supports calling this a RAG replacement or an AGI.
- Coherent text by itself is not evidence that the correct graph relation
  caused the response.

The reversed-row control remains almost as strong as the ordered condition.
Until ordered rows reliably beat reversed rows on held-out relational
composition, sentence structure is an open problem.

## Important implementation limitations

1. Current crown concepts still carry embeddings and text-oriented vaults from
   the earlier memory architecture. They are not yet recursively stored local
   graphlets.
2. Accelerated gestation uses the GGUF tokenizer and mean token embeddings to
   create the current semantic geometry. The graph-native runtime avoids prompt
   text, but development is not tokenizer-free today.
3. X nomination uses a native semantic embedding of the incoming text. That
   vector selects concepts but is not sent to the response transformer.
4. The current 1024D whole-mind row is a weighted projection of non-lexical
   nodes. It may become diffuse as the graph grows and needs scaling tests.
5. The contextual-overlay coefficients are fixed prototype calibration values,
   not learned developmental parameters.
6. The adapter supports four membrane rows in the current bounded experiment.
7. The live output gate currently marks output as external or internal; it does
   not yet feed private language back through the input cone on a later pulse.
8. Output feedback is explicit and receipt-backed, but cross-turn credit
   assignment is not yet a complete live-agent loop.
9. The accelerated curriculum supplies categories and label exposures. Its
   success cannot be described as unsupervised language emergence.
10. The 0.6B model is useful for structural tests but can refuse or misread
    sparse latent sequences even when their topic is recoverable.
11. `latent_language_pulse.py` currently sends the X-nominated input concepts
    through both cones. It has not yet implemented target-free, Y-driven
    outbound trajectory selection.
12. Conserved flow supplies hierarchical regional mass, while target-free
    output still needs complete-path competition plus transient shared-node
    activation to choose a coherent terminal rather than one locally strong edge.
13. The current graph-native GGUF experiment treats every selected output as
    language that is either external or private. It does not yet have separate
    communication, navigation, and action membranes or membrane-specific
    adapters.
14. Current root-gate selection chooses one winning output trunk. It has not yet
    implemented bounded multi-channel output such as acting while separately
    explaining the action.

## Recommended development branches

The branches below are separable, but their merge order matters.

### Branch 0: Y-driven outbound focus

Goal: replace symmetric input/output endpoint tracing with a genuinely
generative output cone.

Work:

- Add a transient activation field keyed by shared concept ID and pulse.
- Populate it from input Y traces, prior private output, and current stability.
- Decay it rapidly without writing it into durable edge strength.
- Add target-free bounded output path enumeration from `SELF`.
- Score complete paths using current edge probabilities and transient internal
  activation.
- Softmax the complete candidate trajectories to a total focus of `1.0`.
- Select the output trunk and terminal concept from that Y competition.
- Recalibrate edge weights again after the winning route becomes active.
- Only then resolve the terminal graphlets through the membrane.
- Preserve the existing X-fixed traversal for input and ordinary directed
  recall; do not replace it globally.
- Introduce explicit communication, navigation/observation, and action/ability
  membrane identities.
- Replace one flat output distribution with hierarchical trunk-gate and
  within-membrane softmax distributions.
- Keep the product of those distributions globally conserved at `1.0`.
- Produce separate output packets for each activated membrane.
- Allow bounded top-k membrane activation so compatible actions can coexist
  without merging their surface representations.
- Route tool receipts and errors back through typed outcome/observation paths,
  not through generated prose.

This should begin as a contained experiment beside `latent_language_pulse.py`.
It should not change the core traversal until its causal controls pass.

Required controls:

- Same input X nomination, different output habit logits: output Y should
  change.
- Same output logits, different transient internal activation: relevant output
  paths should shift without becoming fixed to the input endpoint.
- Same internal activation, shuffled output edges: trajectory should change.
- Strong unrelated habit versus current relevant activation: neither may
  dominate every pulse.
- Remove the external stimulus and observe focus decay across private pulses.
- Verify candidate trajectory mass and root gate mass equal `1.0`; verify every
  propagated frontier is non-increasing and terminal plus truncated mass equals
  `1.0`.
- Confirm the chosen output terminal is not simply the highest input cosine
  endpoint.
- Reinforcing a tool path changes action-membrane probabilities without
  materially changing within-language probabilities.
- Reinforcing a phrase changes communication-membrane probabilities without
  materially changing tool selection.
- `DO` can produce a structured action with no language generation.
- `LOOK` can produce navigation and a returned observation with no external
  speech.
- `SPEAK` can describe a tool without executing it.
- A combined request can activate `DO` and `SPEAK` as two separately receipted
  outputs rather than one mixed packet.

### Branch A: frozen mature-mind fixture

Goal: create a broad enough mind that behavioral negatives are not artifacts
of missing concepts or missing label fibers.

Work:

- Extend deterministic gestation and nursery replay across identity, people,
  objects, places, time, causality, preference, uncertainty, social relations,
  observation, communication, and basic digital actions.
- Teach labels independently before teaching multi-word constructions.
- Include positive, neutral, and bounded negative outcomes.
- Include repeated experiences with different outcomes so concepts do not
  collapse into one affective value.
- Include several shared surface forms and ambiguous names.
- Allow recursive overlap growth rather than directly writing test concepts.
- Freeze milestone databases with checksums and manifests.
- Keep training experiences and evaluation scenarios strictly separate.

Suggested milestones:

1. Gestated trunks and balanced lower preferences.
2. Stable single-label recognition and production.
3. Two-concept relations and short ordered constructions.
4. Ambiguity resolution and contextual correction.
5. Multi-level relational graphlets and cross-cone action habits.
6. Frozen broad fixture ready for adapter evaluation.

Node count alone is not a maturity criterion. Coverage, recursive depth,
cross-cone reachability, ambiguity, and held-out composition matter more.

### Branch B: true Layer 3 graphlets

Goal: make relational structure—not stored prose—the authoritative concept
payload.

Work:

- Add a graphlet representation containing member nodes, directed relations,
  role slots, temporal relations, accumulated stability statistics, and
  provenance references.
- Derive each graphlet's 1024D signature from its members and relations.
- Keep raw episode text outside the active graphlet payload.
- Use the existing relative overlap/growth kernel for recursive parent
  formation at every higher conceptual level.
- Use the same statistics for merge, split, and decay decisions rather than
  introducing a different subsystem per level.
- Preserve evidence references for inspection without rendering them into the
  live adapter input.

Required controls:

- Same words, different graph relation.
- Same graph relation, substituted labels.
- Shuffled member identities.
- Reversed edge direction.
- Parent removed while children remain.
- Dense signature removed while explicit structure remains, and vice versa.

### Branch C: learned graph-to-GGUF adapter

Goal: translate a mature activation frame into the frozen model's language
space without hand-calibrated vector mixing.

Work:

- Preserve `ActivationFrame` as the canonical boundary object.
- Begin with a small projector over input embeddings while keeping the GGUF
  frozen.
- Train on nursery graph states paired with caregiver-approved utterances.
- Hold complete relational combinations out of training.
- Compare a projected sequence, prefix-KV injection, and selected upper-layer
  residual injection only after the input-embedding baseline is stable.
- Train the adapter, not the underlying mind, against language loss.
- Prevent the adapter from learning a shortcut from IDs, sequence numbers, or
  stored test sentences.

The adapter succeeds only if it verbalizes novel combinations of previously
learned graph relations. Reproducing memorized training phrases is insufficient.

The GGUF language adapter belongs only to the communication membrane. The
action and navigation membranes should initially use deterministic structured
adapters whose fields are learned graph bindings. A later specialized model may
assist with arguments or planning, but it should not turn every nonverbal act
back into a language prompt.

### Branch D: continuous live pulse

Goal: join learning, graph state, generation, output gating, and feedback in one
real agent turn.

Work:

- Apply pending verified feedback before the next traversal.
- Ingest the new stimulus into lower nonverbal state without creating a RAG
  prompt.
- Nominate several overlapping crown concepts.
- Activate input paths and immediately recalibrate.
- Resolve output paths and immediately perform the final recalibration.
- Build the adapter frame from that exact snapshot.
- Route generated output according to the strongest current action gate.
- Tag internal language as `self-originated` and attenuate it before returning
  it as a later stimulus.
- Store the output/action association and wait for real outcome evidence before
  reinforcement.
- Add tools only after this path works; tools should grow as learned action
  branches rather than a static prompt catalog.

### Branch E: causal evaluation harness

Goal: distinguish graph-carried meaning from fluent coincidence.

Every experiment should clone one frozen mind per condition and hold model,
sampler, seed, maximum tokens, query, and structural envelope constant.

Minimum conditions:

1. Correct graph plus correct membrane.
2. Correct graph without membrane labels.
3. Membrane labels without graph conditioning.
4. Correct graph plus unrelated membrane.
5. Unrelated graph plus correct membrane.
6. Reversed route and word order.
7. Shuffled graphlet members.
8. Preference-sign inversion.
9. Equal-shaped random opaque rows.
10. Ordinary natural-language model baseline.

## Required test families

### Structural invariants

- Global edge mass equals `1.0` within `1e-12` after every mutation stage.
- Every local outgoing distribution equals `1.0`.
- Frame snapshot digest equals an immediate read-back at the same pulse time.
- All frame edge weights come from the final recalibration.
- X-selected endpoints remain fixed while Y route resistance changes.
- Every activated endpoint is legally reachable through both cones.
- Lexeme nodes can never be nominated as Layer 3 concepts.
- Restarting the mind preserves topology, logits, graphlets, membrane fibers,
  and embedding-space identity.

### Boundary tests

- User text absent from the native packet.
- Query embedding absent from the native packet.
- Retrieved record text absent from the native packet.
- Node labels and token IDs absent from geometry-only nodes.
- Only fixed role delimiters enter as ordinary native tokens.
- Packet width exactly matches the model's native input width.
- Malformed, zero, non-finite, oversized, and trailing packet data fail closed.

### Developmental tests

- A label heard independently becomes receptive before it becomes productive.
- Repeated caregiver approval strengthens the correct productive fiber.
- Unrewarded babble does not become a stable label.
- Separately learned labels compose without seeing the full phrase.
- Incorrect label binding remains distinguishable from the proper curriculum.
- New verified experience can redirect a habit.
- An unverified novelty fades relative to a long-established path.
- Recursive overlap growth forms higher concepts without a layer-specific
  formation script.

### Language and relational tests

- Proper-name identity: `Joshua` and `Josh` refer to self when context supports
  it.
- Name ambiguity: another person named Josh does not always activate self.
- Historical context: a historical Joshua resolves away from both current
  people.
- Polysemy: one surface word routes to different graphlets by context.
- Negation: `likes` and `does not like` remain distinct.
- Temporal order: past, current, and expected future relations remain distinct.
- Role reversal: `Josh helps Alex` differs from `Alex helps Josh`.
- Held-out composition: known concepts in an unseen relationship verbalize
  correctly.
- Same-label/different-graph pairs produce different outputs.
- Same-graph/substituted-label pairs preserve the relation while changing the
  surface form.

### Action and gating tests

- A conversational question with an available answer raises `SPEAK` above
  `LOOK` and `DO`.
- An unresolved factual uncertainty raises `LOOK` and keeps generated language
  private.
- A learned executable intention raises `DO`.
- Switching only the live edge state can change the winning action gate.
- Private output never appears on an external transport.
- Private output does not self-verify.
- A receipt-backed successful action reinforces only credited paths.
- Failed action feedback lowers credited paths while preserving global mass.
- Output terminal selection works with no X endpoint argument.
- Competing complete output trajectories normalize to `1.0`.
- The winning trajectory can differ from the highest input-cosine concept.
- Altering only output habit weights can redirect the next generated thought.
- Altering only transient shared-node activation can redirect focus without
  permanently changing habit logits.
- Repeated private pulses exhibit bounded focus continuity followed by decay,
  rather than a permanent self-reinforcing loop.
- Within-membrane distributions each conserve `1.0`.
- Trunk-gate probabilities conserve `1.0`.
- Effective output edge mass conserves `1.0` after multiplying both levels.
- Speech learning leaves the normalized action-membrane distribution stable.
- Tool learning leaves the normalized communication-membrane distribution
  stable.
- A tool receipt can reinforce `DO` without adding a language-memory record.
- An execution error can suppress the failed action path without suppressing
  the words used to discuss that action.
- Describing an ability does not execute it.
- Executing an ability does not require the response GGUF to emit its schema.

### Longitudinal plasticity tests

- Learn a new preference, repeat it, and observe a new stable route.
- Stop validating it and measure recency decay.
- Reintroduce the old condition and test whether durable history can recover.
- Teach a correction and verify suppression rather than deletion of the older
  route.
- Confirm that repeated focus does not permanently starve unrelated branches.
- Track split/merge oscillation and require hysteresis if cycling appears.

## Metrics and claim gates

Keep the following claims separate:

| Claim | Current status | Required next evidence |
| --- | --- | --- |
| continuous graph rows affect generation | passed | retain regression |
| learned labels condition topic | narrow pass | broad mature fixture |
| graph structure carries additional causal value | preliminary | consistent margin across seeds and controls |
| Y/softmax state changes behavior immediately | structural pass | longitudinal live-agent trial |
| output is selected by internal Y trajectory | controlled pass | longitudinal live-agent trial |
| nonverbal actions use separate membranes | structural pass | receipt-backed real abilities |
| graph learns word order | not passed | ordered beats reversed on held-out relations |
| graph supports compositional language | not passed | unseen relation combinations |
| mature mind answers consistently without RAG | not tested | frozen mature-mind evaluation |
| graph-native tools form stable skills | not tested in this adapter | receipt-backed action curriculum |
| architecture replaces RAG | unsupported | broad factual and agentic evidence |

Recommended quantitative gates:

- Run at least three seeds per behavioral condition.
- Report mean, spread, and per-scenario results—not only an aggregate.
- Require the correct condition to beat random and unrelated controls.
- Require graph-plus-label to beat label-only before claiming graph benefit.
- Require ordered to beat reversed before claiming learned syntax.
- Score intended relations and action outcomes, not merely nonempty language.
- Preserve every packet, snapshot checksum, response, and evaluation decision.

## Stop rules

- If a negative comes from a concept absent from the test mind, classify it as
  missing coverage rather than architectural failure.
- If a positive disappears under unrelated-label or shuffled-graph controls,
  classify it as label or model prior behavior rather than graph understanding.
- If graph-plus-label does not beat label-only across several seeds, improve
  mind maturity or adapter alignment before adding architectural machinery.
- If reversed order remains equivalent, do not claim grammar.
- If the graph-only condition cannot beat equal-shaped random rows, do not claim
  the dense graph field is grounded.
- If exact test phrases or answer labels entered gestation, invalidate the
  corresponding held-out result.
- If a completion has no receipt or read-back, do not reinforce it as success.
- If a branch requires replacing the unified growth kernel with several
  task-specific rules, stop and re-evaluate the abstraction.

## Safe branch and merge practice

The writable working repository is:

```text
/home/nemo/fractal_memory/habitus-ai
```

The separate Antigravity audit copy inspected during this session is:

```text
/home/nemo/habitus-ai-experiments
```

The writable repository already contains a broad, uncommitted package rename
and other existing work. Do not run cleanup, reset, checkout-overwrite, or bulk
formatting operations. Before splitting branches:

1. Capture `git status --short`.
2. Snapshot or commit the intended baseline explicitly.
3. Give each branch its own database and run directory.
4. Never run a mutating pulse against the frozen reference database.
5. Merge only code whose causal controls and receipts survive independently.

## Resume commands

From the repository root:

```bash
cd /home/nemo/fractal_memory/habitus-ai
```

Run the focused structural tests:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:experiments/graph_native_live \
python3 -m pytest -q -p no:cacheprovider \
  tests/test_latent_language_pulse.py \
  tests/test_graph_and_learning.py \
  tests/test_opaque_graph_native.py
```

Run the complete current suite:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:experiments/graph_native_live \
python3 -m pytest -q -p no:cacheprovider
```

The current repository ends this pass with all 62 collected tests passing.

Run the target-free output regression directly:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:experiments/graph_native_live \
python3 -m pytest -q -p no:cacheprovider tests/test_outbound_focus.py
```

Run the frozen 36-topic routing ablation:

```bash
cp --reflink=auto \
  experiments/graph_native_live/accelerated_gestation_runs/habitus-1787966680339559785.sqlite \
  /tmp/habitus-outbound-ablation.sqlite

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:experiments/graph_native_live \
python3 experiments/graph_native_live/outbound_focus_ablation.py \
  --database /tmp/habitus-outbound-ablation.sqlite \
  --output /tmp/habitus-outbound-ablation.json
```

The corrected read-only run scored `32/36` top-one and `35/36` top-two against
the curriculum's intended membrane; the fan-out-sensitive control scored
`8/36` top-one. The source and evaluated copy produced the same logical SQLite
dump hash, `8f094cb37a24b2abf6fd9b15a5a45797ccf2862f20194efa5fd3f89f8d65562f`.

Sequential snapshot comparison:

| Developmental artifact | HEAR coverage | New top-1 | New top-2 | Old top-1 |
| --- | ---: | ---: | ---: | ---: |
| pre-language-schooling | 30/36 | 12/30 | 29/30 | 8/30 |
| 35 language-schooled concepts | 36/36 | 32/36 | 35/36 | 8/36 |
| plus 358 lexical transition edges | 36/36 | 32/36 | 35/36 | 8/36 |

The source/copy logical hashes also matched for the two earlier snapshots.
Treat this as a developmental progression, not a three-seed replication. It
suggests the language-schooling pass repaired input reachability and sharpened
the membrane decision, while later surface transition edges did not leak into
action routing.

Run a graph/membrane ablation from a disposable mind copy:

```bash
cp --reflink=auto \
  experiments/graph_native_live/accelerated_gestation_runs/habitus-1787966680339559785.sqlite \
  /tmp/habitus-language-trial.sqlite

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:experiments/graph_native_live \
python3 experiments/graph_native_live/latent_language_pulse.py \
  --database /tmp/habitus-language-trial.sqlite \
  --once "People consistently keep promises, making cooperation feel safe." \
  --ablations \
  --max-tokens 48 \
  --run-directory /tmp/habitus-language-trial-run
```

Run a verified-feedback pulse only against another disposable copy:

```bash
cp --reflink=auto \
  experiments/graph_native_live/accelerated_gestation_runs/habitus-1787966680339559785.sqlite \
  /tmp/habitus-feedback-trial.sqlite

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:experiments/graph_native_live \
python3 experiments/graph_native_live/latent_language_pulse.py \
  --database /tmp/habitus-feedback-trial.sqlite \
  --once "People consistently keep promises, making cooperation feel safe." \
  --output-feedback 1.0 \
  --feedback-receipt observed-success-001 \
  --run-directory /tmp/habitus-feedback-trial-run
```

## Recommended order when work resumes

1. Preserve the passing target-free prototype and its frozen routing ablation.
2. Build Branch A's broader mature-mind fixture without changing the adapter.
3. Repeat the Y-driven matrix across several graph-development seeds and report
   per-topic variance.
4. Diagnose the four X-nomination misses before changing output-gate math.
5. Connect one harmless LOOK affordance and one harmless DO ability through
   receipt-backed execution on disposable workspaces.
6. Verify that success and error outcomes change only the credited paths, then
   measure decay and habit reversal longitudinally.
7. Implement Layer 3 graphlets and repeat the same causal controls.
8. Train the smallest possible graph-to-language projector.
9. Require held-out composition and ordered-versus-reversed separation before
   calling the language membrane learned syntax.
10. Join the winning adapter to the continuous private/external pulse loop.

The output-direction correction is now a controlled pass, not an open design
item. The immediate priorities are robustness across independently developed
minds and receipt-backed nonverbal execution. Fluent language remains a
separate alignment problem: current routing success must not be reported as a
successful general conversational agent.
