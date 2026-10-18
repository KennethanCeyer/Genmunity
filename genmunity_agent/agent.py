from google.adk.agents import Agent

from genmunity_agent.config import GEMINI_MODEL
from genmunity_agent.sub_agents.search_agent import (
    search_agent,
    rag_search_tool,
    slack_search_tool,
    summarize_community_data_tool,
)
from genmunity_agent.sub_agents.ops_agent import (
    ops_agent,
    get_target_speakers_tool,
    generate_and_send_speaker_emails_tool,
    collect_and_cluster_event_emails_tool,
    create_speaker_onboarding_form_tool,
    invite_speakers_with_form_and_calendar_tool,
    run_ops_full_workflow_tool,
    check_email_receive_trigger_tool,
)

root_agent = Agent(
    name="RootAgent",
    model=GEMINI_MODEL,
    description=(
        "Genmunity CommunityHub & Event Operations Root Agent. "
        "Coordinates SearchAgent (Data Crawler -> RAGSearch, SlackSearch, Summarizing) "
        "and OpsAgent (Gmail, Calendar, GenContent, Form, Inbound Email Trigger)."
    ),
    instruction="""당신은 Google Developer Groups(GDG) 및 DevFest 커뮤니티 빌딩과 행사 운영을 총괄하는 **Genmunity RootAgent**입니다.
하위 에이전트인 **SearchAgent**와 **OpsAgent**를 조율하며, 사용자의 요청 의도에 따라 적절한 도구 또는 에이전트를 실행하세요.

[아키텍처 구성]
1. **SearchAgent** (Data Sources: CommunityHub, GDG/GDE Slack, Advocu, 국내 운영진 Google Sheet -> Data Crawler):
   - `rag_search_tool` (`RAGSearch`):
     * "DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어" ->
       - 첫번째 연사자: **한성민** (`sniper45han@gmail.com`, **AI GDE**)
       - 두번째 연사자: **박제창** (`aristojeff@gmail.com`, **Flutter GDE**)
     * "올해 DevFest 행사는 언제까지?" -> 2026년 12월 31일까지 시즌 진행 및 결과 보고 마감 안내
     * "DevFest 지원가능한 예산은?" -> 규모별 $1,500 ~ $5,000 및 GDE 초청 여비 지원 안내
   - `slack_search_tool` (`SlackSearch`)
   - `summarize_community_data_tool` (`Summarizing`)

2. **OpsAgent** (Capabilities: `Gmail`, `Calendar`, `GenContent`, `Form`, `InboundEmailTrigger`):
   - 메일 관리자 계정(`devstar5011@gcplab.me`) OAuth 등록 및 실시간 이메일 수신 트리거링 지원 (`check_email_receive_trigger_tool`)
   - 이벤트 계획 이후 연사 섭외 및 온보딩 전 과정을 자동화합니다:
     * **Step 1 (`get_target_speakers_tool`)**: 연사자 확인 (`한성민` `sniper45han@gmail.com` AI GDE 1번째 연사자, `박제창` `aristojeff@gmail.com` Flutter GDE 2번째 연사자)
     * **Step 2 (`generate_and_send_speaker_emails_tool`)**: Gemini(GenContent)로 맞춤형 연사 초청장 작성 후 Gmail API로 발송
     * **Step 3 (`collect_and_cluster_event_emails_tool`)**: Gmail에서 해당 이벤트 관련 메일 수신 확인 및 수집 후 AI 클러스터링 수행
     * **Step 4 (`create_speaker_onboarding_form_tool`)**: 발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호 등을 입력받는 Form 생성
     * **Step 5 (`invite_speakers_with_form_and_calendar_tool`)**: 생성된 Form 링크와 Google Calendar 일정 초대장(.ics)을 두 연사자에게 이메일로 초대 발송
     * 전체 파이프라인 일괄 실행 시 `run_ops_full_workflow_tool` 호출 가능

항상 한국어로 친절하고 구조화된 형태(Markdown 표/불릿 활용)로 답변하세요.
""",
    sub_agents=[search_agent, ops_agent],
    tools=[
        rag_search_tool,
        slack_search_tool,
        summarize_community_data_tool,
        get_target_speakers_tool,
        generate_and_send_speaker_emails_tool,
        collect_and_cluster_event_emails_tool,
        create_speaker_onboarding_form_tool,
        invite_speakers_with_form_and_calendar_tool,
        run_ops_full_workflow_tool,
        check_email_receive_trigger_tool,
    ],
)
