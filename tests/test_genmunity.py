from fastapi.testclient import TestClient
from app import app
from genmunity_agent.config import HARDCODED_SPEAKERS, DEVFEST_EVENT_INFO
from genmunity_agent.sub_agents.search_agent import (
    rag_search_tool,
    slack_search_tool,
    summarize_community_data_tool,
)
from genmunity_agent.sub_agents.ops_agent import (
    get_target_speakers_tool,
    create_speaker_onboarding_form_tool,
)
from genmunity_agent.services import get_workspace_service

client = TestClient(app)


def test_hardcoded_speakers_configuration():
    assert len(HARDCODED_SPEAKERS) == 2
    s1, s2 = HARDCODED_SPEAKERS[0], HARDCODED_SPEAKERS[1]

    assert s1["speaker_order"] == 1
    assert s1["name"] == "한성민"
    assert s1["email"] == "sniper45han@gmail.com"
    assert s1["role"] == "AI GDE"

    assert s2["speaker_order"] == 2
    assert s2["name"] == "박제창"
    assert s2["email"] == "aristojeff@gmail.com"
    assert s2["role"] == "Flutter GDE"


def test_search_agent_rag_and_slack_tools():
    rag_res = rag_search_tool("DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어")
    assert rag_res["capability"] == "RAGSearch"
    assert len(rag_res["recommended_speakers"]) == 2
    assert "12월 31일" in rag_res["devfest_schedule_deadline"]
    assert "$1,500" in rag_res["devfest_budget_policy"]["summary"]

    slack_res = slack_search_tool("핸즈온")
    assert slack_res["capability"] == "SlackSearch"
    assert len(slack_res["matched_threads"]) >= 1

    sum_res = summarize_community_data_tool("all")
    assert "한성민" in sum_res["summary_ko"]
    assert "박제창" in sum_res["summary_ko"]


def test_ops_agent_speakers_and_onboarding_form():
    sp_res = get_target_speakers_tool()
    assert len(sp_res["speakers"]) == 2

    form_res = create_speaker_onboarding_form_tool("DevFest 2026 발표자 사전 정보 폼")
    assert "form_id" in form_res
    field_labels = [f["label"] for f in form_res["fields"]]
    assert "발표자 성함" in field_labels
    assert "이메일" in field_labels
    assert "연락처" in field_labels
    assert any("티셔츠 사이즈" in lbl for lbl in field_labels)
    assert any("차량 번호" in lbl for lbl in field_labels)

    # Test rendering and submitting the hosted Speaker Onboarding Form
    form_id = form_res["form_id"]
    get_resp = client.get(
        f"/forms/speaker-onboarding/{form_id}?name=한성민&email=sniper45han@gmail.com"
    )
    assert get_resp.status_code == 200
    assert "발표자 성함" in get_resp.text
    assert "티셔츠 사이즈" in get_resp.text
    assert "차량 번호" in get_resp.text

    post_resp = client.post(
        f"/forms/speaker-onboarding/{form_id}/submit",
        data={
            "speaker_name": "한성민",
            "email": "sniper45han@gmail.com",
            "phone": "010-1111-2222",
            "tshirt_size": "XL (105)",
            "vehicle_number": "123가 4568",
            "session_title": "Google ADK 멀티 에이전트 핸즈온",
        },
    )
    assert post_resp.status_code == 200
    assert "성공적으로 등록되었습니다" in post_resp.text


def test_ics_calendar_generation():
    ws = get_workspace_service()
    ics = ws.build_ics_calendar_invite(
        HARDCODED_SPEAKERS[0], "http://localhost:8080/forms/speaker-onboarding/test"
    )
    assert "BEGIN:VCALENDAR" in ics
    assert "METHOD:REQUEST" in ics
    assert "sniper45han@gmail.com" in ics
    assert DEVFEST_EVENT_INFO["venue"] in ics


def test_fastapi_dashboard_and_health():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["project"] == "Genmunity"
    assert health.json()["primary_model"] == "gemini-4-argon"
    assert health.json()["secondary_model"] == "gemini-3.8-flash"
    assert health.json()["mail_admin"]["target_admin_email"] == "devstar5011@gcplab.me"

    logo_resp = client.get("/logo.png")
    assert logo_resp.status_code == 200
    assert logo_resp.headers["content-type"] == "image/png"

    dash = client.get("/")
    assert dash.status_code == 200
    assert "Genmunity" in dash.text
    assert "devstar5011@gcplab.me" in dash.text
    assert "sniper45han@gmail.com" in dash.text
    assert "aristojeff@gmail.com" in dash.text


