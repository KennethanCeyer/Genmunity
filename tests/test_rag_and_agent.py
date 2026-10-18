"""Unit & integration tests for Community Hub Ingestion, Excel/Slides parsing, Vector RAG, GraphRAG, ADK Workflows, and A2A."""

from __future__ import annotations

import httpx
import pytest
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from community_hub_agent.a2a_server import a2a_app
from community_hub_agent.agent import (
    graph_rag_specialist,
    hybrid_rag_graph_workflow,
    root_agent,
    vector_rag_specialist,
)
from community_hub_agent.config import settings
from community_hub_agent.ingestion.hub_crawler import CommunityHubCrawler
from community_hub_agent.ingestion.sheets_parser import (
    GoogleSheetsParser,
    extract_spreadsheet_id,
)
from community_hub_agent.ingestion.slides_parser import (
    parse_slide_url_metadata,
)
from community_hub_agent.ingestion.slack_parser import SlackChannelParser
from community_hub_agent.tools import (
    adaptive_hybrid_search,
    classify_rag_vs_graphrag,
    lookup_kr_organizer_sheet,
    query_community_knowledge_graph,
    search_build_with_ai_knowledge,
    search_community_hub_rag,
    search_devfest_knowledge,
)


def test_parse_build_with_ai_slide_url_and_resourcekey() -> None:
    url = "https://docs.google.com/presentation/d/1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE/edit?usp=sharing&resourcekey=0-x_2s2Y1o88-1mNOmoQipTA"
    pres_id, resource_key = parse_slide_url_metadata(url)
    assert pres_id == "1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE"
    assert resource_key == "0-x_2s2Y1o88-1mNOmoQipTA"


def test_devfest_hub_discovers_all_internal_google_slides() -> None:
    sample_devfest_html = """
    <html>
      <body>
        <article class="devsite-article-body">
          <h1>DevFest 2026 Organizer Guide</h1>
          <h2>1. Event Planning & Playbook</h2>
          <p>Review the official organizer playbook slide deck before registering your event:</p>
          <a href="https://docs.google.com/presentation/d/1AbCdEfGhIjKlMnOpQrStUvWxYz123456/edit?usp=sharing">DevFest Playbook Slides</a>
          <h2>2. Brand & Speaker Templates</h2>
          <iframe src="https://docs.google.com/presentation/d/1ZyXwVuTsRqPoNmLkJiHgFeDcBa654321/embed?resourcekey=0-abc123XYZ"></iframe>
        </article>
      </body>
    </html>
    """
    crawler = CommunityHubCrawler()
    page_doc = crawler.parse_html(
        html=sample_devfest_html,
        url="https://developers.google.com/community/community-hub/event-series/devfest",
        category="devfest",
    )
    assert page_doc.title == "DevFest 2026 Organizer Guide"
    assert len(page_doc.sections) >= 2
    assert len(page_doc.discovered_slide_urls) == 2
    assert any(
        "1AbCdEfGhIjKlMnOpQrStUvWxYz123456" in u
        for u in page_doc.discovered_slide_urls
    )
    assert any(
        "1ZyXwVuTsRqPoNmLkJiHgFeDcBa654321" in u and "resourcekey=0-abc123XYZ" in u
        for u in page_doc.discovered_slide_urls
    )


def test_parse_kr_organizer_local_xlsx_all_11_tabs() -> None:
    sheet_url = "https://docs.google.com/spreadsheets/d/146hMwkpdORd9njiWo2Yg6yZ7X40igZ3EiIk_kO0PJ34/edit?usp=sharing"
    sheet_id = extract_spreadsheet_id(sheet_url)
    assert sheet_id == "146hMwkpdORd9njiWo2Yg6yZ7X40igZ3EiIk_kO0PJ34"

    parser = GoogleSheetsParser()
    doc = parser.parse_from_local_xlsx(
        file_path=settings.kr_organizer_xlsx_path,
        spreadsheet_id=sheet_id,
        source_url=sheet_url,
    )
    assert doc is not None
    assert len(doc.rows) >= 160
    sheet_titles = {r.sheet_title for r in doc.rows}
    assert "26 DevFest" in sheet_titles
    assert "26 IOEX" in sheet_titles
    assert "26 BwAI" in sheet_titles
    assert "26 Active Rate" in sheet_titles


def test_rag_tools_retrieve_devfest_bwai_and_kr_sheets() -> None:
    devfest_res = search_devfest_knowledge("DevFest 로고 표기 규칙과 준비 타임라인")
    assert devfest_res["total_results"] > 0
    assert all(r["category"] == "devfest" for r in devfest_res["results"])

    bwai_res = search_build_with_ai_knowledge("Build with AI 크레딧 신청 기한과 핸즈온 워크숍")
    assert bwai_res["total_results"] > 0
    assert all(r["category"] == "build_with_ai" for r in bwai_res["results"])

    kr_res = lookup_kr_organizer_sheet("GDG Incheon 26 Active Rate 오프보딩")
    assert kr_res["total_results"] > 0
    assert all(r["category"] == "kr_organizer" for r in kr_res["results"])

    all_res = search_community_hub_rag("Vertex AI Search와 모듈형 커스텀 RAG 차이")
    assert all_res["total_results"] > 0


