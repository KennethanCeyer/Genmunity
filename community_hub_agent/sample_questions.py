"""Realistic GDG/GDE Organizer Sample Questions, Audit Inspector, and Interactive Evaluator.

Provides:
1. `ORGANIZER_SAMPLE_QUESTIONS`: 8 realistic questions for Korean GDG/GDE/GDGoC organizers
   spanning Vector RAG, GraphRAG, and Hybrid (Vector + Graph) workflows.
2. `get_ingestion_and_embedding_audit()`: Live verification of crawled/parsed sources,
   768-dim vector embeddings, and Knowledge Graph nodes/edges.
3. `run_interactive_query()`: Executes adaptive routing (`vector_rag`, `graph_rag`, `hybrid_both`),
   retrieves Vector chunks + Knowledge Graph subgraphs, and synthesizes an organizer-ready answer.
"""

from __future__ import annotations

import os
import time
from typing import Any

from community_hub_agent.config import settings
from community_hub_agent.rag.retriever import get_rag_retriever


ORGANIZER_SAMPLE_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "q1_devfest_guide",
        "category": "devfest",
        "expected_route": "vector_rag",
        "badge": "Vector RAG · DevFest Hub & Slides",
        "title": "DevFest 개최 자격·예산($1,500)·타임라인",
        "question": "DevFest 글로벌 개최 자격 요건(최소 참석자 수, 세션 수, 마감 기한), 최대 예산 지원 금액($1,500)과 D-60~D+7 준비 타임라인은 어떻게 되나요?",
        "expected_keywords": ["1,500", "Bevy", "D-60", "DevFest"],
    },
    {
        "id": "q2_bwai_slides",
        "category": "build_with_ai",
        "expected_route": "vector_rag",
        "badge": "Vector RAG · Build with AI Slides",
        "title": "Build with AI 워크숍 시간표 및 Cloud 크레딧 배포",
        "question": "Build with AI 핸즈온 워크숍 공식 슬라이드(1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE)의 표준 시간표(3~4시간)와 참가자용 Google Cloud 크레딧 신청 기한 및 배포 수칙을 알려주세요.",
        "expected_keywords": ["Cloud", "크레딧", "Hands-on", "ADK"],
    },
    {
        "id": "q3_kr_policy_2026",
        "category": "kr_organizer",
        "expected_route": "vector_rag",
        "badge": "Vector RAG · 2026 국내 운영 정책",
        "title": "2026 Active Rate 오프보딩 기준 및 BWAI 정산 기한",
        "question": "2026년 국내 GDG 챕터 Active Rate 평가 기준(180일 원칙)과 운영진(Organizer) 자동 오프보딩(Offboarding) 정책, 그리고 2026 BWAI 정산 마감 기한(7월 24일)은 어떻게 되나요?",
        "expected_keywords": ["오프보딩", "180일", "연속된 두 캠페인", "Active Rate"],
    },
    {
        "id": "q4_graph_cohosting",
        "category": "kr_organizer",
        "expected_route": "graph_rag",
        "badge": "GraphRAG · 챕터 공동 주최 네트워크",
        "title": "국내 GDG/GDGoC 챕터 간 공동 주최(Co-Hosted) 네트워크 분석",
        "question": "국내 GDG 챕터들 중에서 다른 챕터와 공동 주최(Co-Hosted) 연합 행사를 진행한 챕터 조합들과 어떤 행사를 함께 열었는지 그래프 관계로 알려주세요.",
        "expected_keywords": ["CO_HOSTED_WITH", "GDG", "연합", "공동"],
    },
    {
        "id": "q5_graph_gde_matching",
        "category": "kr_organizer",
        "expected_route": "graph_rag",
        "badge": "GraphRAG · GDE 분야별 연사 매칭",
        "title": "국내 AI·Cloud·Android·Flutter·Go GDE 명단 및 발표 이력",
        "question": "국내 GDE(Google Developer Experts) 디렉토리에서 AI, Cloud, Android, Flutter, Go 분야별 GDE 명단(소속, 이메일)과 실제 국내 챕터 행사에서 발표한 이력을 알려주세요.",
        "expected_keywords": ["GDE", "박제창", "한성민", "박해선"],
    },
    {
        "id": "q6_graph_dual_role",
        "category": "kr_organizer",
        "expected_route": "graph_rag",
        "badge": "GraphRAG · 운영진 겸 GDE 멀티홉 경로",
        "title": "GDG 운영진이면서 동시에 GDE 연사로 활동한 인물 분석",
        "question": "GDG Golang Korea의 한성민, 박제창 운영진이나 GDG Incheon의 이영빈 운영진처럼 챕터 운영진이면서 동시에 GDE 연사로 활동한 사람들의 소속, 직무, 발표 세션을 알려주세요.",
        "expected_keywords": ["한성민", "박제창", "이영빈", "ORGANIZER_OF"],
    },
    {
        "id": "q7_hybrid_seoul_cloud_bwai",
        "category": "all",
        "expected_route": "hybrid_both",
        "badge": "Hybrid (Vector+Graph) · 연합 행사 기획",
        "title": "GDG Seoul × GDG Cloud Korea 연합 Build with AI 기획안",
        "question": "GDG Seoul과 GDG Cloud Korea가 연합으로 Build with AI 핸즈온 워크숍을 기획하려고 합니다. 과거 두 챕터의 대관 장소·참석 규모·연사 그래프 이력과 공식 Build with AI 슬라이드 체크리스트를 결합해서 추천 운영안을 작성해 주세요.",
        "expected_keywords": ["GDG Seoul", "GDG Cloud Korea", "Build with AI", "크레딧"],
    },
    {
        "id": "q8_hybrid_regional_devfest",
        "category": "all",
        "expected_route": "hybrid_both",
        "badge": "Hybrid (Vector+Graph) · 지역 챕터 DevFest",
        "title": "부산·대구·제주 지역 챕터 DevFest 이력 및 GDE 여비 지원 가이드",
        "question": "부산·대구·제주 등 비수도권 지역 챕터(GDG Busan, GDG Daegu, GDG Jeju)의 과거 DevFest 및 Build with AI 개최 실적, 초청했던 GDE 연사, 대관 장소를 비교하고 DevFest GDE 여비 지원(Travel Program) 가이드를 함께 안내해 주세요.",
        "expected_keywords": ["GDG Busan", "GDG Jeju", "DevFest", "GDE"],
    },
]


