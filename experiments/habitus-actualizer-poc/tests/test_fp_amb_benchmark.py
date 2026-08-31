import json
from argparse import Namespace

from benchmarks.fp_amb_growth import run


def test_fp_amb_probe_scores_the_exact_projected_context(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        "\n".join(
            json.dumps(item)
            for item in (
                {"text": "The amber launch code is ORBIT-73.", "speaker": "Josh"},
                {"text": "The greenhouse check is complete.", "speaker": "Rina"},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            [
                {
                    "id": "q1",
                    "category": "Single-Hop Fact Recall",
                    "question": "What is the amber launch code?",
                    "accepted_answers": ["ORBIT-73"],
                }
            ]
        ),
        encoding="utf-8",
    )
    args = Namespace(
        corpus=corpus,
        questions=questions,
        database=tmp_path / "mind.sqlite",
        growth=False,
        category="Single-Hop Fact Recall",
        ollama_model="",
        ollama_url="http://127.0.0.1:11434",
        timeout=1.0,
        context_tokens=1024,
        response_tokens=32,
        seed=7,
    )

    result = run(args)

    assert result["records_ingested"] == 2
    assert result["evidence_correct"] == 1
    assert result["evidence_accuracy"] == 1.0
    assert result["outcomes"][0]["record_ids"]
