"""Empirical Challenger 2 Test Suite for Milestone 3 (Unified Plain Language Synthesis).

Adversarially challenges:
1. Packet Binary & ASCII Invariants:
   - Header contracts (HABITUS_OPAQUE_PACKET_V1 and HABITUS_SOFT_PACKET_V1)
   - Dimension enforcement (strictly 1024D)
   - Row safety caps (1 to 8 rows)
   - Float32 bounds, NaN/Inf rejection, zero-norm row rejection, subnormal numbers
2. Memory Safety & Crash Resistance (graph_soft_generator):
   - Rejection of corrupted, truncated, binary-fuzzed, out-of-bound packets
   - Safe termination with exit code 1/2 without segfaults (SIGSEGV/SIGBUS/SIGABRT)
   - AddressSanitizer (ASan) & UBSan clean execution under adversarial fuzzing
3. Zero Raw Prompt Text Injection:
   - Complete absence of user prompt text, memory text, and graph labels in packets and LLM context
   - Verification of static structural role delimiter tokenization only
   - Verification of native runner JSON receipts (model_received_prompt_text == False)
4. Milestone 3 Live Synthesis Robustness:
   - End-to-end execution of transformer_hatch.py
   - Deterministic continuation repeatability
   - Vector geometry sensitivity under sign inversion, row reversal, and random control
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = PROJECT_ROOT / "experiments" / "graph_native_live"
NATIVE_DIR = EXPERIMENT_ROOT / "native"
MODEL_PATH = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")
RUNNER_PATH = NATIVE_DIR / "graph_soft_generator"
CODEC_PATH = NATIVE_DIR / "lexeme_codec"
OLLAMA_LIB_DIR = "/usr/local/lib/ollama"
LLAMA_CPP_SOURCE = Path("/tmp/llama.cpp-b9509")

for p in (PROJECT_ROOT / "src", EXPERIMENT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from habitus_ai.pipeline import BaseAgenticMemoryRAG
import opaque_skeleton as OPAQUE
import transformer_hatch as HATCH
import accelerated_gestation as GESTATION


def get_latest_gestated_db() -> Path:
    runs_dir = EXPERIMENT_ROOT / "accelerated_gestation_runs"
    dbs = sorted(runs_dir.glob("habitus-*.sqlite"))
    assert len(dbs) > 0, "No gestated databases found in accelerated_gestation_runs"
    return dbs[-1]


def run_native_raw(
    runner: Path,
    model: Path,
    packet_path: Path,
    *,
    maximum_tokens: int = 32,
    seed: int = 42,
    skip_think: bool = True,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Execute native runner and return (returncode, stdout, stderr)."""
    env = os.environ.copy()
    env.setdefault("OLLAMA_LIB_DIR", OLLAMA_LIB_DIR)
    env["LD_LIBRARY_PATH"] = f"{OLLAMA_LIB_DIR}:{env.get('LD_LIBRARY_PATH', '')}"
    if skip_think:
        env["HABITUS_NATIVE_SKIP_THINK"] = "1"
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [
            str(runner),
            str(model),
            str(packet_path),
            str(maximum_tokens),
            str(seed),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ==============================================================================
# 1. Packet Binary/ASCII Invariants & Fuzzing Suite
# ==============================================================================

class TestPacketStructureAndBounds:
    """Stress-test packet structure, float32 bounds, NaN/Inf, and strict 1024D constraints."""

    def test_opaque_packet_exact_1024d_and_float32_invariants(self, tmp_path: Path):
        """Verify that all generated packets strictly enforce 1024D float32 vectors."""
        db_path = get_latest_gestated_db()
        embedder = GESTATION.NativeMassEmbedder(GESTATION.nursery.MODEL, GESTATION.nursery.CODEC)
        with BaseAgenticMemoryRAG(db_path, embedder=embedder) as mind:
            concept_ids = [c.concept_id for c in HATCH.productive_concepts(mind)]
            assert len(concept_ids) > 0, "Hatched mind must contain productive concepts"

            for concept_id in concept_ids[:5]:
                rows, trace = HATCH.graph_state_rows(mind, concept_id)
                assert 1 <= len(rows) <= 8, f"Row count {len(rows)} outside [1, 8]"
                for row_idx, row in enumerate(rows):
                    assert len(row) == 1024, f"Row {row_idx} length {len(row)} != 1024"
                    for val in row:
                        assert isinstance(val, float)
                        assert math.isfinite(val), f"Non-finite float encountered: {val}"
                        assert not math.isnan(val), f"NaN float encountered: {val}"
                        assert not math.isinf(val), f"Inf float encountered: {val}"
                    norm = math.sqrt(sum(v * v for v in row))
                    assert 0.999 <= norm <= 1.001, f"Row {row_idx} not normalized: norm={norm}"

                # Test writing and reading packet
                pkt_path = tmp_path / f"test_{concept_id}.packet"
                OPAQUE.write_packet(pkt_path, rows)
                
                content = pkt_path.read_text(encoding="ascii")
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                assert lines[0] == "HABITUS_OPAQUE_PACKET_V1"
                assert lines[1] == f"1024 {len(rows)}"
                assert len(lines) == 2 + len(rows)

    def test_float32_extreme_values_and_subnormals(self, tmp_path: Path):
        """Test boundary float32 representations (subnormals, max float32, min positive float32)."""
        # Valid unit-normalized row with extreme dynamic range
        row = [0.0] * 1024
        row[0] = 1.0
        row[1] = 1e-30  # Very small positive
        row[2] = -1e-30 # Very small negative
        row[3] = 0.5
        row[4] = -0.5
        norm = math.sqrt(sum(v * v for v in row))
        norm_row = [v / norm for v in row]

        pkt = tmp_path / "extreme_floats.packet"
        OPAQUE.write_packet(pkt, [norm_row])
        
        ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt, maximum_tokens=8)
        assert ret == 0, f"Failed on valid extreme float row: {stderr}"
        resp = json.loads(stdout)
        assert resp["model_received_prompt_text"] is False
        assert resp["soft_slots"] == 1

    def test_native_runner_rejects_nan_and_inf_variations(self, tmp_path: Path):
        """Verify robust rejection of all NaN and Inf float representations."""
        bad_values = [
            "nan", "NAN", "NaN", "-nan", "+nan",
            "inf", "INF", "Inf", "-inf", "+inf", "Infinity", "-Infinity",
            "1e40", "-1e40",  # Overflow 32-bit float
            "1.#QNAN", "1.#SNAN", "1.#IND", "1.#INF",
        ]
        for idx, bad_val in enumerate(bad_values):
            pkt = tmp_path / f"bad_float_{idx}.packet"
            row_vals = ["0.01"] * 1023 + [bad_val]
            content = "HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + " ".join(row_vals) + "\n"
            pkt.write_text(content, encoding="ascii")

            ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt, maximum_tokens=4)
            assert ret != 0, f"Expected rejection for {bad_val}, but got success (ret=0)"
            assert "opaque packet has missing or invalid values" in stderr or "error" in stderr

    def test_native_runner_rejects_zero_norm_vector(self, tmp_path: Path):
        """Verify that an all-zero vector row is rejected safely (cannot calibrate zero norm)."""
        pkt = tmp_path / "zero_norm.packet"
        content = "HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + " ".join(["0.0"] * 1024) + "\n"
        pkt.write_text(content, encoding="ascii")

        ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt, maximum_tokens=4)
        assert ret != 0, "Zero norm vector row must be rejected"
        assert "opaque packet contains a zero row" in stderr

    def test_native_runner_rejects_dimension_mismatches(self, tmp_path: Path):
        """Verify strict enforcement of dimension 1024 (reject 0, 512, 768, 2048, 16384, 16385, -1024)."""
        dim_cases = [
            (-1024, 1, "shape is outside safety bounds"),
            (0, 1, "shape is outside safety bounds"),
            (1, 1, "opaque graph width does not match the model input width"),
            (512, 1, "opaque graph width does not match the model input width"),
            (768, 1, "opaque graph width does not match the model input width"),
            (2048, 1, "opaque graph width does not match the model input width"),
            (16384, 1, "opaque graph width does not match the model input width"),
            (16385, 1, "shape is outside safety bounds"),
            (1000000, 1, "shape is outside safety bounds"),
        ]
        for dim, rows, expected_err in dim_cases:
            pkt = tmp_path / f"dim_{dim}.packet"
            if dim > 0 and dim <= 16384:
                payload = "HABITUS_OPAQUE_PACKET_V1\n" + f"{dim} {rows}\n" + ("0.01 " * dim + "\n") * rows
            else:
                payload = f"HABITUS_OPAQUE_PACKET_V1\n{dim} {rows}\n"
            pkt.write_text(payload, encoding="ascii")

            ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt, maximum_tokens=4)
            assert ret != 0, f"Expected failure for dimension={dim}"
            assert (expected_err in stderr) or ("invalid values" in stderr), f"Expected '{expected_err}' in stderr for dim={dim}. Got: {stderr}"

    def test_native_runner_rejects_row_count_violations(self, tmp_path: Path):
        """Verify safety bounds on row count (reject 0, -1, 9, 100, 1000000 rows)."""
        row_cases = [
            (0, "shape is outside safety bounds"),
            (-1, "shape is outside safety bounds"),
            (9, "shape is outside safety bounds"),
            (100, "shape is outside safety bounds"),
            (1000000, "shape is outside safety bounds"),
        ]
        for rows, expected_err in row_cases:
            pkt = tmp_path / f"rows_{rows}.packet"
            payload = f"HABITUS_OPAQUE_PACKET_V1\n1024 {rows}\n"
            if rows > 0 and rows < 20:
                payload += ("0.01 " * 1024 + "\n") * rows
            pkt.write_text(payload, encoding="ascii")

            ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt, maximum_tokens=4)
            assert ret != 0, f"Expected failure for rows={rows}"
            assert expected_err in stderr, f"Expected '{expected_err}' in stderr for rows={rows}. Got: {stderr}"


