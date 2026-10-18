from typing import Dict, Any
from google.adk.agents import Agent

from genmunity_agent.config import (
    GEMINI_MODEL,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
    record_agent_trace,
)
from genmunity_agent.services import (
    get_workspace_service,
    check_and_trigger_on_inbound_emails,
    sync_live_gmail_profile,
    create_or_modify_event,
    manage_event_rsvp,
    add_event_knowledge_entry,
)


def check_email_receive_trigger_tool(force_process_latest: bool = False) -> Dict[str, Any]:
    """
    [Gmail Inbound Trigger] Check the registered Mail Administrator account (devstar5011@gcplab.me)
    INBOX for newly received speaker emails (from sniper45han@gmail.com or aristojeff@gmail.com)
    and automatically trigger email clustering, speaker onboarding Form creation, and Calendar invite dispatch.

    Args:
        force_process_latest: If True, forces trigger execution on the latest matching inbox email for demo verification.
    """
    return check_and_trigger_on_inbound_emails(
        trigger_source="adk_ops_agent_tool",
        force_process_latest=force_process_latest,
    )



def get_target_speakers_tool() -> Dict[str, Any]:
    """
    [Speaker Search -> Ops Handoff] Retrieve the target DevFest Hands-on speakers
    (1st Speaker: 한성민 AI GDE sniper45han@gmail.com, 2nd Speaker: 박제창 Flutter GDE aristojeff@gmail.com).
    """
    record_agent_trace(
        agent_name="OpsAgent",
        capability="SpeakerSearchHandoff",
        summary="대상 연사자 2명 로드 완료: 한성민(AI GDE, 첫번째 연사자), 박제창(Flutter GDE, 두번째 연사자)",
        details={"speakers": HARDCODED_SPEAKERS},
    )
    return {
        "event_name": DEVFEST_EVENT_INFO["event_name"],
        "speakers": HARDCODED_SPEAKERS,
    }


def generate_and_send_speaker_emails_tool(custom_context: str = "") -> Dict[str, Any]:
    """
    [GenContent + Gmail] Generate personalized DevFest speaker invitation emails using Gemini
    and send them via Gmail API to:
    1. 한성민 (sniper45han@gmail.com) - AI GDE, 첫번째 연사자
    2. 박제창 (aristojeff@gmail.com) - Flutter GDE, 두번째 연사자

    Args:
        custom_context: Optional additional instructions or context for the invitation email.
    """
    ws = get_workspace_service()
    res = ws.send_outreach_to_all_speakers(custom_context=custom_context)
    record_agent_trace(
        agent_name="OpsAgent",
        capability="GenContent + Gmail",
        summary="연사 섭외 이메일 생성 및 Gmail 발송 완료 (한성민 sniper45han@gmail.com, 박제창 aristojeff@gmail.com)",
        details={
            "total_sent": res["total_sent"],
            "recipients": [r["speaker_email"] for r in res["outreach_results"]],
        },
    )
    return res


def collect_and_cluster_event_emails_tool(max_results: int = 20) -> Dict[str, Any]:
    """
    [Gmail + GenContent] Collect event-related emails from Gmail (checking delivery/receipt/replies
    for sniper45han@gmail.com and aristojeff@gmail.com) and cluster them semantically using Gemini.

    Args:
        max_results: Maximum number of event-related Gmail messages to inspect (default 20).
    """
    ws = get_workspace_service()
    res = ws.collect_and_cluster_emails(max_results=max_results)
    record_agent_trace(
        agent_name="OpsAgent",
        capability="Gmail + Clustering",
        summary=f"Gmail 행사 관련 메일 {res['total_emails_collected']}건 수신 확인 및 {len(res['clusters'])}개 클러스터 분류 완료",
        details={
            "total_emails": res["total_emails_collected"],
            "clusters": [c["cluster_name"] for c in res["clusters"]],
        },
    )
    return res


def create_speaker_onboarding_form_tool(form_title: str = "") -> Dict[str, Any]:
    """
    [Form] Create a Speaker Onboarding Form collecting required speaker details:
    - 발표자 성함 (Speaker Name)
    - 이메일 (Email)
    - 연락처 (Phone Number)
    - 티셔츠 사이즈 (T-Shirt Size)
    - 차량 번호 (Vehicle License Plate Number)
    - 핸즈온 세션 제목 및 필요 환경 (Session Topic)

    Args:
        form_title: Optional custom title for the speaker onboarding form.
    """
    ws = get_workspace_service()
    res = ws.create_speaker_onboarding_form(form_title=form_title or None)
    record_agent_trace(
        agent_name="OpsAgent",
        capability="Form",
        summary=f"발표자 사전 정보 입력 Form 생성 완료 (성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호): {res['primary_form_url']}",
        details={
            "form_id": res["form_id"],
            "primary_form_url": res["primary_form_url"],
            "fields": [f["label"] for f in res["fields"]],
        },
    )
    return res


