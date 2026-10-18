"""Approach 2: Modular Custom RAG Vector Store supporting Local Hybrid, Cloud SQL (pgvector), and Vertex AI Vector Search."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np

from community_hub_agent.config import settings
from community_hub_agent.ingestion.models import DocumentChunk
from community_hub_agent.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


def _tokenize_keywords(text: str) -> list[str]:
    return re.findall(r"[가-힣a-z0-9_]{2,}", text.lower())


class LocalHybridVectorStore:
    """In-memory & JSON-persisted Hybrid (Dense Cosine + BM25 Lexical) Vector Store."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        index_path: Path | None = None,
        seed_path: Path | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.index_path = index_path or settings.local_index_file
        self.seed_path = seed_path or settings.seed_file
        self.chunks: dict[str, DocumentChunk] = {}
        self._load_initial_data()

    def _load_initial_data(self) -> None:
        loaded: list[DocumentChunk] = []
        if self.index_path.exists():
            try:
                raw = json.loads(self.index_path.read_text(encoding="utf-8"))
                loaded = [DocumentChunk.model_validate(item) for item in raw]
            except Exception as exc:
                logger.warning("Failed reading local index file: %s", exc)

        if not loaded and self.seed_path.exists():
            try:
                raw = json.loads(self.seed_path.read_text(encoding="utf-8"))
                loaded = [DocumentChunk.model_validate(item) for item in raw]
            except Exception as exc:
                logger.warning("Failed reading seed file: %s", exc)

        if loaded:
            self.upsert_chunks(loaded, persist=False)

    def upsert_chunks(
        self, chunks: list[DocumentChunk], persist: bool = True
    ) -> int:
        missing_emb_chunks = [c for c in chunks if not c.embedding]
        if missing_emb_chunks:
            texts = [
                self.embedding_service.format_document(c.title, c.content)
                for c in missing_emb_chunks
            ]
            vectors = self.embedding_service.embed_texts(texts)
            for chunk, vec in zip(missing_emb_chunks, vectors):
                chunk.embedding = vec

        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk

        if persist:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            serialized = [c.model_dump() for c in self.chunks.values()]
            self.index_path.write_text(
                json.dumps(serialized, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return len(chunks)

    def search(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not self.chunks:
            self._load_initial_data()
        candidates = list(self.chunks.values())
        if category and category not in ("all", ""):
            candidates = [
                c
                for c in candidates
                if c.category == category
                or category in c.metadata.get("secondary_categories", [])
            ]
        if not candidates:
            return []

        query_vec = np.array(
            self.embedding_service.embed_query(query), dtype=np.float32
        )
        query_norm = float(np.linalg.norm(query_vec)) or 1.0
        query_tokens = _tokenize_keywords(query)

        scored_results: list[dict[str, Any]] = []
        for chunk in candidates:
            # 1. Dense Cosine Similarity
            dense_score = 0.0
            if chunk.embedding:
                doc_vec = np.array(chunk.embedding, dtype=np.float32)
                if doc_vec.shape == query_vec.shape:
                    doc_norm = float(np.linalg.norm(doc_vec)) or 1.0
                    dense_score = float(
                        np.dot(query_vec, doc_vec) / (query_norm * doc_norm)
                    )

            # 2. Lexical / Keyword Overlap Boost (Hybrid Search)
            doc_text_lower = f"{chunk.title} {chunk.content}".lower()
            lexical_hits = 0.0
            if query_tokens:
                for qt in query_tokens:
                    if qt in doc_text_lower:
                        lexical_hits += 1.0
                        if qt in chunk.title.lower():
                            lexical_hits += 0.5
                lexical_score = min(1.0, lexical_hits / len(query_tokens))
            else:
                lexical_score = 0.0

            hybrid_score = (0.45 * max(0.0, dense_score)) + (
                0.55 * lexical_score
            )
            effective_category = (
                category
                if (
                    category
                    and category not in ("all", "")
                    and category in chunk.metadata.get("secondary_categories", [])
                )
                else chunk.category
            )
            scored_results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "title": chunk.title,
                    "content": chunk.content,
                    "category": effective_category,
                    "primary_category": chunk.category,
                    "source_type": chunk.source_type,
                    "source_url": chunk.source_url,
                    "score": round(hybrid_score, 4),
                    "metadata": chunk.metadata,
                }
            )

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]


