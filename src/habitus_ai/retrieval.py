from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import replace
from typing import Iterable, Sequence

from .embeddings import cosine_similarity, tokenize
from .graph import GraphRuntime
from .store import MindStore
from .surface import SemanticSurface
from .types import (
    EventKind,
    GraphSide,
    InputTrunk,
    MemoryRecord,
    RetrievalHit,
    RetrievalPacket,
    SurfaceCandidate,
    TraversalTrace,
)


def bm25_scores(query: str, records: Sequence[MemoryRecord]) -> dict[str, float]:
    if not records:
        return {}
    query_terms = tokenize(query)
    if not query_terms:
        return {record.record_id: 0.0 for record in records}
    tokenized = {record.record_id: tokenize(record.text) for record in records}
    document_frequency: Counter[str] = Counter()
    for terms in tokenized.values():
        document_frequency.update(set(terms))
    average_length = sum(len(terms) for terms in tokenized.values()) / max(1, len(records))
    k1, b = 1.5, 0.75
    scores: dict[str, float] = {}
    for record in records:
        terms = tokenized[record.record_id]
        frequencies = Counter(terms)
        score = 0.0
        for term in query_terms:
            df = document_frequency.get(term, 0)
            idf = math.log(1.0 + (len(records) - df + 0.5) / (df + 0.5))
            tf = frequencies.get(term, 0)
            denominator = tf + k1 * (1.0 - b + b * len(terms) / max(1.0, average_length))
            if denominator:
                score += idf * (tf * (k1 + 1.0)) / denominator
        scores[record.record_id] = score
    maximum = max(scores.values(), default=0.0)
    if maximum > 0.0:
        scores = {record_id: score / maximum for record_id, score in scores.items()}
    return scores


