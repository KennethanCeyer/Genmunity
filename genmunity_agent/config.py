import os
import json
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Ensure GOOGLE_API_KEY and GEMINI_API_KEY are synchronized for google-adk and google-genai
if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
elif os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

GEMINI_PRIMARY_MODEL = os.environ.get("GENMUNITY_MODEL", "gemini-4-argon")
GEMINI_SECONDARY_MODEL = os.environ.get("GENMUNITY_SECONDARY_MODEL", "gemini-3.8-flash")
GEMINI_MODEL = GEMINI_PRIMARY_MODEL
GEMINI_MODEL_CANDIDATES: List[str] = [GEMINI_PRIMARY_MODEL]
if GEMINI_SECONDARY_MODEL and GEMINI_SECONDARY_MODEL not in GEMINI_MODEL_CANDIDATES:
    GEMINI_MODEL_CANDIDATES.append(GEMINI_SECONDARY_MODEL)

GENMUNITY_BASE_URL = os.environ.get("GENMUNITY_BASE_URL", "http://localhost:8080")

# GDG Domestic Organizers & GDE Shared Google Sheet
GDG_KOREA_SHEET_ID = "1tC31_8IuWH-2TIeX0t84nyRI0YyaBSI52n97acG32-c"
GDG_KOREA_SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/{GDG_KOREA_SHEET_ID}/edit?usp=sharing"
)

# Hardcoded Speaker Roster (from SearchAgent -> OpsAgent handoff)
HARDCODED_SPEAKERS: List[Dict[str, Any]] = [
    {
        "speaker_order": 1,
        "order_label": "첫번째 연사자 (1st Speaker)",
        "name": "한성민",
        "name_en": "Sungmin Han",
        "email": "sniper45han@gmail.com",
        "role": "AI GDE",
        "badge": "Google Developer Expert in AI / ML",
        "track": "AI / Agentic Workflow Hands-on",
        "proposed_topic": "Google ADK와 Gemini 4.0 Argon을 활용한 멀티 에이전트 커뮤니티 자동화 핸즈온",
        "session_time": "13:30 - 15:00 (90분 핸즈온)",
        "source": "Advocu & GDG Korea GDE Directory",
        "bio": "Google AI/ML GDE. 생성형 AI, 멀티 에이전트 아키텍처(ADK, A2A), Vertex AI 실전 워크숍 전문 연사.",
    },
    {
        "speaker_order": 2,
        "order_label": "두번째 연사자 (2nd Speaker)",
        "name": "박제창",
        "name_en": "Jechang Park",
        "email": "aristojeff@gmail.com",
        "role": "Flutter GDE",
        "badge": "Google Developer Expert in Flutter & Dart",
        "track": "Flutter & On-Device AI Hands-on",
        "proposed_topic": "Flutter와 Firebase Genkit / Gemini API로 구현하는 크로스플랫폼 AI 앱 핸즈온",
        "session_time": "15:20 - 16:50 (90분 핸즈온)",
        "source": "Advocu & GDG Korea GDE Directory",
        "bio": "Google Flutter/Dart GDE. 멀티플랫폼 모바일/웹 애플리케이션 설계 및 Flutter 커뮤니티 핵심 기여자.",
    },
]