def test_mail_admin_status_and_toggle():
    status_resp = client.get("/api/admin/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["target_admin_email"] == "devstar5011@gcplab.me"

    toggle_resp = client.post(
        "/api/admin/trigger/toggle",
        json={"auto_trigger_enabled": True, "auto_send_form_on_reply": True},
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["mail_admin"]["auto_trigger_enabled"] is True


def test_events_gallery_rsvp_knowledge_and_photo_tracking():
    ev_list = client.get("/api/events")
    assert ev_list.status_code == 200
    events = ev_list.json()["events"]
    assert len(events) >= 1
    first_id = events[0]["event_id"]

    # Create RSVP
    rsvp_create = client.post(
        f"/api/events/{first_id}/rsvp",
        json={
            "action": "create",
            "name": "테스트참가자",
            "email": "test.attendee@gdg.kr",
            "role": "AI Engineer",
            "track": "AI / Agentic Workflow Hands-on",
            "dietary": "일반",
        },
    )
    assert rsvp_create.status_code == 200
    assert rsvp_create.json()["rsvp"]["name"] == "테스트참가자"

    # Modify existing RSVP
    rsvp_mod = client.post(
        f"/api/events/{first_id}/rsvp",
        json={
            "action": "modify",
            "name": "테스트참가자",
            "email": "test.attendee@gdg.kr",
            "track": "Flutter & On-Device AI Hands-on",
            "dietary": "비건",
        },
    )
    assert rsvp_mod.status_code == 200
    assert rsvp_mod.json()["action"] == "modified"
    assert rsvp_mod.json()["rsvp"]["dietary"] == "비건"

    # Add Knowledge Base item
    kb_resp = client.post(
        f"/api/events/{first_id}/knowledge",
        json={
            "title": "주차 지원 안내",
            "content": "오토웨이타워 지하 주차장 무료 등록 지원",
            "category": "Logistics",
        },
    )
    assert kb_resp.status_code == 200
    assert kb_resp.json()["status"] == "added"

    # Upload Event Photo and verify Attendee Tracking + Knowledge Base indexing
    with open("assets/logo.png", "rb") as img_f:
        photo_resp = client.post(
            f"/api/events/{first_id}/photos",
            data={"caption": "DevFest 핸즈온 세션 현장 사진"},
            files={"photo": ("session_photo.png", img_f, "image/png")},
        )
    assert photo_resp.status_code == 200
    p_data = photo_resp.json()
    assert p_data["status"] == "analyzed"
    assert "detected_headcount" in p_data["photo"]


def test_adk_a2a_and_mcp_endpoints():
    # A2A Agent Card
    card_resp = client.get("/.well-known/agent-card.json")
    assert card_resp.status_code == 200
    assert card_resp.json()["name"] == "RootAgent"

    # MCP Tools list (REST & JSON-RPC)
    mcp_get = client.get("/api/mcp/tools")
    assert mcp_get.status_code == 200
    tool_names = [t["name"] for t in mcp_get.json()["tools"]]
    assert "GenmunityRootAgent" in tool_names
    assert "rag_search_tool" in tool_names
    assert "manage_event_rsvp_tool" in tool_names

    mcp_rpc = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "rag_search_tool",
                "arguments": {"query": "DevFest 핸즈온 스피커"},
            },
        },
    )
    assert mcp_rpc.status_code == 200
    assert mcp_rpc.json()["result"]["isError"] is False
    assert "sniper45han@gmail.com" in mcp_rpc.json()["result"]["content"][0]["text"]


