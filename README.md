# Base Agentic Memory RAG

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-31%20passed-brightgreen.svg)](#testing)

**Base Agentic Memory RAG** (`base-agentic-memory-rag`) is a lightweight, zero-external-runtime-dependency Python engine for dual-cipher, conserved-weight agentic memory and evidence-preserving RAG (Retrieval-Augmented Generation).

It is a standalone implementation of the smallest dependable core shared by the **Fractal Memory** and **HUMAN** cognitive architectures:

- **One Immutable `SELF` Origin**: Unifying input and output traversal paths.
- **Three Input Trunks**: `HEAR`, `SEE`, and `NOTICE` for causal event perception.
- **Three Output Trunks**: `SPEAK`, `LOOK`, and `DO` for basal external action classification.
- **Dual-Cipher Y-Axis Traversal**: Directional graph search over learned structural branches based on traversal time and familiarity rather than plain cosine distance.
- **Conserved Fluid Weights**: Global and local softmax edge normalization ensuring total probability conservation (`sum(weights) = 1.0`).
- **Two-Lane Factual Retrieval**: Direct semantic Top-3 Safety Rail combined with Graph-Selected Vault Retrieval (Dense + BM25).
- **Canonical SQLite Evidence Authority**: Immutable event records stored in SQLite with explicit supersession history.
- **Multi-Resolution Experience Projections**: Language-free lower-vault numeric projections carrying preference and confidence statistics without prose duplication.
- **Evidence-Backed Growth**: Overlap-gated child branch formation with logarithmic support scaling and semantic surface ports.
- **Persistent Agent Gestation & Hatching**: CLI tools to gestate, hatch, and converse with local LLM agents (e.g. Ollama) backed by durable receipts.
- **Production Vector Store Adapters**: Out-of-the-box adapters for ChromaDB, Pinecone, pgvector, and in-memory stores.

---

## 🏛 Architecture Overview

```text
                                shared crown
                         concepts, vectors, and vaults
                          /                       \
              HEAR -- SEE -- NOTICE       SPEAK -- LOOK -- DO
                          \                       /
                                    SELF
```

### Key Architectural Components

1. **Topology & Causal Trunks**:
   - `HEAR`: Conversational or direct inbound messages.
   - `SEE`: Correlated real-time environmental observations or tool execution returns.
   - `NOTICE`: Uncorrelated background updates, notifications, or delayed results.
   - `SPEAK`: Outbound verbal or text communication.
   - `LOOK`: Non-mutating state inspection or information retrieval actions.
   - `DO`: External state mutations or tool executions.

2. **Y-Axis Traversal**:
   - Travel time formula:
     $$\text{travel\_time}(e) = \frac{\Delta y(e)}{\epsilon + \text{local\_probability}(e | v)} + \text{conflict\_penalty}(e)$$
   - Path selection depends on structural depth and learned familiarity rather than raw text similarity.

3. **Two-Lane Retrieval Pipeline**:
   - **Lane 1 (Direct Dense Rail)**: Top-3 nearest neighbor dense embeddings across canonical memory. Protects dates, numbers, names, paths, and explicit negations from eviction.
   - **Lane 2 (Graph Vault Search)**: Y-path traversal $\rightarrow$ visited node expansion $\rightarrow$ candidate vault aggregation $\rightarrow$ hybrid Dense + BM25 reranking.

4. **Conserved Weight Learning**:
   - Live edge logits are globally and locally softmax-normalized.
   - Durable strength updates occur **only** after a verified outcome carrying an immutable receipt ID. Unverified model outputs cannot reinforce paths.

---

## 🚀 Quick Start

### Installation

Install the package using pip (Python 3.11+ required):

```bash
# Clone the repository
git clone https://github.com/your-org/base-agentic-memory-rag.git
cd base-agentic-memory-rag

# Install in editable mode with test dependencies
pip install -e '.[test]'
```

### Running Tests & Demo

```bash
# Run pytest suite
python3 -m pytest

# Run built-in interactive demo
python3 -m agentic_memory_rag.demo
# Or via installed CLI entrypoint:
agentic-memory-demo
```

---

## 🐣 Gestating and Hatching an Agent

The package includes a guided agent nursery adapter to gestate and hatch persistent local talking agents backed by Ollama:

### One-Command Hatch

```bash
agentic-memory-hatch
```

This interactive CLI prompts for your name, the agent's name, an initial taste seed, and an installed Ollama model (e.g. `granite4.1:8b`, `llama3.2`, `qwen2.5`). It initializes `agentic_memory.sqlite` and launches an interactive chat session.

### Scripted Gestation & Hatching

```bash
# Step 1: Gestate agent profile and seed initial taste
agentic-memory-gestate \
  --human-name Josh \
  --agent-name Nova \
  --taste curious \
  --model granite4.1:8b

# Step 2: Hatch and launch persistent chat shell
agentic-memory-hatch
```

Available taste seeds:
- `balanced`: Equal balance across interaction modes.
- `curious`: Higher output prior on `LOOK` (exploration/inquiry).
- `deliberate`: Higher output prior on structured analysis.
- `builder`: Higher output prior on `DO` (execution/action).

*Note: Taste seeds set initial edge priors; they do not hardcode fixed prompts and adapt over time based on verified outcomes.*

---

## 💡 Python API Usage

### Minimal Example

```python
from agentic_memory_rag import BaseAgenticMemoryRAG, EventKind

# Initialize persistent memory engine (SQLite database)
mind = BaseAgenticMemoryRAG("agentic_memory.sqlite")

# Add domain concepts
mind.add_concept(
    concept_id="project_helios",
    label="Project Helios",
    terms=["helios", "deployment", "launch"],
    input_trunks=["HEAR", "NOTICE"],
    output_trunks=["LOOK", "DO"],
)

# Remember an event (immutable canonical record)
mind.remember(
    text="Josh moved Project Helios deployment to 2027-04-18.",
    kind=EventKind.MESSAGE,
    source_id="josh",
    concept_ids=["project_helios"],
)

# Recall context for a query
result = mind.recall("When is Project Helios deploying?")

print("=== Context for LLM ===")
print(result.context)

print("\n=== Direct Factual Rail IDs ===")
print(result.packet.direct_record_ids)

print("\n=== Y-Paths Visited ===")
print(result.packet.y_paths)

mind.close()
```

### Multi-Resolution Experience Projections

Every remembered experience deposits language-free numeric projections into lower vaults:

```python
mind.remember(
    text="Verified outcome received for turn 42.",
    metadata={
        "experience_id": "turn-42",
        "preference_signals": [0.2, 0.8],
        "preference_confidence": 0.9,
    },
)

# Inspect experience state and lower projections
print(mind.experience_state("turn-42"))
print(mind.experience_projections("turn-42"))
```

### Vector Database Adapters

For production applications requiring vector database backends, `agentic_memory_rag.vector_adapters` provides pluggable vector store adapters:

```python
from agentic_memory_rag.vector_adapters import (
    InMemoryVectorAdapter,
    ChromaVectorAdapter,
    PineconeVectorAdapter,
    PgVectorAdapter,
)

# In-Memory Adapter (pure Python math)
vector_store = InMemoryVectorAdapter()
vector_store.upsert("vec-1", [0.1, 0.5, 0.9], metadata={"concept": "helios"})

# Query top k
results = vector_store.query([0.1, 0.5, 0.9], top_k=3)
```

---

## 🔒 Mandatory Architectural Invariants

1. Exactly one `SELF` origin exists.
2. Input frontier is strictly `HEAR`, `SEE`, and `NOTICE`.
3. Output frontier is strictly `SPEAK`, `LOOK`, and `DO`.
4. Global live edge mass sums to `1.0`.
5. Non-empty local outgoing frontiers sum to `1.0`.
6. Surface semantic scores cannot alter Y travel time.
7. Direct dense rail evidence cannot be evicted by graph retrieval scores.
8. Canonical records in SQLite are immutable; corrections create supersession records.
9. Unverified outputs cannot durably reinforce edge weights.
10. Lower experience projections contain no natural language prose.

Invariant checks can be programmatically verified at runtime via `GraphRuntime.validate_invariants()`.

---

## 🧪 Testing

The repository maintains 100% passing test coverage across topology, retrieval, gestation, multi-resolution projections, and vector adapters.

```bash
# Run pytest suite
python3 -m pytest -v
```

Test modules:
- `tests/test_store_and_topology.py`: SQLite schema, invariants, concept topology.
- `tests/test_graph_and_learning.py`: Y-traversal, travel time, conserved fluid weight learning.
- `tests/test_retrieval_pipeline.py`: Two-lane recall, direct safety rail, BM25 + dense vault retrieval.
- `tests/test_multiresolution_memory.py`: Lower projections, overlap clusters, experience states.
- `tests/test_gestation_and_agent.py`: Gestation profiles, taste seeds, persistent agent turns.
- `tests/test_output_and_demo.py`: Output classification (`SPEAK`/`LOOK`/`DO`), demo pipeline.
- `tests/test_vector_adapters.py`: Vector store adapter interfaces and in-memory engine.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
