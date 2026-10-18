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


def rag_search_tool(query: str) -> Dict[str, Any]:
    """
    [RAGSearch] Search CommunityHub, Advocu, and the GDG Korea Organizers Google Sheet
    for DevFest speaker candidates, DevFest season schedule/deadlines, and supportable budgets.

    Args:
        query: Natural language query (e.g., 'DevFest 핸즈온 스피커', '올해 DevFest 언제까지?', 'DevFest 예산').
    """
    crawler = get_data_crawler()
    data = crawler.crawl_all_sources(query)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="RAGSearch",
        summary=f"RAG 검색 수행: '{query}'",
        details={
            "matched_speakers": [f"{s['name']} ({s['role']})" for s in data["speakers"]],
            "sheet_url": GDG_KOREA_SHEET_URL,
        },
    )
    return {
        "capability": "RAGSearch",
        "query": query,
        "recommended_speakers": HARDCODED_SPEAKERS,
        "devfest_schedule_deadline": DEVFEST_EVENT_INFO["season_deadline"],
        "devfest_event_date": DEVFEST_EVENT_INFO["event_date"],
        "devfest_budget_policy": DEVFEST_EVENT_INFO["budget_policy"],
        "gdg_korea_sheet": data["gdg_korea_sheet"],
    }


def slack_search_tool(query: str) -> Dict[str, Any]:
    """
    [SlackSearch] Search GDG/GDE Slack channels (#devfest-2026-organizers, #gde-korea-speakers, #devfest-2026-ops)
    for speaker availability, hands-on session discussions, and organizer updates.

    Args:
        query: Keyword or topic to search in GDG/GDE Slack threads.
    """
    crawler = get_data_crawler()
    threads = crawler.crawl_slack_messages(query)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="SlackSearch",
        summary=f"GDG/GDE Slack 검색 수행: '{query}' ({len(threads)}건 매칭)",
        details={"thread_count": len(threads)},
    )
    return {
        "capability": "SlackSearch",
        "query": query,
        "matched_threads": threads,
    }


def summarize_community_data_tool(focus: str = "all") -> Dict[str, Any]:
    """
    [Summarizing] Summarize crawled CommunityHub, Advocu, GDG Korea Sheet, and Slack data
    into an actionable briefing for event planners and OpsAgent handoff.

    Args:
        focus: Area to summarize ('speakers', 'schedule', 'budget', or 'all').
    """
    record_agent_trace(
        agent_name="SearchAgent",
        capability="Summarizing",
        summary=f"커뮤니티 데이터 및 연사 매칭 요약 생성 (focus={focus})",
    )
    return {
        "capability": "Summarizing",
        "focus": focus,
        "speaker_handoff_payload": HARDCODED_SPEAKERS,
        "summary_ko": (
            "1. 추천 핸즈온 연사자: (1) 첫번째 연사자 한성민 님 (AI GDE, sniper45han@gmail.com) - "
            "Google ADK & Gemini 멀티 에이전트 핸즈온 / (2) 두번째 연사자 박제창 님 (Flutter GDE, aristojeff@gmail.com) - "
            "Flutter & Gemini 크로스플랫폼 AI 앱 핸즈온.\n"
            f"2. 올해 DevFest 일정 마감: {DEVFEST_EVENT_INFO['season_deadline']}\n"
            f"3. 지원 가능 예산: {DEVFEST_EVENT_INFO['budget_policy']['summary']}"
        ),
    }


search_agent = Agent(
    name="SearchAgent",
    model=GEMINI_MODEL,
    description=(
        "CommunityHub, GDG/GDE Slack, Advocu, 국내 운영진 Google Sheet 데이터를 크롤링 및 검색(RAGSearch, SlackSearch, Summarizing)하여 "
        "DevFest 핸즈온 연사자 매칭(한성민 AI GDE, 박제창 Flutter GDE), 올해 DevFest 행사 기한, 지원 가능 예산 정보를 제공하는 에이전트."
    ),
    instruction="""당신은 Genmunity의 **SearchAgent**입니다.
Data Crawler가 수집한 CommunityHub, GDG/GDE Slack, Advocu, 그리고 국내 GDG/GDE 운영진 공유 시트 데이터를 기반으로 질문에 정확하고 친절하게 한국어로 답변하세요.

핵심 역량(Tools):
1. `rag_search_tool` (RAGSearch):
   - "DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어" ->
     * **첫번째 연사자**: **한성민** (`sniper45han@gmail.com`) — **AI GDE** (Google ADK & Gemini 4.0 Argon 멀티 에이전트 핸즈온)
     * **두번째 연사자**: **박제창** (`aristojeff@gmail.com`) — **Flutter GDE** (Flutter & Gemini 크로스플랫폼 AI 핸즈온)
   - "올해 DevFest 행사는 언제까지?" -> 2026년 9월 1일 ~ 12월 31일 (결과 보고서 및 정산 마감 12월 31일)
   - "DevFest 지원가능한 예산은?" -> 규모별 $1,500 ~ $5,000 (한화 약 200만 원 ~ 680만 원) + GDE 초청 여비 지원 정책 안내
2. `slack_search_tool` (SlackSearch): GDG/GDE 슬랙 채널 내 연사 가용성 및 운영진 논의 검색
3. `summarize_community_data_tool` (Summarizing): 검색된 연사 및 행사 정보를 요약하고, 섭외/메일 발송/폼 생성 요청이 있을 경우 OpsAgent와 연계하도록 안내하세요.
""",
    tools=[rag_search_tool, slack_search_tool, summarize_community_data_tool],
)
