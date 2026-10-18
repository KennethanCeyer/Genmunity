import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from genmunity_agent.config import (
    GEMINI_PRIMARY_MODEL,
    GEMINI_SECONDARY_MODEL,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
    GDG_KOREA_SHEET_URL,
    load_runtime_state,
    save_runtime_state,
    record_agent_trace,
)
from genmunity_agent.services import (
    DEFAULT_ADMIN_EMAIL,
    load_admin_registry,
    save_admin_registry,
    sync_live_gmail_profile,
    register_mail_admin_via_oauth,
    check_and_trigger_on_inbound_emails,
)
from genmunity_agent.sub_agents.ops_agent import (
    get_target_speakers_tool,
    generate_and_send_speaker_emails_tool,
    collect_and_cluster_event_emails_tool,
    create_speaker_onboarding_form_tool,
    invite_speakers_with_form_and_calendar_tool,
    run_ops_full_workflow_tool,
)
from genmunity_agent.runner import run_agent_chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("genmunity.app")

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo.png"


async def _inbox_watcher_loop() -> None:
    """Background task that checks the registered Mail Admin INBOX for new speaker replies."""
    while True:
        try:
            reg = load_admin_registry()
            interval = max(4, int(reg.get("poll_interval_seconds", 6)))
            if reg.get("auto_trigger_enabled", True):
                await asyncio.to_thread(
                    check_and_trigger_on_inbound_emails,
                    trigger_source="background_inbox_watcher",
                    force_process_latest=False,
                )
        except Exception as exc:
            logger.debug(f"Background inbox watcher tick warning: {exc}")
            interval = 8
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_inbox_watcher_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="Genmunity — Agentic CommunityHub & Event Ops Platform (Google ADK)",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/logo.png")
@app.get("/assets/logo.png")
def serve_logo():
    return FileResponse(LOGO_PATH, media_type="image/png")


class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None


class OutreachRequest(BaseModel):
    custom_context: Optional[str] = ""


class FormCreateRequest(BaseModel):
    form_title: Optional[str] = ""


class InviteRequest(BaseModel):
    form_id: Optional[str] = ""


class AdminOAuthRequest(BaseModel):
    target_email: Optional[str] = DEFAULT_ADMIN_EMAIL
    register_pubsub_watch: Optional[bool] = True
    sync_secret_manager: Optional[bool] = True


class TriggerCheckRequest(BaseModel):
    force_process_latest: Optional[bool] = False


class TriggerToggleRequest(BaseModel):
    auto_trigger_enabled: Optional[bool] = None
    auto_send_form_on_reply: Optional[bool] = None


@app.get("/api/health")
def health_check():
    reg = load_admin_registry()
    return {
        "status": "ok",
        "project": "Genmunity",
        "framework": "Google ADK (google-adk) + Gemini 4.0 Argon / 3.8 Flash + Google Workspace",
        "primary_model": GEMINI_PRIMARY_MODEL,
        "secondary_model": GEMINI_SECONDARY_MODEL,
        "agents": ["RootAgent", "SearchAgent", "OpsAgent"],
        "speakers": HARDCODED_SPEAKERS,
        "mail_admin": {
            "target_admin_email": reg.get("target_admin_email", DEFAULT_ADMIN_EMAIL),
            "authenticated_email": reg.get("authenticated_email"),
            "is_target_admin_active": reg.get("is_target_admin_active"),
            "auto_trigger_enabled": reg.get("auto_trigger_enabled", True),
        },
    }


@app.get("/api/state")
def get_state():
    state = load_runtime_state()
    admin_reg = sync_live_gmail_profile()
    return {
        "primary_model": GEMINI_PRIMARY_MODEL,
        "secondary_model": GEMINI_SECONDARY_MODEL,
        "event_info": DEVFEST_EVENT_INFO,
        "gdg_korea_sheet_url": GDG_KOREA_SHEET_URL,
        "speakers": HARDCODED_SPEAKERS,
        "mail_admin": admin_reg,
        "state": state,
    }


@app.get("/api/admin/status")
def get_admin_status():
    return sync_live_gmail_profile()


@app.post("/api/admin/oauth-login")
async def admin_oauth_login(req: AdminOAuthRequest):
    """
    Launch browser OAuth 2.0 flow for the Mail Administrator account (default: devstar5011@gcplab.me)
    and register credentials + Gmail Push Watch + real-time inbox trigger.
    """
    try:
        reg = await asyncio.to_thread(
            register_mail_admin_via_oauth,
            target_email=req.target_email or DEFAULT_ADMIN_EMAIL,
            register_pubsub_watch=bool(req.register_pubsub_watch),
            sync_secret_manager=bool(req.sync_secret_manager),
            open_browser=True,
        )
        return {"status": "registered", "mail_admin": reg}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/admin/trigger/check-now")
