"""Interactive Web UI Playground & FastAPI Router for testing ADK Vector RAG, GraphRAG, and A2A.

Can be mounted directly onto any FastAPI app (`app.include_router(playground_router)`),
providing:
- `GET /playground`: Interactive Web UI for testing Organizer Q&A, inspecting Vector RAG chunks,
  exploring Knowledge Graph triples, and verifying data crawling & embedding status.
- `GET /api/rag/audit`: Real-time audit of crawled sources, 768-dim embeddings, and Knowledge Graph stats.
- `GET /api/rag/sample-questions`: Returns the 8 realistic GDG/GDE organizer sample questions.
- `POST /api/rag/query`: Executes a query through the ADK Adaptive Routing + Vector RAG + GraphRAG pipeline.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from community_hub_agent.sample_questions import (
    ORGANIZER_SAMPLE_QUESTIONS,
    get_ingestion_and_embedding_audit,
    run_interactive_query,
)

playground_router = APIRouter(tags=["RAG & GraphRAG Playground"])


class RagQueryRequest(BaseModel):
    query: str
    mode: str = "auto"
    strategy: str | None = None
    category: str = "all"
    top_k: int = 5
    max_hops: int = 2
    use_llm: bool = False


@playground_router.get("/api/rag/audit")
async def api_rag_audit() -> JSONResponse:
    """Returns real-time verification of all crawled data sources, embeddings, and Knowledge Graph."""
    return JSONResponse(get_ingestion_and_embedding_audit())


@playground_router.get("/api/rag/sample-questions")
async def api_sample_questions() -> JSONResponse:
    """Returns the 8 realistic GDG/GDE organizer sample questions."""
    return JSONResponse({"questions": ORGANIZER_SAMPLE_QUESTIONS})


@playground_router.post("/api/rag/query")
async def api_rag_query(req: RagQueryRequest) -> JSONResponse:
    """Executes an organizer query against Vector RAG, GraphRAG, or Hybrid workflow."""
    result = run_interactive_query(
        query=req.query,
        mode=req.mode,
        strategy=req.strategy,
        category=req.category,
        top_k=req.top_k,
        max_hops=req.max_hops,
        use_llm=req.use_llm,
    )
    return JSONResponse(result)


PLAYGROUND_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Genmunity · GDG · GDE Community Hub RAG & GraphRAG 테스트 콘솔</title>
  <style>
    :root {
      --bg: #0b1020;
      --card: #131b31;
      --card-hover: #192340;
      --border: #263459;
      --text: #eef2ff;
      --muted: #94a3b8;
      --blue: #4285f4;
      --green: #34a853;
      --yellow: #fbbc04;
      --red: #ea4335;
      --purple: #a855f7;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
    }
    header {
      background: linear-gradient(90deg, #0f172a 0%, #172554 100%);
      border-bottom: 1px solid var(--border);
      padding: 16px 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-dots {
      display: flex;
      gap: 5px;
    }
    .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    .dot.b { background: var(--blue); }
    .dot.r { background: var(--red); }
    .dot.y { background: var(--yellow); }
    .dot.g { background: var(--green); }
    .brand h1 {
      font-size: 1.2rem;
      margin: 0;
      font-weight: 700;
    }
    .nav-links {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .nav-links a {
      color: var(--text);
      text-decoration: none;
      font-size: 0.85rem;
      padding: 7px 13px;
      border-radius: 8px;
      background: rgba(255,255,255,0.06);
      border: 1px solid var(--border);
      transition: 0.15s;
    }
    .nav-links a:hover {
      background: rgba(66,133,244,0.2);
      border-color: var(--blue);
    }
    .container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 22px 24px 60px;
    }
    .grid-top {
      display: grid;
      grid-template-columns: 1.35fr 1fr;
      gap: 18px;
      margin-bottom: 20px;
    }
    @media (max-width: 1024px) {
      .grid-top, .results-grid { grid-template-columns: 1fr !important; }
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px 20px;
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 1.02rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .stat-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
    }
    .pill {
      font-size: 0.78rem;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(66,133,244,0.14);
      border: 1px solid rgba(66,133,244,0.35);
      color: #bfdbfe;
      font-weight: 600;
    }
    .pill.green {
      background: rgba(52,168,83,0.15);
      border-color: rgba(52,168,83,0.4);
      color: #86efac;
    }
    .pill.purple {
      background: rgba(168,85,247,0.15);
      border-color: rgba(168,85,247,0.4);
      color: #d8b4fe;
    }
    .source-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.81rem;
    }
    .source-table th, .source-table td {
      text-align: left;
      padding: 7px 8px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .source-table th { color: var(--muted); font-weight: 600; }
    .badge-ok {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      background: rgba(52,168,83,0.2);
      color: #4ade80;
      font-weight: 700;
    }
    .samples-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .sample-btn {
      text-align: left;
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 11px 13px;
      border-radius: 10px;
      cursor: pointer;
      transition: 0.15s;
    }
    .sample-btn:hover {
      background: var(--card-hover);
      border-color: var(--blue);
      transform: translateY(-1px);
    }
    .sample-badge {
      font-size: 0.7rem;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 5px;
      display: inline-block;
      margin-bottom: 5px;
    }
    .sample-badge.vector_rag { background: rgba(66,133,244,0.22); color: #93c5fd; }
    .sample-badge.graph_rag { background: rgba(168,85,247,0.22); color: #d8b4fe; }
    .sample-badge.hybrid_both { background: rgba(52,168,83,0.22); color: #86efac; }
    .sample-title {
      font-size: 0.87rem;
      font-weight: 700;
      margin-bottom: 3px;
    }
    .sample-desc {
      font-size: 0.76rem;
      color: var(--muted);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .query-controls {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 12px;
      align-items: center;
    }
    select, input[type="text"] {
      background: #0b1120;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 10px 13px;
      font-size: 0.9rem;
    }
    input[type="text"] {
      flex: 1;
      min-width: 280px;
    }
    button.primary {
      background: var(--blue);
      color: white;
      border: none;
      border-radius: 9px;
      padding: 10px 18px;
      font-weight: 700;
      cursor: pointer;
      font-size: 0.9rem;
    }
    button.primary:hover { background: #2563eb; }
    .results-grid {
      display: grid;
      grid-template-columns: 1.15fr 1fr 1fr;
      gap: 16px;
      margin-top: 18px;
    }
    .result-box {
      background: #0d1426;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 13px;
      max-height: 580px;
      overflow-y: auto;
      font-size: 0.85rem;
      white-space: pre-wrap;
    }
    .chunk-card, .triple-card {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 9px;
      white-space: normal;
    }
    .chunk-header {
      display: flex;
      justify-content: space-between;
      font-weight: 700;
      font-size: 0.82rem;
      margin-bottom: 5px;
      color: #93c5fd;
    }
    .chunk-body {
      font-size: 0.78rem;
      color: #cbd5e1;
      white-space: pre-wrap;
    }
    .triple-rel {
      color: #facc15;
      font-family: monospace;
      font-weight: 700;
      padding: 0 4px;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-dots">
        <span class="dot b"></span><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
      </div>
      <h1>Genmunity · GDG/GDE Community Hub ADK (Vector RAG + GraphRAG + A2A) 테스트 콘솔</h1>
    </div>
    <div class="nav-links">
      <a href="/">🏠 Genmunity 대시보드</a>
      <a href="/playground">🧪 RAG · GraphRAG · A2A 테스트 콘솔</a>
      <a href="/.well-known/agent.json" target="_blank">🤖 A2A Agent Card (JSON)</a>
      <a href="/api/rag/audit" target="_blank">📊 크롤링·임베딩 감사 API</a>
    </div>
  </header>

  <div class="container">
    <!-- Top Section: Ingestion/Embedding Audit & Architecture Status -->
    <div class="grid-top">
      <div class="panel">
        <h2>
          <span>✅ 데이터 크롤링 · 파싱 · 768차원 벡터 임베딩 검증 현황</span>
          <span class="badge-ok" id="embedding-badge">검증 중...</span>
        </h2>
        <div class="stat-pills" id="vector-stats-pills"></div>
        <table class="source-table">
          <thead>
            <tr>
              <th>데이터 소스</th>
              <th>수집·파싱 방식</th>
              <th>청크 수</th>
              <th>임베딩</th>
            </tr>
          </thead>
          <tbody id="source-audit-tbody"></tbody>
        </table>
      </div>

      <div class="panel">
        <h2>
          <span>🕸️ Knowledge Graph (GraphRAG) 멀티홉 그래프 구축 현황</span>
          <span class="badge-ok" id="graph-badge">로드 중...</span>
        </h2>
        <div class="stat-pills" id="graph-stats-pills"></div>
        <div style="font-size:0.8rem; color:var(--muted); margin-bottom:8px;">
          <strong>ADK Multi-Agent Adaptive Workflow</strong>:
          <code>QueryRouterAgent</code> ➔ (<code>VectorRagAgent</code> || <code>GraphRagAgent</code>) ➔ <code>ResponseSynthesizerAgent</code>
        </div>
        <div class="result-box" id="graph-breakdown-box" style="max-height:210px; font-size:0.79rem;"></div>
      </div>
    </div>

    <!-- Sample Questions Section -->
    <div class="panel" style="margin-bottom: 20px;">
      <h2>
        <span>🎯 실제 GDG·GDE·GDGoC 운영진 시나리오별 원클릭 테스트 샘플 (8종)</span>
        <span style="font-size:0.78rem; color:var(--muted);">카드를 클릭하면 즉시 에이전트에게 질문하고 결과를 비교합니다</span>
      </h2>
      <div class="samples-grid" id="sample-questions-grid"></div>
    </div>

    <!-- Interactive Query Console -->
    <div class="panel">
      <h2>
        <span>💬 에이전트 질의 테스트 (ADK Vector RAG / GraphRAG / Hybrid / A2A JSON-RPC)</span>
        <span id="route-status-pill" class="pill">대기 중</span>
      </h2>
      <div class="query-controls">
        <select id="mode-select">
          <option value="auto">🤖 Auto (ADK QueryRouter 자동 판단)</option>
          <option value="vector_rag">📄 Vector RAG 단독 (문서/슬라이드/시트 청크)</option>
          <option value="graph_rag">🕸️ GraphRAG 단독 (엔티티/관계/멀티홉 경로)</option>
          <option value="hybrid_both">⚡ Hybrid 병렬 (Vector RAG + GraphRAG 동시 결합)</option>
          <option value="a2a_rpc">🔗 A2A JSON-RPC 2.0 (POST / message/send 프로토콜)</option>
        </select>
        <select id="category-select">
          <option value="all">전체 카테고리 (All)</option>
          <option value="devfest">DevFest</option>
          <option value="build_with_ai">Build with AI</option>
          <option value="kr_organizer">국내 운영진 (KR Organizer & GDE)</option>
        </select>
        <label style="font-size:0.82rem; color:var(--muted); display:flex; align-items:center; gap:5px;">
          <input type="checkbox" id="use-llm-checkbox" /> Gemini 실시간 생성 사용
        </label>
      </div>
      <div class="query-controls">
        <input type="text" id="query-input" placeholder="운영진 질문을 입력하세요 (예: 국내 AI·Cloud·Flutter 분야 GDE 명단과 챕터 발표 이력을 알려줘)" />
        <button class="primary" onclick="executeQuery()">질문 실행 (Run)</button>
      </div>

      <div class="results-grid">
        <div>
          <h3 style="font-size:0.92rem; margin:0 0 8px;">1️⃣ 에이전트 종합 답변 (Synthesized Answer)</h3>
          <div class="result-box" id="answer-box">상단 샘플 질문 카드를 클릭하거나 질문을 입력해 실행하세요.</div>
        </div>
        <div>
          <h3 style="font-size:0.92rem; margin:0 0 8px;">2️⃣ Vector RAG 검색 청크 (Top-K Chunks & Scores)</h3>
          <div class="result-box" id="vector-box">Vector RAG 검색 결과가 여기에 표시됩니다.</div>
        </div>
        <div>
          <h3 style="font-size:0.92rem; margin:0 0 8px;">3️⃣ GraphRAG 지식 그래프 서브그래프 (Entities & Triples)</h3>
          <div class="result-box" id="graph-box">GraphRAG 매칭 엔티티, 멀티홉 경로 및 관계 트리플이 여기에 표시됩니다.</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    async function loadAuditAndSamples() {
      const [auditRes, sampleRes] = await Promise.all([
        fetch('/api/rag/audit').then(r => r.json()),
        fetch('/api/rag/sample-questions').then(r => r.json())
      ]);

      // Render Vector Store stats
      const vs = auditRes.vector_store;
      document.getElementById('embedding-badge').textContent =
        `${vs.embedded_chunks}/${vs.total_chunks} 청크 임베딩 완료 (${vs.embedding_coverage_pct}%)`;
      document.getElementById('vector-stats-pills').innerHTML = `
        <span class="pill green">총 청크: ${vs.total_chunks}개</span>
        <span class="pill">임베딩 차원: ${vs.embedding_dimensions}차원 (${vs.embedding_model})</span>
        <span class="pill">파싱된 시트 탭: ${vs.sheet_tabs_count}개 탭</span>
        <span class="pill">파싱된 슬라이드 덱: ${vs.slide_decks_indexed.length}개</span>
      `;

      const tbody = document.getElementById('source-audit-tbody');
      tbody.innerHTML = auditRes.source_verification.map(s => `
        <tr>
          <td><strong>${s.name}</strong></td>
          <td style="color:var(--muted);">${s.method}</td>
          <td><strong>${s.chunks_count}</strong>개</td>
          <td><span class="badge-ok">768-d Embedded</span></td>
        </tr>
      `).join('');

      // Render Graph stats
      const kg = auditRes.knowledge_graph;
      document.getElementById('graph-badge').textContent =
        `${kg.total_nodes} Nodes · ${kg.total_edges} Edges`;
      document.getElementById('graph-stats-pills').innerHTML = `
        <span class="pill purple">총 노드: ${kg.total_nodes}개</span>
        <span class="pill purple">총 관계 엣지: ${kg.total_edges}개</span>
        <span class="pill green">인물(운영진/GDE): ${kg.node_types.Person || 0}명</span>
        <span class="pill">챕터(GDG/GDGoC): ${kg.node_types.Chapter || 0}개</span>
        <span class="pill">이벤트: ${kg.node_types.Event || 0}건</span>
      `;
      document.getElementById('graph-breakdown-box').textContent =
        `[노드 타입 분포]\n` +
        Object.entries(kg.node_types).map(([k, v]) => `• ${k}: ${v}개`).join('\n') +
        `\n\n[엣지(관계) 타입 분포]\n` +
        Object.entries(kg.edge_types).map(([k, v]) => `• ${k}: ${v}개`).join('\n');

      // Render Sample Questions
      const grid = document.getElementById('sample-questions-grid');
      grid.innerHTML = sampleRes.questions.map(q => `
        <button class="sample-btn" onclick="runSampleQuestion(${JSON.stringify(q.question).replace(/"/g, '&quot;')})">
          <span class="sample-badge ${q.expected_route}">${q.badge}</span>
          <div class="sample-title">${q.title}</div>
          <div class="sample-desc">${q.question}</div>
        </button>
      `).join('');

      // Run Q5 (GDE matching) or Q1 by default so the user sees immediate results
      if (sampleRes.questions.length > 0) {
        runSampleQuestion(sampleRes.questions[4].question);
      }
    }

    function runSampleQuestion(questionText) {
      document.getElementById('query-input').value = questionText;
      executeQuery();
    }

    async function executeQuery() {
      const query = document.getElementById('query-input').value.trim();
      if (!query) return;
      const mode = document.getElementById('mode-select').value;
      const category = document.getElementById('category-select').value;
      const useLlm = document.getElementById('use-llm-checkbox').checked;

      const statusPill = document.getElementById('route-status-pill');
      statusPill.textContent = '검색 및 그래프 추론 중...';
      document.getElementById('answer-box').textContent = '⏳ 질의를 분석하고 Vector RAG 및 Knowledge Graph를 검색 중입니다...';

      if (mode === 'a2a_rpc') {
        const rpcPayload = {
          jsonrpc: "2.0",
          id: "web-ui-" + Date.now(),
          method: "message/send",
          params: {
            message: {
              role: "user",
              parts: [{ type: "text", text: query }]
            },
            metadata: { category: category, top_k: 5 }
          }
        };
        const res = await fetch('/a2a', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(rpcPayload)
        }).then(r => r.json());

        statusPill.textContent = 'A2A JSON-RPC 2.0 응답 완료';
        const parts = (res.result && res.result.parts) || [];
        const artifacts = (res.result && res.result.artifacts) || [];
        const answerText = parts[0]?.text || artifacts[0]?.parts?.[0]?.text || JSON.stringify(res, null, 2);
        const citations = parts[1]?.data?.citations || artifacts[1]?.parts?.[0]?.data?.citations || [];
        document.getElementById('answer-box').textContent = answerText;
        document.getElementById('vector-box').innerHTML = citations.map((c, i) => `
          <div class="chunk-card">
            <div class="chunk-header"><span>[${i+1}] ${c.title}</span><span>score: ${c.score}</span></div>
            <div class="chunk-body">category: ${c.category}\nURL: ${c.source_url}</div>
          </div>
        `).join('') || 'A2A Citation 없음';
        document.getElementById('graph-box').textContent = JSON.stringify(res.result, null, 2);
        return;
      }

      const data = await fetch('/api/rag/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          mode: mode,
          category: category,
          top_k: 5,
          max_hops: 2,
          use_llm: useLlm
        })
      }).then(r => r.json());

      statusPill.textContent =
        `라우팅: ${data.route.recommended_mode.toUpperCase()} (${data.elapsed_ms} ms)`;
      document.getElementById('answer-box').textContent = data.answer_markdown;

      // Render Vector Chunks
      if (data.vector_results && data.vector_results.length > 0) {
        document.getElementById('vector-box').innerHTML = data.vector_results.map((c, i) => `
          <div class="chunk-card">
            <div class="chunk-header">
              <span>[${i+1}] ${c.title}</span>
              <span>유사도: ${c.score}</span>
            </div>
            <div style="font-size:0.73rem; color:var(--muted); margin-bottom:4px;">
              분류: <code>${c.category}</code> · 타입: <code>${c.source_type}</code>
            </div>
            <div class="chunk-body">${c.content}</div>
          </div>
        `).join('');
      } else {
        document.getElementById('vector-box').textContent =
          '이 질문은 GraphRAG 전용 모드로 라우팅되어 Vector 청크 검색을 생략했습니다. (모드를 Hybrid 또는 Vector RAG로 변경하면 확인 가능)';
      }

      // Render GraphRAG Subgraph
      if (data.graph_result) {
        const gr = data.graph_result;
        const entitiesHtml = (gr.matched_entities || []).slice(0, 6).map(e => `
          <div class="triple-card">
            <strong>[${e.entity_type}] ${e.label}</strong>
            <div style="font-size:0.75rem; color:var(--muted);">
              ${e.roles ? '역할: ' + e.roles.join(', ') + ' | ' : ''}
              ${e.gde_categories && e.gde_categories.length ? 'GDE 분야: ' + e.gde_categories.join(', ') + ' | ' : ''}
              ${e.primary_chapter ? '챕터: ' + e.primary_chapter + ' | ' : ''}
              ${e.affiliation ? '소속: ' + e.affiliation + ' | ' : ''}
              ${e.email ? '이메일: ' + e.email : ''}
            </div>
          </div>
        `).join('');

        const triplesHtml = (gr.relationships || []).slice(0, 12).map(r => `
          <div class="triple-card" style="font-size:0.78rem;">
            <strong>${r.source_label}</strong> <span style="color:var(--muted);">(${r.source_type})</span>
            <span class="triple-rel">—[${r.relation}]→</span>
            <strong>${r.target_label}</strong> <span style="color:var(--muted);">(${r.target_type})</span>
          </div>
        `).join('');

        document.getElementById('graph-box').innerHTML =
          `<div style="margin-bottom:8px; font-weight:700; color:#d8b4fe;">매칭된 시드 엔티티 (${(gr.matched_entities || []).length}개)</div>` +
          (entitiesHtml || '<div style="color:var(--muted); margin-bottom:8px;">직접 매칭된 단일 엔티티 없음 (전역 그래프 통계 참조)</div>') +
          `<div style="margin:10px 0 8px; font-weight:700; color:#86efac;">서브그래프 관계 트리플 (${(gr.relationships || []).length}개)</div>` +
          triplesHtml;
      } else {
        document.getElementById('graph-box').textContent =
          '이 질문은 Vector RAG 전용 모드로 라우팅되어 지식 그래프 탐색을 생략했습니다. (모드를 Hybrid 또는 GraphRAG로 변경하면 확인 가능)';
      }
    }

    window.addEventListener('DOMContentLoaded', loadAuditAndSamples);
  </script>
</body>
</html>
"""


@playground_router.get("/playground", response_class=HTMLResponse)
async def serve_playground_ui() -> HTMLResponse:
    """Serves the interactive Web UI for testing ADK Vector RAG, GraphRAG, and A2A."""
    return HTMLResponse(content=PLAYGROUND_HTML)