def fetch_google_form_responses_tool(form_id: str = "") -> Dict[str, Any]:
    """
    [Google Forms API v1] Retrieve submitted speaker onboarding responses from Google Forms
    (forms.responses.list) for the given form_id (or latest form).

    Args:
        form_id: Optional Google Form ID to query responses for.
    """
    ws = get_workspace_service()
    res = ws.fetch_google_form_responses(form_id=form_id or None)
    record_agent_trace(
        agent_name="OpsAgent",
        capability="GoogleFormsResponses",
        summary=f"Google Forms 응답 조회 완료 (form_id={res.get('form_id')}, 응답 {len(res.get('responses', []))}건)",
        details=res,
    )
    return res


def invite_speakers_with_form_and_calendar_tool(form_id: str = "") -> Dict[str, Any]:
    """
    [Form + Calendar + Gmail] Send the generated Speaker Onboarding Form link and a Google Calendar
    invitation (.ics METHOD:REQUEST + Calendar API) via Gmail to:
    1. 한성민 (sniper45han@gmail.com) - AI GDE, 첫번째 연사자
    2. 박제창 (aristojeff@gmail.com) - Flutter GDE, 두번째 연사자

    Args:
        form_id: Optional form_id created in the previous step (uses latest form if empty).
    """
    ws = get_workspace_service()
    res = ws.send_speaker_form_and_calendar_invite(form_id=form_id or None)
    record_agent_trace(
        agent_name="OpsAgent",
        capability="Calendar + Form + Gmail",
        summary="연사자 2명에게 발표자 정보 입력 Form 링크 및 캘린더(.ics) 초대장 발송 완료",
        details={
            "form_url": res["primary_form_url"],
            "invited_speakers": [i["speaker_email"] for i in res["invites_sent"]],
        },
    )
    return res


def run_ops_full_workflow_tool(custom_context: str = "") -> Dict[str, Any]:
    """
    [End-to-End Ops Automation] Execute the entire post-planning OpsAgent pipeline sequentially:
    1. Speaker Search Handoff (한성민 AI GDE sniper45han@gmail.com, 박제창 Flutter GDE aristojeff@gmail.com)
    2. GenContent + Gmail: Send personalized speaker outreach emails
    3. Gmail + GenContent: Verify receipt in Gmail and cluster event-related emails
    4. Form: Create Speaker Onboarding Form (발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호)
    5. Calendar + Gmail: Send Onboarding Form link + Calendar Invite (.ics) to both speakers

    Args:
        custom_context: Optional additional message context for the speaker emails.
    """
    speakers_step = get_target_speakers_tool()
    outreach_step = generate_and_send_speaker_emails_tool(custom_context=custom_context)
    cluster_step = collect_and_cluster_event_emails_tool(max_results=20)
    form_step = create_speaker_onboarding_form_tool()
    invite_step = invite_speakers_with_form_and_calendar_tool(form_id=form_step["form_id"])

    return {
        "status": "ops_full_workflow_completed",
        "step_1_speakers": speakers_step,
        "step_2_gmail_outreach": outreach_step,
        "step_3_gmail_clustering": {
            "total_emails_collected": cluster_step["total_emails_collected"],
            "ai_summary": cluster_step["ai_summary"],
            "speaker_tracking": cluster_step["speaker_tracking"],
            "clusters": cluster_step["clusters"],
        },
        "step_4_onboarding_form": form_step,
        "step_5_calendar_and_form_invite": invite_step,
    }


def manage_event_rsvp_tool(
    attendee_name: str,
    attendee_email: str = "attendee@gdg.kr",
    event_id: str = "devfest-2026-seoul",
    action: str = "create",
    role: str = "Developer",
    track: str = "AI / Agentic Workflow Hands-on",
    dietary: str = "일반",
) -> Dict[str, Any]:
    """
    [Event RSVP Management] Create a new RSVP, modify an existing RSVP, or cancel an RSVP
    for a community event (callable from both the Main Chat and Event Gallery Detail Chat).

    Args:
        attendee_name: Name of the attendee (e.g. '김철수', '한성민').
        attendee_email: Email address of the attendee.
        event_id: Event ID or title (default 'devfest-2026-seoul').
        action: 'create', 'modify', or 'cancel'.
        role: Attendee role/job title.
        track: Preferred session track.
        dietary: Dietary preference ('일반', '비건', '할랄' 등).
    """
    return manage_event_rsvp(
        event_id=event_id,
        action=action,
        attendee_name=attendee_name,
        attendee_email=attendee_email,
        role=role,
        track=track,
        dietary=dietary,
    )


def create_or_modify_event_tool(
    title: str,
    event_id: str = "",
    date: str = "2026-11-21",
    venue: str = "구글 스타트업 캠퍼스 서울",
    status: str = "참가자 모집 중 (RSVP 오픈)",
    capacity: int = 150,
    budget: str = "$3,000",
    description: str = "",
) -> Dict[str, Any]:
    """
    [Event Planning & Modification] Create a new GDG/DevFest event or modify an existing event's
    title, date, venue, status, capacity, or budget via chat.

    Args:
        title: Title of the event to create or modify.
        event_id: Optional event_id if modifying an existing event (e.g. 'devfest-2026-seoul').
        date: Event date (YYYY-MM-DD).
        venue: Event venue location.
        status: Current operational status label.
        capacity: Maximum attendee capacity.
        budget: Allocated budget description.
        description: Detailed event overview.
    """
    return create_or_modify_event(
        event_id=event_id or None,
        title=title,
        date=date,
        venue=venue,
        status=status,
        capacity=capacity,
        budget=budget,
        description=description,
    )


