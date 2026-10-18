"""Unified RAG & GraphRAG Retriever combining:
- Approach 1: Fully Managed Vertex AI Search (Agent Builder Data Store)
- Approach 2: Modular Custom Vector RAG (Vertex AI Embeddings + Vector DB)
- Approach 3: GraphRAG (Multi-Hop Knowledge Graph over Chapters, Organizers, GDEs, Speakers, Events, Venues, Topics)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from community_hub_agent.config import settings
from community_hub_agent.ingestion.models import DocumentChunk
from community_hub_agent.rag.embeddings import EmbeddingService
from community_hub_agent.rag.graph_rag import CommunityKnowledgeGraph
from community_hub_agent.rag.vector_store import (
    CloudSQLPgVectorStore,
    LocalHybridVectorStore,
    VertexAIVectorSearchStore,
)
from community_hub_agent.rag.vertex_search import VertexAISearchService

logger = logging.getLogger(__name__)

RetrievalStrategy = Literal["vector_rag", "graph_rag", "hybrid_rag_graph"]

_SINGLETON_RETRIEVER: CommunityHubRagRetriever | None = None

GRAPH_RELATIONAL_KEYWORDS = (
    "연합",
    "공동",
    "함께",
    "관계",
    "네트워크",
    "연결",
    "멀티홉",
    "그래프",
    "참여한",
    "발표한",
    "주최한",
    "개최한",
    "누구",
    "명단",
    "목록",
    "연사",
    "gde",
    "구글러",
    "장소",
    "대관",
    "비교",
    "모두",
    "전체",
    "히스토리",
    "이력",
)

VECTOR_GUIDELINE_KEYWORDS = (
    "가이드",
    "브랜드",
    "로고",
    "컬러",
    "폰트",
    "네이밍",
    "체크리스트",
    "신청 방법",
    "절차",
    "규정",
    "정책",
    "오프보딩",
    "슬라이드",
    "템플릿",
    "설문",
    "코드랩",
    "지원 조건",
    "예산",
    "시간표",
    "타임라인",
    "크레딧",
    "기한",
    "수칙",
)


class CommunityHubRagRetriever:
    """Unified RAG + GraphRAG engine supporting Vector RAG, Vertex AI Search, and Multi-Hop GraphRAG."""

    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.local_store = LocalHybridVectorStore(self.embedding_service)
        self.pgvector_store = CloudSQLPgVectorStore(self.embedding_service)
        self.vertex_vector_store = VertexAIVectorSearchStore(
            self.embedding_service, self.local_store
        )
        self.vertex_search = VertexAISearchService()
        self.knowledge_graph = CommunityKnowledgeGraph()

    def index_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Indexes chunks into the local hybrid store and configured cloud Vector DB."""
        count = self.local_store.upsert_chunks(chunks, persist=True)
        if settings.vector_backend == "pgvector" and self.pgvector_store.is_configured:
            self.pgvector_store.upsert_chunks(chunks)
        return count

    def classify_query_strategy(self, query: str) -> dict[str, Any]:
        """Determines whether a query is best served by `vector_rag`, `graph_rag`, or `hybrid_rag_graph`."""
        q_low = query.lower()
        seed_entities = self.knowledge_graph.resolve_entities(query)

        graph_Signals = sum(1 for kw in GRAPH_RELATIONAL_KEYWORDS if kw in q_low)
        vector_Signals = sum(1 for kw in VECTOR_GUIDELINE_KEYWORDS if kw in q_low)

        specific_entities = [
            nid
            for nid in seed_entities
            if nid.startswith(("person:", "chapter:", "venue:"))
        ]

        # Boost graph score when specific named entities (chapters, organizers, speakers, venues) are matched
        if len(specific_entities) >= 2 and (graph_Signals >= 1 or vector_Signals <= 1):
            graph_Signals += 2
        elif len(specific_entities) == 1 and graph_Signals >= 1:
            graph_Signals += 1

        if graph_Signals >= 2 and vector_Signals >= 1:
            strategy: RetrievalStrategy = "hybrid_rag_graph"
            reason = (
                "질문에 캠페인 가이드라인/정책 요소와 엔티티(챕터·운영진·연사·행사) 관계 분석 요소가 모두 포함되어 "
                "Vector RAG와 GraphRAG를 병렬 결합(Hybrid)합니다."
            )
        elif graph_Signals >= 2 or (
            len(specific_entities) >= 1 and graph_Signals >= 1 and vector_Signals == 0
        ):
            strategy = "graph_rag"
            reason = (
                "질문이 챕터·운영진·연사(GDE)·이벤트·장소 간의 멀티홉 관계, 연합 개최 네트워크, 또는 인물/챕터 이력을 묻고 있어 "
                "GraphRAG 서브그래프 탐색이 최적입니다."
            )
        else:
            strategy = "vector_rag"
            reason = (
                "질문이 행사 가이드라인, 브랜드 규칙, 슬라이드 본문, 지원 조건 등 문서/규정 검색에 해당하여 "
                "Vector RAG 시맨틱 검색이 최적입니다."
            )

        return {
            "strategy": strategy,
            "recommended_strategy": strategy,
            "reason": reason,
            "graph_signal_score": graph_Signals,
            "vector_signal_score": vector_Signals,
            "detected_graph_entities": seed_entities[:6],
        }

    def retrieve_custom_vector(
        self, query: str, category: str | None = None, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Approach 2: Queries the configured Modular Custom Vector DB (`pgvector`, `vertex_vector_search`, or `local`)."""
        backend = settings.vector_backend
        if backend == "pgvector" and self.pgvector_store.is_configured:
            results = self.pgvector_store.search(
                query=query, category=category, top_k=top_k
            )
            if results:
                return results
        elif (
            backend == "vertex_vector_search"
            and self.vertex_vector_store.is_configured
        ):
            results = self.vertex_vector_store.search(
                query=query, category=category, top_k=top_k
            )
            if results:
                return results

        return self.local_store.search(
            query=query, category=category, top_k=top_k
        )

    def retrieve_vertex_search(
        self, query: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Approach 1: Queries Fully Managed Vertex AI Search (Agent Builder Data Store)."""
        return self.vertex_search.search_datastore(query=query, top_k=top_k)

    def retrieve_graph(
        self, query: str, max_hops: int = 2, top_k: int = 20
    ) -> dict[str, Any]:
        """Approach 3: Queries the Knowledge Graph via GraphRAG k-hop subgraph & path traversal."""
        graph_res = self.knowledge_graph.query_subgraph(
            query=query, max_hops=max_hops, top_k=top_k
        )
        co_hosting = [
            rel
            for rel in graph_res.relationships
            if rel.get("relation") == "CO_HOSTED_WITH"
        ]
        return {
            "query": query,
            "retrieval_type": "graph_rag",
            "max_hops": max_hops,
            "graph_stats": self.knowledge_graph.get_stats(),
            "matched_entities": graph_res.matched_entities,
            "matched_seed_nodes": graph_res.matched_entities,
            "multi_hop_paths": graph_res.multi_hop_paths,
            "relationships": graph_res.relationships,
            "subgraph_triples": graph_res.relationships,
            "co_hosting_collaborations": co_hosting,
            "graph_analytics_summary": graph_res.graph_analytics_summary,
            "markdown_context": graph_res.markdown_context,
            "summary_markdown": graph_res.markdown_context,
        }

    def retrieve(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
        mode_override: str | None = None,
    ) -> dict[str, Any]:
        """Executes Vector RAG retrieval using `hybrid`, `custom`, or `vertex_search` mode with RRF fusion."""
        active_mode = mode_override or settings.rag_mode
        vertex_hits: list[dict[str, Any]] = []
        custom_hits: list[dict[str, Any]] = []

        if active_mode in ("vertex_search", "hybrid"):
            vertex_hits = self.retrieve_vertex_search(query=query, top_k=top_k)
            if category and category != "all":
                vertex_hits = [
                    hit
                    for hit in vertex_hits
                    if hit.get("category") == category
                ]

        if active_mode in ("custom", "hybrid") or not vertex_hits:
            custom_hits = self.retrieve_custom_vector(
                query=query, category=category, top_k=top_k
            )

        merged = self._reciprocal_rank_fusion(
            [custom_hits, vertex_hits], top_k=top_k
        )
        return {
            "query": query,
            "category_filter": category or "all",
            "rag_mode": active_mode,
            "vector_backend": settings.vector_backend,
            "vertex_search_configured": self.vertex_search.is_configured,
            "total_results": len(merged),
            "results": merged,
        }

    def retrieve_adaptive(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
        max_hops: int = 2,
        strategy_override: RetrievalStrategy | None = None,
    ) -> dict[str, Any]:
        """Dynamically routes or combines Vector RAG and GraphRAG based on query intent."""
        routing = self.classify_query_strategy(query)
        strategy: RetrievalStrategy = (
            strategy_override or routing["recommended_strategy"]
        )

        vector_payload: dict[str, Any] | None = None
        graph_payload: dict[str, Any] | None = None

        if strategy in ("vector_rag", "hybrid_rag_graph"):
            vector_payload = self.retrieve(
                query=query, category=category, top_k=top_k
            )

        if strategy in ("graph_rag", "hybrid_rag_graph"):
            graph_payload = self.retrieve_graph(
                query=query, max_hops=max_hops, top_k=max(top_k * 3, 15)
            )

        return {
            "query": query,
            "selected_strategy": strategy,
            "routing": routing,
            "routing_analysis": routing,
            "vector_rag": vector_payload,
            "graph_rag": graph_payload,
        }

    @staticmethod
    def _reciprocal_rank_fusion(
        result_lists: list[list[dict[str, Any]]],
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        rrf_scores: dict[str, float] = {}
        items_by_id: dict[str, dict[str, Any]] = {}

        for result_list in result_lists:
            for rank, item in enumerate(result_list, start=1):
                cid = item["chunk_id"]
                rrf_scores[cid] = (
                    rrf_scores.get(cid, 0.0)
                    + (1.0 / (rrf_k + rank))
                    + (float(item.get("score", 0.0)) * 0.05)
                )
                if cid not in items_by_id:
                    items_by_id[cid] = dict(item)

        sorted_ids = sorted(
            rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True
        )
        fused: list[dict[str, Any]] = []
        for cid in sorted_ids[:top_k]:
            entry = items_by_id[cid]
            entry["rrf_score"] = round(rrf_scores[cid], 5)
            fused.append(entry)
        return fused


def get_rag_retriever() -> CommunityHubRagRetriever:
    """Returns singleton CommunityHubRagRetriever instance."""
    global _SINGLETON_RETRIEVER
    if _SINGLETON_RETRIEVER is None:
        _SINGLETON_RETRIEVER = CommunityHubRagRetriever()
    return _SINGLETON_RETRIEVER
