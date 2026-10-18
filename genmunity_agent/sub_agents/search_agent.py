from typing import Dict, Any
from google.adk.agents import Agent

from genmunity_agent.config import (
    GEMINI_MODEL,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
    GDG_KOREA_SHEET_URL,
    record_agent_trace,
)
from genmunity_agent.crawler import get_data_crawler
from genmunity_agent.services import search_all_event_knowledge
from genmunity_agent.services.gdg_directory import search_gdg_gde_directory
from community_hub_agent.tools import (
    adaptive_hybrid_search,
    lookup_kr_organizer_sheet,
    query_community_knowledge_graph,
)


def rag_search_tool(query: str) -> Dict[str, Any]:
    """
    [RAGSearch] Search CommunityHub, Advocu, Google Slides, GDG/GDE Slack, the GDG Korea Organizers & GDE Directory,
    Knowledge Graph (Vector RAG + GraphRAG), and the Event Knowledge Base (including uploaded event photo attendee counts & RSVPs)
    for DevFest speaker candidates, DevFest/Build with AI season schedule/deadlines, supportable budgets,
    and live event status.

    Args:
        query: Natural language query (e.g., 'DevFest 핸즈온 스피커', '올해 DevFest 언제까지?', 'DevFest 예산', '이벤트 참석자 수 통계').
    """
    crawler = get_data_crawler()
    data = crawler.crawl_all_sources(query)
    kb_data = search_all_event_knowledge(query)
    adaptive_bundle = adaptive_hybrid_search(query=query, category="all", top_k=4)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="RAGSearch",
        summary=f"RAG + GraphRAG 하이브리드 검색 수행 (CommunityHub + GDG/GDE Directory + Event Knowledge Base): '{query}' (strategy={adaptive_bundle['routing']['strategy']})",
        details={
            "matched_speakers": [f"{s['name']} ({s['role']})" for s in data["speakers"]],
            "gde_matches_count": len(data.get("gdg_gde_directory", {}).get("gde_matches", [])),
            "gdg_exact_matches_count": len(data.get("gdg_gde_directory", {}).get("gdg_exact_matches", [])),
            "sheet_url": GDG_KOREA_SHEET_URL,
            "knowledge_base_matches": len(kb_data.get("knowledge_base_matches", [])),
            "routing": adaptive_bundle["routing"],
        },
    )
    return {
        "capability": "RAGSearch",
        "query": query,
        "recommended_speakers": data["speakers"],
        "gdg_gde_directory": data.get("gdg_gde_directory", {}),
        "devfest_schedule_deadline": DEVFEST_EVENT_INFO["season_deadline"],
        "devfest_event_date": DEVFEST_EVENT_INFO["event_date"],
        "devfest_budget_policy": DEVFEST_EVENT_INFO["budget_policy"],
        "gdg_korea_sheet": data["gdg_korea_sheet"],
        "community_hub": data.get("community_hub", {}),
        "events_overview": kb_data["events_overview"],
        "event_knowledge_base": kb_data["knowledge_base_matches"],
        "adaptive_rag_graph": adaptive_bundle,
    }


def search_gdg_gde_directory_tool(query: str = "", only_gde: bool = False) -> Dict[str, Any]:
    """
    [GDG & GDE Directory Search with PII Protection] Search the official GDG Korea Chapter Organizers
    and GDE (Google Developer Experts) Directory.
    Protects personal information by masking non-exact email addresses (`***`), while exposing
    speaker-outreach-eligible emails ONLY for verified GDEs or 100% exact-matched GDG members.

    Args:
        query: Name, GDE domain (AI, Flutter, Android, Cloud, Go, Firebase), GDG Chapter, or Slack ID.
        only_gde: If True, returns only verified GDEs.
    """
    res = search_gdg_gde_directory(query=query, only_gde=only_gde, unmask_exact_matches=True)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="GDGDirectorySearch",
        summary=(
            f"GDG/GDE 디렉토리 검색 (개인정보 보호 적용): '{query or '전체'}' "
            f"(GDE {len(res['gde_matches'])}명, GDG 완전매칭 {len(res['gdg_exact_matches'])}명)"
        ),
        details={
            "query": query,
            "only_gde": only_gde,
            "gde_matches": len(res["gde_matches"]),
            "gdg_exact_matches": len(res["gdg_exact_matches"]),
        },
    )
    return res


def crawl_community_hub_tool(force_refresh: bool = False) -> Dict[str, Any]:
    """
    [CommunityHub Live Crawler] Scrape https://developers.google.com/community/community-hub
    (and /event-series/devfest, /tools-and-platforms/speaker-matching, /content/highlighted-topics)
    using authenticated Chrome session cookies to retrieve the latest DevFest 2026 theme,
    highlighted topics (Agent Developer Kit, Antigravity, Gemini, Flutter), and Speaker Matching workflow.

    Args:
        force_refresh: If True, forces a live HTTP scrape of developers.google.com/community/community-hub.
    """
    crawler = get_data_crawler()
    hub = crawler.crawl_community_hub(force_refresh=force_refresh)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="CommunityHubCrawler",
        summary=(
            f"Google CommunityHub ({hub.get('hub_url')}) 인증 세션 스크래핑 완료 "
            f"(페이지 {len(hub.get('pages', []))}개, 쿠키 {hub.get('cookie_count', 0)}개)"
        ),
        details={
            "status": hub.get("status"),
            "authenticated": hub.get("authenticated"),
            "pages": [p.get("url") for p in hub.get("pages", [])],
        },
    )
    return hub


