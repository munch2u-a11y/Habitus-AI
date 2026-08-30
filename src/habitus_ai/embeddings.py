from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, Sequence, runtime_checkable


TOKEN_RE = re.compile(r"[a-z0-9_]+(?:[./:-][a-z0-9_]+)*", re.IGNORECASE)


@runtime_checkable
class Embedder(Protocol):
    """Replaceable embedding boundary used by records and crown concepts."""

    dimension: int
    space_id: str

    def embed(self, text: str) -> list[float]: ...


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(str(text).casefold())


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def opaque_payload_embedding(
    payload: str,
    dimension: int,
    *,
    namespace: str = "sensory",
    features: int = 64,
) -> list[float]:
    """Encode an exact nonverbal payload without token or word features.

    The resulting direction is stable for the same payload but cryptographically
    opaque to lexical overlap. Real sensors and tools should supply structured
    feature vectors when neighborhood similarity matters; this is the safe
    fallback for textual transports whose words must not enter the membrane.
    """
    if dimension < 16:
        raise ValueError("embedding dimension must be at least 16")
    vector = [0.0] * int(dimension)
    material = f"{namespace}\0{payload}".encode("utf-8")
    for counter in range(max(1, min(int(features), dimension))):
        digest = hashlib.sha256(material + counter.to_bytes(4, "big")).digest()
        index = int.from_bytes(digest[:8], "big") % dimension
        sign = 1.0 if digest[8] & 1 else -1.0
        magnitude = 0.5 + digest[9] / 255.0
        vector[index] += sign * magnitude
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class DeterministicHashEmbedder:
    """Offline lexical embedder for reproducible tests and demonstrations.

    Production callers should supply an actual semantic model. Stable SHA-derived
    indices avoid Python hash randomization and make persisted test minds portable.
    """

    def __init__(self, dimension: int = 1024, space_id: str | None = None):
        if dimension < 16:
            raise ValueError("embedding dimension must be at least 16")
        self.dimension = int(dimension)
        self.space_id = space_id or f"deterministic_hash_{self.dimension}_v1"

    @staticmethod
    def _features(text: str) -> list[tuple[str, float]]:
        tokens = tokenize(text)
        features: list[tuple[str, float]] = []
        for token in tokens:
            features.append((f"tok:{token}", 1.0))
            if len(token) >= 4:
                for index in range(len(token) - 2):
                    features.append((f"tri:{token[index:index + 3]}", 0.20))
        for first, second in zip(tokens, tokens[1:]):
            features.append((f"pair:{first}|{second}", 0.35))
        return features

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for feature, magnitude in self._features(text):
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimension
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign * magnitude
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector
