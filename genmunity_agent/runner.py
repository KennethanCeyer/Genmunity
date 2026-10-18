import asyncio
import json
import re
import time
import uuid
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
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

TOOL_LABELS_KO: Dict[str, str] = {
    "rag_search_tool": "CommunityHub · Advocu · GDG 시트 RAG 검색",
    "search_gdg_gde_directory_tool": "GDG 챕터 운영진 · GDE 디렉토리 검색 (개인정보 마스킹 적용)",
    "crawl_community_hub_tool": "Google CommunityHub 라이브 크롤링",
    "search_event_knowledge_base_tool": "행사 지식 베이스 및 참석자 통계 조회",
    "slack_search_tool": "GDG/GDE Slack 스레드 검색",
    "summarize_community_data_tool": "커뮤니티 데이터 요약 생성",
    "get_target_speakers_tool": "매칭된 핸즈온 연사자(한성민·박제창) 로드",
    "generate_and_send_speaker_emails_tool": "맞춤형 연사 섭외 이메일 생성 및 Gmail 발송",
    "generate_and_send_sponsor_emails_tool": "맞춤형 스폰서 후원 제안서 생성 및 Gmail 발송",
    "collect_and_cluster_event_emails_tool": "Gmail 수신 메일 수집 및 AI 의미 클러스터링",
    "create_speaker_onboarding_form_tool": "발표자 사전 정보 Google Form 생성",
    "fetch_google_form_responses_tool": "Google Forms 응답 실시간 동기화",
    "record_speaker_form_response_tool": "발표자 폼 응답 이벤트 상태 반영",
    "invite_speakers_with_form_and_calendar_tool": "온보딩 Form 링크 및 Google Calendar(.ics) 초대 발송",
    "run_ops_full_workflow_tool": "OpsAgent 5단계 전 과정 자동화 파이프라인 실행",
    "check_email_receive_trigger_tool": "수신함(INBOX) 트리거 확인 및 자동 처리",
    "handle_inbound_email_inquiry_tool": "수신 문의 지식 베이스 자동 회신 / 운영자 이관",
    "manage_event_rsvp_tool": "이벤트 참가자 RSVP 등록·수정·취소 처리",
    "create_or_modify_event_tool": "커뮤니티 이벤트 기획 및 상태 업데이트",
    "generate_event_image_tool": "Gemini 이벤트 키비주얼 배너 이미지 생성",
    "add_event_knowledge_tool": "행사 지식 베이스 신규 문서 등재",
    "analyze_event_photo_tool": "Gemini Vision 현장 사진 참가자 수 분석",
    "get_event_readiness_summary_tool": "행사 운영 준비도 및 파이프라인 현황 진단",
}


def _strip_emojis(text: str) -> str:
    return re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text or "")


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


def _extract_images_from_response(resp_data: Any) -> List[Dict[str, Any]]:
    images: List[Dict[str, Any]] = []
    if not isinstance(resp_data, dict):
        return images
    img_obj = resp_data.get("image")
    if isinstance(img_obj, dict) and img_obj.get("url"):
        images.append(img_obj)
    photo_obj = resp_data.get("photo")
    if isinstance(photo_obj, dict) and photo_obj.get("url"):
        images.append(
            {
                "url": photo_obj["url"],
                "prompt": photo_obj.get("caption") or "현장 사진 분석",
                "style": f"감지 인원 {photo_obj.get('detected_headcount', 0)}명",
                "model": "Gemini Vision",
            }
        )
    return images


