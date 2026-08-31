# Persistent Live-Agent Longitudinal Trial — 2026-08-31

## Scope

One persistent Habitus mind was used for conversation, read-only workspace tasks,
failure tracing, narrow corrections, and verbatim reruns. This was a behavioral
refinement trial, not a claim of general agent competence.

- Model: `qwen3.5:9b-q4_K_M`
- Seed: `7`
- Temperature: `0.1`
- Workspace: `examples/continuous_nursery`
- Mind: `/tmp/habitus-growth-mind-20260830.sqlite`
- Loop ledger: `/tmp/habitus-growth-loop-20260830.sqlite`
- Exact model frames: `live_agent_longitudinal_trace_2026-08-31.jsonl`
- Authority: read/list/navigation only; writes and commands were not enabled
- Tool fields sent to Ollama: `0`

Read-only pre-trial snapshots were kept at:

- `/tmp/habitus-growth-mind-pre-live-20260831.sqlite`
- `/tmp/habitus-growth-loop-pre-live-20260831.sqlite`

## Behavioral findings

| Check | Initial behavior | Traced cause | Final behavior |
|---|---|---|---|
| Action-history recall | Denied actions that had verified receipts | Receipt records were excluded from language recall with no separate evidence projection | Recalled the exact `python3 scripts/lamp_status.py` result from verified evidence |
| Pronoun continuity | Not yet isolated | Needed one persistent host rather than turn-by-turn restarts | `What color was it?` resolved to the blue square without another action |
| Read operation provenance | Invented `cat` as the mechanism | Minimal projection retained file content but discarded operation identity; stale speech then supplied a command | Explicitly distinguished direct workspace read from shell execution |
| Single-file task | Answered from memory before a current read | Ability receipt gate existed but action wording drifted into an unrecognized bare command | Read receipt on step 1, grounded final answer on step 2 |
| Explicit local repeat | `repeat that` summarized unrelated retained actions | Generic query admitted weak JIT distractors between the referent and input | Repeat/rephrase requests used the immediately preceding reply; graph recall still ran internally |
| Two-file comparison | One fresh read satisfied the coarse READ gate | Completion tracked ability type, not named targets | Each quoted read target required its own verified receipt |
| Multi-step focus | After both facts were available, the agent answered only from the newest file | Pinned request was far above the newest observation in a long frame | Active request is placed beside each new observation |
| Action-intent leakage | `I will freshly read...` escaped as outward completion | Intent detector required the action verb immediately after `I will` | Common modifiers are recognized as action intent and cannot become a final answer |

## Final controlled task

Request:

> Please freshly read both `objects/blue-square.txt` and
> `objects/red-circle.txt`, compare them, and tell me which is stable and why.

Final event: `agent-event:a433df32d53e43ac905737279095a513`

Observed trajectory:

1. Verified read of `objects/blue-square.txt`.
2. A malformed action attempt was kept private and corrected.
3. A repeated blue read was suppressed without another receipt or reward.
4. Verified read of `objects/red-circle.txt`.
5. The agent answered that the blue square was stable because the square object
   matched the square slot, while the red circle was unstable because its shape
   mismatched that slot.

Authoritative final receipts:

- `receipt:ed83f72675e74078bb10f4ed278b7149` — blue-square read
- `receipt:fbaf98304e5d48aca9c1d8ed4931e706` — red-circle read

Result: **pass** for required actions, receipt coverage, comparison, and final
artifact content. No shell command was used.

## Corrections retained

- Exact JSONL tracing of system text, JIT frame, response, token counts, and the
  absence of a model tool field.
- A bounded verified-result retrieval lane used only for action-evidence
  questions.
- Private thoughts and prior unverified agent claims do not compete with
  receipts when the user asks what actually happened.
- Direct reads retain minimal natural-language provenance after backend metadata
  is stripped.
- Explicit quoted read targets are gated independently inside one event.
- The pinned task is kept next to action observations during multi-step work.
- Explicit repeat/rephrase follow-ups use the immediate conversational referent
  rather than unrelated JIT memory text; ordinary pronoun questions keep recall.

## Known boundaries

- Per-target completion is currently implemented for explicitly backticked
  `read`/`open` paths, not yet for multiple run, write, list, or navigation
  targets.
- The accumulated test mind still contains earlier false spoken claims. They
  were intentionally preserved to test evidence arbitration; no history was
  deleted or rewritten.
- Some successful answers remain stylistically stiff or meta. This trial scored
  grounded behavior and causal receipts, not prose quality.
- The live host remained read-only. Command execution and writes need separate,
  tightly bounded tasks with exact artifacts and read-back verification.
- The ledger includes failures from earlier diagnostic attempts. The final task
  must be judged from its event and receipts, not aggregate historical counts.

## Verification

The full repository collection contains 88 tests. The final run completed with
86 passing and 2 optional skips.
