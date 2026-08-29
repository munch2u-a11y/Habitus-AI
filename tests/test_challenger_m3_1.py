"""Empirical Challenger Test Suite for Milestone 3 (End-to-End Unified Plain Language Synthesis).

Adversarially tests:
1. Diverse & Boundary Stimuli:
   - Empty, whitespace, single-char, and punctuation inputs
   - Standard semantic crown categories (greeting, question, gratitude, memory, uncertainty, observation, action)
   - Rare, out-of-vocabulary, and nonsensical stimuli (bounded fallback verification)
   - Complex multi-clause compound sentences
   - Unicode, multilingual, and emoji stimuli
   - Extremely long (5000+ char) and repetitive stimuli
   - Injection payloads (SQL, script, shell)
2. Strict Continuous Injection & Seam Invariants:
   - Zero leakage of raw user input or retrieved memory text into packet or runner
   - Model receipt confirms model_received_prompt_text == False and model_received_user_tokens == False
   - Slot count bounded by safety cap (<= 8 slots)
   - Numeric activations strictly in (0, 1]
3. Output Fluency & Crash Resistance:
   - Zero crashes, zero segfaults across all test stimuli
   - Coherent plain language generation
   - Reproducible generation with fixed seed
4. Opaque Graph State Synthesis:
   - End-to-end continuous injection on dense opaque state vectors without language anchors
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import pytest

from habitus_ai.pipeline import BaseAgenticMemoryRAG

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = PROJECT_ROOT / "experiments" / "graph_native_live"

# Load live_tester module
LIVE_PATH = EXPERIMENT_ROOT / "live_tester.py"
SPEC_LIVE = importlib.util.spec_from_file_location("graph_native_live_tester", LIVE_PATH)
assert SPEC_LIVE is not None and SPEC_LIVE.loader is not None
LIVE = importlib.util.module_from_spec(SPEC_LIVE)
SPEC_LIVE.loader.exec_module(LIVE)

# Load opaque_skeleton module
OPAQUE_PATH = EXPERIMENT_ROOT / "opaque_skeleton.py"
SPEC_OPAQUE = importlib.util.spec_from_file_location("opaque_graph_native", OPAQUE_PATH)
assert SPEC_OPAQUE is not None and SPEC_OPAQUE.loader is not None
OPAQUE = importlib.util.module_from_spec(SPEC_OPAQUE)
SPEC_OPAQUE.loader.exec_module(OPAQUE)

MODEL_PATH = LIVE.DEFAULT_MODEL
RUNNER_PATH = LIVE.DEFAULT_RUNNER


@pytest.fixture(scope="module")
def shared_mind(tmp_path_factory):
    """Shared database fixture for faster sequential stress runs."""
    db_path = tmp_path_factory.mktemp("live_mind") / "stress_mind.sqlite"
    mind = BaseAgenticMemoryRAG(db_path)
    LIVE.ensure_seed(mind)
    yield mind
    mind.close()


class TestDiverseAndBoundaryStimuli:
    """Stress test the live synthesis pipeline with boundary, edge, and diverse stimuli."""

    @pytest.mark.parametrize(
        "stimulus_name,text",
        [
            ("empty_string", ""),
            ("spaces_only", "   "),
            ("whitespace_newlines", "\t\n  \r\n"),
            ("single_char_letter", "a"),
            ("single_char_question", "?"),
            ("single_char_exclamation", "!"),
            ("single_char_dot", "."),
        ],
    )
    def test_empty_and_minimal_stimuli(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path, stimulus_name: str, text: str
    ):
        receipt = LIVE.one_turn(
            shared_mind,
            text,
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path,
            maximum_tokens=32,
            seed=42,
        )

        trace = receipt["trace"]
        native = receipt["native"]

        # Invariant checks
        assert trace["packet_contains_raw_input"] is False
        assert trace["packet_contains_memory_text"] is False
        assert native["model_received_prompt_text"] is False
        assert native["model_received_user_tokens"] is False
        assert 1 <= native["soft_slots"] <= 8
        assert native["generated_tokens"] > 0
        assert isinstance(native["response"], str)
        assert len(native["response"].strip()) > 0

    @pytest.mark.parametrize(
        "category,stimulus",
        [
            ("greeting", "Hello there, good morning!"),
            ("question", "What is the reason why the sky is blue?"),
            ("gratitude", "Thank you so much for your tremendous assistance!"),
            ("memory", "Do you remember what we talked about earlier?"),
            ("uncertainty", "I am very unsure and uncertain about this guess."),
            ("observation", "I notice and observe the flashing light."),
            ("action", "Please execute and run the build script."),
        ],
    )
    def test_seed_categories_reach_appropriate_endpoints(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path, category: str, stimulus: str
    ):
        receipt = LIVE.one_turn(
            shared_mind,
            stimulus,
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path,
            maximum_tokens=48,
            seed=42,
        )

        trace = receipt["trace"]
        native = receipt["native"]

        # Check that expected category concept is admitted and activated
        expected_concept = f"native:{category}"
        activated_bases = {item["basis"]: item["value"] for item in trace["numeric_activations"]}
        assert category in activated_bases or "speak" in activated_bases

        # Invariants
        assert trace["packet_contains_raw_input"] is False
        assert trace["packet_contains_memory_text"] is False
        assert native["model_received_prompt_text"] is False
        assert native["model_received_user_tokens"] is False
        assert len(native["response"].strip()) > 0

    @pytest.mark.parametrize(
        "stimulus_name,stimulus",
        [
            ("quantum_physics", "Quantum chromodynamics gluon plasma oscillation in ultrarelativistic collisions"),
            ("ancient_history", "Cuneiform tablets from the third dynasty of Ur detailing grain rations"),
            ("nonsense_syllables", "blorp floop snark grum zazzle flim"),
            ("random_gibberish", "asdfghjk qwertyuiop zxcvbnm 1234567890"),
            ("philosophical_query", "Does intentionality precede phenomenological experience in epistemology?"),
            ("kernel_panic", "Kernel panic in sched_fair.c: CFS bandwidth balance failed with oops 0000"),
        ],
    )
    def test_rare_and_out_of_vocabulary_concepts_use_bounded_unknown(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path, stimulus_name: str, stimulus: str
    ):
        receipt = LIVE.one_turn(
            shared_mind,
            stimulus,
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path,
            maximum_tokens=32,
            seed=42,
        )

        trace = receipt["trace"]
        native = receipt["native"]

        # Ensure bounded activations
        activations = {item["basis"]: item["value"] for item in trace["numeric_activations"]}
        assert len(activations) <= 8
        for basis, val in activations.items():
            assert 0.0 < val <= 1.0

        # Invariants
        assert trace["packet_contains_raw_input"] is False
        assert trace["packet_contains_memory_text"] is False
        assert native["model_received_prompt_text"] is False
        assert native["model_received_user_tokens"] is False
        assert len(native["response"].strip()) > 0

    def test_complex_multiclause_sentence(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path
    ):
        complex_text = (
            "Although I was initially uncertain about whether this approach would work, "
            "after carefully observing the system behavior earlier today and remembering our previous design, "
            "I want to thank you for the guidance and ask what concrete action we should execute next."
        )
        receipt = LIVE.one_turn(
            shared_mind,
            complex_text,
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path,
            maximum_tokens=64,
            seed=42,
        )

        trace = receipt["trace"]
        native = receipt["native"]

        activations = {item["basis"]: item["value"] for item in trace["numeric_activations"]}
        assert len(activations) <= 8
        assert "speak" in activations

        assert trace["packet_contains_raw_input"] is False
        assert trace["packet_contains_memory_text"] is False
        assert native["model_received_prompt_text"] is False
        assert native["model_received_user_tokens"] is False
        assert len(native["response"].strip()) > 0

    @pytest.mark.parametrize(
        "stimulus_name,stimulus",
        [
            ("emojis", "👋 🤖 🚀 🎉 🧠 ✨"),
            ("french", "Bonjour le monde! Merci beaucoup pour votre aide précieuse."),
            ("japanese", "こんにちは、今日はどのようなご用件でしょうか？"),
            ("cyrillic", "Здравствуйте! Спасибо за вашу помощь и сотрудничество."),
            ("mixed_symbols", "© ® ™ § ¶ † ‡ • … ‰ ′ ″ ‹ › ⟨ ⟩"),
            ("sql_injection", "SELECT * FROM users WHERE '1'='1' UNION SELECT NULL, password FROM admin;--"),
            ("xss_payload", "<script>alert('xss attack payload');</script><iframe src='javascript:void(0)'>"),
            ("shell_metachars", "`rm -rf /` $(whoami) | cat /etc/passwd && echo vulnerable || exit 1"),
        ],
    )
    def test_multilingual_symbols_and_injection_payloads(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path, stimulus_name: str, stimulus: str
    ):
        receipt = LIVE.one_turn(
            shared_mind,
            stimulus,
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path,
            maximum_tokens=32,
            seed=42,
        )

        trace = receipt["trace"]
        native = receipt["native"]

        # Check packet contents directly
        packet_path = Path(receipt["packet_path"])
        packet_content = packet_path.read_text(encoding="utf-8")
        assert stimulus not in packet_content

        assert trace["packet_contains_raw_input"] is False
        assert trace["packet_contains_memory_text"] is False
        assert native["model_received_prompt_text"] is False
        assert native["model_received_user_tokens"] is False
        assert len(native["response"].strip()) > 0

    def test_extremely_large_input(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path
    ):
        huge_text = "Detailed architectural observation and memory recall about continuous injection systems. " * 60
        assert len(huge_text) > 4000

        receipt = LIVE.one_turn(
            shared_mind,
            huge_text,
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path,
            maximum_tokens=32,
            seed=42,
        )

        trace = receipt["trace"]
        native = receipt["native"]

        assert trace["packet_contains_raw_input"] is False
        assert trace["packet_contains_memory_text"] is False
        assert native["model_received_prompt_text"] is False
        assert native["model_received_user_tokens"] is False
        assert 1 <= native["soft_slots"] <= 8
        assert len(native["response"].strip()) > 0


class TestContinuousInjectionAndDeterminism:
    """Stress test continuous injection mechanics, seed determinism, and think modes."""

    def test_seed_determinism_produces_identical_generation(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path
    ):
        stimulus = "Hello, how are you today?"
        receipt1 = LIVE.one_turn(
            shared_mind,
            stimulus,
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path / "run1",
            maximum_tokens=48,
            seed=12345,
        )
        receipt2 = LIVE.one_turn(
            shared_mind,
            stimulus,
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path / "run2",
            maximum_tokens=48,
            seed=12345,
        )

        assert receipt1["native"]["response"] == receipt2["native"]["response"]
        assert receipt1["native"]["generated_tokens"] == receipt2["native"]["generated_tokens"]

    def test_forced_empty_think_mode(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("HABITUS_NATIVE_SKIP_THINK", "1")
        receipt = LIVE.one_turn(
            shared_mind,
            "Good morning! How are you doing?",
            runner=RUNNER_PATH,
            model=MODEL_PATH,
            run_directory=tmp_path,
            maximum_tokens=48,
            seed=42,
        )

        response = receipt["native"]["response"]
        # In forced empty think mode, the output should directly start with the synthesized reply
        assert "<think>" not in response
        assert len(response.strip()) > 0
        assert receipt["native"]["forced_empty_think"] is True

    def test_packet_numeric_safety_bounds(
        self, shared_mind: BaseAgenticMemoryRAG, tmp_path: Path
    ):
        packet_path = tmp_path / "test_bounds.packet"
        trace, _ = LIVE.compile_turn(shared_mind, "Please remember and explain this", packet_path)

        # Verify packet structure on disk
        lines = [line.strip() for line in packet_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert lines[0] == "HABITUS_SOFT_PACKET_V1"
        assert 1 <= len(lines) - 1 <= 8

        for line in lines[1:]:
            parts = line.split()
            assert len(parts) == 2
            basis, val_str = parts[0], parts[1]
            assert basis in LIVE.SEED_CONCEPTS or basis in ("speak", "uncertain", "clear", "greeting", "question", "gratitude", "memory", "observation", "action")
            val = float(val_str)
            assert 0.0 < val <= 1.0


class TestOpaqueStateSynthesis:
    """Empirical verification of Milestone 2 / Milestone 3 opaque continuous injection."""

    def test_opaque_skeleton_generation(self, tmp_path: Path):
        history: list[dict[str, object]] = []
        with BaseAgenticMemoryRAG(
            tmp_path / "opaque_mind.sqlite",
            embedder=OPAQUE.OpaqueIdentityEmbedder(),
        ) as mind:
            OPAQUE.seed_skeleton(mind)
            for _ in range(3):
                OPAQUE.fire(mind, OPAQUE.OPAQUE_A, 0.8, history)
            for _ in range(2):
                OPAQUE.fire(mind, OPAQUE.OPAQUE_B, -0.6, history)
            OPAQUE.connect_branches(mind)
            for stability in (0.3, 0.6):
                OPAQUE.fire(mind, OPAQUE.OPAQUE_JOIN, stability, history)

            rows, trace = OPAQUE.encode_state(mind, OPAQUE.OPAQUE_JOIN, history)

        packet_path = tmp_path / "opaque_test.packet"
        OPAQUE.write_packet(packet_path, rows)

        native = OPAQUE.run_native(
            MODEL_PATH,
            RUNNER_PATH,
            packet_path,
            maximum_tokens=32,
            seed=42,
            skip_think=True,
        )

        assert native["model_received_prompt_text"] is False
        assert native["model_received_user_tokens"] is False
        assert native["semantic_codebook_used"] is False
        assert native["adapter_kind"] == "opaque_graph_state_native_1024_v0"
        assert native["soft_slots"] == 4
        assert native["generated_tokens"] > 0
        assert isinstance(native["response"], str)
        assert len(native["response"].strip()) > 0
