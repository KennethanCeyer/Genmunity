import uuid
import logging
from typing import Dict, Any, List, Optional
from google.genai import types
from google.adk.runners import InMemoryRunner

from genmunity_agent.agent import root_agent
from genmunity_agent.config import load_runtime_state

logger = logging.getLogger("genmunity.runner")

APP_NAME = "genmunity_adk_app"
_runner: Optional[InMemoryRunner] = None
_initialized_sessions: set[str] = set()


def get_adk_runner() -> InMemoryRunner:
    global _runner
    if _runner is None:
        _runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    return _runner


async def ensure_adk_session(user_id: str, session_id: str) -> None:
    key = f"{user_id}:{session_id}"
    if key in _initialized_sessions:
        return
    runner = get_adk_runner()
    try:
        existing = await runner.session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if not existing:
            await runner.session_service.create_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
    except Exception:
        await runner.session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
    _initialized_sessions.add(key)


async def run_agent_chat(
    prompt: str,
    user_id: str = "gdg_organizer",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run user prompt through the Google ADK RootAgent (-> SearchAgent / OpsAgent)."""
    sid = session_id or f"session-{uuid.uuid4().hex[:8]}"
    await ensure_adk_session(user_id=user_id, session_id=sid)
    runner = get_adk_runner()

    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )

    final_texts: List[str] = []
    tool_calls_made: List[Dict[str, Any]] = []
    active_agents: List[str] = ["RootAgent"]

    async for event in runner.run_async(
        user_id=user_id,
        session_id=sid,
        new_message=new_message,
    ):
        author = getattr(event, "author", None) or "RootAgent"
        if author not in active_agents:
            active_agents.append(author)

        content = getattr(event, "content", None)
        if not content or not getattr(content, "parts", None):
            continue

        for part in content.parts:
            fn_call = getattr(part, "function_call", None)
            if fn_call:
                tool_calls_made.append(
                    {
                        "agent": author,
                        "tool_name": getattr(fn_call, "name", ""),
                        "args": dict(getattr(fn_call, "args", {}) or {}),
                    }
                )
            text_val = getattr(part, "text", None)
            if text_val and text_val.strip():
                final_texts.append(text_val.strip())

    reply = "\n\n".join(final_texts) if final_texts else "요청하신 작업을 처리했습니다."
    state = load_runtime_state()
    return {
        "session_id": sid,
        "prompt": prompt,
        "reply": reply,
        "active_agents": active_agents,
        "tool_calls": tool_calls_made,
        "latest_trace": state.get("agent_trace", [])[-8:],
    }
