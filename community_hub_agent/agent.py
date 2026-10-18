"""Google ADK (Agent Development Kit) Multi-Agent & Workflow Hierarchy for GDG/GDE Event Organizers.

Exposes the mandatory `root_agent` variable for `adk web`, `adk run`, `adk api_server`,
and `to_a2a(root_agent)` Agent2Agent (A2A) protocol interoperability.

Supports Adaptive Retrieval Routing across:
1. Vector RAG (`vector_rag_specialist` & domain specialists): Semantic document, slide, and policy search.
2. GraphRAG (`graph_rag_specialist`): Multi-hop entity traversal across chapters, organizers, GDE speakers,
   co-hosted events, and bilingual (EN/KO) identity links.
3. Hybrid Workflow (`hybrid_rag_graph_workflow` — `SequentialAgent` + `ParallelAgent`): Concurrent
   Vector RAG + GraphRAG retrieval followed by unified context synthesis.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from community_hub_agent.config import settings
from community_hub_agent.tools import (
    adaptive_hybrid_search,
    classify_rag_vs_graphrag,
    lookup_kr_organizer_sheet,
    query_community_knowledge_graph,
    query_vertex_ai_search_grounding,
    search_build_with_ai_knowledge,
    search_community_hub_rag,
    search_devfest_knowledge,
    sync_community_hub_sources,
)
from community_hub_agent.workflows import build_rag_graph_workflow_agents

# Build ADK RAG + GraphRAG Workflow Sub-Agents
_workflow_agents = build_rag_graph_workflow_agents()
vector_rag_specialist = _workflow_agents["vector_rag_specialist"]
graph_rag_specialist = _workflow_agents["graph_rag_specialist"]
hybrid_rag_graph_workflow = _workflow_agents["hybrid_rag_graph_workflow"]

# 1. DevFest Specialist Sub-Agent
devfest_specialist = LlmAgent(
    name="devfest_specialist",
    model=settings.sub_model,
    description=(
        "DevFest 이벤트 시리즈 기획, 브랜딩/로고 가이드라인, 타임라인(D-60~D+7), "
        "연사/스폰서 피치덱 등 DevFest Community Hub 및 내부 Google Slides 전문 에이전트."
    ),
    instruction=(
        "당신은 GDG/GDE 운영진을 돕는 DevFest 전문 에이전트입니다.\n"
        "1. 반드시 `search_devfest_knowledge` 또는 `search_community_hub_rag` 도구를 호출하여 "
        "Community Hub 웹페이지와 페이지 내부의 모든 Google Slides 데이터를 검색하세요.\n"
        "2. 국내 챕터별 DevFest 개최 이력·공동 주최·연사 관계가 함께 질문된 경우 `query_community_knowledge_graph`를 추가로 호출하세요.\n"
        "3. 답변 시 반드시 출처 URL(`source_url`), 슬라이드 제목(`deck_title`), 슬라이드 번호(`slide_number`)를 함께 명시하세요."
    ),
    tools=[
        search_devfest_knowledge,
        search_community_hub_rag,
        query_community_knowledge_graph,
    ],
)

# 2. Build with AI Specialist Sub-Agent
build_with_ai_specialist = LlmAgent(
    name="build_with_ai_specialist",
    model=settings.sub_model,
    description=(
        "Build with AI (BWAI) 핸즈온 워크숍 기획, Google Cloud 크레딧(TryGCP) 신청/배포, "
        "Gemini/Vertex AI/ADK 실습 구성 및 공식 발표 슬라이드(1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE) 전문 에이전트."
    ),
    instruction=(
        "당신은 GDG/GDE 운영진을 위한 Build with AI(BWAI) 전문 에이전트입니다.\n"
        "1. 반드시 `search_build_with_ai_knowledge` 또는 `search_community_hub_rag` 도구를 호출하여 "
        "Build with AI Community Hub(?hl=ko)와 공식 Google Slides(21장) 데이터를 검색하세요.\n"
        "2. 국내 챕터의 2024~2026 Build with AI 개최 내역이나 연사/오거나이저 연결망 질문 시 `query_community_knowledge_graph`도 활용하세요.\n"
        "3. 실습용 Google Cloud 크레딧 신청 기한, 워크숍 시간표, 슬라이드 번호 및 출처 링크를 정확히 안내하세요."
    ),
    tools=[
        search_build_with_ai_knowledge,
        search_community_hub_rag,
        query_community_knowledge_graph,
    ],
)

# 3. Korean GDG/GDE Organizer Operations Specialist Sub-Agent
kr_organizer_ops_specialist = LlmAgent(
    name="kr_organizer_ops_specialist",
    model=settings.sub_model,
    description=(
        "국내 GDG 챕터 현황(Incheon, Seoul, Golang, Campus, Cloud, Android, Busan 등), 2024~2026 캠페인 운영 이력, "
        "26 Active Rate 활동성/오프보딩 정책, 정산/대관 스프레드시트([External] GDG KR Communication.xlsx) 및 "
        "GDG Korea `#organizers` 슬랙 채널(C04E1UAAY) 공지/스레드 전문 에이전트."
    ),
    instruction=(
        "당신은 대한민국 GDG/GDE 운영진 데이터([External] GDG KR Communication.xlsx / Google Sheets 및 GDG Korea `#organizers` 슬랙 채널) 전문 에이전트입니다.\n"
        "1. 개별 시트 행, 슬랙 `#organizers` 공지/스레드(2026 DevFest 1인당 25,000원 예산 증액, 서울 AI 허브 양재 무료 대관, 2026 Summit 리바이스 데님 자켓, GDG Incheon Agentathon 결과물, 신규 오거나이저 합류 등) 검색은 `lookup_kr_organizer_sheet`를 호출하고, "
        "오거나이저-연사(GDE) 겸임 여부·챕터 간 공동 주최(Co-hosting)·다중 탭/슬랙 연결 분석은 `query_community_knowledge_graph`를 호출하세요.\n"
        "2. 시트 탭(`sheet_title`: `26 DevFest`, `26 IOEX`, `26 BwAI`, `26 Active Rate` 등) 또는 슬랙 스레드 링크(`permalink`), 작성자, 날짜를 명확히 정리해 답변하세요."
    ),
    tools=[
        lookup_kr_organizer_sheet,
        query_community_knowledge_graph,
        adaptive_hybrid_search,
    ],
)

# 4. Mandatory Root Agent (`root_agent`) for ADK CLI & A2A Server
root_agent = LlmAgent(
    name="gdg_gde_community_hub_agent",
    model=settings.root_model,
    description=(
        "GDG 및 GDE 이벤트 운영진을 위한 통합 AI 오케스트레이터 에이전트. "
        "질문 유형에 따라 Vector RAG(문서/슬라이드/가이드라인), GraphRAG(챕터·오거나이저·GDE 연사·공동주최 다중 홉 관계망), "
        "또는 ADK Parallel+Sequential 하이브리드 워크플로우를 동적으로 선택하여 답변하고 A2A 프로토콜로 소통합니다."
    ),
    instruction=(
        "당신은 Google Developer Groups(GDG) 및 Google Developer Experts(GDE) 운영진을 지원하는 "
        "수석 커뮤니티 오케스트레이터 에이전트입니다.\n\n"
        "### 1. 질문 유형별 동적 라우팅 전략 (Adaptive RAG vs GraphRAG)\n"
        "질문을 받으면 먼저 `classify_rag_vs_graphrag` 또는 `adaptive_hybrid_search`를 호출하거나 아래 기준에 따라 최적의 에이전트/도구를 선택하세요:\n"
        "- **Case A: Vector RAG (`vector_rag` -> `search_community_hub_rag` / `vector_rag_specialist`)**\n"
        "  - 브랜드/로고 가이드라인, 준비 타임라인(D-60~D+7), Google Cloud 크레딧 신청 기한, 정산/세금계산서 규정, "
        "슬라이드 장표 세부 내용 검색 시 사용합니다.\n"
        "- **Case B: GraphRAG (`graph_rag` -> `query_community_knowledge_graph` / `graph_rag_specialist`)**\n"
        "  - '어떤 챕터들이 연합/공동 주최했는가?', '박제창(PARK JAICHANG) 오거나이저가 연사로도 참여한 행사는?', "
        "'특정 연사나 챕터와 연결된 모든 행사·장소·주제 네트워크는?' 같은 다중 홉(Multi-hop) 관계 추론 및 교차 시트 집계 질문 시 사용합니다.\n"
        "- **Case C: Hybrid RAG + GraphRAG (`hybrid_rag_graph` -> `adaptive_hybrid_search` / `hybrid_rag_graph_workflow`)**\n"
        "  - 관계망(공동 주최/인물/연사 네트워크)과 공식 가이드라인/슬라이드/정책 설명이 동시에 필요한 복합 질문일 때 "
        "Vector RAG와 GraphRAG를 병렬 실행하여 통합 답변을 제공합니다.\n\n"
        "### 2. 핵심 품질 수칙\n"
        "1. **근거 기반 응답**: 반드시 도구 실행 결과에 기반하여 답변하고 추측하지 마세요.\n"
        "2. **명확한 출처 표기(Citations)**: 답변 하단에 참고한 문서 제목, 출처 URL(`source_url`), "
        "Google Slides 슬라이드 번호, Excel/Sheets 탭(`sheet_title`) 및 GraphRAG 관계 트리플(`source --[relation]--> target`)을 함께 표기하세요.\n"
        "3. **데이터 동기화 요청 시**: `sync_community_hub_sources`를 호출하여 Vector DB와 Knowledge Graph를 동시에 갱신하세요."
    ),
    tools=[
        adaptive_hybrid_search,
        classify_rag_vs_graphrag,
        query_community_knowledge_graph,
        search_community_hub_rag,
        search_devfest_knowledge,
        search_build_with_ai_knowledge,
        lookup_kr_organizer_sheet,
        query_vertex_ai_search_grounding,
        sync_community_hub_sources,
    ],
    sub_agents=[
        devfest_specialist,
        build_with_ai_specialist,
        kr_organizer_ops_specialist,
        vector_rag_specialist,
        graph_rag_specialist,
        hybrid_rag_graph_workflow,
    ],
)
