import asyncio

from habitus_actualizer import Actualizer, AgentOutputMiddleware, WorkspacePolicy


def test_model_perception_contains_read_result_but_not_receipt_metadata(tmp_path):
    (tmp_path / "note.txt").write_text("VISIBLE-PROOF", encoding="utf-8")

    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            result = await AgentOutputMiddleware(actualizer).process(
                {"role": "assistant", "content": "I'll read `note.txt`."}
            )

            assert "VISIBLE-PROOF" in result.perception
            assert "note.txt" in result.perception
            assert str(tmp_path) not in result.perception
            assert "sha256" not in result.perception
            assert "receipt" not in result.perception.casefold()
            assert "verified" not in result.perception.casefold()
            assert "workspace read ability" in result.perception
            assert "did not run a shell command" in result.perception
            assert result.observation["results"][0]["verified"] is True
            assert result.observation["results"][0]["receipt_id"]

    asyncio.run(scenario())


def test_run_perception_exposes_program_output_not_process_ledger(tmp_path):
    (tmp_path / "report.py").write_text("print('RUN-PROOF')\n", encoding="utf-8")
    policy = WorkspacePolicy(tmp_path, allowed_commands=("python3",))

    async def scenario():
        async with Actualizer(tmp_path, policy=policy) as actualizer:
            result = await AgentOutputMiddleware(actualizer).process(
                {
                    "role": "assistant",
                    "content": "I'll run `python3 report.py`.",
                }
            )

            assert "RUN-PROOF" in result.perception
            assert "returncode" not in result.perception
            assert "duration_seconds" not in result.perception
            assert "argv" not in result.perception

    asyncio.run(scenario())


def test_failed_action_perception_sanitizes_the_workspace_root(tmp_path):
    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            result = await AgentOutputMiddleware(actualizer).process(
                {"role": "assistant", "content": "I'll read `missing.txt`."}
            )

            assert "failed" in result.perception.casefold()
            assert "missing.txt" in result.perception
            assert str(tmp_path) not in result.perception

    asyncio.run(scenario())
