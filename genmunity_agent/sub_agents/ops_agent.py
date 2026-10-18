from pathlib import Path
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
    evaluate_and_handle_inbound_inquiry,
    sync_live_gmail_profile,
    create_or_modify_event,
    generate_event_image_with_gemini,
    manage_event_rsvp,
    add_event_knowledge_entry,
    analyze_event_photo_and_track_attendees,
    sync_speaker_form_submission_to_event_state,
    get_main_event_readiness_summary,
    send_speaker_collaboration_proposal_emails,
)


def check_email_receive_trigger_tool(force_process_latest: bool = False) -> Dict[str, Any]:
    """
    [Gmail Inbound Trigger] Check the registered Mail Administrator account (devstar5011@gcplab.me,
    Star Developer 5011, Project: kr-devsummit26icn-501) INBOX for newly received inquiry or speaker emails,
    automatically reply from the Event Knowledge Base (or delegate out-of-KB inquiries to sniper45han@gmail.com
    and aristojeff@gmail.com), and trigger speaker clustering & onboarding Form/Calendar invite dispatch.

    Args:
        force_process_latest: If True, forces trigger execution on the latest matching inbox email for demo verification.
    """
    return check_and_trigger_on_inbound_emails(
        trigger_source="adk_ops_agent_tool",
        force_process_latest=force_process_latest,
    )