def _summarize_tool_response(tool_name: str, resp_data: Any) -> str:
    if not isinstance(resp_data, dict):
        return "완료"
    if tool_name == "rag_search_tool":
        cnt = len(resp_data.get("recommended_speakers") or [])
        return f"추천 연사 {cnt}명 및 예산/일정 가이드라인 검색 완료"
    if tool_name == "search_gdg_gde_directory_tool":
        gde_cnt = len(resp_data.get("gde_matches") or [])
        gdg_cnt = len(resp_data.get("gdg_exact_matches") or [])
        return f"GDE {gde_cnt}명 · 완전 매칭 GDG {gdg_cnt}명 검색 완료 (비매칭 개인정보 마스킹)"
    if tool_name == "get_target_speakers_tool":
        names = ", ".join(s.get("name", "") for s in (resp_data.get("speakers") or []))
        return f"대상 연사 로드: {names}"
    if tool_name == "generate_and_send_speaker_emails_tool":
        return f"연사 초청 메일 {resp_data.get('total_sent', 0)}건 발송 완료"
    if tool_name == "generate_and_send_sponsor_emails_tool":
        return f"스폰서 제안 메일 {resp_data.get('total_sent', 0)}건 발송 완료"
    if tool_name == "collect_and_cluster_event_emails_tool":
        return f"메일 {resp_data.get('total_emails_collected', 0)}건 수집 · {len(resp_data.get('clusters') or [])}개 클러스터 분류"
    if tool_name == "create_speaker_onboarding_form_tool":
        return f"온보딩 Form 생성 완료 ({resp_data.get('form_id', '')})"
    if tool_name == "invite_speakers_with_form_and_calendar_tool":
        return f"Form 링크 및 캘린더(.ics) 초대장 {len(resp_data.get('invites_sent') or [])}건 발송"
    if tool_name == "generate_event_image_tool":
        img = resp_data.get("image") or {}
        return f"배너 이미지 생성 완료 ({img.get('url', '')})"
    if tool_name == "manage_event_rsvp_tool":
        rsvp = resp_data.get("rsvp") or {}
        return f"RSVP {resp_data.get('action', '처리')}: {rsvp.get('name', '')} (총 {resp_data.get('total_rsvp_count', 0)}명)"
    if tool_name == "create_or_modify_event_tool":
        ev = resp_data.get("event") or {}
        return f"이벤트 {resp_data.get('action', '업데이트')}: {ev.get('title', '')}"
    if tool_name == "handle_inbound_email_inquiry_tool":
        return f"문의 처리 완료 ({resp_data.get('action', '')})"
    return "실행 완료"


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
    generated_images: List[Dict[str, Any]] = []
    active_agents: List[str] = ["RootAgent"]
    used_model = GEMINI_PRIMARY_MODEL

    last_exc: Optional[Exception] = None
    for model_candidate in GEMINI_MODEL_CANDIDATES:
        _set_agents_model(model_candidate)
        used_model = model_candidate
        final_texts.clear()
        tool_calls_made.clear()
        generated_images.clear()
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
                        t_name = getattr(fn_call, "name", "")
                        tool_calls_made.append(
                            {
                                "agent": author,
                                "tool_name": t_name,
                                "label": TOOL_LABELS_KO.get(t_name, t_name),
                                "args": dict(getattr(fn_call, "args", {}) or {}),
                            }
                        )
                    fn_resp = getattr(part, "function_response", None)
                    if fn_resp:
                        resp_dict = getattr(fn_resp, "response", None)
                        for img in _extract_images_from_response(resp_dict):
                            generated_images.append(img)
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
    reply = _strip_emojis(raw_reply)
    state = load_runtime_state()
    return {
        "session_id": sid,
        "model": used_model,
        "prompt": prompt,
        "reply": reply,
        "active_agents": active_agents,
        "tool_calls": tool_calls_made,
        "images": generated_images,
        "latest_trace": state.get("agent_trace", [])[-8:],
    }


