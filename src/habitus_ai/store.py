from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .types import (
    ConceptNode,
    ExperienceProjection,
    ExperienceState,
    GraphEdge,
    GraphSide,
    MemoryRecord,
    OverlapCluster,
    OutcomePacket,
    RecordType,
    StructuralMiniMap,
    StructuralRelation,
    TraversalTrace,
    as_tuple,
)


def _structural_map_to_dict(s_map: StructuralMiniMap | None) -> dict[str, Any] | None:
    if s_map is None:
        return None
    return {
        "map_id": s_map.map_id,
        "parent_node_ids": list(s_map.parent_node_ids),
        "child_node_ids": list(s_map.child_node_ids),
        "relations": [
            {
                "source_node_id": r.source_node_id,
                "target_node_id": r.target_node_id,
                "coactivation_density": r.coactivation_density,
                "direction": r.direction,
            }
            for r in s_map.relations
        ],
        "total_coactivations": s_map.total_coactivations,
    }


def _structural_map_from_dict(data: dict[str, Any] | None) -> StructuralMiniMap | None:
    if not data:
        return None
    relations = tuple(
        StructuralRelation(
            source_node_id=r["source_node_id"],
            target_node_id=r["target_node_id"],
            coactivation_density=float(r.get("coactivation_density", 1.0)),
            direction=r.get("direction", "bidirectional"),
        )
        for r in data.get("relations", [])
    )
    return StructuralMiniMap(
        map_id=data["map_id"],
        parent_node_ids=tuple(data.get("parent_node_ids", [])),
        child_node_ids=tuple(data.get("child_node_ids", [])),
        relations=relations,
        total_coactivations=int(data.get("total_coactivations", 0)),
    )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


