#!/usr/bin/env python3
"""Continuous graph-to-embedding projector.

The native adapter currently crosses the boundary with a fixed codebook: each basis
slot averages three hand-picked token-embedding anchors, scaled by a scalar activation.
That map was authored, not learned, which is why the decoded stance is reliably valenced
but often lexical -- the model comments on the anchor words instead of speaking from the
state.

This module replaces the authored map with one fitted from the mind's own experience:

    graph state features  ->  W  ->  a 1024D row in the model's input embedding space

Fitting is closed-form ridge regression, so there is no training loop, no gradient
descent, and no dependency beyond numpy.  When the sample count is below the feature
dimension (the usual case for a young mind) the dual form is used:

    primal   W = (X^T X + lambda I)^-1 X^T Y        d x d solve
    dual     W = X^T (X X^T + lambda I)^-1 Y        n x n solve

Targets come from the substrate's own stored records, embedded through the model's
token embedding table by ``lexeme_codec``.  Nothing about the fit is hand-authored:
the pairing is whatever the curriculum actually deposited.

Zero-leakage note: the fitted weights are floats and the emitted packet rows are floats.
No record text is written to the projector file or to any packet.  Text participates
only during fitting, in the same way the codebook's anchor words already did -- see the
"Honest boundaries" section of ARCHITECTURE.md.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Sequence

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
EXPERIMENT_ROOT = Path(__file__).resolve().parent
for import_root in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from habitus_ai.graph import compute_structural_overlay  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import GraphSide  # noqa: E402

import live_tester  # noqa: E402

DIMENSION = 1024
VALENCE_SCALARS = 6
FEATURE_DIMENSION = 3 * DIMENSION + VALENCE_SCALARS
DEFAULT_CODEC = EXPERIMENT_ROOT / "native" / "lexeme_codec"
PROJECTOR_SCHEMA = "habitus.graph-projector.v1"


# ---------------------------------------------------------------------------
# Feature extraction -- structural state only
# ---------------------------------------------------------------------------

def _unit(vector: Sequence[float] | np.ndarray | None, dimension: int = DIMENSION) -> np.ndarray:
    if vector is None or len(vector) == 0:
        return np.zeros(dimension, dtype=np.float64)
    array = np.asarray(vector, dtype=np.float64)
    if array.size < dimension:
        array = np.pad(array, (0, dimension - array.size))
    array = array[:dimension]
    norm = float(np.linalg.norm(array))
    return array / norm if norm > 1e-9 else array


def state_features(
    mind: BaseAgenticMemoryRAG,
    concept_id: str | None,
    *,
    source_id: str = "",
    trunk: str = "HEAR",
) -> np.ndarray:
    """Build the fixed-width structural feature vector for one graph state.

    Three 1024D blocks plus six scalars, all read from graph state:
    concept centroid, Layer 3 structural overlay, dominant preference-node vector,
    and the valence diagnostics.  No stimulus text participates.
    """
    import live_evaluator  # local import: avoids a cycle at module load

    concept = mind.store.get_concept(concept_id) if concept_id else None

    centroid = _unit(concept.embedding if concept is not None else None)

    overlay = np.zeros(DIMENSION, dtype=np.float64)
    if concept is not None:
        computed = compute_structural_overlay(concept, store_or_graph=mind.graph, dimension=DIMENSION)
        if computed:
            overlay = _unit(computed)

    preference = np.zeros(DIMENSION, dtype=np.float64)
    ingress_edges = mind.store.list_edges(source_id=f"IN:{trunk}")
    if ingress_edges:
        dominant = max(ingress_edges, key=lambda edge: edge.softmax_weight)
        node = mind.store.get_concept(dominant.target_id)
        if node is not None:
            preference = _unit(node.embedding)

    _, diagnostics = live_evaluator.preference_valence_activations(
        mind, source_id=source_id, trunk=trunk
    )
    scalars = np.array(
        [
            diagnostics["valence"],
            diagnostics["source_affinity_mean"],
            math.tanh(diagnostics["source_samples"] / 8.0),
            diagnostics["membrane_strength_margin"],
            diagnostics["membrane_softmax_polarity"],
            math.tanh(diagnostics["membrane_conflict_penalty"]),
        ],
        dtype=np.float64,
    )

    return np.concatenate([centroid, overlay, preference, scalars])


# ---------------------------------------------------------------------------
# Targets -- the model's own input embedding space
# ---------------------------------------------------------------------------

def lexical_embeddings(
    texts: Sequence[str],
    *,
    model_path: Path,
    codec_path: Path = DEFAULT_CODEC,
    backend_dir: str = "/usr/local/lib/ollama",
) -> dict[str, np.ndarray]:
    """Embed phrases with the model's token embedding table, one process per batch.

    ``lexeme_codec`` accepts many texts per invocation, so the 610 MB model is loaded
    once regardless of corpus size.
    """
    # Keyed by the exact string passed: a leading space is meaningful to the
    # tokenizer (" answer" is the mid-sentence form, "answer" is not).
    unique = [text for text in dict.fromkeys(texts) if text.strip()]
    if not unique:
        return {}
    if not (codec_path.is_file() and Path(model_path).is_file()):
        raise RuntimeError(f"lexeme_codec or model unavailable: {codec_path}, {model_path}")

    environment = os.environ.copy()
    old_library_path = environment.get("LD_LIBRARY_PATH", "")
    environment["LD_LIBRARY_PATH"] = f"{backend_dir}:{old_library_path}" if old_library_path else backend_dir

    completed = subprocess.run(
        [str(codec_path), str(model_path), "tokenize", *unique],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=600,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"lexeme_codec failed ({completed.returncode}): {completed.stderr.strip()}")

    payload = json.loads(completed.stdout)
    return {
        item["text"]: _unit(item["embedding"])
        for item in payload["items"]
        if item.get("embedding")
    }


def codebook_row(
    slots: Iterable[tuple[str, float]],
    anchor_embeddings: dict[str, np.ndarray],
    anchors: dict[str, tuple[str, ...]],
) -> np.ndarray:
    """Reproduce the fixed codebook's row for a state: activation-weighted anchor mean.

    This is the baseline the fitted projector has to beat.
    """
    row = np.zeros(DIMENSION, dtype=np.float64)
    for slot, activation in slots:
        words = anchors.get(slot)
        if not words:
            continue
        vectors = [anchor_embeddings[word] for word in words if word in anchor_embeddings]
        if not vectors:
            continue
        row += float(activation) * np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(row))
    return row / norm if norm > 1e-9 else row


# ---------------------------------------------------------------------------
# Ridge fit
# ---------------------------------------------------------------------------

@dataclass
class ProjectorFit:
    """A fitted projector plus the numbers that justify it."""

    weights: np.ndarray            # (feature_dim, DIMENSION)
    ridge_lambda: float
    samples: int
    feature_dimension: int
    solver: str                    # "primal" | "dual"
    train_cosine: float

    def predict(self, features: np.ndarray) -> np.ndarray:
        row = np.asarray(features, dtype=np.float64) @ self.weights
        norm = float(np.linalg.norm(row))
        return row / norm if norm > 1e-9 else row


def fit_ridge(X: np.ndarray, Y: np.ndarray, ridge_lambda: float = 1.0) -> ProjectorFit:
    """Closed-form ridge, choosing the cheaper of the primal and dual solves."""
    X = np.asarray(X, dtype=np.float64)
    Y = np.asarray(Y, dtype=np.float64)
    if X.ndim != 2 or Y.ndim != 2 or X.shape[0] != Y.shape[0]:
        raise ValueError(f"shape mismatch: X{X.shape} Y{Y.shape}")
    samples, features = X.shape

    if samples >= features:
        gram = X.T @ X + ridge_lambda * np.eye(features)
        weights = np.linalg.solve(gram, X.T @ Y)
        solver = "primal"
    else:
        gram = X @ X.T + ridge_lambda * np.eye(samples)
        weights = X.T @ np.linalg.solve(gram, Y)
        solver = "dual"

    predictions = X @ weights
    train_cosine = float(np.mean([_cosine(p, y) for p, y in zip(predictions, Y)]))
    return ProjectorFit(
        weights=weights,
        ridge_lambda=ridge_lambda,
        samples=samples,
        feature_dimension=features,
        solver=solver,
        train_cosine=train_cosine,
    )


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator > 1e-12 else 0.0


def save_projector(fit: ProjectorFit, path: Path) -> None:
    """Persist the map. Floats only -- no record text reaches this file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": PROJECTOR_SCHEMA,
                "ridge_lambda": fit.ridge_lambda,
                "samples": fit.samples,
                "feature_dimension": fit.feature_dimension,
                "output_dimension": int(fit.weights.shape[1]),
                "solver": fit.solver,
                "train_cosine": fit.train_cosine,
                "weights": [[float(v) for v in row] for row in fit.weights],
            }
        ),
        encoding="utf-8",
    )