async def admin_trigger_check_now(req: TriggerCheckRequest):
    """Immediately check INBOX for new speaker emails and fire OpsAgent clustering & Form/Calendar invite."""
    res = await asyncio.to_thread(
        check_and_trigger_on_inbound_emails,
        trigger_source="manual_dashboard_trigger",
        force_process_latest=bool(req.force_process_latest),
    )
    return res


@app.post("/api/admin/trigger/toggle")
def admin_trigger_toggle(req: TriggerToggleRequest):
    reg = load_admin_registry()
    if req.auto_trigger_enabled is not None:
        reg["auto_trigger_enabled"] = req.auto_trigger_enabled
    if req.auto_send_form_on_reply is not None:
        reg["auto_send_form_on_reply"] = req.auto_send_form_on_reply
    save_admin_registry(reg)
    return {"status": "updated", "mail_admin": reg}


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    result = await run_agent_chat(prompt=req.prompt, session_id=req.session_id)
    return result


@app.post("/api/ops/speakers")
def ops_step1_speakers():
    return get_target_speakers_tool()


@app.post("/api/ops/outreach")
def ops_step2_outreach(req: OutreachRequest):
    return generate_and_send_speaker_emails_tool(custom_context=req.custom_context or "")


@app.post("/api/ops/cluster")
def ops_step3_cluster():
    return collect_and_cluster_event_emails_tool(max_results=20)


@app.post("/api/ops/form")
def ops_step4_create_form(req: FormCreateRequest):
    return create_speaker_onboarding_form_tool(form_title=req.form_title or "")


@app.post("/api/ops/invite")
def ops_step5_invite(req: InviteRequest):
    return invite_speakers_with_form_and_calendar_tool(form_id=req.form_id or "")


@app.post("/api/ops/run-all")
def ops_run_all(req: OutreachRequest):
    return run_ops_full_workflow_tool(custom_context=req.custom_context or "")


