from habitus_actualizer.continuous import AgentLedger
import json

from habitus_actualizer.continuous_cli import ENGAGED_BEHAVIOR, OllamaLanguageDriver, main


def test_send_cli_maps_to_message_event(tmp_path, capsys):
    assert main([
        "--workspace",
        str(tmp_path),
        "send",
        "hello",
        "--source",
        "Josh",
    ]) == 0

    with AgentLedger(tmp_path / ".habitus" / "agent-loop.sqlite") as ledger:
        events = ledger.list_events()
    assert events[0]["kind"] == "message"
    assert events[0]["source_id"] == "Josh"
    assert '"status": "queued"' in capsys.readouterr().out


def test_ollama_driver_can_trace_exact_frame_without_adding_tools(tmp_path, monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps(
                {
                    "message": {"content": "A grounded response."},
                    "prompt_eval_count": 42,
                    "eval_count": 7,
                }
            ).encode("utf-8")

    monkeypatch.setattr(
        "habitus_actualizer.continuous_cli.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(),
    )
    trace = tmp_path / "trace.jsonl"
    driver = OllamaLanguageDriver("test-model", trace_jsonl=trace)

    assert driver._generate_sync("Exact JIT frame", "engaged") == "A grounded response."

    recorded = json.loads(trace.read_text(encoding="utf-8"))
    assert recorded["frame"] == "Exact JIT frame"
    assert recorded["response"] == "A grounded response."
    assert recorded["tools_field_present"] is False
    assert recorded["prompt_eval_count"] == 42


def test_engaged_behavior_expresses_read_as_natural_language_not_shell():
    assert "I'll read `path`" in ENGAGED_BEHAVIOR
    assert "I do not replace" in ENGAGED_BEHAVIOR
    assert "a bare command" in ENGAGED_BEHAVIOR
