"""ADK Function Tools for RAG Retrieval, Google Slides/Sheets Lookup, and Live Ingestion."""

from __future__ import annotations

from typing import Any

from community_hub_agent.ingestion.pipeline import CommunityHubIngestionPipeline
from community_hub_agent.rag.retriever import get_rag_retriever


def search_community_hub_rag(
    query: str,
    category: str = "all",
    top_k: int = 5,
) -> dict[str, Any]:
    """Searches the GDG/GDE Community Hub RAG knowledge base (Hybrid: Vertex AI Search + Custom Vector DB).

    Args:
        query: Search question or keywords from a GDG/GDE organizer (e.g., 'DevFest 로고 가이드', 'Build with AI 크레딧 신청').
        category: Optional domain filter. One of 'all', 'devfest', 'build_with_ai', 'kr_organizer', 'general'.
        top_k: Number of top matching document chunks to return (default: 5).
    """
    retriever = get_rag_retriever()
    return retriever.retrieve(query=query, category=category, top_k=top_k)


def search_devfest_knowledge(query: str, top_k: int = 4) -> dict[str, Any]:
    """Searches DevFest Community Hub documentation and all parsed DevFest Google Slides presentations.

    Args:
        query: Question regarding DevFest planning, timeline, branding rules, CFP, speaker kits, or slide decks.
        top_k: Number of relevant chunks to retrieve (default: 4).
    """
    retriever = get_rag_retriever()
    return retriever.retrieve(query=query, category="devfest", top_k=top_k)


def search_build_with_ai_knowledge(
    query: str, top_k: int = 4
) -> dict[str, Any]:
    """Searches Build with AI Community Hub (?hl=ko) and the Build with AI Google Slides presentation deck.

    Args:
        query: Question regarding Build with AI workshops, Google Cloud credits, hands-on labs, or slide decks.
        top_k: Number of relevant chunks to retrieve (default: 4).
    """
    retriever = get_rag_retriever()
    return retriever.retrieve(
        query=query, category="build_with_ai", top_k=top_k
    )


def lookup_kr_organizer_sheet(query: str, top_k: int = 5) -> dict[str, Any]:
    """Searches the Korean GDG/GDE Organizer Spreadsheet (.xlsx / Google Sheet) AND the GDG Korea `#organizers` Slack channel (`C04E1UAAY`).

    Args:
        query: Keyword or question about Korean GDG chapters, GDE speakers, active rates, domestic event settlement, venues (e.g., 서울 AI 허브 무료 대관), Slack announcements (2026 DevFest 25,000원 증액, 리바이스 데님 자켓, Agentathon 결과물, 신규 오거나이저 합류 등).
        top_k: Number of matching chunks to return (default: 5).
    """
    retriever = get_rag_retriever()
    return retriever.retrieve(query=query, category="kr_organizer", top_k=top_k)


def classify_rag_vs_graphrag(query: str) -> dict[str, Any]:
    """Classifies whether a question should use Vector RAG ('vector_rag'), GraphRAG ('graph_rag'), or Both ('hybrid_rag_graph').

    Args:
        query: The user's natural language question.
    """
    retriever = get_rag_retriever()
    return retriever.classify_query_strategy(query=query)


def query_community_knowledge_graph(
    query: str,
    max_hops: int = 2,
    top_k: int = 20,
) -> dict[str, Any]:
    """Queries the GDG/GDE Community Knowledge Graph (GraphRAG) for multi-hop entity relations and networks.

    Use this tool when the user asks relational or network questions such as:
    - Which GDG chapters co-hosted events together (연합/공동 주최 네트워크)?
    - Who isboth an organizer and a GDE/Speaker across 2024~2026 events (영문/국문 이름 매핑 포함)?
    - All events, speakers, topics, and venues connected to a specific chapter or person (Multi-hop 탐색)?
    - Shortest relationship path between two organizers, chapters, or campaigns.

    Args:
        query: Entity name or relational question (e.g., 'GDG Incheon 공동 주최 챕터', '박제창 오거나이저 및 연사 활동 이력').
        max_hops: Number of graph hops to traverse from matched seed entities (default: 2).
        top_k: Maximum number of graph triples/edges to return (default: 20).
    """
    retriever = get_rag_retriever()
    return retriever.retrieve_graph(query=query, max_hops=max_hops, top_k=top_k)


def adaptive_hybrid_search(
    query: str,
    category: str = "all",
    top_k: int = 5,
) -> dict[str, Any]:
    """Dynamically routes the query to Vector RAG, GraphRAG, or Hybrid (Vector RAG + GraphRAG) based on query analysis.

    Args:
        query: Natural language question from an organizer.
        category: Optional domain filter ('all', 'devfest', 'build_with_ai', 'kr_organizer').
        top_k: Number of top results to return (default: 5).
    """
    retriever = get_rag_retriever()
    return retriever.retrieve_adaptive(
        query=query, category=category, top_k=top_k
    )


def query_vertex_ai_search_grounding(query: str) -> dict[str, Any]:
    """Executes Approach 1 (Fully Managed Vertex AI Search / Agent Builder Grounding) directly.

    Args:
        query: Natural language question to ground against the Vertex AI Search Data Store.
    """
    retriever = get_rag_retriever()
    return retriever.vertex_search.generate_grounded_answer(query=query)


def sync_community_hub_sources(
    source_filter: str = "all",
    upload_to_gcs: bool = False,
) -> dict[str, Any]:
    """Crawls and re-indexes Community Hub pages, internal Google Slides, and the Korean Organizer Excel/Sheet into Vector DB + GraphRAG.

    Args:
        source_filter: Which source to ingest ('all', 'devfest', 'build_with_ai', 'kr_organizer').
        upload_to_gcs: Whether to also upload JSONL documents to GCS for Vertex AI Search Data Store ingestion.
    """
    pipeline = CommunityHubIngestionPipeline()
    return pipeline.run_ingestion(
        source_filter=source_filter,
        include_seed=True,
        upload_to_gcs=upload_to_gcs,
    )