def load_projector(path: Path) -> ProjectorFit:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != PROJECTOR_SCHEMA:
        raise ValueError(f"unexpected projector schema: {payload.get('schema')!r}")
    return ProjectorFit(
        weights=np.asarray(payload["weights"], dtype=np.float64),
        ridge_lambda=float(payload["ridge_lambda"]),
        samples=int(payload["samples"]),
        feature_dimension=int(payload["feature_dimension"]),
        solver=str(payload["solver"]),
        train_cosine=float(payload["train_cosine"]),
    )


# ---------------------------------------------------------------------------
# Corpus assembly from a live mind
# ---------------------------------------------------------------------------

@dataclass
class TrainingPair:
    concept_id: str
    source_id: str
    text: str


def collect_pairs(mind: BaseAgenticMemoryRAG, *, minimum_words: int = 3) -> list[TrainingPair]:
    """Mine (graph state, associated text) pairs from the mind's own records.

    A pair exists wherever a stored record is bound to a crown concept: the concept and
    the surrounding graph give the state, the record's own text gives the target. The
    pairing is whatever the curriculum deposited, not an authored table.
    """
    records = {record.record_id: record for record in mind.store.list_active_records()}
    rows = mind.store.connection.execute(
        "SELECT record_id, concept_id FROM vault_membership ORDER BY record_id, concept_id"
    ).fetchall()

    pairs: list[TrainingPair] = []
    for row in rows:
        record = records.get(row["record_id"])
        if record is None:
            continue
        text = (record.text or "").strip()
        if len(text.split()) < minimum_words:
            continue
        pairs.append(
            TrainingPair(
                concept_id=row["concept_id"],
                source_id=record.source_id or "",
                text=text,
            )
        )
    return pairs