async def run_agent_chat_stream(
    prompt: str,
    user_id: str = "gdg_organizer",
    session_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream real-time SSE events while executing the Google ADK RootAgent:
    - thinking / phase transitions
    - agent handoffs (RootAgent -> SearchAgent / OpsAgent)
    - tool_start & tool_end with elapsed time and structured summary
    - image_generated events when Gemini Image Generation or Vision runs
    - text_delta events for live Markdown streaming
    - done event with full session metadata
    """
    sid = session_id or f"session-{uuid.uuid4().hex[:8]}"
    await ensure_adk_session(user_id=user_id, session_id=sid)
    runner = get_adk_runner()

    def _sse(payload: Dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    yield _sse(
        {
            "type": "status",
            "session_id": sid,
            "agent": "RootAgent",
            "phase": "thinking",
            "message": "요청 의도를 분석하고 실행 계획을 수립하고 있습니다...",
        }
    )

    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )

    final_texts: List[str] = []
    tool_calls_made: List[Dict[str, Any]] = []
    generated_images: List[Dict[str, Any]] = []
    active_agents: List[str] = ["RootAgent"]
    used_model = GEMINI_PRIMARY_MODEL
    step_timers: Dict[str, float] = {}

    last_exc: Optional[Exception] = None
    for model_candidate in GEMINI_MODEL_CANDIDATES:
        _set_agents_model(model_candidate)
        used_model = model_candidate
        final_texts.clear()
        tool_calls_made.clear()
        generated_images.clear()
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
                    yield _sse(
                        {
                            "type": "agent_handoff",
                            "agent": author,
                            "active_agents": list(active_agents),
                            "message": f"{author} 에이전트가 작업을 수행합니다.",
                        }
                    )

                content = getattr(event, "content", None)
                if not content or not getattr(content, "parts", None):
                    continue

                for part in content.parts:
                    fn_call = getattr(part, "function_call", None)
                    if fn_call:
                        t_name = getattr(fn_call, "name", "")
                        t_args = dict(getattr(fn_call, "args", {}) or {})
                        step_id = f"step-{len(tool_calls_made) + 1}-{t_name}"
                        step_timers[t_name] = time.perf_counter()
                        label = TOOL_LABELS_KO.get(t_name, t_name)
                        tc_entry = {
                            "step_id": step_id,
                            "agent": author,
                            "tool_name": t_name,
                            "label": label,
                            "args": t_args,
                            "status": "running",
                        }
                        tool_calls_made.append(tc_entry)
                        yield _sse(
                            {
                                "type": "tool_start",
                                "step_id": step_id,
                                "agent": author,
                                "tool_name": t_name,
                                "label": label,
                                "args": t_args,
                            }
                        )

                    fn_resp = getattr(part, "function_response", None)
                    if fn_resp:
                        t_name = getattr(fn_resp, "name", "")
                        resp_dict = getattr(fn_resp, "response", None)
                        elapsed_ms = int((time.perf_counter() - step_timers.get(t_name, time.perf_counter())) * 1000)
                        summary_text = _summarize_tool_response(t_name, resp_dict)
                        imgs = _extract_images_from_response(resp_dict)
                        for tc in reversed(tool_calls_made):
                            if tc["tool_name"] == t_name and tc.get("status") == "running":
                                tc["status"] = "completed"
                                tc["elapsed_ms"] = elapsed_ms
                                tc["summary"] = summary_text
                                break
                        yield _sse(
                            {
                                "type": "tool_end",
                                "agent": author,
                                "tool_name": t_name,
                                "label": TOOL_LABELS_KO.get(t_name, t_name),
                                "elapsed_ms": elapsed_ms,
                                "summary": summary_text,
                            }
                        )
                        for img in imgs:
                            generated_images.append(img)
                            yield _sse({"type": "image_generated", "image": img})

                    text_val = getattr(part, "text", None)
                    if text_val and text_val.strip():
                        cleaned = _strip_emojis(text_val.strip())
                        final_texts.append(cleaned)
                        # Stream text smoothly in small chunks for real-time progressive rendering
                        chunk_size = 18
                        for i in range(0, len(cleaned), chunk_size):
                            chunk = cleaned[i : i + chunk_size]
                            yield _sse({"type": "text_delta", "delta": chunk, "agent": author})
                            await asyncio.sleep(0.01)

            last_exc = None
            break
        except Exception as exc:
            logger.warning(f"ADK stream run failed with model {model_candidate}, falling back: {exc}")
            last_exc = exc

    if last_exc is not None:
        yield _sse({"type": "error", "message": f"오류가 발생했습니다: {last_exc}"})
        return

    reply = "\n\n".join(final_texts) if final_texts else "요청하신 작업을 처리했습니다."
    state = load_runtime_state()
    yield _sse(
        {
            "type": "done",
            "session_id": sid,
            "model": used_model,
            "reply": reply,
            "active_agents": active_agents,
            "tool_calls": tool_calls_made,
            "images": generated_images,
            "latest_trace": state.get("agent_trace", [])[-8:],
        }
    )
