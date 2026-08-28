from __future__ import annotations

import argparse
import os
from pathlib import Path

from .agent import HatchedAgent
from .gestation import TASTE_SCHEMAS, GestationProfile, gestate, load_profile
from .models import ModelUnavailableError, OllamaChatModel
from .pipeline import BaseAgenticMemoryRAG


DEFAULT_DATABASE = "agentic_memory.sqlite"


def _taste_prompt(default: str = "balanced") -> str:
    print("Choose a gentle initial taste. It is a bias, not a permanent personality:")
    keys = list(TASTE_SCHEMAS)
    for index, key in enumerate(keys, 1):
        schema = TASTE_SCHEMAS[key]
        print(f"  {index}. {schema.label}: {schema.description}")
    answer = input(f"Taste [{default}]: ").strip().casefold()
    if not answer:
        return default
    if answer.isdigit() and 1 <= int(answer) <= len(keys):
        return keys[int(answer) - 1]
    return answer


def _create_profile(
    mind: BaseAgenticMemoryRAG,
    *,
    human_name: str | None,
    agent_name: str | None,
    taste_schema: str | None,
    model_name: str | None,
) -> GestationProfile:
    human = human_name or input("Your name: ").strip()
    agent = agent_name or input("Agent name: ").strip()
    taste = taste_schema or _taste_prompt()
    model = model_name or input(
        f"Ollama model [{os.environ.get('OLLAMA_MODEL', 'granite4.1:8b')}]: "
    ).strip() or os.environ.get("OLLAMA_MODEL", "granite4.1:8b")
    return gestate(
        mind,
        human_name=human,
        agent_name=agent,
        taste_schema=taste,
        model_backend="ollama",
        model_name=model,
    )


def _setup_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--human-name")
    parser.add_argument("--agent-name")
    parser.add_argument("--taste", choices=tuple(TASTE_SCHEMAS))
    parser.add_argument("--model")


def gestate_main() -> None:
    parser = argparse.ArgumentParser(description="Gestate a persistent agent mind")
    _setup_arguments(parser)
    args = parser.parse_args()
    database = Path(args.database)
    with BaseAgenticMemoryRAG(database) as mind:
        existing = load_profile(mind)
        if existing is not None:
            print(
                f"{existing.agent_name} is already hatched in {database} "
                f"with the {existing.taste_schema} seed."
            )
            return
        profile = _create_profile(
            mind,
            human_name=args.human_name,
            agent_name=args.agent_name,
            taste_schema=args.taste,
            model_name=args.model,
        )
        print(
            f"{profile.agent_name} is ready to hatch beside {profile.human_name}. "
            f"Persistent mind: {database}"
        )


def _status(agent: HatchedAgent) -> None:
    store = agent.mind.store
    record_count = int(store.connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
    crown_count = len(store.list_concepts(kind="crown"))
    edge_count = len(store.list_edges())
    errors = agent.mind.graph.validate_invariants()
    state = "healthy" if not errors else "; ".join(errors)
    print(
        f"mind={agent.profile.agent_name} records={record_count} "
        f"concepts={crown_count} edges={edge_count} graph={state}"
    )


def hatch_main() -> None:
    parser = argparse.ArgumentParser(description="Hatch and talk with a persistent agent")
    _setup_arguments(parser)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--history-messages", type=int, default=8)
    args = parser.parse_args()
    database = Path(args.database)
    with BaseAgenticMemoryRAG(database) as mind:
        profile = load_profile(mind)
        if profile is None:
            profile = _create_profile(
                mind,
                human_name=args.human_name,
                agent_name=args.agent_name,
                taste_schema=args.taste,
                model_name=args.model,
            )
        model_name = args.model or profile.model_name
        if profile.model_backend != "ollama":
            raise SystemExit(f"unsupported configured model backend: {profile.model_backend}")
        model = OllamaChatModel(
            model_name,
            base_url=args.ollama_url,
            timeout_seconds=args.timeout,
        )
        agent = HatchedAgent(mind, model, history_messages=args.history_messages)
        print(
            f"{profile.agent_name} is awake with a persistent mind. "
            "Type /status or /quit."
        )
        while True:
            try:
                message = input(f"{profile.human_name}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not message:
                continue
            if message.casefold() in {"/quit", "/exit"}:
                break
            if message.casefold() == "/status":
                _status(agent)
                continue
            try:
                turn = agent.turn(message)
            except ModelUnavailableError as error:
                print(f"Model unavailable: {error}")
                continue
            print(f"{profile.agent_name}> {turn.response}")
            agent.acknowledge_delivery(turn, channel="terminal")


if __name__ == "__main__":
    hatch_main()
