"""
Google ADK A2A (Agent-to-Agent) & MCP (Model Context Protocol) Server Exposure for Genmunity.

Exposes:
1. A2A Protocol:
   - Uses Google ADK's `AgentCardBuilder` and `to_a2a` (`google.adk.a2a.utils.agent_to_a2a`)
   - Serves `/.well-known/agent-card.json` (and `/a2a/.well-known/agent-card.json`)
   - Serves A2A JSON-RPC 2.0 endpoint (`POST /a2a` and `POST /a2a/rpc`) for external agents (`message/send`, `tasks/send`, `agent/authenticatedExtendedCard`)
2. MCP Server (Model Context Protocol):
   - Uses Google ADK's `to_mcp_server` (`google.adk.tools.mcp_tool._agent_to_mcp`) + `FastMCP`
   - Exposes all Genmunity tools (`RootAgent`, `SearchAgent`, `OpsAgent`, `EventHub`, `PhotoAttendeeTracker`, `RSVP`, `KnowledgeBase`)
   - Supports MCP JSON-RPC 2.0 (`tools/list`, `tools/call`, `initialize`) over HTTP (`/mcp`) and stdio (`python -m genmunity_agent.mcp_a2a`).
"""
import uuid
import logging
from typing import Dict, Any, List, Optional

from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.tools.mcp_tool._agent_to_mcp import to_mcp_server

from genmunity_agent.agent import root_agent
from genmunity_agent.sub_agents.search_agent import (
    search_agent,
    rag_search_tool,
    search_event_knowledge_base_tool,
    slack_search_tool,
    summarize_community_data_tool,
)
from genmunity_agent.sub_agents.ops_agent import (
    ops_agent,
    get_target_speakers_tool,
    generate_and_send_speaker_emails_tool,
    generate_and_send_sponsor_emails_tool,
    collect_and_cluster_event_emails_tool,
    create_speaker_onboarding_form_tool,
    invite_speakers_with_form_and_calendar_tool,
    run_ops_full_workflow_tool,
    check_email_receive_trigger_tool,
    handle_inbound_email_inquiry_tool,
    manage_event_rsvp_tool,
    create_or_modify_event_tool,
    generate_event_image_tool,
    add_event_knowledge_tool,
)
from genmunity_agent.runner import run_agent_chat
from genmunity_agent.config import GENMUNITY_BASE_URL

logger = logging.getLogger("genmunity.mcp_a2a")

_cached_agent_card_dict: Optional[Dict[str, Any]] = None


def build_mcp_server():
    """Build the FastMCP server exposing RootAgent and all Genmunity tools via Google ADK."""
    mcp_srv = to_mcp_server(
        root_agent,
        name="GenmunityRootAgent",
        instructions=(
            "Genmunity Multi-Agent MCP Server (Google ADK). "
            "Provides CommunityHub Speaker Search, DevFest Schedule/Budget RAG, "
            "OpsAgent Gmail Speaker & Sponsor Outreach/Clustering/Onboarding Form/Calendar Invite, "
            "Pub/Sub -> Cloud Run Inbound Inquiry KB Auto-Reply & Organizer Delegation (sniper45han@gmail.com, aristojeff@gmail.com), "
            "Event RSVP Management, Gemini Image Generation, and Gemini Vision Photo Attendee Tracking."
        ),
    )
    # Register granular tools on the FastMCP server so external MCP clients can call either RootAgent or specific tools
    mcp_srv.add_tool(rag_search_tool, name="rag_search_tool", description="Search CommunityHub, Advocu, GDG Sheet, and Event Knowledge Base.")
    mcp_srv.add_tool(search_event_knowledge_base_tool, name="search_event_knowledge_base_tool", description="Search Event Knowledge Base and Gemini Vision photo attendee stats.")
    mcp_srv.add_tool(slack_search_tool, name="slack_search_tool", description="Search GDG/GDE Slack threads.")
    mcp_srv.add_tool(get_target_speakers_tool, name="get_target_speakers_tool", description="Get matched DevFest speakers (한성민 AI GDE, 박제창 Flutter GDE).")
    mcp_srv.add_tool(generate_and_send_speaker_emails_tool, name="generate_and_send_speaker_emails_tool", description="Generate and send speaker invitation emails via Gmail.")
    mcp_srv.add_tool(generate_and_send_sponsor_emails_tool, name="generate_and_send_sponsor_emails_tool", description="Generate and send sponsor sponsorship proposal emails via Gmail.")
    mcp_srv.add_tool(collect_and_cluster_event_emails_tool, name="collect_and_cluster_event_emails_tool", description="Collect and cluster event-related Gmail threads.")
    mcp_srv.add_tool(create_speaker_onboarding_form_tool, name="create_speaker_onboarding_form_tool", description="Create Speaker Onboarding Form (name, email, phone, t-shirt, vehicle number).")
    mcp_srv.add_tool(invite_speakers_with_form_and_calendar_tool, name="invite_speakers_with_form_and_calendar_tool", description="Send Onboarding Form link and .ics Calendar invite to speakers.")
    mcp_srv.add_tool(handle_inbound_email_inquiry_tool, name="handle_inbound_email_inquiry_tool", description="Auto-reply to inbound event inquiries from Event Knowledge Base or delegate out-of-KB inquiries to sniper45han@gmail.com and aristojeff@gmail.com.")
    mcp_srv.add_tool(manage_event_rsvp_tool, name="manage_event_rsvp_tool", description="Create, modify, or cancel an event RSVP.")
    mcp_srv.add_tool(create_or_modify_event_tool, name="create_or_modify_event_tool", description="Create or modify a GDG/DevFest event.")
    mcp_srv.add_tool(generate_event_image_tool, name="generate_event_image_tool", description="Generate an event banner or RSVP illustration using Gemini Image Generation.")
    mcp_srv.add_tool(add_event_knowledge_tool, name="add_event_knowledge_tool", description="Add an entry to the Event Knowledge Base.")
    return mcp_srv


