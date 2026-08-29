## 2026-08-29T02:40:02Z
<USER_REQUEST>
You are the Forensic Auditor for Milestone 3 (End-to-End Unified Plain Language Synthesis) of Habitus-AI.
Your working directory is /home/nemo/habitus-ai-experiments/.agents/auditor_m3.

Conduct a rigorous Forensic Integrity Audit of Milestone 3:
1. Static analysis of `experiments/graph_native_live/`, `src/habitus_ai/`, and `tests/`:
   - Verify NO hardcoded test results, fake responses, or stubbed outputs.
   - Verify NO prompt text leakage (the LLM must NOT receive serialized prompt strings; only continuous 1024D soft-input packets).
2. Runtime / Execution validation:
   - Check if `graph_soft_generator` and `lexeme_codec` are real compiled C++ binaries dynamically linked against `/usr/local/lib/ollama/libllama.so` and `libggml.so`.
   - Check if the SQLite mind (`habitus-1787969878668476910.sqlite`) is genuinely queried.
   - Check if the Qwen3 GGUF model (`/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`) is genuinely loaded and evaluated by llama.cpp.

Deliver your clear binary verdict: `CLEAN` or `INTEGRITY VIOLATION`, along with full supporting evidence directly in your message response.
</USER_REQUEST>
