import os
import json
import subprocess
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from genmunity_agent.config import (
    BASE_DIR,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
    record_agent_trace,
)
from genmunity_agent.services.google_workspace import get_workspace_service

logger = logging.getLogger("genmunity.mail_trigger")

DEFAULT_ADMIN_EMAIL = "devstar5011@gcplab.me"
DEFAULT_GCP_PROJECT = "automation-511905"
DEFAULT_PUBSUB_TOPIC = f"projects/{DEFAULT_GCP_PROJECT}/topics/gmail-push-topic"

ADMIN_REGISTRY_PATH: Path = BASE_DIR / "data" / "mail_admin_registry.json"
CREDENTIALS_FILE_CANDIDATES = [
    BASE_DIR / "credentials.json",
    Path(os.path.expanduser("~/automation/credentials.json")),
]
TOKEN_PATH: Path = BASE_DIR / "token.json"

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]


def load_admin_registry() -> Dict[str, Any]:
    """Load persisted mail admin OAuth registration & trigger state."""
    if ADMIN_REGISTRY_PATH.exists():
        try:
            with open(ADMIN_REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Failed to read mail_admin_registry.json: {exc}")

    return {
        "target_admin_email": DEFAULT_ADMIN_EMAIL,
        "authenticated_email": None,
        "is_target_admin_active": False,
        "registered_at": None,
        "initial_history_id": None,
        "last_history_id": None,
        "pubsub_topic": DEFAULT_PUBSUB_TOPIC,
        "pubsub_watch": None,
        "secret_manager_synced": False,
        "auto_trigger_enabled": True,
        "auto_send_form_on_reply": True,
        "poll_interval_seconds": 6,
        "baseline_message_ids": [],
        "processed_inbound_message_ids": [],
        "trigger_events": [],
    }


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
) -> Dict[str, Any]:
    """
    Launch OAuth 2.0 InstalledAppFlow for the Mail Administrator account (default: devstar5011@gcplab.me),
    save token.json, snapshot existing inbox message IDs so only NEW replies trigger actions,
    register Gmail API users.watch (Cloud Pub/Sub), and optionally update GCP Secret Manager.
    """
    creds_file = find_credentials_file()
    if not creds_file:
        raise FileNotFoundError(
            "OAuth client file 'credentials.json' not found in Genmunity or ~/automation."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), DEFAULT_SCOPES)
    creds = flow.run_local_server(
        port=0,
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


def check_and_trigger_on_inbound_emails(
    trigger_source: str = "polling_or_webhook",
    force_process_latest: bool = False,
) -> Dict[str, Any]:
    """
    Inspect the registered Mail Admin's INBOX (devstar5011@gcplab.me) for new incoming emails
    from our target speakers (sniper45han@gmail.com, aristojeff@gmail.com) or regarding DevFest.

    When a new speaker reply is detected:
    1. Automatically runs OpsAgent's Gmail Collection & Gemini Clustering (`collect_and_cluster_emails`).
    2. If `auto_send_form_on_reply` is True, automatically generates the Speaker Onboarding Form
       (발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호) and sends the Form link + Calendar Invite (.ics)
       to the speaker who replied!
    """
    reg = sync_live_gmail_profile()
    ws = get_workspace_service()
    gmail = ws.get_gmail_service()
    if not gmail:
        return {"status": "no_gmail_credentials", "new_triggers": []}

    speaker_emails = [sp["email"].lower() for sp in HARDCODED_SPEAKERS]
    query = (
        "label:INBOX ("
        + " OR ".join(f"from:{email}" for email in speaker_emails)
        + ' OR subject:"DevFest" OR subject:"연사")'
    )

    try:
        res = gmail.users().messages().list(userId="me", q=query, maxResults=15).execute()
        messages = res.get("messages", [])
    except Exception as exc:
        logger.warning(f"Failed to check inbound emails for trigger: {exc}")
        return {"status": "error", "error": str(exc), "new_triggers": []}

    baseline_set = set(reg.get("baseline_message_ids", []))
    processed_set = set(reg.get("processed_inbound_message_ids", []))

    # If baseline was never initialized (e.g. first run before OAuth script), initialize baseline
    # unless force_process_latest is True
    if not baseline_set and not reg.get("registered_at") and not force_process_latest:
        reg["baseline_message_ids"] = [m["id"] for m in messages]
        save_admin_registry(reg)
        return {
            "status": "baseline_initialized",
            "authenticated_email": reg.get("authenticated_email"),
            "baseline_count": len(messages),
            "new_triggers": [],
        }

    new_triggers: List[Dict[str, Any]] = []
    for idx, m in enumerate(messages):
        msg_id = m["id"]
        if not force_process_latest:
            if msg_id in baseline_set or msg_id in processed_set:
                continue
        else:
            # When force_process_latest is True, only process the most recent 1 message if not already in this call
            if idx > 0:
                break

        try:
            detail = gmail.users().messages().get(userId="me", id=msg_id, format="full").execute()
            payload = detail.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            sender = headers.get("from", "")
            subject = headers.get("subject", "(제목 없음)")
            date_str = headers.get("date", "")
            snippet = detail.get("snippet", "")

            # Avoid self-sent loops if the admin sent an email to themselves with [연사 초대 및 사전 정보 등록]
            if "연사 초대 및 사전 정보 등록" in subject:
                processed_set.add(msg_id)
                continue

            matched_speaker = None
            for sp in HARDCODED_SPEAKERS:
                if sp["email"].lower() in sender.lower() or sp["name"] in sender or sp["name"] in subject:
                    matched_speaker = sp
                    break

            # 1. Trigger Gemini Email Collection & Clustering
            cluster_result = ws.collect_and_cluster_emails(max_results=20)

            # 2. Create Onboarding Form & send Form + Calendar Invite if enabled
            auto_invite_result = None
            if reg.get("auto_send_form_on_reply", True):
                form_record = ws.create_speaker_onboarding_form()
                if matched_speaker:
                    # Send specifically to the speaker who replied (or all speakers)
                    invite_res = ws.send_speaker_form_and_calendar_invite(
                        form_id=form_record["form_id"]
                    )
                    auto_invite_result = {
                        "form_id": form_record["form_id"],
                        "form_url": form_record["primary_form_url"],
                        "invites_sent": invite_res.get("invites_sent", []),
                    }

            event_record = {
                "trigger_id": f"trig-{msg_id}",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "trigger_source": trigger_source,
                "admin_inbox": reg.get("authenticated_email"),
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
                "actions_executed": [
                    "collect_and_cluster_event_emails (Gmail + GenContent)",
                    "create_speaker_onboarding_form (성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호)",
                    "send_speaker_form_and_calendar_invite (Form + Calendar .ics + Gmail)",
                ]
                if auto_invite_result
                else ["collect_and_cluster_event_emails (Gmail + GenContent)"],
                "cluster_summary": cluster_result.get("ai_summary"),
                "onboarding_form_url": (
                    auto_invite_result["form_url"] if auto_invite_result else None
                ),
            }
            new_triggers.append(event_record)
            processed_set.add(msg_id)

            reg.setdefault("trigger_events", []).append(event_record)
            reg["trigger_events"] = reg["trigger_events"][-30:]

            record_agent_trace(
                agent_name="OpsAgent",
                capability="InboundEmailTrigger",
                summary=(
                    f"[{reg.get('authenticated_email')}] 이메일 수신 트리거 발동! "
                    f"발신자: {sender} | 제목: '{subject}' -> 자동 클러스터링 및 온보딩 Form/캘린더 초대 발송 완료"
                ),
                details=event_record,
            )
        except Exception as exc:
            logger.warning(f"Error processing inbound trigger message {msg_id}: {exc}")

    reg["processed_inbound_message_ids"] = list(processed_set)
    save_admin_registry(reg)

    return {
        "status": "checked",
        "authenticated_email": reg.get("authenticated_email"),
        "is_target_admin_active": reg.get("is_target_admin_active"),
        "new_triggers_count": len(new_triggers),
        "new_triggers": new_triggers,
        "recent_trigger_events": reg.get("trigger_events", [])[-10:],
    }
