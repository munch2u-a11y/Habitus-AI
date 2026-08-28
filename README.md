# Habitus AI 🏛️🧠

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-31%20passed-brightgreen.svg)](#testing)
[![Developer Docs](https://img.shields.io/badge/docs-Developer%20Audit-purple.svg)](DEVELOPMENT.md)

**Habitus AI** (`habitus-ai`) is a lightweight, zero-external-runtime-dependency Python engine for dual-cipher, conserved-weight agentic memory and evidence-preserving RAG (Retrieval-Augmented Generation).

Named after the architectural concept of *habitus* (embodied, structural dispositions learned through experience), **Habitus AI** unifies long-term memory authority, structural graph routing, and action classification into a single, elegant cognitive substrate.

---

## 🎨 Architectural Geometry

![Habitus AI Folded Hourglass Toroidal Architecture](assets/habitus_hourglass_geometry.png)

---

## 🌟 How It Works (In Plain English)

Traditional AI memory relies on flat vector databases or massive prompt context dumps that cause hallucinations, prompt bloat, and context eviction. **Habitus AI** takes a radically different approach based on structural 3D geometry and conserved fluid dynamics:

### 1. The Hourglass Bicone Topology
Memory in Habitus AI is organized around an immutable center point called **`SELF`** (Layer 0):
- **+Y Perceptual Trunks (`HEAR`, `SEE`, `NOTICE`)**: Intakes conversational text, real-time tool returns, and background notifications.
- **-Y Effector Trunks (`SPEAK`, `LOOK`, `DO`)**: Classifies outbound action intents—distinguishing verbal responses (`SPEAK`), non-mutating inspections (`LOOK`), and external state changes (`DO`).
- **Semantic Crown**: Shared 1024D concept vectors and vault storage connecting sensory input to action output.

### 2. Dual-Cipher Y-Axis Traversal
Instead of pulling nearest-neighbor text snippets purely by cosine similarity, Habitus AI runs a **Y-axis travel time cipher**. It calculates structural depth, path travel times, and learned familiarity:
$$\text{travel\_time}(e) = \frac{\Delta y(e)}{\epsilon + \text{local\_probability}(e | v)} + \text{conflict\_penalty}(e)$$
Winning Y-paths activate visited node vaults for associative expansion, ensuring memory retrieval is guided by structural routing rather than simple keyword proximity.

### 3. Conserved Fluid Edge Weights
Just like physical conservation laws, live edge strengths in Habitus AI sum to `1.0` both globally and locally. Reinforcing one successful route naturally optimizes competitor pathways, preventing runaway score inflation and eliminating memory drift.

### 4. Two-Lane Factual Safety Rail
- **Lane 1 (Direct Dense Rail)**: Locked top-3 dense nearest neighbors pulling immutable canonical records directly from SQLite. Crucial dates, numbers, names, paths, and negations can never be evicted by graph scores.
- **Lane 2 (Graph Vault Retrieval)**: Traverses visited Y-paths $\rightarrow$ expands candidate vaults $\rightarrow$ applies hybrid Dense + BM25 reranking.

### 5. Gestation & Hatching
---

## 📊 Why Habitus AI? (Architecture Comparison)

| Capability / Feature | Traditional Vector RAG | Standard Graph RAG | Habitus AI 🏛️🧠 |
| :--- | :---: | :---: | :---: |
| **Memory Authority** | Loose Vector Chunks | Static Triples | **Immutable Canonical SQLite Records** |
| **Factual Safety Rail** | ❌ (Eviction Prone) | ❌ (Eviction Prone) | **✅ Direct Top-3 Rail (Zero Eviction)** |
| **Action Classification** | ❌ (LLM Prompt Guesses) | ❌ (None) | **✅ Classified Trunks (`SPEAK`/`LOOK`/`DO`)** |
| **Durable Learning** | ❌ (Unverified Context) | ❌ (Manual Schema) | **✅ Receipt-Gated (`ActionReceipt` verified)** |
| **Probability Mechanics** | N/A | Accumulating Scores | **✅ Softmax Fluid Weight Conservation ($\sum=1.0$)** |
| **Runtime Dependencies** | External Vector DB | Neo4j / NetworkX | **⚡ 0 External DBs (Pure Python + SQLite)** |

---

## 🚀 Endless Possibilities for Habitus AI

- 🤖 **Zero-Drift Autonomous Agents**: Persistent identity and evidence memory that survive process restarts without context drift.
- 🛡️ **Receipt-Gated Action Verification**: Agents learn durably **only** after receiving a verified external execution receipt (`ActionReceipt`). Unverified internal model chatter cannot corrupt edge weights.
- 🛠️ **Built-in Operational Tool Suite & Trunk Binding**: Includes standard tools (`read_file`, `write_file`, `inspect_directory`, `execute_python`, `web_search`, `send_message`) pre-bound to motor trunks (`LOOK`, `DO`, `SPEAK`), generating verified receipts (`ToolReceipt`).
- ⚡ **Ultra-Fast Local Execution**: 0 external database servers required; runs entirely in pure Python standard library and SQLite with optional vector database adapters (ChromaDB, Pinecone, pgvector).

---

## 🐣 Quick Start for Testers

### 1. Installation

```bash
git clone https://github.com/munch2u-a11y/Habitus-AI.git
cd habitus-ai
pip install -e '.[test]'
```

### 2. Launch the Interactive Web App Launcher 🌐🐣

Launch the visual web launcher with auto-detection of local models, developer tools manager, and an animated egg gestation modal:

```bash
habitus-launch
```

- **Auto-Detect Models**: Automatically queries local Ollama models (`http://127.0.0.1:11434/api/tags`).
- **Animated Gestation Progress**: Watch the egg sprite 🥚 float & glow with a live `0%` $\rightarrow$ `100%` progress bar.
- **Developer Tools Tab**: Load and manage single-use execution gateway tools (`LOOK`, `DO`, `SPEAK`).
- **Interactive Chat**: Chat with responses classified into motor trunks (`SPEAK`, `LOOK`, `DO`) and Y-paths traversed.

### 3. Terminal CLI Setup & Hatching

During chat:
- Type `/status` to inspect record counts, crown concepts, total edges, and graph health.
- Type `/quit` to safely exit.

### 3. Scripted Gestation

```bash
habitus-gestate \
  --human-name Josh \
  --agent-name Nova \
  --taste curious \
  --model granite4.1:8b

habitus-hatch
```

### 4. Run the Pipeline Demo

```bash
habitus-demo
```

### 5. Run Automated Tests

```bash
python3 -m pytest -v
```

### 6. Registering Tools & Verified Receipts

```python
from habitus_ai import HabitusAI, OutputTrunk
from habitus_ai.tools import ToolRegistry, BUILTIN_OPERATIONAL_TOOLS

mind = HabitusAI("habitus_memory.sqlite")
registry = ToolRegistry(mind)

# Register operational tools bound to motor trunks (LOOK, DO, SPEAK)
for tool in BUILTIN_OPERATIONAL_TOOLS:
    registry.register_tool(tool)

# Execute tool and generate verified execution receipt
receipt = registry.execute("tool:read_file", {"filepath": "README.md"})
print("Verified:", receipt.verified, "| Output size:", receipt.output["size_bytes"])
```

#### 💡 Custom Tools & How "Skills" Form Naturally

In traditional frameworks, developers must write complex prompt catalogs and manual tool routing rules. In **Habitus AI**:

- **Plug In Whatever Tools You Want**: Register any custom Python function, REST API, DB query, or system command using `ToolDefinition` bound to the appropriate motor trunk (`LOOK` for inspections, `DO` for state mutations, `SPEAK` for verbal notifications).
- **Emergent Skills from Repetition & Reinforcement**: As your agent executes tools and receives verified receipts (`ToolReceipt`), lower-vault experience projections form overlap clusters. Over time, repeated successful tool patterns **naturally coalesce into durable learned skills** via conserved fluid weight reinforcement—without needing hardcoded skill files!

### 7. Verbal Audio Reflex Bridge (Piper TTS & STT Intake)

```python
from habitus_ai import HabitusAI
from habitus_ai.audio import AudioReflexBridge

mind = HabitusAI("habitus_memory.sqlite")
audio_bridge = AudioReflexBridge(mind, piper_model="en_US-lessac-medium")

# Execute verbal intake -> Y-traversal -> TTS speech synthesis reflex
result = audio_bridge.process_reflex_turn("Hello Nova")

print("Spoken output:", result["spoken_text"])
print("Trunk classified:", result["classified_trunk"])
print("Audio WAV path:", result["audio_path"])
print("Verified receipt:", result["receipt"].receipt_id)
```

---

## 📚 Developer & Researcher Documentation

For deep technical audits, mathematical derivations, sequence workflow diagrams, and our LLM-free experimental benchmarks (language projection & reflective tool routing without an LLM), read the **[Developer & Architectural Audit (DEVELOPMENT.md)](DEVELOPMENT.md)**.

---

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).
