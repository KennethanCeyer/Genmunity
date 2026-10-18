"""RAG package supporting Vertex AI Search (Approach 1) and Modular Custom Vector DB (Approach 2)."""

from community_hub_agent.rag.embeddings import EmbeddingService
from community_hub_agent.rag.retriever import (
    CommunityHubRagRetriever,
    get_rag_retriever,
)
from community_hub_agent.rag.vector_store import (
    CloudSQLPgVectorStore,
    LocalHybridVectorStore,
    VertexAIVectorSearchStore,
)
from community_hub_agent.rag.vertex_search import VertexAISearchService

__all__ = [
    "CloudSQLPgVectorStore",
    "CommunityHubRagRetriever",
    "EmbeddingService",
    "LocalHybridVectorStore",
    "VertexAIVectorSearchStore",
    "VertexAISearchService",
    "get_rag_retriever",
]