def build_dataset(
    mind: BaseAgenticMemoryRAG,
    pairs: Sequence[TrainingPair],
    *,
    model_path: Path,
    codec_path: Path = DEFAULT_CODEC,
) -> tuple[np.ndarray, np.ndarray, list[TrainingPair]]:
    """Turn pairs into (features, targets), dropping any the codec could not embed."""
    embeddings = lexical_embeddings(
        [pair.text for pair in pairs], model_path=model_path, codec_path=codec_path
    )
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    kept: list[TrainingPair] = []
    for pair in pairs:
        target = embeddings.get(pair.text)
        if target is None:
            continue
        features.append(state_features(mind, pair.concept_id, source_id=pair.source_id))
        targets.append(target)
        kept.append(pair)
    if not kept:
        return np.zeros((0, FEATURE_DIMENSION)), np.zeros((0, DIMENSION)), []
    return np.vstack(features), np.vstack(targets), kept


def train_holdout_split(
    X: np.ndarray,
    Y: np.ndarray,
    pairs: Sequence[TrainingPair],
    *,
    holdout: float = 0.25,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, list[TrainingPair], np.ndarray, np.ndarray, list[TrainingPair]]:
    """Deterministically shuffle, then split.

    Records arrive grouped by concept, so an ordered split would hold out whole concepts
    and measure extrapolation rather than fit quality.
    """
    order = np.random.default_rng(seed).permutation(len(pairs))
    split = max(1, int(len(pairs) * (1.0 - holdout)))
    train, held = order[:split], order[split:]
    return (
        X[train], Y[train], [pairs[i] for i in train],
        X[held], Y[held], [pairs[i] for i in held],
    )