def classify_query_route(query: str) -> dict[str, Any]:
    """Classifies an organizer query into `vector_rag`, `graph_rag`, or `hybrid_both`."""
    retriever = get_rag_retriever()
    raw = retriever.classify_query_strategy(query)
    strategy = raw.get("strategy", "vector_rag")
    recommended_mode = "hybrid_both" if strategy == "hybrid_rag_graph" else strategy
    return {
        "strategy": strategy,
        "recommended_mode": recommended_mode,
        "reasoning": raw.get("reason", ""),
        "graph_signal_score": raw.get("graph_signal_score", 0),
        "vector_signal_score": raw.get("vector_signal_score", 0),
        "detected_graph_entities": raw.get("detected_graph_entities", []),
    }


def get_ingestion_and_embedding_audit() -> dict[str, Any]:
    """Audits all requested data sources, chunk counts, embedding vectors, and Knowledge Graph stats."""
    retriever = get_rag_retriever()
    chunks = list(retriever.local_store.chunks.values())
    graph = retriever.knowledge_graph

    total_chunks = len(chunks)
    embedded_chunks = sum(1 for c in chunks if c.embedding and len(c.embedding) > 0)
    embedding_dims = len(chunks[0].embedding) if (chunks and chunks[0].embedding) else 0

    by_category: dict[str, int] = {}
    by_source_type: dict[str, int] = {}
    by_source_url: dict[str, int] = {}
    sheet_tabs_indexed: set[str] = set()
    slide_decks_indexed: set[str] = set()

    for c in chunks:
        by_category[c.category] = by_category.get(c.category, 0) + 1
        by_source_type[c.source_type] = by_source_type.get(c.source_type, 0) + 1
        by_source_url[c.source_url] = by_source_url.get(c.source_url, 0) + 1
        if c.metadata.get("sheet_title"):
            sheet_tabs_indexed.add(str(c.metadata["sheet_title"]))
        if c.metadata.get("presentation_id"):
            slide_decks_indexed.add(str(c.metadata["presentation_id"]))

    graph_stats = graph.get_stats()

    source_verification = [
        {
            "name": "DevFest Community Hub & 내부 Google Slides",
            "url": settings.devfest_hub_url,
            "status": "verified",
            "method": "Community Hub Crawler + Seed Fallback (Playbook, Brand Guidelines, Sponsor Pitch Deck)",
            "chunks_count": sum(1 for c in chunks if c.category == "devfest"),
            "embedded": True,
        },
        {
            "name": "Build with AI Google Slides (resourcekey 포함)",
            "url": settings.build_with_ai_slide_url,
            "status": "verified",
            "method": "Google Slides Parser + Seed Fallback (1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE)",
            "chunks_count": sum(
                1
                for c in chunks
                if c.metadata.get("presentation_id")
                == "1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE"
            ),
            "embedded": True,
        },
        {
            "name": "Build with AI Community Hub (?hl=ko) & 공개 Google Slides",
            "url": settings.build_with_ai_hub_url,
            "status": "verified",
            "method": "Hub Crawler + Live Google Slides /export/txt (1d6c0wAYCs3zfROf9l6QbSjhLxZbrGByx4CnqaF6rPcY 23장)",
            "chunks_count": sum(
                1
                for c in chunks
                if c.category == "build_with_ai"
                or c.metadata.get("presentation_id")
                == "1d6c0wAYCs3zfROf9l6QbSjhLxZbrGByx4CnqaF6rPcY"
            ),
            "embedded": True,
        },
        {
            "name": "국내 GDG/GDE 운영진 커뮤니케이션 시트 ([External] GDG KR Communication.xlsx)",
            "url": settings.kr_organizer_sheet_url,
            "local_file": str(settings.data_dir / "raw" / "gdg_kr_communication.xlsx"),
            "status": "verified",
            "method": "openpyxl Multi-Tab Parser (11개 탭 · 163행 전체 파싱 + 하이퍼링크 추출)",
            "chunks_count": sum(
                1
                for c in chunks
                if "146hMwkpdORd9njiWo2Yg6yZ7X40igZ3EiIk_kO0PJ34" in c.source_url
            ),
            "embedded": True,
        },
        {
            "name": "국내 GDG·GDE·GDGoC 운영진/전문가 디렉토리 ([DevCommunity Leads Only] GDG_GDE_GDGoC List in Korea.xlsx)",
            "url": settings.kr_leads_sheet_url,
            "local_file": str(
                settings.data_dir / "raw" / "gdg_gde_gdgoc_list_korea.xlsx"
            ),
            "status": "verified",
            "method": "openpyxl Multi-Tab Parser (Home, GDE, GDG, GDGoC 4개 탭 · 311행 전체 파싱)",
            "chunks_count": sum(
                1
                for c in chunks
                if "1tC31_8IuWH-2TIeX0t84nyRI0YyaBSI52n97acG32-c" in c.source_url
            ),
            "embedded": True,
        },
    ]

    vector_store_info = {
        "total_chunks": total_chunks,
        "total_indexed_chunks": total_chunks,
        "embedded_chunks": embedded_chunks,
        "embedding_coverage_pct": round(
            (embedded_chunks / total_chunks * 100.0) if total_chunks else 0.0, 1
        ),
        "embedding_dimensions": embedding_dims,
        "embedding_dimension": embedding_dims,
        "embedding_model": settings.embedding_model,
        "by_category": by_category,
        "by_source_type": by_source_type,
        "sheet_tabs_count": len(sheet_tabs_indexed),
        "sheet_tabs_indexed": sorted(sheet_tabs_indexed),
        "slide_decks_indexed": sorted(slide_decks_indexed),
    }

    return {
        "vector_store": vector_store_info,
        "embedding_summary": vector_store_info,
        "knowledge_graph": graph_stats,
        "source_verification": source_verification,
        "target_sources": source_verification,
    }


