from __future__ import annotations

import math
from typing import Sequence

from .embeddings import cosine_similarity, tokenize
from .store import MindStore
from .types import EventKind, GraphSide, SurfaceCandidate


class SemanticSurface:
    """Conventional crown nomination independent of Y-axis travel cost."""

    def __init__(self, store: MindStore):
        self.store = store

    @staticmethod
    def _weights(event_kind: EventKind | None) -> tuple[float, float]:
        if event_kind == EventKind.OBSERVATION:
            return 0.45, 0.55
        if event_kind == EventKind.NOTIFICATION:
            return 0.55, 0.45
        return 0.70, 0.30

    @staticmethod
    def normalized_entropy(candidates: Sequence[SurfaceCandidate]) -> float:
        if len(candidates) <= 1:
            return 0.0
        values = [candidate.joint_score for candidate in candidates]
        maximum = max(values)
        exps = [math.exp((value - maximum) / 0.20) for value in values]
        total = sum(exps) or 1.0
        probabilities = [value / total for value in exps]
        entropy = -sum(p * math.log(max(p, 1e-12)) for p in probabilities)
        return entropy / math.log(len(probabilities))

    def project(
        self,
        text: str,
        embedding: Sequence[float],
        *,
        side: GraphSide,
        event_kind: EventKind | None = None,
        maximum_candidates: int = 8,
    ) -> list[SurfaceCandidate]:
        reachable = {
            edge.target_id for edge in self.store.list_edges(side)
        }
        crown = [
            concept for concept in self.store.list_concepts(kind="crown")
            if concept.concept_id in reachable
            or any(
                edge.target_id == concept.concept_id
                for edge in self.store.list_edges(side)
            )
        ]
        if not crown:
            return []
        query_tokens = tokenize(text)
        query_set = set(query_tokens)
        semantic_weight, lexical_weight = self._weights(event_kind)
        scored: list[SurfaceCandidate] = []
        for concept in crown:
            semantic = max(0.0, cosine_similarity(embedding, concept.embedding))
            concept_terms = set(concept.terms)
            overlap = len(query_set & concept_terms)
            lexical = overlap / math.sqrt(max(1, len(query_set)) * max(1, len(concept_terms)))
            joint = semantic_weight * semantic + lexical_weight * lexical
            if joint <= 0.0:
                continue
            scored.append(
                SurfaceCandidate(
                    concept_id=concept.concept_id,
                    semantic_score=round(semantic, 8),
                    lexical_score=round(lexical, 8),
                    joint_score=round(joint, 8),
                )
            )
        scored.sort(key=lambda candidate: (-candidate.joint_score, candidate.concept_id))
        if not scored:
            return []
        preliminary = scored[: max(2, maximum_candidates)]
        entropy = self.normalized_entropy(preliminary)
        dynamic_k = min(
            maximum_candidates,
            len(preliminary),
            max(2, int(math.ceil(math.sqrt(len(preliminary)))) + int(math.ceil(entropy * 2))),
        )
        return preliminary[:dynamic_k]