def build_a2a_starlette_app(base_url: str = GENMUNITY_BASE_URL):
    """Build an ADK A2A Starlette sub-application using `google.adk.a2a.utils.agent_to_a2a.to_a2a`."""
    return to_a2a(root_agent, rpc_path="")


async def get_a2a_agent_card(base_url: str = GENMUNITY_BASE_URL) -> Dict[str, Any]:
    """Build and return the Google ADK A2A AgentCard JSON dictionary."""
    global _cached_agent_card_dict
    rpc_url = f"{base_url.rstrip('/')}/a2a"
    if _cached_agent_card_dict is not None:
        card_copy = dict(_cached_agent_card_dict)
        card_copy["url"] = rpc_url
        return card_copy

    card_dict = {
        "name": "RootAgent",
        "description": root_agent.description,
        "url": rpc_url,
        "version": "1.0.0",
        "protocolVersion": "0.3.0",
        "capabilities": {"streaming": False, "pushNotifications": True},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "subAgents": ["SearchAgent", "OpsAgent"],
        "skills": [
            {
                "id": "search_agent_rag",
                "name": "SearchAgent (CommunityHub, Slack, Advocu & Event Knowledge Base RAG)",
                "description": search_agent.description,
                "tags": ["RAGSearch", "SlackSearch", "Summarizing", "EventKnowledgeBase"],
            },
            {
                "id": "ops_agent_automation",
                "name": "OpsAgent (Gmail Outreach, Clustering, Google Forms, Google Calendar, RSVP & Vision)",
                "description": ops_agent.description,
                "tags": ["Gmail", "Calendar", "GenContent", "Form", "RSVP", "GeminiVision"],
            },
        ],
    }
    _cached_agent_card_dict = card_dict
    return card_dict


