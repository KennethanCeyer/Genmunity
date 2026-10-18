import os
import re
import uuid
import json
import base64
import subprocess
import logging
import datetime
from email.utils import parseaddr
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from google.genai import types
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from genmunity_agent.config import (
    BASE_DIR,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
    EVENT_MANAGER_ACCOUNT,
    EVENT_ORGANIZER_DELEGATES,
    EVENT_ORGANIZER_DELEGATE_EMAILS,
    load_runtime_state,
    save_runtime_state,
    record_agent_trace,
)
from genmunity_agent.services.google_workspace import get_workspace_service
from genmunity_agent.services.event_hub import search_all_event_knowledge

logger = logging.getLogger("genmunity.mail_trigger")

DEFAULT_ADMIN_EMAIL = EVENT_MANAGER_ACCOUNT["email"]
DEFAULT_GCP_PROJECT = EVENT_MANAGER_ACCOUNT["assigned_project"]
DEFAULT_PUBSUB_TOPIC = EVENT_MANAGER_ACCOUNT["pubsub_topic"]
DEFAULT_PUBSUB_SUBSCRIPTION = EVENT_MANAGER_ACCOUNT["pubsub_subscription"]

ADMIN_REGISTRY_PATH: Path = BASE_DIR / "data" / "mail_admin_registry.json"
CREDENTIALS_FILE_CANDIDATES = [
    BASE_DIR / "credentials.json",
    Path(os.path.expanduser("~/automation/credentials.json")),
]
TOKEN_PATH: Path = BASE_DIR / "token.json"

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.file",
]


