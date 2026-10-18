import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from genmunity_agent.config import (
    GEMINI_PRIMARY_MODEL,
    GEMINI_SECONDARY_MODEL,
    GEMINI_MODEL_CANDIDATES,
    GEMINI_IMAGE_MODEL,
    GENMUNITY_BASE_URL,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
    EVENT_MANAGER_ACCOUNT,
    EVENT_ORGANIZER_DELEGATES,
    EVENT_ORGANIZER_DELEGATE_EMAILS,
    GDG_KOREA_SHEET_URL,
    load_runtime_state,
    save_runtime_state,
    record_agent_trace,
)
from genmunity_agent.services import (
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_GCP_PROJECT,
    DEFAULT_PUBSUB_TOPIC,
    DEFAULT_PUBSUB_SUBSCRIPTION,
    UPLOADS_DIR,
    get_workspace_service,
    render_genmunity_email_html,
    load_admin_registry,
    save_admin_registry,
    sync_live_gmail_profile,
    register_mail_admin_via_oauth,
    check_and_trigger_on_inbound_emails,
    evaluate_and_handle_inbound_inquiry,
    decode_pubsub_push_payload,
    list_events,
    get_event_by_id,
    create_or_modify_event,
    save_event_wysiwyg_content,
    generate_event_image_with_gemini,
    manage_event_rsvp,
    add_event_knowledge_entry,
    analyze_event_photo_and_track_attendees,
    search_all_event_knowledge,
    sync_speaker_form_submission_to_event_state,
    get_main_event_readiness_summary,
)
from genmunity_agent.crawler import get_data_crawler
from genmunity_agent.sub_agents.ops_agent import (
    get_target_speakers_tool,
    generate_and_send_speaker_emails_tool,
    generate_and_send_sponsor_emails_tool,
    collect_and_cluster_event_emails_tool,
    create_speaker_onboarding_form_tool,
    fetch_google_form_responses_tool,
    invite_speakers_with_form_and_calendar_tool,
    run_ops_full_workflow_tool,
    handle_inbound_email_inquiry_tool,
)
from genmunity_agent.runner import (
    run_agent_chat,
    run_agent_chat_stream,
    TOOL_LABELS_KO,
    _summarize_tool_response,
    _extract_images_from_response,
)
from genmunity_agent.mcp_a2a import (
    MCP_TOOLS_CATALOG,
    execute_mcp_tool_call,
    get_a2a_agent_card,
    handle_a2a_jsonrpc,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("genmunity.app")

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo.png"
FAVICON_PNG_PATH = BASE_DIR / "assets" / "favicon.png"
FAVICON_ICO_PATH = BASE_DIR / "assets" / "favicon.ico"


def _ensure_contained_favicon_assets() -> None:
    """Ensure 1:1 square contained favicon.png and favicon.ico exist without stretching logo.png."""
    if FAVICON_PNG_PATH.exists() and FAVICON_ICO_PATH.exists():
        return
    try:
        from PIL import Image, ImageOps

        im = Image.open(LOGO_PATH).convert("RGBA")
        size = 256
        contained = ImageOps.contain(im, (size, size), method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        offset = ((size - contained.width) // 2, (size - contained.height) // 2)
        canvas.paste(contained, offset, contained)
        FAVICON_PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(FAVICON_PNG_PATH, format="PNG")
        canvas.save(FAVICON_ICO_PATH, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    except Exception as exc:
        logger.warning(f"Failed to generate contained favicon assets: {exc}")


async def _inbox_watcher_loop() -> None:
    """Background task that checks the registered Mail Admin INBOX and syncs Google Form responses."""
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
                ws = get_workspace_service()
                await asyncio.to_thread(ws.fetch_google_form_responses)
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
    title="Genmunity — Agentic CommunityHub & Event Ops Platform (Google ADK + A2A + MCP)",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/logo.png")
@app.get("/assets/logo.png")
def serve_logo():
    return FileResponse(LOGO_PATH, media_type="image/png")


@app.get("/favicon.png")
@app.get("/assets/favicon.png")
def serve_favicon_png():
    _ensure_contained_favicon_assets()
    target = FAVICON_PNG_PATH if FAVICON_PNG_PATH.exists() else LOGO_PATH
    return FileResponse(target, media_type="image/png")


@app.get("/favicon.ico")
def serve_favicon_ico():
    _ensure_contained_favicon_assets()
    if FAVICON_ICO_PATH.exists():
        return FileResponse(FAVICON_ICO_PATH, media_type="image/x-icon")
    target = FAVICON_PNG_PATH if FAVICON_PNG_PATH.exists() else LOGO_PATH
    return FileResponse(target, media_type="image/png")


@app.get("/api/uploads/{filename}")
def serve_uploaded_photo(filename: str):
    target = UPLOADS_DIR / Path(filename).name
    if target.exists():
        return FileResponse(target)
    return FileResponse(LOGO_PATH, media_type="image/png")


class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    event_id: Optional[str] = None
    image_mode: Optional[bool] = False
    image_style: Optional[str] = "Modern Minimal Tech"


class MCPBatchRequest(BaseModel):
    tools: List[Dict[str, Any]]
    session_id: Optional[str] = None
    event_id: Optional[str] = "devfest-2026-seoul"


class OutreachRequest(BaseModel):
    custom_context: Optional[str] = ""


class SponsorOutreachRequest(BaseModel):
    custom_context: Optional[str] = ""
    target_email: Optional[str] = ""
    company_name: Optional[str] = ""
    contact_name: Optional[str] = ""
    tier: Optional[str] = ""


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
    auto_inquiry_reply_enabled: Optional[bool] = None


class InboundInquiryRequest(BaseModel):
    sender_email: str
    sender_name: Optional[str] = "문의자"
    subject: str
    inquiry_body: str
    event_id: Optional[str] = "devfest-2026-seoul"
    trigger_source: Optional[str] = "pubsub_cloudrun_webhook"


class EventUpsertRequest(BaseModel):
    event_id: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    time_str: Optional[str] = None
    venue: Optional[str] = None
    status: Optional[str] = None
    capacity: Optional[int] = None
    budget: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    rsvp_content_html: Optional[str] = None
    banner_url: Optional[str] = None


class EventWysiwygRequest(BaseModel):
    rsvp_content_html: Optional[str] = None
    wysiwyg_html: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    banner_url: Optional[str] = None


class EventImageGenRequest(BaseModel):
    prompt: Optional[str] = ""
    style: Optional[str] = "Modern Minimal Tech"
    set_as_banner: Optional[bool] = True


class RSVPRequest(BaseModel):
    action: Optional[str] = "create"
    name: str
    email: Optional[str] = "attendee@gdg.kr"
    role: Optional[str] = "Developer"
    track: Optional[str] = "AI / Agentic Workflow Hands-on"
    dietary: Optional[str] = "일반"
    note: Optional[str] = ""
    status: Optional[str] = "confirmed"
    rsvp_id: Optional[str] = None


class KnowledgeCreateRequest(BaseModel):
    title: str
    content: str
    category: Optional[str] = "Event Knowledge"
    source: Optional[str] = "Organizer"


class MCPCallRequest(BaseModel):
    name: str
    arguments: Optional[Dict[str, Any]] = None


@app.get("/api/health")
def health_check():
    reg = load_admin_registry()
    return {
        "status": "ok",
        "project": "Genmunity",
        "assigned_project": DEFAULT_GCP_PROJECT,
        "framework": "Google ADK (google-adk) + A2A + MCP + Gemini + Google Workspace",
        "primary_model": GEMINI_PRIMARY_MODEL,
        "secondary_model": GEMINI_SECONDARY_MODEL,
        "image_model": GEMINI_IMAGE_MODEL,
        "model_candidates": GEMINI_MODEL_CANDIDATES,
        "agents": ["RootAgent", "SearchAgent", "OpsAgent"],
        "protocols": ["ADK", "A2A (/.well-known/agent-card.json, /a2a)", "MCP (/mcp, /api/mcp/tools)"],
        "speakers": HARDCODED_SPEAKERS,
        "organizer_delegates": EVENT_ORGANIZER_DELEGATES,
        "mail_admin": {
            "target_admin_email": reg.get("target_admin_email", DEFAULT_ADMIN_EMAIL),
            "event_manager": EVENT_MANAGER_ACCOUNT,
            "authenticated_email": reg.get("authenticated_email"),
            "is_target_admin_active": reg.get("is_target_admin_active"),
            "pubsub_topic": DEFAULT_PUBSUB_TOPIC,
            "pubsub_subscription": DEFAULT_PUBSUB_SUBSCRIPTION,
            "auto_trigger_enabled": reg.get("auto_trigger_enabled", True),
            "auto_inquiry_reply_enabled": reg.get("auto_inquiry_reply_enabled", True),
        },
    }


@app.get("/api/state")
def get_state():
    state = load_runtime_state()
    admin_reg = sync_live_gmail_profile()
    events = list_events()
    readiness = get_main_event_readiness_summary()
    crawler = get_data_crawler()
    community_hub = crawler.crawl_community_hub(force_refresh=False)
    return {
        "primary_model": GEMINI_PRIMARY_MODEL,
        "secondary_model": GEMINI_SECONDARY_MODEL,
        "image_model": GEMINI_IMAGE_MODEL,
        "assigned_project": DEFAULT_GCP_PROJECT,
        "event_manager": EVENT_MANAGER_ACCOUNT,
        "organizer_delegates": EVENT_ORGANIZER_DELEGATES,
        "event_info": DEVFEST_EVENT_INFO,
        "gdg_korea_sheet_url": GDG_KOREA_SHEET_URL,
        "speakers": crawler.crawl_speakers(),
        "readiness": readiness,
        "community_hub": community_hub,
        "mail_admin": admin_reg,
        "events": events,
        "mcp_tools": MCP_TOOLS_CATALOG,
        "state": state,
    }


# -----------------------------------------------------------------------------
# Events Gallery, Detail State, WYSIWYG RSVP, Gemini Image Gen, Photo & KB
# -----------------------------------------------------------------------------
@app.get("/api/events")
def api_list_events():
    return {"events": list_events()}


@app.get("/api/events/{event_id}")
def api_get_event(event_id: str):
    ev = get_event_by_id(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return {**ev, "event": ev}


@app.post("/api/events")
def api_create_or_modify_event(req: EventUpsertRequest):
    return create_or_modify_event(
        event_id=req.event_id,
        title=req.title,
        date=req.date,
        time_str=req.time_str,
        venue=req.venue,
        status=req.status,
        capacity=req.capacity,
        budget=req.budget,
        description=req.description,
        category=req.category,
        rsvp_content_html=req.rsvp_content_html,
        banner_url=req.banner_url,
    )


@app.post("/api/events/{event_id}/wysiwyg")
def api_save_event_wysiwyg(event_id: str, req: EventWysiwygRequest):
    return save_event_wysiwyg_content(
        event_id=event_id,
        rsvp_content_html=req.rsvp_content_html if req.rsvp_content_html is not None else (req.wysiwyg_html or ""),
        title=req.title,
        description=req.description,
        banner_url=req.banner_url,
    )


@app.post("/api/events/{event_id}/generate-image")
async def api_generate_event_image(event_id: str, req: EventImageGenRequest):
    return await asyncio.to_thread(
        generate_event_image_with_gemini,
        event_id=event_id,
        prompt=req.prompt or "",
        style=req.style or "Modern Minimal Tech",
        set_as_banner=True if req.set_as_banner is None else bool(req.set_as_banner),
    )


@app.post("/api/events/{event_id}/rsvp")
def api_manage_event_rsvp(event_id: str, req: RSVPRequest):
    return manage_event_rsvp(
        event_id=event_id,
        action=req.action or "create",
        attendee_name=req.name,
        attendee_email=req.email or "attendee@gdg.kr",
        role=req.role or "Developer",
        track=req.track or "AI / Agentic Workflow Hands-on",
        dietary=req.dietary or "일반",
        note=req.note or "",
        status=req.status or "confirmed",
        rsvp_id=req.rsvp_id,
    )


@app.post("/api/events/{event_id}/knowledge")
def api_add_event_knowledge(event_id: str, req: KnowledgeCreateRequest):
    return add_event_knowledge_entry(
        event_id=event_id,
        title=req.title,
        content=req.content,
        category=req.category or "Event Knowledge",
        source=req.source or "Organizer",
    )


@app.post("/api/events/{event_id}/photos")
async def api_upload_event_photo(
    event_id: str,
    photo: UploadFile = File(...),
    caption: str = Form(""),
):
    img_bytes = await photo.read()
    mime_type = photo.content_type or "image/jpeg"
    filename = photo.filename or "event_photo.jpg"
    res = await asyncio.to_thread(
        analyze_event_photo_and_track_attendees,
        event_id=event_id,
        image_bytes=img_bytes,
        mime_type=mime_type,
        filename=filename,
        caption=caption,
    )
    return res


# -----------------------------------------------------------------------------
# Google ADK A2A (Agent-to-Agent) & MCP (Model Context Protocol) Endpoints
# -----------------------------------------------------------------------------
@app.get("/.well-known/agent-card.json")
@app.get("/a2a/.well-known/agent-card.json")
@app.get("/api/a2a/card")
async def a2a_agent_card(request: Request):
    base_url = str(request.base_url).rstrip("/")
    card = await get_a2a_agent_card(base_url=base_url)
    return card


@app.post("/a2a")
@app.post("/a2a/rpc")
@app.post("/api/a2a")
async def a2a_jsonrpc_endpoint(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    base_url = str(request.base_url).rstrip("/")
    return await handle_a2a_jsonrpc(payload=payload, base_url=base_url)


@app.get("/api/mcp/tools")
@app.get("/mcp")
def mcp_list_tools():
    return {
        "protocol": "MCP (Model Context Protocol)",
        "server": "GenmunityRootAgent (Google ADK to_mcp_server)",
        "transport": ["streamable-http (/mcp)", "stdio (python -m genmunity_agent.mcp_a2a)"],
        "tools": MCP_TOOLS_CATALOG,
    }


@app.post("/api/mcp/call")
async def mcp_call_tool_rest(req: MCPCallRequest):
    try:
        output = await execute_mcp_tool_call(req.name, req.arguments or {})
        return {"status": "ok", "tool": req.name, "output": output}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/mcp")
async def mcp_jsonrpc_endpoint(request: Request):
    """Standard MCP JSON-RPC 2.0 HTTP endpoint supporting initialize, tools/list, and tools/call."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    req_id = body.get("id", 1)
    method = body.get("method", "tools/list")
    params = body.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "Genmunity-ADK-MCP", "version": "2.0.0"},
            },
        }
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS_CATALOG},
        }
    if method == "tools/call":
        t_name = params.get("name", "GenmunityRootAgent")
        t_args = params.get("arguments") or {}
        try:
            res = await execute_mcp_tool_call(t_name, t_args)
            import json
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res, ensure_ascii=False, indent=2)
                            if not isinstance(res, str)
                            else res,
                        }
                    ],
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                },
            }
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"tools": MCP_TOOLS_CATALOG},
    }


# -----------------------------------------------------------------------------
# Mail Admin OAuth & OpsAgent Endpoints
# -----------------------------------------------------------------------------
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
    if req.auto_inquiry_reply_enabled is not None:
        reg["auto_inquiry_reply_enabled"] = req.auto_inquiry_reply_enabled
    save_admin_registry(reg)
    return {"status": "updated", "mail_admin": reg}


@app.get("/api/admin/inquiries")
def list_inbound_inquiries():
    """Return Event Manager account info, Pub/Sub -> Cloud Run config, and inquiry auto-reply/delegation history."""
    reg = load_admin_registry()
    return {
        "assigned_project": DEFAULT_GCP_PROJECT,
        "event_manager": EVENT_MANAGER_ACCOUNT,
        "organizer_delegates": EVENT_ORGANIZER_DELEGATES,
        "pubsub_topic": DEFAULT_PUBSUB_TOPIC,
        "pubsub_subscription": DEFAULT_PUBSUB_SUBSCRIPTION,
        "inquiry_events": reg.get("inquiry_events", []),
    }


@app.post("/api/admin/inquiry/process")
async def process_inbound_inquiry_endpoint(req: InboundInquiryRequest):
    """
    Process an incoming inquiry to Event Manager devstar5011@gcplab.me (Project: kr-devsummit26icn-501):
    - If answerable via Event Knowledge Base -> Auto-Reply via Gmail (`auto_replied_from_kb`)
    - If beyond Event Knowledge Base -> Delegate via Gmail to sniper45han@gmail.com and aristojeff@gmail.com (`delegated_to_organizers`)
    """
    res = await asyncio.to_thread(
        evaluate_and_handle_inbound_inquiry,
        sender_email=req.sender_email,
        sender_name=req.sender_name or "문의자",
        subject=req.subject,
        inquiry_body=req.inquiry_body,
        event_id=req.event_id or "devfest-2026-seoul",
        trigger_source=req.trigger_source or "pubsub_cloudrun_webhook",
    )
    return res


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    prompt = req.prompt
    if req.event_id:
        ev = get_event_by_id(req.event_id)
        if ev:
            prompt = f"[현재 선택된 이벤트 컨텍스트: {ev['title']} (event_id={ev['event_id']})]\n사용자 요청: {req.prompt}"
    if req.image_mode:
        img_res = await asyncio.to_thread(
            generate_event_image_with_gemini,
            event_id=req.event_id or "devfest-2026-seoul",
            prompt=req.prompt,
            style=req.image_style or "Modern Minimal Tech",
            set_as_banner=True,
        )
        img_obj = img_res.get("image") or {}
        reply_md = (
            f"### 이벤트 키비주얼 이미지 생성 완료\n\n"
            f"- **대상 이벤트**: {img_res.get('event_title')}\n"
            f"- **프롬프트**: `{img_obj.get('prompt')}`\n"
            f"- **스타일**: `{img_obj.get('style')}` ({img_obj.get('model')})\n\n"
            f"![Generated Event Banner]({img_obj.get('url')})"
        )
        return {
            "session_id": req.session_id or "session-img",
            "model": img_obj.get("model", GEMINI_IMAGE_MODEL),
            "prompt": req.prompt,
            "reply": reply_md,
            "active_agents": ["RootAgent", "OpsAgent"],
            "tool_calls": [
                {
                    "agent": "OpsAgent",
                    "tool_name": "generate_event_image_tool",
                    "label": TOOL_LABELS_KO.get("generate_event_image_tool"),
                    "status": "completed",
                }
            ],
            "images": [img_obj] if img_obj else [],
            "events": list_events(),
        }
    result = await run_agent_chat(prompt=prompt, session_id=req.session_id)
    result["events"] = list_events()
    return result


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    import json
    import time

    if req.image_mode:
        async def _image_gen_stream():
            def _sse(payload: Dict[str, Any]) -> str:
                return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            sid = req.session_id or "session-img"
            yield _sse(
                {
                    "type": "status",
                    "session_id": sid,
                    "agent": "OpsAgent",
                    "phase": "thinking",
                    "message": "Gemini 이미지 생성 파이프라인을 준비하고 있습니다...",
                }
            )
            step_id = "step-1-generate_event_image_tool"
            t0 = time.perf_counter()
            yield _sse(
                {
                    "type": "tool_start",
                    "step_id": step_id,
                    "agent": "OpsAgent",
                    "tool_name": "generate_event_image_tool",
                    "label": TOOL_LABELS_KO["generate_event_image_tool"],
                    "args": {"prompt": req.prompt, "style": req.image_style or "Modern Minimal Tech"},
                }
            )
            img_res = await asyncio.to_thread(
                generate_event_image_with_gemini,
                event_id=req.event_id or "devfest-2026-seoul",
                prompt=req.prompt,
                style=req.image_style or "Modern Minimal Tech",
                set_as_banner=True,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            img_obj = img_res.get("image") or {}
            yield _sse(
                {
                    "type": "tool_end",
                    "step_id": step_id,
                    "agent": "OpsAgent",
                    "tool_name": "generate_event_image_tool",
                    "label": TOOL_LABELS_KO["generate_event_image_tool"],
                    "elapsed_ms": elapsed_ms,
                    "summary": f"배너 이미지 생성 완료 ({img_obj.get('url', '')})",
                }
            )
            if img_obj.get("url"):
                yield _sse({"type": "image_generated", "image": img_obj})

            reply_md = (
                f"### 이벤트 키비주얼 배너 이미지 생성 완료\n\n"
                f"요청하신 프롬프트를 바탕으로 **{img_res.get('event_title')}** 행사의 키비주얼 이미지를 생성하여 이벤트 배너에 반영했습니다.\n\n"
                f"| 항목 | 상세 내용 |\n"
                f"| --- | --- |\n"
                f"| **대상 이벤트** | {img_res.get('event_title')} (`{img_res.get('event_id')}`) |\n"
                f"| **적용 스타일** | `{img_obj.get('style')}` |\n"
                f"| **생성 모델** | `{img_obj.get('model')}` |\n"
                f"| **이미지 경로** | [{img_obj.get('url')}]({img_obj.get('url')}) |\n"
            )
            for i in range(0, len(reply_md), 18):
                yield _sse({"type": "text_delta", "delta": reply_md[i : i + 18], "agent": "OpsAgent"})
                await asyncio.sleep(0.01)

            yield _sse(
                {
                    "type": "done",
                    "session_id": sid,
                    "model": img_obj.get("model", GEMINI_IMAGE_MODEL),
                    "reply": reply_md,
                    "active_agents": ["RootAgent", "OpsAgent"],
                    "tool_calls": [
                        {
                            "step_id": step_id,
                            "agent": "OpsAgent",
                            "tool_name": "generate_event_image_tool",
                            "label": TOOL_LABELS_KO["generate_event_image_tool"],
                            "status": "completed",
                            "elapsed_ms": elapsed_ms,
                            "summary": f"배너 이미지 생성 완료 ({img_obj.get('url', '')})",
                        }
                    ],
                    "images": [img_obj] if img_obj else [],
                }
            )

        return StreamingResponse(_image_gen_stream(), media_type="text/event-stream")

    prompt = req.prompt
    if req.event_id:
        ev = get_event_by_id(req.event_id)
        if ev:
            prompt = f"[현재 선택된 이벤트 컨텍스트: {ev['title']} (event_id={ev['event_id']})]\n사용자 요청: {req.prompt}"
    return StreamingResponse(
        run_agent_chat_stream(prompt=prompt, session_id=req.session_id),
        media_type="text/event-stream",
    )


@app.post("/api/images/generate")
async def api_generate_image_direct(req: EventImageGenRequest, event_id: str = "devfest-2026-seoul"):
    res = await asyncio.to_thread(
        generate_event_image_with_gemini,
        event_id=event_id,
        prompt=req.prompt or "",
        style=req.style or "Modern Minimal Tech",
        set_as_banner=True if req.set_as_banner is None else bool(req.set_as_banner),
    )
    res["events"] = list_events()
    return res


@app.post("/api/mcp/batch-stream")
async def mcp_batch_stream_endpoint(req: MCPBatchRequest):
    """Execute one or multiple MCP tools sequentially and stream real-time progress + Markdown summary."""
    import json
    import time

    async def _batch_gen():
        def _sse(payload: Dict[str, Any]) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        sid = req.session_id or "session-mcp"
        tools_to_run = req.tools or []
        yield _sse(
            {
                "type": "status",
                "session_id": sid,
                "agent": "MCP Client -> GenmunityRootAgent",
                "phase": "thinking",
                "message": f"선택된 MCP 액션 {len(tools_to_run)}개를 순차 실행합니다...",
            }
        )

        executed_calls: List[Dict[str, Any]] = []
        generated_images: List[Dict[str, Any]] = []
        md_sections: List[str] = [f"### MCP 멀티 액션 실행 리포트 (총 {len(tools_to_run)}개 도구)\n"]

        for idx, item in enumerate(tools_to_run, start=1):
            t_name = item.get("name", "rag_search_tool")
            t_args = item.get("arguments") or {}
            label = TOOL_LABELS_KO.get(t_name, t_name)
            step_id = f"mcp-step-{idx}-{t_name}"
            t0 = time.perf_counter()

            yield _sse(
                {
                    "type": "tool_start",
                    "step_id": step_id,
                    "agent": "MCP Server",
                    "tool_name": t_name,
                    "label": label,
                    "args": t_args,
                }
            )
            try:
                res = await execute_mcp_tool_call(t_name, t_args)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                summary_str = _summarize_tool_response(t_name, res)
                imgs = _extract_images_from_response(res)
                for img in imgs:
                    generated_images.append(img)
                    yield _sse({"type": "image_generated", "image": img})

                call_record = {
                    "step_id": step_id,
                    "agent": "MCP Server",
                    "tool_name": t_name,
                    "label": label,
                    "args": t_args,
                    "status": "completed",
                    "elapsed_ms": elapsed_ms,
                    "summary": summary_str,
                }
                executed_calls.append(call_record)
                yield _sse(
                    {
                        "type": "tool_end",
                        "step_id": step_id,
                        "agent": "MCP Server",
                        "tool_name": t_name,
                        "label": label,
                        "elapsed_ms": elapsed_ms,
                        "summary": summary_str,
                    }
                )

                # Build structured Markdown section per tool
                md_sections.append(f"#### {idx}. {label} (`{t_name}`)\n- **상태**: 완료 (`{elapsed_ms}ms`) — {summary_str}")
                if isinstance(res, dict):
                    if res.get("recommended_speakers") or res.get("speakers"):
                        sp_list = res.get("recommended_speakers") or res.get("speakers") or []
                        for sp in sp_list:
                            md_sections.append(f"  - **{sp.get('name')}** (`{sp.get('email')}`, {sp.get('role')}): {sp.get('proposed_topic')}")
                    if res.get("outreach_results"):
                        for r in res["outreach_results"]:
                            md_sections.append(f"  - 수신자: `{r.get('speaker_email')}` | 제목: {r.get('subject')} | 상태: `{r.get('delivery', {}).get('status')}`")
                    if res.get("sponsor_outreach_results"):
                        for r in res["sponsor_outreach_results"]:
                            md_sections.append(f"  - 후원사: **{r.get('company_name')}** (`{r.get('sponsor_email')}`, {r.get('tier')}) | 상태: `{r.get('delivery', {}).get('status')}`")
                    if res.get("clusters"):
                        for c in res["clusters"]:
                            md_sections.append(f"  - 클러스터 **{c.get('cluster_name')}** ({c.get('email_count')}건): {c.get('key_insights')}")
                    if res.get("primary_form_url"):
                        md_sections.append(f"  - **생성된 온보딩 Form 링크**: [{res['primary_form_url']}]({res['primary_form_url']})")
                    if res.get("invites_sent"):
                        for inv in res["invites_sent"]:
                            md_sections.append(f"  - 캘린더(.ics) & Form 발송: **{inv.get('speaker_name')}** (`{inv.get('speaker_email')}`)")
                    if res.get("rsvp"):
                        rv = res["rsvp"]
                        md_sections.append(f"  - 참가자: **{rv.get('name')}** (`{rv.get('email')}`) | 트랙: {rv.get('track')} | 누적 RSVP: {res.get('total_rsvp_count')}명")
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                yield _sse(
                    {
                        "type": "tool_end",
                        "step_id": step_id,
                        "agent": "MCP Server",
                        "tool_name": t_name,
                        "label": label,
                        "elapsed_ms": elapsed_ms,
                        "summary": f"오류: {exc}",
                    }
                )
                md_sections.append(f"#### {idx}. {label} (`{t_name}`)\n- **오류**: `{exc}`")

        final_md = "\n".join(md_sections)
        for i in range(0, len(final_md), 20):
            yield _sse({"type": "text_delta", "delta": final_md[i : i + 20], "agent": "MCP Server"})
            await asyncio.sleep(0.01)

        yield _sse(
            {
                "type": "done",
                "session_id": sid,
                "model": GEMINI_PRIMARY_MODEL,
                "reply": final_md,
                "active_agents": ["RootAgent", "MCP Server"],
                "tool_calls": executed_calls,
                "images": generated_images,
            }
        )

    return StreamingResponse(_batch_gen(), media_type="text/event-stream")


@app.post("/api/ops/speakers")
def ops_step1_speakers():
    return get_target_speakers_tool()


@app.post("/api/ops/outreach")
def ops_step2_outreach(req: OutreachRequest):
    return generate_and_send_speaker_emails_tool(custom_context=req.custom_context or "")


@app.post("/api/ops/sponsor-outreach")
def ops_sponsor_outreach(req: SponsorOutreachRequest):
    return generate_and_send_sponsor_emails_tool(
        custom_context=req.custom_context or "",
        target_email=req.target_email or "",
        company_name=req.company_name or "",
        contact_name=req.contact_name or "",
        tier=req.tier or "",
    )


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


class FormSubmissionJsonRequest(BaseModel):
    form_id: Optional[str] = ""
    speaker_name: str
    email: str
    phone: Optional[str] = "010-9123-4567"
    tshirt_size: Optional[str] = "XL (105)"
    vehicle_number: Optional[str] = "123가 4567"
    session_title: Optional[str] = ""
    source: Optional[str] = "google_forms_sync"


@app.post("/api/ops/form/sync")
def ops_sync_form_responses():
    """Fetch responses from Google Forms API v1 + local submissions and sync into main event state."""
    res = fetch_google_form_responses_tool()
    readiness = get_main_event_readiness_summary()
    return {
        "status": "synced",
        "form_responses": res,
        "readiness": readiness,
        "events": list_events(),
    }


@app.post("/api/ops/form/submit-json")
def ops_submit_form_json(req: FormSubmissionJsonRequest):
    """Synchronize a speaker's Google Form response directly into main event state and return updated readiness."""
    sync_res = sync_speaker_form_submission_to_event_state(
        {
            "form_id": req.form_id or None,
            "speaker_name": req.speaker_name,
            "email": req.email,
            "phone": req.phone,
            "tshirt_size": req.tshirt_size,
            "vehicle_number": req.vehicle_number,
            "session_title": req.session_title,
            "source": req.source or "google_forms_sync",
        }
    )
    return {
        "status": "synced",
        "sync_result": sync_res,
        "readiness": get_main_event_readiness_summary(),
        "events": list_events(),
    }


@app.get("/api/ops/email-preview")
def ops_email_preview(email_type: str = "outreach", speaker_order: int = 1):
    """Render the Genmunity Email Design System HTML preview for outreach, onboarding_invite, inquiry_reply, or delegation."""
    sp = HARDCODED_SPEAKERS[0] if speaker_order == 1 else HARDCODED_SPEAKERS[1]
    state = load_runtime_state()
    latest_form = state.get("latest_form") or {}
    form_url = (
        latest_form.get("google_form_url")
        or latest_form.get("primary_form_url")
        or DEVFEST_EVENT_INFO.get(
            "default_google_form_url",
            "https://docs.google.com/forms/d/e/1FAIpQLSeVYvU9nyRQmdhYgLIO2IwFc7PCZCAd-O43Rl-ltWyvhm8tjA/viewform",
        )
    )
    if not str(form_url).startswith("https://docs.google.com/forms/"):
        form_url = DEVFEST_EVENT_INFO.get(
            "default_google_form_url",
            "https://docs.google.com/forms/d/e/1FAIpQLSeVYvU9nyRQmdhYgLIO2IwFc7PCZCAd-O43Rl-ltWyvhm8tjA/viewform",
        )
    cal_invites = state.get("calendar_invites") or []
    sp_cal = next(
        (c for c in reversed(cal_invites) if (c.get("speaker_email") or "").lower() == sp["email"].lower()),
        {},
    )
    cal_link = sp_cal.get("calendar_html_link") or "https://calendar.google.com/calendar/r"
    meet_link = sp_cal.get("google_meet_link")

    if email_type == "onboarding_invite":
        subject = f"{DEVFEST_EVENT_INFO['event_tag']} [연사 초대 및 사전 정보 등록] {sp['name']} {sp['role']}님 Google Form 및 Google Calendar 초대장"
        body_text = (
            f"안녕하세요 {sp['name']} {sp['role']}님 ({sp['order_label']}),\n\n"
            f"{DEVFEST_EVENT_INFO['event_name']} 연사로 함께해 주셔서 진심으로 감사드립니다!\n"
            f"원활한 현장 운영과 연사 웰컴 키트 제작, 당일 무료 주차 등록을 위해 아래 발표자 사전 정보 등록 Google Form 작성을 부탁드립니다.\n\n"
            f"■ 발표자 사전 정보 입력 Google Form 링크\n"
            f"- {form_url}\n\n"
            f"■ 필수 입력 항목 안내\n"
            f"1. 발표자 성함: {sp['name']}\n"
            f"2. 이메일: {sp['email']}\n"
            f"3. 연락처: 행사 당일 비상 연락용 휴대폰 번호\n"
            f"4. 티셔츠 사이즈: 연사 전용 웰컴 티셔츠 사이즈 (S / M / L / XL / 2XL / 3XL)\n"
            f"5. 차량 번호: 오토웨이타워 무료 주차 사전 등록용 차량 번호 (자차 미이용 시 '없음' 기재)\n"
            f"6. 핸즈온 세션 제목: {sp['proposed_topic']}\n\n"
            f"■ Google Calendar 공식 일정 등록 안내\n"
            f"- 일시: {DEVFEST_EVENT_INFO['event_date']} ({sp['session_time']})\n"
            f"- 장소: {DEVFEST_EVENT_INFO['venue']}\n"
            f"- Google Calendar 일정 링크: {cal_link}\n\n"
            f"감사합니다.\nGDG Korea DevFest 2026 운영팀 (Genmunity OpsAgent) 드림"
        )
    elif email_type == "inquiry_reply":
        subject = f"Re: {DEVFEST_EVENT_INFO['event_tag']} [자동 회신] 행사 장소, 무료 주차 등록 및 연사자 라인업 안내"
        body_text = (
            "안녕하세요 문의자님,\n\n"
            "GDG DevFest 2026 행사 담당자 Star Developer 5011 (devstar5011@gcplab.me) 입니다.\n"
            "문의해 주신 내용은 Genmunity 행사 지식 베이스(Event Knowledge Base)에서 확인되어 아래와 같이 안내드립니다.\n\n"
            "■ 행사 장소 및 일정 안내\n"
            f"- 행사명: {DEVFEST_EVENT_INFO['event_name']}\n"
            f"- 일시: {DEVFEST_EVENT_INFO['event_date']} (13:00 - 18:00 KST)\n"
            f"- 장소: {DEVFEST_EVENT_INFO['venue']}\n"
            "- 주차 지원: 연사 및 사전 등록 차량 대상 오토웨이타워 지하 주차장 무료 등록 지원\n\n"
            "■ 핸즈온 연사자 라인업\n"
            "- 첫번째 연사자: 한성민 (AI GDE) — Google ADK & Gemini 4.0 Argon 멀티 에이전트 핸즈온\n"
            "- 두번째 연사자: 박제창 (Flutter GDE) — Flutter & Gemini 크로스플랫폼 AI 앱 핸즈온\n\n"
            "감사합니다.\nGenmunity OpsAgent 드림"
        )
        form_url = None
        cal_link = None
    elif email_type == "delegation":
        subject = f"{DEVFEST_EVENT_INFO['event_tag']} [문의 딜리게이션/이관] 지식 베이스 초과 특례 문의 검토 요청"
        body_text = (
            f"안녕하세요 {sp['name']} ({sp['role']}) 총괄 운영자님,\n\n"
            "행사 담당자 계정(devstar5011@gcplab.me / Assigned Project: kr-devsummit26icn-501)으로 수신된 문의가 "
            "기본 행사 지식 베이스(Knowledge Base) 범위를 넘어서서 운영진 두 분(sniper45han@gmail.com, aristojeff@gmail.com)께 이관되었습니다.\n\n"
            "■ 문의자 및 이관 사유\n"
            "- 발신자: 박이사 <sponsor.director@techcorp.kr>\n"
            "- 원 제목: [특례 문의] 기업 단독 스폰서십 계약 체결, 세금계산서 선발행 및 야간 대관 연장 요청\n"
            "- 수신 경로: Cloud Pub/Sub (gmail-push-topic) -> Cloud Run (/gmail-webhook)\n"
            "- 이관 사유: 기업 스폰서십 NDA 계약 및 대관 시간 연장 특례는 운영진 직접 승인이 필요합니다.\n\n"
            "감사합니다.\nGenmunity OpsAgent (Star Developer 5011 / devstar5011@gcplab.me)"
        )
        form_url = None
        cal_link = None
    else:
        subject = f"{DEVFEST_EVENT_INFO['event_tag']} {sp['name']} {sp['role']}님, 핸즈온 세션({sp['order_label']}) 연사 초청의 건"
        body_text = (
            f"안녕하세요 {sp['name']} {sp['role']}님,\n\n"
            f"GDG Korea CommunityHub & DevFest 2026 운영팀(Genmunity OpsAgent)입니다.\n"
            f"다가오는 {DEVFEST_EVENT_INFO['event_date']}에 {DEVFEST_EVENT_INFO['venue']}에서 개최되는 '{DEVFEST_EVENT_INFO['event_name']}' 행사의 "
            f"[{sp['order_label']} - {sp['track']}] 트랙 연사로 {sp['name']}님을 정중히 모시고자 연락드렸습니다.\n\n"
            f"■ 행사 및 세션 안내\n"
            f"- 행사명: {DEVFEST_EVENT_INFO['event_name']}\n"
            f"- 일시: {DEVFEST_EVENT_INFO['event_date']} ({sp['session_time']})\n"
            f"- 장소: {DEVFEST_EVENT_INFO['venue']}\n"
            f"- 초청 구분: {sp['order_label']} ({sp['role']})\n"
            f"- 제안 세션 주제: {sp['proposed_topic']}\n\n"
            f"참석 및 발표 가능 여부를 본 메일의 답장으로 회신해 주시면, "
            f"발표자 사전 정보 입력 Google Form(성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호)과 "
            f"Google Calendar 공식 초대장을 곧바로 발송해 드리겠습니다.\n\n"
            f"감사합니다.\nGDG Korea DevFest 2026 운영팀 드림"
        )
        form_url = None
        cal_link = None

    html_rendered = render_genmunity_email_html(
        subject=subject,
        body_text=body_text,
        email_type=email_type,
        speaker=sp,
        form_url=form_url,
        calendar_link=cal_link,
        meet_link=meet_link,
    )
    return {
        "email_type": email_type,
        "speaker": sp,
        "subject": subject,
        "html": html_rendered,
    }


@app.get("/api/community-hub")
def api_get_community_hub(force_refresh: bool = False):
    crawler = get_data_crawler()
    return crawler.crawl_community_hub(force_refresh=force_refresh)


@app.post("/api/community-hub/crawl")
async def api_crawl_community_hub():
    crawler = get_data_crawler()
    hub = await asyncio.to_thread(crawler.crawl_community_hub, True)
    record_agent_trace(
        agent_name="SearchAgent",
        capability="CommunityHubLiveScrape",
        summary=(
            f"Google CommunityHub ({hub.get('hub_url')}) 쿠키 인증 라이브 스크래핑 완료 "
            f"(페이지 {len(hub.get('pages', []))}개, 쿠키 {hub.get('cookie_count', 0)}개)"
        ),
        details={"status": hub.get("status"), "scraped_at": hub.get("scraped_at")},
    )
    return hub


@app.post("/gmail-webhook")
@app.post("/pubsub/gmail-inquiry")
async def gmail_pubsub_webhook(request: Request):
    """
    Cloud Pub/Sub -> Cloud Run Push endpoint (`projects/kr-devsummit26icn-501/topics/gmail-push-topic`).
    When an email arrives at Event Manager `devstar5011@gcplab.me` (Star Developer 5011):
    1. Decodes the Cloud Pub/Sub Push payload (`message.data` base64 JSON or direct inquiry payload).
    2. If the Pub/Sub message contains an inquiry payload (`sender_email`, `subject`, `inquiry_body`/`body`),
       evaluates it against the Event Knowledge Base to auto-reply (`auto_replied_from_kb`) or delegate
       out-of-KB inquiries to `sniper45han@gmail.com` and `aristojeff@gmail.com` (`delegated_to_organizers`).
    3. Also checks the live Gmail INBOX of `devstar5011@gcplab.me` and runs clustering & onboarding triggers.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    logger.info(f"Received Gmail Pub/Sub -> Cloud Run Push notification: {payload}")

    pubsub_meta = decode_pubsub_push_payload(payload)
    decoded = pubsub_meta.get("decoded_data") or {}

    direct_inquiry_result = None
    if decoded.get("sender_email") and (decoded.get("subject") or decoded.get("inquiry_body") or decoded.get("body")):
        direct_inquiry_result = await asyncio.to_thread(
            evaluate_and_handle_inbound_inquiry,
            sender_email=decoded["sender_email"],
            sender_name=decoded.get("sender_name", "문의자"),
            subject=decoded.get("subject", "DevFest 행사 문의"),
            inquiry_body=decoded.get("inquiry_body") or decoded.get("body") or "",
            event_id=decoded.get("event_id", "devfest-2026-seoul"),
            trigger_source="cloud_pubsub_push_cloudrun",
        )

    trigger_res = await asyncio.to_thread(
        check_and_trigger_on_inbound_emails,
        trigger_source="cloud_pubsub_push_cloudrun",
        force_process_latest=False,
    )
    clustered = collect_and_cluster_event_emails_tool(max_results=20)
    return JSONResponse(
        {
            "status": "processed",
            "trigger": "gmail_pubsub_push_cloudrun",
            "assigned_project": DEFAULT_GCP_PROJECT,
            "event_manager": EVENT_MANAGER_ACCOUNT["email"],
            "pubsub_topic": DEFAULT_PUBSUB_TOPIC,
            "pubsub_message_id": pubsub_meta.get("pubsub_message_id"),
            "direct_inquiry_result": direct_inquiry_result,
            "new_triggers_count": trigger_res.get("new_triggers_count", 0),
            "inquiry_results": trigger_res.get("inquiry_results", []),
            "total_emails_collected": clustered["total_emails_collected"],
            "clusters": len(clustered["clusters"]),
        }
    )


@app.get("/forms/speaker-onboarding/{form_id}")
def render_speaker_onboarding_form(
    form_id: str,
    name: str = "",
    email: str = "",
    role: str = "",
    session_title: str = "",
):
    """Redirect any legacy /forms/speaker-onboarding/{form_id} request directly to the real Google Form (docs.google.com/forms)."""
    from fastapi.responses import RedirectResponse
    from urllib.parse import urlencode

    base_gf_url = DEVFEST_EVENT_INFO.get(
        "default_google_form_url",
        "https://docs.google.com/forms/d/e/1FAIpQLSeVYvU9nyRQmdhYgLIO2IwFc7PCZCAd-O43Rl-ltWyvhm8tjA/viewform",
    )
    gf_params = {"usp": "pp_url"}
    if name:
        gf_params["entry.1854756518"] = name
    if email:
        gf_params["entry.565900156"] = email
    if session_title or role:
        gf_params["entry.2024692064"] = f"[{role}] {session_title}".strip() if role else session_title
    target_gf_url = f"{base_gf_url}?{urlencode(gf_params)}" if len(gf_params) > 1 else base_gf_url
    return RedirectResponse(url=target_gf_url, status_code=302)


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
    """Store speaker onboarding form submission and synchronize into main Genmunity event state."""
    sync_res = sync_speaker_form_submission_to_event_state(
        {
            "form_id": form_id,
            "speaker_name": speaker_name,
            "email": email,
            "phone": phone,
            "tshirt_size": tshirt_size,
            "vehicle_number": vehicle_number,
            "session_title": session_title,
            "source": "genmunity_onboarding_form",
            "submitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    )
    sub = sync_res["submission"]

    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>제출 완료 — Genmunity</title><link rel="icon" type="image/png" sizes="256x256" href="/favicon.png" /><link rel="icon" type="image/x-icon" href="/favicon.ico" /></head>
<body style="font-family: 'Plus Jakarta Sans', 'Pretendard', sans-serif; background: #f8fafc; padding: 48px 16px;">
  <div style="max-width: 580px; margin: 0 auto; background: #fff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 10px 30px rgba(15,23,42,0.06);">
    <div style="height: 6px; background: linear-gradient(90deg, #4285F4 0%, #34A853 35%, #FBBC05 70%, #EA4335 100%);"></div>
    <div style="padding: 32px;">
      <span style="display:inline-block;padding:4px 10px;border-radius:999px;background:#dcfce7;color:#166534;font-size:12px;font-weight:700;margin-bottom:10px;">
        Genmunity 메인 이벤트 상태 동기화 완료 ({sync_res['completed_speakers']}/{sync_res['total_speakers']}명 확정)
      </span>
      <h2 style="color: #0f172a; margin: 0 0 16px; font-size: 22px;">발표자 사전 정보가 성공적으로 등록되었습니다!</h2>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;font-size:14px;line-height:1.8;">
        <div><b>발표자 성함:</b> {sub['speaker_name']} ({sub['speaker_role']})</div>
        <div><b>이메일:</b> {sub['email']}</div>
        <div><b>연락처:</b> {sub['phone']}</div>
        <div><b>티셔츠 사이즈 (웰컴 키트):</b> {sub['tshirt_size']}</div>
        <div><b>차량 번호 (무료 주차 등록):</b> {sub['vehicle_number']}</div>
        <div><b>핸즈온 세션 제목:</b> {sub['session_title']}</div>
      </div>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:22px 0;"/>
      <a href="/" style="display:inline-block;padding:11px 20px;background:#2563eb;color:#ffffff;border-radius:10px;font-weight:700;text-decoration:none;font-size:14px;">← Genmunity 운영 콘솔로 돌아가기</a>
    </div>
  </div>
</body>
</html>"""
    )


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Render the Genmunity Operations Console Web Application."""
    import importlib
    import genmunity_agent.ui_template as _ui_template
    importlib.reload(_ui_template)
    return HTMLResponse(content=_ui_template.DASHBOARD_HTML)