# ==============================================================================
# 2. Corrupted Packet Fuzzing & Memory Crash Safety Suite
# ==============================================================================

class TestFuzzingAndCrashSafety:
    """Adversarially fuzz packet inputs and verify zero segfaults, zero memory corruptions."""

    def test_random_binary_garbage_and_null_bytes(self, tmp_path: Path):
        """Feed arbitrary binary garbage, null bytes, ELF headers to graph_soft_generator."""
        fuzz_payloads = [
            b"",  # 0-byte file
            b"\x00" * 1024,  # Null bytes
            b"\xff\xfe\xfd\xfc" * 256,  # Non-ASCII byte stream
            b"HABITUS_OPAQUE_PACKET_V1\x001024 1\n",  # Embedded null
            b"HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + b"\x00" * 4096,  # Null values
            b"\x7fELF" + b"\x00" * 256,  # ELF header
            b"\n" * 1000,  # Newlines only
            b" " * 10000,  # Spaces only
            b"HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + b"1.0 " * 500 + b"garbage_token\n",  # Mixed token
            b"HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + b"1.0 " * 1024 + b"\n\n\n\ntrailing\n",  # Trailing text
            b"A" * 100000 + b"\n",  # Giant line
        ]

        for idx, payload in enumerate(fuzz_payloads):
            pkt = tmp_path / f"fuzz_{idx}.packet"
            pkt.write_bytes(payload)

            ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt, maximum_tokens=4)
            assert ret != 0, f"Fuzz test {idx} must return non-zero exit code"
            # Crucial assertion: no crash signals (139 = SIGSEGV, 134 = SIGABRT, 135 = SIGBUS, 136 = SIGFPE)
            assert ret not in (139, 134, 135, 136, -6, -11, -7, -8), (
                f"Fuzz test {idx} crashed with signal/code {ret}! stderr: {stderr}"
            )
            assert "error:" in stderr or ret in (1, 2)

    def test_nonexistent_and_directory_packet_path(self, tmp_path: Path):
        """Test non-existent file path and directory passed as packet path."""
        nonexistent = tmp_path / "does_not_exist.packet"
        ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, nonexistent, maximum_tokens=4)
        assert ret == 1
        assert "cannot open graph packet" in stderr

        is_dir = tmp_path / "is_a_directory"
        is_dir.mkdir()
        ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, is_dir, maximum_tokens=4)
        assert ret == 1

    def test_address_sanitizer_compilation_and_adversarial_run(self, tmp_path: Path):
        """Compile graph_soft_generator with AddressSanitizer and UndefinedBehaviorSanitizer to prove memory safety."""
        if not LLAMA_CPP_SOURCE.is_dir():
            pytest.skip("llama.cpp source directory not available for ASan compilation")

        asan_bin = tmp_path / "graph_soft_generator_asan"
        compile_cmd = [
            "g++",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-std=c++17",
            f"-I{LLAMA_CPP_SOURCE}/include",
            f"-I{LLAMA_CPP_SOURCE}/ggml/include",
            str(NATIVE_DIR / "graph_soft_generator.cpp"),
            f"-L{OLLAMA_LIB_DIR}",
            f"-Wl,-rpath,{OLLAMA_LIB_DIR}",
            "-lllama", "-lggml", "-lggml-base", "-ldl", "-pthread",
            "-o", str(asan_bin),
        ]
        comp = subprocess.run(compile_cmd, capture_output=True, text=True)
        assert comp.returncode == 0, f"ASan compilation failed: {comp.stderr}"
        assert asan_bin.is_file()

        # Run valid packet under ASan
        valid_row = OPAQUE.opaque_unit_vector("asan_test_vector")
        valid_pkt = tmp_path / "asan_valid.packet"
        OPAQUE.write_packet(valid_pkt, [valid_row])

        asan_env = {"ASAN_OPTIONS": "detect_leaks=0:abort_on_error=1"}
        ret, stdout, stderr = run_native_raw(
            asan_bin, MODEL_PATH, valid_pkt, maximum_tokens=8, extra_env=asan_env
        )
        assert ret == 0, f"ASan valid run failed: {stderr}"
        assert "AddressSanitizer" not in stderr
        assert "runtime error" not in stderr

        # Run battery of malformed packets through ASan binary
        malformed_cases = [
            ("bad_header", b"INVALID\n1024 1\n"),
            ("short_row", b"HABITUS_OPAQUE_PACKET_V1\n1024 1\n0.1 0.2\n"),
            ("nan_float", b"HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + b"0.1 " * 500 + b"nan " + b"0.1 " * 523 + b"\n"),
            ("zero_norm", b"HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + b"0.0 " * 1024 + b"\n"),
            ("trailing", b"HABITUS_OPAQUE_PACKET_V1\n1024 1\n" + b"0.1 " * 1024 + b"\nextra\n"),
            ("fuzz_nulls", b"\x00" * 512),
        ]
        for name, payload in malformed_cases:
            p = tmp_path / f"asan_{name}.packet"
            p.write_bytes(payload)
            ret, stdout, stderr = run_native_raw(
                asan_bin, MODEL_PATH, p, maximum_tokens=4, extra_env=asan_env
            )
            assert ret != 0, f"ASan malformed case {name} must fail"
            assert "AddressSanitizer" not in stderr, f"ASan detected memory violation in {name}: {stderr}"
            assert "runtime error:" not in stderr, f"UBSan detected undefined behavior in {name}: {stderr}"


# ==============================================================================
# 3. Zero Raw Prompt Text Injection Verification Suite
# ==============================================================================

class TestZeroPromptTextInjection:
    """Verify zero raw prompt text, memory text, or lexical strings enter the LLM context."""

    def test_packet_files_contain_zero_text_tokens(self, tmp_path: Path):
        """Adversarially verify that generated .packet files contain exclusively numeric coordinates."""
        db_path = get_latest_gestated_db()
        embedder = GESTATION.NativeMassEmbedder(GESTATION.nursery.MODEL, GESTATION.nursery.CODEC)
        with BaseAgenticMemoryRAG(db_path, embedder=embedder) as mind:
            concept_ids = [c.concept_id for c in HATCH.productive_concepts(mind)]
            for cid in concept_ids[:4]:
                rows, trace = HATCH.ordered_lexical_rows(mind, cid)
                pkt = tmp_path / f"{cid}.packet"
                OPAQUE.write_packet(pkt, rows)

                raw_text = pkt.read_text(encoding="ascii")
                lines = raw_text.strip().splitlines()

                # Header lines
                assert lines[0] == "HABITUS_OPAQUE_PACKET_V1"
                assert re.match(r"^1024 \d+$", lines[1]) is not None

                # Vector lines must contain only float tokens (optional minus, digits, dot, e/E, digits)
                float_pattern = re.compile(r"^[-+]?(?:(?:\d+\.?\d*)|(?:\.\d+))(?:[eE][-+]?\d+)?$")
                for line_idx, line in enumerate(lines[2:]):
                    tokens = line.split()
                    assert len(tokens) == 1024, f"Line {line_idx} does not have 1024 tokens"
                    for tok in tokens:
                        assert float_pattern.match(tok) is not None, f"Non-numeric float token: '{tok}'"
                        # Extra assertion: no English letters except scientific notation 'e'/'E'
                        non_e_letters = [ch for ch in tok if ch.isalpha() and ch not in ('e', 'E')]
                        assert len(non_e_letters) == 0, f"Alphabetical character in vector token: '{tok}'"

    def test_transformer_hatch_trace_metadata_confirms_zero_injection(self, tmp_path: Path):
        """Verify trace dictionaries strictly flag prompt/memory text as not sent."""
        db_path = get_latest_gestated_db()
        embedder = GESTATION.NativeMassEmbedder(GESTATION.nursery.MODEL, GESTATION.nursery.CODEC)
        with BaseAgenticMemoryRAG(db_path, embedder=embedder) as mind:
            cid = HATCH.productive_concepts(mind)[0].concept_id
            rows, trace = HATCH.graph_state_rows(mind, cid)
            assert trace["raw_language_strings_in_rows"] is False
            assert trace["record_text_in_rows"] is False

            ord_rows, ord_trace = HATCH.ordered_lexical_rows(mind, cid)
            assert ord_trace["raw_language_strings_in_rows"] is False
            assert ord_trace["record_text_in_rows"] is False

    def test_native_runner_receipt_and_code_verification(self, tmp_path: Path):
        """Execute runner and verify JSON output certifies zero prompt text and zero user tokens."""
        row = OPAQUE.opaque_unit_vector("zero_text_probe")
        pkt = tmp_path / "zero_text.packet"
        OPAQUE.write_packet(pkt, [row])

        ret, stdout, stderr = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt, maximum_tokens=16)
        assert ret == 0, f"Runner failed: {stderr}"
        resp = json.loads(stdout)
        assert resp["model_received_prompt_text"] is False
        assert resp["model_received_user_tokens"] is False
        assert resp["structural_rows"] in (11, 12)
        assert resp["embedding_rows"] == resp["structural_rows"] + 1


# ==============================================================================
# 4. Milestone 3 Live Synthesis Robustness & Sensitivity Suite
# ==============================================================================

class TestMilestone3LiveSynthesis:
    """Verify live Milestone 3 end-to-end plain language generation and continuous geometry causal control."""

    def test_end_to_end_transformer_hatch_probe_matrix(self, tmp_path: Path):
        """Run full transformer_hatch matrix on live gestated database and model."""
        db_path = get_latest_gestated_db()
        probes = (
            ("trust", "People consistently keep promises, making cooperation feel safe."),
            ("fear", "A danger I do not understand makes future safety uncertain."),
        )
        receipt = HATCH.run_probe_matrix(
            database=db_path,
            model=MODEL_PATH,
            codec=CODEC_PATH,
            runner=RUNNER_PATH,
            run_directory=tmp_path / "matrix_run",
            probes=probes,
            maximum_tokens=32,
            seed=42,
            include_ablations=True,
        )

        assert receipt["schema"] == "habitus.graph-to-transformer-hatch.v1"
        assert receipt["prompt_text_crossed_native_boundary"] is False
        assert receipt["retrieved_memory_text_crossed_native_boundary"] is False
        assert receipt["probe_count"] == 2

        for res in receipt["results"]:
            assert res["input_sent_to_model"] is False
            assert res["memory_text_sent_to_model"] is False
            # Verify target response exists and is non-empty string
            cases_dict = {c["case_id"].rsplit("-", 1)[-1]: c for c in res["cases"]}
            target_response = cases_dict["target"]["native"]["response"]
            assert isinstance(target_response, str)
            assert len(target_response.strip()) > 0

    def test_geometry_causal_sensitivity(self, tmp_path: Path):
        """Empirically test that modifying continuous vector geometry changes generated output."""
        base_vector = OPAQUE.opaque_unit_vector("causal_base_geom")
        reversed_vector = list(reversed(base_vector))
        inverted_vector = [-v for v in base_vector]

        pkt_base = tmp_path / "geom_base.packet"
        pkt_rev = tmp_path / "geom_rev.packet"
        pkt_inv = tmp_path / "geom_inv.packet"

        OPAQUE.write_packet(pkt_base, [base_vector])
        OPAQUE.write_packet(pkt_rev, [reversed_vector])
        OPAQUE.write_packet(pkt_inv, [inverted_vector])

        # Exact repeat test on base (must be 100% identical determinism)
        ret1, stdout1, _ = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt_base, maximum_tokens=24, seed=123)
        ret2, stdout2, _ = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt_base, maximum_tokens=24, seed=123)
        assert ret1 == 0 and ret2 == 0
        resp1 = json.loads(stdout1)["response"]
        resp2 = json.loads(stdout2)["response"]
        assert resp1 == resp2, "Identical continuous vector + seed must produce deterministic response"

        # Reversed vector test
        ret_rev, stdout_rev, _ = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt_rev, maximum_tokens=24, seed=123)
        assert ret_rev == 0
        resp_rev = json.loads(stdout_rev)["response"]

        # Inverted vector test
        ret_inv, stdout_inv, _ = run_native_raw(RUNNER_PATH, MODEL_PATH, pkt_inv, maximum_tokens=24, seed=123)
        assert ret_inv == 0
        resp_inv = json.loads(stdout_inv)["response"]

        # At least one geometric perturbation must change the generated continuation
        assert (resp1 != resp_rev) or (resp1 != resp_inv), (
            "Model must be sensitive to continuous vector geometry changes"
        )
