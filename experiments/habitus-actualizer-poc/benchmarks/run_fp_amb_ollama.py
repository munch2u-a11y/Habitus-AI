#!/usr/bin/env python3
"""Run FP-AMB with Ollama thinking disabled for answer-budget compatibility.

FP-AMB's evaluator limits local generation to 90 tokens. Thinking-capable
Qwen models can otherwise spend that entire allowance in the separate
``thinking`` field and return an empty answer. This runner changes only that
transport flag; the official evaluator still performs ingestion, prompting,
grading, diagnostics, and report generation.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import requests

from fp_amb.cli import load_provider_from_file
from fp_amb.evaluator import FPAMBEvaluator


class NonThinkingOllamaEvaluator(FPAMBEvaluator):
    """FP-AMB evaluator with visible-answer generation for thinking models."""

    def _query_llm(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1, "num_predict": 90},
        }
        for _ in range(3):
            try:
                response = requests.post(
                    self.ollama_url,
                    json=payload,
                    timeout=90,
                )
                if response.status_code == 200:
                    return response.json().get("response", "").strip()
            except Exception:
                time.sleep(1)
        return "[Connection Timeout]"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434/api/generate",
    )
    args = parser.parse_args()
    provider = load_provider_from_file(args.provider)
    evaluator = NonThinkingOllamaEvaluator(
        provider=provider,
        provider_name=provider.__class__.__name__,
        model_name=args.model,
        ollama_url=args.ollama_url,
        use_llm_generation=True,
    )
    evaluator.evaluate(output_path=args.output)


if __name__ == "__main__":
    main()