def evaluate_against_codebook(
    mind: BaseAgenticMemoryRAG,
    fit: ProjectorFit,
    X_holdout: np.ndarray,
    Y_holdout: np.ndarray,
    pairs_holdout: Sequence[TrainingPair],
    *,
    model_path: Path,
    codec_path: Path = DEFAULT_CODEC,
) -> dict[str, float]:
    """Compare the fitted map with the authored codebook on held-out states."""
    anchors = {
        "speak": (" answer", " respond", " say"),
        "greeting": (" hello", " welcome", " greetings"),
        "warm": (" warm", " friendly", " kind"),
        "question": (" answer", " explain", " helpful"),
        "clear": (" clear", " direct", " concise"),
        "memory": (" remember", " recall", " familiar"),
        "uncertain": (" uncertain", " careful", " honest"),
        "gratitude": (" thanks", " appreciate", " welcome"),
        "observation": (" observe", " notice", " describe"),
        "action": (" act", " execute", " complete"),
        "affinity": (" trust", " friend", " glad"),
        "caution": (" cautious", " wary", " guarded"),
        "withhold": (" decline", " withhold", " refrain"),
    }
    anchor_embeddings = lexical_embeddings(
        [word for words in anchors.values() for word in words],
        model_path=model_path,
        codec_path=codec_path,
    )

    projector_scores: list[float] = []
    codebook_scores: list[float] = []
    for features, target, pair in zip(X_holdout, Y_holdout, pairs_holdout):
        projector_scores.append(_cosine(fit.predict(features), target))
        specification = live_tester.SEED_CONCEPTS.get(pair.concept_id)
        slots = tuple(specification["basis"]) if specification else (("speak", 1.0),)
        codebook_scores.append(_cosine(codebook_row(slots, anchor_embeddings, anchors), target))

    return {
        "holdout_samples": float(len(projector_scores)),
        "projector_cosine": float(np.mean(projector_scores)) if projector_scores else 0.0,
        "codebook_cosine": float(np.mean(codebook_scores)) if codebook_scores else 0.0,
        "projector_wins": float(
            np.mean([p > c for p, c in zip(projector_scores, codebook_scores)])
        )
        if projector_scores
        else 0.0,
    }


# ---------------------------------------------------------------------------
# Per-concept targets from discriminative vocabulary
# ---------------------------------------------------------------------------

STRUCTURAL_NODE = re.compile(r"^(SELF|IN:|OUT:|PREF:)")


def crown_concept_records(
    mind: BaseAgenticMemoryRAG, *, minimum_records: int = 3
) -> dict[str, list[str]]:
    """Group record texts by crown concept.

    Trunk, preference and SELF nodes are excluded: they are routing structure, not
    meaning, and every record touches them, so they carry no discriminative vocabulary.
    """
    records = {record.record_id: record for record in mind.store.list_active_records()}
    grouped: dict[str, list[str]] = {}
    for row in mind.store.connection.execute(
        "SELECT record_id, concept_id FROM vault_membership ORDER BY concept_id, record_id"
    ):
        concept_id = row["concept_id"]
        if STRUCTURAL_NODE.match(concept_id):
            continue
        record = records.get(row["record_id"])
        if record is None:
            continue
        text = (record.text or "").strip()
        if text:
            grouped.setdefault(concept_id, []).append(text)
    return {
        concept_id: texts
        for concept_id, texts in grouped.items()
        if len(texts) >= minimum_records
    }