def test_graph_rag_bilingual_entity_resolution_and_cohosting() -> None:
    # 1. Bilingual person resolution: PARK JAICHANG (26 Active Rate) <-> 박제창 (24~26 Events)
    person_graph = query_community_knowledge_graph("박제창 오거나이저 및 연사 활동 이력", max_hops=2)
    assert person_graph["graph_stats"]["total_nodes"] > 200
    matched_labels = [n["label"] for n in person_graph["matched_seed_nodes"]]
    assert any("박제창" in lbl and "PARK JAICHANG" in lbl for lbl in matched_labels)
    relations = {t["relation"] for t in person_graph["subgraph_triples"]}
    assert "ORGANIZER_OF" in relations or "PARTICIPATED_AS_ORGANIZER" in relations
    assert "SPOKE_AT" in relations

    # 2. Chapter co-hosting network (CO_HOSTED_WITH)
    cohost_graph = query_community_knowledge_graph("GDG Incheon 공동 주최 연합 챕터 관계망", max_hops=2)
    assert len(cohost_graph["co_hosting_collaborations"]) > 0
    assert "GDG Incheon" in cohost_graph["summary_markdown"]


def test_slack_organizers_channel_rag_and_graphrag() -> None:
    # 1. SlackChannelParser parses threads, pins, and discovers the 2026 Offsite Google Slides deck
    parser = SlackChannelParser()
    slack_doc = parser.parse()
    assert slack_doc is not None
    assert slack_doc.channel_id == "C04E1UAAY"
    assert len(slack_doc.threads) >= 28
    assert sum(1 for t in slack_doc.threads if t.is_pinned) == 3
    assert any(
        "1fnQNauWcxgt5eqhTAuaBGn2giNQU6f_f_fv3R7nAvp4" in url
        for url, _ in slack_doc.discovered_slide_urls
    )

    # 2. Vector RAG retrieves Slack #organizers announcements via lookup_kr_organizer_sheet
    devfest_budget = lookup_kr_organizer_sheet("2026 DevFest 지원금 25,000원 증액")
    assert any(
        "25,000" in r["content"] and r["source_type"] == "slack_channel"
        for r in devfest_budget["results"]
    )

    venue_res = lookup_kr_organizer_sheet("서울 AI 허브 양재 100명 무료 대관")
    assert any(
        "서울 AI 허브" in r["content"] and r["source_type"] == "slack_channel"
        for r in venue_res["results"]
    )

    agentathon_res = lookup_kr_organizer_sheet("GDG Incheon 에이전트톤 1조 7조 배포 링크")
    assert any(
        ("downhill-route.vercel.app" in r["content"] or "gdg-fieldagent.vercel.app" in r["content"])
        and r["source_type"] == "slack_channel"
        for r in agentathon_res["results"]
    )

    # 3. Secondary category matching allows search_devfest_knowledge to retrieve Slack DevFest notice
    devfest_cross = search_devfest_knowledge("2026 DevFest 참가자 1인당 지원금 25,000원 증액")
    assert any("25,000" in r["content"] for r in devfest_cross["results"])

    # 4. GraphRAG resolves Slack entities (권나현 -> 서울 AI 허브 무료 대관, GDG Busan 신입 오거나이저)
    nahyun_graph = query_community_knowledge_graph("권나현 서울 AI 허브 무료 대관", max_hops=2)
    relations = {t["relation"] for t in nahyun_graph["subgraph_triples"]}
    assert "ANNOUNCED_FREE_VENUE" in relations or "MANAGES_CHANNEL" in relations

    busan_graph = query_community_knowledge_graph("GDG Busan 황재웅 이재훈 오거나이저", max_hops=2)
    assert "GDG Busan" in busan_graph["summary_markdown"]


def test_adaptive_query_classification_and_hybrid_search() -> None:
    # Case 1: Pure Vector RAG (guidelines / slides / policy)
    c_vec = classify_rag_vs_graphrag("DevFest 로고 표기 규칙과 슬라이드 템플릿 가이드라인 알려줘")
    assert c_vec["strategy"] == "vector_rag"

    # Case 2: Pure GraphRAG (multi-hop network / co-hosting / dual-role)
    c_graph = classify_rag_vs_graphrag("GDG 챕터 간 공동 주최(연합) 네트워크와 오거나이저 겸 연사 관계망 분석해줘")
    assert c_graph["strategy"] == "graph_rag"

    # Case 3: Hybrid RAG + GraphRAG (both relational network + slide/guideline policy)
    c_hybrid = classify_rag_vs_graphrag(
        "GDG Incheon과 공동 주최한 챕터 관계망을 찾고 Build with AI 슬라이드 가이드라인과 정산 규정도 함께 알려줘"
    )
    assert c_hybrid["strategy"] == "hybrid_rag_graph"

    hybrid_res = adaptive_hybrid_search(
        "GDG Incheon과 공동 주최한 챕터 관계망을 찾고 Build with AI 슬라이드 가이드라인과 정산 규정도 함께 알려줘"
    )
    assert hybrid_res["routing"]["strategy"] == "hybrid_rag_graph"
    assert hybrid_res["vector_rag"] is not None
    assert hybrid_res["graph_rag"] is not None