@app.post("/gmail-webhook")
async def gmail_pubsub_webhook(request: Request):
    """Cloud Pub/Sub Push endpoint that triggers automatic Gmail collection, clustering & Form/Calendar dispatch."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    logger.info(f"Received Gmail Pub/Sub Push notification: {payload}")
    trigger_res = await asyncio.to_thread(
        check_and_trigger_on_inbound_emails,
        trigger_source="cloud_pubsub_push",
        force_process_latest=False,
    )
    clustered = collect_and_cluster_event_emails_tool(max_results=20)
    return JSONResponse(
        {
            "status": "processed",
            "trigger": "gmail_pubsub_push",
            "new_triggers_count": trigger_res.get("new_triggers_count", 0),
            "total_emails_collected": clustered["total_emails_collected"],
            "clusters": len(clustered["clusters"]),
        }
    )


@app.get("/forms/speaker-onboarding/{form_id}", response_class=HTMLResponse)
def render_speaker_onboarding_form(
    form_id: str,
    name: str = "",
    email: str = "",
    role: str = "",
    session_title: str = "",
):
    """Render an interactive Google-Forms-styled Speaker Onboarding Form."""
    state = load_runtime_state()
    form_meta = state.get("forms", {}).get(form_id) or {
        "form_id": form_id,
        "title": f"{DEVFEST_EVENT_INFO['event_tag']} 발표자 사전 정보 등록 폼 (Speaker Onboarding)",
    }
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{form_meta['title']}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
      background: #f0f4f9;
      margin: 0;
      padding: 32px 16px;
      color: #1f2937;
    }}
    .container {{
      max-width: 640px;
      margin: 0 auto;
    }}
    .banner {{
      height: 12px;
      background: linear-gradient(90deg, #4285F4 0%, #34A853 35%, #FBBC05 70%, #EA4335 100%);
      border-radius: 12px 12px 0 0;
    }}
    .card {{
      background: #fff;
      border-radius: 0 0 12px 12px;
      padding: 28px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
      margin-bottom: 18px;
    }}
    .field-card {{
      background: #fff;
      border-radius: 12px;
      padding: 22px 26px;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
      margin-bottom: 14px;
      border: 1px solid #e5e7eb;
    }}
    label {{
      display: block;
      font-weight: 600;
      margin-bottom: 10px;
      font-size: 15px;
    }}
    .req {{ color: #EA4335; margin-left: 4px; }}
    input[type="text"], input[type="email"], input[type="tel"], select, textarea {{
      width: 100%;
      box-sizing: border-box;
      padding: 11px 14px;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      font-size: 15px;
      outline: none;
    }}
    input:focus, select:focus, textarea:focus {{
      border-color: #4285F4;
      box-shadow: 0 0 0 3px rgba(66, 133, 244, 0.15);
    }}
    .submit-btn {{
      background: #1a73e8;
      color: #fff;
      border: none;
      padding: 13px 28px;
      font-size: 15px;
      font-weight: 700;
      border-radius: 8px;
      cursor: pointer;
    }}
    .submit-btn:hover {{ background: #1557b0; }}
    .badge {{
      display: inline-block;
      background: #e8f0fe;
      color: #1967d2;
      font-size: 12px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 999px;
      margin-bottom: 8px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="banner"></div>
    <div class="card">
      <span class="badge">Genmunity OpsAgent • Google ADK Form</span>
      <h1 style="margin: 6px 0 10px; font-size: 22px;">{form_meta['title']}</h1>
      <p style="margin: 0; color: #4b5563; font-size: 14px; line-height: 1.6;">
        <b>{DEVFEST_EVENT_INFO['event_name']}</b> ({DEVFEST_EVENT_INFO['event_date']}, {DEVFEST_EVENT_INFO['venue']}) 연사자 온보딩 및 현장 지원(웰컴 키트 티셔츠, 무료 주차 등록)을 위한 사전 정보 입력 폼입니다.
      </p>
    </div>

    <form method="POST" action="/forms/speaker-onboarding/{form_id}/submit">
      <div class="field-card">
        <label>1. 발표자 성함 <span class="req">*</span></label>
        <input type="text" name="speaker_name" value="{name}" placeholder="예: 한성민 / 박제창" required />
      </div>

      <div class="field-card">
        <label>2. 이메일 <span class="req">*</span></label>
        <input type="email" name="email" value="{email}" placeholder="예: sniper45han@gmail.com" required />
      </div>

      <div class="field-card">
        <label>3. 연락처 (휴대폰 번호) <span class="req">*</span></label>
        <input type="tel" name="phone" placeholder="예: 010-1234-5678" required />
      </div>

      <div class="field-card">
        <label>4. 티셔츠 사이즈 (연사 웰컴 키트) <span class="req">*</span></label>
        <select name="tshirt_size" required>
          <option value="L (100)">L (100)</option>
          <option value="S (90)">S (90)</option>
          <option value="M (95)">M (95)</option>
          <option value="XL (105)">XL (105)</option>
          <option value="2XL (110)">2XL (110)</option>
          <option value="3XL (115)">3XL (115)</option>
        </select>
      </div>

      <div class="field-card">
        <label>5. 차량 번호 (오토웨이타워 무료 주차 등록용, 미이용 시 '없음') <span class="req">*</span></label>
        <input type="text" name="vehicle_number" placeholder="예: 123가 4568 또는 없음" required />
      </div>

      <div class="field-card">
        <label>6. 연사 구분 및 핸즈온 세션 제목</label>
        <textarea name="session_title" rows="3" placeholder="발표 주제 및 요청 사항">{f"[{role}] {session_title}".strip() if (role or session_title) else ""}</textarea>
      </div>

      <button type="submit" class="submit-btn">발표자 정보 제출하기</button>
    </form>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/forms/speaker-onboarding/{form_id}/submit", response_class=HTMLResponse)
def submit_speaker_onboarding_form(
    form_id: str,
    speaker_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    tshirt_size: str = Form(...),
    vehicle_number: str = Form(...),
    session_title: str = Form(""),
):
    """Store speaker onboarding form submission and record trace in OpsAgent."""
    submission = {
        "form_id": form_id,
        "speaker_name": speaker_name,
        "email": email,
        "phone": phone,
        "tshirt_size": tshirt_size,
        "vehicle_number": vehicle_number,
        "session_title": session_title,
        "submitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    state = load_runtime_state()
    state.setdefault("form_submissions", []).append(submission)
    save_runtime_state(state)

    record_agent_trace(
        agent_name="OpsAgent",
        capability="FormSubmission",
        summary=f"발표자 온보딩 Form 응답 수신: {speaker_name} ({email}, 티셔츠 {tshirt_size}, 차량번호 {vehicle_number})",
        details=submission,
    )

    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>제출 완료 — Genmunity</title></head>
<body style="font-family: sans-serif; background: #f0f4f9; padding: 48px 16px;">
  <div style="max-width: 560px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
    <h2 style="color: #1a73e8; margin-top: 0;">발표자 사전 정보가 성공적으로 등록되었습니다!</h2>
    <p><b>성함:</b> {speaker_name}</p>
    <p><b>이메일:</b> {email}</p>
    <p><b>연락처:</b> {phone}</p>
    <p><b>티셔츠 사이즈:</b> {tshirt_size}</p>
    <p><b>차량 번호:</b> {vehicle_number}</p>
    <p><b>세션 정보:</b> {session_title}</p>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;"/>
    <a href="/" style="color:#1a73e8;font-weight:700;text-decoration:none;">← Genmunity 대시보드로 돌아가기</a>
  </div>
</body>
</html>"""
    )


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Render the interactive Genmunity Builderthon Web UI."""
    html = r"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Genmunity — CommunityHub & OpsAgent (Google ADK)</title>
  <link rel="icon" type="image/png" href="/logo.png" />
  <style>
    :root {
      --blue: #4285F4;
      --green: #34A853;
      --yellow: #FBBC05;
      --red: #EA4335;
      --bg: #0f172a;
      --card: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      background: linear-gradient(90deg, rgba(66,133,244,0.18), rgba(52,168,83,0.15), rgba(251,188,5,0.12));
      border-bottom: 1px solid var(--card-border);
      padding: 18px 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .brand-logo {
      height: 36px;
      width: auto;
      display: block;
    }
    .brand h1 { margin: 0; font-size: 21px; font-weight: 800; letter-spacing: -0.3px; }
    .brand span { font-size: 13px; color: var(--muted); }
    .pill-bar { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill {
      background: rgba(255,255,255,0.07);
      border: 1px solid var(--card-border);
      padding: 5px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
    }
    .main-grid {
      max-width: 1480px;
      margin: 0 auto;
      padding: 22px 24px 48px;
      display: grid;
      grid-template-columns: 1.15fr 1fr;
      gap: 22px;
    }
    @media (max-width: 1100px) {
      .main-grid { grid-template-columns: 1fr; }
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 20px;
      margin-bottom: 20px;
    }
    .panel-title {
      font-size: 16px;
      font-weight: 700;
      margin: 0 0 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    /* Architecture Diagram Box */
    .arch-diagram {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px;
    }
    .arch-node {
      border-radius: 10px;
      padding: 12px;
      border: 1px solid #475569;
      background: #1e293b;
    }
    .arch-node.root {
      grid-column: span 2;
      border-color: var(--blue);
      background: rgba(66, 133, 244, 0.14);
      text-align: center;
    }
    .arch-node.search {
      border-color: #eab308;
      background: rgba(251, 188, 5, 0.10);
    }
    .arch-node.ops {
      border-color: var(--green);
      background: rgba(52, 168, 83, 0.12);
    }
    .chip-list {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 8px;
    }
    .chip {
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 6px;
      background: rgba(255,255,255,0.09);
      font-weight: 600;
    }
    /* Speaker Cards */
    .speaker-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 16px;
    }
    .speaker-card {
      background: rgba(15, 23, 42, 0.65);
      border: 1px solid #3b82f6;
      border-radius: 10px;
      padding: 14px;
    }
    .speaker-card h4 { margin: 4px 0 6px; font-size: 16px; }
    .speaker-card p { margin: 3px 0; font-size: 13px; color: var(--muted); }
    /* Pipeline Steps */
    .step-card {
      background: rgba(15, 23, 42, 0.55);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 14px 16px;
      margin-bottom: 12px;
    }
    .step-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }
    .step-title { font-weight: 700; font-size: 14px; }
    .btn {
      background: var(--blue);
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      transition: opacity 0.15s;
    }
    .btn:hover { opacity: 0.9; }
    .btn.green { background: var(--green); }
    .btn.yellow { background: #d97706; }
    .btn.purple { background: #7c3aed; }
    .btn:disabled { opacity: 0.5; cursor: wait; }
    .step-output {
      margin-top: 10px;
      font-size: 13px;
      background: #0b1120;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 12px;
      max-height: 260px;
      overflow-y: auto;
      white-space: pre-wrap;
      line-height: 1.55;
      display: none;
    }
    /* Chat UI */
    .scenario-btns {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-bottom: 14px;
    }
    .scenario-btn {
      background: rgba(66, 133, 244, 0.15);
      border: 1px solid rgba(66, 133, 244, 0.4);
      color: #bfdbfe;
      padding: 7px 11px;
      border-radius: 8px;
      font-size: 12px;
      cursor: pointer;
      text-align: left;
    }
    .scenario-btn:hover { background: rgba(66, 133, 244, 0.28); }
    .chat-box {
      height: 410px;
      overflow-y: auto;
      background: #0b1120;
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 12px;
    }
    .msg {
      margin-bottom: 14px;
      padding: 12px 15px;
      border-radius: 10px;
      font-size: 14px;
      line-height: 1.6;
      white-space: pre-wrap;
    }
    .msg.user {
      background: #1d4ed8;
      margin-left: 48px;
    }
    .msg.agent {
      background: #1e293b;
      border: 1px solid #334155;
      margin-right: 24px;
    }
    .chat-input-row {
      display: flex;
      gap: 8px;
    }
    .chat-input-row input {
      flex: 1;
      background: #0b1120;
      border: 1px solid var(--card-border);
      color: #fff;
      padding: 12px 14px;
      border-radius: 8px;
      font-size: 14px;
    }
    a { color: #60a5fa; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <img src="/logo.png" alt="Genmunity Logo" class="brand-logo" />
      <div>
        <h1>Genmunity <span style="font-weight:500;color:#93c5fd;">CommunityHub & Event Ops Multi-Agent</span></h1>
        <span>Builderthon Live Demo • Powered by Google ADK, Gemini 4.0 Argon (3.8 Flash fallback), Gmail, Google Forms & Calendar</span>
      </div>
    </div>
    <div class="pill-bar">
      <span class="pill">Google ADK v2</span>
      <span class="pill">Gemini 4.0 Argon / 3.8 Flash</span>
      <span class="pill">Gmail API (Real)</span>
      <span class="pill">Form & Calendar Invite</span>
    </div>
  </header>

  <div class="main-grid">
    <!-- Left Column: Architecture + OpsAgent 5-Step Automation Pipeline -->
    <div>
      <div class="panel">
        <div class="panel-title">
          <span>Genmunity Multi-Agent Architecture (Google ADK)</span>
          <a href="https://docs.google.com/spreadsheets/d/1tC31_8IuWH-2TIeX0t84nyRI0YyaBSI52n97acG32-c/edit?usp=sharing" target="_blank" style="font-size:12px;">국내 운영진/GDE 시트 열기 ↗</a>
        </div>
        <div class="arch-diagram">
          <div class="arch-node root">
            <strong>RootAgent</strong> (ADK Entry Coordinator)
            <div style="font-size:12px;color:var(--muted);margin-top:4px;">Routes user intent & orchestrates SearchAgent ↔ OpsAgent handoff</div>
          </div>
          <div class="arch-node search">
            <strong>SearchAgent</strong>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;">Data Crawler ← CommunityHub, Slack, Advocu, GDG Sheet</div>
            <div class="chip-list">
              <span class="chip">RAGSearch</span>
              <span class="chip">SlackSearch</span>
              <span class="chip">Summarizing</span>
            </div>
          </div>
          <div class="arch-node ops">
            <strong>OpsAgent (Primary Focus)</strong>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;">Post-Planning Speaker Outreach, Email Clustering, Form & Invite</div>
            <div class="chip-list">
              <span class="chip">Gmail</span>
              <span class="chip">Calendar</span>
              <span class="chip">GenContent</span>
              <span class="chip">Form</span>
            </div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">
          <span>Mail Admin OAuth 등록 & 실시간 이메일 수신 트리거 (devstar5011@gcplab.me)</span>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn" id="btnOAuthLogin" onclick="runAdminOAuthLogin()">OAuth 로그인 & 트리거 등록 (devstar5011@gcplab.me)</button>
            <button class="btn yellow" onclick="runTriggerCheckNow(false)">수신함(INBOX) 트리거 즉시 체크</button>
            <button class="btn purple" onclick="runTriggerCheckNow(true)">최신 메일로 트리거 강제 실행</button>
          </div>
        </div>
        <div id="adminStatusBox" style="font-size:13px;background:rgba(15,23,42,0.65);border:1px solid var(--card-border);border-radius:10px;padding:12px 14px;line-height:1.6;">
          관리자 계정 상태를 확인하는 중...
        </div>
        <div id="outAdminTrigger" class="step-output"></div>
      </div>

      <div class="panel">
        <div class="panel-title">
          <span>OpsAgent — 이벤트 계획 이후 연사 운영 자동화 파이프라인</span>
          <button class="btn green" id="btnRunAll" onclick="runFullOpsPipeline()">전 과정 원클릭 실행 (Step 1~5)</button>
        </div>

        <!-- Target Speakers (Hardcoded from SearchAgent) -->
        <div class="speaker-grid">
          <div class="speaker-card">
            <span class="chip" style="background:#1d4ed8;color:#fff;">첫번째 연사자 • AI GDE</span>
            <h4>한성민 (Sungmin Han)</h4>
            <p><b>sniper45han@gmail.com</b></p>
            <p>Google ADK와 Gemini 4.0 Argon 멀티 에이전트 핸즈온 (13:30 - 15:00)</p>
          </div>
          <div class="speaker-card">
            <span class="chip" style="background:#047857;color:#fff;">두번째 연사자 • Flutter GDE</span>
            <h4>박제창 (Jechang Park)</h4>
            <p><b>aristojeff@gmail.com</b></p>
            <p>Flutter & Gemini API 크로스플랫폼 AI 앱 핸즈온 (15:20 - 16:50)</p>
          </div>
        </div>

        <!-- Step 1 -->
        <div class="step-card">
          <div class="step-header">
            <div>
              <div class="step-title">Step 1. Speaker Search 연동 확인 (한성민 AI GDE, 박제창 Flutter GDE)</div>
              <div style="font-size:12px;color:var(--muted);">SearchAgent에서 매칭된 핸즈온 연사자 2명의 프로필 및 트랙 정보를 불러옵니다.</div>
            </div>
            <button class="btn" onclick="runStep('speakers', 'outStep1')">연사 정보 조회</button>
          </div>
          <div id="outStep1" class="step-output"></div>
        </div>

        <!-- Step 2 -->
        <div class="step-card">
          <div class="step-header">
            <div>
              <div class="step-title">Step 2. Gmail 연사 섭외 메일 생성 및 발송 (GenContent + Gmail)</div>
              <div style="font-size:12px;color:var(--muted);">Gemini가 연사별 맞춤형 초청장을 작성하고 sniper45han@gmail.com, aristojeff@gmail.com 으로 실제 발송합니다.</div>
            </div>
            <button class="btn" onclick="runStep('outreach', 'outStep2')">섭외 메일 발송</button>
          </div>
          <div id="outStep2" class="step-output"></div>
        </div>

        <!-- Step 3 -->
        <div class="step-card">
          <div class="step-header">
            <div>
              <div class="step-title">Step 3. Gmail 이벤트 관련 메일 수신 확인 및 AI 클러스터링 (Gmail + GenContent)</div>
              <div style="font-size:12px;color:var(--muted);">Gmail에서 행사/연사 관련 메일을 수집하여 수신 상태를 확인하고 의미별 클러스터로 분류합니다.</div>
            </div>
            <button class="btn yellow" onclick="runStep('cluster', 'outStep3')">메일 수집 & 클러스터링</button>
          </div>
          <div id="outStep3" class="step-output"></div>
        </div>

        <!-- Step 4 -->
        <div class="step-card">
          <div class="step-header">
            <div>
              <div class="step-title">Step 4. 발표자 사전 정보 등록 Form 생성 (성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호)</div>
              <div style="font-size:12px;color:var(--muted);">발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호를 수집하는 온보딩 Form을 생성합니다.</div>
            </div>
            <button class="btn purple" onclick="runStep('form', 'outStep4')">온보딩 Form 생성</button>
          </div>
          <div id="outStep4" class="step-output"></div>
        </div>

        <!-- Step 5 -->
        <div class="step-card">
          <div class="step-header">
            <div>
              <div class="step-title">Step 5. 발표자 Form 링크 & Google Calendar 초대장(.ics) 발송 (Form + Calendar + Gmail)</div>
              <div style="font-size:12px;color:var(--muted);">두 연사자(한성민, 박제창)에게 생성된 Form 링크와 캘린더 일정 초대장을 이메일로 발송합니다.</div>
            </div>
            <button class="btn green" onclick="runStep('invite', 'outStep5')">Form + 캘린더 초대 발송</button>
          </div>
          <div id="outStep5" class="step-output"></div>
        </div>
      </div>
    </div>

    <!-- Right Column: Interactive ADK Chat & Live Demo Scenarios -->
    <div>
      <div class="panel">
        <div class="panel-title">
          <span>Genmunity ADK 에이전트 대화 & 데모 시나리오</span>
          <span style="font-size:12px;color:var(--muted);">RootAgent → SearchAgent / OpsAgent</span>
        </div>

        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">클릭하면 빌더톤 데모 시나리오 프롬프트가 즉시 실행됩니다:</div>
        <div class="scenario-btns">
          <button class="scenario-btn" onclick="sendScenario('DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어')">
            "DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어"
          </button>
          <button class="scenario-btn" onclick="sendScenario('올해 DevFest 행사는 언제까지?')">
            "올해 DevFest 행사는 언제까지?"
          </button>
          <button class="scenario-btn" onclick="sendScenario('DevFest 지원가능한 예산은?')">
            "DevFest 지원가능한 예산은?"
          </button>
          <button class="scenario-btn" onclick="sendScenario('OpsAgent를 사용해서 첫번째 연사자 한성민(sniper45han@gmail.com, AI GDE)과 두번째 연사자 박제창(aristojeff@gmail.com, Flutter GDE)에게 Gmail로 섭외 메일을 발송해줘')">
            "한성민(AI GDE), 박제창(Flutter GDE) 연사에게 Gmail 섭외 메일 발송해줘"
          </button>
          <button class="scenario-btn" onclick="sendScenario('Gmail에서 DevFest 이벤트 및 연사 관련 메일 수신 확인 후 수집해서 클러스터링 해줘')">
            "Gmail에서 이벤트 메일 수신 확인 및 수집하여 클러스터링 해줘"
          </button>
          <button class="scenario-btn" onclick="sendScenario('발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호를 입력받는 Form을 생성하고 두 연사자에게 캘린더 초대장과 함께 보내줘')">
            "발표자 정보 Form(성함/이메일/연락처/티셔츠/차량번호) 생성 및 초대장 발송해줘"
          </button>
        </div>

        <div class="chat-box" id="chatBox">
          <div class="msg agent">안녕하세요! <b>Genmunity RootAgent</b>입니다.
<b>SearchAgent</b>(스피커 매칭, DevFest 일정/예산 RAG 검색)와 <b>OpsAgent</b>(Gmail 연사 섭외 발송, 수신 메일 클러스터링, 발표자 온보딩 Form 생성 및 캘린더 초대)가 준비되어 있습니다.
위의 데모 시나리오 버튼을 클릭하거나 아래에 질문을 입력해 보세요!</div>
        </div>

        <div class="chat-input-row">
          <input type="text" id="chatInput" placeholder="예: DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어" onkeydown="if(event.key==='Enter') sendChat()" />
          <button class="btn" onclick="sendChat()">전송</button>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">
          <span>실시간 에이전트 실행 트레이스 & Form 응답 현황</span>
          <button class="btn" style="padding:4px 10px;font-size:11px;" onclick="refreshState()">새로고침</button>
        </div>
        <div id="traceBox" style="font-size:12px;color:#cbd5e1;background:#0b1120;padding:12px;border-radius:8px;max-height:240px;overflow-y:auto;white-space:pre-wrap;">에이전트 실행 로그를 불러오는 중...</div>
      </div>
    </div>
  </div>

  <script>
    let currentSessionId = null;

    function formatOutputHtml(data) {
      let jsonStr = JSON.stringify(data, null, 2);
      // Convert URLs into clickable links
      jsonStr = jsonStr.replace(/(https?:\/\/[^\s"']+)/g, '<a href="$1" target="_blank">$1</a>');
      return jsonStr;
    }

    async function runAdminOAuthLogin() {
      const btn = document.getElementById('btnOAuthLogin');
      const outEl = document.getElementById('outAdminTrigger');
      btn.disabled = true;
      btn.innerText = '브라우저 OAuth 인증 대기 중...';
      outEl.style.display = 'block';
      outEl.innerHTML = '브라우저 창에서 devstar5011@gcplab.me 계정으로 로그인해 주세요...';
      try {
        const res = await fetch('/api/admin/oauth-login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_email: 'devstar5011@gcplab.me' })
        });
        const data = await res.json();
        outEl.innerHTML = formatOutputHtml(data);
        refreshState();
      } catch (err) {
        outEl.innerHTML = '[오류 발생] ' + err;
      } finally {
        btn.disabled = false;
        btn.innerText = 'OAuth 로그인 & 트리거 등록 (devstar5011@gcplab.me)';
      }
    }

    async function runTriggerCheckNow(forceLatest) {
      const outEl = document.getElementById('outAdminTrigger');
      outEl.style.display = 'block';
      outEl.innerHTML = '관리자 수신함(INBOX)에서 신규 연사 메일 트리거를 확인 중입니다...';
      try {
        const res = await fetch('/api/admin/trigger/check-now', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ force_process_latest: forceLatest })
        });
        const data = await res.json();
        outEl.innerHTML = formatOutputHtml(data);
        refreshState();
      } catch (err) {
        outEl.innerHTML = '[오류 발생] ' + err;
      }
    }

    async function runStep(endpoint, outputId) {
      const outEl = document.getElementById(outputId);
      outEl.style.display = 'block';
      outEl.innerHTML = 'OpsAgent가 작업을 수행 중입니다...';
      try {
        const res = await fetch('/api/ops/' + endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const data = await res.json();
        outEl.innerHTML = formatOutputHtml(data);
        refreshState();
      } catch (err) {
        outEl.innerHTML = '[오류 발생] ' + err;
      }
    }

    async function runFullOpsPipeline() {
      const btn = document.getElementById('btnRunAll');
      btn.disabled = true;
      btn.innerText = 'Step 1~5 순차 실행 중...';
      try {
        await runStep('speakers', 'outStep1');
        await runStep('outreach', 'outStep2');
        await runStep('cluster', 'outStep3');
        await runStep('form', 'outStep4');
        await runStep('invite', 'outStep5');
      } finally {
        btn.disabled = false;
        btn.innerText = '전 과정 원클릭 실행 (Step 1~5)';
      }
    }

    function sendScenario(text) {
      document.getElementById('chatInput').value = text;
      sendChat();
    }

    async function sendChat() {
      const input = document.getElementById('chatInput');
      const prompt = input.value.trim();
      if (!prompt) return;
      input.value = '';

      const chatBox = document.getElementById('chatBox');
      const userDiv = document.createElement('div');
      userDiv.className = 'msg user';
      userDiv.textContent = prompt;
      chatBox.appendChild(userDiv);

      const loadingDiv = document.createElement('div');
      loadingDiv.className = 'msg agent';
      loadingDiv.textContent = 'Google ADK 에이전트(RootAgent → SearchAgent / OpsAgent)가 실행 중입니다...';
      chatBox.appendChild(loadingDiv);
      chatBox.scrollTop = chatBox.scrollHeight;

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: prompt, session_id: currentSessionId })
        });
        const data = await res.json();
        currentSessionId = data.session_id;
        const toolsInfo = (data.tool_calls || []).map(t => `[${t.agent}] ${t.tool_name}`).join(' → ');
        let headerHtml = toolsInfo ? `<div style="font-size:11px;color:#fbbf24;margin-bottom:6px;font-weight:700;">${toolsInfo}</div>` : '';
        let replyHtml = (data.reply || '').replace(/(https?:\/\/[^\s)]+)/g, '<a href="$1" target="_blank">$1</a>');
        loadingDiv.innerHTML = headerHtml + replyHtml;
        chatBox.scrollTop = chatBox.scrollHeight;
        refreshState();
      } catch (err) {
        loadingDiv.textContent = '[오류 발생] ' + err;
      }
    }

    async function refreshState() {
      try {
        const res = await fetch('/api/state');
        const data = await res.json();
        const admin = data.mail_admin || {};
        const adminBox = document.getElementById('adminStatusBox');
        if (adminBox) {
          const authEmail = admin.authenticated_email || '미인증';
          const targetEmail = admin.target_admin_email || 'devstar5011@gcplab.me';
          const isTarget = admin.is_target_admin_active;
          const badgeColor = isTarget ? '#10b981' : '#f59e0b';
          const statusLabel = isTarget
            ? '목표 메일 관리자(devstar5011@gcplab.me) 활성화됨'
            : `현재 인증 계정: ${authEmail} (목표 관리자: ${targetEmail} — OAuth 로그인 버튼 또는 python register_mail_admin.py 실행 가능)`;
          const watchInfo = admin.pubsub_watch ? admin.pubsub_watch.status : 'local_background_watcher_active';
          adminBox.innerHTML = `
            <div><b>상태:</b> <span style="color:${badgeColor};font-weight:700;">${statusLabel}</span></div>
            <div><b>수신 감시 트리거:</b> ${admin.auto_trigger_enabled ? '활성화됨 (6초 주기 INBOX 감시 + Pub/Sub Webhook)' : '비활성'} | <b>Watch 모드:</b> ${watchInfo} | <b>History ID:</b> ${admin.last_history_id || '-'}</div>
            <div style="font-size:12px;color:var(--muted);margin-top:4px;">CLI 등록 명령어: <code>.venv/bin/python register_mail_admin.py --email devstar5011@gcplab.me</code></div>
          `;
        }

        const trace = (data.state && data.state.agent_trace) || [];
        const submissions = (data.state && data.state.form_submissions) || [];
        const triggers = (admin.trigger_events) || [];
        let lines = [];
        if (triggers.length > 0) {
          lines.push('[이메일 수신 자동 트리거 실행 내역 (' + triggers.length + '건)]');
          triggers.slice().reverse().forEach(t => {
            lines.push(`  • [${t.trigger_source}] 발신: ${t.from} | 제목: ${t.subject} -> Form: ${t.onboarding_form_url || '완료'}`);
          });
          lines.push('');
        }
        if (submissions.length > 0) {
          lines.push('[제출된 발표자 Form 응답 (' + submissions.length + '건)]');
          submissions.forEach(s => {
            lines.push(`  • ${s.speaker_name} (${s.email}) | 연락처: ${s.phone} | 티셔츠: ${s.tshirt_size} | 차량번호: ${s.vehicle_number}`);
          });
          lines.push('');
        }
        lines.push('[최근 ADK 에이전트 실행 트레이스]');
        if (trace.length === 0) {
          lines.push('  • 아직 실행 기록이 없습니다.');
        } else {
          trace.slice().reverse().forEach(t => {
            lines.push(`  • [${t.agent} :: ${t.capability}] ${t.summary}`);
          });
        }
        document.getElementById('traceBox').textContent = lines.join('\\n');
      } catch (e) {}
    }

    refreshState();
    setInterval(refreshState, 6000);
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
