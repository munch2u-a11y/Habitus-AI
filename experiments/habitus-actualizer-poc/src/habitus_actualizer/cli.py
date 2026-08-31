from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .policy import WorkspacePolicy
from .runtime import Actualizer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="habitus-actualize",
        description="Actualize a bounded workspace ability from ordinary assistant prose.",
    )
    parser.add_argument("text", nargs="*", help="assistant output; stdin is used when omitted")
    parser.add_argument("--workspace", default=".", help="workspace authority root")
    parser.add_argument("--state", help="persistent SQLite state path")
    parser.add_argument("--allow-write", action="store_true", help="enable atomic file writes")
    parser.add_argument(
        "--allow-command",
        action="append",
        default=[],
        metavar="NAME",
        help="allow one executable basename; may be repeated",
    )
    parser.add_argument("--dry-run", action="store_true", help="route and validate without execution")
    parser.add_argument("--threshold", type=float, default=0.72)
    parser.add_argument("--max-abilities", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = " ".join(args.text).strip() if args.text else sys.stdin.read().strip()
    if not text:
        raise SystemExit("assistant text is required")
    workspace = Path(args.workspace).expanduser().resolve(strict=True)
    policy = WorkspacePolicy(
        workspace,
        allow_write=args.allow_write,
        allowed_commands=WorkspacePolicy.normalize_allowed_commands(args.allow_command),
    )
    with Actualizer(
        workspace,
        state_path=args.state,
        policy=policy,
        confidence_threshold=args.threshold,
        maximum_abilities=args.max_abilities,
    ) as actualizer:
        batch = actualizer.actualize_sync(text, dry_run=args.dry_run)
        print(batch.to_json())
    if any(receipt.status != "success" for receipt in batch.receipts):
        return 2
    if batch.suppressed and not batch.receipts:
        return 3
    return 0
