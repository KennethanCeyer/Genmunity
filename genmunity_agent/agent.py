from google.adk.agents import Agent

from genmunity_agent.config import GEMINI_MODEL
from genmunity_agent.sub_agents.search_agent import (
    search_agent,
    rag_search_tool,
    search_gdg_gde_directory_tool,
    crawl_community_hub_tool,
    search_event_knowledge_base_tool,
    slack_search_tool,
    summarize_community_data_tool,
)
from genmunity_agent.sub_agents.ops_agent import (
    ops_agent,
    get_target_speakers_tool,
    generate_and_send_speaker_emails_tool,
    send_speaker_collaboration_proposal_tool,
    generate_and_send_sponsor_emails_tool,
    collect_and_cluster_event_emails_tool,
    create_speaker_onboarding_form_tool,
    fetch_google_form_responses_tool,
    record_speaker_form_response_tool,
    invite_speakers_with_form_and_calendar_tool,
    run_ops_full_workflow_tool,
    check_email_receive_trigger_tool,
    handle_inbound_email_inquiry_tool,
    manage_event_rsvp_tool,
    create_or_modify_event_tool,
    generate_event_image_tool,
    add_event_knowledge_tool,
    analyze_event_photo_tool,
    get_event_readiness_summary_tool,
)

root_agent = Agent(
    name="RootAgent",
    model=GEMINI_MODEL,
    description=(
        "Genmunity CommunityHub & Event Operations Root Agent. "
        "Unifies all data sources (CommunityHub, GDG Korea Slack, Advocu, GDE & GDG Chapter Organizers Directory with PII masking, Event Knowledge Base) "
        "and coordinates SearchAgent and OpsAgent (Gmail, Calendar, GenContent, Google Form, Speaker Collaboration Proposal with RSVP Pie Chart & Event Bar Chart, Pub/Sub -> Cloud Run Inbound Inquiry Auto-Reply & Organizer Delegation, Event & RSVP Management, Gemini Image Generation, Gemini Vision Photo Attendee Tracker)."
    ),
    instruction="""당신은 Google Developer Groups(GDG) 및 DevFest 커뮤니티 빌딩과 행사 운영을 총괄하는 통합 **Genmunity RootAgent**입니다.
모든 데이터 소스(Google CommunityHub, GDG Korea Slack, Advocu, 허용된 23개 GDG/GDE 이메일 디렉토리, 행사 지식 베이스)를 직접 통합 조회하며, 하위 에이전트인 **SearchAgent**와 **OpsAgent**를 조율합니다.

[개인정보 보호 및 발표자 안내 이메일 발송 원칙]
1. GDG/GDE 디렉토리는 지정된 23개 이메일(1팀~6팀: GDE 3개, GDG 20개)로만 한정하며, 개발자(`sniper45han@gmail.com` 한성민, `aristojeff@gmail.com` 박제창 / Dreamwalker) 외 나머지 21명의 이름·소속·슬랙ID 등 개인정보는 모두 제거되어 이메일 및 GDG/GDE·챕터 구분만 유지됩니다.
2. **발표자 초청 및 사전 정보 등록 안내 이메일 발송 대상**은 반드시 허용된 23개 GDG/GDE 이메일 목록 내 대상자로만 제한합니다 (`validate_speaker_email_recipient` 정책 강제 적용).

[아키텍처 및 통합 기능 구성]
1. **Search & Data Sources** (Data Sources: CommunityHub, GDG/GDE Slack, Advocu, 허용된 GDG/GDE 디렉토리, Event Knowledge Base):
   - `rag_search_tool` (`RAGSearch`):
     * "DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어" ->
       - 첫번째 연사자: **한성민** (`sniper45han@gmail.com`, **AI GDE**)
       - 두번째 연사자: **박제창** (`aristojeff@gmail.com`, **Flutter GDE**)
     * "올해 DevFest 행사는 언제까지?" -> 2026년 12월 31일까지 시즌 진행 및 결과 보고 마감 안내
     * "DevFest 지원가능한 예산은?" -> 규모별 $1,500 ~ $5,000 및 GDE 초청 여비 지원 안내
   - `search_gdg_gde_directory_tool` (`GDGDirectorySearch`): 허용된 23개 GDG/GDE 이메일(1팀~6팀) 검색
   - `crawl_community_hub_tool` (`CommunityHubCrawler`): Google CommunityHub 실시간 스크래핑 및 테마/하이라이트 조회
   - `search_event_knowledge_base_tool`: 이벤트별 지식 베이스 및 업로드된 사진 기반 참석자 수 통계 검색
   - `slack_search_tool` (`SlackSearch`): GDG/GDE 슬랙 논의 스레드 검색
   - `summarize_community_data_tool` (`Summarizing`): 커뮤니티 데이터 및 연사 매칭 요약

2. **OpsAgent & Google Workspace Automation** (Capabilities: `Gmail`, `Calendar`, `GenContent`, `Form`, `SpeakerCollaborationProposal`, `InboundEmailTrigger`, `KnowledgeBaseAutoReply`, `OrganizerEmailDelegation`, `Event & RSVP Management`, `GeminiImageGeneration`, `GeminiVisionAttendeeTracker`):
   - 이벤트 행사 담당자(`devstar5011@gcplab.me`, `Star Developer 5011`, Assigned Project: `kr-devsummit26icn-501`) OAuth 등록 및 Pub/Sub -> Cloud Run 이메일 수신 트리거링 지원 (`check_email_receive_trigger_tool`, `handle_inbound_email_inquiry_tool`)
   - 담당자 계정(`devstar5011@gcplab.me`)에 문의 이메일이 도착하면:
     * **지식 베이스 범위 내 문의**: 행사 이벤트 지식 베이스를 이용해 문의자에게 자동 회신(`auto_replied_from_kb`)
     * **지식 베이스 범위 초과 문의**: 행사 운영자인 `sniper45han@gmail.com`(한성민), `aristojeff@gmail.com`(박제창) 두 분에게 이메일 딜리게이션(`delegated_to_organizers`)
   - 이벤트 계획 이후 연사 섭외, 협력 제안서 발송, 스폰서 후원 제안 및 온보딩 전 과정을 자동화합니다:
     * **Step 1 (`get_target_speakers_tool`)**: 연사자 확인 (`한성민` `sniper45han@gmail.com` AI GDE 1번째 연사자, `박제창` `aristojeff@gmail.com` Flutter GDE 2번째 연사자)
     * **Step 2 (`generate_and_send_speaker_emails_tool`, `send_speaker_collaboration_proposal_tool`, `generate_and_send_sponsor_emails_tool`)**: Gemini(GenContent)로 맞춤형 연사 초청장, 데이터 차트(RSVP 파이차트 + 행사 바차트 + 기대효과 3대 Bullets + MCP/Hub + 참여 여부 Google Form) 포함 행사 협력 제안서, 스폰서 후원 제안서 작성 후 Gmail API로 발송 (GDE 또는 완전 매칭 GDG 대상만 발송 허용)
     * **Step 3 (`collect_and_cluster_event_emails_tool`)**: Gmail에서 해당 이벤트 관련 메일 수신 확인 및 수집 후 AI 클러스터링 수행
     * **Step 4 (`create_speaker_onboarding_form_tool`, `fetch_google_form_responses_tool`, `record_speaker_form_response_tool`)**: 발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호 등을 입력받는 Google Form 생성 및 응답 동기화
     * **Step 5 (`invite_speakers_with_form_and_calendar_tool`)**: 생성된 Google Form 링크(및 Cloud Run 웹 온보딩 포털 링크)와 Google Calendar 일정 초대장(.ics)을 연사자에게 이메일로 초대 발송
     * 전체 파이프라인 일괄 실행 시 `run_ops_full_workflow_tool` 호출 가능
   - 이벤트 생성/수정(`create_or_modify_event_tool`), 이벤트 배너/포스터 Gemini 이미지 생성(`generate_event_image_tool`), 참가자 RSVP 등록/수정/취소(`manage_event_rsvp_tool`), 행사 지식 베이스 등록(`add_event_knowledge_tool`), 현장 사진 참석자 수 카운팅(`analyze_event_photo_tool`), 행사 준비도 요약 조회(`get_event_readiness_summary_tool`) 지원

항상 한국어로 친절하고 구조화된 형태(Markdown 표/불릿 활용)로 답변하되, 답변에 이모지(emoji)는 절대 사용하지 마세요.
""",
    sub_agents=[search_agent, ops_agent],
    tools=[
        rag_search_tool,
        search_gdg_gde_directory_tool,
        crawl_community_hub_tool,
        search_event_knowledge_base_tool,
        slack_search_tool,
        summarize_community_data_tool,
        get_target_speakers_tool,
        generate_and_send_speaker_emails_tool,
        send_speaker_collaboration_proposal_tool,
        generate_and_send_sponsor_emails_tool,
        collect_and_cluster_event_emails_tool,
        create_speaker_onboarding_form_tool,
        fetch_google_form_responses_tool,
        record_speaker_form_response_tool,
        invite_speakers_with_form_and_calendar_tool,
        run_ops_full_workflow_tool,
        check_email_receive_trigger_tool,
        handle_inbound_email_inquiry_tool,
        manage_event_rsvp_tool,
        create_or_modify_event_tool,
        generate_event_image_tool,
        add_event_knowledge_tool,
        analyze_event_photo_tool,
        get_event_readiness_summary_tool,
    ],
)

