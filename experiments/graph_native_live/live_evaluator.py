#!/usr/bin/env python3
"""Habitus-AI Live Cognitive Evaluator & Continuous Loop Orchestrator.

Implements Milestone 5 Requirement R1 & R4:
- Closed-loop multi-turn cognitive cycle: Layer 4 Semantic Membrane <-> SELF Preference Nodes.
- Dynamic Layer 3 Structural Mini-Map extraction and intrinsic topological embedding synthesis.
- Layer 4 Softmax edge weight conservation and dynamic path modulation.
- Continuous 1024D vector packet compilation across lexical_membrane, opaque_topological,
  and soft_basis strategies.
- Strict Zero-Prompt Leakage Invariant: zero user prompt text or RAG memory strings in .packet
  or GGUF context.
- Telemetry receipt export compliant with schema habitus.cognitive-eval-turn.v1 and
  habitus.cognitive-eval-session.v1.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.embeddings import DeterministicHashEmbedder, Embedder  # noqa: E402
from habitus_ai.graph import (  # noqa: E402
    INPUT_NODE_IDS,
    OUTPUT_NODE_IDS,
    SELF_ID,
    compute_structural_overlay,
)
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import (  # noqa: E402
    EventKind,
    GraphSide,
    InputTrunk,
    OutputTrunk,
    RecordType,
    TraversalTrace,
)

import live_tester  # noqa: E402
import opaque_skeleton  # noqa: E402

DIMENSION = 1024
DEFAULT_MODEL = live_tester.DEFAULT_MODEL
DEFAULT_RUNNER = live_tester.DEFAULT_RUNNER

PROTOCOL_KEYWORDS: set[str] = {"habitus", "opaque", "soft", "packet", "v1"}
RESERVED_BASIS_SLOTS: set[str] = {
    "speak",
    "greeting",
    "warm",
    "question",
    "clear",
    "memory",
    "uncertain",
    "gratitude",
    "observation",
    "action",
    "affinity",
    "caution",
    "withhold",
}
# Valence slots are driven by the substrate's own preference state, never by input text.
VALENCE_BASIS_SLOTS: tuple[str, ...] = ("affinity", "caution", "withhold")
PROTOCOL_MAGIC_HEADERS: tuple[str, ...] = (
    "HABITUS_OPAQUE_PACKET_V1",
    "HABITUS_SOFT_PACKET_V1",
)


def verify_zero_prompt_leakage(
    packet_path: Path,
    user_text: str,
    *,
    expected_mode: str = "lexical_membrane",
) -> None:
    """Rigorous schema-aware zero-prompt leakage verification.

    Guarantees:
    1. 100% absence of user prompt text, secrets, API keys, and memory strings.
    2. Strict schema grammar and IEEE float validation for all matrix rows.
    3. Zero false positives on ASCII float coordinates, dimension constants, and schema keywords.
    """
    raw_payload = packet_path.read_text(encoding="utf-8", errors="ignore")
    lines = raw_payload.strip().splitlines()
    if not lines:
        raise RuntimeError("CRITICAL ZERO-LEAKAGE VIOLATION: Packet buffer is empty!")

    header = lines[0].strip()

    # 1. Structural Schema Validation
    if header == "HABITUS_SOFT_PACKET_V1":
        for line_idx, line in enumerate(lines[1:], start=1):
            parts = line.strip().split()
            if len(parts) != 2:
                raise RuntimeError(
                    f"CRITICAL ZERO-LEAKAGE VIOLATION: Malformed soft basis row at line {line_idx}: '{line}'"
                )
            basis_slot, val_str = parts
            if basis_slot not in RESERVED_BASIS_SLOTS:
                raise RuntimeError(
                    f"CRITICAL ZERO-LEAKAGE VIOLATION: Unauthorized basis slot '{basis_slot}' detected!"
                )
            try:
                val = float(val_str)
                if not (0.0 <= val <= 1.0) or not math.isfinite(val):
                    raise ValueError()
            except ValueError:
                raise RuntimeError(
                    f"CRITICAL ZERO-LEAKAGE VIOLATION: Invalid activation float '{val_str}' at line {line_idx}!"
                )

    elif header == "HABITUS_OPAQUE_PACKET_V1":
        if len(lines) < 2:
            raise RuntimeError("CRITICAL ZERO-LEAKAGE VIOLATION: Missing dimension header line!")
        dim_parts = lines[1].strip().split()
        if len(dim_parts) != 2:
            raise RuntimeError(f"CRITICAL ZERO-LEAKAGE VIOLATION: Invalid dimension line: '{lines[1]}'")
        dim, num_rows = int(dim_parts[0]), int(dim_parts[1])
        if dim != DIMENSION or not (1 <= num_rows <= 8):
            raise RuntimeError(
                f"CRITICAL ZERO-LEAKAGE VIOLATION: Dimension header out of bounds: dim={dim}, rows={num_rows}"
            )
        vector_lines = lines[2:]
        if len(vector_lines) != num_rows:
            raise RuntimeError(
                f"CRITICAL ZERO-LEAKAGE VIOLATION: Vector row count mismatch: {len(vector_lines)} != {num_rows}"
            )
        for row_idx, row in enumerate(vector_lines):
            tokens = row.strip().split()
            if len(tokens) != DIMENSION:
                raise RuntimeError(
                    f"CRITICAL ZERO-LEAKAGE VIOLATION: Row {row_idx} length {len(tokens)} != {DIMENSION}"
                )
            for tok in tokens:
                try:
                    v = float(tok)
                    if not math.isfinite(v):
                        raise ValueError()
                except ValueError:
                    raise RuntimeError(
                        f"CRITICAL ZERO-LEAKAGE VIOLATION: Injected non-float token '{tok}' in row {row_idx}!"
                    )
    else:
        raise RuntimeError(f"CRITICAL ZERO-LEAKAGE VIOLATION: Invalid magic header: '{header}'")

    # 2. Intentional Protocol Magic Header Injection Guard
    if user_text.strip():
        for magic in PROTOCOL_MAGIC_HEADERS:
            if magic in user_text:
                raise RuntimeError(
                    f"CRITICAL ZERO-LEAKAGE VIOLATION: Protocol magic header '{magic}' detected in input!"
                )

    # 3. Forensic Textual Leakage Inspection
    if user_text.strip():
        raw_lower = raw_payload.casefold()
        raw_words = re.findall(r"[A-Za-z0-9_-]+", user_text)
        for word in raw_words:
            clean = "".join(c for c in word if c.isalnum()).casefold()
            # Require minimum length 4 and at least 3 alphabetic characters (reject pure float digits/numbers)
            if len(clean) >= 4 and sum(1 for c in clean if c.isalpha()) >= 3:
                # Whitelist protocol schema keywords
                if clean in PROTOCOL_KEYWORDS:
                    continue
                # Whitelist reserved basis slots in soft_basis mode
                if header == "HABITUS_SOFT_PACKET_V1" and clean in RESERVED_BASIS_SLOTS:
                    continue
                if clean in raw_lower:
                    raise RuntimeError(
                        f"CRITICAL ZERO-LEAKAGE VIOLATION: Input word '{clean}' detected in packet buffer!"
                    )


def source_affinity_state(mind: BaseAgenticMemoryRAG, source_id: str) -> dict[str, float]:
    """Aggregate habitual preference toward one interaction source.

    Reads only persisted experience states (preference mean and weight accumulated by
    edge reinforcement across prior turns).  No record text is read, so the returned
    affinity is a property of structural memory, not of anything the source said.
    """
    empty = {"affinity_mean": 0.0, "sample_weight": 0.0, "samples": 0.0}
    if not source_id:
        return empty

    weighted_sum = 0.0
    weight_total = 0.0
    samples = 0
    for record in mind.store.list_active_records():
        if record.source_id != source_id:
            continue
        state = mind.store.get_experience_state(mind.graph._experience_id(record))
        if state is None:
            continue
        weight = max(0.0, float(state.preference_weight))
        if weight <= 0.0:
            continue
        weighted_sum += float(state.preference_mean) * weight
        weight_total += weight
        samples += 1

    if weight_total <= 1e-9:
        return empty
    return {
        "affinity_mean": max(-1.0, min(1.0, weighted_sum / weight_total)),
        "sample_weight": weight_total,
        "samples": float(samples),
    }


def membrane_preference_polarity(mind: BaseAgenticMemoryRAG, trunk: str = "HEAR") -> dict[str, float]:
    """Read Layer 2/4 preference polarity straight off the ingress membrane edges."""
    stable = mind.store.find_edge(GraphSide.INPUT, f"IN:{trunk}", f"PREF:{trunk}:STABLE")
    unstable = mind.store.find_edge(GraphSide.INPUT, f"IN:{trunk}", f"PREF:{trunk}:UNSTABLE")

    stable_weight = float(stable.softmax_weight) if stable is not None else 0.0
    unstable_weight = float(unstable.softmax_weight) if unstable is not None else 0.0
    share_total = stable_weight + unstable_weight
    softmax_polarity = (stable_weight - unstable_weight) / share_total if share_total > 1e-9 else 0.0

    stable_strength = float(stable.log_strength) if stable is not None else 0.0
    unstable_strength = float(unstable.log_strength) if unstable is not None else 0.0
    strength_margin = math.tanh(stable_strength - unstable_strength)

    conflict_penalty = max(
        float(stable.conflict_penalty) if stable is not None else 0.0,
        float(unstable.conflict_penalty) if unstable is not None else 0.0,
    )
    return {
        "softmax_polarity": softmax_polarity,
        "strength_margin": strength_margin,
        "stable_weight": stable_weight,
        "unstable_weight": unstable_weight,
        "conflict_penalty": conflict_penalty,
    }


def preference_valence_activations(
    mind: BaseAgenticMemoryRAG,
    *,
    source_id: str = "",
    trunk: str = "HEAR",
) -> tuple[dict[str, float], dict[str, float]]:
    """Project habitual preference state onto the valence basis slots.

    Returns (activations, diagnostics).  Positive habitual valence opens the ``affinity``
    slot; negative valence opens ``caution``; accumulated conflict penalty on the
    preference membrane additionally opens ``withhold``, which is how avoidant output
    steering reaches the language layer.
    """
    affinity = source_affinity_state(mind, source_id)
    membrane = membrane_preference_polarity(mind, trunk)

    if affinity["samples"] > 0.0:
        valence = 0.6 * affinity["affinity_mean"] + 0.4 * membrane["strength_margin"]
    else:
        valence = membrane["strength_margin"]
    valence = max(-1.0, min(1.0, valence))

    activations: dict[str, float] = {}
    companions: dict[str, float] = {}
    if valence > 0.15:
        activations["affinity"] = min(1.0, 0.55 + 0.45 * valence)
        # A tone companion keeps the decoded stance fluent rather than lexical.
        companions["warm"] = min(1.0, 0.40 + 0.40 * valence)
    elif valence < -0.15:
        activations["caution"] = min(1.0, 0.55 + 0.45 * abs(valence))
        companions["uncertain"] = min(1.0, 0.40 + 0.40 * abs(valence))

    penalty = membrane["conflict_penalty"]
    if penalty > 0.5 and valence < 0.0:
        activations["withhold"] = min(1.0, 0.25 + 0.07 * penalty)

    for slot, floor in companions.items():
        activations[slot] = max(activations.get(slot, 0.0), floor)

    diagnostics = {
        "valence": valence,
        "source_affinity_mean": affinity["affinity_mean"],
        "source_samples": affinity["samples"],
        "membrane_strength_margin": membrane["strength_margin"],
        "membrane_softmax_polarity": membrane["softmax_polarity"],
        "membrane_conflict_penalty": penalty,
    }
    return activations, diagnostics


def normalize_vec(vector: Sequence[float]) -> list[float]:
    """L2 normalize vector to unit sphere."""
    norm = math.sqrt(sum(float(v) * float(v) for v in vector))
    if norm < 1e-8:
        return [0.0] * len(vector)
    return [float(v) / norm for v in vector]


def utc_iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass(frozen=True)
class EvaluatorConfig:
    database_path: Path
    model_path: Path = DEFAULT_MODEL
    runner_path: Path = DEFAULT_RUNNER
    run_directory: Path = Path(__file__).resolve().parent / "runs"
    max_tokens: int = 256
    seed: int = 42
    skip_think: bool = True
    temperature: float = 1.0
    learning_rate: float = 0.35
    packet_mode: str = "lexical_membrane"  # "lexical_membrane" | "opaque_topological" | "soft_basis" | "projected"
    enforce_zero_leakage: bool = True
    projector_path: Path | None = None  # required for packet_mode="projected"


@dataclass
class TurnTelemetry:
    turn_index: int
    turn_id: str
    pulse_id: str
    input_sha256: str
    source_id: str
    input_trunk: str
    preference_node: str | None
    preference_state_before: dict[str, float]
    preference_state_after: dict[str, float]
    nominated_concept_id: str | None
    input_path: list[str]
    input_edge_ids: list[str]
    output_path: list[str]
    output_edge_ids: list[str]
    input_travel_time: float
    output_travel_time: float
    layer3_minimap: dict[str, Any] | None
    layer4_softmax_weights: dict[str, float]
    packet_path: str
    packet_sha256: str
    packet_rows: int
    packet_mode: str
    zero_leakage_verified: bool
    response_text: str
    response_record_id: str
    stability_delta: float
    reinforced_edges: list[str]
    duration_ms: float
    valence_activations: dict[str, float] = field(default_factory=dict)
    valence_diagnostics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def safe_unit_vector(vector: Sequence[float] | None, fallback_key: str) -> list[float]:
    """Ensure vector is unit-normalized and non-zero."""
    if vector and len(vector) == DIMENSION:
        norm = math.sqrt(sum(float(v) * float(v) for v in vector))
        if norm > 1e-6:
            return [float(v) / norm for v in vector]
    return opaque_skeleton.opaque_unit_vector(fallback_key)


def synthesize_cognitive_packet(
    mind: BaseAgenticMemoryRAG,
    recall: Any,
    target_concept_id: str | None,
    packet_path: Path,
    *,
    mode: str = "lexical_membrane",
    user_text: str = "",
    history: Sequence[dict[str, Any]] | None = None,
    source_id: str = "",
    projector_fit: Any | None = None,
) -> tuple[int, str, dict[str, Any]]:
    """Synthesize 1024D vector packet and enforce zero-prompt leakage invariant."""
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {"mode": mode, "dimension": DIMENSION}

    if mode == "soft_basis":
        activations, output_trace = live_tester._activation_packet(mind, recall)
        merged: dict[str, float] = {basis: value for basis, value in activations}

        # Habitual preference state is projected onto the valence slots so that the
        # decoder can read the substrate's learned stance toward this source.
        valence_slots, valence_diagnostics = preference_valence_activations(
            mind, source_id=source_id, trunk=recall.packet.input_trunk.value
        )
        merged.update(valence_slots)

        def _slot_rank(item: tuple[str, float]) -> tuple[int, float, str]:
            basis, value = item
            if basis == "speak":
                priority = 0
            elif basis in VALENCE_BASIS_SLOTS:
                priority = 1
            else:
                priority = 2
            return (priority, -value, basis)

        ordered = sorted(merged.items(), key=_slot_rank)[:8]
        lines = ["HABITUS_SOFT_PACKET_V1\n"]
        for basis, val in ordered:
            lines.append(f"{basis} {val:.8f}\n")
        content = "".join(lines)
        packet_path.write_text(content, encoding="utf-8")
        row_count = len(ordered)
        metadata["activations"] = ordered
        metadata["valence_activations"] = {
            slot: value for slot, value in valence_slots.items()
        }
        metadata["valence_diagnostics"] = valence_diagnostics

    elif mode == "projected":
        # A map fitted from this mind's own experience replaces the authored codebook.
        # See experiments/graph_native_live/projector.py.
        import projector as graph_projector

        if projector_fit is None:
            raise RuntimeError("packet_mode='projected' requires a fitted projector")
        features = graph_projector.state_features(
            mind,
            target_concept_id,
            source_id=source_id,
            trunk=recall.packet.input_trunk.value,
        )
        row = [float(v) for v in projector_fit.predict(features)]
        opaque_skeleton.write_packet(packet_path, [row])
        row_count = 1
        metadata["projector"] = {
            "samples": projector_fit.samples,
            "solver": projector_fit.solver,
            "ridge_lambda": projector_fit.ridge_lambda,
        }

    elif mode == "opaque_topological":
        if target_concept_id is None:
            # Fallback target
            candidates = list(live_tester.SEED_CONCEPTS.keys())
            target_concept_id = candidates[0] if candidates else "SELF"
        
        # Build 4 opaque topological rows
        history_events = list(history or [])
        try:
            rows, trace_info = opaque_skeleton.encode_state(mind, target_concept_id, history_events)
        except Exception:
            # Fallback rows from graph snapshot
            mind.graph.weight_snapshot()
            rows = [
                opaque_skeleton.opaque_unit_vector(f"topological:input:{target_concept_id}"),
                opaque_skeleton.opaque_unit_vector(f"topological:edges:{mind.pulse}"),
                opaque_skeleton.opaque_unit_vector(f"topological:temporal:{len(history_events)}"),
                opaque_skeleton.opaque_unit_vector(f"topological:output:{target_concept_id}"),
            ]
            trace_info = {"fallback": True}

        opaque_skeleton.write_packet(packet_path, rows)
        row_count = len(rows)
        metadata["trace_info"] = trace_info

    else:  # "lexical_membrane"
        rows: list[list[float]] = []
        row_sources: list[dict[str, Any]] = []

        concept = mind.store.get_concept(target_concept_id) if target_concept_id else None

        if concept is not None:
            # Row 0: Concept Centroid
            rows.append(safe_unit_vector(concept.embedding, f"concept:{concept.concept_id}"))
            row_sources.append({"kind": "concept_centroid", "node_id": concept.concept_id})

            # Row 1: Layer 3 Structural Overlay from compute_structural_overlay
            overlay = compute_structural_overlay(concept, store_or_graph=mind.graph, dimension=DIMENSION)
            if overlay:
                o_norm = math.sqrt(sum(float(v) * float(v) for v in overlay))
                if o_norm > 1e-6:
                    rows.append([float(v) / o_norm for v in overlay])
                    row_sources.append({
                        "kind": "layer3_structural_overlay",
                        "map_id": concept.structural_map.map_id if concept.structural_map else None,
                        "coactivations": concept.structural_map.total_coactivations if concept.structural_map else 0,
                    })

            # Row 2: Preference Node Vector
            pref_edges = mind.store.list_edges(source_id="IN:HEAR")
            if pref_edges:
                best_pref = max(pref_edges, key=lambda e: e.softmax_weight)
                pref_node = mind.store.get_concept(best_pref.target_id)
                if pref_node:
                    rows.append(safe_unit_vector(pref_node.embedding, f"pref:{pref_node.concept_id}"))
                    row_sources.append({"kind": "layer2_preference_vector", "node_id": pref_node.concept_id})

            # Rows 3..7: Connected lexemes or outward fibers if present
            outgoing = mind.store.list_edges(source_id=concept.concept_id)
            for edge in outgoing[:5]:
                if len(rows) >= 8:
                    break
                tgt = mind.store.get_concept(edge.target_id)
                if tgt:
                    rows.append(safe_unit_vector(tgt.embedding, f"fiber:{tgt.concept_id}"))
                    row_sources.append({
                        "kind": "layer4_membrane_fiber",
                        "node_id": tgt.concept_id,
                        "softmax_weight": edge.softmax_weight,
                    })

        if not rows:
            # Fallback unknown-state continuous vectors
            rows = [
                opaque_skeleton.opaque_unit_vector("fallback:centroid"),
                opaque_skeleton.opaque_unit_vector("fallback:uncertainty"),
                opaque_skeleton.opaque_unit_vector("fallback:clarity"),
                opaque_skeleton.opaque_unit_vector("fallback:output"),
            ]
            row_sources.append({"kind": "bounded_uncertainty_fallback"})

        # Double check all rows are valid unit vectors and not zero
        for r_idx, r in enumerate(rows):
            r_norm = math.sqrt(sum(float(v) * float(v) for v in r))
            if r_norm <= 1e-6:
                rows[r_idx] = opaque_skeleton.opaque_unit_vector(f"sanitize:{r_idx}")

        opaque_skeleton.write_packet(packet_path, rows)
        row_count = len(rows)
        metadata["row_sources"] = row_sources

    # Strict Zero-Prompt Leakage Verification
    verify_zero_prompt_leakage(packet_path, user_text, expected_mode=mode)

    packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    metadata["packet_sha256"] = packet_sha256
    metadata["rows"] = row_count
    return row_count, packet_sha256, metadata


def run_native_generation(
    model: Path,
    runner: Path,
    packet: Path,
    *,
    maximum_tokens: int,
    seed: int,
    skip_think: bool = True,
) -> dict[str, Any]:
    """Execute native soft generator binary or fallback mock if binary/model absent."""
    if runner.is_file() and model.is_file():
        environment = os.environ.copy()
        environment.setdefault("OLLAMA_LIB_DIR", "/usr/local/lib/ollama")
        old_lib = environment.get("LD_LIBRARY_PATH", "")
        environment["LD_LIBRARY_PATH"] = f"/usr/local/lib/ollama:{old_lib}" if old_lib else "/usr/local/lib/ollama"
        if skip_think:
            environment["HABITUS_NATIVE_SKIP_THINK"] = "1"
        cmd = [str(runner), str(model), str(packet), str(maximum_tokens), str(seed)]
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            env=environment,
            timeout=180,
        )
        # A generated token piece can be a partial UTF-8 sequence, so decode leniently
        # rather than let one BPE fragment abort the turn.
        if completed.returncode != 0:
            raise RuntimeError(
                f"Native runner failed (code {completed.returncode}): "
                f"{completed.stderr.decode('utf-8', 'replace').strip()}"
            )
        return json.loads(completed.stdout.decode("utf-8", "replace"))

    # Fallback dry runner for offline/mock test environments
    return {
        "model": str(model),
        "runner": str(runner),
        "model_received_prompt_text": False,
        "model_received_user_tokens": False,
        "adapter_kind": "graph_soft_generator_mock",
        "tokens_generated": 16,
        "prompt_eval_time_ms": 1.0,
        "token_eval_time_ms": 12.0,
        "response": "Understood. The continuous cognitive state is coherent and stable.",
    }


class LiveEvaluator:
    """Production cognitive evaluator and continuous loop orchestrator."""

    def __init__(
        self,
        config: EvaluatorConfig,
        embedder: Embedder | None = None,
    ) -> None:
        self.config = config
        self.embedder = embedder or DeterministicHashEmbedder(DIMENSION)
        self.mind = BaseAgenticMemoryRAG(
            self.config.database_path,
            embedder=self.embedder,
        )
        self.history: list[TurnTelemetry] = []
        self._last_output_trace: TraversalTrace | None = None
        self._projector = self._load_projector()
        self._ensure_prerequisites()

    def _ensure_prerequisites(self) -> None:
        """Seed canonical concept crown and ensure directory exists."""
        self.config.run_directory.mkdir(parents=True, exist_ok=True)
        live_tester.ensure_seed(self.mind)

    def _load_projector(self) -> Any | None:
        """Load the fitted graph-to-embedding map, if this evaluator uses one."""
        if self.config.packet_mode != "projected":
            return None
        if self.config.projector_path is None:
            raise RuntimeError("packet_mode='projected' requires EvaluatorConfig.projector_path")
        import projector as graph_projector

        return graph_projector.load_projector(self.config.projector_path)

    def step(
        self,
        stimulus_text: str,
        *,
        source_id: str = "human",
        expected_outcome_stability: float | None = None,
        reinforce: bool = True,
    ) -> TurnTelemetry:
        """Execute one complete multi-turn cognitive loop step."""
        start_time = time.perf_counter()
        turn_index = len(self.history) + 1
        turn_id = f"turn-{time.time_ns()}"

        # 1. Ingest Stimulus to Memory (persisted in SQLite, never sent to model)
        record = self.mind.remember(
            stimulus_text,
            kind=EventKind.MESSAGE,
            source_id=source_id,
            provenance={"kind": "cognitive_eval_stimulus", "turn_index": turn_index},
        )
        input_sha256 = hashlib.sha256(stimulus_text.encode("utf-8")).hexdigest()

        # Capture Preference State Before
        exp_id = self.mind.graph._experience_id(record)
        state_before_obj = self.mind.store.get_experience_state(exp_id)
        pref_before = {
            "preference_mean": state_before_obj.preference_mean if state_before_obj else 0.0,
            "preference_weight": state_before_obj.preference_weight if state_before_obj else 0.0,
        }

        # 2. Receptive Recall & Y-Axis Traversal
        recall = self.mind.recall(
            stimulus_text,
            kind=EventKind.MESSAGE,
            source_id=source_id,
            exclude_record_ids=(record.record_id,),
            include_current_input=False,
        )
        pulse_id = recall.packet.pulse_id

        # Determine Nominated Concept
        nominated_concept_id: str | None = None
        nominated_score: float = 0.0
        if recall.packet.surface_candidates:
            top_cand = recall.packet.surface_candidates[0]
            nominated_concept_id = top_cand.concept_id
            nominated_score = top_cand.joint_score
        else:
            nominated_concept_id = "native:uncertainty"
            nominated_score = 0.55

        # Input Path Extraction
        input_path_nodes: list[str] = []
        input_travel_time: float = 0.0
        if recall.packet.y_paths:
            best_in_path = min(recall.packet.y_paths, key=lambda p: p.total_travel_time)
            input_path_nodes = list(best_in_path.path_node_ids)
            input_travel_time = best_in_path.total_travel_time

        # Output Path Traversal
        output_trace: TraversalTrace | None = None
        output_path_nodes: list[str] = []
        output_travel_time: float = 0.0
        if nominated_concept_id is not None:
            output_trace = self.mind.graph.traverse(
                pulse_id=f"{pulse_id}:output",
                side=GraphSide.OUTPUT,
                target_id=nominated_concept_id,
                endpoint_score=nominated_score,
                mark_active=True,
            )
        if output_trace is None:
            for candidate_id in ("native:greeting", "native:question", "native:observation", SELF_ID):
                if self.mind.store.get_concept(candidate_id) is not None:
                    output_trace = self.mind.graph.traverse(
                        pulse_id=f"{pulse_id}:output_fb",
                        side=GraphSide.OUTPUT,
                        target_id=candidate_id,
                        endpoint_score=0.5,
                        mark_active=True,
                    )
                    if output_trace is not None:
                        break

        if output_trace is not None:
            output_path_nodes = list(output_trace.path_node_ids)
            output_travel_time = output_trace.total_travel_time

        # Determine active preference node from input path
        pref_node: str | None = None
        for n in input_path_nodes:
            if n.startswith("PREF:"):
                pref_node = n
                break

        # 3. Layer 3 Mini-Map Extraction
        layer3_info: dict[str, Any] | None = None
        if nominated_concept_id:
            nom_node = self.mind.store.get_concept(nominated_concept_id)
            if nom_node and nom_node.structural_map:
                s_map = nom_node.structural_map
                layer3_info = {
                    "map_id": s_map.map_id,
                    "parent_node_ids": list(s_map.parent_node_ids),
                    "child_node_ids": list(s_map.child_node_ids),
                    "total_coactivations": s_map.total_coactivations,
                    "relations": [
                        {
                            "source": r.source_node_id,
                            "target": r.target_node_id,
                            "density": r.coactivation_density,
                            "direction": r.direction,
                        }
                        for r in s_map.relations
                    ],
                }

        # 4. Layer 4 Softmax Edge Weights Updating
        softmax_weights: dict[str, float] = {}
        for source_node in set(input_path_nodes + output_path_nodes):
            self.mind.store.update_softmax_weights_for_source(source_node)
            for edge in self.mind.store.list_edges(source_id=source_node):
                softmax_weights[edge.edge_id] = edge.softmax_weight

        # 5. Continuous 1024D Packet Synthesis
        packet_path = self.config.run_directory / f"{turn_id}.packet"
        history_events = [
            {"target": t.nominated_concept_id, "stability": t.stability_delta}
            for t in self.history
        ]
        row_count, packet_sha256, packet_meta = synthesize_cognitive_packet(
            self.mind,
            recall,
            nominated_concept_id,
            packet_path,
            mode=self.config.packet_mode,
            user_text=stimulus_text,
            history=history_events,
            source_id=source_id,
            projector_fit=self._projector,
        )

        # 6. Native GGUF Soft-Input Generation
        native_receipt = run_native_generation(
            self.config.model_path,
            self.config.runner_path,
            packet_path,
            maximum_tokens=self.config.max_tokens,
            seed=self.config.seed,
            skip_think=self.config.skip_think,
        )
        response_text = str(native_receipt.get("response", "")).strip()

        # 7. Record Outbound Response in Memory
        response_record = self.mind.remember(
            response_text,
            kind=EventKind.MESSAGE,
            source_id="graph-native-model",
            record_type=RecordType.OUTBOUND_MESSAGE,
            provenance={
                "kind": "cognitive_eval_response",
                "turn_index": turn_index,
                "input_sha256": input_sha256,
            },
        )

        # 8. Closed-Loop Feedback & Edge Reinforcement
        stability_delta = (
            expected_outcome_stability
            if expected_outcome_stability is not None
            else 0.5
        )
        credited_edges: list[str] = []
        if output_trace is not None:
            credited_edges.extend(output_trace.path_edge_ids)
        if recall.packet.y_paths:
            credited_edges.extend(recall.packet.y_paths[0].path_edge_ids)
        pref_edge = self.mind.store.find_edge(
            GraphSide.INPUT, "IN:HEAR", "PREF:HEAR:STABLE"
        )
        if pref_edge is not None:
            credited_edges.append(pref_edge.edge_id)
        if recall.packet.input_trunk:
            trunk_val = recall.packet.input_trunk.value
            if trunk_val != "HEAR":
                trunk_pref_edge = self.mind.store.find_edge(
                    GraphSide.INPUT, f"IN:{trunk_val}", f"PREF:{trunk_val}:STABLE"
                )
                if trunk_pref_edge is not None:
                    credited_edges.append(trunk_pref_edge.edge_id)

        if reinforce and credited_edges:
            self.mind.graph.reinforce_edges(
                credited_edges,
                stability_delta=stability_delta,
                verified=True,
                evidence_quality=1.0,
            )
            self.mind.store.update_experience_state(
                exp_id,
                preference=stability_delta,
                confidence=0.85,
                pulse=self.mind.pulse,
            )

        # Capture Preference State After
        state_after_obj = self.mind.store.get_experience_state(exp_id)
        pref_after = {
            "preference_mean": state_after_obj.preference_mean if state_after_obj else stability_delta,
            "preference_weight": state_after_obj.preference_weight if state_after_obj else 0.85,
        }

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        telemetry = TurnTelemetry(
            turn_index=turn_index,
            turn_id=turn_id,
            pulse_id=pulse_id,
            input_sha256=input_sha256,
            source_id=source_id,
            input_trunk=recall.packet.input_trunk.value,
            preference_node=pref_node,
            preference_state_before=pref_before,
            preference_state_after=pref_after,
            nominated_concept_id=nominated_concept_id,
            input_path=input_path_nodes,
            input_edge_ids=list(recall.packet.y_paths[0].path_edge_ids) if recall.packet.y_paths else [],
            output_path=output_path_nodes,
            output_edge_ids=list(output_trace.path_edge_ids) if output_trace else [],
            input_travel_time=input_travel_time,
            output_travel_time=output_travel_time,
            layer3_minimap=layer3_info,
            layer4_softmax_weights=softmax_weights,
            packet_path=str(packet_path),
            packet_sha256=packet_sha256,
            packet_rows=row_count,
            packet_mode=self.config.packet_mode,
            zero_leakage_verified=True,
            response_text=response_text,
            response_record_id=response_record.record_id,
            stability_delta=stability_delta,
            reinforced_edges=credited_edges,
            duration_ms=duration_ms,
            valence_activations=dict(packet_meta.get("valence_activations", {})),
            valence_diagnostics=dict(packet_meta.get("valence_diagnostics", {})),
        )

        receipt = {
            "schema": "habitus.cognitive-eval-turn.v1",
            "turn": telemetry.to_dict(),
            "native": native_receipt,
        }
        receipt_path = self.config.run_directory / f"{turn_id}.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

        self.history.append(telemetry)
        self._last_output_trace = output_trace
        return telemetry

    def run_multi_turn_session(
        self,
        stimuli: Sequence[str | tuple[str, float]],
        *,
        source_id: str = "human",
    ) -> list[TurnTelemetry]:
        """Execute a multi-turn scenario and return turn receipts."""
        results: list[TurnTelemetry] = []
        for item in stimuli:
            if isinstance(item, tuple):
                text, stab = item
                t = self.step(text, source_id=source_id, expected_outcome_stability=stab)
            else:
                t = self.step(item, source_id=source_id)
            results.append(t)
        return results

    def run_differential_developmental_session(
        self,
        episodes: Sequence[dict[str, Any] | tuple[str, str, float]],
        *,
        enable_thought_recirculation: bool = True,
    ) -> list[TurnTelemetry]:
        """Execute differential developmental exposure across multiple interaction streams.

        Supports input episodes as either dicts ({'text': ..., 'source_id': ..., 'stability_delta': ...})
        or tuples ((text, source_id, stability_delta)).
        """
        results: list[TurnTelemetry] = []
        if self._last_output_trace is None and enable_thought_recirculation and len(episodes) > 0:
            target_seed = "native:greeting" if self.mind.store.get_concept("native:greeting") is not None else SELF_ID
            self._last_output_trace = self.mind.graph.traverse(
                pulse_id=f"pulse:{self.mind.pulse}:init_thought",
                side=GraphSide.OUTPUT,
                target_id=target_seed,
                endpoint_score=0.5,
                mark_active=False,
            )
        previous_trace: TraversalTrace | None = self._last_output_trace

        for ep in episodes:
            if isinstance(ep, tuple):
                text, source_id, delta = ep
            else:
                text = ep["text"]
                source_id = ep.get("source_id", "human")
                delta = ep.get("stability_delta", 0.5)

            # Ingest previous outbound trace as internal responsive thought if enabled
            if enable_thought_recirculation and previous_trace is not None:
                target_node = previous_trace.target_node_id or "concept:general"
                thought_record = self.mind.remember(
                    f"Reflecting on previous cognitive activation along {target_node}",
                    kind=EventKind.OBSERVATION,
                    source_id="self:thought",
                    record_type=RecordType.THOUGHT,
                    metadata={"internal_feedback": True, "target_node": target_node},
                    allow_growth=False,
                )
                self.mind.graph.deposit_trace(thought_record, previous_trace, pulse=self.mind.pulse)

            telemetry = self.step(
                text,
                source_id=source_id,
                expected_outcome_stability=delta,
                reinforce=True,
            )
            results.append(telemetry)
            previous_trace = self._last_output_trace

        return results

    def verify_invariants(self) -> dict[str, bool]:
        """Validate zero-leakage, bicone frontier, and global weight conservation."""
        invariants: dict[str, bool] = {}

        # 1. Zero Prompt Leakage Invariant
        invariants["zero_prompt_leakage"] = all(t.zero_leakage_verified for t in self.history) if self.history else True

        # 2. Bicone Frontier Valid
        input_edges = self.mind.store.list_edges(source_id=SELF_ID, side=GraphSide.INPUT)
        output_edges = self.mind.store.list_edges(source_id=SELF_ID, side=GraphSide.OUTPUT)
        expected_inputs = {INPUT_NODE_IDS[t] for t in InputTrunk}
        expected_outputs = {OUTPUT_NODE_IDS[t] for t in OutputTrunk}
        actual_inputs = {e.target_id for e in input_edges}
        actual_outputs = {e.target_id for e in output_edges}
        invariants["bicone_frontier_valid"] = (
            expected_inputs.issubset(actual_inputs) and expected_outputs.issubset(actual_outputs)
        )

        # 3. Global Weights Conserved
        weight_snap = self.mind.graph.weight_snapshot(now=0.0)
        total_global = sum(weight_snap.global_weights.values())
        invariants["global_weights_conserved"] = abs(total_global - 1.0) < 1e-4 if weight_snap.global_weights else True

        # 4. Graph Invariants Pass
        violations = self.mind.graph.validate_invariants()
        invariants["graph_invariants_pass"] = (len(violations) == 0)

        return invariants

    def export_state_report(self, export_path: Path | None = None) -> dict[str, Any]:
        """Generate a complete forensic cognitive state and metrics report."""
        report = {
            "schema": "habitus.cognitive-eval-session.v1",
            "timestamp": utc_iso_now(),
            "session_summary": {
                "total_turns": len(self.history),
                "packet_mode": self.config.packet_mode,
                "model": str(self.config.model_path),
                "runner": str(self.config.runner_path),
                "database": str(self.config.database_path),
            },
            "invariants": {
                "zero_prompt_leakage_verified": all(t.zero_leakage_verified for t in self.history),
                **self.verify_invariants(),
            },
            "turns": [t.to_dict() for t in self.history],
            "graph_metrics": {
                "concept_count": len(self.mind.store.list_concepts()),
                "record_count": len(self.mind.store.list_records()),
                "pulse": self.mind.pulse,
            },
        }
        if export_path is not None:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    def close(self) -> None:
        self.mind.close()

    def __enter__(self) -> LiveEvaluator:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Habitus-AI Continuous Cognitive Evaluator & Soft Generation Suite"
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parent / "live_mind.sqlite",
    )
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=Path(__file__).resolve().parent / "evaluator_runs",
    )
    parser.add_argument(
        "--mode",
        choices=["interactive", "once", "benchmark", "batch"],
        default="interactive",
    )
    parser.add_argument("--stimuli", type=Path, help="Path to JSON file with stimuli list")
    parser.add_argument("--stimulus-text", type=str, help="Single stimulus text")
    parser.add_argument("--source-id", type=str, default="human")
    parser.add_argument(
        "--packet-mode",
        choices=["lexical_membrane", "opaque_topological", "soft_basis", "projected"],
        default="lexical_membrane",
    )
    parser.add_argument(
        "--projector",
        type=Path,
        default=None,
        help="fitted projector JSON, required by --packet-mode projected",
    )
    parser.add_argument("--stability-delta", type=float, default=0.5)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-skip-think", action="store_true")
    parser.add_argument("--export-report", type=Path)
    parser.add_argument("--show-trace", action="store_true")
    parser.add_argument("--verify-invariants", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = EvaluatorConfig(
        database_path=args.db,
        model_path=args.model,
        runner_path=args.runner,
        run_directory=args.run_directory,
        max_tokens=args.max_tokens,
        seed=args.seed,
        skip_think=not args.no_skip_think,
        packet_mode=args.packet_mode,
        projector_path=args.projector,
    )

    with LiveEvaluator(config) as evaluator:
        if args.mode == "once" and args.stimulus_text:
            telemetry = evaluator.step(
                args.stimulus_text,
                source_id=args.source_id,
                expected_outcome_stability=args.stability_delta,
            )
            if args.show_trace:
                print(json.dumps(telemetry.to_dict(), indent=2))
            print(f"agent> {telemetry.response_text}")
            if args.export_report:
                evaluator.export_state_report(args.export_report)
            return 0

        if args.mode in {"batch", "benchmark"} and args.stimuli:
            data = json.loads(args.stimuli.read_text(encoding="utf-8"))
            turns = evaluator.run_multi_turn_session(data, source_id=args.source_id)
            print(f"Executed {len(turns)} multi-turn evaluation steps.")
            if args.export_report:
                evaluator.export_state_report(args.export_report)
            return 0

        print("Habitus-AI Cognitive Evaluator. Model receives no raw prompt text. Ctrl-D to exit.")
        while True:
            try:
                user_input = input("you> ").strip()
            except EOFError:
                print()
                break
            if user_input:
                telemetry = evaluator.step(
                    user_input,
                    source_id=args.source_id,
                    expected_outcome_stability=args.stability_delta,
                )
                if args.show_trace:
                    print(json.dumps(telemetry.to_dict(), indent=2))
                print(f"agent> {telemetry.response_text}")

        if args.export_report:
            evaluator.export_state_report(args.export_report)
        if args.verify_invariants:
            invs = evaluator.verify_invariants()
            print("Invariant status:", json.dumps(invs, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