# Event Metadata & Community Knowledge Base for SearchAgent RAG
DEVFEST_EVENT_INFO: Dict[str, Any] = {
    "event_name": "DevFest 2026 Hands-on & Agentic Builderthon",
    "event_tag": "[DevFest 2026]",
    "event_date": "2026-11-21",
    "event_start_iso": "2026-11-21T13:00:00+09:00",
    "event_end_iso": "2026-11-21T18:00:00+09:00",
    "venue": "구글 스타트업 캠퍼스 서울 (Google for Startups Campus Seoul, 대치동 오토웨이타워)",
    "organizer": "GDG Korea CommunityHub & Ops Automation Team",
    "season_deadline": "올해 DevFest 공식 시즌은 2026년 9월 1일부터 12월 31일까지 진행되며, 챕터별 결과 보고서(Advocu) 및 정산 마감은 행사 종료 후 14일 이내(최종 2026년 12월 31일 23:59 KST)입니다.",
    "budget_policy": {
        "summary": "DevFest 2026 챕터 지원 가능 예산은 참석자 규모 및 핸즈온 트랙 여부에 따라 최소 $1,500 ~ 최대 $5,000 (한화 약 200만 원 ~ 680만 원)까지 신청 가능합니다.",
        "tiers": [
            {
                "tier": "Tier 1 (소규모 핸즈온 / 50~100명)",
                "amount": "$1,500 (약 200만 원)",
                "covered_items": "다과/케이터링, 연사 기념품, 기본 현수막 및 네임택",
            },
            {
                "tier": "Tier 2 (중규모 멀티트랙 핸즈온 / 100~250명)",
                "amount": "$3,000 (약 400만 원)",
                "covered_items": "케이터링, 연사 웰컴 키트/티셔츠, 주차 지원, Google Cloud 크레딧($25/인), 촬영비",
            },
            {
                "tier": "Tier 3 (대규모 연합 DevFest / 250명 이상)",
                "amount": "$5,000 (약 680만 원)",
                "covered_items": "대관료 보조, 케이터링, 연사 여비/숙박(타 지역 GDE 초청 시 별도 GDE Travel Fund 연계 가능), 굿즈 제작",
            },
        ],
        "gde_support": "GDE 연사(한성민 AI GDE, 박제창 Flutter GDE 등) 초청 시 Advocu GDE 프로그램에서 교통비/숙박비 별도 지원 트랙 신청 가능.",
        "application_deadline": "행사 개최 최소 6주 전까지 GDG Chapter 예산 신청 폼 제출 필수.",
    },
    "onboarding_form_fields": [
        {
            "key": "speaker_name",
            "label": "발표자 성함",
            "type": "text",
            "required": True,
            "placeholder": "예: 한성민 / 박제창",
        },
        {
            "key": "email",
            "label": "이메일",
            "type": "email",
            "required": True,
            "placeholder": "예: sniper45han@gmail.com",
        },
        {
            "key": "phone",
            "label": "연락처",
            "type": "tel",
            "required": True,
            "placeholder": "예: 010-1234-5678",
        },
        {
            "key": "tshirt_size",
            "label": "티셔츠 사이즈",
            "type": "select",
            "required": True,
            "options": ["S (90)", "M (95)", "L (100)", "XL (105)", "2XL (110)", "3XL (115)"],
        },
        {
            "key": "vehicle_number",
            "label": "차량 번호 (무료 주차 등록용, 없으면 '없음' 기재)",
            "type": "text",
            "required": True,
            "placeholder": "예: 123가 4568 또는 없음",
        },
        {
            "key": "session_title",
            "label": "핸즈온 세션 제목 및 필요 환경",
            "type": "textarea",
            "required": False,
            "placeholder": "발표 제목 및 참가자 사전 준비 사항(노트북, Cloud 크레딧 등)을 적어주세요.",
        },
    ],
}

RUNTIME_STATE_PATH = BASE_DIR / "data" / "runtime_state.json"


def load_runtime_state() -> Dict[str, Any]:
    """Load persisted operational state (sent emails, clusters, generated forms, invites)."""
    if RUNTIME_STATE_PATH.exists():
        try:
            with open(RUNTIME_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "speakers": HARDCODED_SPEAKERS,
        "outreach_history": [],
        "clustered_emails": None,
        "forms": {},
        "form_submissions": [],
        "calendar_invites": [],
        "agent_trace": [],
    }


def save_runtime_state(state: Dict[str, Any]) -> None:
    """Persist operational state to disk."""
    RUNTIME_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNTIME_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def record_agent_trace(agent_name: str, capability: str, summary: str, details: Any = None) -> None:
    """Append an execution trace entry for live visualization in the Web UI."""
    state = load_runtime_state()
    trace = state.setdefault("agent_trace", [])
    import datetime

    trace.append(
        {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "agent": agent_name,
            "capability": capability,
            "summary": summary,
            "details": details,
        }
    )
    # Keep latest 50 trace events
    state["agent_trace"] = trace[-50:]
    save_runtime_state(state)