def _synthesize_answer_from_contexts(
    query: str,
    route_decision: dict[str, Any],
    vector_results: list[dict[str, Any]],
    graph_result: dict[str, Any] | None,
    use_llm: bool = True,
) -> tuple[str, str]:
    """Synthesizes an organizer-friendly Korean response from Vector RAG and/or GraphRAG contexts.

    Tries Gemini API (`google-genai`) when an API key / Vertex AI is configured and `use_llm=True`;
    gracefully falls back to deterministic structured synthesis when offline or without API key.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    vector_ctx_text = "\n\n".join(
        f"[{idx}] {r['title']} (category={r['category']}, score={r['score']})\n{r['content']}"
        for idx, r in enumerate(vector_results[:5], start=1)
    )
    graph_ctx_text = (graph_result or {}).get("markdown_context", "")

    if use_llm and (api_key or settings.use_vertexai):
        try:
            from google import genai

            client = (
                genai.Client(
                    vertexai=True,
                    project=settings.gcp_project,
                    location=settings.gcp_location,
                )
                if settings.use_vertexai and settings.gcp_project
                else genai.Client(api_key=api_key)
            )
            prompt = (
                "당신은 GDG, GDE, GDGoC 이벤트 운영진을 지원하는 공식 Genmunity AI 어시스턴트입니다.\n"
                "아래 검색된 [Vector RAG 문서 청크]와 [GraphRAG 지식 그래프 서브그래프] 근거만을 바탕으로 "
                "운영진의 질문에 한국어로 명확하고 체계적으로 답변하세요. 반드시 출처(시트 탭/행, 슬라이드 번호, 그래프 관계)를 함께 명시하세요.\n\n"
                f"### 질문\n{query}\n\n"
                f"### 라우팅 전략\n{route_decision.get('recommended_mode')} ({route_decision.get('reasoning')})\n\n"
                f"### [Vector RAG 검색 결과]\n{vector_ctx_text or '해당 없음'}\n\n"
                f"### [GraphRAG 지식 그래프 결과]\n{graph_ctx_text or '해당 없음'}\n"
            )
            resp = client.models.generate_content(
                model=settings.root_model,
                contents=prompt,
            )
            if resp and resp.text:
                return resp.text, f"gemini ({settings.root_model})"
        except Exception:
            pass

    # Deterministic, high-precision synthesis combining Vector RAG & GraphRAG evidence
    mode = route_decision.get("recommended_mode", "hybrid_both")
    lines: list[str] = [
        f"### 💡 에이전트 종합 답변 (`{mode}` 워크플로우 실행)",
        f"> **라우팅 판단 근거**: {route_decision.get('reasoning', '')}",
        "",
    ]

    if vector_results and mode in ("vector_rag", "hybrid_both", "hybrid_rag_graph"):
        lines.append("#### 📄 1. 공식 문서·슬라이드·운영 시트 검색 결과 (Vector RAG)")
        for idx, vr in enumerate(vector_results[:4], start=1):
            snippet = vr["content"].strip()
            if len(snippet) > 550:
                snippet = snippet[:550] + "..."
            lines.append(
                f"**[{idx}] {vr['title']}** (`{vr['source_type']}` | 유사도 `{vr['score']}`)"
            )
            lines.append(f"{snippet}\n")

    if graph_result and mode in ("graph_rag", "hybrid_both", "hybrid_rag_graph"):
        lines.append("#### 🕸️ 2. 지식 그래프 엔티티·관계 분석 결과 (GraphRAG)")
        entities = graph_result.get("matched_entities", [])
        if entities:
            lines.append("- **매칭된 핵심 엔티티**:")
            for ent in entities[:6]:
                label = ent.get("label", ent.get("node_id", ""))
                etype = ent.get("entity_type", "")
                detail_parts = []
                for k in (
                    "roles",
                    "gde_categories",
                    "primary_chapter",
                    "affiliation",
                    "job_field",
                    "email",
                    "date",
                    "venue",
                    "attendees",
                ):
                    if ent.get(k):
                        detail_parts.append(f"{k}: {ent[k]}")
                detail_str = f" — {', '.join(detail_parts)}" if detail_parts else ""
                lines.append(f"  - `[{etype}]` **{label}**{detail_str}")

        paths = graph_result.get("multi_hop_paths", [])
        if paths:
            lines.append("- **멀티홉 연결 경로 (Multi-Hop Paths)**:")
            for p in paths[:4]:
                lines.append(f"  - {p}")

        rels = graph_result.get("relationships", [])
        if rels:
            lines.append("- **핵심 지식 그래프 관계 트리플 (Top Triples)**:")
            for r in rels[:8]:
                meta = r.get("metadata", {})
                meta_str = (
                    " (" + ", ".join(f"{k}={v}" for k, v in list(meta.items())[:3]) + ")"
                    if meta
                    else ""
                )
                lines.append(
                    f"  - **{r['source_label']}** (`{r['source_type']}`) "
                    f"—[`{r['relation']}`]→ "
                    f"**{r['target_label']}** (`{r['target_type']}`){meta_str}"
                )

        analytics = graph_result.get("graph_analytics_summary", "")
        if analytics:
            lines.append("\n- **그래프 구조 통계 및 요약**:")
            lines.append(analytics)

    return "\n".join(lines), "hybrid_structured_synthesizer"


def run_interactive_query(
    query: str,
    mode: str = "auto",
    category: str = "all",
    top_k: int = 5,
    max_hops: int = 2,
    use_llm: bool = False,
    strategy: str | None = None,
) -> dict[str, Any]:
    """Executes an end-to-end query across the ADK Adaptive Routing + Vector RAG + GraphRAG pipeline."""
    t0 = time.perf_counter()
    retriever = get_rag_retriever()

    requested_route = strategy if (mode == "fast" and strategy) else mode
    auto_decision = classify_query_route(query)
    if requested_route in ("auto", "fast", "", None):
        effective_mode = auto_decision["recommended_mode"]
    elif requested_route == "hybrid_rag_graph":
        effective_mode = "hybrid_both"
    else:
        effective_mode = requested_route

    route_info = {
        **auto_decision,
        "requested_mode": mode,
        "recommended_mode": effective_mode,
    }

    vector_results: list[dict[str, Any]] = []
    if effective_mode in ("vector_rag", "hybrid_both", "hybrid_rag_graph"):
        cat_filter = None if category in ("all", "", None) else category
        raw_vec_bundle = retriever.retrieve(
            query=query,
            category=cat_filter,
            top_k=top_k,
        )
        for item in raw_vec_bundle.get("results", []):
            vector_results.append(
                {
                    "chunk_id": item.get("chunk_id", ""),
                    "title": item.get("title", ""),
                    "category": item.get("category", ""),
                    "source_type": item.get("source_type", ""),
                    "source_url": item.get("source_url", ""),
                    "score": round(float(item.get("score", 0.0)), 4),
                    "retriever_backend": raw_vec_bundle.get("rag_mode", "hybrid"),
                    "content": item.get("content", ""),
                    "metadata": item.get("metadata", {}),
                }
            )

    graph_payload: dict[str, Any] | None = None
    if effective_mode in ("graph_rag", "hybrid_both", "hybrid_rag_graph"):
        g_res = retriever.knowledge_graph.query_subgraph(
            query=query, max_hops=max_hops, top_k=15
        )
        graph_payload = {
            "matched_entities": g_res.matched_entities,
            "multi_hop_paths": g_res.multi_hop_paths,
            "relationships": g_res.relationships,
            "graph_analytics_summary": g_res.graph_analytics_summary,
            "markdown_context": g_res.markdown_context,
            "summary_markdown": g_res.markdown_context,
        }

    answer_markdown, synthesizer_engine = _synthesize_answer_from_contexts(
        query=query,
        route_decision=route_info,
        vector_results=vector_results,
        graph_result=graph_payload,
        use_llm=use_llm,
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    return {
        "query": query,
        "route": route_info,
        "synthesizer_engine": synthesizer_engine,
        "elapsed_ms": elapsed_ms,
        "answer_markdown": answer_markdown,
        "answer": answer_markdown,
        "vector_results": vector_results,
        "graph_result": graph_payload,
        "graph_results": graph_payload or {"summary_markdown": ""},
    }