class RetrievalEngine:
    def __init__(
        self,
        store: MindStore,
        graph: GraphRuntime,
        surface: SemanticSurface,
        *,
        direct_top_k: int = 3,
        direct_similarity_floor: float = 0.08,
        direct_diversity_ceiling: float = 0.96,
        maximum_surface_candidates: int = 8,
        maximum_paths: int = 4,
        maximum_expansions: int = 4,
        base_context_chars: int = 3200,
        maximum_context_chars: int = 6400,
    ):
        self.store = store
        self.graph = graph
        self.surface = surface
        self.direct_top_k = max(1, direct_top_k)
        self.direct_similarity_floor = max(0.0, min(1.0, direct_similarity_floor))
        self.direct_diversity_ceiling = direct_diversity_ceiling
        self.maximum_surface_candidates = max(2, maximum_surface_candidates)
        self.maximum_paths = max(1, maximum_paths)
        self.maximum_expansions = max(0, maximum_expansions)
        self.base_context_chars = max(512, base_context_chars)
        self.maximum_context_chars = max(self.base_context_chars, maximum_context_chars)

    def _direct_hits(
        self,
        query_embedding: Sequence[float],
        records: Sequence[MemoryRecord],
        excluded: set[str],
    ) -> list[RetrievalHit]:
        ranked = sorted(
            (
                (cosine_similarity(query_embedding, record.embedding), record)
                for record in records
                if record.record_id not in excluded
            ),
            key=lambda item: (-item[0], item[1].record_id),
        )
        selected: list[RetrievalHit] = []
        for score, record in ranked:
            if score < self.direct_similarity_floor:
                continue
            if any(
                cosine_similarity(record.embedding, prior.record.embedding)
                >= self.direct_diversity_ceiling
                and record.text.casefold() == prior.record.text.casefold()
                for prior in selected
            ):
                continue
            selected.append(
                RetrievalHit(record, "direct", float(score), 0.0)
            )
            if len(selected) >= self.direct_top_k:
                break
        return selected

    @staticmethod
    def _endpoint_count(candidates: Sequence[SurfaceCandidate]) -> int:
        """Let X-axis ambiguity decide how many semantic endpoints are admitted."""
        if not candidates:
            return 0
        entropy = SemanticSurface.normalized_entropy(candidates)
        return max(1, int(math.ceil(1.0 + entropy * 2.0)))

    def _traces(
        self,
        pulse_id: str,
        trunk: InputTrunk,
        candidates: Sequence[SurfaceCandidate],
    ) -> list[TraversalTrace]:
        # The semantic surface (X) has already ranked endpoint relevance. Freeze
        # that decision before traversal so Y resistance can choose only the
        # route to an admitted endpoint, never replace it with a cheaper target.
        limit = min(
            self.maximum_paths,
            self._endpoint_count(candidates),
            len(candidates),
        )
        admitted = candidates[:limit]
        selected: list[TraversalTrace] = []
        for candidate in admitted:
            trace = self.graph.traverse(
                pulse_id=pulse_id,
                side=GraphSide.INPUT,
                target_id=candidate.concept_id,
                endpoint_score=candidate.joint_score,
                required_input_trunk=trunk,
                mark_active=False,
            )
            if trace is not None:
                selected.append(trace)
        for trace in selected:
            self.graph.activate_trace(pulse_id, trace)
        return selected

    def _vault_hits(
        self,
        query: str,
        query_embedding: Sequence[float],
        concept_ids: Sequence[str],
        excluded: set[str],
        target_k: int,
    ) -> list[RetrievalHit]:
        vault_rankings: list[list[RetrievalHit]] = []
        seen_vaults: set[str] = set()
        for path_index, concept_id in enumerate(concept_ids):
            concept = self.store.get_concept(concept_id)
            if concept is None or not concept.vault_id or concept.vault_id in seen_vaults:
                continue
            seen_vaults.add(concept.vault_id)
            records = [
                record for record in self.store.records_for_vault(concept.vault_id)
                if record.record_id not in excluded
            ]
            lexical = bm25_scores(query, records)
            ranked: list[RetrievalHit] = []
            for record in records:
                dense = max(0.0, cosine_similarity(query_embedding, record.embedding))
                lexical_score = lexical.get(record.record_id, 0.0)
                if dense <= 0.0 and lexical_score <= 0.0:
                    continue
                path_score = 1.0 / (1.0 + path_index)
                ranked.append(
                    RetrievalHit(
                        record=record,
                        lane="vault",
                        dense_score=dense,
                        lexical_score=lexical_score,
                        vault_id=concept.vault_id,
                        path_score=path_score,
                    )
                )
            ranked.sort(
                key=lambda hit: (
                    -(0.55 * hit.dense_score + 0.45 * hit.lexical_score),
                    hit.record.record_id,
                )
            )
            if ranked:
                vault_rankings.append(ranked)

        # Round robin guarantees one nomination per vault before any second hit.
        selected: list[RetrievalHit] = []
        depth = 0
        while len(selected) < target_k:
            added = False
            for ranking in vault_rankings:
                if depth < len(ranking):
                    selected.append(ranking[depth])
                    added = True
                    if len(selected) >= target_k:
                        break
            if not added:
                break
            depth += 1
        return selected

    @staticmethod
    def _contradictions(records: Sequence[MemoryRecord]) -> list[tuple[str, str]]:
        by_key: dict[str, list[MemoryRecord]] = {}
        for record in records:
            key = str(record.metadata.get("fact_key", "")).strip()
            if key:
                by_key.setdefault(key, []).append(record)
        conflicts: list[tuple[str, str]] = []
        for grouped in by_key.values():
            for index, left in enumerate(grouped):
                for right in grouped[index + 1 :]:
                    left_value = left.metadata.get("fact_value")
                    right_value = right.metadata.get("fact_value")
                    if left_value is not None and right_value is not None and left_value != right_value:
                        conflicts.append((left.record_id, right.record_id))
        return conflicts

    def retrieve(
        self,
        *,
        pulse_id: str,
        query: str,
        query_embedding: Sequence[float],
        event_kind: EventKind,
        trunk: InputTrunk,
        exclude_record_ids: Iterable[str] = (),
    ) -> tuple[RetrievalPacket, list[RetrievalHit]]:
        excluded = set(exclude_record_ids)
        records = self.store.list_active_records()
        direct = self._direct_hits(query_embedding, records, excluded)
        candidates = self.surface.project(
            query,
            query_embedding,
            side=GraphSide.INPUT,
            event_kind=event_kind,
            maximum_candidates=self.maximum_surface_candidates,
        )
        traces = self._traces(pulse_id, trunk, candidates)
        path_concepts = [trace.target_node_id for trace in traces]
        expanded = self.graph.expanded_concept_ids(
            traces,
            side=GraphSide.INPUT,
            maximum=self.maximum_expansions,
        )
        concept_ids = list(dict.fromkeys((*path_concepts, *expanded)))
        entropy = SemanticSurface.normalized_entropy(candidates)
        associative_target = max(2, int(math.ceil(4 + entropy * 8)))
        vault = self._vault_hits(
            query,
            query_embedding,
            concept_ids,
            excluded,
            target_k=associative_target,
        )

        combined: list[RetrievalHit] = []
        seen: set[str] = set()
        for hit in (*direct, *vault):
            if hit.record.record_id in seen:
                continue
            seen.add(hit.record.record_id)
            combined.append(hit)
        contradictions = self._contradictions([hit.record for hit in combined])
        context_budget = min(
            self.maximum_context_chars,
            int(self.base_context_chars * (1.0 + 0.60 * entropy) + 400 * len(contradictions)),
        )
        trace_material = {
            "pulse_id": pulse_id,
            "trunk": trunk.value,
            "candidates": [candidate.__dict__ for candidate in candidates],
            "paths": [
                {
                    "target": trace.target_node_id,
                    "nodes": trace.path_node_ids,
                    "edges": trace.path_edge_ids,
                    "time": trace.total_travel_time,
                }
                for trace in traces
            ],
            "selected": [hit.record.record_id for hit in combined],
        }
        trace_hash = hashlib.sha256(
            json.dumps(trace_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        packet = RetrievalPacket(
            pulse_id=pulse_id,
            input_trunk=trunk,
            surface_candidates=tuple(candidates),
            y_paths=tuple(traces),
            direct_record_ids=tuple(hit.record.record_id for hit in direct),
            vault_record_ids=tuple(hit.record.record_id for hit in vault),
            selected_record_ids=tuple(hit.record.record_id for hit in combined),
            retained_record_ids=(),
            contradictions=tuple(contradictions),
            context_budget_chars=context_budget,
            trace_hash=trace_hash,
        )
        return packet, combined