def test_adk_root_agent_and_workflow_agents_structure() -> None:
    assert root_agent.name == "gdg_gde_community_hub_agent"
    sub_names = [sa.name for sa in root_agent.sub_agents]
    assert "devfest_specialist" in sub_names
    assert "build_with_ai_specialist" in sub_names
    assert "kr_organizer_ops_specialist" in sub_names
    assert "vector_rag_specialist" in sub_names
    assert "graph_rag_specialist" in sub_names
    assert "hybrid_rag_graph_workflow" in sub_names

    assert isinstance(vector_rag_specialist, LlmAgent)
    assert isinstance(graph_rag_specialist, LlmAgent)
    assert isinstance(hybrid_rag_graph_workflow, SequentialAgent)
    assert isinstance(hybrid_rag_graph_workflow.sub_agents[0], ParallelAgent)


@pytest.mark.asyncio
async def test_web_playground_audit_and_sample_questions() -> None:
    transport = httpx.ASGITransport(app=a2a_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost:8001"
    ) as client:
        # 1. Interactive Web Playground HTML
        pg_resp = await client.get("/playground")
        assert pg_resp.status_code == 200
        assert "GDG · GDE Community Hub RAG" in pg_resp.text

        # 2. Data Crawling & Embedding Audit API
        audit_resp = await client.get("/api/rag/audit")
        assert audit_resp.status_code == 200
        audit = audit_resp.json()
        assert audit["embedding_summary"]["total_indexed_chunks"] >= 135
        assert audit["embedding_summary"]["embedding_coverage_pct"] == 100.0
        assert audit["embedding_summary"]["embedding_dimension"] == 768
        assert audit["knowledge_graph"]["total_nodes"] >= 400
        assert len(audit["target_sources"]) == 5

        # 3. Organizer Sample Questions API & Execution
        sq_resp = await client.get("/api/rag/sample-questions")
        assert sq_resp.status_code == 200
        questions = sq_resp.json()["questions"]
        assert len(questions) == 8

        for q in questions:
            q_resp = await client.post(
                "/api/rag/query",
                json={
                    "query": q["question"],
                    "mode": "fast",
                    "strategy": "auto",
                    "category": q.get("category", "all"),
                },
            )
            assert q_resp.status_code == 200
            q_data = q_resp.json()
            combined_text = (
                q_data["answer"]
                + " "
                + " ".join(c.get("title", "") + " " + c.get("content", "") for c in q_data["vector_results"])
                + " "
                + q_data["graph_results"].get("summary_markdown", "")
            ).lower()
            matched_kw = [
                kw for kw in q["expected_keywords"] if kw.lower() in combined_text
            ]
            assert len(matched_kw) >= 3, f"Failed keyword check on {q['id']}: {matched_kw}"


@pytest.mark.asyncio
async def test_a2a_agent_card_and_jsonrpc_message_send(monkeypatch: pytest.MonkeyPatch) -> None:
    from community_hub_agent.config import settings
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "use_vertexai", False)
    transport = httpx.ASGITransport(app=a2a_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost:8001"
    ) as client:
        # 1. Check Agent Card discovery includes GraphRAG skill
        card_resp = await client.get("/.well-known/agent-card.json")
        assert card_resp.status_code == 200
        card = card_resp.json()
        assert card["name"] == "gdg_gde_community_hub_agent"
        skill_ids = [s["id"] for s in card["skills"]]
        assert "devfest_community_hub_rag" in skill_ids
        assert "build_with_ai_rag" in skill_ids
        assert "kr_organizer_sheet_lookup" in skill_ids
        assert "community_knowledge_graph_rag" in skill_ids

        # 2. Check dedicated A2A GraphRAG endpoint
        graph_resp = await client.post(
            "/a2a/graph-rag",
            json={"query": "박제창 오거나이저 및 연사 활동", "max_hops": 2},
        )
        assert graph_resp.status_code == 200
        graph_json = graph_resp.json()
        assert len(graph_json["graph_payload"]["subgraph_triples"]) > 0

        # 3. Check A2A JSON-RPC message/send (both / and /a2a)
        rpc_req = {
            "jsonrpc": "2.0",
            "id": "test-a2a-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": "m-1",
                    "parts": [
                        {
                            "kind": "text",
                            "text": "Build with AI 크레딧 신청 기한과 슬라이드 내용 알려줘",
                        }
                    ],
                }
            },
        }
        rpc_resp = await client.post("/a2a", json=rpc_req)
        assert rpc_resp.status_code == 200
        payload = rpc_resp.json()
        assert payload["id"] == "test-a2a-1"
        parts = payload["result"]["parts"]
        assert len(parts) >= 2
        assert "Build with AI" in parts[0]["text"]
        assert len(parts[1]["data"]["citations"]) > 0
