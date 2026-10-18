import os
import uuid
import json
import base64
import logging
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, formatdate, make_msgid
from urllib.parse import urlencode
from typing import Dict, Any, List, Optional

from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build

from genmunity_agent.config import (
    BASE_DIR,
    GEMINI_MODEL,
    GEMINI_MODEL_CANDIDATES,
    GENMUNITY_BASE_URL,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
    load_runtime_state,
    save_runtime_state,
)

logger = logging.getLogger("genmunity.workspace")


class GoogleWorkspaceService:
    """
    Integrates Google Workspace APIs (Gmail, Forms, Calendar) and Gemini GenContent
    for OpsAgent's speaker automation pipeline.
    """

    def __init__(self) -> None:
        self._genai_client: Optional[genai.Client] = None

    def get_genai_client(self) -> Optional[genai.Client]:
        if self._genai_client is not None:
            return self._genai_client
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            self._genai_client = genai.Client(api_key=api_key)
        return self._genai_client

    def generate_content_with_fallback(
        self, contents: str, config: types.GenerateContentConfig
    ):
        """Try primary model (gemini-4-argon) first, falling back to secondary (gemini-3.8-flash)."""
        client = self.get_genai_client()
        if not client:
            raise RuntimeError("No Gemini API client configured")
        last_exc: Optional[Exception] = None
        for model_name in GEMINI_MODEL_CANDIDATES:
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                logger.warning(f"Gemini model {model_name} failed, trying fallback if available: {exc}")
                last_exc = exc
        if last_exc:
            raise last_exc
        raise RuntimeError("No Gemini model candidates configured")

    def load_oauth_credentials(self) -> Optional[Credentials]:
        """Load Google OAuth credentials from environment, local token.json, or ~/automation/token.json."""
        creds: Optional[Credentials] = None
        creds_json_str = os.environ.get("GMAIL_CREDENTIALS_JSON")
        if creds_json_str:
            try:
                info = json.loads(creds_json_str)
                creds = Credentials.from_authorized_user_info(info)
            except Exception as exc:
                logger.warning(f"Failed to parse GMAIL_CREDENTIALS_JSON: {exc}")

        if creds is None:
            candidate_paths = [
                BASE_DIR / "token.json",
                os.path.expanduser("~/automation/token.json"),
            ]
            for path in candidate_paths:
                p_str = str(path)
                if os.path.exists(p_str):
                    try:
                        with open(p_str, "r", encoding="utf-8") as f:
                            info = json.load(f)
                        creds = Credentials.from_authorized_user_info(info)
                        break
                    except Exception as exc:
                        logger.warning(f"Failed to load token from {p_str}: {exc}")

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
            except Exception as exc:
                logger.warning(f"Token refresh warning: {exc}")

        return creds

    def get_gmail_service(self):
        creds = self.load_oauth_credentials()
        if not creds:
            return None
        return build("gmail", "v1", credentials=creds)

    def get_forms_service(self):
        creds = self.load_oauth_credentials()
        if not creds:
            return None
        return build("forms", "v1", credentials=creds)

    def get_calendar_service(self):
        creds = self.load_oauth_credentials()
        if not creds:
            return None
        return build("calendar", "v3", credentials=creds)

    # -------------------------------------------------------------------------
    # Step 2: GenContent + Gmail Speaker Outreach
    # -------------------------------------------------------------------------
    def generate_speaker_outreach_email(
        self, speaker: Dict[str, Any], custom_context: str = ""
    ) -> Dict[str, str]:
        """Use Gemini (GenContent) to craft a personalized DevFest speaker invitation email."""
        name = speaker["name"]
        role = speaker["role"]
        order_label = speaker["order_label"]
        track = speaker["track"]
        topic = speaker["proposed_topic"]
        session_time = speaker["session_time"]
        event_name = DEVFEST_EVENT_INFO["event_name"]
        event_date = DEVFEST_EVENT_INFO["event_date"]
        venue = DEVFEST_EVENT_INFO["venue"]

        default_subject = (
            f"{DEVFEST_EVENT_INFO['event_tag']} {name} {role}님, 핸즈온 세션({order_label}) 연사 초청의 건"
        )
        default_body = (
            f"안녕하세요 {name} {role}님,\n\n"
            f"GDG Korea CommunityHub & DevFest 2026 운영팀(Genmunity OpsAgent)입니다.\n"
            f"다가오는 {event_date}에 {venue}에서 개최되는 '{event_name}' 행사의 "
            f"[{order_label} - {track}] 트랙 연사로 {name}님을 정중히 모시고자 연락드렸습니다.\n\n"
            f"■ 행사 및 세션 안내\n"
            f"- 행사명: {event_name}\n"
            f"- 일시: {event_date} ({session_time})\n"
            f"- 장소: {venue}\n"
            f"- 초청 구분: {order_label} ({role})\n"
            f"- 제안 세션 주제: {topic}\n\n"
            f"참석 및 발표 가능 여부를 본 메일의 답장으로 회신해 주시면, "
            f"발표자 사전 정보 입력 폼(성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호 등)과 "
            f"구글 캘린더 공식 초대장을 곧바로 발송해 드리겠습니다.\n\n"
            f"감사합니다.\n"
            f"GDG Korea DevFest 2026 운영팀 드림"
        )

        client = self.get_genai_client()
        if not client:
            return {"subject": default_subject, "body": default_body}

        prompt = f"""당신은 GDG Korea DevFest 2026 운영팀의 연사 섭외 담당 AI 에이전트(OpsAgent)입니다.
아래 연사자 정보를 바탕으로 정중하고 친절하며 명확한 한국어 연사 섭외 이메일 제목(subject)과 본문(body)을 JSON 형식으로 작성하세요.

[연사자 정보]
- 성함: {name}
- 직함/자격: {role} ({speaker.get('badge', '')})
- 연사 순서: {order_label}
- 이메일: {speaker['email']}
- 담당 트랙: {track}
- 제안 발표 주제: {topic}
- 배정 시간: {session_time}

[행사 정보]
- 행사명: {event_name}
- 태그(제목 맨 앞에 포함 필수): {DEVFEST_EVENT_INFO['event_tag']}
- 일시: {event_date}
- 장소: {venue}
- 추가 요청 컨텍스트: {custom_context or '수락 회신을 주시면 발표자 정보 등록 Form(성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호) 및 캘린더 초대장을 보내드린다는 안내 포함'}

반드시 JSON 객체 {{"subject": "...", "body": "..."}} 형태로만 응답하세요.
제목에는 반드시 '{DEVFEST_EVENT_INFO['event_tag']}' 와 '{name}' 님의 성함, '{role}' 가 포함되어야 합니다.
"""
        try:
            resp = self.generate_content_with_fallback(
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            parsed = json.loads(resp.text)
            subj = parsed.get("subject") or default_subject
            if DEVFEST_EVENT_INFO["event_tag"] not in subj:
                subj = f"{DEVFEST_EVENT_INFO['event_tag']} {subj}"
            body = parsed.get("body") or default_body
            return {"subject": subj, "body": body}
        except Exception as exc:
            logger.warning(f"Gemini outreach generation fallback for {name}: {exc}")
            return {"subject": default_subject, "body": default_body}

    def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body_text: str,
        ics_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an email via Gmail API (with optional RFC-5545 Calendar .ics attachment)."""
        gmail = self.get_gmail_service()
        if not gmail:
            return {
                "status": "simulated_no_credentials",
                "to": to_email,
                "subject": subject,
                "message_id": f"sim-{uuid.uuid4().hex[:10]}",
            }

        msg = MIMEMultipart("mixed")
        msg["To"] = formataddr((to_name, to_email))
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="genmunity.gdg.kr")

        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(body_text, "plain", "utf-8"))

        html_body = (
            "<div style='font-family: -apple-system, BlinkMacSystemFont, \"Apple SD Gothic Neo\", "
            "\"Malgun Gothic\", sans-serif; line-height: 1.65; color: #1f2937; max-width: 640px;'>"
            "<div style='background: linear-gradient(135deg, #4285F4, #34A853); padding: 16px 22px; "
            "border-radius: 12px 12px 0 0; color: white; font-weight: 700; font-size: 16px;'>"
            f"Google Developer Groups — {DEVFEST_EVENT_INFO['event_name']}"
            "</div>"
            "<div style='border: 1px solid #e5e7eb; border-top: none; padding: 24px; "
            "border-radius: 0 0 12px 12px; background: #ffffff;'>"
            + body_text.replace("\n", "<br/>")
            + "<hr style='margin: 24px 0; border: none; border-top: 1px solid #e5e7eb;'/>"
            "<div style='font-size: 12px; color: #6b7280;'>"
            "Sent automatically by <b>Genmunity OpsAgent (Google ADK + Workspace Automation)</b>"
            "</div></div></div>"
        )
        alt_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt_part)

        if ics_content:
            cal_part = MIMEText(ics_content, "calendar; method=REQUEST", "utf-8")
            cal_part.add_header("Content-Disposition", "inline; filename=invite.ics")
            msg.attach(cal_part)

            ics_attachment = MIMEBase("application", "ics")
            ics_attachment.set_payload(ics_content.encode("utf-8"))
            encoders.encode_base64(ics_attachment)
            ics_attachment.add_header(
                "Content-Disposition", 'attachment; filename="devfest_2026_speaker_invite.ics"'
            )
            msg.attach(ics_attachment)

        raw_bytes = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        sent = gmail.users().messages().send(userId="me", body={"raw": raw_bytes}).execute()
        return {
            "status": "sent",
            "to": to_email,
            "to_name": to_name,
            "subject": subject,
            "message_id": sent.get("id"),
            "thread_id": sent.get("threadId"),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def send_outreach_to_all_speakers(self, custom_context: str = "") -> Dict[str, Any]:
        """Generate personalized invitation emails and send them via Gmail to both speakers."""
        results = []
        state = load_runtime_state()
        for speaker in HARDCODED_SPEAKERS:
            draft = self.generate_speaker_outreach_email(speaker, custom_context=custom_context)
            send_res = self.send_email(
                to_email=speaker["email"],
                to_name=speaker["name"],
                subject=draft["subject"],
                body_text=draft["body"],
            )
            record = {
                "speaker_order": speaker["speaker_order"],
                "order_label": speaker["order_label"],
                "speaker_name": speaker["name"],
                "speaker_role": speaker["role"],
                "speaker_email": speaker["email"],
                "subject": draft["subject"],
                "body": draft["body"],
                "delivery": send_res,
            }
            results.append(record)
            state.setdefault("outreach_history", []).append(record)

        save_runtime_state(state)
        return {
            "status": "completed",
            "total_sent": len(results),
            "outreach_results": results,
        }

    # -------------------------------------------------------------------------
    # Step 3: Gmail Event Email Collection & AI Clustering
    # -------------------------------------------------------------------------
    def _extract_plain_text_from_payload(self, payload: Dict[str, Any]) -> str:
        """Recursively extract plain text from Gmail message payload."""
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data")
        if body_data and mime_type in ("text/plain", "text/html"):
            try:
                decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
                return decoded
            except Exception:
                pass
        for part in payload.get("parts", []) or []:
            text = self._extract_plain_text_from_payload(part)
            if text:
                return text
        return ""

    def collect_event_emails_from_gmail(self, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Query Gmail API for emails related to the DevFest event or our speakers
        (sniper45han@gmail.com, aristojeff@gmail.com).
        """
        gmail = self.get_gmail_service()
        collected: List[Dict[str, Any]] = []
        if not gmail:
            return collected

        query = (
            "(from:sniper45han@gmail.com OR to:sniper45han@gmail.com "
            "OR from:aristojeff@gmail.com OR to:aristojeff@gmail.com "
            'OR subject:"DevFest" OR subject:"연사")'
        )
        try:
            res = (
                gmail.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = res.get("messages", [])
            for m in messages:
                msg_detail = (
                    gmail.users()
                    .messages()
                    .get(userId="me", id=m["id"], format="full")
                    .execute()
                )
                payload = msg_detail.get("payload", {})
                headers = {
                    h["name"].lower(): h["value"] for h in payload.get("headers", [])
                }
                subject = headers.get("subject", "(제목 없음)")
                sender = headers.get("from", "")
                recipient = headers.get("to", "")
                date_str = headers.get("date", "")
                snippet = msg_detail.get("snippet", "")
                body_text = self._extract_plain_text_from_payload(payload) or snippet
                labels = msg_detail.get("labelIds", [])

                # Match speaker
                matched_speaker = None
                for sp in HARDCODED_SPEAKERS:
                    if (
                        sp["email"].lower() in sender.lower()
                        or sp["email"].lower() in recipient.lower()
                        or sp["name"] in subject
                        or sp["name"] in body_text
                    ):
                        matched_speaker = {
                            "name": sp["name"],
                            "role": sp["role"],
                            "email": sp["email"],
                            "order_label": sp["order_label"],
                        }
                        break

                direction = "INBOUND_RECEIVED"
                if "SENT" in labels and not any(
                    sp["email"].lower() in sender.lower() for sp in HARDCODED_SPEAKERS
                ):
                    direction = "OUTBOUND_SENT_CONFIRMED"

                collected.append(
                    {
                        "message_id": m["id"],
                        "thread_id": msg_detail.get("threadId"),
                        "subject": subject,
                        "from": sender,
                        "to": recipient,
                        "date": date_str,
                        "direction": direction,
                        "labels": labels,
                        "snippet": snippet,
                        "body_preview": body_text[:600],
                        "speaker": matched_speaker,
                    }
                )
        except Exception as exc:
            logger.warning(f"Failed to query Gmail messages: {exc}")

        return collected

    def collect_and_cluster_emails(self, max_results: int = 20) -> Dict[str, Any]:
        """
        Collect event-related emails from Gmail, verify receipt/reply status for
        한성민 (sniper45han@gmail.com) and 박제창 (aristojeff@gmail.com), and cluster them using Gemini.
        """
        emails = self.collect_event_emails_from_gmail(max_results=max_results)

        # Build per-speaker receipt & response tracking summary
        speaker_tracking = []
        for sp in HARDCODED_SPEAKERS:
            sp_emails = [
                e
                for e in emails
                if (e.get("speaker") and e["speaker"]["email"] == sp["email"])
                or sp["email"].lower() in (e.get("from", "") + e.get("to", "")).lower()
            ]
            inbound = [e for e in sp_emails if e["direction"] == "INBOUND_RECEIVED"]
            outbound = [e for e in sp_emails if e["direction"] == "OUTBOUND_SENT_CONFIRMED"]
            speaker_tracking.append(
                {
                    "speaker_order": sp["speaker_order"],
                    "order_label": sp["order_label"],
                    "name": sp["name"],
                    "role": sp["role"],
                    "email": sp["email"],
                    "total_related_emails": len(sp_emails),
                    "outbound_sent_count": len(outbound),
                    "inbound_reply_count": len(inbound),
                    "receipt_verified": len(sp_emails) > 0,
                    "status": (
                        "회신 수신 완료 (Reply Confirmed)"
                        if inbound
                        else (
                            "섭외 메일 발송 및 수신 확인됨 (Outreach Delivered)"
                            if outbound
                            else "발송 대기 (Pending Outreach)"
                        )
                    ),
                    "latest_subject": sp_emails[0]["subject"] if sp_emails else None,
                }
            )

        # Default heuristic clusters (enhanced by Gemini below)
        outreach_msgs = [
            e for e in emails if "초청" in e["subject"] or "섭외" in e["subject"] or "연사" in e["subject"]
        ]
        onboarding_msgs = [
            e for e in emails if "폼" in e["subject"] or "Form" in e["subject"] or "캘린더" in e["subject"] or "정보" in e["subject"]
        ]
        inbound_msgs = [e for e in emails if e["direction"] == "INBOUND_RECEIVED"]

        default_clusters = [
            {
                "cluster_id": "cluster_outreach_confirmation",
                "cluster_name": "연사 섭외 발송 및 수신 확인 (Speaker Outreach & Delivery)",
                "description": "AI GDE 한성민님(1번째 연사자) 및 Flutter GDE 박제창님(2번째 연사자) 대상 DevFest 핸즈온 섭외 메일 스레드",
                "email_count": len(outreach_msgs),
                "speakers_involved": ["한성민 (AI GDE)", "박제창 (Flutter GDE)"],
                "key_insights": "섭외 메일 발송 및 Gmail 스레드 트래킹 활성화 완료. 연사 정보 수집용 Form 생성 단계 진입 가능.",
                "sample_subjects": [e["subject"] for e in outreach_msgs[:4]],
            },
            {
                "cluster_id": "cluster_speaker_replies",
                "cluster_name": "연사 회신 및 세션 조율 (Speaker Replies & Session Alignment)",
                "description": "연사자로부터 수신된 참석 수락, 핸즈온 주제 확정 및 시간표 조율 관련 메일 클러스터",
                "email_count": len(inbound_msgs),
                "speakers_involved": list(
                    {
                        f"{e['speaker']['name']} ({e['speaker']['role']})"
                        for e in inbound_msgs
                        if e.get("speaker")
                    }
                )
                or ["한성민 (AI GDE)", "박제창 (Flutter GDE)"],
                "key_insights": (
                    f"수신된 연사 관련 메일 {len(inbound_msgs)}건 감지됨. 발표자 온보딩 Form 및 캘린더 초대장 발송 권장."
                ),
                "sample_subjects": [e["subject"] for e in inbound_msgs[:4]],
            },
            {
                "cluster_id": "cluster_onboarding_logistics",
                "cluster_name": "발표자 온보딩 Form 및 캘린더 초대 (Onboarding Form & Logistics)",
                "description": "발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호 수집 Form 및 캘린더 일정 초대 클러스터",
                "email_count": len(onboarding_msgs),
                "speakers_involved": ["한성민 (AI GDE)", "박제창 (Flutter GDE)"],
                "key_insights": "현장 주차 등록(차량 번호) 및 연사 웰컴 키트(티셔츠 사이즈) 사전 취합 프로세스.",
                "sample_subjects": [e["subject"] for e in onboarding_msgs[:4]],
            },
        ]

        client = self.get_genai_client()
        ai_summary = (
            f"총 {len(emails)}건의 DevFest 2026 행사 및 연사(한성민 AI GDE, 박제창 Flutter GDE) 관련 Gmail 메시지를 수집하여 "
            "3개의 운영 클러스터로 분류했습니다. 다음 단계로 발표자 정보 입력 Form(성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호) 생성 및 초대를 진행할 수 있습니다."
        )
        clusters = default_clusters

        if client and emails:
            compact_emails = [
                {
                    "subject": e["subject"],
                    "from": e["from"],
                    "to": e["to"],
                    "direction": e["direction"],
                    "speaker": e["speaker"]["name"] if e.get("speaker") else "기타",
                    "snippet": e["snippet"][:200],
                }
                for e in emails[:15]
            ]
            prompt = f"""당신은 GDG DevFest 행사 운영을 자동화하는 OpsAgent입니다.
Gmail에서 수집된 아래 행사/연사 관련 이메일 목록을 분석하여 의미 단위 클러스터(clusters)와 종합 요약(ai_summary), 그리고 다음 권장 액션(next_recommended_action)을 JSON으로 생성하세요.

[대상 연사자]
1. 한성민 (sniper45han@gmail.com) - AI GDE, 첫번째 연사자
2. 박제창 (aristojeff@gmail.com) - Flutter GDE, 두번째 연사자

[수집된 Gmail 메시지 ({len(emails)}건)]
{json.dumps(compact_emails, ensure_ascii=False, indent=2)}

JSON 스키마:
{{
  "ai_summary": "전체 수신/발신 현황 및 연사별 상태 한국어 요약",
  "next_recommended_action": "발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호 수집용 Form 생성 및 캘린더 초대장 발송",
  "clusters": [
    {{
      "cluster_id": "string",
      "cluster_name": "한국어 클러스터 이름",
      "description": "클러스터 설명",
      "email_count": 1,
      "speakers_involved": ["한성민 (AI GDE)", "박제창 (Flutter GDE)"],
      "key_insights": "핵심 요약",
      "sample_subjects": ["메일 제목 예시"]
    }}
  ]
}}"""
            try:
                resp = self.generate_content_with_fallback(
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                parsed = json.loads(resp.text)
                if parsed.get("clusters"):
                    clusters = parsed["clusters"]
                if parsed.get("ai_summary"):
                    ai_summary = parsed["ai_summary"]
            except Exception as exc:
                logger.warning(f"Gemini email clustering fallback: {exc}")

        result = {
            "status": "clustered",
            "total_emails_collected": len(emails),
            "speaker_tracking": speaker_tracking,
            "ai_summary": ai_summary,
            "next_recommended_action": (
                "발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호 수집용 Form 생성 및 연사 초대장 발송"
            ),
            "clusters": clusters,
            "emails": emails,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        state = load_runtime_state()
        state["clustered_emails"] = result
        save_runtime_state(state)
        return result

    # -------------------------------------------------------------------------
    # Step 4: Speaker Onboarding Form Creation (Google Forms API v1)
    # -------------------------------------------------------------------------
    def create_speaker_onboarding_form(
        self, form_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a real Google Form (via Google Forms API v1: forms.googleapis.com) collecting:
        - 발표자 성함 (Speaker Name)
        - 이메일 (Email)
        - 연락처 (Phone Number)
        - 티셔츠 사이즈 (T-Shirt Size)
        - 차량 번호 (Vehicle License Plate Number)
        - 핸즈온 세션 제목 및 필요 환경 (Session Title)
        """
        title = form_title or f"{DEVFEST_EVENT_INFO['event_tag']} 발표자 사전 정보 등록 폼 (Speaker Onboarding)"
        form_id = f"devfest2026-{uuid.uuid4().hex[:8]}"
        google_form_url: Optional[str] = None
        google_form_edit_url: Optional[str] = None
        form_provider = "genmunity_hosted_fallback"

        try:
            forms_service = self.get_forms_service()
            if forms_service:
                created = (
                    forms_service.forms()
                    .create(body={"info": {"title": title, "documentTitle": title}})
                    .execute()
                )
                g_form_id = created.get("formId")
                if g_form_id:
                    batch_requests = [
                        {
                            "updateFormInfo": {
                                "info": {
                                    "description": (
                                        f"{DEVFEST_EVENT_INFO['event_name']} ({DEVFEST_EVENT_INFO['event_date']}, "
                                        f"{DEVFEST_EVENT_INFO['venue']}) 연사자 사전 정보 및 현장 지원(웰컴 티셔츠, 무료 주차 등록) 입력 폼입니다."
                                    )
                                },
                                "updateMask": "description",
                            }
                        },
                        {
                            "createItem": {
                                "item": {
                                    "title": "발표자 성함",
                                    "questionItem": {
                                        "question": {
                                            "required": True,
                                            "textQuestion": {"paragraph": False},
                                        }
                                    },
                                },
                                "location": {"index": 0},
                            }
                        },
                        {
                            "createItem": {
                                "item": {
                                    "title": "이메일",
                                    "questionItem": {
                                        "question": {
                                            "required": True,
                                            "textQuestion": {"paragraph": False},
                                        }
                                    },
                                },
                                "location": {"index": 1},
                            }
                        },
                        {
                            "createItem": {
                                "item": {
                                    "title": "연락처 (휴대폰 번호)",
                                    "questionItem": {
                                        "question": {
                                            "required": True,
                                            "textQuestion": {"paragraph": False},
                                        }
                                    },
                                },
                                "location": {"index": 2},
                            }
                        },
                        {
                            "createItem": {
                                "item": {
                                    "title": "티셔츠 사이즈 (연사 웰컴 키트)",
                                    "questionItem": {
                                        "question": {
                                            "required": True,
                                            "choiceQuestion": {
                                                "type": "RADIO",
                                                "options": [
                                                    {"value": "S (90)"},
                                                    {"value": "M (95)"},
                                                    {"value": "L (100)"},
                                                    {"value": "XL (105)"},
                                                    {"value": "2XL (110)"},
                                                    {"value": "3XL (115)"},
                                                ],
                                            },
                                        }
                                    },
                                },
                                "location": {"index": 3},
                            }
                        },
                        {
                            "createItem": {
                                "item": {
                                    "title": "차량 번호 (오토웨이타워 무료 주차 등록용, 차량 미이용 시 '없음' 기재)",
                                    "questionItem": {
                                        "question": {
                                            "required": True,
                                            "textQuestion": {"paragraph": False},
                                        }
                                    },
                                },
                                "location": {"index": 4},
                            }
                        },
                        {
                            "createItem": {
                                "item": {
                                    "title": "핸즈온 세션 제목 및 필요 환경",
                                    "questionItem": {
                                        "question": {
                                            "required": False,
                                            "textQuestion": {"paragraph": True},
                                        }
                                    },
                                },
                                "location": {"index": 5},
                            }
                        },
                    ]
                    forms_service.forms().batchUpdate(
                        formId=g_form_id, body={"requests": batch_requests}
                    ).execute()
                    google_form_url = created.get(
                        "responderUri", f"https://docs.google.com/forms/d/{g_form_id}/viewform"
                    )
                    google_form_edit_url = f"https://docs.google.com/forms/d/{g_form_id}/edit"
                    form_id = g_form_id
                    form_provider = "google_forms_api_v1"
        except Exception as exc:
            logger.info(
                f"Google Forms API requires forms.body scope on user OAuth token (fallback active): {exc}"
            )

        hosted_form_url = f"{GENMUNITY_BASE_URL.rstrip('/')}/forms/speaker-onboarding/{form_id}"
        primary_form_url = google_form_url or hosted_form_url

        speaker_personalized_links = []
        for sp in HARDCODED_SPEAKERS:
            if google_form_url:
                target_url = google_form_url
            else:
                params = urlencode(
                    {
                        "name": sp["name"],
                        "email": sp["email"],
                        "role": f"{sp['role']} ({sp['order_label']})",
                        "session_title": sp["proposed_topic"],
                    }
                )
                target_url = f"{hosted_form_url}?{params}"
            speaker_personalized_links.append(
                {
                    "speaker_order": sp["speaker_order"],
                    "order_label": sp["order_label"],
                    "name": sp["name"],
                    "role": sp["role"],
                    "email": sp["email"],
                    "personalized_form_url": target_url,
                }
            )

        form_record = {
            "form_id": form_id,
            "form_provider": form_provider,
            "title": title,
            "primary_form_url": primary_form_url,
            "google_form_url": google_form_url,
            "google_form_edit_url": google_form_edit_url,
            "hosted_form_url": hosted_form_url,
            "fields": DEVFEST_EVENT_INFO["onboarding_form_fields"],
            "speaker_links": speaker_personalized_links,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        state = load_runtime_state()
        state.setdefault("forms", {})[form_id] = form_record
        state["latest_form"] = form_record
        save_runtime_state(state)
        return form_record

    def fetch_google_form_responses(self, form_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch submitted responses from Google Forms API v1 (forms.responses.list)."""
        state = load_runtime_state()
        target_form_id = form_id or (state.get("latest_form") or {}).get("form_id")
        if not target_form_id:
            return {"status": "no_form_id", "responses": []}

        try:
            forms_service = self.get_forms_service()
            if forms_service and not target_form_id.startswith("devfest2026-"):
                res = forms_service.forms().responses().list(formId=target_form_id).execute()
                return {
                    "status": "fetched_from_google_forms_api",
                    "form_id": target_form_id,
                    "responses": res.get("responses", []),
                }
        except Exception as exc:
            logger.warning(f"Failed to list Google Form responses for {target_form_id}: {exc}")

        return {
            "status": "fetched_from_local_state",
            "form_id": target_form_id,
            "responses": [
                s
                for s in state.get("form_submissions", [])
                if s.get("form_id") == target_form_id or not form_id
            ],
        }

    # -------------------------------------------------------------------------
    # Step 5: Google Calendar API Event Creation & Onboarding Form Dispatch
    # -------------------------------------------------------------------------
    def create_google_calendar_event_for_speaker(
        self, speaker: Dict[str, Any], form_url: str
    ) -> Dict[str, Any]:
        """
        Create a real Google Calendar Event via Google Calendar API v3 (calendar.events().insert).
        First tries user OAuth credentials (sending native Google Calendar attendee updates),
        then falls back to GCP Service Account credentials if user OAuth lacks calendar scope.
        """
        summary = f"{DEVFEST_EVENT_INFO['event_tag']} {speaker['name']} ({speaker['role']}) 핸즈온 세션"
        description = (
            f"{DEVFEST_EVENT_INFO['event_name']} 공식 연사 세션 일정입니다.\n"
            f"- 연사자: {speaker['name']} ({speaker['role']} / {speaker['order_label']})\n"
            f"- 담당 트랙: {speaker['track']}\n"
            f"- 제안 주제: {speaker['proposed_topic']}\n"
            f"- 발표 시간: {speaker['session_time']}\n"
            f"- 발표자 정보 등록 Google Form: {form_url}"
        )

        # 1. Try User OAuth Calendar Service (supports attendees & Google Meet creation)
        try:
            cal_service = self.get_calendar_service()
            if cal_service:
                ev = (
                    cal_service.events()
                    .insert(
                        calendarId="primary",
                        sendUpdates="all",
                        conferenceDataVersion=1,
                        body={
                            "summary": summary,
                            "location": DEVFEST_EVENT_INFO["venue"],
                            "description": description,
                            "start": {
                                "dateTime": DEVFEST_EVENT_INFO["event_start_iso"],
                                "timeZone": "Asia/Seoul",
                            },
                            "end": {
                                "dateTime": DEVFEST_EVENT_INFO["event_end_iso"],
                                "timeZone": "Asia/Seoul",
                            },
                            "attendees": [
                                {"email": speaker["email"], "displayName": speaker["name"]}
                            ],
                            "conferenceData": {
                                "createRequest": {
                                    "requestId": f"meet-{uuid.uuid4().hex[:10]}",
                                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                                }
                            },
                        },
                    )
                    .execute()
                )
                return {
                    "provider": "google_calendar_api_v3_oauth",
                    "event_id": ev.get("id"),
                    "html_link": ev.get("htmlLink"),
                    "hangout_link": ev.get("hangoutLink"),
                }
        except Exception as exc:
            logger.info(f"User OAuth Calendar insert fallback to Service Account: {exc}")

        # 2. Fallback to GCP Service Account Calendar API v3 so a real Google Calendar event is always created
        sa_path = BASE_DIR / "service_account.json"
        if sa_path.exists():
            try:
                from google.oauth2 import service_account

                sa_creds = service_account.Credentials.from_service_account_file(
                    str(sa_path), scopes=["https://www.googleapis.com/auth/calendar"]
                )
                sa_cal = build("calendar", "v3", credentials=sa_creds)
                ev = (
                    sa_cal.events()
                    .insert(
                        calendarId="primary",
                        body={
                            "summary": summary,
                            "location": DEVFEST_EVENT_INFO["venue"],
                            "description": description,
                            "start": {
                                "dateTime": DEVFEST_EVENT_INFO["event_start_iso"],
                                "timeZone": "Asia/Seoul",
                            },
                            "end": {
                                "dateTime": DEVFEST_EVENT_INFO["event_end_iso"],
                                "timeZone": "Asia/Seoul",
                            },
                        },
                    )
                    .execute()
                )
                return {
                    "provider": "google_calendar_api_v3_service_account",
                    "event_id": ev.get("id"),
                    "html_link": ev.get("htmlLink"),
                    "hangout_link": ev.get("hangoutLink"),
                }
            except Exception as exc:
                logger.warning(f"Service account Google Calendar creation failed: {exc}")

        return {"provider": "ics_only", "event_id": None, "html_link": None, "hangout_link": None}

    def build_ics_calendar_invite(self, speaker: Dict[str, Any], form_url: str) -> str:
        """Build an RFC-5545 iCalendar (METHOD:REQUEST) payload for native Gmail Calendar invite card."""
        uid = f"devfest2026-speaker-{speaker['speaker_order']}-{uuid.uuid4().hex[:8]}@genmunity.gdg.kr"
        dtstamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dtstart = "20261121T040000Z"
        dtend = "20261121T090000Z"
        summary = f"{DEVFEST_EVENT_INFO['event_tag']} {speaker['name']} ({speaker['role']}) 핸즈온 세션 발표"
        description = (
            f"안녕하세요 {speaker['name']} ({speaker['role']} / {speaker['order_label']})님,\\n"
            f"DevFest 2026 핸즈온 세션 공식 캘린더 초대장입니다.\\n\\n"
            f"- 배정 트랙: {speaker['track']}\\n"
            f"- 발표 시간: {speaker['session_time']}\\n"
            f"- 발표자 정보 등록 Google Form(성함/이메일/연락처/티셔츠 사이즈/차량 번호): {form_url}"
        )
        location = DEVFEST_EVENT_INFO["venue"]

        lines = [
            "BEGIN:VCALENDAR",
            "PRODID:-//Genmunity OpsAgent//GDG DevFest 2026//KO",
            "VERSION:2.0",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{location}",
            f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN={speaker['name']}:mailto:{speaker['email']}",
            "STATUS:CONFIRMED",
            "SEQUENCE:0",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        return "\r\n".join(lines)

    def send_speaker_form_and_calendar_invite(
        self, form_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send the Google Form link (발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호)
        and Google Calendar Event Invitation (Google Calendar API v3 + .ics) to both speakers via Gmail.
        """
        state = load_runtime_state()
        form_record = None
        if form_id and form_id in state.get("forms", {}):
            form_record = state["forms"][form_id]
        elif state.get("latest_form"):
            form_record = state["latest_form"]
        else:
            form_record = self.create_speaker_onboarding_form()

        link_map = {
            item["email"]: item["personalized_form_url"]
            for item in form_record.get("speaker_links", [])
        }

        invite_results = []
        for speaker in HARDCODED_SPEAKERS:
            personal_form_url = (
                form_record.get("google_form_url")
                or link_map.get(speaker["email"])
                or form_record["primary_form_url"]
            )
            cal_event = self.create_google_calendar_event_for_speaker(speaker, personal_form_url)
            cal_html_link = cal_event.get("html_link") or "첨부된 .ics 캘린더 파일 참조"

            subject = (
                f"{DEVFEST_EVENT_INFO['event_tag']} [연사 초대 및 사전 정보 등록] "
                f"{speaker['name']} {speaker['role']}님 Google Form 및 Google Calendar 초대장"
            )
            body_text = (
                f"안녕하세요 {speaker['name']} {speaker['role']}님 ({speaker['order_label']}),\n\n"
                f"{DEVFEST_EVENT_INFO['event_name']} 연사로 함께해 주셔서 진심으로 감사드립니다!\n"
                f"원활한 현장 운영과 연사 웰컴 키트 제작, 당일 무료 주차 등록을 위해 아래 발표자 사전 정보 등록 Google Form 작성을 부탁드립니다.\n\n"
                f"■ 발표자 사전 정보 입력 Google Form 링크\n"
                f"- {personal_form_url}\n\n"
                f"■ 필수 입력 항목 안내\n"
                f"1. 발표자 성함: {speaker['name']}\n"
                f"2. 이메일: {speaker['email']}\n"
                f"3. 연락처: 행사 당일 비상 연락용 휴대폰 번호\n"
                f"4. 티셔츠 사이즈: 연사 전용 웰컴 티셔츠 사이즈 (S / M / L / XL / 2XL / 3XL)\n"
                f"5. 차량 번호: 오토웨이타워 무료 주차 사전 등록용 차량 번호 (자차 미이용 시 '없음' 기재)\n"
                f"6. 핸즈온 세션 제목: {speaker['proposed_topic']}\n\n"
                f"■ Google Calendar 공식 일정 등록 안내\n"
                f"- 일시: {DEVFEST_EVENT_INFO['event_date']} ({speaker['session_time']})\n"
                f"- 장소: {DEVFEST_EVENT_INFO['venue']}\n"
                f"- Google Calendar 일정 링크: {cal_html_link}\n"
                + (
                    f"- Google Meet 링크: {cal_event['hangout_link']}\n"
                    if cal_event.get("hangout_link")
                    else ""
                )
                + "\n감사합니다.\n"
                f"GDG Korea DevFest 2026 운영팀 (Genmunity OpsAgent) 드림"
            )

            ics_payload = self.build_ics_calendar_invite(speaker, personal_form_url)
            email_res = self.send_email(
                to_email=speaker["email"],
                to_name=speaker["name"],
                subject=subject,
                body_text=body_text,
                ics_content=ics_payload,
            )

            rec = {
                "speaker_order": speaker["speaker_order"],
                "order_label": speaker["order_label"],
                "speaker_name": speaker["name"],
                "speaker_role": speaker["role"],
                "speaker_email": speaker["email"],
                "form_provider": form_record.get("form_provider"),
                "form_url": personal_form_url,
                "google_form_url": form_record.get("google_form_url"),
                "calendar_provider": cal_event.get("provider"),
                "calendar_api_event_id": cal_event.get("event_id"),
                "calendar_html_link": cal_event.get("html_link"),
                "google_meet_link": cal_event.get("hangout_link"),
                "calendar_ics_attached": True,
                "delivery": email_res,
            }
            invite_results.append(rec)

        state = load_runtime_state()
        state.setdefault("calendar_invites", []).extend(invite_results)
        save_runtime_state(state)

        return {
            "status": "invited",
            "form_id": form_record["form_id"],
            "form_provider": form_record.get("form_provider"),
            "form_title": form_record["title"],
            "primary_form_url": form_record["primary_form_url"],
            "google_form_url": form_record.get("google_form_url"),
            "google_form_edit_url": form_record.get("google_form_edit_url"),
            "required_fields": [f["label"] for f in form_record["fields"]],
            "invites_sent": invite_results,
        }


_workspace_service: Optional[GoogleWorkspaceService] = None


def get_workspace_service() -> GoogleWorkspaceService:
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = GoogleWorkspaceService()
    return _workspace_service
