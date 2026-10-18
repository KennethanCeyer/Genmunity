"""A2A (Agent2Agent) Protocol Server for the GDG/GDE Community Hub ADK Agent.

Exposes our `root_agent` over the A2A open protocol so external agents can:
1. Discover capabilities via `/.well-known/agent.json` and `/.well-known/agent-card.json`
2. Communicate via ADK `to_a2a(root_agent)` / JSON-RPC 2.0 (`message/send`, `tasks/send`)
3. Query Adaptive RAG + GraphRAG data directly via `/a2a/rag` and `/a2a/graph-rag`.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from community_hub_agent.agent import root_agent
from community_hub_agent.config import settings
from community_hub_agent.rag.retriever import get_rag_retriever
from community_hub_agent.web_ui import playground_router

logger = logging.getLogger(__name__)


def build_agent_card(base_url: str | None = None) -> dict[str, Any]:
    """Constructs the A2A Protocol Agent Card metadata for agent discovery."""
    public_url = (base_url or settings.a2a_public_url).rstrip("/")
    return {
        "name": root_agent.name,
        "description": root_agent.description,
        "url": f"{public_url}/",
        "version": "1.1.0",
        "protocolVersion": "0.2.5",
        "defaultInputModes": ["text", "text/plain", "application/json"],
        "defaultOutputModes": ["text", "text/plain", "application/json"],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "skills": [
            {
                "id": "devfest_community_hub_rag",
                "name": "DevFest Community Hub & Slides Search",
                "description": (
                    "DevFest 이벤트 시리즈 가이드라인 및 페이지 내부 모든 Google Slides 발표장표 데이터 RAG 질의응답"
                ),
                "tags": ["gdg", "gde", "devfest", "slides", "rag"],
                "examples": [
                    "DevFest 준비 타임라인(D-60~D+7)과 공식 로고 표기 규칙 알려줘",
                    "DevFest에서 GDE 연사 초청 여비 지원은 언제까지 신청해야 해?",
                ],
            },
            {
                "id": "build_with_ai_rag",
                "name": "Build with AI Workshop & Slide Deck Search",
                "description": (
                    "Build with AI 커뮤니티 허브(?hl=ko) 및 공식 Google Slides(1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE) 데이터 검색"
                ),
                "tags": ["gdg", "gde", "build-with-ai", "credits", "gemini", "adk"],
                "examples": [
                    "Build with AI 핸즈온 워크숍 추천 시간표와 Google Cloud 크레딧 신청 기한 알려줘",
                ],
            },
            {
                "id": "kr_organizer_sheet_lookup",
                "name": "Korean GDG/GDE Organizer Spreadsheet Lookup",
                "description": (
                    "국내 GDG/GDE 운영진 스프레드시트([External] GDG KR Communication.xlsx) 11개 탭(24~26 이벤트, 26 Active Rate) 조회"
                ),
                "tags": ["korea", "gdg-kr", "gde-kr", "sheets", "organizer"],
                "examples": [
                    "국내 GDG 챕터 종류와 2026 Active Rate 오프보딩 기준 알려줘",
                ],
            },
            {
                "id": "community_knowledge_graph_rag",
                "name": "GDG/GDE Community GraphRAG & Adaptive Hybrid Workflow",
                "description": (
                    "챕터 간 공동 주최(Co-hosting) 네트워크, 영문/국문 오거나이저-연사(GDE) 겸임 관계, "
                    "다중 홉(Multi-hop) 지식 그래프 탐색 및 ADK Parallel+Sequential 하이브리드 RAG+GraphRAG 질의응답"
                ),
                "tags": ["graphrag", "knowledge-graph", "hybrid-rag", "adk-workflow", "network"],
                "examples": [
                    "GDG Incheon과 공동 주최한 챕터들과 박제창(PARK JAICHANG) 오거나이저의 연사/운영 활동 이력 알려줘",
                    "국내 GDG 챕터 중 연합 행사를 개최한 챕터 관계망을 분석해줘",
                ],
            },
        ],
    }


async def run_agent_or_rag_fallback(user_text: str, session_id: str | None = None) -> dict[str, Any]:
    """Executes `root_agent` via ADK Runner if Gemini/Vertex AI credentials exist, else returns adaptive RAG+GraphRAG answer."""
    retriever = get_rag_retriever()
    adaptive_bundle = retriever.retrieve_adaptive(query=user_text, top_k=4)
    routing = adaptive_bundle["routing"]
    rag_results = (adaptive_bundle.get("vector_rag") or {}).get("results", [])
    graph_payload = adaptive_bundle.get("graph_rag") or {}

    api_key = os.getenv("GOOGLE_API_KEY", "")
    has_llm_creds = bool(
        (api_key and api_key != "your-gemini-api-key")
        or (
            settings.use_vertexai
            and settings.gcp_project
            and settings.gcp_project != "your-gcp-project-id"
        )
    )

    if has_llm_creds:
        try:
            from google.adk.runners import InMemoryRunner
            from google.genai import types

            runner = InMemoryRunner(
                agent=root_agent, app_name="community_hub_a2a"
            )
            sid = session_id or f"session_{uuid.uuid4().hex[:8]}"
            user_id = "a2a_peer_agent"
            await runner.session_service.create_session(
                app_name="community_hub_a2a", user_id=user_id, session_id=sid
            )
            msg = types.Content(
                role="user", parts=[types.Part.from_text(text=user_text)]
            )
            final_texts: list[str] = []
            async for event in runner.run_async(
                user_id=user_id, session_id=sid, new_message=msg
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            final_texts.append(part.text)
            if final_texts:
                return {
                    "text": "\n".join(final_texts),
                    "rag_results": rag_results,
                    "graph_rag": graph_payload,
                    "routing": routing,
                    "mode": "adk_llm_agent",
                }
        except Exception as exc:
            logger.warning("ADK LLM execution fell back to adaptive RAG+GraphRAG synthesis: %s", exc)

    # Deterministic Grounded Adaptive RAG + GraphRAG Response
    lines = [
        f"### [GDG/GDE Community Hub Adaptive 응답 (`{routing['strategy']}`)] 질문: {user_text}",
        f"- **선택된 전략**: `{routing['strategy']}` ({routing['reason']})",
        "",
    ]

    if graph_payload and graph_payload.get("subgraph_triples"):
        lines.append("#### [GraphRAG 지식 그래프 탐색 결과]")
        lines.append(graph_payload.get("summary_markdown", ""))
        lines.append("")

    if rag_results:
        lines.append("#### [Vector RAG 문서/슬라이드/시트 검색 결과]")
        for idx, hit in enumerate(rag_results, start=1):
            lines.append(
                f"**{idx}. {hit['title']}** (카테고리: `{hit['category']}`, 유사도: `{hit['score']}`)"
            )
            lines.append(hit["content"])
            lines.append(f"- 출처 URL: {hit['source_url']}")
            lines.append("")

    # Ensure citations list is always populated for A2A clients even in pure graph_rag mode
    if not rag_results:
        fallback_vec = retriever.retrieve(query=user_text, top_k=2)
        rag_results = fallback_vec.get("results", [])

    return {
        "text": "\n".join(lines).strip(),
        "rag_results": rag_results,
        "graph_rag": graph_payload,
        "routing": routing,
        "mode": f"adaptive_{routing['strategy']}_grounding",
    }


def create_a2a_app() -> FastAPI:
    """Creates a FastAPI application supporting both ADK `to_a2a` and standard A2A JSON-RPC + REST."""
    app = FastAPI(
        title="GDG/GDE Community Hub ADK + A2A Server (Vector RAG & GraphRAG)",
        version="1.1.0",
        description="A2A-enabled Google ADK Agent with Adaptive Vector RAG and GraphRAG workflows",
    )

    app.include_router(playground_router)

    @app.get("/.well-known/agent.json")
    @app.get("/.well-known/agent-card.json")
    async def get_well_known_agent_card() -> JSONResponse:
        return JSONResponse(content=build_agent_card())

    @app.get("/health")
    async def health() -> dict[str, Any]:
        retriever = get_rag_retriever()
        return {
            "status": "healthy",
            "agent_name": root_agent.name,
            "rag_mode": settings.rag_mode,
            "vector_backend": settings.vector_backend,
            "indexed_chunks_count": len(retriever.local_store.chunks),
            "knowledge_graph": retriever.knowledge_graph.stats(),
        }

    @app.post("/a2a/rag")
    async def direct_a2a_rag_exchange(payload: dict[str, Any]) -> dict[str, Any]:
        """Structured data-exchange endpoint for peer agents requesting Adaptive RAG + GraphRAG data."""
        query = str(payload.get("query", "")).strip()
        category = str(payload.get("category", "all")).strip()
        top_k = int(payload.get("top_k", 5))
        retriever = get_rag_retriever()
        adaptive_data = retriever.retrieve_adaptive(
            query=query, category=category, top_k=top_k
        )
        agent_reply = await run_agent_or_rag_fallback(query)
        return {
            "agent": root_agent.name,
            "answer": agent_reply["text"],
            "execution_mode": agent_reply["mode"],
            "routing": adaptive_data["routing"],
            "rag_payload": adaptive_data.get("vector_rag"),
            "graph_payload": adaptive_data.get("graph_rag"),
        }

    @app.post("/a2a/graph-rag")
    async def direct_a2a_graph_rag_exchange(payload: dict[str, Any]) -> dict[str, Any]:
        """Dedicated GraphRAG endpoint for multi-hop entity & relationship queries from peer agents."""
        query = str(payload.get("query", "")).strip()
        max_hops = int(payload.get("max_hops", 2))
        top_k = int(payload.get("top_k", 20))
        retriever = get_rag_retriever()
        graph_data = retriever.retrieve_graph(
            query=query, max_hops=max_hops, top_k=top_k
        )
        return {
            "agent": root_agent.name,
            "graph_payload": graph_data,
        }

    @app.post("/")
    @app.post("/a2a")
    async def a2a_jsonrpc_endpoint(request: Request) -> JSONResponse:
        """Standard A2A JSON-RPC 2.0 endpoint handling `message/send`, `tasks/send`, and `agent/authenticatedExtendedCard`."""
        body = await request.json()
        rpc_id = body.get("id", str(uuid.uuid4()))
        method = body.get("method", "message/send")
        params = body.get("params", {}) or {}

        if method in ("agent/authenticatedExtendedCard", "agent/card"):
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": build_agent_card(),
                }
            )

        user_text = ""
        message_obj = params.get("message", {})
        for part in message_obj.get("parts", []):
            if isinstance(part, dict):
                if "text" in part:
                    user_text += str(part["text"]) + "\n"
                elif part.get("kind") == "text" and "text" in part:
                    user_text += str(part["text"]) + "\n"
        user_text = user_text.strip() or str(params.get("query", "")).strip()

        if not user_text:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {
                        "code": -32602,
                        "message": "Missing text part in A2A message params.",
                    },
                },
                status_code=400,
            )

        session_id = params.get("contextId") or params.get("id")
        result_bundle = await run_agent_or_rag_fallback(
            user_text=user_text, session_id=session_id
        )
        task_id = params.get("id") or f"task_{uuid.uuid4().hex[:10]}"
        context_id = session_id or f"ctx_{uuid.uuid4().hex[:10]}"
        message_id = f"msg_{uuid.uuid4().hex[:10]}"

        response_payload = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "kind": "message",
                "messageId": message_id,
                "taskId": task_id,
                "contextId": context_id,
                "role": "agent",
                "parts": [
                    {
                        "kind": "text",
                        "text": result_bundle["text"],
                    },
                    {
                        "kind": "data",
                        "data": {
                            "source_agent": root_agent.name,
                            "execution_mode": result_bundle["mode"],
                            "routing": result_bundle["routing"],
                            "citations": [
                                {
                                    "chunk_id": r["chunk_id"],
                                    "title": r["title"],
                                    "category": r["category"],
                                    "source_url": r["source_url"],
                                    "score": r["score"],
                                }
                                for r in result_bundle["rag_results"]
                            ],
                            "graph_triples": (result_bundle.get("graph_rag") or {}).get(
                                "subgraph_triples", []
                            )[:10],
                        },
                    },
                ],
            },
        }
        return JSONResponse(content=response_payload)

    try:
        from google.adk.a2a.utils.agent_to_a2a import to_a2a

        native_a2a_app = to_a2a(root_agent, port=settings.a2a_port)
        app.mount("/adk-a2a", native_a2a_app)
        logger.info("Mounted native ADK `to_a2a` application at /adk-a2a")
    except Exception as exc:
        logger.debug("Native `to_a2a` mount skipped (using built-in A2A JSON-RPC server): %s", exc)

    return app


a2a_app = create_a2a_app()


def main() -> None:
    uvicorn.run(
        "community_hub_agent.a2a_server:a2a_app",
        host=settings.a2a_host,
        port=settings.a2a_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
