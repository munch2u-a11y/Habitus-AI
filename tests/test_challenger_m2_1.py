"""Empirical Challenger Test Suite for Milestone 2 Opaque Continuous State Vectors.

Adversarially tests:
1. Packet Invariants: HABITUS_OPAQUE_PACKET_V1 and HABITUS_SOFT_PACKET_V1 shape,
   dimension (1024), row counts (1-8), non-zero finite values, no NaN/Inf coordinates,
   and native runner strict parser rejection of malformed packets.
2. Orthogonality & Label Absence: OpaqueIdentityEmbedder orthogonality (|cosine| < 0.12)
   across comprehensive linguistic/adversarial string corpora, unit norm, determinism,
   and zero lexical/semantic label leakage in state traces and serialized payloads.
3. Row Order & Inversion Sensitivity: Transformer generation sensitivity to continuous
   slot geometry (exact repeat determinism, row reversals, sign inversions, cyclic shifts).
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import pytest

from habitus_ai.pipeline import BaseAgenticMemoryRAG

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = PROJECT_ROOT / "experiments" / "graph_native_live"
MODULE_PATH = EXPERIMENT_ROOT / "opaque_skeleton.py"
SPEC = importlib.util.spec_from_file_location("opaque_graph_native", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
OPAQUE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPAQUE)

MODEL_PATH = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")
RUNNER_PATH = EXPERIMENT_ROOT / "native" / "graph_soft_generator"


# ==============================================================================
# Helper Functions
# ==============================================================================

def compute_l2_norm(vector: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))


def compute_cosine(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = compute_l2_norm(v1)
    n2 = compute_l2_norm(v2)
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return dot / (n1 * n2)


def run_native_raw(
    packet_path: Path,
    *,
    maximum_tokens: int = 48,
    seed: int = 42,
    skip_think: bool = True,
) -> tuple[int, str, str]:
    """Execute graph_soft_generator directly and return (returncode, stdout, stderr)."""
    env = os.environ.copy()
    env.setdefault("OLLAMA_LIB_DIR", "/usr/local/lib/ollama")
    env["LD_LIBRARY_PATH"] = "/usr/local/lib/ollama"
    if skip_think:
        env["HABITUS_NATIVE_SKIP_THINK"] = "1"
    proc = subprocess.run(
        [
            str(RUNNER_PATH),
            str(MODEL_PATH),
            str(packet_path),
            str(maximum_tokens),
            str(seed),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ==============================================================================
# 1. Packet Invariants Stress Tests
# ==============================================================================

class TestPacketInvariants:
    """Stress-test HABITUS_OPAQUE_PACKET_V1 and HABITUS_SOFT_PACKET_V1."""

    def test_opaque_packet_invariants_across_developmental_states(self, tmp_path: Path):
        """Verify dimension 1024, exact row count, and no NaN/Inf under multiple topologies."""
        history: list[dict[str, object]] = []
        with BaseAgenticMemoryRAG(
            tmp_path / "mind.sqlite",
            embedder=OPAQUE.OpaqueIdentityEmbedder(),
        ) as mind:
            OPAQUE.seed_skeleton(mind)
            
            # State 1: Before join node creation (2 branch targets)
            for _ in range(3):
                OPAQUE.fire(mind, OPAQUE.OPAQUE_A, 0.7, history)
            for _ in range(2):
                OPAQUE.fire(mind, OPAQUE.OPAQUE_B, -0.5, history)
            
            rows_a, trace_a = OPAQUE.encode_state(mind, OPAQUE.OPAQUE_A, history)
            rows_b, trace_b = OPAQUE.encode_state(mind, OPAQUE.OPAQUE_B, history)

            # State 2: After connect branches and join node firing
            OPAQUE.connect_branches(mind)
            for s in (0.1, 0.3, 0.5, 0.8, -0.4):
                OPAQUE.fire(mind, OPAQUE.OPAQUE_JOIN, s, history)

            rows_join, trace_join = OPAQUE.encode_state(mind, OPAQUE.OPAQUE_JOIN, history)
            
            # State 3: Control rows
            ctrl_rows = OPAQUE.control_rows()

        for case_name, rows, trace in [
            ("branch_a", rows_a, trace_a),
            ("branch_b", rows_b, trace_b),
            ("join", rows_join, trace_join),
            ("control", ctrl_rows, {"rows": 4, "dimension": 1024}),
        ]:
            # Invariant 1: Exactly 4 rows generated for standard state slots
            assert len(rows) == 4, f"Case {case_name} has invalid row count {len(rows)}"
            assert trace["rows"] == 4
            assert trace["dimension"] == 1024

            for row_idx, row in enumerate(rows):
                # Invariant 2: Dimension is strictly 1024
                assert len(row) == 1024, f"Row {row_idx} in {case_name} has dimension {len(row)} != 1024"
                
                # Invariant 3: No NaN, Inf, or -Inf
                for col_idx, val in enumerate(row):
                    assert math.isfinite(val), f"Non-finite value {val} at ({row_idx}, {col_idx}) in {case_name}"
                    assert not math.isnan(val), f"NaN at ({row_idx}, {col_idx}) in {case_name}"
                
                # Invariant 4: Non-zero L2 norm, exactly unit length
                norm = compute_l2_norm(row)
                assert norm > 0.0, f"Zero norm row {row_idx} in {case_name}"
                assert abs(norm - 1.0) < 1e-4, f"Row {row_idx} norm {norm} is not unit normalized in {case_name}"

            # Invariant 5: Serialized packet header and content validation
            pkt_path = tmp_path / f"{case_name}.packet"
            OPAQUE.write_packet(pkt_path, rows)
            raw_content = pkt_path.read_text(encoding="ascii")
            lines = raw_content.splitlines()

            assert lines[0] == "HABITUS_OPAQUE_PACKET_V1"
            assert lines[1] == "1024 4"
            assert len(lines) == 6  # header + shape + 4 rows
            
            for line_idx, line in enumerate(lines[2:]):
                tokens = line.split()
                assert len(tokens) == 1024, f"Serialized line {line_idx} has {len(tokens)} tokens != 1024"
                for tok in tokens:
                    val = float(tok)
                    assert math.isfinite(val)

    def test_soft_packet_invariants_and_shape(self, tmp_path: Path):
        """Verify HABITUS_SOFT_PACKET_V1 format, basis vocabulary, and (0, 1] activation bounds."""
        valid_bases = {
            "speak", "greeting", "warm", "question", "clear",
            "memory", "uncertain", "gratitude", "observation", "action"
        }
        
        # Test valid soft packet
        soft_pkt = tmp_path / "valid_soft.packet"
        lines = [
            "HABITUS_SOFT_PACKET_V1",
            "greeting 0.850000",
            "warm 0.600000",
            "clear 0.400000",
        ]
        soft_pkt.write_text("\n".join(lines) + "\n", encoding="ascii")
        
        # Parse and verify invariants
        parsed_lines = [line.strip() for line in soft_pkt.read_text().splitlines() if line.strip()]
        assert parsed_lines[0] == "HABITUS_SOFT_PACKET_V1"
        activations = []
        for line in parsed_lines[1:]:
            parts = line.split()
            assert len(parts) == 2
            basis, val_str = parts[0], parts[1]
            assert basis in valid_bases, f"Basis {basis} not in valid basis set"
            val = float(val_str)
            assert math.isfinite(val)
            assert 0.0 < val <= 1.0, f"Activation {val} outside (0.0, 1.0]"
            activations.append((basis, val))
        
        assert 1 <= len(activations) <= 8

        # Run native runner to verify C++ parser accepts valid soft packet
        ret, stdout, stderr = run_native_raw(soft_pkt, maximum_tokens=16)
        assert ret == 0, f"Native runner failed on valid soft packet: {stderr}"
        resp_json = json.loads(stdout)
        assert resp_json["semantic_codebook_used"] is True
        assert resp_json["soft_slots"] == len(activations)
        assert resp_json["adapter_kind"] == "train_free_semantic_codebook_v0"

    def test_native_runner_rejects_malformed_opaque_packets(self, tmp_path: Path):
        """Adversarially probe native runner C++ safety bounds and error handling."""
        cases = [
            ("bad_header", "CORRUPT_HEADER_V1\n1024 4\n" + "0.1 " * 1024 + "\n", "unsupported graph packet header"),
            ("missing_shape", "HABITUS_OPAQUE_PACKET_V1\n", "opaque packet is missing its shape"),
            ("dimension_mismatch", "HABITUS_OPAQUE_PACKET_V1\n512 4\n" + ("0.1 " * 512 + "\n") * 4, "opaque graph width does not match"),
            ("dimension_zero", "HABITUS_OPAQUE_PACKET_V1\n0 4\n", "opaque packet shape is outside safety bounds"),
            ("rows_zero", "HABITUS_OPAQUE_PACKET_V1\n1024 0\n", "opaque packet shape is outside safety bounds"),
            ("rows_too_many", "HABITUS_OPAQUE_PACKET_V1\n1024 9\n" + ("0.1 " * 1024 + "\n") * 9, "opaque packet shape is outside safety bounds"),
            ("nan_value", "HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + ("0.1 " * 500 + "nan " + "0.1 " * 523 + "\n"), "opaque packet has missing or invalid values"),
            ("inf_value", "HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + ("0.1 " * 500 + "inf " + "0.1 " * 523 + "\n"), "opaque packet has missing or invalid values"),
            ("trailing_garbage", "HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + ("0.1 " * 1024 + "\n") + "extra_token\n", "opaque packet has trailing data"),
            ("truncated_row", "HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + "0.1 " * 1000 + "\n", "opaque packet has missing or invalid values"),
            ("zero_norm_row", "HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + "0.0 " * 1024 + "\n", "opaque packet contains a zero row"),
        ]

        for name, payload, expected_err_sub in cases:
            pkt = tmp_path / f"malformed_{name}.packet"
            pkt.write_text(payload, encoding="ascii")
            ret, stdout, stderr = run_native_raw(pkt, maximum_tokens=8)
            assert ret != 0, f"Expected non-zero returncode for {name}, but got 0. stdout={stdout}"
            assert expected_err_sub in stderr, f"Expected '{expected_err_sub}' in stderr for {name}. Got stderr: {stderr}"

    def test_native_runner_rejects_malformed_soft_packets(self, tmp_path: Path):
        """Adversarially probe native runner C++ validation for soft packets."""
        cases = [
            ("unknown_basis", "HABITUS_SOFT_PACKET_V1\nunknown_basis 0.5\n", "unknown semantic basis"),
            ("negative_activation", "HABITUS_SOFT_PACKET_V1\ngreeting -0.2\n", "activation must be in (0, 1]"),
            ("zero_activation", "HABITUS_SOFT_PACKET_V1\ngreeting 0.0\n", "activation must be in (0, 1]"),
            ("overflow_activation", "HABITUS_SOFT_PACKET_V1\ngreeting 1.5\n", "activation must be in (0, 1]"),
            ("nan_activation", "HABITUS_SOFT_PACKET_V1\ngreeting nan\n", ("activation must be in (0, 1]", "malformed activation line")),
            ("empty_activations", "HABITUS_SOFT_PACKET_V1\n# only comments\n", "graph packet has no activations"),
            ("too_many_slots", "HABITUS_SOFT_PACKET_V1\n" + "\n".join(f"greeting 0.{i}" for i in range(1, 10)) + "\n", "graph packet exceeds the eight-slot safety cap"),
            ("trailing_tokens", "HABITUS_SOFT_PACKET_V1\ngreeting 0.5 extra\n", "malformed activation line"),
        ]

        for name, payload, expected_err_sub in cases:
            pkt = tmp_path / f"malformed_soft_{name}.packet"
            pkt.write_text(payload, encoding="ascii")
            ret, stdout, stderr = run_native_raw(pkt, maximum_tokens=8)
            assert ret != 0, f"Expected non-zero returncode for {name}, but got 0"
            if isinstance(expected_err_sub, tuple):
                assert any(sub in stderr for sub in expected_err_sub), (
                    f"Expected one of {expected_err_sub} in stderr for {name}. Got: {stderr}"
                )
            else:
                assert expected_err_sub in stderr, f"Expected '{expected_err_sub}' in stderr for {name}. Got: {stderr}"


# ==============================================================================
# 2. Orthogonality & Label Absence Stress Tests
# ==============================================================================

class TestOrthogonalityAndLabelAbsence:
    """Stress-test OpaqueIdentityEmbedder orthogonality (|cosine| < 0.12) and label absence."""

    def test_opaque_identity_embedder_orthogonality_across_diverse_corpus(self):
        """Assert |cosine| < 0.12 across a wide corpus of semantic synonyms, morphology, edge strings."""
        embedder = OPAQUE.OpaqueIdentityEmbedder()

        corpus = [
            # Semantic synonyms and related concepts
            "hello", "greeting", "hi", "welcome", "salutations",
            "good", "great", "excellent", "superb", "wonderful",
            "bad", "terrible", "horrible", "awful", "poor",
            "dog", "puppy", "canine", "hound", "mutt",
            "cat", "kitten", "feline",
            "king", "queen", "monarch", "emperor", "ruler",
            "hot", "warm", "boiling", "scorching",
            "cold", "freezing", "chilly", "frigid",
            "happy", "joyful", "glad", "cheerful", "ecstatic",
            "sad", "depressed", "sorrowful", "mournful", "unhappy",
            "fast", "quick", "swift", "rapid", "speedy",
            "slow", "sluggish", "gradual", "leisurely",

            # Morphological variations and prefix/suffix stems
            "walk", "walking", "walked", "walker", "walks",
            "think", "thinking", "thought", "thinker", "thinks",
            "run", "running", "ran", "runner", "runs",
            "embed", "embedding", "embedded", "embedder", "embeddings",
            "test", "testing", "tested", "tester", "pretest", "retest",

            # Substrings and overlaps
            "a", "aa", "aaa", "aaaa", "b", "ab", "ba",
            "0", "1", "10", "100", "01",
            
            # Punctuation, symbols, emojis, whitespace
            "", " ", "   ", "\n", "\t", " \n \t ",
            "!", "?", "...", ":-)", "🔥", "🧠", "✨", "🚀",

            # Complex / structured strings
            '{"key": "value", "id": 1}',
            "SELECT * FROM memory WHERE pulse > 10;",
            "def test_function(x): return x * 2",
            "A" * 500,  # Long string
            "The quick brown fox jumps over the lazy dog.",
        ]

        # Invariant 1: Determinism & Unit Norm
        embeddings = {}
        for text in corpus:
            v1 = embedder.embed(text)
            v2 = embedder.embed(text)
            assert v1 == v2, f"Embedding not deterministic for {text!r}"
            assert len(v1) == 1024, f"Dimension {len(v1)} != 1024 for {text!r}"
            
            norm = compute_l2_norm(v1)
            assert abs(norm - 1.0) < 1e-6, f"Norm {norm} != 1.0 for {text!r}"
            for val in v1:
                assert math.isfinite(val)
            embeddings[text] = v1

        # Invariant 2: Pairwise Orthogonality (|cosine| < 0.12)
        pairs = list(itertools.combinations(corpus, 2))
        cosines = []
        violations = []
        for t1, t2 in pairs:
            v1 = embeddings[t1]
            v2 = embeddings[t2]
            cos = compute_cosine(v1, v2)
            cosines.append(cos)
            if abs(cos) >= 0.12:
                violations.append((t1, t2, cos))

        assert len(violations) == 0, f"Found {len(violations)} pairs violating |cosine| < 0.12: {violations[:5]}"

        # Statistical properties check
        mean_cos = sum(cosines) / len(cosines)
        variance = sum((c - mean_cos) ** 2 for c in cosines) / len(cosines)
        std_cos = math.sqrt(variance)
        max_abs_cos = max(abs(c) for c in cosines)

        # In 1024D, random unit vectors have std dev ~ 1 / sqrt(1024) = 0.03125
        assert abs(mean_cos) < 0.005, f"Mean cosine {mean_cos} deviates significantly from 0.0"
        assert 0.025 < std_cos < 0.040, f"Standard deviation {std_cos} deviates from expected 0.03125"
        assert max_abs_cos < 0.12, f"Max absolute cosine {max_abs_cos} >= 0.12"

    def test_label_absence_in_state_encoding_and_serialization(self, tmp_path: Path):
        """Verify zero lexical anchor or semantic label leakage in encoded state traces and payloads."""
        history: list[dict[str, object]] = []
        with BaseAgenticMemoryRAG(
            tmp_path / "mind.sqlite",
            embedder=OPAQUE.OpaqueIdentityEmbedder(),
        ) as mind:
            OPAQUE.seed_skeleton(mind)
            OPAQUE.fire(mind, OPAQUE.OPAQUE_A, 0.8, history)
            OPAQUE.fire(mind, OPAQUE.OPAQUE_B, -0.6, history)
            OPAQUE.connect_branches(mind)
            OPAQUE.fire(mind, OPAQUE.OPAQUE_JOIN, 0.4, history)
            
            rows, trace = OPAQUE.encode_state(mind, OPAQUE.OPAQUE_JOIN, history)

        # Assert trace contains NO semantic labels or language anchors
        assert trace["semantic_labels"] == []
        assert trace["language_anchors"] == []
        
        # Serialize packet and verify raw payload
        pkt_path = tmp_path / "opaque_check.packet"
        OPAQUE.write_packet(pkt_path, rows)
        payload = pkt_path.read_text(encoding="ascii")
        
        # The payload must contain strictly the header "HABITUS_OPAQUE_PACKET_V1", dimensions, and ASCII numbers
        lines = payload.splitlines()
        assert lines[0] == "HABITUS_OPAQUE_PACKET_V1"
        assert lines[1] == "1024 4"
        for line in lines[2:]:
            for token in line.split():
                # Every token must be a valid float representation (digits, '.', '-', 'e')
                float_val = float(token)
                assert math.isfinite(float_val)
                # Ensure no alphabetic characters other than 'e' for exponent
                cleaned = token.lower().replace("e", "").replace("-", "").replace("+", "").replace(".", "")
                assert cleaned.isdigit(), f"Non-numeric character in token: {token}"


# ==============================================================================
# 3. Row Order & Inversion Sensitivity Stress Tests
# ==============================================================================

@pytest.fixture(scope="module")
def prepared_packets(tmp_path_factory) -> tuple[Path, Path, Path, Path, Path]:
    """Generate base, repeat, reversed, negated, and cyclically shifted packets."""
    tmp_dir = tmp_path_factory.mktemp("geom_packets")
    history: list[dict[str, object]] = []
    with BaseAgenticMemoryRAG(
        tmp_dir / "mind.sqlite",
        embedder=OPAQUE.OpaqueIdentityEmbedder(),
    ) as mind:
        OPAQUE.seed_skeleton(mind)
        for _ in range(4):
            OPAQUE.fire(mind, OPAQUE.OPAQUE_A, 0.8, history)
        for _ in range(3):
            OPAQUE.fire(mind, OPAQUE.OPAQUE_B, -0.6, history)
        OPAQUE.connect_branches(mind)
        for s in (0.25, 0.40, 0.55, 0.70):
            OPAQUE.fire(mind, OPAQUE.OPAQUE_JOIN, s, history)

        base_rows, _ = OPAQUE.encode_state(mind, OPAQUE.OPAQUE_JOIN, history)

    repeat_rows = [list(r) for r in base_rows]
    reversed_rows = [list(r) for r in reversed(base_rows)]
    negated_rows = [[-v for v in r] for r in base_rows]
    shifted_rows = [base_rows[1], base_rows[2], base_rows[3], base_rows[0]]

    p_base = tmp_dir / "base.packet"
    p_repeat = tmp_dir / "repeat.packet"
    p_rev = tmp_dir / "reversed.packet"
    p_neg = tmp_dir / "negated.packet"
    p_shift = tmp_dir / "shifted.packet"

    OPAQUE.write_packet(p_base, base_rows)
    OPAQUE.write_packet(p_repeat, repeat_rows)
    OPAQUE.write_packet(p_rev, reversed_rows)
    OPAQUE.write_packet(p_neg, negated_rows)
    OPAQUE.write_packet(p_shift, shifted_rows)

    return p_base, p_repeat, p_rev, p_neg, p_shift


class TestContinuousSlotGeometrySensitivity:
    """Stress-test transformer generation sensitivity to continuous slot geometry."""

    def test_transformer_exact_repeat_determinism(self, prepared_packets):
        """Identical packet with identical seed must yield byte-for-byte identical output."""
        p_base, p_repeat, _, _, _ = prepared_packets
        
        for seed in (42, 100, 2026):
            ret1, out1, err1 = run_native_raw(p_base, maximum_tokens=64, seed=seed)
            ret2, out2, err2 = run_native_raw(p_repeat, maximum_tokens=64, seed=seed)

            assert ret1 == 0, f"Error on p_base: {err1}"
            assert ret2 == 0, f"Error on p_repeat: {err2}"

            j1 = json.loads(out1)
            j2 = json.loads(out2)

            assert j1["response"] == j2["response"], f"Non-deterministic generation for seed {seed}"
            assert j1["generated_tokens"] == j2["generated_tokens"]

    def test_transformer_sensitivity_to_row_reversal(self, prepared_packets):
        """Reversing row order ([s0, s1, s2, s3] -> [s3, s2, s1, s0]) must alter generation."""
        p_base, _, p_rev, _, _ = prepared_packets

        divergences = 0
        seeds = [42, 123, 456, 789]
        for seed in seeds:
            ret_base, out_base, _ = run_native_raw(p_base, maximum_tokens=64, seed=seed)
            ret_rev, out_rev, _ = run_native_raw(p_rev, maximum_tokens=64, seed=seed)

            assert ret_base == 0
            assert ret_rev == 0

            resp_base = json.loads(out_base)["response"].strip()
            resp_rev = json.loads(out_rev)["response"].strip()

            if resp_base != resp_rev:
                divergences += 1

        # All or vast majority of seeds must produce distinct outputs
        assert divergences >= len(seeds) - 1, (
            f"Row reversal did not produce distinct outputs across seeds: {divergences}/{len(seeds)} diverged"
        )

    def test_transformer_sensitivity_to_sign_inversion(self, prepared_packets):
        """Sign-inverting continuous vectors ([s0, s1, s2, s3] -> [-s0, -s1, -s2, -s3]) must alter generation."""
        p_base, _, _, p_neg, _ = prepared_packets

        divergences = 0
        seeds = [42, 123, 456, 789]
        for seed in seeds:
            ret_base, out_base, _ = run_native_raw(p_base, maximum_tokens=64, seed=seed)
            ret_neg, out_neg, _ = run_native_raw(p_neg, maximum_tokens=64, seed=seed)

            assert ret_base == 0
            assert ret_neg == 0

            resp_base = json.loads(out_base)["response"].strip()
            resp_neg = json.loads(out_neg)["response"].strip()

            if resp_base != resp_neg:
                divergences += 1

        assert divergences >= len(seeds) - 1, (
            f"Sign inversion did not produce distinct outputs across seeds: {divergences}/{len(seeds)} diverged"
        )

    def test_transformer_sensitivity_to_cyclic_row_shifts(self, prepared_packets):
        """Cyclically shifting rows must alter generation, confirming positional slot sensitivity."""
        p_base, _, _, _, p_shift = prepared_packets

        divergences = 0
        seeds = [42, 123, 456, 789]
        for seed in seeds:
            ret_base, out_base, _ = run_native_raw(p_base, maximum_tokens=64, seed=seed)
            ret_shift, out_shift, _ = run_native_raw(p_shift, maximum_tokens=64, seed=seed)

            assert ret_base == 0
            assert ret_shift == 0

            resp_base = json.loads(out_base)["response"].strip()
            resp_shift = json.loads(out_shift)["response"].strip()

            if resp_base != resp_shift:
                divergences += 1

        assert divergences >= len(seeds) - 1, (
            f"Cyclic shift did not produce distinct outputs across seeds: {divergences}/{len(seeds)} diverged"
        )
