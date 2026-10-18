import re
import uuid
import logging
from typing import Dict, Any, List, Optional
from google.genai import types
from google.adk.runners import InMemoryRunner

from genmunity_agent.agent import root_agent
from genmunity_agent.config import (
    GEMINI_PRIMARY_MODEL,
    GEMINI_SECONDARY_MODEL,
    GEMINI_MODEL_CANDIDATES,
    load_runtime_state,
)

logger = logging.getLogger("genmunity.runner")

APP_NAME = "genmunity_adk_app"
_runner: Optional[InMemoryRunner] = None
_initialized_sessions: set[str] = set()


def _set_agents_model(model_name: str) -> None:
    root_agent.model = model_name
    for sub in getattr(root_agent, "sub_agents", []) or []:
        sub.model = model_name


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
    """Run user prompt through the Google ADK RootAgent (primary: gemini-4-argon, secondary: gemini-3.8-flash)."""
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
    used_model = GEMINI_PRIMARY_MODEL

    last_exc: Optional[Exception] = None
    for model_candidate in GEMINI_MODEL_CANDIDATES:
        _set_agents_model(model_candidate)
        used_model = model_candidate
        final_texts.clear()
        tool_calls_made.clear()
        active_agents = ["RootAgent"]
        try:
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
            last_exc = None
            break
        except Exception as exc:
            logger.warning(f"ADK run failed with model {model_candidate}, falling back to {GEMINI_SECONDARY_MODEL}: {exc}")
            last_exc = exc

    if last_exc is not None:
        raise last_exc

    raw_reply = "\n\n".join(final_texts) if final_texts else "요청하신 작업을 처리했습니다."
    reply = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", raw_reply)
    state = load_runtime_state()
    return {
        "session_id": sid,
        "model": used_model,
        "prompt": prompt,
        "reply": reply,
        "active_agents": active_agents,
        "tool_calls": tool_calls_made,
        "latest_trace": state.get("agent_trace", [])[-8:],
    }
