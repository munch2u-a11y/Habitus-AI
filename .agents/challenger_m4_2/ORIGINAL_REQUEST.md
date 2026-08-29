## 2026-08-29T02:40:34Z

<USER_REQUEST>
You are Challenger 2 for Milestone 4 (Full Suite E2E Verification & Victory Audit) of Habitus-AI.
Your working directory is /home/nemo/habitus-ai-experiments/.agents/challenger_m4_2.

Perform adversarial stress testing on the complete Habitus-AI system:
- Enforce single runner rule: `pkill -9 -f "python3"`.
- Set `export LD_LIBRARY_PATH=/usr/local/lib/ollama:$LD_LIBRARY_PATH`.
- Set `export PYTHONPATH=src:experiments/graph_native_live:$PYTHONPATH`.
- Stress test zero-prompt leakage: verify that no string serialization of prompts, graph labels, or episodic memories enters the LLM embedding or context buffers.
- Stress test packet boundary conditions, extreme activation values, and C++ binary error recovery.

Provide your empirical findings and pass/fail determination directly in your message response.
</USER_REQUEST>