def discriminative_words(
    concept_texts: dict[str, list[str]],
    *,
    top_k: int = 3,
    minimum_length: int = 4,
    maximum_document_ratio: float = 0.10,
) -> dict[str, list[str]]:
    """Pick each concept's most distinguishing words by tf-idf over the concept corpus.

    This is the data-driven form of the authored anchor list: where the codebook has a
    human writing (" thanks", " appreciate", " welcome") for gratitude, this selects the
    words that actually separate one concept's experiences from every other concept's.
    """
    tokenized = {
        concept_id: [
            word
            for text in texts
            for word in re.findall(r"[A-Za-z']+", text.casefold())
            if len(word) >= minimum_length
        ]
        for concept_id, texts in concept_texts.items()
    }
    document_frequency: dict[str, int] = {}
    for words in tokenized.values():
        for word in set(words):
            document_frequency[word] = document_frequency.get(word, 0) + 1

    total_concepts = max(1, len(tokenized))
    # A developmental curriculum is templated, so frame vocabulary ("broader",
    # "coactivation") recurs across most concepts.  Anything that common describes the
    # curriculum rather than the concept, so it is dropped outright before scoring.
    ubiquity_cutoff = max(2, int(total_concepts * maximum_document_ratio))

    selected: dict[str, list[str]] = {}
    for concept_id, words in tokenized.items():
        if not words:
            continue
        counts: dict[str, int] = {}
        for word in words:
            counts[word] = counts.get(word, 0) + 1
        scored = sorted(
            (
                (word, count)
                for word, count in counts.items()
                if document_frequency[word] <= ubiquity_cutoff
            ),
            key=lambda item: (
                -(item[1] / len(words)) * math.log(total_concepts / document_frequency[item[0]]),
                item[0],
            ),
        )
        chosen = [word for word, _ in scored[:top_k]]
        if chosen:
            selected[concept_id] = chosen
    return selected


def concept_targets(
    words_by_concept: dict[str, list[str]],
    *,
    model_path: Path,
    codec_path: Path = DEFAULT_CODEC,
) -> dict[str, np.ndarray]:
    """Average each concept's discriminative words into one direction.

    Words are embedded with a leading space, the tokenizer's mid-sentence form and the
    same convention the authored anchors use.
    """
    phrases = sorted({f" {word}" for words in words_by_concept.values() for word in words})
    embeddings = lexical_embeddings(phrases, model_path=model_path, codec_path=codec_path)

    targets: dict[str, np.ndarray] = {}
    for concept_id, words in words_by_concept.items():
        vectors = [embeddings[f" {word}"] for word in words if f" {word}" in embeddings]
        if not vectors:
            continue
        targets[concept_id] = _unit(np.mean(vectors, axis=0))
    return targets