MCP_TOOLS_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "GenmunityRootAgent",
        "description": "Run the full Google ADK Genmunity RootAgent (coordinates SearchAgent & OpsAgent via natural language).",
        "inputSchema": {
            "type": "object",
            "properties": {"request": {"type": "string", "description": "Natural language instruction for RootAgent"}},
            "required": ["request"],
        },
    },
    {
        "name": "rag_search_tool",
        "description": "[SearchAgent] Search CommunityHub, Advocu, GDG Korea Sheet, and Event Knowledge Base for speakers, schedule, budget, and photo attendee counts.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
    {
        "name": "search_event_knowledge_base_tool",
        "description": "[SearchAgent] Search event knowledge base entries, RSVP counts, and Gemini Vision photo attendee tracking stats.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Keyword or event ID"}},
        },
    },
    {
        "name": "get_target_speakers_tool",
        "description": "[OpsAgent] Retrieve matched DevFest Hands-on speakers (1st: 한성민 AI GDE sniper45han@gmail.com, 2nd: 박제창 Flutter GDE aristojeff@gmail.com).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "generate_and_send_speaker_emails_tool",
        "description": "[OpsAgent] Generate personalized speaker invitation emails with Gemini and send via Gmail API.",
        "inputSchema": {
            "type": "object",
            "properties": {"custom_context": {"type": "string"}},
        },
    },
    {
        "name": "generate_and_send_sponsor_emails_tool",
        "description": "[OpsAgent] Generate personalized sponsor sponsorship proposal emails with Gemini and send via Gmail API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "custom_context": {"type": "string"},
                "target_email": {"type": "string"},
                "company_name": {"type": "string"},
                "contact_name": {"type": "string"},
                "tier": {"type": "string"},
            },
        },
    },
    {
        "name": "collect_and_cluster_event_emails_tool",
        "description": "[OpsAgent] Collect event-related emails from Gmail and cluster them semantically with Gemini.",
        "inputSchema": {
            "type": "object",
            "properties": {"max_results": {"type": "integer", "default": 20}},
        },
    },
    {
        "name": "create_speaker_onboarding_form_tool",
        "description": "[OpsAgent] Create Speaker Onboarding Form (발표자 성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호).",
        "inputSchema": {
            "type": "object",
            "properties": {"form_title": {"type": "string"}},
        },
    },
    {
        "name": "invite_speakers_with_form_and_calendar_tool",
        "description": "[OpsAgent] Send Speaker Onboarding Form link and Google Calendar (.ics) invite to speakers.",
        "inputSchema": {
            "type": "object",
            "properties": {"form_id": {"type": "string"}},
        },
    },
    {
        "name": "manage_event_rsvp_tool",
        "description": "[OpsAgent] Create, modify, or cancel an attendee RSVP for any GDG/DevFest event.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "attendee_name": {"type": "string"},
                "attendee_email": {"type": "string"},
                "event_id": {"type": "string", "default": "devfest-2026-seoul"},
                "action": {"type": "string", "enum": ["create", "modify", "cancel"], "default": "create"},
                "role": {"type": "string"},
                "track": {"type": "string"},
                "dietary": {"type": "string"},
            },
            "required": ["attendee_name"],
        },
    },
    {
        "name": "create_or_modify_event_tool",
        "description": "[OpsAgent] Create a new community event or modify an existing event.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "event_id": {"type": "string"},
                "date": {"type": "string"},
                "venue": {"type": "string"},
                "status": {"type": "string"},
                "capacity": {"type": "integer"},
                "budget": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "add_event_knowledge_tool",
        "description": "[OpsAgent / SearchAgent] Add a new entry to an event's Knowledge Base.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "event_id": {"type": "string", "default": "devfest-2026-seoul"},
                "category": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "handle_inbound_email_inquiry_tool",
        "description": "[OpsAgent] Evaluate an inbound email inquiry to devstar5011@gcplab.me (Project: kr-devsummit26icn-501). Auto-replies using the Event Knowledge Base or delegates out-of-KB inquiries to sniper45han@gmail.com and aristojeff@gmail.com.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sender_email": {"type": "string", "description": "Sender email address"},
                "sender_name": {"type": "string", "description": "Sender name"},
                "subject": {"type": "string", "description": "Inquiry email subject"},
                "inquiry_body": {"type": "string", "description": "Inquiry email body"},
                "event_id": {"type": "string", "default": "devfest-2026-seoul"},
            },
            "required": ["sender_email", "subject", "inquiry_body"],
        },
    },
]


