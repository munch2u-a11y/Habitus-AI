from __future__ import annotations

from abc import ABC, abstractmethod
import math
from typing import Any, Sequence


class BaseVectorAdapter(ABC):
    """Abstract Vector Store Adapter Interface for concept and record embeddings."""

    @abstractmethod
    def upsert(
        self,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Upsert a vector embedding into the store."""
        pass

    @abstractmethod
    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Query top_k similar vectors. Returns list of (vector_id, similarity_score, metadata)."""
        pass

    @abstractmethod
    def delete(self, vector_id: str) -> None:
        """Delete a vector by ID."""
        pass


class InMemoryVectorAdapter(BaseVectorAdapter):
    """In-Memory fallback Vector Store Adapter using pure Python math."""

    def __init__(self) -> None:
        self.vectors: dict[str, list[float]] = {}
        self.metadatas: dict[str, dict[str, Any]] = {}

    def upsert(
        self,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.vectors[vector_id] = list(embedding)
        self.metadatas[vector_id] = metadata or {}

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        scores: list[tuple[str, float, dict[str, Any]]] = []
        q_norm = math.sqrt(sum(x * x for x in query_embedding))
        if q_norm == 0.0:
            return []

        for vid, vec in self.vectors.items():
            meta = self.metadatas.get(vid, {})
            if filter_metadata:
                match = all(meta.get(k) == v for k, v in filter_metadata.items())
                if not match:
                    continue

            v_norm = math.sqrt(sum(x * x for x in vec))
            if v_norm == 0.0:
                score = 0.0
            else:
                dot = sum(a * b for a, b in zip(query_embedding, vec))
                score = dot / (q_norm * v_norm)

            scores.append((vid, score, meta))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def delete(self, vector_id: str) -> None:
        self.vectors.pop(vector_id, None)
        self.metadatas.pop(vector_id, None)


class ChromaVectorAdapter(BaseVectorAdapter):
    """Adapter for ChromaDB Vector Database."""

    def __init__(
        self,
        collection_name: str = "agentic_memory",
        persist_directory: str | None = None,
    ) -> None:
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb package is not installed. Install with 'pip install chromadb'"
            )

        if persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()

        self.collection = self.client.get_or_create_collection(name=collection_name)

    def upsert(
        self,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.collection.upsert(
            ids=[vector_id],
            embeddings=[embedding],
            metadatas=[metadata or {}],
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        where_clause = filter_metadata if filter_metadata else None
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause,
        )

        output: list[tuple[str, float, dict[str, Any]]] = []
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            distances = (
                results["distances"][0]
                if results.get("distances")
                else [0.0] * len(ids)
            )
            metadatas = (
                results["metadatas"][0]
                if results.get("metadatas")
                else [{}] * len(ids)
            )

            for vid, dist, meta in zip(ids, distances, metadatas):
                similarity = 1.0 / (1.0 + dist)
                output.append((vid, similarity, meta or {}))

        return output

    def delete(self, vector_id: str) -> None:
        self.collection.delete(ids=[vector_id])


class PineconeVectorAdapter(BaseVectorAdapter):
    """Adapter for Pinecone Vector Database."""

    def __init__(
        self,
        api_key: str,
        index_name: str,
        namespace: str = "agentic_memory",
    ) -> None:
        try:
            from pinecone import Pinecone
        except ImportError:
            raise ImportError(
                "pinecone-client package is not installed. Install with 'pip install pinecone-client'"
            )

        pc = Pinecone(api_key=api_key)
        self.index = pc.Index(index_name)
        self.namespace = namespace

    def upsert(
        self,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.index.upsert(
            vectors=[(vector_id, embedding, metadata or {})],
            namespace=self.namespace,
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        response = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter_metadata,
            namespace=self.namespace,
        )

        output: list[tuple[str, float, dict[str, Any]]] = []
        for match in response.get("matches", []):
            output.append((match["id"], match["score"], match.get("metadata", {})))

        return output

    def delete(self, vector_id: str) -> None:
        self.index.delete(ids=[vector_id], namespace=self.namespace)


class PgVectorAdapter(BaseVectorAdapter):
    """Adapter for PostgreSQL with pgvector extension."""

    def __init__(
        self,
        connection_string: str,
        table_name: str = "agentic_memory_vectors",
    ) -> None:
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError:
            raise ImportError(
                "psycopg and pgvector packages are required. Install with 'pip install psycopg[binary] pgvector'"
            )

        self.conn = psycopg.connect(connection_string, autocommit=True)
        register_vector(self.conn)
        self.table_name = table_name

        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id TEXT PRIMARY KEY,
                    embedding vector,
                    metadata JSONB
                );
            """)

    def upsert(
        self,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        import json

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.table_name} (id, embedding, metadata)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata;
            """,
                (vector_id, embedding, json.dumps(metadata or {})),
            )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        import json

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, 1 - (embedding <=> %s::vector) AS similarity, metadata
                FROM {self.table_name}
                ORDER BY embedding <=> %s::vector ASC
                LIMIT %s;
            """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()

        return [
            (
                row[0],
                float(row[1]),
                row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
            )
            for row in rows
        ]

    def delete(self, vector_id: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table_name} WHERE id = %s;", (vector_id,))
