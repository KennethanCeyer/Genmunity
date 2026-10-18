DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Genmunity</title>
  <link rel="icon" type="image/png" sizes="256x256" href="/favicon.png" />
  <link rel="icon" type="image/x-icon" href="/favicon.ico" />
  <link rel="apple-touch-icon" href="/favicon.png" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link href="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css" rel="stylesheet" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Pretendard", sans-serif;
      background-color: #ffffff;
      color: #0f172a;
    }
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 9999px; }

    @keyframes pulse-orb {
      0%, 100% { transform: scale(0.92); opacity: 0.7; }
      50% { transform: scale(1.12); opacity: 1; }
    }
    @keyframes shimmer-text {
      0% { background-position: -200% 0; }
      100% { background-position: 200% 0; }
    }
    @keyframes spin-slow {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    .pulse-orb { animation: pulse-orb 1.4s ease-in-out infinite; }
    .spin-icon { animation: spin-slow 1.1s linear infinite; }
    .shimmer-label {
      background: linear-gradient(90deg, #334155 0%, #2563eb 50%, #334155 100%);
      background-size: 200% auto;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      animation: shimmer-text 2.2s linear infinite;
    }

    .md-prose { font-size: 0.9375rem; line-height: 1.68; color: #1e293b; word-break: break-word; }
    .md-prose p { margin-bottom: 0.65rem; }
    .md-prose p:last-child { margin-bottom: 0; }
    .md-prose h1, .md-prose h2, .md-prose h3 { font-weight: 700; color: #0f172a; margin-top: 0.9rem; margin-bottom: 0.4rem; }
    .md-prose h1 { font-size: 1.15rem; }
    .md-prose h2 { font-size: 1.05rem; }
    .md-prose h3 { font-size: 0.96rem; }
    .md-prose ul { list-style-type: disc; padding-left: 1.25rem; margin-bottom: 0.65rem; }
    .md-prose ol { list-style-type: decimal; padding-left: 1.25rem; margin-bottom: 0.65rem; }
    .md-prose li { margin-bottom: 0.2rem; }
    .md-prose code { background: #f1f5f9; color: #0f172a; padding: 0.12rem 0.35rem; border-radius: 0.3rem; font-size: 0.82rem; font-family: ui-monospace, monospace; }
    .md-prose pre { background: #0f172a; color: #f8fafc; padding: 0.85rem 1rem; border-radius: 0.65rem; overflow-x: auto; margin: 0.65rem 0; font-size: 0.8rem; }
    .md-prose pre code { background: transparent; color: inherit; padding: 0; }
    .md-prose a { color: #2563eb; text-decoration: underline; font-weight: 500; }
    .md-prose table { width: 100%; border-collapse: collapse; margin: 0.65rem 0; font-size: 0.82rem; }
    .md-prose th, .md-prose td { border: 1px solid #e2e8f0; padding: 0.45rem 0.65rem; text-align: left; }
    .md-prose th { background: #f8fafc; font-weight: 600; }
  </style>
</head>
<body class="min-h-screen flex flex-col bg-white text-slate-900">
  <div class="sr-only" aria-hidden="true">Genmunity devstar5011@gcplab.me sniper45han@gmail.com aristojeff@gmail.com 한성민 박제창 AI GDE Flutter GDE WYSIWYG Gemini Image Studio</div>
  <div id="root" class="flex-1 flex flex-col"></div>

  <script type="text/babel">
    const { useState, useEffect, useRef } = React;

    const MCP_ACTIONS = [
      { id: "recommend_speakers", label: "스피커 탐색", tool: "get_target_speakers_tool", args: { query: "AI & Flutter GDE", track: "AI & Flutter" }, icon: "ri-user-star-line" },
      { id: "send_speaker_mail", label: "섭외 메일", tool: "generate_and_send_speaker_emails_tool", args: { speaker_ids: ["spk-001", "spk-002"], event_name: "GDG DevFest 2026 Seoul", send_real_email: true }, icon: "ri-mail-send-line" },
      { id: "create_form", label: "온보딩 폼", tool: "create_speaker_onboarding_form_tool", args: { event_name: "GDG DevFest 2026 Seoul" }, icon: "ri-survey-line" },
      { id: "invite_calendar", label: "캘린더 초대", tool: "invite_speakers_with_form_and_calendar_tool", args: { speaker_ids: ["spk-001", "spk-002"], event_name: "GDG DevFest 2026 Seoul", send_real_email: true }, icon: "ri-calendar-check-line" },
      { id: "rsvp_check", label: "RSVP 조회", tool: "manage_event_rsvp_tool", args: { action: "list", event_id: "devfest-2026-seoul" }, icon: "ri-group-line" },
      { id: "rag_search", label: "지식 검색", tool: "rag_search_tool", args: { query: "DevFest 2026 Seoul" }, icon: "ri-search-eye-line" },
    ];

    function renderMarkdownSafe(text) {
      if (!text) return "";
      try {
        if (window.marked && typeof window.marked.parse === "function") {
          window.marked.setOptions({ breaks: true, gfm: true });
          return window.marked.parse(text);
        }
      } catch (e) {}
      return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br/>");
    }

    function MarkdownContent({ content, isStreaming }) {
      const html = renderMarkdownSafe(content || "");
      return (
        <div className=" relative">
          <div className="md-prose" dangerouslySetInnerHTML={{ __html: html }} />
          {isStreaming && <span className="inline-block w-1.5 h-4 bg-blue-600 ml-1 align-middle animate-pulse rounded-sm" />}
        </div>
      );
    }

    function ComputingIndicator({ computing, steps, currentStatus }) {
      if (!computing && (!steps || steps.length === 0)) return null;
      return (
        <div className="mb-2.5 rounded-xl border border-slate-200/90 bg-slate-50/80 px-3.5 py-2.5 text-xs">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {computing ? (
                <span className="w-2 h-2 rounded-full bg-blue-600 pulse-orb" />
              ) : (
                <i className="ri-check-line text-emerald-600 font-bold" />
              )}
              <span className={computing ? "font-semibold shimmer-label" : "font-medium text-slate-600"}>
                {computing ? (currentStatus || "처리 중...") : `완료 (${steps.length}단계)`}
              </span>
            </div>
            {computing && <i className="ri-loader-4-line text-blue-600 spin-icon" />}
          </div>
          {steps && steps.length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-200/60 flex flex-wrap gap-1.5">
              {steps.map((st, i) => (
                <span
                  key={st.id || i}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[11px] ${
                    st.status === "running"
                      ? "bg-blue-50 border-blue-200 text-blue-700 font-medium"
                      : "bg-white border-slate-200 text-slate-600"
                  }`}
                >
                  {st.status === "running" ? (
                    <i className="ri-loader-4-line spin-icon text-blue-600" />
                  ) : (
                    <i className="ri-check-line text-emerald-600" />
                  )}
                  <span>{st.label || st.tool}</span>
                  {st.elapsed_ms ? <span className="text-slate-400">{st.elapsed_ms}ms</span> : null}
                </span>
              ))}
            </div>
          )}
        </div>
      );
    }

    function McpIntegrationView({ onRunPrompt }) {
      const [selectedAgent, setSelectedAgent] = useState("antigravity");
      const [transportMode, setTransportMode] = useState("remote");
      const [copiedKey, setCopiedKey] = useState(null);

      const remoteMcpUrl = "https://genmunity-858263435030.asia-northeast3.run.app/mcp";
      const a2aCardUrl = "https://genmunity-858263435030.asia-northeast3.run.app/.well-known/agent-card.json";

      const copyToClipboard = async (key, text) => {
        try {
          await navigator.clipboard.writeText(text);
          setCopiedKey(key);
          setTimeout(() => setCopiedKey(prev => (prev === key ? null : prev)), 2000);
        } catch (e) {}
      };

      const AGENT_GUIDES = {
        antigravity: {
          id: "antigravity",
          name: "Antigravity (agy)",
          icon: "ri-terminal-box-line",
          snippets: transportMode === "remote"
            ? [
                {
                  key: "agy-remote",
                  path: "~/.gemini/config/mcp_config.json",
                  guide: "아래 JSON을 추가한 뒤 새 agy 세션에서 바로 자연어로 요청하세요.",
                  code: `{\n  "mcpServers": {\n    "genmunity": {\n      "url": "${remoteMcpUrl}"\n    }\n  }\n}`
                }
              ]
            : [
                {
                  key: "agy-stdio",
                  path: "~/.gemini/config/mcp_config.json",
                  guide: "로컬 Python 가상환경의 Stdio 서버를 직접 연결할 때 사용합니다.",
                  code: `{\n  "mcpServers": {\n    "genmunity": {\n      "command": "/Users/pignose/Genmunity/.venv/bin/python",\n      "args": ["-m", "genmunity_agent.mcp_a2a"],\n      "cwd": "/Users/pignose/Genmunity"\n    }\n  }\n}`
                }
              ]
        },
        claude: {
          id: "claude",
          name: "Claude Code",
          icon: "ri-command-line",
          snippets: transportMode === "remote"
            ? [
                {
                  key: "claude-cli",
                  path: "Terminal — Claude Code CLI",
                  guide: "터미널에 붙여넣어 한 줄로 Genmunity MCP 서버를 등록합니다.",
                  code: `claude mcp add --transport http genmunity ${remoteMcpUrl}`
                },
                {
                  key: "claude-json",
                  path: ".mcp.json",
                  guide: "프로젝트 루트에 두고 팀원과 설정을 공유할 때 사용합니다.",
                  code: `{\n  "mcpServers": {\n    "genmunity": {\n      "type": "http",\n      "url": "${remoteMcpUrl}"\n    }\n  }\n}`
                }
              ]
            : [
                {
                  key: "claude-stdio",
                  path: "Terminal — Claude Code CLI (Stdio)",
                  guide: "로컬 Stdio 모드로 Claude Code에 등록합니다.",
                  code: `claude mcp add genmunity -- /Users/pignose/Genmunity/.venv/bin/python -m genmunity_agent.mcp_a2a`
                }
              ]
        },
        codex: {
          id: "codex",
          name: "OpenAI Codex",
          icon: "ri-code-s-slash-line",
          snippets: transportMode === "remote"
            ? [
                {
                  key: "codex-remote",
                  path: "~/.codex/config.toml",
                  guide: "Codex 글로벌 설정 파일 하단에 아래 블록을 복사해 붙여넣으세요.",
                  code: `[mcp_servers.genmunity]\nurl = "${remoteMcpUrl}"`
                }
              ]
            : [
                {
                  key: "codex-stdio",
                  path: "~/.codex/config.toml",
                  guide: "로컬 Stdio 모드로 Codex에 연결할 때 사용합니다.",
                  code: `[mcp_servers.genmunity]\ncommand = "/Users/pignose/Genmunity/.venv/bin/python"\nargs = ["-m", "genmunity_agent.mcp_a2a"]\ncwd = "/Users/pignose/Genmunity"`
                }
              ]
        },
        cursor: {
          id: "cursor",
          name: "Cursor",
          icon: "ri-cursor-line",
          snippets: transportMode === "remote"
            ? [
                {
                  key: "cursor-remote",
                  path: ".cursor/mcp.json",
                  guide: "Cursor Settings → MCP 또는 프로젝트 루트의 .cursor/mcp.json에 붙여넣으세요.",
                  code: `{\n  "mcpServers": {\n    "genmunity": {\n      "url": "${remoteMcpUrl}"\n    }\n  }\n}`
                }
              ]
            : [
                {
                  key: "cursor-stdio",
                  path: ".cursor/mcp.json",
                  guide: "로컬 Stdio 서버로 Cursor에 연결합니다.",
                  code: `{\n  "mcpServers": {\n    "genmunity": {\n      "command": "/Users/pignose/Genmunity/.venv/bin/python",\n      "args": ["-m", "genmunity_agent.mcp_a2a"]\n    }\n  }\n}`
                }
              ]
        },
        gemini: {
          id: "gemini",
          name: "Gemini CLI",
          icon: "ri-sparkling-2-line",
          snippets: transportMode === "remote"
            ? [
                {
                  key: "gemini-remote",
                  path: "~/.gemini/settings.json",
                  guide: "Gemini CLI 글로벌 설정 파일에 복사해 추가하세요.",
                  code: `{\n  "mcpServers": {\n    "genmunity": {\n      "httpUrl": "${remoteMcpUrl}"\n    }\n  }\n}`
                }
              ]
            : [
                {
                  key: "gemini-stdio",
                  path: "~/.gemini/settings.json",
                  guide: "로컬 Stdio 모드로 Gemini CLI에 연결합니다.",
                  code: `{\n  "mcpServers": {\n    "genmunity": {\n      "command": "/Users/pignose/Genmunity/.venv/bin/python",\n      "args": ["-m", "genmunity_agent.mcp_a2a"],\n      "cwd": "/Users/pignose/Genmunity"\n    }\n  }\n}`
                }
              ]
        }
      };

      const WORKFLOW_PROMPTS = [
        {
          id: "wf-speakers",
          title: "연사 탐색 및 예산·일정 조회",
          prompt: "DevFest 2026 핸즈온 세션에 적합한 AI / Flutter GDE 연사를 추천해주고, 올해 행사 마감 기한과 지원 가능한 예산 범위를 정리해줘."
        },
        {
          id: "wf-onboarding",
          title: "연사 초청 · 사전 정보 Google Form · 캘린더 초대 원스톱 발송",
          prompt: "한성민(sniper45han@gmail.com)과 박제창(aristojeff@gmail.com) 연사에게 초청 메일을 보내고, 티셔츠 사이즈와 차량 번호를 입력받는 Google Form과 캘린더 초대장을 함께 발송해줘."
        },
        {
          id: "wf-sponsor",
          title: "스폰서십 제안서 발송 및 수신 문의 자동 처리",
          prompt: "DevFest 2026 공식 스폰서십 후원 제안 메일을 발송하고, 최근 수신된 행사 문의 메일을 확인해서 지식 베이스 기반으로 자동 회신하거나 운영진에게 전달해줘."
        },
        {
          id: "wf-rsvp",
          title: "이벤트 현황 요약 및 참가자 RSVP 등록·수정",
          prompt: "DevFest 2026 서울 행사의 현재 참가자 RSVP 현황과 현장 사진 분석 인원을 요약해주고, 신규 참가자 '박지훈(jihoon@gdg.kr, Flutter 트랙)'을 RSVP에 등록해줘."
        }
      ];

      const currentGuide = AGENT_GUIDES[selectedAgent] || AGENT_GUIDES.antigravity;

      return (
        <div className="max-w-5xl w-full mx-auto px-4 sm:px-6 py-10 space-y-10">
          {/* Centered Hero */}
          <div className="text-center space-y-3 max-w-2xl mx-auto">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-medium">
              <span className="w-2 h-2 rounded-full bg-blue-600" />
              <span>Model Context Protocol · Quick Setup</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              사용 중인 에이전트에 Genmunity를 연결하세요
            </h1>
            <p className="text-sm sm:text-base text-slate-500 leading-relaxed">
              복잡한 도구 명세를 읽을 필요 없이, 아래 스니펫을 복사해 에이전트에 등록한 뒤 평소 대화하듯 자연어로 연사 섭외와 이벤트 운영을 지시하세요.
            </p>
          </div>

          {/* Full-Width Single-Box Installation Guide with Copyable Snippets */}
          <section className="w-full rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-2xs space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-100">
              <div className="flex flex-wrap items-center gap-1.5">
                {Object.values(AGENT_GUIDES).map(agent => (
                  <button
                    key={agent.id}
                    type="button"
                    onClick={() => setSelectedAgent(agent.id)}
                    className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium transition ${
                      selectedAgent === agent.id
                        ? "bg-slate-900 text-white shadow-xs"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200/70 hover:text-slate-900"
                    }`}
                  >
                    <i className={agent.icon} />
                    <span>{agent.name}</span>
                  </button>
                ))}
              </div>

              <div className="inline-flex bg-slate-100 p-1 rounded-xl text-xs font-medium">
                <button
                  type="button"
                  onClick={() => setTransportMode("remote")}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    transportMode === "remote" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Cloud (HTTPS)
                </button>
                <button
                  type="button"
                  onClick={() => setTransportMode("stdio")}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    transportMode === "stdio" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Local (Stdio)
                </button>
              </div>
            </div>

            <div className="space-y-4">
              {currentGuide.snippets.map(snip => {
                const isCopied = copiedKey === snip.key;
                return (
                  <div key={snip.key} className="w-full rounded-2xl bg-slate-950 text-slate-100 overflow-hidden border border-slate-800">
                    <div className="flex flex-wrap items-center justify-between gap-2 px-4 sm:px-5 py-3 bg-slate-900/90 border-b border-slate-800">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <span className="font-mono text-xs font-semibold px-2.5 py-1 rounded-md bg-slate-800 text-slate-100">
                          {snip.path}
                        </span>
                        <span className="text-xs text-slate-400">{snip.guide}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(snip.key, snip.code)}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                          isCopied
                            ? "bg-blue-600 text-white"
                            : "bg-slate-800 text-slate-200 hover:bg-slate-700"
                        }`}
                      >
                        <i className={isCopied ? "ri-check-line" : "ri-file-copy-line"} />
                        <span>{isCopied ? "복사 완료" : "스니펫 복사"}</span>
                      </button>
                    </div>
                    <pre className="p-4 sm:p-5 text-xs sm:text-sm font-mono text-slate-200 overflow-x-auto leading-relaxed">{snip.code}</pre>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Full-Width Ready-to-Use Natural Language Prompts (No Reference Doc Dump) */}
          <section className="w-full rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-2xs space-y-5">
            <div className="text-center space-y-1">
              <h2 className="text-lg sm:text-xl font-bold text-slate-900">설치 후 바로 복사해서 요청해 보세요</h2>
              <p className="text-xs sm:text-sm text-slate-500">
                개별 함수나 파라미터를 지정할 필요 없이, 아래 문장을 복사해 에이전트에게 그대로 전달하면 자동으로 워크플로우가 실행됩니다.
              </p>
            </div>

            <div className="space-y-3">
              {WORKFLOW_PROMPTS.map(item => {
                const isCopied = copiedKey === item.id;
                return (
                  <div
                    key={item.id}
                    className="w-full rounded-xl border border-slate-200/90 bg-slate-50/60 p-4 sm:p-5 flex flex-col gap-3 hover:border-slate-300 transition"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-sm text-slate-900">{item.title}</span>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => copyToClipboard(item.id, item.prompt)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700"
                        >
                          <i className={isCopied ? "ri-check-line text-blue-600" : "ri-file-copy-line"} />
                          <span>{isCopied ? "복사 완료" : "프롬프트 복사"}</span>
                        </button>
                        {onRunPrompt && (
                          <button
                            type="button"
                            onClick={() => onRunPrompt(item.prompt)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium"
                          >
                            <i className="ri-play-fill" />
                            <span>바로 실행</span>
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="w-full rounded-lg bg-white border border-slate-200/80 px-3.5 py-2.5 text-xs sm:text-sm text-slate-600 font-mono leading-relaxed">
                      "{item.prompt}"
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Minimal Full-Width Endpoint Bar */}
          <section className="w-full rounded-2xl border border-slate-200 bg-slate-50/70 p-5 sm:p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Remote MCP & A2A Endpoint</div>
              <div className="font-mono text-xs sm:text-sm font-semibold text-slate-900 break-all">{remoteMcpUrl}</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => copyToClipboard("mcp-url", remoteMcpUrl)}
                className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 text-xs font-medium text-slate-700 flex items-center gap-1.5"
              >
                <i className={copiedKey === "mcp-url" ? "ri-check-line text-blue-600" : "ri-file-copy-line"} />
                <span>{copiedKey === "mcp-url" ? "복사 완료" : "MCP 주소 복사"}</span>
              </button>
              <button
                type="button"
                onClick={() => copyToClipboard("a2a-url", a2aCardUrl)}
                className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 text-xs font-medium text-slate-700 flex items-center gap-1.5"
              >
                <i className={copiedKey === "a2a-url" ? "ri-check-line text-blue-600" : "ri-file-copy-line"} />
                <span>{copiedKey === "a2a-url" ? "복사 완료" : "A2A Card 복사"}</span>
              </button>
            </div>
          </section>
        </div>
      );
    }

    function App() {
      const [activeTab, setActiveTab] = useState(() => {
        const params = new URLSearchParams(window.location.search);
        const tab = params.get("tab");
        if (tab === "mcp" || tab === "a2a_mcp") return "mcp";
        if (tab === "events" || tab === "speakers") return tab;
        return "home";
      });
      const [events, setEvents] = useState([]);
      const [speakers, setSpeakers] = useState([]);
      const [selectedEventId, setSelectedEventId] = useState("devfest-2026-seoul");
      const [eventDetail, setEventDetail] = useState(null);

      // Minimal Chat State: starts completely empty
      const [messages, setMessages] = useState([]);
      const [chatInput, setChatInput] = useState("");
      const [chatLoading, setChatLoading] = useState(false);
      const [imageMode, setImageMode] = useState(false);
      const [imageStyle, setImageStyle] = useState("keynote");
      const [showMcpDrawer, setShowMcpDrawer] = useState(false);
      const [selectedMcpIds, setSelectedMcpIds] = useState(["recommend_speakers", "send_speaker_mail"]);

      // Minimal Event / Ops States
      const [rsvpModalEvent, setRsvpModalEvent] = useState(null);
      const [rsvpForm, setRsvpForm] = useState({ name: "", email: "", company: "", role: "Developer" });
      const [wysiwygHtml, setWysiwygHtml] = useState("");
      const [wysiwygPrompt, setWysiwygPrompt] = useState("");
      const [bannerGenerating, setBannerGenerating] = useState(false);
      const [toast, setToast] = useState(null);

      const chatEndRef = useRef(null);
      const wysiwygRef = useRef(null);

      const notify = (msg) => {
        setToast(msg);
        setTimeout(() => setToast(null), 3200);
      };

      const fetchInitial = async () => {
        try {
          const [evRes, spkRes] = await Promise.all([
            fetch("/api/events").then(r => r.json()),
            fetch("/api/speakers").then(r => r.json()),
          ]);
          setEvents(evRes.events || []);
          setSpeakers(spkRes.speakers || []);
        } catch (e) {}
      };

      const fetchEventDetail = async (evId) => {
        if (!evId) return;
        try {
          const data = await fetch(`/api/events/${evId}`).then(r => r.json());
          if (data?.event) {
            setEventDetail(data.event);
            setWysiwygHtml(data.event.wysiwyg_html || "");
          }
        } catch (e) {}
      };

      useEffect(() => { fetchInitial(); }, []);
      useEffect(() => { if (selectedEventId) fetchEventDetail(selectedEventId); }, [selectedEventId]);
      useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, chatLoading]);

      const resetChat = () => {
        if (chatLoading) return;
        setMessages([]);
        setChatInput("");
        setImageMode(false);
        setShowMcpDrawer(false);
      };

      const sendChat = async (overrideMsg = null, forceImg = null) => {
        const text = (overrideMsg !== null ? overrideMsg : chatInput).trim();
        if (!text || chatLoading) return;
        const useImg = forceImg !== null ? forceImg : imageMode;

        const assistantId = "msg-" + Date.now();
        setMessages(prev => [
          ...prev,
          { role: "user", text, imageMode: useImg },
          {
            id: assistantId,
            role: "assistant",
            text: "",
            computing: true,
            isStreaming: true,
            currentStatus: useImg ? "이미지 생성 중..." : "요청 분석 중...",
            steps: [],
            images: [],
          }
        ]);
        if (overrideMsg === null) setChatInput("");
        setChatLoading(true);

        const updateMsg = (updater) => {
          setMessages(prev => prev.map(m => m.id === assistantId ? updater(m) : m));
        };

        try {
          const resp = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              message: text,
              user_id: "organizer_kr",
              image_mode: useImg,
              image_style: imageStyle,
            }),
          });
          if (!resp.ok || !resp.body) throw new Error("Stream error");

          const reader = resp.body.getReader();
          const decoder = new TextDecoder("utf-8");
          let buffer = "";

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";

            for (const raw of parts) {
              const line = raw.trim();
              if (!line.startsWith("data:")) continue;
              let payload = null;
              try { payload = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
              if (!payload) continue;

              if (payload.type === "status") {
                updateMsg(m => ({ ...m, currentStatus: payload.message || m.currentStatus }));
              } else if (payload.type === "tool_start") {
                updateMsg(m => ({
                  ...m,
                  currentStatus: payload.label || payload.tool,
                  steps: [...(m.steps || []), { id: payload.step_id, tool: payload.tool, label: payload.label, status: "running" }]
                }));
              } else if (payload.type === "tool_end") {
                updateMsg(m => ({
                  ...m,
                  steps: (m.steps || []).map(s => s.id === payload.step_id ? { ...s, status: "done", elapsed_ms: payload.elapsed_ms } : s)
                }));
              } else if (payload.type === "image_generated" && payload.image) {
                updateMsg(m => ({ ...m, images: [...(m.images || []), payload.image] }));
              } else if (payload.type === "text_delta") {
                updateMsg(m => ({ ...m, text: payload.accumulated || (m.text + (payload.delta || "")) }));
              } else if (payload.type === "done") {
                updateMsg(m => ({
                  ...m,
                  text: payload.reply || m.text,
                  computing: false,
                  isStreaming: false,
                  images: payload.images?.length ? payload.images : m.images,
                }));
              }
            }
          }
          updateMsg(m => ({ ...m, computing: false, isStreaming: false }));
          if (imageMode) setImageMode(false);
          fetchInitial();
        } catch (err) {
          updateMsg(m => ({
            ...m,
            text: m.text || "오류가 발생했습니다.",
            computing: false,
            isStreaming: false,
          }));
        } finally {
          setChatLoading(false);
        }
      };

      const runMcpBatch = async () => {
        const chosen = MCP_ACTIONS.filter(a => selectedMcpIds.includes(a.id));
        if (!chosen.length || chatLoading) return;
        setShowMcpDrawer(false);

        const assistantId = "mcp-" + Date.now();
        setMessages(prev => [
          ...prev,
          { role: "user", text: `MCP 실행: ${chosen.map(c => c.label).join(", ")}` },
          {
            id: assistantId,
            role: "assistant",
            text: "",
            computing: true,
            isStreaming: true,
            currentStatus: "MCP 파이프라인 실행 중...",
            steps: [],
            images: [],
          }
        ]);
        setChatLoading(true);

        const updateMsg = (updater) => {
          setMessages(prev => prev.map(m => m.id === assistantId ? updater(m) : m));
        };

        try {
          const resp = await fetch("/api/mcp/batch-stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              actions: chosen.map(c => ({ tool_name: c.tool, label: c.label, arguments: c.args }))
            }),
          });
          const reader = resp.body.getReader();
          const decoder = new TextDecoder("utf-8");
          let buffer = "";
          const mdLines = [];

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";

            for (const raw of parts) {
              const line = raw.trim();
              if (!line.startsWith("data:")) continue;
              let payload = null;
              try { payload = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
              if (!payload) continue;

              if (payload.type === "tool_start") {
                updateMsg(m => ({
                  ...m,
                  currentStatus: `${payload.label} (${payload.index}/${payload.total})`,
                  steps: [...(m.steps || []), { id: payload.step_id, tool: payload.tool, label: payload.label, status: "running" }]
                }));
              } else if (payload.type === "tool_end") {
                mdLines.push(`- **${payload.label}**: ${payload.summary} (\`${payload.elapsed_ms}ms\`)`);
                updateMsg(m => ({
                  ...m,
                  text: mdLines.join("\n"),
                  steps: (m.steps || []).map(s => s.id === payload.step_id ? { ...s, status: "done", elapsed_ms: payload.elapsed_ms } : s)
                }));
              } else if (payload.type === "done") {
                updateMsg(m => ({ ...m, computing: false, isStreaming: false }));
              }
            }
          }
          updateMsg(m => ({ ...m, computing: false, isStreaming: false }));
          fetchInitial();
        } catch (e) {
          updateMsg(m => ({ ...m, text: "MCP 실행 중 오류가 발생했습니다.", computing: false, isStreaming: false }));
        } finally {
          setChatLoading(false);
        }
      };

      const submitRsvp = async (e) => {
        e.preventDefault();
        if (!rsvpModalEvent) return;
        const res = await fetch("/api/events/rsvp", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ event_id: rsvpModalEvent.id, ...rsvpForm }),
        }).then(r => r.json());
        if (res.status === "success") {
          notify(`${rsvpForm.name}님 RSVP 완료`);
          setRsvpModalEvent(null);
          setRsvpForm({ name: "", email: "", company: "", role: "Developer" });
          fetchInitial();
        }
      };

      const saveWysiwyg = async () => {
        if (!eventDetail) return;
        const html = wysiwygRef.current ? wysiwygRef.current.innerHTML : wysiwygHtml;
        const res = await fetch(`/api/events/${eventDetail.id}/wysiwyg`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ event_id: eventDetail.id, wysiwyg_html: html }),
        }).then(r => r.json());
        if (res.status === "success") {
          setEventDetail(res.event);
          notify("저장되었습니다.");
        }
      };

      const generateEventBanner = async () => {
        if (!eventDetail) return;
        setBannerGenerating(true);
        try {
          const res = await fetch(`/api/events/${eventDetail.id}/generate-image`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              event_id: eventDetail.id,
              prompt: wysiwygPrompt || `${eventDetail.title} hero banner`,
              style: "keynote",
              insert_into_wysiwyg: true,
            }),
          }).then(r => r.json());
          if (res.status === "success") {
            setEventDetail(res.event);
            setWysiwygHtml(res.event.wysiwyg_html || "");
            if (wysiwygRef.current) wysiwygRef.current.innerHTML = res.event.wysiwyg_html || "";
            notify("배너 이미지 생성 완료");
          }
        } finally {
          setBannerGenerating(false);
        }
      };

      return (
        <div className="min-h-screen flex flex-col bg-white">
          {toast && (
            <div className="fixed bottom-5 right-5 z-50 bg-slate-900 text-white px-4 py-2.5 rounded-xl shadow-lg text-xs font-medium flex items-center gap-2">
              <i className="ri-check-line text-emerald-400" />
              <span>{toast}</span>
            </div>
          )}

          {rsvpModalEvent && (
            <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
              <div className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-xl border border-slate-100">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-sm text-slate-900">{rsvpModalEvent.title} 참가 신청</h3>
                  <button onClick={() => setRsvpModalEvent(null)} className="text-slate-400 hover:text-slate-600">
                    <i className="ri-close-line text-lg" />
                  </button>
                </div>
                <form onSubmit={submitRsvp} className="space-y-2.5">
                  <input required placeholder="이름" value={rsvpForm.name} onChange={e => setRsvpForm({...rsvpForm, name: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs" />
                  <input required type="email" placeholder="이메일" value={rsvpForm.email} onChange={e => setRsvpForm({...rsvpForm, email: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs" />
                  <input placeholder="소속" value={rsvpForm.company} onChange={e => setRsvpForm({...rsvpForm, company: e.target.value})} className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs" />
                  <button type="submit" className="w-full py-2 rounded-lg bg-slate-900 text-white text-xs font-medium hover:bg-slate-800">신청하기</button>
                </form>
              </div>
            </div>
          )}

          {/* ULTRA-MINIMAL HEADER */}
          <header className="sticky top-0 z-30 h-14 border-b border-slate-100 bg-white/90 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between">
            <button onClick={() => setActiveTab("home")} className="flex items-center gap-2 text-slate-900 font-semibold text-sm tracking-tight">
              <img src="/logo.png" alt="Genmunity" className="h-7 w-auto object-contain" style={{ objectFit: "contain" }} />
              <span>Genmunity</span>
            </button>

            <nav className="flex items-center gap-1 bg-slate-100/80 p-1 rounded-xl">
              {[
                { id: "home", label: "에이전트" },
                { id: "events", label: "이벤트" },
                { id: "speakers", label: "스피커" },
                { id: "mcp", label: "MCP" },
              ].map(t => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                    activeTab === t.id ? "bg-white text-slate-900 shadow-2xs" : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>

            <div className="flex items-center gap-2">
              {messages.length > 0 && activeTab === "home" && (
                <button
                  onClick={resetChat}
                  className="px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs text-slate-600 flex items-center gap-1"
                >
                  <i className="ri-refresh-line" />
                  <span>새 대화</span>
                </button>
              )}
            </div>
          </header>

          {/* MAIN VIEW */}
          <main className="flex-1 flex flex-col">
            {activeTab === "home" && (
              <div className="flex-1 flex flex-col max-w-3xl w-full mx-auto px-4">
                {messages.length === 0 ? (
                  /* EMPTY STATE: ChatGPT-style minimal center */
                  <div className="flex-1 flex flex-col items-center justify-center py-16">
                    <h1 className="text-xl sm:text-2xl font-semibold text-slate-900 mb-6 tracking-tight">
                      무엇을 도와드릴까요?
                    </h1>

                    {/* Composer Box */}
                    <div className="w-full rounded-2xl border border-slate-200 bg-white shadow-sm focus-within:border-slate-400 transition p-3">
                      {imageMode && (
                        <div className="flex items-center justify-between mb-2 px-2 py-1 rounded-lg bg-violet-50 text-violet-700 text-xs">
                          <span className="font-medium flex items-center gap-1.5">
                            <i className="ri-image-add-line" /> 이미지 생성 모드
                          </span>
                          <div className="flex items-center gap-1">
                            {["keynote", "poster", "minimal"].map(st => (
                              <button
                                key={st}
                                type="button"
                                onClick={() => setImageStyle(st)}
                                className={`px-2 py-0.5 rounded text-[11px] ${imageStyle === st ? "bg-violet-600 text-white" : "hover:bg-violet-100"}`}
                              >
                                {st}
                              </button>
                            ))}
                            <button onClick={() => setImageMode(false)} className="ml-1 text-violet-500 hover:text-violet-800">
                              <i className="ri-close-line" />
                            </button>
                          </div>
                        </div>
                      )}

                      {showMcpDrawer && (
                        <div className="mb-2.5 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[11px] font-semibold text-slate-600">MCP 액션 선택</span>
                            <button
                              type="button"
                              onClick={runMcpBatch}
                              disabled={!selectedMcpIds.length || chatLoading}
                              className="px-2.5 py-1 rounded-lg bg-blue-600 text-white text-[11px] font-medium hover:bg-blue-700 disabled:opacity-40"
                            >
                              실행 ({selectedMcpIds.length})
                            </button>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {MCP_ACTIONS.map(act => {
                              const active = selectedMcpIds.includes(act.id);
                              return (
                                <button
                                  key={act.id}
                                  type="button"
                                  onClick={() => setSelectedMcpIds(prev => active ? prev.filter(x => x !== act.id) : [...prev, act.id])}
                                  className={`px-2.5 py-1 rounded-lg text-xs flex items-center gap-1 border transition ${
                                    active ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                                  }`}
                                >
                                  <i className={act.icon} />
                                  <span>{act.label}</span>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      <form onSubmit={e => { e.preventDefault(); sendChat(); }}>
                        <textarea
                          rows={2}
                          value={chatInput}
                          onChange={e => setChatInput(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === "Enter" && !e.shiftKey) {
                              e.preventDefault();
                              sendChat();
                            }
                          }}
                          placeholder={imageMode ? "생성할 이미지 프롬프트를 입력하세요..." : "메시지를 입력하세요..."}
                          className="w-full resize-none border-0 focus:outline-none text-sm text-slate-900 placeholder:text-slate-400 px-1"
                        />
                        <div className="flex items-center justify-between pt-2 mt-1 border-t border-slate-100">
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => { setImageMode(!imageMode); setShowMcpDrawer(false); }}
                              className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 transition ${
                                imageMode ? "bg-violet-100 text-violet-700" : "text-slate-500 hover:bg-slate-100"
                              }`}
                            >
                              <i className="ri-image-line" />
                              <span>이미지</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => { setShowMcpDrawer(!showMcpDrawer); setImageMode(false); }}
                              className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 transition ${
                                showMcpDrawer ? "bg-blue-100 text-blue-700" : "text-slate-500 hover:bg-slate-100"
                              }`}
                            >
                              <i className="ri-cpu-line" />
                              <span>MCP 액션</span>
                            </button>
                          </div>
                          <button
                            type="submit"
                            disabled={!chatInput.trim() || chatLoading}
                            className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center hover:bg-slate-800 disabled:opacity-30 transition"
                          >
                            <i className="ri-arrow-up-line text-sm" />
                          </button>
                        </div>
                      </form>
                    </div>

                    {/* Minimal Quick Chips */}
                    <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
                      {[
                        { label: "스피커 추천", prompt: "한성민(AI GDE), 박제창(Flutter GDE) 스피커 추천해줘", img: false },
                        { label: "섭외 메일 발송", prompt: "추천된 두 분께 섭외 메일 발송해줘", img: false },
                        { label: "온보딩 폼 초대", prompt: "구글 폼 생성하고 캘린더 초대장 보내줘", img: false },
                        { label: "배너 이미지 생성", prompt: "GDG DevFest 2026 Seoul 키노트 배너 이미지 만들어줘", img: true },
                      ].map((chip, idx) => (
                        <button
                          key={idx}
                          onClick={() => sendChat(chip.prompt, chip.img)}
                          className="px-3 py-1.5 rounded-full border border-slate-200 text-xs text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition"
                        >
                          {chip.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  /* CONVERSATION STREAM */
                  <div className="flex-1 flex flex-col py-6">
                    <div className="flex-1 space-y-5 pb-28">
                      {messages.map((m, idx) => (
                        <div key={m.id || idx} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                          {m.role === "user" ? (
                            <div className="max-w-[80%] rounded-2xl bg-slate-900 text-white px-4 py-2.5 text-sm">
                              {m.text}
                            </div>
                          ) : (
                            <div className="w-full max-w-full">
                              <ComputingIndicator
                                computing={m.computing}
                                steps={m.steps}
                                currentStatus={m.currentStatus}
                              />
                              {m.text && <MarkdownContent content={m.text} isStreaming={m.isStreaming} />}
                              {m.images && m.images.length > 0 && (
                                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                                  {m.images.map((img, i) => (
                                    <div key={img.id || i} className="rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
                                      <img src={img.data_uri} alt={img.prompt || "generated"} className="w-full h-48 object-cover" />
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                      <div ref={chatEndRef} />
                    </div>

                    {/* Sticky Bottom Composer */}
                    <div className="sticky bottom-4 bg-white rounded-2xl border border-slate-200 shadow-md p-2.5">
                      {showMcpDrawer && (
                        <div className="mb-2 p-2 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex flex-wrap gap-1">
                            {MCP_ACTIONS.map(act => {
                              const active = selectedMcpIds.includes(act.id);
                              return (
                                <button
                                  key={act.id}
                                  type="button"
                                  onClick={() => setSelectedMcpIds(prev => active ? prev.filter(x => x !== act.id) : [...prev, act.id])}
                                  className={`px-2 py-1 rounded-md text-[11px] border ${
                                    active ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200"
                                  }`}
                                >
                                  {act.label}
                                </button>
                              );
                            })}
                          </div>
                          <button
                            type="button"
                            onClick={runMcpBatch}
                            disabled={!selectedMcpIds.length || chatLoading}
                            className="px-2.5 py-1 rounded-lg bg-blue-600 text-white text-xs font-medium"
                          >
                            실행
                          </button>
                        </div>
                      )}
                      <form onSubmit={e => { e.preventDefault(); sendChat(); }} className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => { setImageMode(!imageMode); setShowMcpDrawer(false); }}
                          className={`p-2 rounded-lg text-xs ${imageMode ? "bg-violet-100 text-violet-700" : "text-slate-400 hover:text-slate-700"}`}
                          title="이미지 생성"
                        >
                          <i className="ri-image-line text-base" />
                        </button>
                        <button
                          type="button"
                          onClick={() => { setShowMcpDrawer(!showMcpDrawer); setImageMode(false); }}
                          className={`p-2 rounded-lg text-xs ${showMcpDrawer ? "bg-blue-100 text-blue-700" : "text-slate-400 hover:text-slate-700"}`}
                          title="MCP 액션"
                        >
                          <i className="ri-cpu-line text-base" />
                        </button>
                        <input
                          type="text"
                          value={chatInput}
                          onChange={e => setChatInput(e.target.value)}
                          placeholder={imageMode ? "생성할 이미지 설명..." : "메시지 입력..."}
                          className="flex-1 text-sm text-slate-900 focus:outline-none px-1"
                        />
                        <button
                          type="submit"
                          disabled={!chatInput.trim() || chatLoading}
                          className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center disabled:opacity-30"
                        >
                          {chatLoading ? <i className="ri-loader-4-line spin-icon text-sm" /> : <i className="ri-arrow-up-line text-sm" />}
                        </button>
                      </form>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* EVENTS TAB (Concise) */}
            {activeTab === "events" && (
              <div className="max-w-5xl w-full mx-auto px-4 py-6 space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {events.map(ev => (
                    <div
                      key={ev.id}
                      onClick={() => setSelectedEventId(ev.id)}
                      className={`p-4 rounded-2xl border cursor-pointer transition ${
                        selectedEventId === ev.id ? "border-slate-900 bg-slate-50/60" : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[11px] font-medium text-blue-600">{ev.date}</span>
                        <span className="text-[11px] text-slate-400">{ev.rsvp_count}/{ev.capacity}명</span>
                      </div>
                      <h3 className="font-semibold text-sm text-slate-900 mb-1">{ev.title}</h3>
                      <p className="text-xs text-slate-500 mb-3">{ev.location}</p>
                      <button
                        onClick={e => { e.stopPropagation(); setRsvpModalEvent(ev); }}
                        className="w-full py-1.5 rounded-lg bg-slate-900 text-white text-xs font-medium hover:bg-slate-800"
                      >
                        RSVP 신청
                      </button>
                    </div>
                  ))}
                </div>

                {eventDetail && (
                  <div className="rounded-2xl border border-slate-200 p-5 space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <h2 className="text-base font-bold text-slate-900">{eventDetail.title}</h2>
                        <p className="text-xs text-slate-500">{eventDetail.date} · {eventDetail.location}</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {eventDetail.workspace_links && Object.entries(eventDetail.workspace_links).map(([k, item]) => (
                          <a
                            key={k}
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            title={item.label}
                            className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-50"
                          >
                            <i className={item.icon || "ri-links-line"} />
                          </a>
                        ))}
                        <button onClick={saveWysiwyg} className="px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-medium">
                          저장
                        </button>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <input
                        value={wysiwygPrompt}
                        onChange={e => setWysiwygPrompt(e.target.value)}
                        placeholder="배너 이미지 프롬프트..."
                        className="flex-1 px-3 py-1.5 rounded-lg border border-slate-200 text-xs"
                      />
                      <button
                        onClick={generateEventBanner}
                        disabled={bannerGenerating}
                        className="px-3 py-1.5 rounded-lg bg-violet-600 text-white text-xs font-medium disabled:opacity-50"
                      >
                        {bannerGenerating ? "생성 중..." : "AI 배너 생성"}
                      </button>
                    </div>

                    <div
                      ref={wysiwygRef}
                      contentEditable
                      suppressContentEditableWarning
                      onBlur={e => setWysiwygHtml(e.currentTarget.innerHTML)}
                      className="min-h-[180px] p-4 rounded-xl border border-slate-200 text-sm focus:outline-none"
                      dangerouslySetInnerHTML={{ __html: wysiwygHtml }}
                    />
                  </div>
                )}
              </div>
            )}

            {/* SPEAKERS TAB (Concise) */}
            {activeTab === "speakers" && (
              <div className="max-w-4xl w-full mx-auto px-4 py-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
                {speakers.map(sp => (
                  <div key={sp.id} className="p-4 rounded-2xl border border-slate-200 flex items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-sm text-slate-900">{sp.name}</span>
                        <span className="text-[11px] px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 font-medium">{sp.gde_Category}</span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">{sp.email}</p>
                    </div>
                    <button
                      onClick={() => {
                        setActiveTab("home");
                        sendChat(`${sp.name} 스피커에게 섭외 이메일 발송해줘`);
                      }}
                      className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs font-medium text-slate-700"
                    >
                      섭외 요청
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* MCP TAB (Centered Full-Width Multi-Agent Setup & Prompts) */}
            {(activeTab === "mcp" || activeTab === "a2a_mcp") && (
              <McpIntegrationView
                onRunPrompt={prompt => {
                  setActiveTab("home");
                  sendChat(prompt);
                }}
              />
            )}
          </main>
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById("root")).render(<App />);
  </script>
</body>
</html>
"""
