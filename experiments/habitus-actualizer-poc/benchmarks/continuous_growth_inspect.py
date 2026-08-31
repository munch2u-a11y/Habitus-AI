#!/usr/bin/env python3
"""Inspect one persistent continuous mind without asking a model to judge it."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from habitus_actualizer import AbilityId, Actualizer, AgentLedger


def inspect(workspace: Path, state: Path, ledger_path: Path | None) -> dict:
    with Actualizer(workspace, state_path=state) as actualizer:
        store = actualizer.mind.store
        concepts = store.list_concepts()
        edges = store.list_edges()
        records = store.list_records()
        connection = store.connection
        input_depths = {"SELF": 0}
        for _ in range(len(concepts)):
            changed = False
            for edge in edges:
                if edge.side.value != "input" or edge.source_id not in input_depths:
                    continue
                proposed = input_depths[edge.source_id] + 1
                if proposed > input_depths.get(edge.target_id, -1):
                    input_depths[edge.target_id] = proposed
                    changed = True
            if not changed:
                break
        all_clusters = [
            cluster
            for parent in concepts
            for cluster in store.list_overlap_clusters(parent.concept_id)
        ]
        projections = {
            str(row["layer"]): int(row["count"])
            for row in connection.execute(
                """
                SELECT layer, COUNT(*) AS count
                FROM experience_projections GROUP BY layer ORDER BY layer
                """
            )
        }
        clusters = {
            "total": len(all_clusters),
            "promoted_children": sum(
                item.child_node_id is not None for item in all_clusters
            ),
            "semantic_ports": sum(
                item.semantic_node_id is not None for item in all_clusters
            ),
            "largest": [
                {
                    "cluster_id": item.cluster_id,
                    "parent_node_id": item.parent_node_id,
                    "experiences": len(item.experience_ids),
                    "preference_mean": round(item.preference_mean, 6),
                    "child_node_id": item.child_node_id,
                    "semantic_node_id": item.semantic_node_id,
                }
                for item in sorted(
                    all_clusters,
                    key=lambda candidate: (
                        -len(candidate.experience_ids),
                        candidate.cluster_id,
                    ),
                )[:12]
            ],
        }
        outcomes = {
            "total": int(connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]),
            "verified_returns": int(
                connection.execute(
                    "SELECT COUNT(*) FROM experience_cycle_returns WHERE verified = 1"
                ).fetchone()[0]
            ),
        }
        snapshot = actualizer.mind.graph.weight_snapshot()
        grouped = defaultdict(list)
        for edge in edges:
            grouped[(edge.side.value, edge.source_id)].append(edge.edge_id)
        sibling_deviation = max(
            (
                abs(sum(snapshot.local_weights.get(edge_id, 0.0) for edge_id in edge_ids) - 1.0)
                for edge_ids in grouped.values()
            ),
            default=0.0,
        )
        edge_rank = sorted(
            (
                {
                    "edge_id": edge.edge_id,
                    "side": edge.side.value,
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "log_strength": round(edge.log_strength, 8),
                    "conflict_penalty": round(edge.conflict_penalty, 8),
                    "local_probability": round(
                        snapshot.local_weights.get(edge.edge_id, 0.0), 8
                    ),
                }
                for edge in edges
            ),
            key=lambda item: (
                -(item["log_strength"] - item["conflict_penalty"]),
                item["edge_id"],
            ),
        )
        result = {
            "pulse_counter": actualizer.mind.pulse,
            "graph_health": actualizer.graph_health(),
            "concepts": {
                "total": len(concepts),
                "by_kind": dict(sorted(Counter(item.kind for item in concepts).items())),
                "children_by_depth": dict(
                    sorted(
                        Counter(
                            str(input_depths.get(item.concept_id, -1))
                            for item in concepts
                            if item.kind == "child"
                        ).items()
                    )
                ),
            },
            "edges": {
                "total": len(edges),
                "by_side": dict(
                    sorted(Counter(item.side.value for item in edges).items())
                ),
                "maximum_sibling_mass_deviation": sibling_deviation,
                "top_by_learned_strength": edge_rank[:12],
            },
            "records": {
                "total": len(records),
                "by_type": dict(
                    sorted(Counter(item.record_type.value for item in records).items())
                ),
            },
            "experience_projections_by_layer": projections,
            "overlap_clusters": clusters,
            "outcomes": outcomes,
            "ability_priors": {
                ability.value: {
                    "mass": actualizer.ability_prior(ability)[0],
                    "neutral": actualizer.ability_prior(ability)[1],
                }
                for ability in AbilityId
            },
        }
    if ledger_path is not None and ledger_path.exists():
        with AgentLedger(ledger_path) as ledger:
            cycles = ledger.list_cycles()
            result["host"] = {
                **ledger.status(),
                "cycle_statuses": dict(
                    sorted(Counter(item.status for item in cycles).items())
                ),
                "cycle_modes": dict(sorted(Counter(item.mode for item in cycles).items())),
                "receipt_count": sum(len(item.receipts) for item in cycles),
                "receipt_abilities": dict(
                    sorted(
                        Counter(
                            str(receipt.get("ability"))
                            for item in cycles
                            for receipt in item.receipts
                        ).items()
                    )
                ),
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--ledger")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = inspect(
        Path(args.workspace).expanduser().resolve(strict=True),
        Path(args.state).expanduser(),
        Path(args.ledger).expanduser() if args.ledger else None,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        target = Path(args.output).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
