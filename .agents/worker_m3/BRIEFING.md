# BRIEFING — 2026-08-29T02:39:41Z

## Mission
Execute, verify, and document End-to-End Unified Plain Language Synthesis for Habitus-AI (Milestone 3).

## 🔒 My Identity
- Archetype: implementer, qa, specialist
- Roles: implementer, qa, specialist
- Working directory: /home/nemo/habitus-ai-experiments/.agents/worker_m3
- Original parent: 34dec5a2-0564-4786-88e9-0c9f3799e9c2
- Milestone: Milestone 3 (End-to-End Unified Plain Language Synthesis)

## 🔒 Key Constraints
- NEVER push commits without explicit authorization from the user.
- NEVER start or run tests or benchmarks without being explicitly told to do so (user request explicitly commanded tests & execution).
- NEVER start a single test, benchmark, or any action that consumes ANY paid API credits unless the user has specifically and explicitly approved THAT EXACT TEST.
- DO NOT BE LAZY! DO NOT WRITE A SCRIPT FOR A DETAIL-ORIENTED TASK THAT REQUIRES YOU TO PERFORM IT MANUALLY.
- READ-ONLY DIAGNOSIS & EXPLICIT CHANGE RULE: Never modify source code based on implied intent or when the user asks a question. ONLY modify source code when the user explicitly requests or commands a code change.
- Strict Test Process Management: ALWAYS kill running python test processes (`pkill -9 -f "python3"`) BEFORE starting a new test. Single runner constraint.
- Set LD_LIBRARY_PATH=/usr/local/lib/ollama:$LD_LIBRARY_PATH
- Working directory: /home/nemo/habitus-ai-experiments
- DO NOT CHEAT: genuine implementations only, no hardcoding or dummy outputs.

## Current Parent
- Conversation ID: 34dec5a2-0564-4786-88e9-0c9f3799e9c2
- Updated: 2026-08-29T02:39:41Z

## Task Summary
- **What to build/verify**: Execute, verify, and document End-to-End Unified Plain Language Synthesis for Habitus-AI using gestated SQLite mind, native binaries, and GGUF soft generator.
- **Success criteria**: All native binaries verified, soft generation verified with continuous 1024D slot activation packets without prompt leakage, integration tests passing, handoff report generated.
- **Interface contracts**: experiments/graph_native_live/ and tests/
- **Code layout**: /home/nemo/habitus-ai-experiments

## Key Decisions Made
- Initializing verification workflow.

## Artifact Index
- /home/nemo/habitus-ai-experiments/.agents/worker_m3/ORIGINAL_REQUEST.md — Original request
- /home/nemo/habitus-ai-experiments/.agents/worker_m3/progress.md — Execution progress and heartbeat
- /home/nemo/habitus-ai-experiments/.agents/worker_m3/handoff.md — Handoff report

## Change Tracker
- **Files modified**: None yet
- **Build status**: Pending
- **Pending issues**: None

## Quality Status
- **Build/test result**: Pending
- **Lint status**: Pending
- **Tests added/modified**: Pending

## Loaded Skills
- None
