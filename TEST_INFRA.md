# E2E Test Infra: Habitus-AI GGUF-Unified Mind Substrate

## Test Philosophy
- Requirement-driven verification of preference matrix gestation, native GGUF soft-input adapter, and plain language generation.
- Dual-track opaque-box and white-box verification.

## Feature Inventory
| # | Feature | Requirement | Verification Target |
|---|---------|-------------|---------------------|
| F1 | Gestation & Nursery Pipeline | R1 & AC1 | `experiments/graph_native_live/accelerated_gestation.py`, `nursery.py`, `tests/test_accelerated_gestation.py`, `tests/test_nursery.py` |
| F2 | Soft-Input GGUF Generation | R2 & AC2 | `experiments/graph_native_live/native/graph_soft_generator`, `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`, 1024D continuous vectors |
| F3 | Unified Plain Language Synthesis | R3 & AC3 | `experiments/graph_native_live/transformer_hatch.py`, `live_tester.py`, coherent output strings |
| F4 | Full Graph-Native Test Suite | AC4 | `pytest tests/test_graph_native_live.py tests/test_accelerated_gestation.py tests/test_nursery.py` |

## Test Execution Commands (Workers & Reviewers)
- `pytest tests/test_nursery.py`
- `pytest tests/test_accelerated_gestation.py`
- `pytest tests/test_graph_native_live.py`
- `make -C experiments/graph_native_live build`
- `make -C experiments/graph_native_live gestate-fast`
- `make -C experiments/graph_native_live nursery`
- `make -C experiments/graph_native_live live`
