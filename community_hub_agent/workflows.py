"""Google ADK Agent Workflows for Adaptive Vector RAG + GraphRAG Orchestration.

Implements three complementary ADK execution patterns:
1. `vector_rag_specialist` (`LlmAgent`): Semantic chunk retrieval over Community Hub pages,
   parsed Google Slides (`2026 Build with AI`, `2025 I/O Extended`), and Excel/Sheet rows.
2. `graph_rag_specialist` (`LlmAgent`): Multi-hop Knowledge Graph traversal over `CommunityKnowledgeGraph`
   (organizers, GDE speakers, chapters, co-hosted networks, venues, topics, and bilingual identity links).
3. `hybrid_rag_graph_workflow` (`SequentialAgent` wrapping `ParallelAgent` + synthesizer `LlmAgent`):
   Executes Vector RAG and GraphRAG in parallel, stores results in `session.state` (`vector_rag_context`,
   `graph_rag_context`), and synthesizes a unified answer with document & graph citations.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from community_hub_agent.config import settings
from community_hub_agent.tools import (
    adaptive_hybrid_search,
    classify_rag_vs_graphrag,
    lookup_kr_organizer_sheet,
    query_community_knowledge_graph,
    search_build_with_ai_knowledge,
    search_community_hub_rag,
    search_devfest_knowledge,
)


def build_rag_graph_workflow_agents() -> dict[str, LlmAgent | ParallelAgent | SequentialAgent]:
    """Constructs the ADK specialist agents and the Parallel+Sequential Hybrid RAG+GraphRAG workflow."""

    # -------------------------------------------------------------------------
    # 1. Dedicated Vector RAG Specialist (Semantic Document & Slide Retrieval)
    # -------------------------------------------------------------------------
    vector_rag_specialist = LlmAgent(
        name="vector_rag_specialist",
        model=settings.sub_model,
        description=(
            "문서·가이드라인·발표 슬라이드·정산 규정 등 의미 기반(Semantic) 검색이 필요할 때 "
            "Vector RAG(Vertex AI Search + Custom Vector DB)로 답변하는 전문 에이전트."
        ),
        instruction=(
            "당신은 Vector RAG 전문 에이전트입니다.\n"
            "1. 질문의 도메인에 따라 `search_community_hub_rag`, `search_devfest_knowledge`, "
            "`search_build_with_ai_knowledge`, `lookup_kr_organizer_sheet` 중 가장 적합한 도구를 호출하세요.\n"
            "2. 검색된 청크의 핵심 내용과 함께 반드시 출처 URL(`source_url`), 슬라이드 제목/번호 또는 시트 탭/행 번호를 인용하세요."
        ),
        tools=[
            search_community_hub_rag,
            search_devfest_knowledge,
            search_build_with_ai_knowledge,
            lookup_kr_organizer_sheet,
        ],
    )

    # -------------------------------------------------------------------------
    # 2. Dedicated GraphRAG Specialist (Multi-Hop Entity & Network Traversal)
    # -------------------------------------------------------------------------
    graph_rag_specialist = LlmAgent(
        name="graph_rag_specialist",
        model=settings.sub_model,
        description=(
            "챕터 간 공동 주최(Co-hosting) 네트워크, 영문/국문 오거나이저-연사(GDE) 겸임 관계, "
            "연도별(2024~2026) 이벤트-연사-장소-주제 연결망 등 다중 홉(Multi-hop) 관계 추론이 필요할 때 "
            "Knowledge Graph(GraphRAG)를 탐색하는 전문 에이전트."
        ),
        instruction=(
            "당신은 GDG/GDE 커뮤니티 지식 그래프(GraphRAG) 전문 에이전트입니다.\n"
            "1. 반드시 `query_community_knowledge_graph` 도구를 호출하여 시드 엔티티(챕터, 오거나이저, 연사, 행사, 장소)와 "
            "다중 홉 관계 트리플(`PARTICIPATED_AS_ORGANIZER`, `SPOKE_AT`, `CO_HOSTED_WITH`, `ORGANIZER_OF`, `HELD_AT_VENUE`)을 조회하세요.\n"
            "2. 영문 이름(예: `PARK JAICHANG`, `Lee Young Bin`, `Sungmin Han`)과 국문 이름(예: `박제창`, `이영빈`, `한성민`)이 "
            "동일 인물 노드로 매핑된 그래프 특성을 활용하여 26 Active Rate 시트와 24~26 이벤트 시트 간의 연결 관계를 명확히 설명하세요.\n"
            "3. 답변 시 탐색된 그래프 경로(Entity A --[Relation]--> Entity B)와 출처 시트 탭(`sheet_title`)을 명시하세요."
        ),
        tools=[
            query_community_knowledge_graph,
            classify_rag_vs_graphrag,
        ],
    )

    # -------------------------------------------------------------------------
    # 3. Hybrid Parallel + Sequential Workflow (Vector RAG || GraphRAG -> Synthesizer)
    # -------------------------------------------------------------------------
    parallel_vector_researcher = LlmAgent(
        name="parallel_vector_researcher",
        model=settings.sub_model,
        description="병렬 워크플로우 내부에서 Vector RAG 문서·슬라이드·정책 청크를 수집하는 리서처.",
        instruction=(
            "사용자의 질문에서 가이드라인, 슬라이드 장표, 예산/정산 정책, 상세 설명에 해당하는 정보를 "
            "`search_community_hub_rag`로 검색하여 핵심 팩트와 출처(URL, 슬라이드 번호, 시트 행)를 요약하세요."
        ),
        tools=[
            search_community_hub_rag,
            search_devfest_knowledge,
            search_build_with_ai_knowledge,
            lookup_kr_organizer_sheet,
        ],
        output_key="vector_rag_context",
    )

    parallel_graph_researcher = LlmAgent(
        name="parallel_graph_researcher",
        model=settings.sub_model,
        description="병렬 워크플로우 내부에서 GraphRAG 엔티티 관계망 및 다중 홉 트리플을 수집하는 리서처.",
        instruction=(
            "사용자의 질문과 관련된 챕터, 오거나이저, GDE/연사, 공동 주최 네트워크, 행사 이력 관계를 "
            "`query_community_knowledge_graph`로 탐색하여 핵심 엔티티 노드, 관계 트리플, 최단 경로를 요약하세요."
        ),
        tools=[query_community_knowledge_graph],
        output_key="graph_rag_context",
    )

    parallel_rag_and_graph_retriever = ParallelAgent(
        name="parallel_rag_and_graph_retriever",
        description="Vector RAG 검색과 GraphRAG 지식 그래프 탐색을 동시에 병렬 수행하는 ADK ParallelAgent.",
        sub_agents=[
            parallel_vector_researcher,
            parallel_graph_researcher,
        ],
    )

    hybrid_context_synthesizer = LlmAgent(
        name="hybrid_context_synthesizer",
        model=settings.root_model,
        description="병렬 수집된 Vector RAG 컨텍스트와 GraphRAG 관계망 컨텍스트를 통합하여 최종 답변을 생성하는 에이전트.",
        instruction=(
            "당신은 Vector RAG와 GraphRAG 결과를 결합하는 하이브리드 신디사이저(Synthesizer) 에이전트입니다.\n"
            "세션 상태(Session State)에 저장된 두 가지 근거 데이터를 종합하여 답변을 작성하세요:\n"
            "- [Vector RAG 문서/슬라이드 컨텍스트]: {vector_rag_context}\n"
            "- [GraphRAG 엔티티/네트워크 컨텍스트]: {graph_rag_context}\n\n"
            "### 작성 지침\n"
            "1. 관계망/네트워크 분석 결과(챕터 간 공동 주최, 오거나이저·연사 활동 이력 등)와 "
            "공식 가이드라인/슬라이드/운영 정책 정보를 유기적으로 연결해 설명하세요.\n"
            "2. 답변 마지막에 **[참고 출처 (Vector RAG Chunks & GraphRAG Triples)]** 섹션을 만들어 "
            "문서 URL·슬라이드 번호와 그래프 관계 경로를 함께 제시하세요."
        ),
        tools=[adaptive_hybrid_search],
        output_key="hybrid_final_answer",
    )

    hybrid_rag_graph_workflow = SequentialAgent(
        name="hybrid_rag_graph_workflow",
        description=(
            "질문이 문서/슬라이드 가이드라인(Vector RAG)과 챕터·인물·행사 간 관계망(GraphRAG)을 모두 필요로 할 때, "
            "ParallelAgent로 두 검색을 동시 수행한 뒤 결과를 통합하는 ADK SequentialAgent 워크플로우."
        ),
        sub_agents=[
            parallel_rag_and_graph_retriever,
            hybrid_context_synthesizer,
        ],
    )

    return {
        "vector_rag_specialist": vector_rag_specialist,
        "graph_rag_specialist": graph_rag_specialist,
        "hybrid_rag_graph_workflow": hybrid_rag_graph_workflow,
    }
