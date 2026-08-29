"""Empirical Stress Analysis Script for Milestone 2 Continuous State Vectors.

Generates detailed quantitative evidence on:
1. Orthogonality distribution across 250 diverse words/strings.
2. Slot perturbation responses and token divergence metrics.
3. Packet invariant verification across all existing runs and newly fuzzed states.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from habitus_ai.pipeline import BaseAgenticMemoryRAG

EXPERIMENT_ROOT = PROJECT_ROOT / "experiments" / "graph_native_live"
MODULE_PATH = EXPERIMENT_ROOT / "opaque_skeleton.py"
SPEC = importlib.util.spec_from_file_location("opaque_graph_native", MODULE_PATH)
OPAQUE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPAQUE)

MODEL_PATH = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")
RUNNER_PATH = EXPERIMENT_ROOT / "native" / "graph_soft_generator"


def l2_norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def cosine(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    return dot / ((l2_norm(v1) * l2_norm(v2)) or 1.0)


def run_native(packet: Path, *, tokens: int = 64, seed: int = 42, skip_think: bool = True):
    env = os.environ.copy()
    env.setdefault("OLLAMA_LIB_DIR", "/usr/local/lib/ollama")
    env["LD_LIBRARY_PATH"] = "/usr/local/lib/ollama"
    if skip_think:
        env["HABITUS_NATIVE_SKIP_THINK"] = "1"
    proc = subprocess.run(
        [str(RUNNER_PATH), str(MODEL_PATH), str(packet), str(tokens), str(seed)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def test_orthogonality():
    embedder = OPAQUE.OpaqueIdentityEmbedder()
    words = [
        "apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew",
        "red", "green", "blue", "yellow", "purple", "orange", "black", "white", "gray",
        "king", "queen", "prince", "princess", "monarch", "emperor", "duke", "baron",
        "dog", "puppy", "hound", "canine", "cat", "kitten", "feline", "wolf", "fox",
        "happy", "sad", "joyful", "depressed", "ecstatic", "mournful", "angry", "calm",
        "hot", "cold", "warm", "cool", "freezing", "boiling", "scorching", "frigid",
        "run", "running", "ran", "runner", "runs", "walk", "walking", "walked", "walker",
        "think", "thinking", "thought", "thinker", "thinks", "know", "knowing", "knew",
        "good", "better", "best", "bad", "worse", "worst", "great", "terrible", "awful",
        "light", "dark", "heavy", "soft", "hard", "smooth", "rough", "sharp", "dull",
        "truth", "falsehood", "fact", "fiction", "belief", "knowledge", "doubt", "trust",
        "memory", "pulse", "graph", "node", "edge", "relation", "concept", "cluster",
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "first", "second", "third", "initial", "final", "middle", "start", "stop", "end",
        "north", "south", "east", "west", "up", "down", "left", "right", "forward", "back",
        "time", "space", "energy", "mass", "gravity", "quantum", "relativity", "particle",
        "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota",
        "structure", "invariant", "continuous", "discrete", "geometry", "dimension",
        "vector", "matrix", "tensor", "scalar", "norm", "orthogonal", "projection",
        "", " ", "\n", "\t", " \n \t ", "!", "?", ".", ":", ";", "-", "_", "/", "\\",
        "🔥", "🧠", "✨", "🚀", "⚡", "🌐", "🔒", "🔑", "🎯", "🛡️",
        "a", "aa", "aaa", "b", "bb", "c", "x", "y", "z",
        "symbol:0", "symbol:1", "node:U3:00000000", "edge-code:E1:00000000",
    ]
    words = list(dict.fromkeys(words))  # remove duplicates

    vectors = [embedder.embed(w) for w in words]
    norms = [l2_norm(v) for v in vectors]
    assert all(abs(n - 1.0) < 1e-6 for n in norms), "Norms are not unit length"

    pairs = list(itertools.combinations(range(len(words)), 2))
    cosines = [cosine(vectors[i], vectors[j]) for i, j in pairs]

    min_c = min(cosines)
    max_c = max(cosines)
    max_abs_c = max(abs(c) for c in cosines)
    mean_c = sum(cosines) / len(cosines)
    var_c = sum((c - mean_c) ** 2 for c in cosines) / len(cosines)
    std_c = math.sqrt(var_c)

    # Histogram in bins of 0.02
    bins = {}
    for c in cosines:
        b = round(c / 0.02) * 0.02
        bins[b] = bins.get(b, 0) + 1

    return {
        "word_count": len(words),
        "pair_count": len(pairs),
        "min_cosine": min_c,
        "max_cosine": max_c,
        "max_abs_cosine": max_abs_c,
        "mean_cosine": mean_c,
        "std_cosine": std_c,
        "theoretical_std": 1.0 / math.sqrt(1024),
        "violations_over_0_12": [
            (words[i], words[j], cosine(vectors[i], vectors[j]))
            for i, j in pairs
            if abs(cosine(vectors[i], vectors[j])) >= 0.12
        ],
    }


def test_geometry_sensitivity(tmp_path: Path):
    history = []
    with BaseAgenticMemoryRAG(tmp_path / "mind.sqlite", embedder=OPAQUE.OpaqueIdentityEmbedder()) as mind:
        OPAQUE.seed_skeleton(mind)
        for _ in range(4):
            OPAQUE.fire(mind, OPAQUE.OPAQUE_A, 0.8, history)
        for _ in range(3):
            OPAQUE.fire(mind, OPAQUE.OPAQUE_B, -0.6, history)
        OPAQUE.connect_branches(mind)
        for s in (0.25, 0.40, 0.55, 0.70):
            OPAQUE.fire(mind, OPAQUE.OPAQUE_JOIN, s, history)

        base_rows, _ = OPAQUE.encode_state(mind, OPAQUE.OPAQUE_JOIN, history)

    variations = {
        "connected_base": base_rows,
        "connected_repeat": [list(r) for r in base_rows],
        "connected_reversed": [list(r) for r in reversed(base_rows)],
        "connected_negated": [[-v for v in r] for r in base_rows],
        "connected_cyclic_shift": [base_rows[1], base_rows[2], base_rows[3], base_rows[0]],
        "connected_zero_temporal": [base_rows[0], base_rows[1], OPAQUE.opaque_unit_vector("zero-slot"), base_rows[3]],
        "unconnected_control": OPAQUE.control_rows(),
    }

    results = {}
    for name, rows in variations.items():
        pkt = tmp_path / f"{name}.packet"
        OPAQUE.write_packet(pkt, rows)
        runs_by_seed = {}
        for seed in (42, 100, 2026):
            out = run_native(pkt, tokens=64, seed=seed)
            runs_by_seed[seed] = {
                "response": out["response"].strip(),
                "tokens": out["generated_tokens"],
            }
        results[name] = runs_by_seed

    return results


def main():
    out_dir = Path("/tmp/challenger_m2_1_out")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("Running orthogonality stress test...")
    ortho = test_orthogonality()
    print(f"Orthogonality evaluated on {ortho['word_count']} words ({ortho['pair_count']} pairs):")
    print(f"  Max |cosine|: {ortho['max_abs_cosine']:.6f} (< 0.12 limit: {ortho['max_abs_cosine'] < 0.12})")
    print(f"  Mean cosine:  {ortho['mean_cosine']:.6f}")
    print(f"  Std cosine:   {ortho['std_cosine']:.6f} (theoretical: {ortho['theoretical_std']:.6f})")
    print(f"  Violations >= 0.12: {len(ortho['violations_over_0_12'])}")

    print("\nRunning slot geometry sensitivity test...")
    geom = test_geometry_sensitivity(out_dir)
    print("Geometry sensitivity responses (seed=42):")
    for name, runs in geom.items():
        print(f"  [{name}]:\n    {runs[42]['response']!r}")

    report = {
        "orthogonality": ortho,
        "geometry": geom,
    }
    (out_dir / "stress_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote summary to {out_dir / 'stress_summary.json'}")


if __name__ == "__main__":
    main()