def handle_inbound_email_inquiry_tool(
    sender_email: str,
    subject: str,
    inquiry_body: str,
    sender_name: str = "문의자",
    event_id: str = "devfest-2026-seoul",
) -> Dict[str, Any]:
    """
    [Pub/Sub -> Cloud Run Inbound Inquiry Auto-Reply & Organizer Delegation]
    Process an incoming inquiry email sent to the Event Manager account (`devstar5011@gcplab.me`,
    `Star Developer 5011`, Assigned Project: `kr-devsummit26icn-501`):
    1. Searches the Event Knowledge Base (`search_all_event_knowledge` + `DEVFEST_EVENT_INFO`).
    2. If the inquiry can be answered using the Event Knowledge Base (`is_within_knowledge_base=True`):
       automatically replies to `sender_email` via Gmail (`action='auto_replied_from_kb'`).
    3. If the inquiry exceeds the Event Knowledge Base (`is_within_knowledge_base=False`):
       automatically delegates (forwards/escalates via email) the inquiry to the event organizers
       `sniper45han@gmail.com` (한성민) and `aristojeff@gmail.com` (박제창) (`action='delegated_to_organizers'`).

    Args:
        sender_email: Email address of the person asking the question.
        subject: Subject line of the inquiry email.
        inquiry_body: Full body text of the inquiry email.
        sender_name: Optional display name of the sender.
        event_id: Target event ID (default 'devfest-2026-seoul').
    """
    return evaluate_and_handle_inbound_inquiry(
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        inquiry_body=inquiry_body,
        event_id=event_id,
        trigger_source="adk_ops_agent_inquiry_tool",
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


def generate_and_send_sponsor_emails_tool(
    custom_context: str = "",
    target_email: str = "",
    company_name: str = "",
    contact_name: str = "",
    tier: str = "",
) -> Dict[str, Any]:
    """
    [GenContent + Gmail Sponsorship Proposal Outreach] Generate personalized DevFest 2026
    sponsor sponsorship proposal emails using Gemini (Tier 1 $1,500 / Tier 2 $3,000 / Tier 3 $5,000)
    and send them via Gmail API to target sponsor contacts (default: sniper45han@gmail.com, aristojeff@gmail.com).

    Args:
        custom_context: Optional additional instructions or sponsorship package context.
        target_email: Optional single sponsor recipient email address.
        company_name: Optional sponsor company name.
        contact_name: Optional sponsor contact person name.
        tier: Optional sponsorship tier label.
    """
    ws = get_workspace_service()
    res = ws.send_sponsor_outreach_emails(
        custom_context=custom_context,
        target_email=target_email or None,
        company_name=company_name or None,
        contact_name=contact_name or None,
        tier=tier or None,
    )
    record_agent_trace(
        agent_name="OpsAgent",
        capability="SponsorOutreach + Gmail",
        summary=(
            f"스폰서 후원 제안 이메일 생성 및 Gmail 발송 완료 ({res['total_sent']}건: "
            f"{', '.join(r['sponsor_email'] for r in res['sponsor_outreach_results'])})"
        ),
        details={
            "total_sent": res["total_sent"],
            "recipients": [r["sponsor_email"] for r in res["sponsor_outreach_results"]],
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


def record_speaker_form_response_tool(
    speaker_name: str = "한성민",
    email: str = "sniper45han@gmail.com",
    phone: str = "010-9123-4567",
    tshirt_size: str = "XL (105)",
    vehicle_number: str = "123가 4567",
    session_title: str = "",
) -> Dict[str, Any]:
    """
    [Google Form Response Sync -> Main Event State]
    Record or synchronize a speaker's onboarding Google Form submission (발표자 성함, 이메일, 연락처,
    티셔츠 사이즈, 차량 번호, 세션 제목) directly into the main Genmunity event state (`devfest-2026-seoul`).

    Args:
        speaker_name: Speaker full name (e.g. '한성민' or '박제창').
        email: Speaker email ('sniper45han@gmail.com' or 'aristojeff@gmail.com').
        phone: Mobile phone number for event day contact.
        tshirt_size: Welcome kit T-shirt size ('S (90)', 'M (95)', 'L (100)', 'XL (105)', '2XL (110)').
        vehicle_number: Vehicle license plate for free parking registration (or '없음').
        session_title: Confirmed hands-on session title.
    """
    return sync_speaker_form_submission_to_event_state(
        {
            "speaker_name": speaker_name,
            "email": email,
            "phone": phone,
            "tshirt_size": tshirt_size,
            "vehicle_number": vehicle_number,
            "session_title": session_title,
            "source": "adk_ops_agent_sync",
        }
    )


def analyze_event_photo_tool(
    event_id: str = "devfest-2026-seoul",
    filename: str = "event_photo.jpg",
    caption: str = "DevFest 2026 핸즈온 세션 현장 사진",
    image_path: str = "",
) -> Dict[str, Any]:
    """
    [Gemini Vision Photo Attendee Tracker] Analyze an event venue photo using Gemini Vision
    (gemini-4-argon / gemini-3.8-flash) to count detected attendees, estimate crowd density,
    and automatically update the event's `tracked_photo_attendees` and Event Knowledge Base.

    Args:
        event_id: Target event ID (default 'devfest-2026-seoul').
        filename: Photo filename label (e.g. 'session_photo.jpg').
        caption: Description or caption of the event photo.
        image_path: Optional local file path to an image to read bytes from.
    """
    image_bytes = None
    mime_type = "image/jpeg"
    if image_path:
        p = Path(image_path).expanduser()
        if p.exists() and p.is_file():
            image_bytes = p.read_bytes()
            if p.suffix.lower() == ".png":
                mime_type = "image/png"
            elif p.suffix.lower() == ".webp":
                mime_type = "image/webp"
            if filename == "event_photo.jpg":
                filename = p.name

    return analyze_event_photo_and_track_attendees(
        event_id=event_id,
        image_bytes=image_bytes,
        mime_type=mime_type,
        filename=filename,
        caption=caption,
    )


def generate_event_image_tool(
    prompt: str = "DevFest 2026 Seoul modern minimalist developer conference key visual banner",
    event_id: str = "devfest-2026-seoul",
    style: str = "Modern Minimal Tech",
) -> Dict[str, Any]:
    """
    [Gemini Image Generation] Generate an event key visual banner, poster, or RSVP illustration
    using Gemini Image Generation (`gemini-3.1-flash-image` / `gemini-2.5-flash-image`) and attach it
    to the specified event's banner and WYSIWYG gallery.

    Args:
        prompt: Image generation prompt describing the desired event banner or illustration.
        event_id: Target event ID (default 'devfest-2026-seoul').
        style: Visual style preset ('Modern Minimal Tech', '3D Isometric', 'Editorial Poster', 'Geometric Mono').
    """
    return generate_event_image_with_gemini(
        event_id=event_id,
        prompt=prompt,
        style=style,
        set_as_banner=True,
    )


def get_event_readiness_summary_tool() -> Dict[str, Any]:
    """
    [Event Operational Readiness Dashboard] Retrieve the comprehensive operational readiness summary
    for the primary DevFest 2026 event (`devfest-2026-seoul`), including readiness percentage,
    per-speaker 5-stage pipeline status, onboarding form submissions, RSVP count, and photo attendee count.
    """
    res = get_main_event_readiness_summary()
    record_agent_trace(
        agent_name="OpsAgent",
        capability="EventReadinessSummary",
        summary=(
            f"메인 이벤트 준비도 요약 조회 완료: 준비도 {res.get('readiness_pct')}% "
            f"(온보딩 완료 {res.get('completed_onboarding')}/{res.get('total_speakers')}명)"
        ),
        details={
            "readiness_pct": res.get("readiness_pct"),
            "completed_onboarding": res.get("completed_onboarding"),
        },
    )
    return res


def send_speaker_collaboration_proposal_tool() -> Dict[str, Any]:
    """
    [GDG/GDE Speaker Event Collaboration Proposal + RSVP Pie Chart + Event Bar Chart + MCP/Hub + Google Form]
    Audit all links, generate high-resolution RSVP Pie Chart and Event Operations Bar Chart PNGs,
    summarize the 3 key collaboration expectation bullets, and send the Event Collaboration Proposal email
    with the Participation Confirmation Google Form, Genmunity Hub Web URL, and Genmunity MCP Server URL
    to the verified GDE speakers (한성민 sniper45han@gmail.com, 박제창 aristojeff@gmail.com).
    """
    return send_speaker_collaboration_proposal_emails()


ops_agent = Agent(
    name="OpsAgent",
    model=GEMINI_MODEL,
    description=(
        "이벤트 계획 이후 연사자 섭외 메일 발송(Gmail + GenContent), 연사 및 운영 협력 제안서(RSVP 파이차트 + 행사 바차트 + 기대효과 3대 Bullets + MCP/Hub + 참여 여부 Google Form) 발송, "
        "스폰서 후원 제안 메일 발송(Gmail + GenContent), 행사 관련 수신 메일 수집 및 클러스터링(Gmail + GenContent), "
        "발표자 정보 입력 Form 생성(성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호), 캘린더 초대장 발송(Calendar + Gmail), "
        "Google Form 응답 수신 시 메인 이벤트 상태 동기화, "
        "담당자(devstar5011@gcplab.me / kr-devsummit26icn-501) 수신 문의의 지식 베이스 자동 회신 및 운영자(sniper45han@gmail.com, aristojeff@gmail.com) 이메일 딜리게이션, "
        "그리고 이벤트 생성/수정, 참가자 RSVP 관리, Gemini 이미지 생성(배너/포스터), 행사 지식 베이스 등록, Gemini Vision 현장 사진 참석자 수 분석을 수행하는 운영 자동화 에이전트."
    ),
    instruction="""당신은 Genmunity의 핵심 운영 자동화 에이전트인 **OpsAgent**입니다.
아키텍처에 정의된 핵심 모듈(**Gmail**, **Calendar**, **GenContent**, **Form**, **Pub/Sub -> Cloud Run Inbound Inquiry Auto-Reply & Delegation**, **Event & RSVP Management**, **Gemini Image Generation**, **Gemini Vision Photo Attendee Tracker**)을 조합하여 이벤트 기획부터 연사자 섭외, 문의 자동 회신/딜리게이션 및 참가자 RSVP/사후 정리를 자동화합니다.

[이벤트 행사 담당자 및 딜리게이션 운영자 정보]
- **행사 담당자(Event Manager)**: **Star Developer 5011** (`devstar5011@gcplab.me`, Assigned Project: `kr-devsummit26icn-501`)
- **행사 운영자(Delegation Recipients & GDE Speakers)**:
  1. **한성민** (`sniper45han@gmail.com`) — **행사 운영자 & AI GDE** (첫번째 연사자)
  2. **박제창** (`aristojeff@gmail.com`) — **행사 운영자 & Flutter GDE** (두번째 연사자)

[Pub/Sub -> Cloud Run 이메일 문의 자동 회신 & 운영자 딜리게이션]
- 담당자 계정(`devstar5011@gcplab.me`, Project: `kr-devsummit26icn-501`)에 문의가 도착하면 `handle_inbound_email_inquiry_tool` 또는 `check_email_receive_trigger_tool`을 실행합니다:
  1. 문의 내용이 **행사 이벤트 지식 베이스(Event Knowledge Base)** 범위 내(일정, 장소, 주차/차량번호, 티셔츠, 연사자 라인업, 예산/마감일, 크레딧 등)이면 지식 베이스를 활용해 문의자에게 즉시 **자동 회신 이메일**(`auto_replied_from_kb`)을 발송합니다.
  2. 문의 내용이 **행사 이벤트 지식 베이스 범위를 넘어서면**(기업 스폰서십 계약/세금계산서, VIP 만찬, 언론 취재 승인, 법률/NDA, 환불 분쟁, 대관 연장 특례 등) 행사 운영자인 `sniper45han@gmail.com`과 `aristojeff@gmail.com` 두 분에게 **이메일 딜리게이션(이관)**(`delegated_to_organizers`)을 자동 발송합니다.

[표준 운영 자동화 워크플로우 (5단계 + Form 응답 동기화 + 연사 협력 제안서)]
- **Step 1 (`get_target_speakers_tool`)**: 대상 연사자(한성민 AI GDE, 박제창 Flutter GDE) 정보 및 세션 트랙 확인
- **Step 2 (`generate_and_send_speaker_emails_tool`)**: Gemini(GenContent)로 맞춤형 연사 섭외 메일을 작성하고 Genmunity 이메일 디자인 시스템으로 Gmail API 발송 (`sniper45han@gmail.com`, `aristojeff@gmail.com`)
- **Speaker Collaboration Proposal (`send_speaker_collaboration_proposal_tool`)**: 현재 RSVP 파이차트 + 행사 운영 업데이트 바차트 + 운영진 공동 협력 기대효과 3대 Bullets + Genmunity MCP/Hub 웹사이트 + 참여 여부 Google Form을 포함한 행사 협력 제안서를 링크 사전 검수 후 발송
- **Sponsor Outreach (`generate_and_send_sponsor_emails_tool`)**: Gemini(GenContent)로 맞춤형 스폰서 후원 제안 메일(Tier 1 $1,500 / Tier 2 $3,000 / Tier 3 $5,000)을 작성하고 Gmail API로 발송
- **Step 3 (`collect_and_cluster_event_emails_tool`)**: Gmail에서 해당 이벤트/연사 관련 메일의 수신 및 발송 내역을 수집하고 의미별로 클러스터링
- **Step 4 (`create_speaker_onboarding_form_tool`)**: 발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호(주차 등록용), 발표 주제를 입력받는 Google Form 생성
- **Step 5 (`invite_speakers_with_form_and_calendar_tool`)**: 생성된 Google Form 링크와 Google Calendar 일정 초대장(.ics + Calendar API)을 두 연사자에게 발송
- **Form 응답 동기화 (`fetch_google_form_responses_tool`, `record_speaker_form_response_tool`)**: 연사자가 제출한 Google Form 응답을 조회하거나 등록하여 메인 시스템(DevFest 2026 이벤트 상태, 연사 온보딩 상태, 지식 베이스)을 즉시 업데이트
- 전체 과정을 한 번에 실행해달라는 요청이면 `run_ops_full_workflow_tool`을 호출하세요.

[이벤트 기획/수정, RSVP 조작, Gemini 배너 이미지 생성 및 현장 사진 참석자 분석]
- 이벤트 생성 또는 기존 이벤트 상태/정원/일정 수정 요청 시 `create_or_modify_event_tool`을 호출하세요.
- 이벤트 배너/포스터/RSVP 일러스트 이미지 생성 요청 시 `generate_event_image_tool`을 호출하세요.
- 참가자 RSVP 신청, 수정(트랙/식단 변경 등), 취소 요청 시 `manage_event_rsvp_tool`을 호출하세요.
- 행사 지식 베이스 추가 요청 시 `add_event_knowledge_tool`을 호출하세요.
- 현장 사진 기반 참석자 수 카운팅 및 분석 요청 시 `analyze_event_photo_tool`을 호출하세요.
- 행사 전체 준비도 및 연사별 온보딩 현황 조회 시 `get_event_readiness_summary_tool`을 호출하세요.

실행 결과를 브리핑할 때는 불필요하게 장황한 설명 없이 핵심 결과(발송 상태, 클러스터 요약, Form URL, 연사 온보딩 상태, 메인 이벤트 준비도)만 간결하고 구조화된 한국어 마크다운으로 정리해 주세요.
""",
    tools=[
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