def build_concept_dataset(
    mind: BaseAgenticMemoryRAG,
    targets: dict[str, np.ndarray],
    *,
    source_id: str = "",
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """One row per concept: structural features against its discriminative direction."""
    concept_ids = sorted(targets)
    if not concept_ids:
        return np.zeros((0, FEATURE_DIMENSION)), np.zeros((0, DIMENSION)), []
    X = np.vstack([state_features(mind, cid, source_id=source_id) for cid in concept_ids])
    Y = np.vstack([targets[cid] for cid in concept_ids])
    return X, Y, concept_ids


def nearest_words(
    vectors: Sequence[np.ndarray],
    *,
    model_path: Path,
    codec_path: Path = DEFAULT_CODEC,
    top_k: int = 5,
    backend_dir: str = "/usr/local/lib/ollama",
    batch_size: int = 12,
) -> list[list[tuple[str, float]]]:
    """Decode rows back to vocabulary through the model's own output projection.

    This is the readable end of the seam: a graph state becomes a direction becomes words.
    """
    if not vectors:
        return []
    environment = os.environ.copy()
    old_library_path = environment.get("LD_LIBRARY_PATH", "")
    environment["LD_LIBRARY_PATH"] = f"{backend_dir}:{old_library_path}" if old_library_path else backend_dir

    decoded: list[list[tuple[str, float]]] = []
    for start in range(0, len(vectors), batch_size):
        batch = vectors[start : start + batch_size]
        encoded = [",".join(f"{float(value):.6g}" for value in vector) for vector in batch]
        completed = subprocess.run(
            [str(codec_path), str(model_path), "nearest", str(top_k), *encoded],
            check=False,
            capture_output=True,
            env=environment,
            timeout=600,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"lexeme_codec nearest failed: {completed.stderr.decode('utf-8', 'replace').strip()}"
            )
        # A BPE piece can be a partial UTF-8 sequence, so decode leniently rather than
        # letting one fragment abort the whole batch.
        payload = json.loads(completed.stdout.decode("utf-8", "replace"))
        for item in payload["items"]:
            decoded.append(
                [(candidate["piece"], float(candidate["score"])) for candidate in item["candidates"]]
            )
    return decoded


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def lexical_concept_indices(X: np.ndarray) -> list[int]:
    """Rows whose concept carries a centroid.

    Opaque child nodes are stored with a zero embedding by design, so they have no
    lexical direction to predict and are excluded from a vocabulary fit.
    """
    return [index for index in range(len(X)) if float(np.linalg.norm(X[index][:DIMENSION])) > 1e-9]


def fit_concept_projector(
    mind: BaseAgenticMemoryRAG,
    *,
    model_path: Path,
    codec_path: Path = DEFAULT_CODEC,
    top_k_words: int = 3,
    minimum_records: int = 3,
    ridge_lambda: float = 0.1,
) -> tuple[ProjectorFit, list[str], dict[str, list[str]]]:
    """Fit state -> discriminative-vocabulary direction, one row per crown concept."""
    grouped = crown_concept_records(mind, minimum_records=minimum_records)
    words = discriminative_words(grouped, top_k=top_k_words)
    targets = concept_targets(words, model_path=model_path, codec_path=codec_path)
    X, Y, concept_ids = build_concept_dataset(mind, targets)
    if len(concept_ids) < 2:
        raise RuntimeError("not enough crown concepts with records to fit a concept projector")

    lexical = lexical_concept_indices(X)
    if len(lexical) < 2:
        raise RuntimeError("no crown concepts carry a centroid; nothing lexical to fit")
    fit = fit_ridge(X[lexical], Y[lexical], ridge_lambda=ridge_lambda)
    return fit, [concept_ids[index] for index in lexical], words


def decode_concept_vocabulary(
    mind: BaseAgenticMemoryRAG,
    fit: ProjectorFit,
    concept_ids: Sequence[str],
    words_by_concept: dict[str, list[str]],
    *,
    model_path: Path,
    codec_path: Path = DEFAULT_CODEC,
    top_k: int = 3,
) -> tuple[list[tuple[str, list[str], list[str]]], float]:
    """Round-trip every state back to words and score against its own vocabulary."""
    predictions = [fit.predict(state_features(mind, concept_id)) for concept_id in concept_ids]
    decoded = nearest_words(predictions, model_path=model_path, codec_path=codec_path, top_k=top_k)

    rows: list[tuple[str, list[str], list[str]]] = []
    hits = 0
    for concept_id, candidates in zip(concept_ids, decoded):
        expected = words_by_concept.get(concept_id, [])
        produced = [piece.strip() for piece, _ in candidates]
        if any(word.casefold() in {e.casefold() for e in expected} for word in produced):
            hits += 1
        rows.append((concept_id, expected, produced))
    return rows, (hits / len(rows) if rows else 0.0)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit the graph-to-embedding projector.")
    parser.add_argument(
        "--mode",
        choices=["record", "concept"],
        default="record",
        help="record: state -> pooled record-text embedding. concept: state -> discriminative vocabulary.",
    )
    parser.add_argument("--top-k-words", type=int, default=3)
    parser.add_argument("--database", type=Path, required=True, help="mind SQLite path")
    parser.add_argument("--model", type=Path, default=live_tester.DEFAULT_MODEL)
    parser.add_argument("--codec", type=Path, default=DEFAULT_CODEC)
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "projector_runs" / "projector.json")
    parser.add_argument("--ridge-lambda", type=float, default=1.0)
    parser.add_argument("--holdout", type=float, default=0.25, help="fraction held out for evaluation")
    parser.add_argument("--seed", type=int, default=42, help="split shuffle seed")
    parser.add_argument(
        "--embedder",
        choices=["default", "native"],
        default="default",
        help="native: match a mind gestated in the Qwen token-mean embedding space",
    )
    return parser.parse_args(argv)