class MindStore:
    """SQLite authority store with immutable memory records.

    Graph topology and derived strengths may evolve. Canonical event content may
    only be superseded by another immutable record.
    """

    def __init__(self, path: str | Path, *, space_id: str, dimension: int):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.connection.execute("PRAGMA journal_mode = WAL")
        self._create_schema()
        self._bind_embedding_space(space_id, dimension)

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def _create_schema(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    event_id TEXT UNIQUE,
                    record_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    supersedes_id TEXT REFERENCES records(record_id)
                );

                CREATE TRIGGER IF NOT EXISTS records_are_immutable_update
                BEFORE UPDATE ON records BEGIN
                    SELECT RAISE(ABORT, 'canonical records are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS records_are_immutable_delete
                BEFORE DELETE ON records BEGIN
                    SELECT RAISE(ABORT, 'canonical records are immutable');
                END;

                CREATE TABLE IF NOT EXISTS record_links (
                    source_record_id TEXT NOT NULL REFERENCES records(record_id),
                    relation TEXT NOT NULL,
                    target_record_id TEXT NOT NULL REFERENCES records(record_id),
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (source_record_id, relation, target_record_id)
                );

                CREATE TABLE IF NOT EXISTS concepts (
                    concept_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    terms_json TEXT NOT NULL,
                    vault_id TEXT,
                    created_pulse INTEGER NOT NULL,
                    last_active_pulse INTEGER NOT NULL DEFAULT 0,
                    structural_map_json TEXT,
                    invocation_count INTEGER NOT NULL DEFAULT 0,
                    softmax_weight REAL NOT NULL DEFAULT 1.0
                );

                CREATE TABLE IF NOT EXISTS edges (
                    edge_id TEXT PRIMARY KEY,
                    side TEXT NOT NULL,
                    source_id TEXT NOT NULL REFERENCES concepts(concept_id),
                    target_id TEXT NOT NULL REFERENCES concepts(concept_id),
                    delta_y REAL NOT NULL,
                    log_strength REAL NOT NULL,
                    conflict_penalty REAL NOT NULL DEFAULT 0.0,
                    last_active_time REAL,
                    created_pulse INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    invocation_count INTEGER NOT NULL DEFAULT 0,
                    softmax_weight REAL NOT NULL DEFAULT 1.0,
                    UNIQUE (side, source_id, target_id)
                );

                CREATE TABLE IF NOT EXISTS edge_evidence (
                    edge_id TEXT NOT NULL REFERENCES edges(edge_id),
                    record_id TEXT NOT NULL REFERENCES records(record_id),
                    relation TEXT NOT NULL DEFAULT 'supports',
                    PRIMARY KEY (edge_id, record_id, relation)
                );

                CREATE TABLE IF NOT EXISTS vault_membership (
                    vault_id TEXT NOT NULL,
                    record_id TEXT NOT NULL REFERENCES records(record_id),
                    concept_id TEXT NOT NULL REFERENCES concepts(concept_id),
                    PRIMARY KEY (vault_id, record_id, concept_id)
                );

                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    pulse_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    pulse_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS experience_state (
                    experience_id TEXT PRIMARY KEY,
                    preference_mean REAL NOT NULL DEFAULT 0.0,
                    preference_weight REAL NOT NULL DEFAULT 0.0,
                    observation_count INTEGER NOT NULL DEFAULT 0,
                    last_pulse INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS experience_projections (
                    experience_id TEXT NOT NULL,
                    record_id TEXT NOT NULL REFERENCES records(record_id),
                    node_id TEXT NOT NULL REFERENCES concepts(concept_id),
                    layer INTEGER NOT NULL,
                    side TEXT NOT NULL,
                    activation REAL NOT NULL,
                    preference REAL NOT NULL,
                    confidence REAL NOT NULL,
                    pulse INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (record_id, node_id, side)
                );

                CREATE TABLE IF NOT EXISTS overlap_clusters (
                    cluster_id TEXT PRIMARY KEY,
                    parent_node_id TEXT NOT NULL REFERENCES concepts(concept_id),
                    centroid_json TEXT NOT NULL,
                    record_ids_json TEXT NOT NULL,
                    experience_ids_json TEXT NOT NULL,
                    preference_mean REAL NOT NULL,
                    confidence_mean REAL NOT NULL,
                    first_pulse INTEGER NOT NULL,
                    last_pulse INTEGER NOT NULL,
                    child_node_id TEXT REFERENCES concepts(concept_id),
                    semantic_node_id TEXT REFERENCES concepts(concept_id)
                );

                CREATE INDEX IF NOT EXISTS idx_edges_side_source
                    ON edges(side, source_id, archived);
                CREATE INDEX IF NOT EXISTS idx_vault_membership_vault
                    ON vault_membership(vault_id);
                CREATE INDEX IF NOT EXISTS idx_records_timestamp
                    ON records(timestamp);
                CREATE INDEX IF NOT EXISTS idx_projection_node
                    ON experience_projections(node_id, layer, pulse);
                CREATE INDEX IF NOT EXISTS idx_projection_experience
                    ON experience_projections(experience_id);
                CREATE INDEX IF NOT EXISTS idx_overlap_parent
                    ON overlap_clusters(parent_node_id, last_pulse);
                """
            )
            for table, col, col_def in [
                ("concepts", "structural_map_json", "TEXT"),
                ("concepts", "invocation_count", "INTEGER NOT NULL DEFAULT 0"),
                ("concepts", "softmax_weight", "REAL NOT NULL DEFAULT 1.0"),
                ("edges", "invocation_count", "INTEGER NOT NULL DEFAULT 0"),
                ("edges", "softmax_weight", "REAL NOT NULL DEFAULT 1.0"),
            ]:
                try:
                    self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                except Exception:
                    pass

    def _bind_embedding_space(self, space_id: str, dimension: int) -> None:
        existing = {
            row["key"]: row["value"]
            for row in self.connection.execute(
                "SELECT key, value FROM metadata WHERE key IN ('embedding_space_id', 'embedding_dimension')"
            )
        }
        if existing:
            if existing.get("embedding_space_id") != space_id:
                raise ValueError(
                    f"embedding space mismatch: store={existing.get('embedding_space_id')} runtime={space_id}"
                )
            if int(existing.get("embedding_dimension", -1)) != int(dimension):
                raise ValueError(
                    f"embedding dimension mismatch: store={existing.get('embedding_dimension')} runtime={dimension}"
                )
            return
        with self.connection:
            self.connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                (("embedding_space_id", space_id), ("embedding_dimension", str(dimension))),
            )

    def set_metadata(self, key: str, value: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO metadata(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        row = self.connection.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    # ------------------------------------------------------------------ records

    def add_record(self, record: MemoryRecord) -> MemoryRecord:
        with self._lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO records(
                    record_id, event_id, record_type, source_id, timestamp, text,
                    embedding_json, provenance_json, metadata_json, supersedes_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.event_id,
                    record.record_type.value,
                    record.source_id,
                    record.timestamp,
                    record.text,
                    _json(record.embedding),
                    _json(dict(record.provenance)),
                    _json(dict(record.metadata)),
                    record.supersedes_id,
                ),
            )
        return record

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            record_id=row["record_id"],
            event_id=row["event_id"],
            record_type=RecordType(row["record_type"]),
            source_id=row["source_id"],
            timestamp=row["timestamp"],
            text=row["text"],
            embedding=as_tuple(_loads(row["embedding_json"], [])),
            provenance=_loads(row["provenance_json"], {}),
            metadata=_loads(row["metadata_json"], {}),
            supersedes_id=row["supersedes_id"],
        )

    def get_record(self, record_id: str) -> MemoryRecord | None:
        row = self.connection.execute(
            "SELECT * FROM records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return self._record_from_row(row) if row else None

    def get_records(self, record_ids: Iterable[str]) -> list[MemoryRecord]:
        wanted = list(dict.fromkeys(record_ids))
        if not wanted:
            return []
        placeholders = ",".join("?" for _ in wanted)
        rows = self.connection.execute(
            f"SELECT * FROM records WHERE record_id IN ({placeholders})", wanted
        ).fetchall()
        by_id = {row["record_id"]: self._record_from_row(row) for row in rows}
        return [by_id[record_id] for record_id in wanted if record_id in by_id]

    def list_active_records(self) -> list[MemoryRecord]:
        rows = self.connection.execute(
            """
            SELECT r.* FROM records r
            WHERE NOT EXISTS (
                SELECT 1 FROM records newer WHERE newer.supersedes_id = r.record_id
            )
            ORDER BY r.timestamp, r.record_id
            """
        ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def list_records(self) -> list[MemoryRecord]:
        rows = self.connection.execute(
            "SELECT * FROM records ORDER BY timestamp, record_id"
        ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def add_record_link(
        self,
        source_record_id: str,
        relation: str,
        target_record_id: str,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO record_links VALUES (?, ?, ?, ?)",
                (source_record_id, relation, target_record_id, _json(dict(evidence or {}))),
            )

    # ---------------------------------------------------------------- concepts

    def add_concept(self, concept: ConceptNode) -> ConceptNode:
        s_map_json = _json(_structural_map_to_dict(concept.structural_map)) if concept.structural_map else None
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO concepts(
                    concept_id, label, kind, embedding_json, terms_json, vault_id,
                    created_pulse, last_active_pulse, structural_map_json, invocation_count, softmax_weight
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    concept.concept_id,
                    concept.label,
                    concept.kind,
                    _json(concept.embedding),
                    _json(concept.terms),
                    concept.vault_id,
                    concept.created_pulse,
                    concept.last_active_pulse,
                    s_map_json,
                    concept.invocation_count,
                    concept.softmax_weight,
                ),
            )
        return self.get_concept(concept.concept_id) or concept

    @staticmethod
    def _concept_from_row(row: sqlite3.Row) -> ConceptNode:
        keys = row.keys()
        s_map_raw = row["structural_map_json"] if "structural_map_json" in keys else None
        s_map = _structural_map_from_dict(_loads(s_map_raw, None)) if s_map_raw else None
        inv_count = int(row["invocation_count"]) if "invocation_count" in keys else 0
        sm_weight = float(row["softmax_weight"]) if "softmax_weight" in keys else 1.0
        return ConceptNode(
            concept_id=row["concept_id"],
            label=row["label"],
            kind=row["kind"],
            embedding=as_tuple(_loads(row["embedding_json"], [])),
            terms=tuple(_loads(row["terms_json"], [])),
            vault_id=row["vault_id"],
            created_pulse=int(row["created_pulse"]),
            last_active_pulse=int(row["last_active_pulse"]),
            structural_map=s_map,
            invocation_count=inv_count,
            softmax_weight=sm_weight,
        )

    def get_concept(self, concept_id: str) -> ConceptNode | None:
        row = self.connection.execute(
            "SELECT * FROM concepts WHERE concept_id = ?", (concept_id,)
        ).fetchone()
        return self._concept_from_row(row) if row else None

    def list_concepts(self, *, kind: str | None = None) -> list[ConceptNode]:
        if kind is None:
            rows = self.connection.execute(
                "SELECT * FROM concepts ORDER BY concept_id"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM concepts WHERE kind = ? ORDER BY concept_id", (kind,)
            ).fetchall()
        return [self._concept_from_row(row) for row in rows]

    def mark_concepts_active(self, concept_ids: Iterable[str], pulse: int) -> None:
        with self.connection:
            self.connection.executemany(
                "UPDATE concepts SET last_active_pulse = ? WHERE concept_id = ?",
                ((pulse, concept_id) for concept_id in set(concept_ids)),
            )

    def set_concept_vault(self, concept_id: str, vault_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE concepts SET vault_id = ? WHERE concept_id = ?",
                (vault_id, concept_id),
            )

    def set_concept_structural_map(self, concept_id: str, s_map: StructuralMiniMap) -> None:
        s_map_json = _json(_structural_map_to_dict(s_map))
        with self.connection:
            self.connection.execute(
                "UPDATE concepts SET structural_map_json = ? WHERE concept_id = ?",
                (s_map_json, concept_id),
            )

    def increment_concept_invocation(self, concept_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE concepts SET invocation_count = invocation_count + 1 WHERE concept_id = ?",
                (concept_id,),
            )

    def update_concept_embedding(
        self,
        concept_id: str,
        embedding: Sequence[float],
        *,
        terms: Sequence[str] | None = None,
    ) -> None:
        assignments = ["embedding_json = ?"]
        values: list[Any] = [_json(tuple(float(value) for value in embedding))]
        if terms is not None:
            assignments.append("terms_json = ?")
            values.append(_json(tuple(dict.fromkeys(str(term) for term in terms))))
        values.append(concept_id)
        with self.connection:
            self.connection.execute(
                f"UPDATE concepts SET {', '.join(assignments)} WHERE concept_id = ?",
                values,
            )

    # -------------------------------------------------------------------- edges

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO edges(
                    edge_id, side, source_id, target_id, delta_y, log_strength,
                    conflict_penalty, last_active_time, created_pulse, archived,
                    invocation_count, softmax_weight
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.edge_id,
                    edge.side.value,
                    edge.source_id,
                    edge.target_id,
                    edge.delta_y,
                    edge.log_strength,
                    edge.conflict_penalty,
                    edge.last_active_time,
                    edge.created_pulse,
                    int(edge.archived),
                    edge.invocation_count,
                    edge.softmax_weight,
                ),
            )
        return self.get_edge(edge.edge_id) or edge

    @staticmethod
    def _edge_from_row(row: sqlite3.Row) -> GraphEdge:
        keys = row.keys()
        inv_count = int(row["invocation_count"]) if "invocation_count" in keys else 0
        sm_weight = float(row["softmax_weight"]) if "softmax_weight" in keys else 1.0
        return GraphEdge(
            edge_id=row["edge_id"],
            side=GraphSide(row["side"]),
            source_id=row["source_id"],
            target_id=row["target_id"],
            delta_y=float(row["delta_y"]),
            log_strength=float(row["log_strength"]),
            conflict_penalty=float(row["conflict_penalty"]),
            last_active_time=(
                float(row["last_active_time"])
                if row["last_active_time"] is not None
                else None
            ),
            created_pulse=int(row["created_pulse"]),
            archived=bool(row["archived"]),
            invocation_count=inv_count,
            softmax_weight=sm_weight,
        )

    def increment_edge_invocation(self, edge_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE edges SET invocation_count = invocation_count + 1 WHERE edge_id = ?",
                (edge_id,),
            )
        edge = self.get_edge(edge_id)
        if edge:
            self.update_softmax_weights_for_source(edge.source_id)

    def update_softmax_weights_for_source(self, source_id: str) -> None:
        import math
        rows = self.connection.execute(
            "SELECT edge_id, log_strength, invocation_count FROM edges WHERE source_id = ? AND archived = 0",
            (source_id,),
        ).fetchall()
        if not rows:
            return
        # Compute combined score: log_strength + log(1 + invocation_count)
        scores = [float(r["log_strength"]) + math.log(1.0 + int(r["invocation_count"])) for r in rows]
        max_score = max(scores)
        exps = [math.exp(s - max_score) for s in scores]
        sum_exps = sum(exps)
        softmax_weights = [e / sum_exps if sum_exps > 0 else 1.0 / len(rows) for e in exps]
        
        with self.connection:
            self.connection.executemany(
                "UPDATE edges SET softmax_weight = ? WHERE edge_id = ?",
                [(sm_w, r["edge_id"]) for sm_w, r in zip(softmax_weights, rows)],
            )

    def get_edge(self, edge_id: str) -> GraphEdge | None:
        row = self.connection.execute(
            "SELECT * FROM edges WHERE edge_id = ?", (edge_id,)
        ).fetchone()
        return self._edge_from_row(row) if row else None

    def find_edge(self, side: GraphSide, source_id: str, target_id: str) -> GraphEdge | None:
        row = self.connection.execute(
            "SELECT * FROM edges WHERE side = ? AND source_id = ? AND target_id = ?",
            (side.value, source_id, target_id),
        ).fetchone()
        return self._edge_from_row(row) if row else None

    def list_edges(self, side: GraphSide | None = None, *, include_archived: bool = False) -> list[GraphEdge]:
        clauses: list[str] = []
        values: list[Any] = []
        if side is not None:
            clauses.append("side = ?")
            values.append(side.value)
        if not include_archived:
            clauses.append("archived = 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.connection.execute(
            f"SELECT * FROM edges {where} ORDER BY edge_id", values
        ).fetchall()
        return [self._edge_from_row(row) for row in rows]

    def update_edge_state(
        self,
        edge_id: str,
        *,
        log_strength: float | None = None,
        conflict_penalty: float | None = None,
        last_active_time: float | None = None,
        archived: bool | None = None,
    ) -> None:
        assignments: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("log_strength", log_strength),
            ("conflict_penalty", conflict_penalty),
            ("last_active_time", last_active_time),
            ("archived", int(archived) if archived is not None else None),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(value)
        if not assignments:
            return
        values.append(edge_id)
        with self.connection:
            self.connection.execute(
                f"UPDATE edges SET {', '.join(assignments)} WHERE edge_id = ?", values
            )

    def add_edge_evidence(self, edge_id: str, record_id: str, relation: str = "supports") -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO edge_evidence VALUES (?, ?, ?)",
                (edge_id, record_id, relation),
            )

    # ------------------------------------------------------------------- vaults

    def add_to_vault(self, vault_id: str, record_id: str, concept_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO vault_membership VALUES (?, ?, ?)",
                (vault_id, record_id, concept_id),
            )

    def vault_record_ids(self, vault_id: str) -> list[str]:
        return [
            row["record_id"]
            for row in self.connection.execute(
                "SELECT record_id FROM vault_membership WHERE vault_id = ? ORDER BY record_id",
                (vault_id,),
            )
        ]

    def records_for_vault(self, vault_id: str) -> list[MemoryRecord]:
        rows = self.connection.execute(
            """
            SELECT r.* FROM vault_membership vm
            JOIN records r ON r.record_id = vm.record_id
            WHERE vm.vault_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM records newer WHERE newer.supersedes_id = r.record_id
              )
            ORDER BY r.timestamp, r.record_id
            """,
            (vault_id,),
        ).fetchall()
        return [self._record_from_row(row) for row in rows]

    # --------------------------------------------------- multi-resolution memory

    def update_experience_state(
        self,
        experience_id: str,
        *,
        preference: float,
        confidence: float,
        pulse: int,
    ) -> ExperienceState:
        bounded_preference = max(-1.0, min(1.0, float(preference)))
        bounded_confidence = max(0.0, min(1.0, float(confidence)))
        existing = self.connection.execute(
            "SELECT * FROM experience_state WHERE experience_id = ?",
            (experience_id,),
        ).fetchone()
        old_mean = float(existing["preference_mean"]) if existing else 0.0
        old_weight = float(existing["preference_weight"]) if existing else 0.0
        old_count = int(existing["observation_count"]) if existing else 0
        total_weight = old_weight + bounded_confidence
        mean = (
            (old_mean * old_weight + bounded_preference * bounded_confidence) / total_weight
            if total_weight > 0.0
            else old_mean
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO experience_state(
                    experience_id, preference_mean, preference_weight,
                    observation_count, last_pulse
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(experience_id) DO UPDATE SET
                    preference_mean=excluded.preference_mean,
                    preference_weight=excluded.preference_weight,
                    observation_count=excluded.observation_count,
                    last_pulse=excluded.last_pulse
                """,
                (experience_id, mean, total_weight, old_count + 1, int(pulse)),
            )
            self.connection.execute(
                """
                UPDATE experience_projections
                SET preference = ?, confidence = ?, pulse = MAX(pulse, ?)
                WHERE experience_id = ?
                """,
                (mean, min(1.0, total_weight), int(pulse), experience_id),
            )
        return ExperienceState(
            experience_id=experience_id,
            preference_mean=mean,
            preference_weight=total_weight,
            observation_count=old_count + 1,
            last_pulse=int(pulse),
        )

    def get_experience_state(self, experience_id: str) -> ExperienceState | None:
        row = self.connection.execute(
            "SELECT * FROM experience_state WHERE experience_id = ?",
            (experience_id,),
        ).fetchone()
        if row is None:
            return None
        return ExperienceState(
            experience_id=row["experience_id"],
            preference_mean=float(row["preference_mean"]),
            preference_weight=float(row["preference_weight"]),
            observation_count=int(row["observation_count"]),
            last_pulse=int(row["last_pulse"]),
        )

    def add_experience_projection(self, projection: ExperienceProjection) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO experience_projections(
                    experience_id, record_id, node_id, layer, side, activation,
                    preference, confidence, pulse, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id, node_id, side) DO UPDATE SET
                    activation=MAX(experience_projections.activation, excluded.activation),
                    preference=excluded.preference,
                    confidence=MAX(experience_projections.confidence, excluded.confidence),
                    pulse=MAX(experience_projections.pulse, excluded.pulse),
                    metadata_json=excluded.metadata_json
                """,
                (
                    projection.experience_id,
                    projection.record_id,
                    projection.node_id,
                    int(projection.layer),
                    projection.side.value,
                    max(0.0, min(1.0, float(projection.activation))),
                    max(-1.0, min(1.0, float(projection.preference))),
                    max(0.0, min(1.0, float(projection.confidence))),
                    int(projection.pulse),
                    _json(dict(projection.metadata)),
                ),
            )

    @staticmethod
    def _projection_from_row(row: sqlite3.Row) -> ExperienceProjection:
        return ExperienceProjection(
            experience_id=row["experience_id"],
            record_id=row["record_id"],
            node_id=row["node_id"],
            layer=int(row["layer"]),
            side=GraphSide(row["side"]),
            activation=float(row["activation"]),
            preference=float(row["preference"]),
            confidence=float(row["confidence"]),
            pulse=int(row["pulse"]),
            metadata=_loads(row["metadata_json"], {}),
        )

    def projections_for_node(self, node_id: str) -> list[ExperienceProjection]:
        rows = self.connection.execute(
            """
            SELECT * FROM experience_projections
            WHERE node_id = ? ORDER BY pulse, record_id
            """,
            (node_id,),
        ).fetchall()
        return [self._projection_from_row(row) for row in rows]

    def projections_for_experience(self, experience_id: str) -> list[ExperienceProjection]:
        rows = self.connection.execute(
            """
            SELECT * FROM experience_projections
            WHERE experience_id = ? ORDER BY layer, node_id, record_id
            """,
            (experience_id,),
        ).fetchall()
        return [self._projection_from_row(row) for row in rows]

    def has_record_projections(self, record_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM experience_projections WHERE record_id = ? LIMIT 1",
            (record_id,),
        ).fetchone() is not None

    def lower_vault_stats(self, node_id: str) -> Mapping[str, float | int]:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS projection_count,
                   COUNT(DISTINCT experience_id) AS experience_count,
                   COALESCE(AVG(preference), 0.0) AS preference_mean,
                   COALESCE(SUM(activation), 0.0) AS activation_total,
                   COALESCE(MAX(pulse), 0) AS last_pulse
            FROM experience_projections WHERE node_id = ?
            """,
            (node_id,),
        ).fetchone()
        return {
            "projection_count": int(row["projection_count"]),
            "experience_count": int(row["experience_count"]),
            "preference_mean": float(row["preference_mean"]),
            "activation_total": float(row["activation_total"]),
            "last_pulse": int(row["last_pulse"]),
        }

    # --------------------------------------------------------- overlap clusters

    @staticmethod
    def _cluster_from_row(row: sqlite3.Row) -> OverlapCluster:
        return OverlapCluster(
            cluster_id=row["cluster_id"],
            parent_node_id=row["parent_node_id"],
            centroid=as_tuple(_loads(row["centroid_json"], [])),
            record_ids=tuple(_loads(row["record_ids_json"], [])),
            experience_ids=tuple(_loads(row["experience_ids_json"], [])),
            preference_mean=float(row["preference_mean"]),
            confidence_mean=float(row["confidence_mean"]),
            first_pulse=int(row["first_pulse"]),
            last_pulse=int(row["last_pulse"]),
            child_node_id=row["child_node_id"],
            semantic_node_id=row["semantic_node_id"],
        )

    def list_overlap_clusters(self, parent_node_id: str) -> list[OverlapCluster]:
        rows = self.connection.execute(
            """
            SELECT * FROM overlap_clusters
            WHERE parent_node_id = ? ORDER BY first_pulse, cluster_id
            """,
            (parent_node_id,),
        ).fetchall()
        return [self._cluster_from_row(row) for row in rows]

    def overlap_cluster_for_child(self, child_node_id: str) -> OverlapCluster | None:
        row = self.connection.execute(
            "SELECT * FROM overlap_clusters WHERE child_node_id = ?",
            (child_node_id,),
        ).fetchone()
        return self._cluster_from_row(row) if row else None

    def put_overlap_cluster(self, cluster: OverlapCluster) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO overlap_clusters(
                    cluster_id, parent_node_id, centroid_json, record_ids_json,
                    experience_ids_json, preference_mean, confidence_mean,
                    first_pulse, last_pulse, child_node_id, semantic_node_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cluster_id) DO UPDATE SET
                    centroid_json=excluded.centroid_json,
                    record_ids_json=excluded.record_ids_json,
                    experience_ids_json=excluded.experience_ids_json,
                    preference_mean=excluded.preference_mean,
                    confidence_mean=excluded.confidence_mean,
                    last_pulse=excluded.last_pulse,
                    child_node_id=excluded.child_node_id,
                    semantic_node_id=excluded.semantic_node_id
                """,
                (
                    cluster.cluster_id,
                    cluster.parent_node_id,
                    _json(cluster.centroid),
                    _json(cluster.record_ids),
                    _json(cluster.experience_ids),
                    cluster.preference_mean,
                    cluster.confidence_mean,
                    cluster.first_pulse,
                    cluster.last_pulse,
                    cluster.child_node_id,
                    cluster.semantic_node_id,
                ),
            )

    # --------------------------------------------------------------- trace/audit

    def save_trace(self, pulse_id: str, trace: TraversalTrace) -> None:
        payload = {
            "trace_id": trace.trace_id,
            "side": trace.side.value,
            "start_node_id": trace.start_node_id,
            "target_node_id": trace.target_node_id,
            "path_node_ids": trace.path_node_ids,
            "path_edge_ids": trace.path_edge_ids,
            "total_travel_time": trace.total_travel_time,
            "endpoint_score": trace.endpoint_score,
            "evidence_record_ids": trace.evidence_record_ids,
        }
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO traces(trace_id, pulse_id, side, payload_json) VALUES (?, ?, ?, ?)",
                (trace.trace_id, pulse_id, trace.side.value, _json(payload)),
            )

    def save_outcome(self, outcome: OutcomePacket) -> None:
        payload = {
            "outcome_id": outcome.outcome_id,
            "pulse_id": outcome.pulse_id,
            "output_trunk": outcome.output_trunk.value if outcome.output_trunk else None,
            "credited_edge_ids": outcome.credited_edge_ids,
            "verified": outcome.verified,
            "stability_delta": outcome.stability_delta,
            "proposal_id": outcome.proposal_id,
            "receipt_id": outcome.receipt_id,
            "metadata": dict(outcome.metadata),
        }
        with self.connection:
            self.connection.execute(
                "INSERT INTO outcomes(outcome_id, pulse_id, payload_json) VALUES (?, ?, ?)",
                (outcome.outcome_id, outcome.pulse_id, _json(payload)),
            )