class CloudSQLPgVectorStore:
    """Cloud SQL / AlloyDB for PostgreSQL (`pgvector`) backend for Modular Custom RAG."""

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self.embedding_service = embedding_service
        self.conn_str = settings.pgvector_connection_string
        self.table_name = settings.pgvector_table_name

    @property
    def is_configured(self) -> bool:
        return bool(self.conn_str)

    def _ensure_schema(self, conn: Any) -> None:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    chunk_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    embedding vector(768)
                );
                """
            )
        conn.commit()

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not self.is_configured:
            return 0
        try:
            import psycopg
            from pgvector.psycopg import register_vector

            missing = [c for c in chunks if not c.embedding]
            if missing:
                vecs = self.embedding_service.embed_texts(
                    [
                        self.embedding_service.format_document(c.title, c.content)
                        for c in missing
                    ]
                )
                for c, v in zip(missing, vecs):
                    c.embedding = v

            with psycopg.connect(self.conn_str) as conn:
                self._ensure_schema(conn)
                register_vector(conn)
                with conn.cursor() as cur:
                    for c in chunks:
                        cur.execute(
                            f"""
                            INSERT INTO {self.table_name}
                            (chunk_id, title, content, category, source_type, source_url, metadata, embedding)
                            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                            ON CONFLICT (chunk_id) DO UPDATE SET
                                title = EXCLUDED.title,
                                content = EXCLUDED.content,
                                category = EXCLUDED.category,
                                source_type = EXCLUDED.source_type,
                                source_url = EXCLUDED.source_url,
                                metadata = EXCLUDED.metadata,
                                embedding = EXCLUDED.embedding;
                            """,
                            (
                                c.chunk_id,
                                c.title,
                                c.content,
                                c.category,
                                c.source_type,
                                c.source_url,
                                json.dumps(c.metadata, ensure_ascii=False),
                                c.embedding,
                            ),
                        )
                conn.commit()
            return len(chunks)
        except Exception as exc:
            logger.warning("Cloud SQL pgvector upsert failed: %s", exc)
            return 0

    def search(
        self, query: str, category: str | None = None, top_k: int = 5
    ) -> list[dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            import psycopg
            from pgvector.psycopg import register_vector

            query_vec = self.embedding_service.embed_query(query)
            with psycopg.connect(self.conn_str) as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    if category and category not in ("all", ""):
                        cur.execute(
                            f"""
                            SELECT chunk_id, title, content, category, source_type, source_url, metadata,
                                   1 - (embedding <=> %s::vector) AS score
                            FROM {self.table_name}
                            WHERE category = %s
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s;
                            """,
                            (query_vec, category, query_vec, top_k),
                        )
                    else:
                        cur.execute(
                            f"""
                            SELECT chunk_id, title, content, category, source_type, source_url, metadata,
                                   1 - (embedding <=> %s::vector) AS score
                            FROM {self.table_name}
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s;
                            """,
                            (query_vec, query_vec, top_k),
                        )
                    rows = cur.fetchall()
            return [
                {
                    "chunk_id": r[0],
                    "title": r[1],
                    "content": r[2],
                    "category": r[3],
                    "source_type": r[4],
                    "source_url": r[5],
                    "metadata": r[6] if isinstance(r[6], dict) else {},
                    "score": round(float(r[7]), 4),
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("Cloud SQL pgvector search failed: %s", exc)
            return []


class VertexAIVectorSearchStore:
    """Vertex AI Vector Search (Matching Engine) backend for massive-scale vector retrieval."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        local_store: LocalHybridVectorStore,
    ) -> None:
        self.embedding_service = embedding_service
        self.local_store = local_store
        self.index_endpoint_name = settings.vertex_vector_index_endpoint
        self.deployed_index_id = settings.vertex_vector_deployed_index_id

    @property
    def is_configured(self) -> bool:
        return bool(
            self.index_endpoint_name
            and "YOUR_ENDPOINT_ID" not in self.index_endpoint_name
        )

    def search(
        self, query: str, category: str | None = None, top_k: int = 5
    ) -> list[dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            from google.cloud import aiplatform
            from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import (
                Namespace,
            )

            aiplatform.init(
                project=settings.gcp_project or None,
                location=settings.gcp_location,
            )
            endpoint = aiplatform.MatchingEngineIndexEndpoint(
                index_endpoint_name=self.index_endpoint_name
            )
            query_vec = self.embedding_service.embed_query(query)
            filters = (
                [Namespace(name="category", allow_tokens=[category])]
                if category and category not in ("all", "")
                else []
            )
            response = endpoint.find_neighbors(
                deployed_index_id=self.deployed_index_id,
                queries=[query_vec],
                num_neighbors=top_k,
                filter=filters,
            )
            results: list[dict[str, Any]] = []
            for neighbor in response[0] if response else []:
                chunk = self.local_store.chunks.get(neighbor.id)
                if chunk:
                    results.append(
                        {
                            "chunk_id": chunk.chunk_id,
                            "title": chunk.title,
                            "content": chunk.content,
                            "category": chunk.category,
                            "source_type": chunk.source_type,
                            "source_url": chunk.source_url,
                            "score": round(float(neighbor.distance), 4),
                            "metadata": chunk.metadata,
                        }
                    )
            return results
        except Exception as exc:
            logger.warning("Vertex AI Vector Search query failed: %s", exc)
            return []