def _embedder_for(args: argparse.Namespace) -> Any | None:
    """Match the store's persisted embedding space, which a gestated mind pins."""
    if args.embedder == "native":
        import accelerated_gestation

        return accelerated_gestation.NativeMassEmbedder(args.model, args.codec)
    return None


def _run_concept_mode(mind: BaseAgenticMemoryRAG, args: argparse.Namespace) -> int:
    fit, concept_ids, words = fit_concept_projector(
        mind,
        model_path=args.model,
        codec_path=args.codec,
        top_k_words=args.top_k_words,
        ridge_lambda=args.ridge_lambda,
    )
    rows, accuracy = decode_concept_vocabulary(
        mind, fit, concept_ids, words, model_path=args.model, codec_path=args.codec
    )
    save_projector(fit, args.output)

    print(f"lexical concepts : {len(concept_ids)}")
    print(f"solver           : {fit.solver} (lambda={fit.ridge_lambda})")
    print(f"train cosine     : {fit.train_cosine:.4f}")
    print(f"state -> words   : {accuracy * 100:.0f}% decode one of their own words")
    print(f"written          : {args.output}\n")
    for concept_id, expected, produced in rows[:20]:
        marker = "HIT " if any(
            word.casefold() in {e.casefold() for e in expected} for word in produced
        ) else "miss"
        print(f"  {marker} {concept_id[:38]:38} own={expected} decoded={produced}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    with BaseAgenticMemoryRAG(args.database, embedder=_embedder_for(args)) as mind:
        if args.mode == "concept":
            return _run_concept_mode(mind, args)
        pairs = collect_pairs(mind)
        if not pairs:
            print("No (state, text) pairs found in this mind. Gestate or run turns first.")
            return 1
        X, Y, kept = build_dataset(mind, pairs, model_path=args.model, codec_path=args.codec)
        if len(kept) < 4:
            print(f"Only {len(kept)} usable pairs; need at least 4.")
            return 1

        X_fit, Y_fit, _, X_held, Y_held, pairs_held = train_holdout_split(
            X, Y, kept, holdout=args.holdout, seed=args.seed
        )
        fit = fit_ridge(X_fit, Y_fit, ridge_lambda=args.ridge_lambda)
        metrics = evaluate_against_codebook(
            mind, fit, X_held, Y_held, pairs_held,
            model_path=args.model, codec_path=args.codec,
        )
        save_projector(fit, args.output)

        print(f"pairs           : {len(kept)} ({len(X_fit)} train / {len(X_held)} holdout)")
        print(f"solver          : {fit.solver} (lambda={fit.ridge_lambda})")
        print(f"train cosine    : {fit.train_cosine:.4f}")
        print(f"holdout cosine  : projector {metrics['projector_cosine']:.4f}"
              f"  vs codebook {metrics['codebook_cosine']:.4f}")
        print(f"projector wins  : {metrics['projector_wins'] * 100:.1f}% of held-out states")
        print(f"written         : {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