def search_event_knowledge_base_tool(query: str = "") -> Dict[str, Any]:
    """
    [Event Knowledge Base & Photo Attendee Stats] Search across all GDG/DevFest events,
    their knowledge base articles, RSVP statistics, and Gemini Vision photo attendee headcount records.

    Args:
        query: Topic, event title, or keyword to search in the event knowledge base.
    """
    res = search_all_event_knowledge(query)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="EventKnowledgeBase",
        summary=f"행사 지식 베이스 및 참석자 통계 검색: '{query or '전체'}'",
        details={"events_count": len(res["events_overview"]), "kb_matches": len(res["knowledge_base_matches"])},
    )
    return res


def hybrid_community_hub_rag_tool(query: str, category: str = "all") -> Dict[str, Any]:
    """
    [HybridRAG+GraphRAG] Query the 171-chunk Vector RAG index (text-embedding-005) and 435-node
    Knowledge Graph across DevFest Hub/Slides, Build with AI Hub/Slides, Korean Organizer Sheets
    ([External] GDG KR Communication.xlsx & [External] GDG, GDE, GDGoC List - Korea.xlsx),
    and GDG Korea #organizers Slack threads.

    Args:
        query: Question about DevFest, Build with AI, GDE directory, Chapter leads, Co-hosting graph, or Slack threads.
        category: Optional domain filter ('all', 'devfest', 'build_with_ai', 'kr_organizer').
    """
    bundle = adaptive_hybrid_search(query=query, category=category, top_k=5)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="HybridRAGGraphRAG",
        summary=f"Community Hub Vector RAG + GraphRAG 검색: '{query}' ({bundle['routing']['strategy']})",
        details={"routing": bundle["routing"]},
    )
    return bundle


def slack_search_tool(query: str) -> Dict[str, Any]:
    """
    [SlackSearch] Search GDG/GDE Slack channels (#organizers C04E1UAAY, #devfest-2026-organizers, #gde-korea-speakers)
    for speaker availability, hands-on session discussions, and organizer updates.

    Args:
        query: Keyword or topic to search in GDG/GDE Slack threads.
    """
    crawler = get_data_crawler()
    threads = crawler.crawl_slack_messages(query)
    real_slack = lookup_kr_organizer_sheet(query=query, top_k=4)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="SlackSearch",
        summary=f"GDG/GDE Slack 검색 수행: '{query}' ({len(threads)}건 + 실제 #organizers 스레드 매칭)",
        details={"thread_count": len(threads), "real_slack_hits": len(real_slack.get("results", []))},
    )
    return {
        "capability": "SlackSearch",
        "query": query,
        "matched_threads": threads,
        "kr_organizers_slack_rag": real_slack,
    }


def summarize_community_data_tool(focus: str = "all") -> Dict[str, Any]:
    """
    [Summarizing] Summarize crawled CommunityHub, Advocu, GDG Korea Sheet, Event Knowledge Base, and Slack data
    into an actionable briefing for event planners and OpsAgent handoff.

    Args:
        focus: Area to summarize ('speakers', 'schedule', 'budget', 'events', or 'all').
    """
    crawler = get_data_crawler()
    speakers = crawler.crawl_speakers()
    hub = crawler.crawl_community_hub(force_refresh=False)
    kb_data = search_all_event_knowledge("")
    record_agent_trace(
        agent_name="SearchAgent",
        capability="Summarizing",
        summary=f"커뮤니티 데이터 및 연사 매칭 요약 생성 (focus={focus})",
    )
    return {
        "capability": "Summarizing",
        "focus": focus,
        "speaker_handoff_payload": speakers,
        "community_hub_highlights": hub.get("devfest_2026_highlights", {}),
        "events_overview": kb_data["events_overview"],
        "summary_ko": (
            "1. 추천 핸즈온 연사자: (1) 첫번째 연사자 한성민 님 (AI GDE, sniper45han@gmail.com) - "
            "Google ADK & Gemini 멀티 에이전트 핸즈온 / (2) 두번째 연사자 박제창 님 (Flutter GDE, aristojeff@gmail.com) - "
            "Flutter & Gemini 크로스플랫폼 AI 앱 핸즈온.\n"
            f"2. 올해 DevFest 일정 마감: {DEVFEST_EVENT_INFO['season_deadline']}\n"
            f"3. 지원 가능 예산: {DEVFEST_EVENT_INFO['budget_policy']['summary']}\n"
            f"4. CommunityHub 공식 테마: {hub.get('devfest_2026_highlights', {}).get('theme', '')}"
        ),
    }


