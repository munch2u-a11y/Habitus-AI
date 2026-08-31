import asyncio

from habitus_actualizer import Actualizer, AgentOutputMiddleware


def test_framework_neutral_middleware_returns_observation(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            middleware = AgentOutputMiddleware(actualizer)
            result = await middleware.process(
                {"role": "assistant", "content": "I'll read `README.md`."}
            )
            assert result.observation["acted"] is True
            assert result.observation["results"][0]["verified"] is True
            assert result.observation["results"][0]["output"]["content"] == "hello"
            assert result.perception == (
                "I directly read README.md through the workspace read ability; "
                "I did not run a shell command:\nhello"
            )

    asyncio.run(scenario())


def test_middleware_does_not_execute_user_messages(tmp_path):
    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            result = await AgentOutputMiddleware(actualizer).process(
                {"role": "user", "content": "I'll list `.`."}
            )
            assert result.batch.receipts == ()
            assert result.observation["acted"] is False

    asyncio.run(scenario())


def test_list_perception_is_natural_and_contains_no_double_period(tmp_path):
    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            result = await AgentOutputMiddleware(actualizer).process(
                {"role": "assistant", "content": "I'll list `.`."}
            )
            assert result.perception.startswith("I looked in . and found:")
            assert ".." not in result.perception

    asyncio.run(scenario())
