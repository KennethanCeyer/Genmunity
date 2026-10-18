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

    dash = client.get("/")
    assert dash.status_code == 200
    assert "Genmunity" in dash.text
    assert "sniper45han@gmail.com" in dash.text
    assert "aristojeff@gmail.com" in dash.text