def load_admin_registry() -> Dict[str, Any]:
    """Load persisted mail admin OAuth registration & trigger state."""
    reg: Dict[str, Any] = {
        "target_admin_email": DEFAULT_ADMIN_EMAIL,
        "event_manager": {
            "username": EVENT_MANAGER_ACCOUNT["username"],
            "first_name": EVENT_MANAGER_ACCOUNT["first_name"],
            "last_name": EVENT_MANAGER_ACCOUNT["last_name"],
            "full_name": EVENT_MANAGER_ACCOUNT["full_name"],
            "assigned_project": DEFAULT_GCP_PROJECT,
        },
        "organizer_delegates": EVENT_ORGANIZER_DELEGATES,
        "authenticated_email": None,
        "is_target_admin_active": False,
        "registered_at": None,
        "initial_history_id": None,
        "last_history_id": None,
        "pubsub_topic": DEFAULT_PUBSUB_TOPIC,
        "pubsub_subscription": DEFAULT_PUBSUB_SUBSCRIPTION,
        "pubsub_watch": None,
        "secret_manager_synced": False,
        "auto_trigger_enabled": True,
        "auto_send_form_on_reply": True,
        "auto_inquiry_reply_enabled": True,
        "poll_interval_seconds": 6,
        "baseline_message_ids": [],
        "processed_inbound_message_ids": [],
        "trigger_events": [],
        "inquiry_events": [],
    }
    if ADMIN_REGISTRY_PATH.exists():
        try:
            with open(ADMIN_REGISTRY_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                reg.update(loaded)
        except Exception as exc:
            logger.warning(f"Failed to read mail_admin_registry.json: {exc}")

    # Always keep assigned project and Pub/Sub topic aligned with kr-devsummit26icn-501
    reg["target_admin_email"] = DEFAULT_ADMIN_EMAIL
    reg["event_manager"] = {
        "username": EVENT_MANAGER_ACCOUNT["username"],
        "first_name": EVENT_MANAGER_ACCOUNT["first_name"],
        "last_name": EVENT_MANAGER_ACCOUNT["last_name"],
        "full_name": EVENT_MANAGER_ACCOUNT["full_name"],
        "assigned_project": DEFAULT_GCP_PROJECT,
    }
    reg["organizer_delegates"] = EVENT_ORGANIZER_DELEGATES
    reg["pubsub_topic"] = DEFAULT_PUBSUB_TOPIC
    reg["pubsub_subscription"] = DEFAULT_PUBSUB_SUBSCRIPTION
    reg.setdefault("auto_inquiry_reply_enabled", True)
    reg.setdefault("inquiry_events", [])
    return reg


def save_admin_registry(reg: Dict[str, Any]) -> None:
    """Persist mail admin registration & trigger state to disk."""
    ADMIN_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ADMIN_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def find_credentials_file() -> Optional[Path]:
    for candidate in CREDENTIALS_FILE_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_oauth_client_config() -> Dict[str, Any]:
    """Load OAuth 2.0 client configuration from environment variables or credentials.json."""
    client_id = os.environ.get(
        "GOOGLE_OAUTH_CLIENT_ID",
        "858263435030-sd5l2pvi8edkngnm8ndb7nvqpbak0rkj.apps.googleusercontent.com",
    )
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

    creds_file = find_credentials_file()
    if creds_file:
        try:
            with open(creds_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "installed" in data or "web" in data:
                return data
        except Exception as exc:
            logger.warning(f"Failed to parse {creds_file}: {exc}")

    if not client_secret:
        raise FileNotFoundError(
            "OAuth client credentials not found in credentials.json or GOOGLE_OAUTH_CLIENT_SECRET."
        )

    return {
        "installed": {
            "client_id": client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [
                "http://localhost",
                "http://localhost:8080",
                "http://localhost:8085/",
            ],
        }
    }


def sync_live_gmail_profile() -> Dict[str, Any]:
    """Check the currently active token.json and synchronize admin registry metadata."""
    reg = load_admin_registry()
    ws = get_workspace_service()
    gmail = ws.get_gmail_service()
    if not gmail:
        return reg

    try:
        profile = gmail.users().getProfile(userId="me").execute()
        email_addr = profile.get("emailAddress")
        history_id = str(profile.get("historyId", ""))
        reg["authenticated_email"] = email_addr
        reg["is_target_admin_active"] = (
            email_addr is not None
            and email_addr.lower() == reg.get("target_admin_email", DEFAULT_ADMIN_EMAIL).lower()
        )
        if not reg.get("initial_history_id"):
            reg["initial_history_id"] = history_id
        if not reg.get("last_history_id"):
            reg["last_history_id"] = history_id
        save_admin_registry(reg)
    except Exception as exc:
        logger.warning(f"Could not query live Gmail profile: {exc}")

    return reg


def register_mail_admin_via_oauth(
    target_email: str = DEFAULT_ADMIN_EMAIL,
    register_pubsub_watch: bool = True,
    sync_secret_manager: bool = True,
    open_browser: bool = True,
    port: int = 0,
) -> Dict[str, Any]:
    """
    Launch OAuth 2.0 InstalledAppFlow for the Mail Administrator account (default: devstar5011@gcplab.me),
    save token.json, snapshot existing inbox message IDs so only NEW replies trigger actions,
    register Gmail API users.watch (Cloud Pub/Sub), and optionally update GCP Secret Manager.
    """
    client_config = load_oauth_client_config()
    flow = InstalledAppFlow.from_client_config(client_config, DEFAULT_SCOPES)
    creds = flow.run_local_server(
        port=port,
        open_browser=open_browser,
        login_hint=target_email,
        prompt="select_account consent",
    )

    token_json_str = creds.to_json()
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(token_json_str)

    # Also keep ~/automation/token.json in sync if directory exists
    auto_token = Path(os.path.expanduser("~/automation/token.json"))
    if auto_token.parent.exists():
        try:
            with open(auto_token, "w", encoding="utf-8") as f:
                f.write(token_json_str)
        except Exception:
            pass

    gmail = build("gmail", "v1", credentials=creds)
    profile = gmail.users().getProfile(userId="me").execute()
    authenticated_email = profile.get("emailAddress", "")
    history_id = str(profile.get("historyId", ""))

    # Snapshot current INBOX speaker messages as baseline so we only trigger on newly arriving emails
    baseline_ids: List[str] = []
    try:
        q = (
            "label:INBOX ("
            + " OR ".join(f"from:{sp['email']}" for sp in HARDCODED_SPEAKERS)
            + ' OR subject:"DevFest" OR subject:"연사")'
        )
        existing_res = gmail.users().messages().list(userId="me", q=q, maxResults=30).execute()
        baseline_ids = [m["id"] for m in existing_res.get("messages", [])]
    except Exception as exc:
        logger.warning(f"Failed to snapshot baseline inbox messages: {exc}")

    # Register Gmail API users.watch for Cloud Pub/Sub real-time push
    watch_info: Dict[str, Any] = {"status": "skipped"}
    if register_pubsub_watch:
        try:
            watch_res = (
                gmail.users()
                .watch(
                    userId="me",
                    body={
                        "topicName": DEFAULT_PUBSUB_TOPIC,
                        "labelIds": ["INBOX"],
                    },
                )
                .execute()
            )
            watch_info = {
                "status": "active",
                "historyId": watch_res.get("historyId"),
                "expiration": watch_res.get("expiration"),
                "topicName": DEFAULT_PUBSUB_TOPIC,
            }
        except Exception as exc:
            watch_info = {
                "status": "local_polling_fallback",
                "reason": str(exc),
                "topicName": DEFAULT_PUBSUB_TOPIC,
            }

    # Optionally update GCP Secret Manager [gmail-credentials]
    secret_synced = False
    if sync_secret_manager:
        try:
            compact = json.dumps(json.loads(token_json_str))
            proc = subprocess.run(
                [
                    "gcloud",
                    "secrets",
                    "versions",
                    "add",
                    "gmail-credentials",
                    f"--project={DEFAULT_GCP_PROJECT}",
                    "--data-file=-",
                ],
                input=compact.encode("utf-8"),
                capture_output=True,
                timeout=15,
            )
            secret_synced = proc.returncode == 0
        except Exception as exc:
            logger.warning(f"Secret Manager update skipped: {exc}")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reg = load_admin_registry()
    reg.update(
        {
            "target_admin_email": target_email,
            "authenticated_email": authenticated_email,
            "is_target_admin_active": authenticated_email.lower() == target_email.lower(),
            "registered_at": now_iso,
            "initial_history_id": history_id,
            "last_history_id": history_id,
            "pubsub_topic": DEFAULT_PUBSUB_TOPIC,
            "pubsub_watch": watch_info,
            "secret_manager_synced": secret_synced,
            "auto_trigger_enabled": True,
            "baseline_message_ids": baseline_ids,
        }
    )
    save_admin_registry(reg)

    record_agent_trace(
        agent_name="OpsAgent",
        capability="MailAdminOAuthRegistration",
        summary=(
            f"메일 관리자 OAuth 로그인 및 수신 트리거 등록 완료: {authenticated_email} "
            f"(historyId={history_id}, watch={watch_info.get('status')})"
        ),
        details={
            "authenticated_email": authenticated_email,
            "target_admin_email": target_email,
            "pubsub_watch": watch_info,
            "secret_manager_synced": secret_synced,
        },
    )
    return reg


def extract_gmail_message_body(payload: Dict[str, Any]) -> str:
    """Recursively extract plain-text or HTML body content from a Gmail API message payload."""
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")
    body_data = (payload.get("body") or {}).get("data")
    if body_data and mime_type in ("text/plain", "text/html"):
        try:
            decoded = base64.urlsafe_b64decode(body_data.encode("utf-8")).decode("utf-8", errors="replace")
            if mime_type == "text/html":
                decoded = re.sub(r"<[^>]+>", " ", decoded)
            return decoded.strip()
        except Exception:
            pass

    parts = payload.get("parts") or []
    plain_candidates: List[str] = []
    html_candidates: List[str] = []
    for part in parts:
        p_mime = part.get("mimeType", "")
        text = extract_gmail_message_body(part)
        if text:
            if "text/plain" in p_mime:
                plain_candidates.append(text)
            else:
                html_candidates.append(text)

    if plain_candidates:
        return "\n".join(plain_candidates).strip()
    if html_candidates:
        return "\n".join(html_candidates).strip()
    return ""


def parse_sender_header(from_header: str) -> Tuple[str, str]:
    """Extract (sender_name, sender_email) from an RFC-5322 From header."""
    name, addr = parseaddr(from_header or "")
    if not addr and "@" in (from_header or ""):
        addr = from_header.strip()
    if not name:
        name = addr.split("@")[0] if "@" in addr else "문의자"
    return name.strip(), addr.strip()


# Keywords indicating an inquiry is outside the standard Event Knowledge Base and requires Organizer Delegation
_OUT_OF_KB_KEYWORDS = [
    "스폰서",
    "후원",
    "협찬",
    "세금계산서",
    "계약",
    "법률",
    "nda",
    "비밀유지",
    "환불",
    "결제 오류",
    "소송",
    "언론",
    "취재",
    "인터뷰",
    "방송",
    "vip",
    "만찬",
    "단독 부스",
    "부스 설치",
    "대관 시간 연장",
    "야간 개방",
    "특례",
    "예외 승인",
    "개인정보 파기",
    "비공개",
    "단독 미팅",
    "고액",
    "custom contract",
    "sponsorship",
    "refund",
    "legal",
]

# Keywords covered by the Event Knowledge Base (Schedule, Venue, Parking, Speakers, Budget, Credits, RSVP, T-Shirt)
_IN_KB_KEYWORDS = [
    "일정",
    "언제",
    "날짜",
    "시간",
    "장소",
    "어디",
    "오토웨이타워",
    "스타트업 캠퍼스",
    "주차",
    "차량",
    "티셔츠",
    "사이즈",
    "웰컴",
    "연사",
    "스피커",
    "한성민",
    "박제창",
    "발표",
    "주제",
    "트랙",
    "핸즈온",
    "예산",
    "지원금",
    "마감",
    "12월 31일",
    "크레딧",
    "노트북",
    "준비물",
    "rsvp",
    "참가",
    "신청",
    "정원",
    "참석자",
    "사진",
    "gde",
    "여비",
    "숙박",
    "교통비",
]


def _build_knowledge_base_context_text(event_id: str = "devfest-2026-seoul") -> Tuple[str, List[Dict[str, Any]]]:
    """Compile all Event Knowledge Base entries and official DevFest metadata into a single RAG context string."""
    kb_search = search_all_event_knowledge("")
    all_kb_items = kb_search.get("knowledge_base_matches", [])
    events_overview = kb_search.get("events_overview", [])

    lines = [
        f"[공식 행사 기본 정보 — {DEVFEST_EVENT_INFO['event_name']}]",
        f"- 담당자(Event Manager): {EVENT_MANAGER_ACCOUNT['full_name']} ({EVENT_MANAGER_ACCOUNT['email']}) / 프로젝트: {DEFAULT_GCP_PROJECT}",
        f"- 행사 일시: {DEVFEST_EVENT_INFO['event_date']} (13:00 - 18:00 KST)",
        f"- 행사 장소: {DEVFEST_EVENT_INFO['venue']}",
        f"- 시즌 및 결과 보고 마감: {DEVFEST_EVENT_INFO['season_deadline']}",
        f"- 예산 지원 정책: {DEVFEST_EVENT_INFO['budget_policy']['summary']}",
        f"- GDE 초청 여비 지원: {DEVFEST_EVENT_INFO['budget_policy']['gde_support']}",
        "- 확정 핸즈온 연사자:",
    ]
    for sp in HARDCODED_SPEAKERS:
        lines.append(
            f"  * {sp['order_label']}: {sp['name']} ({sp['role']}, {sp['email']}) | 트랙: {sp['track']} | 주제: {sp['proposed_topic']} | 시간: {sp['session_time']}"
        )
    lines.append("\n[등록된 이벤트 현황]")
    for ev in events_overview:
        lines.append(
            f"- [{ev['event_id']}] {ev['title']} | 일시: {ev['date']} | 장소: {ev['venue']} | 상태: {ev['status']} | RSVP: {ev['rsvp_count']}/{ev['capacity']}명 | 사진 감지 참석자: {ev['tracked_photo_attendees']}명 | 예산: {ev['budget']}"
        )
    lines.append("\n[행사 이벤트 지식 베이스 문서 (Event Knowledge Base)]")
    for idx, item in enumerate(all_kb_items, start=1):
        lines.append(
            f"{idx}. [{item.get('event_title', 'Event')} / {item.get('category', 'KB')}] {item.get('title', '')}: {item.get('content', '')}"
        )

    return "\n".join(lines), all_kb_items


def evaluate_and_handle_inbound_inquiry(
    sender_email: str,
    subject: str,
    inquiry_body: str,
    sender_name: str = "",
    message_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    event_id: str = "devfest-2026-seoul",
    trigger_source: str = "pubsub_cloudrun_webhook",
) -> Dict[str, Any]:
    """
    [Pub/Sub -> Cloud Run Inbound Inquiry Automation]
    When an inquiry email arrives at the Event Manager account (`devstar5011@gcplab.me`,
    `Star Developer 5011`, Assigned Project: `kr-devsummit26icn-501`):

    1. Searches the Event Knowledge Base (`search_all_event_knowledge` + `DEVFEST_EVENT_INFO`).
    2. Evaluates with Gemini (`gemini-4-argon` primary -> `gemini-3.8-flash` fallback) + deterministic rules
       whether the inquiry can be answered within the Event Knowledge Base.
    3. If answerable from the Event Knowledge Base (`is_within_knowledge_base == True`):
       - Automatically replies to `sender_email` via Gmail with an accurate answer grounded in the Knowledge Base.
    4. If the inquiry exceeds the Event Knowledge Base (`is_within_knowledge_base == False`):
       - Automatically delegates (forwards/escalates via email) the inquiry to the Event Organizers:
         `sniper45han@gmail.com` (한성민) and `aristojeff@gmail.com` (박제창),
         and sends an escalation notice to the inquirer.
    """
    parsed_name, parsed_addr = parse_sender_header(sender_email)
    clean_sender_email = parsed_addr or sender_email.strip()
    clean_sender_name = (sender_name or parsed_name or "문의자").strip()

    kb_context_text, kb_items = _build_knowledge_base_context_text(event_id=event_id)
    combined_inquiry = f"{subject}\n{inquiry_body}".strip()
    combined_lower = combined_inquiry.lower()

    # Deterministic pre-check for explicit out-of-KB vs in-KB signals
    has_out_of_kb_signal = any(kw in combined_lower for kw in _OUT_OF_KB_KEYWORDS)
    has_in_kb_signal = any(kw in combined_lower for kw in _IN_KB_KEYWORDS)

    matched_kb_titles: List[str] = []
    for item in kb_items:
        title_str = item.get("title", "")
        content_str = item.get("content", "")
        if any(tok in f"{title_str} {content_str}".lower() for tok in combined_lower.split() if len(tok) >= 2):
            matched_kb_titles.append(title_str)
    if not matched_kb_titles and kb_items:
        matched_kb_titles = [kb_items[0].get("title", "DevFest 2026 기본 운영 가이드")]

    # Default deterministic evaluation (used if Gemini is unavailable or as baseline)
    is_within_kb = bool(has_in_kb_signal and not has_out_of_kb_signal)
    confidence = 0.92 if is_within_kb else 0.89
    category = "Event Knowledge Base FAQ" if is_within_kb else "Out-of-KB / Organizer Escalation"
    if is_within_kb:
        reason = "문의하신 내용(일정, 장소, 주차, 연사 라인업, 예산/시즌 정책 등)이 행사 이벤트 지식 베이스에 명시되어 있어 자동 회신을 생성했습니다."
    else:
        reason = "문의하신 내용은 표준 행사 이벤트 지식 베이스(일정/장소/연사/예산/기본 안내) 범위를 넘어서는 운영/특례/계약 사안이므로 행사 운영자(sniper45han@gmail.com, aristojeff@gmail.com)에게 딜리게이션합니다."

    default_kb_reply_body = (
        f"안녕하세요 {clean_sender_name}님,\n\n"
        f"GDG DevFest 2026 행사 담당자 {EVENT_MANAGER_ACCOUNT['full_name']} ({EVENT_MANAGER_ACCOUNT['email']}, Project: {DEFAULT_GCP_PROJECT}) 입니다.\n"
        f"보내주신 문의('{subject}')에 대해 행사 이벤트 지식 베이스(Event Knowledge Base)를 바탕으로 아래와 같이 안내드립니다.\n\n"
        f"■ 행사 기본 안내\n"
        f"- 행사명: {DEVFEST_EVENT_INFO['event_name']}\n"
        f"- 일시: {DEVFEST_EVENT_INFO['event_date']} (13:00 - 18:00 KST)\n"
        f"- 장소: {DEVFEST_EVENT_INFO['venue']}\n"
        f"- 주차 및 사전 등록: 오토웨이타워 무료 주차 지원(사전 등록 폼에 차량 번호 및 티셔츠 사이즈 S~3XL 입력)\n\n"
        f"■ 핸즈온 연사자 라인업\n"
        f"1. 한성민 님 (AI GDE, sniper45han@gmail.com) — Google ADK와 Gemini 4.0 Argon 멀티 에이전트 핸즈온 (13:30 - 15:00)\n"
        f"2. 박제창 님 (Flutter GDE, aristojeff@gmail.com) — Flutter & Gemini API 크로스플랫폼 AI 앱 핸즈온 (15:20 - 16:50)\n\n"
        f"■ 시즌 마감 및 예산 정책\n"
        f"- 시즌 기한: {DEVFEST_EVENT_INFO['season_deadline']}\n"
        f"- 예산 정책: {DEVFEST_EVENT_INFO['budget_policy']['summary']}\n\n"
        f"추가 문의 사항이 있으시면 언제든 회신해 주세요.\n"
        f"감사합니다.\n"
        f"{EVENT_MANAGER_ACCOUNT['full_name']} ({EVENT_MANAGER_ACCOUNT['email']}) 드림"
    )
    reply_body = default_kb_reply_body
    delegation_summary = (
        f"발신자({clean_sender_name} <{clean_sender_email}>)의 문의('{subject}')가 행사 지식 베이스 범위를 초과하여 "
        f"행사 운영자 한성민(sniper45han@gmail.com), 박제창(aristojeff@gmail.com) 님께 검토 및 직접 회신을 요청합니다."
    )

    ws = get_workspace_service()
    prompt = f"""당신은 GDG DevFest 2026 행사 담당자 AI 에이전트({EVENT_MANAGER_ACCOUNT['full_name']}, 이메일: {EVENT_MANAGER_ACCOUNT['email']}, GCP 프로젝트: {DEFAULT_GCP_PROJECT})입니다.
수신된 이메일 문의가 아래 [행사 이벤트 지식 베이스] 내의 정보만으로 정확하고 완결성 있게 답변 가능한지 판단하세요.

[판단 기준]
1. `is_within_knowledge_base`: true
   - 행사 일시/날짜/시간, 장소(구글 스타트업 캠퍼스 서울/오토웨이타워), 무료 주차 등록/차량번호, 티셔츠 사이즈(S~3XL), 핸즈온 연사자(한성민 AI GDE, 박제창 Flutter GDE) 및 발표 주제, DevFest 시즌 일정(12월 31일 마감), 챕터 지원 예산($1,500~$5,000) 및 GDE 여비 지원, 참가자 RSVP/노트북 준비물/$25 크레딧, 현장 사진 참석자 수 통계 등 지식 베이스에 있는 내용으로 답변 가능한 경우.
2. `is_within_knowledge_base`: false
   - 지식 베이스에 없는 내용이나 운영진의 별도 의사결정/승인이 필요한 경우 (예: 기업 스폰서십 계약/세금계산서/후원 협상, VIP 비공개 만찬, 언론/방송 단독 취재 허가, 법률/보안 NDA 체결, 환불/결제 분쟁, 대관 시간 야간 연장 특례, 지식 베이스에 전혀 없는 질문 등).
   - 이 경우 행사 운영자인 `sniper45han@gmail.com` (한성민)과 `aristojeff@gmail.com` (박제창)에게 이메일 딜리게이션(이관)을 수행합니다.

[행사 이벤트 지식 베이스]
{kb_context_text}

[수신된 문의 이메일]
- 발신자: {clean_sender_name} <{clean_sender_email}>
- 제목: {subject}
- 본문:
{inquiry_body}

반드시 아래 JSON 스키마로만 응답하세요:
{{
  "is_within_knowledge_base": true,
  "confidence": 0.95,
  "category": "Schedule / Venue / Speakers / Budget / Out-of-Scope",
  "matched_kb_titles": ["매칭된 지식 베이스 문서 제목"],
  "reason": "지식 베이스 내 답변 가능 여부 판단 근거 (한국어)",
  "reply_body": "is_within_knowledge_base가 true일 때 문의자에게 보낼 정중하고 구체적인 한국어 자동 회신 본문 (담당자 Star Developer 5011 devstar5011@gcplab.me 서명 포함)",
  "delegation_summary": "is_within_knowledge_base가 false일 때 행사 운영자(sniper45han@gmail.com, aristojeff@gmail.com)에게 전달할 문의 핵심 요약 및 요청 사항 (한국어)"
}}"""

    try:
        resp = ws.generate_content_with_fallback(
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        parsed = json.loads(resp.text)
        if isinstance(parsed, dict):
            ai_within = bool(parsed.get("is_within_knowledge_base", is_within_kb))
            # Respect explicit out-of-KB guardrail if present
            if has_out_of_kb_signal:
                is_within_kb = False
            elif has_in_kb_signal:
                is_within_kb = True
            else:
                is_within_kb = ai_within

            confidence = float(parsed.get("confidence") or confidence)
            category = parsed.get("category") or category
            if parsed.get("matched_kb_titles"):
                matched_kb_titles = list(parsed["matched_kb_titles"])
            if parsed.get("reason"):
                reason = str(parsed["reason"])
            if parsed.get("reply_body") and is_within_kb:
                reply_body = str(parsed["reply_body"])
            if parsed.get("delegation_summary"):
                delegation_summary = str(parsed["delegation_summary"])
    except Exception as exc:
        logger.warning(f"Gemini KB inquiry evaluation fallback used: {exc}")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    inquiry_id = f"inq-{uuid.uuid4().hex[:8]}"

    if is_within_kb:
        # Case 1: Auto-Reply using Event Knowledge Base
        reply_subject = (
            subject
            if subject.startswith("Re:")
            else f"Re: {DEVFEST_EVENT_INFO['event_tag']} [자동 회신] {subject}"
        )
        auto_reply_delivery = ws.send_email(
            to_email=clean_sender_email,
            to_name=clean_sender_name,
            subject=reply_subject,
            body_text=reply_body,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            email_type="inquiry_reply",
        )
        inquiry_record = {
            "inquiry_id": inquiry_id,
            "timestamp": now_iso,
            "trigger_source": trigger_source,
            "assigned_project": DEFAULT_GCP_PROJECT,
            "event_manager": EVENT_MANAGER_ACCOUNT["email"],
            "event_manager_name": EVENT_MANAGER_ACCOUNT["full_name"],
            "sender_name": clean_sender_name,
            "sender_email": clean_sender_email,
            "subject": subject,
            "inquiry_body": inquiry_body,
            "is_within_knowledge_base": True,
            "action": "auto_replied_from_kb",
            "confidence": confidence,
            "category": category,
            "matched_kb_titles": matched_kb_titles,
            "reason": reason,
            "auto_reply": {
                "to_email": clean_sender_email,
                "subject": reply_subject,
                "body": reply_body,
                "delivery": auto_reply_delivery,
            },
            "delegation": None,
        }
        trace_capability = "KnowledgeBaseAutoReply"
        trace_summary = (
            f"[{ DEFAULT_ADMIN_EMAIL } / { DEFAULT_GCP_PROJECT }] 지식 베이스 기반 문의 자동 회신 완료: "
            f"수신자 {clean_sender_email} | 제목: '{subject}'"
        )
    else:
        # Case 2: Exceeds Event Knowledge Base -> Delegate via Email to Organizers (sniper45han@gmail.com, aristojeff@gmail.com)
        delegation_subject = (
            f"{DEVFEST_EVENT_INFO['event_tag']} [문의 딜리게이션/이관] 지식 베이스 초과 문의 — {subject}"
        )
        delegation_deliveries: List[Dict[str, Any]] = []
        for org in EVENT_ORGANIZER_DELEGATES:
            org_body = (
                f"안녕하세요 {org['name']} ({org['role']})님,\n\n"
                f"이벤트 행사 담당자 계정({EVENT_MANAGER_ACCOUNT['full_name']} / {EVENT_MANAGER_ACCOUNT['email']}, "
                f"Assigned Project: {DEFAULT_GCP_PROJECT})으로 수신된 문의가 행사 이벤트 지식 베이스(Knowledge Base) 범위를 넘어서서 "
                f"행사 운영자 두 분(sniper45han@gmail.com, aristojeff@gmail.com)께 이메일 딜리게이션(이관)되었습니다.\n\n"
                f"■ 문의자 및 원문 정보\n"
                f"- 발신자: {clean_sender_name} <{clean_sender_email}>\n"
                f"- 원 제목: {subject}\n"
                f"- 수신 경로: Cloud Pub/Sub ({DEFAULT_PUBSUB_TOPIC}) -> Cloud Run ({ trigger_source })\n"
                f"- 지식 베이스 초과 판단 사유: {reason}\n"
                f"- AI 에이전트 요약 및 검토 요청: {delegation_summary}\n\n"
                f"■ 문의 원문\n"
                f"----------------------------------------\n"
                f"{inquiry_body}\n"
                f"----------------------------------------\n\n"
                f"문의자 이메일({clean_sender_email})로 직접 회신 또는 운영진 결정을 부탁드립니다.\n"
                f"감사합니다.\n"
                f"Genmunity OpsAgent ({EVENT_MANAGER_ACCOUNT['full_name']} / {EVENT_MANAGER_ACCOUNT['email']})"
            )
            deliv = ws.send_email(
                to_email=org["email"],
                to_name=org["name"],
                subject=delegation_subject,
                body_text=org_body,
                email_type="organizer_delegation",
            )
            delegation_deliveries.append(
                {
                    "organizer_name": org["name"],
                    "organizer_email": org["email"],
                    "organizer_role": org["role"],
                    "subject": delegation_subject,
                    "delivery": deliv,
                }
            )

        # Also notify the inquirer that their message was delegated to the organizers
        ack_subject = (
            subject
            if subject.startswith("Re:")
            else f"Re: {DEVFEST_EVENT_INFO['event_tag']} [운영진 이관 안내] {subject}"
        )
        ack_body = (
            f"안녕하세요 {clean_sender_name}님,\n\n"
            f"GDG DevFest 2026 행사 담당자 {EVENT_MANAGER_ACCOUNT['full_name']} ({EVENT_MANAGER_ACCOUNT['email']}) 입니다.\n"
            f"문의해 주신 내용('{subject}')은 기본 행사 지식 베이스(FAQ) 범위를 넘어서는 운영진 검토 사항으로 확인되어, "
            f"행사 총괄 운영자인 한성민 님(sniper45han@gmail.com)과 박제창 님(aristojeff@gmail.com)께 이메일 딜리게이션(이관)을 완료했습니다.\n\n"
            f"운영진 확인 후 빠른 시일 내에 안내드리겠습니다.\n"
            f"감사합니다.\n"
            f"{EVENT_MANAGER_ACCOUNT['full_name']} ({EVENT_MANAGER_ACCOUNT['email']}) 드림"
        )
        ack_delivery = ws.send_email(
            to_email=clean_sender_email,
            to_name=clean_sender_name,
            subject=ack_subject,
            body_text=ack_body,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            email_type="inquiry_reply",
        )

        inquiry_record = {
            "inquiry_id": inquiry_id,
            "timestamp": now_iso,
            "trigger_source": trigger_source,
            "assigned_project": DEFAULT_GCP_PROJECT,
            "event_manager": EVENT_MANAGER_ACCOUNT["email"],
            "event_manager_name": EVENT_MANAGER_ACCOUNT["full_name"],
            "sender_name": clean_sender_name,
            "sender_email": clean_sender_email,
            "subject": subject,
            "inquiry_body": inquiry_body,
            "is_within_knowledge_base": False,
            "action": "delegated_to_organizers",
            "confidence": confidence,
            "category": category,
            "matched_kb_titles": matched_kb_titles,
            "reason": reason,
            "delegation_summary": delegation_summary,
            "delegated_organizers": EVENT_ORGANIZER_DELEGATE_EMAILS,
            "delegation": {
                "organizers": delegation_deliveries,
                "inquirer_acknowledgment": ack_delivery,
            },
            "auto_reply": None,
        }
        trace_capability = "OrganizerEmailDelegation"
        trace_summary = (
            f"[{ DEFAULT_ADMIN_EMAIL } / { DEFAULT_GCP_PROJECT }] 지식 베이스 초과 문의 이메일 딜리게이션 완료 -> "
            f"sniper45han@gmail.com, aristojeff@gmail.com (발신자: {clean_sender_email} | 제목: '{subject}')"
        )

    # Persist to mail_admin_registry.json and runtime_state.json
    reg = load_admin_registry()
    reg.setdefault("inquiry_events", []).append(inquiry_record)
    reg["inquiry_events"] = reg["inquiry_events"][-40:]
    save_admin_registry(reg)

    state = load_runtime_state()
    state.setdefault("inquiry_history", []).append(inquiry_record)
    state["inquiry_history"] = state["inquiry_history"][-40:]
    save_runtime_state(state)

    record_agent_trace(
        agent_name="OpsAgent",
        capability=trace_capability,
        summary=trace_summary,
        details=inquiry_record,
    )
    return inquiry_record


def decode_pubsub_push_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decode a Google Cloud Pub/Sub Push webhook request body delivered to Cloud Run (`/gmail-webhook`).
    Supports both standard Gmail `users.watch` Pub/Sub notifications:
      {"message": {"data": base64({"emailAddress": "devstar5011@gcplab.me", "historyId": 12345}), "messageId": "..."}, "subscription": "..."}
    and direct inquiry JSON payloads inside `message.data` or top-level JSON.
    """
    if not isinstance(payload, dict):
        return {"pubsub_message_id": None, "decoded_data": {}}

    msg = payload.get("message")
    decoded_data: Dict[str, Any] = {}
    pubsub_message_id = None
    subscription = payload.get("subscription")

    if isinstance(msg, dict):
        pubsub_message_id = msg.get("messageId") or msg.get("message_id")
        raw_b64 = msg.get("data")
        if raw_b64 and isinstance(raw_b64, str):
            try:
                raw_str = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
                parsed = json.loads(raw_str)
                if isinstance(parsed, dict):
                    decoded_data = parsed
            except Exception:
                pass

    # Merge top-level fields if direct inquiry testing payload was posted
    for k in ("emailAddress", "historyId", "sender_email", "sender_name", "subject", "inquiry_body", "body", "event_id"):
        if k in payload and k not in decoded_data:
            decoded_data[k] = payload[k]

    if decoded_data.get("historyId"):
        reg = load_admin_registry()
        reg["last_history_id"] = str(decoded_data["historyId"])
        save_admin_registry(reg)

    return {
        "pubsub_message_id": pubsub_message_id,
        "subscription": subscription or DEFAULT_PUBSUB_SUBSCRIPTION,
        "topic": DEFAULT_PUBSUB_TOPIC,
        "assigned_project": DEFAULT_GCP_PROJECT,
        "event_manager": DEFAULT_ADMIN_EMAIL,
        "decoded_data": decoded_data,
    }


def check_and_trigger_on_inbound_emails(
    trigger_source: str = "polling_or_webhook",
    force_process_latest: bool = False,
) -> Dict[str, Any]:
    """
    Inspect the registered Mail Admin's INBOX (devstar5011@gcplab.me, Project: kr-devsummit26icn-501)
    for new incoming emails:
    - Evaluates incoming event inquiries against the Event Knowledge Base:
      * If within the Event Knowledge Base -> automatically sends a reply via Gmail (`auto_replied_from_kb`).
      * If beyond the Event Knowledge Base -> automatically delegates via email to the event organizers
        `sniper45han@gmail.com` and `aristojeff@gmail.com` (`delegated_to_organizers`).
    - When a target speaker reply is detected:
      * Automatically runs OpsAgent's Gmail Collection & Gemini Clustering (`collect_and_cluster_emails`).
      * Generates the Speaker Onboarding Form and sends the Form link + Calendar Invite (.ics).
    """
    reg = sync_live_gmail_profile()
    ws = get_workspace_service()
    gmail = ws.get_gmail_service()
    if not gmail:
        return {
            "status": "no_gmail_credentials",
            "assigned_project": DEFAULT_GCP_PROJECT,
            "target_admin_email": DEFAULT_ADMIN_EMAIL,
            "new_triggers": [],
            "inquiry_results": [],
        }

    speaker_emails = [sp["email"].lower() for sp in HARDCODED_SPEAKERS]
    query = (
        "label:INBOX ("
        + " OR ".join(f"from:{email}" for email in speaker_emails)
        + ' OR subject:"DevFest" OR subject:"연사" OR subject:"문의" OR subject:"행사" OR subject:"질문")'
    )

    try:
        res = gmail.users().messages().list(userId="me", q=query, maxResults=15).execute()
        messages = res.get("messages", [])
    except Exception as exc:
        logger.warning(f"Failed to check inbound emails for trigger: {exc}")
        return {"status": "error", "error": str(exc), "new_triggers": [], "inquiry_results": []}

    baseline_set = set(reg.get("baseline_message_ids", []))
    processed_set = set(reg.get("processed_inbound_message_ids", []))

    if not baseline_set and not reg.get("registered_at") and not force_process_latest:
        reg["baseline_message_ids"] = [m["id"] for m in messages]
        save_admin_registry(reg)
        return {
            "status": "baseline_initialized",
            "authenticated_email": reg.get("authenticated_email"),
            "baseline_count": len(messages),
            "new_triggers": [],
            "inquiry_results": [],
        }

    new_triggers: List[Dict[str, Any]] = []
    inquiry_results: List[Dict[str, Any]] = []
    admin_email_lower = (reg.get("authenticated_email") or DEFAULT_ADMIN_EMAIL).lower()

    for idx, m in enumerate(messages):
        msg_id = m["id"]
        if not force_process_latest:
            if msg_id in baseline_set or msg_id in processed_set:
                continue
        else:
            if idx > 0:
                break

        try:
            detail = gmail.users().messages().get(userId="me", id=msg_id, format="full").execute()
            payload = detail.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            sender = headers.get("from", "")
            subject = headers.get("subject", "(제목 없음)")
            date_str = headers.get("date", "")
            message_id_hdr = headers.get("message-id", "")
            thread_id = detail.get("threadId")
            snippet = detail.get("snippet", "")
            full_body = extract_gmail_message_body(payload) or snippet

            # Avoid self-sent loops from automated replies, delegations, or speaker onboarding invites
            if any(
                skip_tag in subject
                for skip_tag in (
                    "연사 초대 및 사전 정보 등록",
                    "[자동 회신]",
                    "[문의 딜리게이션/이관]",
                    "[운영진 이관 안내]",
                )
            ):
                processed_set.add(msg_id)
                continue

            sender_name, sender_addr = parse_sender_header(sender)
            if sender_addr.lower() == admin_email_lower and not force_process_latest:
                processed_set.add(msg_id)
                continue

            matched_speaker = None
            for sp in HARDCODED_SPEAKERS:
                if sp["email"].lower() in sender.lower() or sp["name"] in sender or sp["name"] in subject:
                    matched_speaker = sp
                    break

            # 1. Run Event Knowledge Base Auto-Reply or Organizer Email Delegation
            inquiry_outcome = None
            if reg.get("auto_inquiry_reply_enabled", True):
                inquiry_outcome = evaluate_and_handle_inbound_inquiry(
                    sender_email=sender_addr or sender,
                    sender_name=sender_name,
                    subject=subject,
                    inquiry_body=full_body,
                    message_id=msg_id,
                    thread_id=thread_id,
                    in_reply_to=message_id_hdr,
                    trigger_source=trigger_source,
                )
                inquiry_results.append(inquiry_outcome)

            # 2. Trigger Gemini Email Collection & Clustering
            cluster_result = ws.collect_and_cluster_emails(max_results=20)

            # 3. Create Onboarding Form & send Form + Calendar Invite if speaker reply
            auto_invite_result = None
            if reg.get("auto_send_form_on_reply", True) and matched_speaker:
                form_record = ws.create_speaker_onboarding_form()
                invite_res = ws.send_speaker_form_and_calendar_invite(
                    form_id=form_record["form_id"]
                )
                auto_invite_result = {
                    "form_id": form_record["form_id"],
                    "form_url": form_record["primary_form_url"],
                    "invites_sent": invite_res.get("invites_sent", []),
                }

            actions_executed = ["collect_and_cluster_event_emails (Gmail + GenContent)"]
            if inquiry_outcome:
                if inquiry_outcome["is_within_knowledge_base"]:
                    actions_executed.insert(
                        0,
                        f"auto_replied_from_kb (Event Knowledge Base -> {sender_addr})",
                    )
                else:
                    actions_executed.insert(
                        0,
                        "delegated_to_organizers (Escalated -> sniper45han@gmail.com, aristojeff@gmail.com)",
                    )
            if auto_invite_result:
                actions_executed.extend(
                    [
                        "create_speaker_onboarding_form (성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호)",
                        "send_speaker_form_and_calendar_invite (Form + Calendar .ics + Gmail)",
                    ]
                )

            event_record = {
                "trigger_id": f"trig-{msg_id}",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "trigger_source": trigger_source,
                "assigned_project": DEFAULT_GCP_PROJECT,
                "admin_inbox": reg.get("authenticated_email") or DEFAULT_ADMIN_EMAIL,
                "message_id": msg_id,
                "from": sender,
                "subject": subject,
                "date": date_str,
                "snippet": snippet,
                "matched_speaker": (
                    f"{matched_speaker['name']} ({matched_speaker['role']}, {matched_speaker['email']})"
                    if matched_speaker
                    else sender
                ),
                "inquiry_action": inquiry_outcome["action"] if inquiry_outcome else None,
                "is_within_knowledge_base": (
                    inquiry_outcome["is_within_knowledge_base"] if inquiry_outcome else None
                ),
                "actions_executed": actions_executed,
                "cluster_summary": cluster_result.get("ai_summary"),
                "onboarding_form_url": (
                    auto_invite_result["form_url"] if auto_invite_result else None
                ),
            }
            new_triggers.append(event_record)
            processed_set.add(msg_id)

            reg = load_admin_registry()
            reg.setdefault("trigger_events", []).append(event_record)
            reg["trigger_events"] = reg["trigger_events"][-30:]
            reg["processed_inbound_message_ids"] = list(processed_set)
            save_admin_registry(reg)

            record_agent_trace(
                agent_name="OpsAgent",
                capability="InboundEmailTrigger",
                summary=(
                    f"[{reg.get('authenticated_email') or DEFAULT_ADMIN_EMAIL}] 이메일 수신 트리거 발동! "
                    f"발신자: {sender} | 제목: '{subject}' -> "
                    f"{'지식 베이스 자동 회신' if (inquiry_outcome and inquiry_outcome['is_within_knowledge_base']) else '운영자(sniper45han, aristojeff) 딜리게이션'}"
                ),
                details=event_record,
            )
        except Exception as exc:
            logger.warning(f"Error processing inbound trigger message {msg_id}: {exc}")

    reg = load_admin_registry()
    reg["processed_inbound_message_ids"] = list(processed_set)
    save_admin_registry(reg)

    return {
        "status": "checked",
        "assigned_project": DEFAULT_GCP_PROJECT,
        "target_admin_email": DEFAULT_ADMIN_EMAIL,
        "authenticated_email": reg.get("authenticated_email"),
        "is_target_admin_active": reg.get("is_target_admin_active"),
        "new_triggers_count": len(new_triggers),
        "new_triggers": new_triggers,
        "inquiry_results": inquiry_results,
        "recent_trigger_events": reg.get("trigger_events", [])[-10:],
        "recent_inquiry_events": reg.get("inquiry_events", [])[-10:],
    }