def add_event_knowledge_tool(
    title: str,
    content: str,
    event_id: str = "devfest-2026-seoul",
    category: str = "Event Knowledge",
) -> Dict[str, Any]:
    """
    [Event Knowledge Base] Add a new knowledge base note, FAQ, or operational guideline to an event
    so that SearchAgent can retrieve it.

    Args:
        title: Title of the knowledge entry.
        content: Detailed content of the knowledge entry.
        event_id: Target event ID (default 'devfest-2026-seoul').
        category: Category label ('Logistics', 'Policy & Budget', 'FAQ', 'Session Note').
    """
    return add_event_knowledge_entry(
        event_id=event_id,
        title=title,
        content=content,
        category=category,
    )


ops_agent = Agent(
    name="OpsAgent",
    model=GEMINI_MODEL,
    description=(
        "이벤트 계획 이후 연사자 섭외 메일 발송(Gmail + GenContent), 행사 관련 수신 메일 수집 및 클러스터링(Gmail + GenContent), "
        "발표자 정보 입력 Form 생성(성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호), 캘린더 초대장 발송(Calendar + Gmail), "
        "그리고 이벤트 생성/수정 및 참가자 RSVP 관리, 행사 지식 베이스 등록을 수행하는 운영 자동화 에이전트."
    ),
    instruction="""당신은 Genmunity의 핵심 운영 자동화 에이전트인 **OpsAgent**입니다.
아키텍처에 정의된 핵심 모듈(**Gmail**, **Calendar**, **GenContent**, **Form**, **Event & RSVP Management**)을 조합하여 이벤트 기획부터 연사자 섭외 및 참가자 RSVP/사후 정리를 자동화합니다.

[기본 대상 연사자 (SearchAgent 연동 하드코딩 정보)]
1. **첫번째 연사자**: **한성민** (`sniper45han@gmail.com`) — **AI GDE**
2. **두번째 연사자**: **박제창** (`aristojeff@gmail.com`) — **Flutter GDE**

[표준 운영 자동화 워크플로우 (5단계)]
- **Step 1 (`get_target_speakers_tool`)**: 대상 연사자(한성민 AI GDE, 박제창 Flutter GDE) 정보 및 세션 트랙 확인
- **Step 2 (`generate_and_send_speaker_emails_tool`)**: Gemini(GenContent)로 맞춤형 연사 섭외 메일을 작성하고 Gmail API로 `sniper45han@gmail.com`, `aristojeff@gmail.com` 에 실제 발송
- **Step 3 (`collect_and_cluster_event_emails_tool`)**: Gmail에서 해당 이벤트/연사 관련 메일의 수신 및 발송 내역을 수집하고 의미별로 클러스터링(섭외/수신 확인, 회신/세션 조율, 온보딩/현장 운영)
- **Step 4 (`create_speaker_onboarding_form_tool`)**: 발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호(주차 등록용), 발표 주제를 입력받는 Form 생성
- **Step 5 (`invite_speakers_with_form_and_calendar_tool`)**: 생성된 Form 링크와 Google Calendar 일정 초대장(.ics)을 두 연사자(`sniper45han@gmail.com`, `aristojeff@gmail.com`)에게 발송
- 전체 과정을 한 번에 실행해달라는 요청이면 `run_ops_full_workflow_tool`을 호출하세요.

[이벤트 기획/수정 및 RSVP 조작]
- 이벤트 생성 또는 기존 이벤트 상태/정원/일정 수정 요청 시 `create_or_modify_event_tool`을 호출하세요.
- 참가자 RSVP 신청, 수정(트랙/식단 변경 등), 취소 요청 시 `manage_event_rsvp_tool`을 호출하세요.
- 행사 지식 베이스 추가 요청 시 `add_event_knowledge_tool`을 호출하세요.

실행 결과를 브리핑할 때는 발송된 Gmail 메시지 ID, 클러스터링 요약, 생성된 Form URL(필드: 발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호), 캘린더 초대 및 RSVP/이벤트 상태를 명확하고 친절하게 한국어로 정리해 주세요.
""",
    tools=[
        get_target_speakers_tool,
        generate_and_send_speaker_emails_tool,
        collect_and_cluster_event_emails_tool,
        create_speaker_onboarding_form_tool,
        fetch_google_form_responses_tool,
        invite_speakers_with_form_and_calendar_tool,
        run_ops_full_workflow_tool,
        check_email_receive_trigger_tool,
        manage_event_rsvp_tool,
        create_or_modify_event_tool,
        add_event_knowledge_tool,
    ],
)
