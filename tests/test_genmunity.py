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
    assert form_res["form_provider"] == "google_forms_api_v1"
    assert form_res["google_form_url"].startswith("https://docs.google.com/forms/d/")
    assert form_res["primary_form_url"].startswith("https://docs.google.com/forms/d/")
    assert "speaker-onboarding" not in form_res["primary_form_url"]
    for sp_link in form_res["speaker_links"]:
        assert sp_link["personalized_form_url"].startswith("https://docs.google.com/forms/d/")
        assert "speaker-onboarding" not in sp_link["personalized_form_url"]

    field_labels = [f["label"] for f in form_res["fields"]]
    assert "발표자 성함" in field_labels
    assert "이메일" in field_labels
    assert "연락처" in field_labels
    assert any("티셔츠 사이즈" in lbl for lbl in field_labels)
    assert any("차량 번호" in lbl for lbl in field_labels)


def test_ics_calendar_generation():
    ws = get_workspace_service()
    ics = ws.build_ics_calendar_invite(
        HARDCODED_SPEAKERS[0], DEVFEST_EVENT_INFO["default_google_form_url"]
    )
    assert "BEGIN:VCALENDAR" in ics
    assert "METHOD:REQUEST" in ics
    assert "sniper45han@gmail.com" in ics
    assert "https://docs.google.com/forms/d/" in ics
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
    assert inv_data["form_provider"] == "google_forms_api_v1"
    assert inv_data["google_form_url"].startswith("https://docs.google.com/forms/d/")
    assert "speaker-onboarding" not in inv_data["primary_form_url"]
    assert len(inv_data["invites_sent"]) == 2
    for inv in inv_data["invites_sent"]:
        assert inv["calendar_ics_attached"] is True
        assert inv["form_url"].startswith("https://docs.google.com/forms/d/")
        assert "speaker-onboarding" not in inv["form_url"]
        assert "speaker-onboarding" not in inv["body"]
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


def test_mcp_catalog_and_server_completeness_and_rsvp_validation():
    import asyncio
    from genmunity_agent.mcp_a2a import (
        MCP_TOOLS_CATALOG,
        build_mcp_server,
        execute_mcp_tool_call,
    )
    from genmunity_agent.sub_agents.search_agent import crawl_community_hub_tool

    expected_tools = {
        "GenmunityRootAgent",
        "rag_search_tool",
        "crawl_community_hub_tool",
        "search_event_knowledge_base_tool",
        "slack_search_tool",
        "summarize_community_data_tool",
        "get_target_speakers_tool",
        "generate_and_send_speaker_emails_tool",
        "generate_and_send_sponsor_emails_tool",
        "collect_and_cluster_event_emails_tool",
        "create_speaker_onboarding_form_tool",
        "fetch_google_form_responses_tool",
        "record_speaker_form_response_tool",
        "invite_speakers_with_form_and_calendar_tool",
        "run_ops_full_workflow_tool",
        "check_email_receive_trigger_tool",
        "handle_inbound_email_inquiry_tool",
        "manage_event_rsvp_tool",
        "create_or_modify_event_tool",
        "generate_event_image_tool",
        "add_event_knowledge_tool",
        "analyze_event_photo_tool",
        "get_event_readiness_summary_tool",
    }

    catalog_names = {t["name"] for t in MCP_TOOLS_CATALOG}
    assert expected_tools.issubset(catalog_names)

    srv = build_mcp_server()
    stdio_tools = set(srv._tool_manager._tools.keys())
    assert expected_tools.issubset(stdio_tools)

    # Verify CommunityHub crawler normalized keys
    hub_res = crawl_community_hub_tool(force_refresh=False)
    assert hub_res.get("hub_url") is not None
    assert hub_res.get("source_url") is not None
    assert isinstance(hub_res.get("cookie_count"), int)
    assert isinstance(hub_res.get("devfest_2026_highlights"), dict)
    assert hub_res["devfest_2026_highlights"].get("theme")

    # Verify newly exposed MCP tools via execute_mcp_tool_call
    readiness = asyncio.run(execute_mcp_tool_call("get_event_readiness_summary_tool", {}))
    assert "readiness_pct" in readiness
    assert len(readiness.get("speaker_cards", [])) == 2

    form_res = asyncio.run(execute_mcp_tool_call("fetch_google_form_responses_tool", {}))
    assert "form_id" in form_res

    sync_res = asyncio.run(
        execute_mcp_tool_call(
            "record_speaker_form_response_tool",
            {
                "speaker_name": "박제창",
                "email": "aristojeff@gmail.com",
                "phone": "010-2222-3333",
                "tshirt_size": "L (100)",
                "vehicle_number": "456나 7890",
                "session_title": "Flutter & Gemini 크로스플랫폼 AI 앱 핸즈온",
            },
        )
    )
    assert sync_res["status"] == "synced"

    # Verify RSVP cancel on non-existent attendee does NOT create a confirmed RSVP
    cancel_missing = asyncio.run(
        execute_mcp_tool_call(
            "manage_event_rsvp_tool",
            {
                "attendee_name": "존재하지않는참가자999",
                "attendee_email": "nonexistent999@gdg.kr",
                "event_id": "devfest-2026-seoul",
                "action": "cancel",
            },
        )
    )
    assert cancel_missing["status"] == "not_found"
    assert cancel_missing["action"] == "not_found"


def test_live_google_forms_prefill_and_response_sync():
    import urllib.request

    ws = get_workspace_service()
    default_form_id = DEVFEST_EVENT_INFO["default_google_form_id"]
    default_form_url = DEVFEST_EVENT_INFO["default_google_form_url"]

    assert default_form_url.startswith("https://docs.google.com/forms/d/e/")
    assert "speaker-onboarding" not in default_form_url

    # 1. Verify live Google Form responder URL returns HTTP 200 without login redirect
    req = urllib.request.urlopen(default_form_url, timeout=15)
    html = req.read().decode("utf-8")
    assert req.status == 200
    assert "발표자 성함" in html
    assert "티셔츠 사이즈" in html
    assert "차량 번호" in html

    # 2. Verify Google Forms API v1 response retrieval on the provisioned Google Form
    fetched = ws.fetch_google_form_responses(default_form_id)
    assert fetched["form_id"] == default_form_id
    assert fetched["total_responses"] >= 1
    assert "sniper45han@gmail.com" in fetched["speaker_onboarding"]
    assert "aristojeff@gmail.com" in fetched["speaker_onboarding"]


def test_streaming_chat_image_gen_and_mcp_batch():
    # 1. Image Generation SSE stream (/api/chat/stream with image_mode=True)
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={
            "prompt": "DevFest 2026 Seoul minimalist banner",
            "image_mode": True,
            "image_style": "Modern Minimal Tech",
        },
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
        assert "tool_start" in body
        assert "image_generated" in body
        assert "text_delta" in body
        assert '"type": "done"' in body

    # 2. Multi-MCP Batch SSE stream (/api/mcp/batch-stream)
    with client.stream(
        "POST",
        "/api/mcp/batch-stream",
        json={
            "tools": [
                {"name": "get_target_speakers_tool", "arguments": {}},
                {"name": "rag_search_tool", "arguments": {"query": "DevFest 예산"}},
            ]
        },
    ) as batch_resp:
        assert batch_resp.status_code == 200
        batch_body = "".join(batch_resp.iter_text())
        assert "get_target_speakers_tool" in batch_body
        assert "rag_search_tool" in batch_body
        assert '"type": "done"' in batch_body