async def execute_mcp_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute an MCP tool call by name and return structured output."""
    args = arguments or {}
    if tool_name == "GenmunityRootAgent":
        req_text = args.get("request") or args.get("prompt") or "DevFest 핸즈온 연사자 추천해줘"
        return await run_agent_chat(prompt=req_text)
    if tool_name == "rag_search_tool":
        return rag_search_tool(query=args.get("query", ""))
    if tool_name == "search_event_knowledge_base_tool":
        return search_event_knowledge_base_tool(query=args.get("query", ""))
    if tool_name == "slack_search_tool":
        return slack_search_tool(query=args.get("query", ""))
    if tool_name == "summarize_community_data_tool":
        return summarize_community_data_tool(focus=args.get("focus", "all"))
    if tool_name == "get_target_speakers_tool":
        return get_target_speakers_tool()
    if tool_name == "generate_and_send_speaker_emails_tool":
        return generate_and_send_speaker_emails_tool(custom_context=args.get("custom_context", ""))
    if tool_name == "generate_and_send_sponsor_emails_tool":
        return generate_and_send_sponsor_emails_tool(
            custom_context=args.get("custom_context", ""),
            target_email=args.get("target_email", ""),
            company_name=args.get("company_name", ""),
            contact_name=args.get("contact_name", ""),
            tier=args.get("tier", ""),
        )
    if tool_name == "collect_and_cluster_event_emails_tool":
        return collect_and_cluster_event_emails_tool(max_results=int(args.get("max_results", 20)))
    if tool_name == "create_speaker_onboarding_form_tool":
        return create_speaker_onboarding_form_tool(form_title=args.get("form_title", ""))
    if tool_name == "invite_speakers_with_form_and_calendar_tool":
        return invite_speakers_with_form_and_calendar_tool(form_id=args.get("form_id", ""))
    if tool_name == "run_ops_full_workflow_tool":
        return run_ops_full_workflow_tool(custom_context=args.get("custom_context", ""))
    if tool_name == "check_email_receive_trigger_tool":
        return check_email_receive_trigger_tool(force_process_latest=bool(args.get("force_process_latest", False)))
    if tool_name == "handle_inbound_email_inquiry_tool":
        return handle_inbound_email_inquiry_tool(
            sender_email=args.get("sender_email", "attendee@gdg.kr"),
            sender_name=args.get("sender_name", "문의자"),
            subject=args.get("subject", "DevFest 문의"),
            inquiry_body=args.get("inquiry_body", ""),
            event_id=args.get("event_id", "devfest-2026-seoul"),
        )
    if tool_name == "manage_event_rsvp_tool":
        return manage_event_rsvp_tool(
            attendee_name=args.get("attendee_name", "참가자"),
            attendee_email=args.get("attendee_email", "attendee@gdg.kr"),
            event_id=args.get("event_id", "devfest-2026-seoul"),
            action=args.get("action", "create"),
            role=args.get("role", "Developer"),
            track=args.get("track", "AI / Agentic Workflow Hands-on"),
            dietary=args.get("dietary", "일반"),
        )
    if tool_name == "create_or_modify_event_tool":
        return create_or_modify_event_tool(
            title=args.get("title", "신규 GDG 이벤트"),
            event_id=args.get("event_id", ""),
            date=args.get("date", "2026-11-21"),
            venue=args.get("venue", "구글 스타트업 캠퍼스 서울"),
            status=args.get("status", "참가자 모집 중 (RSVP 오픈)"),
            capacity=int(args.get("capacity", 150)),
            budget=args.get("budget", "$3,000"),
            description=args.get("description", ""),
        )
    if tool_name == "add_event_knowledge_tool":
        return add_event_knowledge_tool(
            title=args.get("title", "이벤트 지식 노트"),
            content=args.get("content", ""),
            event_id=args.get("event_id", "devfest-2026-seoul"),
            category=args.get("category", "Event Knowledge"),
        )
    raise ValueError(f"Unknown MCP tool: {tool_name}")


async def handle_a2a_jsonrpc(payload: Dict[str, Any], base_url: str = GENMUNITY_BASE_URL) -> Dict[str, Any]:
    """
    Handle A2A JSON-RPC 2.0 requests (`message/send`, `tasks/send`, `agent/card`)
    by routing through the Google ADK RootAgent (-> SearchAgent / OpsAgent) and returning
    an A2A-compliant Task / Message response.
    """
    req_id = payload.get("id", f"a2a-{uuid.uuid4().hex[:8]}")
    method = payload.get("method", "message/send")
    params = payload.get("params") or {}

    if method in ("agent/card", "agent/authenticatedExtendedCard"):
        card = await get_a2a_agent_card(base_url=base_url)
        return {"jsonrpc": "2.0", "id": req_id, "result": card}

    # Extract user prompt from A2A message parts or prompt field
    prompt_text = ""
    message_obj = params.get("message") or {}
    parts = message_obj.get("parts") or params.get("parts") or []
    for p in parts:
        if isinstance(p, dict):
            if p.get("text"):
                prompt_text += p["text"] + "\n"
            elif p.get("kind") == "text" and p.get("text"):
                prompt_text += p["text"] + "\n"
    if not prompt_text.strip():
        prompt_text = params.get("prompt") or params.get("text") or "DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어"

    session_id = params.get("sessionId") or params.get("contextId") or message_obj.get("contextId")
    chat_res = await run_agent_chat(prompt=prompt_text.strip(), session_id=session_id)

    task_id = params.get("id") or f"task-{uuid.uuid4().hex[:8]}"
    context_id = chat_res["session_id"]

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "id": task_id,
            "contextId": context_id,
            "kind": "task",
            "status": {
                "state": "completed",
                "message": {
                    "role": "agent",
                    "messageId": f"msg-{uuid.uuid4().hex[:8]}",
                    "contextId": context_id,
                    "parts": [{"kind": "text", "text": chat_res["reply"]}],
                },
            },
            "artifacts": [
                {
                    "artifactId": f"art-{uuid.uuid4().hex[:8]}",
                    "name": "adk_execution_metadata",
                    "parts": [
                        {
                            "kind": "data",
                            "data": {
                                "model": chat_res.get("model"),
                                "active_agents": chat_res.get("active_agents", []),
                                "tool_calls": chat_res.get("tool_calls", []),
                            },
                        }
                    ],
                }
            ],
        },
    }


if __name__ == "__main__":
    # Allow running as an stdio MCP server directly: `python -m genmunity_agent.mcp_a2a`
    server = build_mcp_server()
    server.run(transport="stdio")