search_agent = Agent(
    name="SearchAgent",
    model=GEMINI_MODEL,
    description=(
        "CommunityHub(https://developers.google.com/community/community-hub), Google Slides, GDG/GDE Slack(#organizers), Advocu, 국내 운영진/GDE/GDGoC 디렉토리(개인정보 보호 마스킹 및 Vector RAG + GraphRAG), "
        "그리고 행사 지식 베이스(Form 응답 및 사진 참석자 수 추적 통계 포함)를 검색하여 "
        "DevFest/Build with AI 가이드, 핸즈온 연사자 매칭(한성민 AI GDE, 박제창 Flutter GDE 및 분야별 GDE/완전 매칭 GDG), 올해 DevFest 행사 기한, 지원 가능 예산, 이벤트 지식을 제공하는 에이전트."
    ),
    instruction="""당신은 Genmunity의 **SearchAgent**입니다.
Data Crawler와 Community Hub Vector RAG(171개 임베딩 청크) + GraphRAG(435개 노드, 843개 엣지)가 수집한 **Google CommunityHub (`https://developers.google.com/community/community-hub`)**, Google Slides, GDG/GDE Slack(`#organizers`), Advocu, 국내 GDG/GDE/GDGoC 운영진 시트 및 디렉토리, 그리고 **행사 지식 베이스(Event Knowledge Base, Google Form 연사 온보딩 응답 현황, Gemini Vision 참석자 수 통계)** 데이터를 기반으로 질문에 정확하고 간결하게 한국어로 답변하세요.

[개인정보 보호 및 발표자 안내 이메일 대상자 원칙]
- GDG Korea 챕터 및 GDE 디렉토리는 지정된 23개 이메일(1팀~6팀)로만 한정하여 사용합니다.
- 개발자(`sniper45han@gmail.com` 한성민, `aristojeff@gmail.com` 박제창 / Dreamwalker) 외 나머지 21명의 이름·소속·슬랙ID 등 개인정보는 모두 제거되어 이메일과 GDG/GDE·챕터 구분만 유지됩니다.
- 발표자 초청/안내 이메일 발송 대상은 반드시 허용된 23개 GDG/GDE 이메일 목록 내 대상자로만 한정하세요.

핵심 역량(Tools):
1. `rag_search_tool` (RAGSearch):
   - "DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어" ->
     * **첫번째 연사자**: **한성민** (`sniper45han@gmail.com`) — **AI GDE** (Google ADK & Gemini 4.0 Argon 멀티 에이전트 핸즈온)
     * **두번째 연사자**: **박제창** (`aristojeff@gmail.com`) — **Flutter GDE** (Flutter & Gemini 크로스플랫폼 AI 핸즈온)
   - "올해 DevFest 행사는 언제까지?" -> 2026년 9월 1일 ~ 12월 31일 (결과 보고서 및 정산 마감 12월 31일)
   - "DevFest 지원가능한 예산은?" -> 규모별 $1,500 ~ $5,000 (한화 약 200만 원 ~ 680만 원) + GDE 초청 여비 지원 정책 안내
2. `hybrid_community_hub_rag_tool` (HybridRAGGraphRAG):
   - DevFest, Build with AI 슬라이드(`1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE`), 2025 I/O Extended 가이드(`1d6c0wAYCs3zfROf9l6QbSjhLxZbrGByx4CnqaF6rPcY`), 2026 오프사이트 슬라이드(`1fnQNauWcxgt5eqhTAuaBGn2giNQU6f_f_fv3R7nAvp4`), 국내 GDG/GDE/GDGoC 디렉토리, 챕터 간 공동 주최(Co-hosting) 네트워크 및 2026 Active Rate 규정을 Vector RAG + GraphRAG로 정밀 검색
3. `search_gdg_gde_directory_tool` (GDG/GDE Directory Search): 허용된 23개 GDG/GDE 이메일(1팀~6팀, GDE 3명 · GDG 20명) 검색
4. `crawl_community_hub_tool` (CommunityHub Live Crawler): `https://developers.google.com/community/community-hub` 실시간 스크래핑 결과 조회
5. `search_event_knowledge_base_tool` (Event Knowledge Base): 이벤트별 지식 베이스 문서, 연사 Google Form 응답, 업로드된 현장 사진의 Gemini Vision 참석자 수 카운팅 통계 및 RSVP 현황 검색
6. `slack_search_tool` (SlackSearch): GDG/GDE 슬랙 채널(`#organizers` 포함) 내 연사 가용성 및 운영진 논의 검색
7. `summarize_community_data_tool` (Summarizing): 검색된 연사 및 행사 정보를 요약하고, 섭외/메일 발송/폼 생성 요청이 있을 경우 OpsAgent와 연계하도록 안내하세요.
""",
    tools=[
        rag_search_tool,
        hybrid_community_hub_rag_tool,
        query_community_knowledge_graph,
        search_gdg_gde_directory_tool,
        crawl_community_hub_tool,
        search_event_knowledge_base_tool,
        slack_search_tool,
        summarize_community_data_tool,
    ],
)