def test_pubsub_cloudrun_inquiry_kb_auto_reply_and_organizer_delegation():
    import base64
    import json

    # 1. Verify Event Manager (devstar5011@gcplab.me / kr-devsummit26icn-501) and Delegation Organizers
    inq_meta = client.get("/api/admin/inquiries")
    assert inq_meta.status_code == 200
    meta = inq_meta.json()
    assert meta["assigned_project"] == "kr-devsummit26icn-501"
    assert meta["event_manager"]["username"] == "devstar5011@gcplab.me"
    assert meta["event_manager"]["first_name"] == "Star"
    assert meta["event_manager"]["last_name"] == "Developer 5011"
    assert meta["pubsub_topic"] == "projects/kr-devsummit26icn-501/topics/gmail-push-topic"

    # 2. Case A: Inquiry within Event Knowledge Base -> Auto-Reply via Pub/Sub -> Cloud Run (/gmail-webhook)
    kb_payload_b64 = base64.b64encode(
        json.dumps(
            {
                "emailAddress": "devstar5011@gcplab.me",
                "historyId": "900101",
                "sender_email": "attendee.kim@gdg.kr",
                "sender_name": "김철수",
                "subject": "[DevFest 문의] 행사 장소와 오토웨이타워 무료 주차, 핸즈온 연사자 라인업 문의",
                "inquiry_body": "DevFest 2026 행사 장소가 어디인지, 주차 등록이 지원되는지, 그리고 한성민/박제창 연사님 발표 주제가 궁금합니다.",
            }
        ).encode("utf-8")
    ).decode("utf-8")

    webhook_kb_resp = client.post(
        "/gmail-webhook",
        json={
            "message": {
                "data": kb_payload_b64,
                "messageId": "pubsub-msg-kb-1",
            },
            "subscription": "projects/kr-devsummit26icn-501/subscriptions/gmail-push-cloudrun-sub",
        },
    )
    assert webhook_kb_resp.status_code == 200
    w_kb = webhook_kb_resp.json()
    assert w_kb["assigned_project"] == "kr-devsummit26icn-501"
    assert w_kb["event_manager"] == "devstar5011@gcplab.me"
    kb_res = w_kb["direct_inquiry_result"]
    assert kb_res is not None
    assert kb_res["is_within_knowledge_base"] is True
    assert kb_res["action"] == "auto_replied_from_kb"
    assert kb_res["auto_reply"]["to_email"] == "attendee.kim@gdg.kr"

    # 3. Case B: Inquiry exceeding Event Knowledge Base -> Delegate to sniper45han@gmail.com & aristojeff@gmail.com
    out_of_kb_resp = client.post(
        "/api/admin/inquiry/process",
        json={
            "sender_email": "sponsor@enterprise.co.kr",
            "sender_name": "박팀장",
            "subject": "[특례 문의] 기업 단독 스폰서십 계약 체결, 세금계산서 선발행 및 VIP 만찬 요청",
            "inquiry_body": "지식 베이스에 없는 당사 맞춤형 스폰서십 NDA 계약 체결, 세금계산서 발행, 야간 대관 시간 연장 특례 승인을 요청합니다.",
            "event_id": "devfest-2026-seoul",
        },
    )
    assert out_of_kb_resp.status_code == 200
    deleg_res = out_of_kb_resp.json()
    assert deleg_res["is_within_knowledge_base"] is False
    assert deleg_res["action"] == "delegated_to_organizers"
    assert "sniper45han@gmail.com" in deleg_res["delegated_organizers"]
    assert "aristojeff@gmail.com" in deleg_res["delegated_organizers"]
    org_emails = [o["organizer_email"] for o in deleg_res["delegation"]["organizers"]]
    assert "sniper45han@gmail.com" in org_emails
    assert "aristojeff@gmail.com" in org_emails


def test_speaker_invitation_and_sponsor_sponsorship_email_scenarios():
    # Scenario 1: Speaker Invitation Email Dispatch (한성민 AI GDE & 박제창 Flutter GDE)
    speaker_outreach_resp = client.post(
        "/api/ops/outreach",
        json={
            "custom_context": "DevFest 2026 핸즈온 세션 공식 연사 초청 및 사전 온보딩 안내",
        },
    )
    assert speaker_outreach_resp.status_code == 200
    sp_data = speaker_outreach_resp.json()
    assert sp_data["status"] == "completed"
    assert sp_data["total_sent"] == 2
    sent_speaker_emails = [r["speaker_email"] for r in sp_data["outreach_results"]]
    assert "sniper45han@gmail.com" in sent_speaker_emails
    assert "aristojeff@gmail.com" in sent_speaker_emails
    for r in sp_data["outreach_results"]:
        assert r["email_type"] == "outreach"
        assert "[DevFest 2026]" in r["subject"]
        assert r["delivery"]["status"] in ("sent", "simulated_no_credentials")

    # Scenario 2: Speaker Onboarding Form + Calendar (.ics) Invitation Dispatch
    invite_resp = client.post("/api/ops/invite", json={})
    assert invite_resp.status_code == 200
    inv_data = invite_resp.json()
    assert inv_data["status"] == "invited"
    assert len(inv_data["invites_sent"]) == 2
    for inv in inv_data["invites_sent"]:
        assert inv["calendar_ics_attached"] is True
        assert inv["delivery"]["status"] in ("sent", "simulated_no_credentials")

    # Scenario 3: Sponsor Sponsorship Proposal Email Dispatch (Tier 2 $3,000 & Tier 3 $5,000)
    sponsor_outreach_resp = client.post(
        "/api/ops/sponsor-outreach",
        json={
            "custom_context": "DevFest 2026 공식 스폰서십 후원 패키지 제안 (홍보 부스, 키노트 세션, 웰컴 키트 브랜딩)",
        },
    )
    assert sponsor_outreach_resp.status_code == 200
    spon_data = sponsor_outreach_resp.json()
    assert spon_data["status"] == "completed"
    assert spon_data["total_sent"] == 2
    sent_sponsor_emails = [r["sponsor_email"] for r in spon_data["sponsor_outreach_results"]]
    assert "sniper45han@gmail.com" in sent_sponsor_emails
    assert "aristojeff@gmail.com" in sent_sponsor_emails
    for r in spon_data["sponsor_outreach_results"]:
        assert r["email_type"] == "sponsor_outreach"
        assert "[DevFest 2026]" in r["subject"]
        assert r["delivery"]["status"] in ("sent", "simulated_no_credentials")
