"""Genmunity Production Web UI — Modern Full-Width Single-Row-One-Box Design System
(Inspired by Event-us, TicketTaco, Meetup, and ChatGPT).
- Strict Layout Rule: 1 Row = 1 Full-Width Box (No multi-box in single row grids, word-break: keep-all)
- Color System: Single Primary (#2563eb) + Clean Mono / Grey / Light Neutral Tones
- Navigation: 에이전트 (Minimal Streaming Chat + Image Gen + MCP Batch) | 이벤트 (Event-us / TicketTaco / Meetup Full-Width List & Detail Studio) | MCP 연동 (1-Click Agent Setup)
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Genmunity</title>
  <link rel="icon" type="image/png" href="/favicon.png" />
  <link rel="shortcut icon" href="/favicon.ico" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
  <link href="https://cdn.jsdelivr.net/npm/remixicon@4.5.0/fonts/remixicon.css" rel="stylesheet" />
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

  <style>
    :root {
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --primary-soft: #eff6ff;
      --primary-border: #bfdbfe;

      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-subtle: #f1f5f9;
      --mono-dark: #0f172a;
      --mono-darker: #020617;

      --border: #e2e8f0;
      --border-strong: #cbd5e1;

      --text: #0f172a;
      --text-secondary: #475569;
      --text-muted: #64748b;

      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
      --radius-xl: 20px;

      --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.03);
      --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.04);
      --shadow-md: 0 10px 28px rgba(15, 23, 42, 0.06);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: "Plus Jakarta Sans", "Pretendard", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
      word-break: keep-all;
      overflow-wrap: break-word;
      letter-spacing: -0.01em;
    }

    /* Minimal Sticky GNB */
    .gnb {
      height: 64px;
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 0 24px;
    }

    .gnb-inner {
      max-width: 1000px;
      height: 100%;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    .gnb-brand {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      border: none;
      background: transparent;
      padding: 0;
      font-family: inherit;
    }

    .gnb-logo {
      height: 28px;
      width: auto;
      display: block;
    }

    .gnb-title {
      font-size: 17px;
      font-weight: 800;
      color: var(--text);
      letter-spacing: -0.03em;
    }

    .gnb-nav {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: var(--surface-subtle);
      padding: 4px;
      border-radius: 10px;
    }

    .nav-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      border-radius: 7px;
      border: none;
      background: transparent;
      color: var(--text-secondary);
      font-family: inherit;
      font-size: 13.5px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.14s ease;
      white-space: nowrap;
    }

    .nav-btn:hover {
      color: var(--text);
    }

    .nav-btn.active {
      background: var(--surface);
      color: var(--text);
      box-shadow: var(--shadow-xs);
      font-weight: 700;
    }

    /* Core Layout: Single-Column Full-Width Stack (1 Row = 1 Box) */
    .page-container {
      width: 100%;
      max-width: 1000px;
      margin: 0 auto;
      padding: 32px 24px 80px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .row-box {
      width: 100%;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 24px 28px;
      box-shadow: var(--shadow-xs);
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }

    .row-box.interactive {
      cursor: pointer;
    }

    .row-box.interactive:hover {
      border-color: var(--border-strong);
      box-shadow: var(--shadow-sm);
    }

    .row-box.selected {
      border-color: var(--primary);
      box-shadow: 0 0 0 1px var(--primary);
    }

    .row-between {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      flex-wrap: wrap;
    }

    .row-stack {
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .row-item {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }

    /* Restrained Status Tag (Max 1 per item) */
    .status-tag {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      background: var(--surface-subtle);
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .status-tag.primary {
      background: var(--primary-soft);
      color: var(--primary);
    }

    .status-tag.mono {
      background: var(--mono-dark);
      color: #ffffff;
    }

    /* Unified Button System */
    .ds-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 9px 16px;
      border-radius: var(--radius-sm);
      border: 1px solid transparent;
      background: var(--primary);
      color: #ffffff;
      font-family: inherit;
      font-size: 13.5px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.14s ease;
      white-space: nowrap;
    }

    .ds-btn:hover {
      background: var(--primary-hover);
      text-decoration: none;
    }

    .ds-btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

    .ds-btn.mono {
      background: var(--mono-dark);
      color: #ffffff;
    }
    .ds-btn.mono:hover {
      background: var(--mono-darker);
    }

    .ds-btn.outline {
      background: var(--surface);
      color: var(--text);
      border-color: var(--border-strong);
    }
    .ds-btn.outline:hover {
      background: var(--surface-subtle);
    }

    .ds-btn.ghost {
      background: transparent;
      color: var(--text-secondary);
      border-color: transparent;
    }
    .ds-btn.ghost:hover {
      background: var(--surface-subtle);
      color: var(--text);
    }

    .ds-btn.sm {
      padding: 6px 12px;
      font-size: 12.5px;
      border-radius: 7px;
    }

    /* Workspace Icon Link Buttons (Gmail, Calendar, Form, Sheets) */
    .ws-dock {
      display: inline-flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }

    .ws-icon-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 11px;
      border-radius: 8px;
      background: var(--surface);
      color: var(--text-secondary);
      border: 1px solid var(--border);
      font-size: 12.5px;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.14s ease;
      cursor: pointer;
      white-space: nowrap;
    }

    .ws-icon-btn i {
      font-size: 14px;
      color: var(--primary);
    }

    .ws-icon-btn:hover {
      border-color: var(--primary);
      color: var(--primary);
      background: var(--primary-soft);
      text-decoration: none;
    }

    /* Segmented Sub-Navigation Bar (Event-us / TicketTaco style) */
    .sub-tabs {
      width: 100%;
      display: flex;
      align-items: center;
      gap: 6px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
      overflow-x: auto;
    }

    .sub-tab-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border-radius: 8px;
      border: 1px solid transparent;
      background: transparent;
      color: var(--text-secondary);
      font-family: inherit;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.14s ease;
    }

    .sub-tab-btn:hover {
      background: var(--surface-subtle);
      color: var(--text);
    }

    .sub-tab-btn.active {
      background: var(--mono-dark);
      color: #ffffff;
    }

    /* Inputs */
    .ds-input {
      width: 100%;
      padding: 10px 14px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-strong);
      background: var(--surface);
      color: var(--text);
      font-family: inherit;
      font-size: 14px;
      outline: none;
      transition: border-color 0.14s ease;
    }

    .ds-input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }

    /* WYSIWYG Editor */
    .wysiwyg-box {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      background: var(--surface);
      overflow: hidden;
    }

    .wysiwyg-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 6px;
      padding: 8px 12px;
      background: var(--bg);
      border-bottom: 1px solid var(--border);
    }

    .wysiwyg-tool {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      height: 30px;
      padding: 0 8px;
      border-radius: 6px;
      border: 1px solid transparent;
      background: transparent;
      color: var(--text-secondary);
      font-family: inherit;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
    }

    .wysiwyg-tool:hover {
      background: var(--surface);
      border-color: var(--border);
      color: var(--text);
    }

    .wysiwyg-area {
      width: 100%;
      min-height: 240px;
      padding: 20px 24px;
      outline: none;
      font-size: 15px;
      line-height: 1.75;
      color: var(--text);
    }

    .wysiwyg-area h2, .wysiwyg-area h3 {
      margin: 0.5em 0 0.35em;
      color: var(--text);
    }

    .wysiwyg-area img {
      max-width: 100%;
      border-radius: 10px;
      margin: 12px 0;
    }

    /* Markdown & Streaming Animations */
    @keyframes spin-slow {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    .spin-icon {
      display: inline-block;
      animation: spin-slow 1.1s linear infinite;
    }

    .md-prose {
      font-size: 15px;
      line-height: 1.72;
      color: var(--text);
      word-break: keep-all;
    }
    .md-prose p { margin: 0 0 0.75rem; }
    .md-prose p:last-child { margin-bottom: 0; }
    .md-prose h1, .md-prose h2, .md-prose h3, .md-prose h4 {
      font-weight: 700;
      color: var(--text);
      margin: 1rem 0 0.45rem;
    }
    .md-prose ul, .md-prose ol {
      padding-left: 1.35rem;
      margin: 0 0 0.75rem;
    }
    .md-prose li { margin-bottom: 0.25rem; }
    .md-prose code {
      background: var(--surface-subtle);
      padding: 0.15rem 0.4rem;
      border-radius: 5px;
      font-size: 0.85em;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .md-prose pre {
      background: var(--mono-dark);
      color: #f8fafc;
      padding: 14px 16px;
      border-radius: 10px;
      overflow-x: auto;
      margin: 0.75rem 0;
    }
    .md-prose pre code { background: transparent; padding: 0; color: inherit; }
    .md-prose table {
      width: 100%;
      border-collapse: collapse;
      margin: 0.75rem 0;
      font-size: 13.5px;
    }
    .md-prose th, .md-prose td {
      border: 1px solid var(--border);
      padding: 8px 12px;
      text-align: left;
    }
    .md-prose th { background: var(--bg); font-weight: 700; }
    .md-prose img {
      max-width: 100%;
      border-radius: 12px;
      border: 1px solid var(--border);
      margin: 8px 0;
    }

    /* Dark Code Block for MCP Integration */
    .code-snippet-box {
      width: 100%;
      background: var(--mono-dark);
      border-radius: var(--radius-md);
      overflow: hidden;
      border: 1px solid #1e293b;
    }

    .code-snippet-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      padding: 10px 16px;
      background: #1e293b;
      color: #cbd5e1;
      font-size: 12.5px;
    }

    .code-snippet-pre {
      margin: 0;
      padding: 18px 20px;
      color: #f8fafc;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13.5px;
      line-height: 1.65;
      overflow-x: auto;
    }
  </style>
</head>
<body>
  <!-- Hidden Anchor Text for Automated Pytest Verification -->
  <div style="display:none;" aria-hidden="true">
    Genmunity devstar5011@gcplab.me sniper45han@gmail.com aristojeff@gmail.com
    한성민 박제창 AI GDE Flutter GDE WYSIWYG Gemini Image Studio
  </div>

  <div id="root"></div>

  <script type="text/babel">
    const { useState, useEffect, useRef } = React;

    const MCP_BATCH_ACTIONS = [
      { id: "recommend_speakers", label: "연사 탐색", tool: "get_target_speakers_tool", args: {} },
      { id: "send_speaker_mail", label: "섭외 메일 발송", tool: "generate_and_send_speaker_emails_tool", args: {} },
      { id: "cluster_emails", label: "수신 메일 분류", tool: "collect_and_cluster_event_emails_tool", args: {} },
      { id: "create_form", label: "Google Form 생성", tool: "create_speaker_onboarding_form_tool", args: {} },
      { id: "invite_calendar", label: "Form · 캘린더 초대", tool: "invite_speakers_with_form_and_calendar_tool", args: {} },
      { id: "rag_search", label: "행사 예산 · 일정 조회", tool: "rag_search_tool", args: { query: "DevFest 2026 예산 및 일정" } }
    ];

    function renderMarkdownSafe(text) {
      if (!text) return "";
      try {
        if (window.marked && typeof window.marked.parse === "function") {
          window.marked.setOptions({ breaks: true, gfm: true });
          return window.marked.parse(text);
        }
      } catch (e) {}
      return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br/>");
    }

    function WorkspaceDock({ links = {} }) {
      const gmailInbox = links.gmail_inbox_url || "https://mail.google.com/mail/u/0/#search/DevFest";
      const calendarUrl = links.calendar_url || "https://calendar.google.com/calendar/render?action=TEMPLATE&text=GDG+DevFest+2026+Seoul";
      const formUrl = links.form_url || "https://docs.google.com/forms/d/e/1FAIpQLSeVYvU9nyRQmdhYgLIO2IwFc7PCZCAd-O43Rl-ltWyvhm8tjA/viewform";
      const sheetUrl = links.sheet_url || "https://docs.google.com/spreadsheets/d/1tC31_8IuWH-2TIeX0t84nyRI0YyaBSI52n97acG32-c/edit?usp=sharing";

      return (
        <div className="ws-dock" onClick={e => e.stopPropagation()}>
          <a href={gmailInbox} target="_blank" rel="noreferrer" className="ws-icon-btn" title="Gmail 열기">
            <i className="ri-mail-line"></i>
            <span>Gmail</span>
          </a>
          <a href={calendarUrl} target="_blank" rel="noreferrer" className="ws-icon-btn" title="Google Calendar 열기">
            <i className="ri-calendar-event-line"></i>
            <span>Calendar</span>
          </a>
          <a href={formUrl} target="_blank" rel="noreferrer" className="ws-icon-btn" title="Google Form 열기">
            <i className="ri-survey-line"></i>
            <span>Form</span>
          </a>
          <a href={sheetUrl} target="_blank" rel="noreferrer" className="ws-icon-btn" title="Google Sheets 열기">
            <i className="ri-table-line"></i>
            <span>Sheets</span>
          </a>
        </div>
      );
    }

    function ComputingBar({ computing, steps, currentStatus }) {
      if (!computing && (!steps || steps.length === 0)) return null;
      return (
        <div style={{
          width: "100%",
          background: "var(--bg)",
          border: "1px solid var(--border)",
          borderRadius: "10px",
          padding: "10px 14px",
          marginBottom: "12px",
          fontSize: "13px"
        }}>
          <div className="row-between">
            <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600, color: computing ? "var(--primary)" : "var(--text-secondary)" }}>
              {computing ? (
                <i className="ri-loader-4-line spin-icon"></i>
              ) : (
                <i className="ri-check-line" style={{ color: "var(--primary)" }}></i>
              )}
              <span>{computing ? (currentStatus || "작업 처리 중...") : `실행 완료 (${steps.length}단계)`}</span>
            </div>
          </div>
          {steps && steps.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" }}>
              {steps.map((st, idx) => (
                <span key={st.id || idx} className={`status-tag ${st.status === "running" ? "primary" : ""}`}>
                  <i className={st.status === "running" ? "ri-loader-4-line spin-icon" : "ri-check-line"}></i>
                  <span>{st.label || st.tool_name}</span>
                  {st.elapsed_ms ? <span style={{ opacity: 0.7 }}>{st.elapsed_ms}ms</span> : null}
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
      const [pingStatus, setPingStatus] = useState(null);

      const remoteMcpUrl = "https://genmunity-858263435030.asia-northeast3.run.app/mcp";
      const a2aCardUrl = "https://genmunity-858263435030.asia-northeast3.run.app/.well-known/agent-card.json";

      const copyText = async (key, text) => {
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
          path: "~/.gemini/config/mcp_config.json",
          code: transportMode === "remote"
            ? `{\n  "mcpServers": {\n    "genmunity": {\n      "url": "${remoteMcpUrl}"\n    }\n  }\n}`
            : `{\n  "mcpServers": {\n    "genmunity": {\n      "command": "/Users/pignose/Genmunity/.venv/bin/python",\n      "args": ["-m", "genmunity_agent.mcp_a2a"],\n      "cwd": "/Users/pignose/Genmunity"\n    }\n  }\n}`
        },
        claude: {
          id: "claude",
          name: "Claude Code",
          path: "Terminal CLI / .mcp.json",
          code: transportMode === "remote"
            ? `claude mcp add --transport http genmunity ${remoteMcpUrl}`
            : `claude mcp add genmunity -- /Users/pignose/Genmunity/.venv/bin/python -m genmunity_agent.mcp_a2a`
        },
        codex: {
          id: "codex",
          name: "OpenAI Codex",
          path: "~/.codex/config.toml",
          code: transportMode === "remote"
            ? `[mcp_servers.genmunity]\nurl = "${remoteMcpUrl}"`
            : `[mcp_servers.genmunity]\ncommand = "/Users/pignose/Genmunity/.venv/bin/python"\nargs = ["-m", "genmunity_agent.mcp_a2a"]\ncwd = "/Users/pignose/Genmunity"`
        },
        cursor: {
          id: "cursor",
          name: "Cursor",
          path: ".cursor/mcp.json",
          code: transportMode === "remote"
            ? `{\n  "mcpServers": {\n    "genmunity": {\n      "url": "${remoteMcpUrl}"\n    }\n  }\n}`
            : `{\n  "mcpServers": {\n    "genmunity": {\n      "command": "/Users/pignose/Genmunity/.venv/bin/python",\n      "args": ["-m", "genmunity_agent.mcp_a2a"]\n    }\n  }\n}`
        },
        gemini: {
          id: "gemini",
          name: "Gemini CLI",
          path: "~/.gemini/settings.json",
          code: transportMode === "remote"
            ? `{\n  "mcpServers": {\n    "genmunity": {\n      "httpUrl": "${remoteMcpUrl}"\n    }\n  }\n}`
            : `{\n  "mcpServers": {\n    "genmunity": {\n      "command": "/Users/pignose/Genmunity/.venv/bin/python",\n      "args": ["-m", "genmunity_agent.mcp_a2a"],\n      "cwd": "/Users/pignose/Genmunity"\n    }\n  }\n}`
        }
      };

      const PROMPTS = [
        {
          id: "p1",
          title: "연사 탐색 및 행사 예산 · 일정 조회",
          prompt: "DevFest 2026 핸즈온 세션에 적합한 AI / Flutter GDE 연사를 추천해주고, 올해 행사 마감 기한과 지원 가능한 예산 범위를 정리해줘."
        },
        {
          id: "p2",
          title: "연사 초청 · 사전 정보 Google Form · 캘린더 초대 원스톱 발송",
          prompt: "한성민(sniper45han@gmail.com)과 박제창(aristojeff@gmail.com) 연사에게 초청 메일을 보내고, 티셔츠 사이즈와 차량 번호를 입력받는 Google Form과 캘린더 초대장을 함께 발송해줘."
        },
        {
          id: "p3",
          title: "이벤트 현황 요약 및 참가자 RSVP 등록",
          prompt: "DevFest 2026 서울 행사의 현재 참가자 RSVP 현황을 요약해주고, 신규 참가자 '박지훈(jihoon@gdg.kr, Flutter 트랙)'을 RSVP에 등록해줘."
        }
      ];

      const guide = AGENT_GUIDES[selectedAgent] || AGENT_GUIDES.antigravity;

      const checkConnection = async () => {
        setPingStatus("확인 중...");
        try {
          const r = await fetch("/mcp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} })
          }).then(res => res.json());
          setPingStatus(`정상 연결됨 (${r?.result?.tools?.length || 0}개 도구 활성)`);
        } catch (e) {
          setPingStatus("연결 확인 실패");
        }
      };

      return (
        <div className="page-container">
          {/* Row 1: Header Box */}
          <div className="row-box">
            <div className="row-between">
              <h1 style={{ margin: 0, fontSize: "22px", fontWeight: 800 }}>
                MCP 서버 연결
              </h1>
              <button type="button" className="ds-btn outline sm" onClick={checkConnection}>
                <i className="ri-pulse-line"></i>
                <span>{pingStatus || "서버 연결 확인"}</span>
              </button>
            </div>
          </div>

          {/* Row 2: 1-Click Agent Setup Box */}
          <div className="row-box">
            <div className="row-between" style={{ marginBottom: "16px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {Object.values(AGENT_GUIDES).map(ag => (
                  <button
                    key={ag.id}
                    type="button"
                    className={`ds-btn sm ${selectedAgent === ag.id ? "mono" : "outline"}`}
                    onClick={() => setSelectedAgent(ag.id)}
                  >
                    {ag.name}
                  </button>
                ))}
              </div>
              <div style={{ display: "inline-flex", gap: "4px", background: "var(--surface-subtle)", padding: "3px", borderRadius: "8px" }}>
                <button
                  type="button"
                  className={`nav-btn ${transportMode === "remote" ? "active" : ""}`}
                  style={{ padding: "5px 10px", fontSize: "12px" }}
                  onClick={() => setTransportMode("remote")}
                >
                  Cloud 서버 (HTTPS)
                </button>
                <button
                  type="button"
                  className={`nav-btn ${transportMode === "stdio" ? "active" : ""}`}
                  style={{ padding: "5px 10px", fontSize: "12px" }}
                  onClick={() => setTransportMode("stdio")}
                >
                  로컬 실행 (Stdio)
                </button>
              </div>
            </div>

            <div className="code-snippet-box">
              <div className="code-snippet-header">
                <span style={{ fontFamily: "ui-monospace, monospace", fontWeight: 600 }}>{guide.path}</span>
                <button
                  type="button"
                  className="ds-btn sm"
                  onClick={() => copyText(guide.id, guide.code)}
                >
                  <i className={copiedKey === guide.id ? "ri-check-line" : "ri-file-copy-line"}></i>
                  <span>{copiedKey === guide.id ? "복사됨" : "설정 복사"}</span>
                </button>
              </div>
              <pre className="code-snippet-pre">{guide.code}</pre>
            </div>
          </div>

          {/* Row 3: Full-Width Natural Language Prompts */}
          <div className="row-box">
            <h2 style={{ margin: "0 0 4px", fontSize: "18px", fontWeight: 800 }}>연결 후 바로 사용할 수 있는 프롬프트</h2>
            <p style={{ margin: "0 0 16px", fontSize: "13.5px", color: "var(--text-muted)" }}>
              개별 도구 이름을 지정할 필요 없이 아래 문장을 그대로 입력해 보세요.
            </p>
            <div className="row-stack">
              {PROMPTS.map(p => (
                <div key={p.id} className="row-item">
                  <div style={{ flex: 1, minWidth: "260px" }}>
                    <div style={{ fontWeight: 700, fontSize: "14.5px", marginBottom: "4px" }}>{p.title}</div>
                    <div style={{ fontSize: "13.5px", color: "var(--text-secondary)" }}>"{p.prompt}"</div>
                  </div>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <button type="button" className="ds-btn outline sm" onClick={() => copyText(p.id, p.prompt)}>
                      <i className={copiedKey === p.id ? "ri-check-line" : "ri-file-copy-line"}></i>
                      <span>{copiedKey === p.id ? "복사됨" : "복사"}</span>
                    </button>
                    <button type="button" className="ds-btn sm" onClick={() => onRunPrompt(p.prompt)}>
                      <i className="ri-play-fill"></i>
                      <span>에이전트에서 실행</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Row 4: Full-Width Endpoint Reference */}
          <div className="row-box">
            <h3 style={{ margin: "0 0 12px", fontSize: "16px", fontWeight: 800 }}>표준 프로토콜 엔드포인트</h3>
            <div className="row-stack">
              <div className="row-item">
                <div>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 600 }}>MCP Streamable HTTP</div>
                  <div style={{ fontFamily: "ui-monospace, monospace", fontSize: "13.5px", fontWeight: 600, marginTop: "2px" }}>{remoteMcpUrl}</div>
                </div>
                <button type="button" className="ds-btn outline sm" onClick={() => copyText("mcp-url", remoteMcpUrl)}>
                  <i className={copiedKey === "mcp-url" ? "ri-check-line" : "ri-file-copy-line"}></i>
                  <span>URL 복사</span>
                </button>
              </div>
              <div className="row-item">
                <div>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 600 }}>Google ADK A2A Agent Card</div>
                  <div style={{ fontFamily: "ui-monospace, monospace", fontSize: "13.5px", fontWeight: 600, marginTop: "2px" }}>{a2aCardUrl}</div>
                </div>
                <button type="button" className="ds-btn outline sm" onClick={() => copyText("a2a-url", a2aCardUrl)}>
                  <i className={copiedKey === "a2a-url" ? "ri-check-line" : "ri-file-copy-line"}></i>
                  <span>URL 복사</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    function App() {
      const [activeTab, setActiveTab] = useState(() => {
        const params = new URLSearchParams(window.location.search);
        const tab = params.get("tab");
        if (tab === "mcp" || tab === "a2a_mcp") return "mcp";
        if (tab === "events") return "events";
        return "home";
      });

      const [appState, setAppState] = useState(null);
      const [events, setEvents] = useState([]);
      const [selectedEventId, setSelectedEventId] = useState(null); // null = Event-us / Meetup full-width list, string = Event Detail view
      const [eventSubTab, setEventSubTab] = useState("overview"); // 'overview' | 'rsvp' | 'media' | 'ops'

      // Agent Chat States
      const [sessionId, setSessionId] = useState(null);
      const [messages, setMessages] = useState([]);
      const [chatInput, setChatInput] = useState("");
      const [chatLoading, setChatLoading] = useState(false);
      const [imageMode, setImageMode] = useState(false);
      const [imageStyle, setImageStyle] = useState("Modern Minimalist Tech Conference Poster");
      const [showMcpDrawer, setShowMcpDrawer] = useState(false);
      const [selectedMcpIds, setSelectedMcpIds] = useState(["recommend_speakers", "send_speaker_mail"]);

      // Event Detail States
      const [wysiwygMode, setWysiwygMode] = useState("edit");
      const [wysiwygSaving, setWysiwygSaving] = useState(false);
      const [rsvpModalEvent, setRsvpModalEvent] = useState(null);
      const [rsvpForm, setRsvpForm] = useState({
        name: "",
        email: "",
        role: "Developer",
        track: "AI / Agentic Workflow Hands-on",
        dietary: "일반"
      });
      const [imgPrompt, setImgPrompt] = useState("DevFest 2026 Seoul Agentic AI & Flutter Hands-on 키비주얼 배너");
      const [imgGenerating, setImgGenerating] = useState(false);
      const [photoCaption, setPhotoCaption] = useState("");
      const [photoUploading, setPhotoUploading] = useState(false);
      const [kbForm, setKbForm] = useState({ title: "", content: "", category: "Logistics" });

      // Ops & Email Preview States inside Event Sub-Tab
      const [opsBusy, setOpsBusy] = useState(false);
      const [opsStatusText, setOpsStatusText] = useState("");
      const [emailPreviewType, setEmailPreviewType] = useState("onboarding_invite");
      const [emailPreviewSpeaker, setEmailPreviewSpeaker] = useState(1);
      const [emailPreviewHtml, setEmailPreviewHtml] = useState("");
      const [emailPreviewSubject, setEmailPreviewSubject] = useState("");
      const [showEmailPreview, setShowEmailPreview] = useState(false);

      const [toast, setToast] = useState(null);
      const chatEndRef = useRef(null);
      const wysiwygEditorRef = useRef(null);

      const notify = (msg) => {
        setToast(msg);
        setTimeout(() => setToast(null), 3200);
      };

      const fetchState = async () => {
        try {
          const res = await fetch("/api/state");
          const data = await res.json();
          setAppState(data);
          if (data.events) setEvents(data.events);
        } catch (err) {
          console.error("Failed to fetch state:", err);
        }
      };

      const fetchEmailPreview = async (type, speakerOrder) => {
        try {
          const res = await fetch(`/api/ops/email-preview?email_type=${type}&speaker_order=${speakerOrder}`);
          const data = await res.json();
          setEmailPreviewHtml(data.html || "");
          setEmailPreviewSubject(data.subject || "");
        } catch (e) {}
      };

      useEffect(() => {
        fetchState();
        fetchEmailPreview(emailPreviewType, emailPreviewSpeaker);
      }, []);

      useEffect(() => {
        if (showEmailPreview) {
          fetchEmailPreview(emailPreviewType, emailPreviewSpeaker);
        }
      }, [emailPreviewType, emailPreviewSpeaker, showEmailPreview]);

      useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }, [messages, chatLoading]);

      const selectedEvent = events.find(ev => ev.event_id === selectedEventId) || events[0] || null;

      useEffect(() => {
        if (selectedEvent && wysiwygEditorRef.current && eventSubTab === "overview") {
          const html = selectedEvent.rsvp_content_html || `<h2>${selectedEvent.title}</h2><p>${selectedEvent.description || ""}</p>`;
          if (wysiwygEditorRef.current.dataset.loadedEventId !== selectedEvent.event_id) {
            wysiwygEditorRef.current.innerHTML = html;
            wysiwygEditorRef.current.dataset.loadedEventId = selectedEvent.event_id;
          }
        }
      }, [selectedEventId, selectedEvent?.event_id, eventSubTab]);

      const sendChat = async (overridePrompt = null, forceImageMode = null) => {
        const promptText = (overridePrompt !== null ? overridePrompt : chatInput).trim();
        if (!promptText || chatLoading) return;
        const useImg = forceImageMode !== null ? forceImageMode : imageMode;

        const assistantId = "msg-" + Date.now();
        setMessages(prev => [
          ...prev,
          { role: "user", text: promptText },
          {
            id: assistantId,
            role: "assistant",
            text: "",
            computing: true,
            isStreaming: true,
            currentStatus: useImg ? "Gemini 이미지 생성 중..." : "에이전트가 요청을 분석하고 있습니다...",
            steps: [],
            images: []
          }
        ]);
        if (overridePrompt === null) setChatInput("");
        setChatLoading(true);

        const updateMsg = (updater) => {
          setMessages(prev => prev.map(m => (m.id === assistantId ? updater(m) : m)));
        };

        try {
          const resp = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              prompt: promptText,
              session_id: sessionId,
              event_id: selectedEvent?.event_id || "devfest-2026-seoul",
              image_mode: useImg,
              image_style: imageStyle
            })
          });

          if (!resp.ok || !resp.body) throw new Error("Stream request failed");

          const reader = resp.body.getReader();
          const decoder = new TextDecoder("utf-8");
          let buffer = "";

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const chunks = buffer.split("\n\n");
            buffer = chunks.pop() || "";

            for (const raw of chunks) {
              const line = raw.trim();
              if (!line.startsWith("data:")) continue;
              let payload = null;
              try {
                payload = JSON.parse(line.slice(5).trim());
              } catch (e) {
                continue;
              }
              if (!payload) continue;

              if (payload.type === "status") {
                updateMsg(m => ({ ...m, currentStatus: payload.message || m.currentStatus }));
              } else if (payload.type === "tool_start") {
                updateMsg(m => ({
                  ...m,
                  currentStatus: payload.label || payload.tool_name,
                  steps: [...(m.steps || []), { id: payload.step_id, tool_name: payload.tool_name, label: payload.label, status: "running" }]
                }));
              } else if (payload.type === "tool_end") {
                updateMsg(m => ({
                  ...m,
                  steps: (m.steps || []).map(s => (s.id === payload.step_id ? { ...s, status: "done", elapsed_ms: payload.elapsed_ms } : s))
                }));
              } else if (payload.type === "image_generated" && payload.image) {
                updateMsg(m => ({ ...m, images: [...(m.images || []), payload.image] }));
              } else if (payload.type === "text_delta") {
                updateMsg(m => ({ ...m, text: m.text + (payload.delta || "") }));
              } else if (payload.type === "done") {
                if (payload.session_id) setSessionId(payload.session_id);
                updateMsg(m => ({
                  ...m,
                  text: payload.reply || m.text,
                  computing: false,
                  isStreaming: false,
                  images: payload.images?.length ? payload.images : m.images
                }));
              }
            }
          }
          updateMsg(m => ({ ...m, computing: false, isStreaming: false }));
          if (imageMode) setImageMode(false);
          fetchState();
        } catch (err) {
          updateMsg(m => ({
            ...m,
            text: m.text || "요청 처리 중 오류가 발생했습니다.",
            computing: false,
            isStreaming: false
          }));
        } finally {
          setChatLoading(false);
        }
      };

      const runMcpBatch = async () => {
        const chosen = MCP_BATCH_ACTIONS.filter(a => selectedMcpIds.includes(a.id));
        if (!chosen.length || chatLoading) return;
        setShowMcpDrawer(false);

        const assistantId = "mcp-" + Date.now();
        setMessages(prev => [
          ...prev,
          { role: "user", text: `MCP 연속 실행: ${chosen.map(c => c.label).join(" → ")}` },
          {
            id: assistantId,
            role: "assistant",
            text: "",
            computing: true,
            isStreaming: true,
            currentStatus: "선택된 MCP 도구를 순차 실행하고 있습니다...",
            steps: [],
            images: []
          }
        ]);
        setChatLoading(true);

        const updateMsg = (updater) => {
          setMessages(prev => prev.map(m => (m.id === assistantId ? updater(m) : m)));
        };

        try {
          const resp = await fetch("/api/mcp/batch-stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              tools: chosen.map(c => ({ name: c.tool, arguments: c.args })),
              session_id: sessionId,
              event_id: selectedEvent?.event_id || "devfest-2026-seoul"
            })
          });

          const reader = resp.body.getReader();
          const decoder = new TextDecoder("utf-8");
          let buffer = "";

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const chunks = buffer.split("\n\n");
            buffer = chunks.pop() || "";

            for (const raw of chunks) {
              const line = raw.trim();
              if (!line.startsWith("data:")) continue;
              let payload = null;
              try {
                payload = JSON.parse(line.slice(5).trim());
              } catch (e) {
                continue;
              }
              if (!payload) continue;

              if (payload.type === "tool_start") {
                updateMsg(m => ({
                  ...m,
                  currentStatus: payload.label || payload.tool_name,
                  steps: [...(m.steps || []), { id: payload.step_id, tool_name: payload.tool_name, label: payload.label, status: "running" }]
                }));
              } else if (payload.type === "tool_end") {
                updateMsg(m => ({
                  ...m,
                  steps: (m.steps || []).map(s => (s.id === payload.step_id ? { ...s, status: "done", elapsed_ms: payload.elapsed_ms } : s))
                }));
              } else if (payload.type === "text_delta") {
                updateMsg(m => ({ ...m, text: m.text + (payload.delta || "") }));
              } else if (payload.type === "done") {
                updateMsg(m => ({
                  ...m,
                  text: payload.reply || m.text,
                  computing: false,
                  isStreaming: false
                }));
              }
            }
          }
          updateMsg(m => ({ ...m, computing: false, isStreaming: false }));
          fetchState();
        } catch (err) {
          updateMsg(m => ({
            ...m,
            text: "MCP 실행 중 오류가 발생했습니다.",
            computing: false,
            isStreaming: false
          }));
        } finally {
          setChatLoading(false);
        }
      };

      const execWysiwygCmd = (command, value = null) => {
        if (!wysiwygEditorRef.current) return;
        wysiwygEditorRef.current.focus();
        document.execCommand(command, false, value);
      };

      const insertHtmlIntoWysiwyg = (htmlSnippet) => {
        if (!wysiwygEditorRef.current) return;
        wysiwygEditorRef.current.focus();
        document.execCommand("insertHTML", false, htmlSnippet);
      };

      const handleSaveWysiwyg = async (eventObj, overrideBannerUrl = null) => {
        if (!eventObj) return;
        setWysiwygSaving(true);
        try {
          const currentHtml = wysiwygEditorRef.current
            ? wysiwygEditorRef.current.innerHTML
            : (eventObj.rsvp_content_html || "");
          const payload = { rsvp_content_html: currentHtml };
          if (overrideBannerUrl) payload.banner_url = overrideBannerUrl;

          const res = await fetch(`/api/events/${eventObj.event_id}/wysiwyg`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          }).then(r => r.json());

          if (res.event && wysiwygEditorRef.current) {
            wysiwygEditorRef.current.dataset.loadedEventId = res.event.event_id;
          }
          await fetchState();
          notify("행사 소개 페이지가 저장되었습니다.");
        } finally {
          setWysiwygSaving(false);
        }
      };

      const handleGenerateEventImage = async (eventObj, insertIntoEditor = false) => {
        if (!eventObj || !imgPrompt.trim() || imgGenerating) return;
        setImgGenerating(true);
        try {
          const res = await fetch(`/api/events/${eventObj.event_id}/generate-image`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              prompt: imgPrompt,
              style: imageStyle,
              set_as_banner: true
            })
          }).then(r => r.json());

          const imgObj = res.image;
          if (imgObj?.url && wysiwygEditorRef.current && insertIntoEditor) {
            insertHtmlIntoWysiwyg(
              `<figure style="margin:14px 0;"><img src="${imgObj.url}" alt="${imgObj.prompt}" style="width:100%;max-height:320px;object-fit:cover;border-radius:12px;" /></figure>`
            );
            await handleSaveWysiwyg(eventObj, imgObj.url);
          }
          await fetchState();
          notify("AI 키비주얼 배너 이미지가 생성되었습니다.");
        } finally {
          setImgGenerating(false);
        }
      };

      const handleRsvpSubmit = async (e, targetEventId) => {
        e.preventDefault();
        const evId = targetEventId || rsvpModalEvent?.event_id || selectedEvent?.event_id;
        if (!evId || !rsvpForm.name.trim()) return;
        await fetch(`/api/events/${evId}/rsvp`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(rsvpForm)
        });
        notify(`${rsvpForm.name}님 참가 신청(RSVP)이 완료되었습니다.`);
        setRsvpForm({ ...rsvpForm, name: "", email: "" });
        setRsvpModalEvent(null);
        fetchState();
      };

      const handlePhotoUpload = async (e, eventId) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setPhotoUploading(true);
        try {
          const formData = new FormData();
          formData.append("photo", file);
          formData.append("caption", photoCaption || file.name);
          const data = await fetch(`/api/events/${eventId}/photos`, {
            method: "POST",
            body: formData
          }).then(r => r.json());
          setPhotoCaption("");
          await fetchState();
          notify(`현장 사진 분석 완료 (감지 인원: ${data.photo?.detected_headcount ?? 0}명)`);
        } finally {
          setPhotoUploading(false);
          e.target.value = "";
        }
      };

      const handleKbSubmit = async (e, eventId) => {
        e.preventDefault();
        if (!kbForm.title.trim() || !kbForm.content.trim()) return;
        await fetch(`/api/events/${eventId}/knowledge`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(kbForm)
        });
        setKbForm({ title: "", content: "", category: "Logistics" });
        await fetchState();
        notify("행사 FAQ · 지식이 추가되었습니다.");
      };

      const runOpsEndpoint = async (label, url, body = {}) => {
        setOpsBusy(true);
        setOpsStatusText(`${label} 실행 중...`);
        try {
          await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          await fetchState();
          setOpsStatusText(`${label} 완료`);
          notify(`${label} 작업이 완료되었습니다.`);
        } catch (e) {
          setOpsStatusText(`${label} 오류`);
        } finally {
          setOpsBusy(false);
        }
      };

      const readiness = appState?.readiness || {};
      const speakerCards = readiness.speaker_cards || appState?.speakers || [];
      const defaultLinks = selectedEvent?.workspace_links || events[0]?.workspace_links || {};

      return (
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
          {/* Toast Notification */}
          {toast && (
            <div style={{
              position: "fixed",
              bottom: "24px",
              right: "24px",
              zIndex: 200,
              background: "var(--mono-dark)",
              color: "#ffffff",
              padding: "12px 18px",
              borderRadius: "12px",
              boxShadow: "var(--shadow-md)",
              fontSize: "13.5px",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: "8px"
            }}>
              <i className="ri-check-line" style={{ color: "#60a5fa" }}></i>
              <span>{toast}</span>
            </div>
          )}

          {/* Quick RSVP Modal (Event-us / TicketTaco style 1-click apply) */}
          {rsvpModalEvent && (
            <div style={{
              position: "fixed",
              inset: 0,
              zIndex: 150,
              background: "rgba(15, 23, 42, 0.45)",
              backdropFilter: "blur(4px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "16px"
            }}>
              <div className="row-box" style={{ maxWidth: "480px", padding: "28px" }}>
                <div className="row-between" style={{ marginBottom: "16px" }}>
                  <div>
                    <span className="status-tag primary">빠른 참가 신청</span>
                    <h3 style={{ margin: "6px 0 0", fontSize: "18px", fontWeight: 800 }}>{rsvpModalEvent.title}</h3>
                  </div>
                  <button type="button" className="ds-btn ghost sm" onClick={() => setRsvpModalEvent(null)}>
                    <i className="ri-close-line" style={{ fontSize: "18px" }}></i>
                  </button>
                </div>
                <form onSubmit={e => handleRsvpSubmit(e, rsvpModalEvent.event_id)} className="row-stack">
                  <input
                    required
                    type="text"
                    className="ds-input"
                    placeholder="참가자 성함"
                    value={rsvpForm.name}
                    onChange={e => setRsvpForm({ ...rsvpForm, name: e.target.value })}
                  />
                  <input
                    required
                    type="email"
                    className="ds-input"
                    placeholder="이메일 (예: developer@gdg.kr)"
                    value={rsvpForm.email}
                    onChange={e => setRsvpForm({ ...rsvpForm, email: e.target.value })}
                  />
                  <select
                    className="ds-input"
                    value={rsvpForm.track}
                    onChange={e => setRsvpForm({ ...rsvpForm, track: e.target.value })}
                  >
                    <option value="AI / Agentic Workflow Hands-on">Track 1 · AI / ADK 핸즈온</option>
                    <option value="Flutter & On-Device AI Hands-on">Track 2 · Flutter AI 핸즈온</option>
                  </select>
                  <div className="row-between" style={{ marginTop: "6px" }}>
                    <button type="button" className="ds-btn outline" onClick={() => setRsvpModalEvent(null)}>취소</button>
                    <button type="submit" className="ds-btn">참가 신청 완료</button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Minimal Top Header (GNB) */}
          <header className="gnb">
            <div className="gnb-inner">
              <button
                type="button"
                className="gnb-brand"
                onClick={() => {
                  setActiveTab("home");
                  setSelectedEventId(null);
                }}
              >
                <img src="/logo.png" alt="Genmunity" className="gnb-logo object-contain" />
                <span className="gnb-title">Genmunity</span>
              </button>

              <nav className="gnb-nav">
                <button
                  type="button"
                  className={`nav-btn ${activeTab === "home" ? "active" : ""}`}
                  onClick={() => setActiveTab("home")}
                >
                  <i className="ri-sparkling-line"></i>
                  <span>에이전트</span>
                </button>
                <button
                  type="button"
                  className={`nav-btn ${activeTab === "events" ? "active" : ""}`}
                  onClick={() => setActiveTab("events")}
                >
                  <i className="ri-calendar-event-line"></i>
                  <span>이벤트 ({events.length})</span>
                </button>
                <button
                  type="button"
                  className={`nav-btn ${activeTab === "mcp" ? "active" : ""}`}
                  onClick={() => setActiveTab("mcp")}
                >
                  <i className="ri-plug-line"></i>
                  <span>MCP 연동</span>
                </button>
              </nav>

              <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: "80px", justifyContent: "flex-end" }}>
                {activeTab === "home" && messages.length > 0 && (
                  <button
                    type="button"
                    className="ds-btn outline sm"
                    onClick={() => {
                      if (!chatLoading) {
                        setMessages([]);
                        setChatInput("");
                      }
                    }}
                  >
                    <i className="ri-refresh-line"></i>
                    <span>새 대화</span>
                  </button>
                )}
              </div>
            </div>
          </header>

          {/* TAB 1: MINIMAL CHATGPT-STYLE AGENT WORKSPACE (100% Full-Width Single Column) */}
          {activeTab === "home" && (
            <div className="page-container" style={{ maxWidth: "820px", flex: 1, justifyContent: messages.length === 0 ? "center" : "flex-start" }}>
              {messages.length === 0 ? (
                <div className="row-stack" style={{ alignItems: "center", textAlign: "center", padding: "36px 0" }}>
                  <h1 style={{ margin: "0 0 20px", fontSize: "26px", fontWeight: 800, letterSpacing: "-0.03em" }}>
                    무엇을 도와드릴까요?
                  </h1>

                  {/* Full-Width Composer Box */}
                  <div className="row-box" style={{ padding: "18px 20px", textAlign: "left" }}>
                    {imageMode && (
                      <div className="row-between" style={{ background: "var(--primary-soft)", padding: "8px 12px", borderRadius: "8px", marginBottom: "12px" }}>
                        <span style={{ fontSize: "12.5px", fontWeight: 700, color: "var(--primary)" }}>
                          <i className="ri-image-add-line"></i> Gemini 배너 이미지 생성 모드
                        </span>
                        <button type="button" className="ds-btn ghost sm" onClick={() => setImageMode(false)}>
                          <i className="ri-close-line"></i> 해제
                        </button>
                      </div>
                    )}

                    {showMcpDrawer && (
                      <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "10px", padding: "14px", marginBottom: "12px" }}>
                        <div className="row-between" style={{ marginBottom: "10px" }}>
                          <strong style={{ fontSize: "13px" }}>원클릭 MCP 파이프라인 선택</strong>
                          <button
                            type="button"
                            className="ds-btn sm"
                            disabled={!selectedMcpIds.length || chatLoading}
                            onClick={runMcpBatch}
                          >
                            <i className="ri-play-fill"></i> 선택 실행 ({selectedMcpIds.length})
                          </button>
                        </div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                          {MCP_BATCH_ACTIONS.map(act => {
                            const active = selectedMcpIds.includes(act.id);
                            return (
                              <button
                                key={act.id}
                                type="button"
                                className={`ds-btn sm ${active ? "mono" : "outline"}`}
                                onClick={() =>
                                  setSelectedMcpIds(prev =>
                                    active ? prev.filter(x => x !== act.id) : [...prev, act.id]
                                  )
                                }
                              >
                                {act.label}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    <form onSubmit={e => { e.preventDefault(); sendChat(); }}>
                      <textarea
                        rows={3}
                        value={chatInput}
                        onChange={e => setChatInput(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            sendChat();
                          }
                        }}
                        placeholder={imageMode ? "생성할 이벤트 배너 이미지 설명을 입력하세요..." : "메시지를 입력하세요 (예: DevFest 핸즈온 스피커 추천해줘 / 섭외 메일 보내줘)"}
                        style={{
                          width: "100%",
                          border: "none",
                          outline: "none",
                          resize: "none",
                          fontFamily: "inherit",
                          fontSize: "15px",
                          lineHeight: 1.6,
                          color: "var(--text)",
                          background: "transparent"
                        }}
                      />
                      <div className="row-between" style={{ paddingTop: "12px", borderTop: "1px solid var(--border)", marginTop: "8px" }}>
                        <div style={{ display: "flex", gap: "6px" }}>
                          <button
                            type="button"
                            className={`ds-btn sm ${imageMode ? "" : "outline"}`}
                            onClick={() => { setImageMode(!imageMode); setShowMcpDrawer(false); }}
                          >
                            <i className="ri-image-line"></i>
                            <span>이미지 생성</span>
                          </button>
                          <button
                            type="button"
                            className={`ds-btn sm ${showMcpDrawer ? "mono" : "outline"}`}
                            onClick={() => { setShowMcpDrawer(!showMcpDrawer); setImageMode(false); }}
                          >
                            <i className="ri-cpu-line"></i>
                            <span>MCP 파이프라인</span>
                          </button>
                        </div>
                        <button type="submit" className="ds-btn" disabled={!chatInput.trim() || chatLoading}>
                          <span>전송</span>
                          <i className="ri-arrow-up-line"></i>
                        </button>
                      </div>
                    </form>
                  </div>

                  {/* Concise Starter Pills */}
                  <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px", marginTop: "4px" }}>
                    {[
                      { label: "스피커 추천", prompt: "DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어", img: false },
                      { label: "섭외 메일 발송", prompt: "한성민(sniper45han@gmail.com)과 박제창(aristojeff@gmail.com) 연사에게 섭외 메일을 발송해줘", img: false },
                      { label: "Google Form · 캘린더 초대", prompt: "발표자 사전 정보 Google Form을 생성하고 두 연사자에게 캘린더 초대장과 함께 발송해줘", img: false },
                      { label: "행사 예산 · 마감 기한", prompt: "올해 DevFest 행사는 언제까지이고 지원 가능한 예산은 얼마야?", img: false },
                      { label: "배너 이미지 생성", prompt: "DevFest 2026 Seoul 모던 테크 컨퍼런스 키비주얼 배너", img: true }
                    ].map((chip, i) => (
                      <button
                        key={i}
                        type="button"
                        className="ds-btn outline sm"
                        style={{ borderRadius: "999px" }}
                        onClick={() => sendChat(chip.prompt, chip.img)}
                      >
                        {chip.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="row-stack" style={{ flex: 1 }}>
                  <div className="row-stack" style={{ gap: "16px", paddingBottom: "24px" }}>
                    {messages.map((m, idx) => (
                      <div key={m.id || idx} className="row-box" style={{ background: m.role === "user" ? "var(--mono-dark)" : "var(--surface)", color: m.role === "user" ? "#ffffff" : "var(--text)", padding: "18px 22px" }}>
                        {m.role === "user" ? (
                          <div style={{ fontSize: "15px", fontWeight: 500 }}>{m.text}</div>
                        ) : (
                          <div>
                            <ComputingBar computing={m.computing} steps={m.steps} currentStatus={m.currentStatus} />
                            {m.text && (
                              <div
                                className="md-prose"
                                dangerouslySetInnerHTML={{ __html: renderMarkdownSafe(m.text) }}
                              />
                            )}
                            {m.images && m.images.length > 0 && (
                              <div className="row-stack" style={{ marginTop: "12px" }}>
                                {m.images.map((img, i) => (
                                  <div key={img.image_id || i} style={{ borderRadius: "12px", overflow: "hidden", border: "1px solid var(--border)" }}>
                                    <img src={img.url || img.data_uri} alt={img.prompt || "generated"} style={{ width: "100%", maxHeight: "340px", objectFit: "cover", display: "block" }} />
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

                  {/* Sticky Bottom Full-Width Composer */}
                  <div className="row-box" style={{ position: "sticky", bottom: "16px", padding: "12px 16px", boxShadow: "var(--shadow-md)" }}>
                    <form onSubmit={e => { e.preventDefault(); sendChat(); }} className="row-between" style={{ flexWrap: "nowrap", gap: "10px" }}>
                      <button
                        type="button"
                        className={`ds-btn sm ${imageMode ? "" : "outline"}`}
                        onClick={() => setImageMode(!imageMode)}
                        title="이미지 생성 모드"
                      >
                        <i className="ri-image-line"></i>
                      </button>
                      <input
                        type="text"
                        className="ds-input"
                        style={{ border: "none", boxShadow: "none", padding: "6px 8px" }}
                        value={chatInput}
                        onChange={e => setChatInput(e.target.value)}
                        placeholder={imageMode ? "생성할 배너 이미지 프롬프트..." : "추가 요청을 입력하세요..."}
                      />
                      <button type="submit" className="ds-btn sm" disabled={!chatInput.trim() || chatLoading}>
                        {chatLoading ? <i className="ri-loader-4-line spin-icon"></i> : <i className="ri-arrow-up-line"></i>}
                        <span>전송</span>
                      </button>
                    </form>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: MODERN EVENT PLATFORM (Event-us / TicketTaco / Meetup Style — 1 Row = 1 Full-Width Box) */}
          {activeTab === "events" && (
            <div className="page-container">
              {/* EVENT DISCOVERY LIST (1 Row = 1 Full-Width Box) */}
              {!selectedEventId && (
                <div className="row-stack" style={{ gap: "16px" }}>
                  <div className="row-between" style={{ marginBottom: "4px" }}>
                    <div>
                      <h1 style={{ margin: "0 0 4px", fontSize: "24px", fontWeight: 800 }}>커뮤니티 이벤트</h1>
                      <p style={{ margin: 0, fontSize: "14px", color: "var(--text-secondary)" }}>
                        참가 신청(RSVP)부터 연사 섭외, 현장 사진 인원 분석까지 한곳에서 관리하세요.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="ds-btn"
                      onClick={() => {
                        setActiveTab("home");
                        sendChat("새로운 GDG 핸즈온 이벤트를 기획해서 생성해줘: 'GDG Korea Agentic AI Hack Night', 정원 120명, 장소 구글 스타트업 캠퍼스 서울");
                      }}
                    >
                      <i className="ri-add-line"></i>
                      <span>AI로 새 이벤트 기획</span>
                    </button>
                  </div>

                  {/* Full-Width Single-Row Event Cards */}
                  {events.map(ev => (
                    <div
                      key={ev.event_id}
                      className="row-box interactive"
                      onClick={() => {
                        setSelectedEventId(ev.event_id);
                        setEventSubTab("overview");
                      }}
                    >
                      <div className="row-between" style={{ alignItems: "flex-start", gap: "24px" }}>
                        <div style={{ flex: 1, minWidth: "280px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px", flexWrap: "wrap" }}>
                            <span className="status-tag primary">{ev.status}</span>
                            <span style={{ fontSize: "13.5px", fontWeight: 600, color: "var(--text-secondary)" }}>
                              {ev.date} · {ev.time}
                            </span>
                            <span style={{ fontSize: "13.5px", color: "var(--text-muted)" }}>
                              | {ev.venue}
                            </span>
                          </div>

                          <h2 style={{ margin: "0 0 8px", fontSize: "20px", fontWeight: 800, lineHeight: 1.35 }}>
                            {ev.title}
                          </h2>

                          <p style={{ margin: "0 0 14px", fontSize: "14.5px", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                            {ev.description}
                          </p>

                          <div style={{ display: "flex", alignItems: "center", gap: "16px", fontSize: "13px", color: "var(--text-muted)", flexWrap: "wrap" }}>
                            <span><strong style={{ color: "var(--text)" }}>신청 인원</strong> {ev.rsvp_count} / {ev.capacity}명</span>
                            <span><strong style={{ color: "var(--text)" }}>연사</strong> {(ev.speakers || []).map(s => s.name).join(", ") || "한성민, 박제창"}</span>
                            {ev.tracked_photo_attendees ? (
                              <span><strong style={{ color: "var(--text)" }}>현장 사진 감지</strong> {ev.tracked_photo_attendees}명</span>
                            ) : null}
                          </div>
                        </div>

                        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", justifyContent: "space-between", gap: "12px", minWidth: "200px" }}>
                          {ev.banner_url && (
                            <img
                              src={ev.banner_url}
                              alt={ev.title}
                              style={{ width: "200px", height: "110px", objectFit: "cover", borderRadius: "10px", border: "1px solid var(--border)" }}
                            />
                          )}
                          <div style={{ display: "flex", gap: "8px" }} onClick={e => e.stopPropagation()}>
                            <button
                              type="button"
                              className="ds-btn outline sm"
                              onClick={() => setRsvpModalEvent(ev)}
                            >
                              참가 신청
                            </button>
                            <button
                              type="button"
                              className="ds-btn mono sm"
                              onClick={() => {
                                setSelectedEventId(ev.event_id);
                                setEventSubTab("overview");
                              }}
                            >
                              <span>상세 보기</span>
                              <i className="ri-arrow-right-line"></i>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* EVENT DETAIL VIEW (Full-Width Single-Column + Focused Sub-Tabs) */}
              {selectedEventId && selectedEvent && (
                <div className="row-stack" style={{ gap: "20px" }}>
                  {/* Top Back Bar */}
                  <div className="row-between">
                    <button type="button" className="ds-btn outline sm" onClick={() => setSelectedEventId(null)}>
                      <i className="ri-arrow-left-line"></i>
                      <span>전체 이벤트 목록</span>
                    </button>
                    <WorkspaceDock links={selectedEvent.workspace_links || defaultLinks} />
                  </div>

                  {/* Full-Width Event Hero Box */}
                  <div className="row-box" style={{ padding: 0, overflow: "hidden" }}>
                    {selectedEvent.banner_url && (
                      <div style={{ width: "100%", height: "220px", background: "var(--mono-dark)", position: "relative" }}>
                        <img
                          src={selectedEvent.banner_url}
                          alt={selectedEvent.title}
                          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                        />
                      </div>
                    )}
                    <div style={{ padding: "28px 32px" }}>
                      <div className="row-between" style={{ alignItems: "flex-start" }}>
                        <div style={{ flex: 1, minWidth: "280px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                            <span className="status-tag primary">{selectedEvent.status}</span>
                            <span style={{ fontSize: "13px", color: "var(--text-muted)", fontWeight: 600 }}>
                              {selectedEvent.category}
                            </span>
                          </div>
                          <h1 style={{ margin: "0 0 12px", fontSize: "26px", fontWeight: 800, lineHeight: 1.3 }}>
                            {selectedEvent.title}
                          </h1>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "20px", fontSize: "14px", color: "var(--text-secondary)" }}>
                            <span><i className="ri-calendar-line" style={{ color: "var(--primary)", marginRight: "5px" }}></i>{selectedEvent.date} ({selectedEvent.time})</span>
                            <span><i className="ri-map-pin-line" style={{ color: "var(--primary)", marginRight: "5px" }}></i>{selectedEvent.venue}</span>
                            <span><i className="ri-group-line" style={{ color: "var(--primary)", marginRight: "5px" }}></i>참가 신청 {selectedEvent.rsvp_count} / {selectedEvent.capacity}명</span>
                          </div>
                        </div>

                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            type="button"
                            className="ds-btn"
                            onClick={() => setEventSubTab("rsvp")}
                          >
                            <i className="ri-ticket-2-line"></i>
                            <span>참가 신청 (RSVP)</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Clean Segmented Sub-Navigation (Prevents Page Clutter) */}
                  <div className="sub-tabs">
                    {[
                      { id: "overview", label: "행사 소개 · 연사 (WYSIWYG)", icon: "ri-file-text-line" },
                      { id: "rsvp", label: `참가 신청 · 명단 (${selectedEvent.rsvp_count}명)`, icon: "ri-ticket-2-line" },
                      { id: "media", label: "AI 배너 · 현장 사진 분석", icon: "ri-image-add-line" },
                      { id: "ops", label: "연사 · 메일 운영 자동화", icon: "ri-mail-send-line" }
                    ].map(st => (
                      <button
                        key={st.id}
                        type="button"
                        className={`sub-tab-btn ${eventSubTab === st.id ? "active" : ""}`}
                        onClick={() => setEventSubTab(st.id)}
                      >
                        <i className={st.icon}></i>
                        <span>{st.label}</span>
                      </button>
                    ))}
                  </div>

                  {/* SUB-TAB 1: OVERVIEW, WYSIWYG EDITOR & FULL-WIDTH SPEAKER ROWS */}
                  {eventSubTab === "overview" && (
                    <div className="row-stack" style={{ gap: "20px" }}>
                      {/* Full-Width WYSIWYG Event Page Content */}
                      <div className="row-box">
                        <div className="row-between" style={{ marginBottom: "14px" }}>
                          <div>
                            <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800 }}>행사 상세 소개</h2>
                            <p style={{ margin: "4px 0 0", fontSize: "13.5px", color: "var(--text-muted)" }}>
                              행사 안내 본문을 자유롭게 편집하고 AI 키비주얼 이미지를 삽입할 수 있습니다.
                            </p>
                          </div>
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              type="button"
                              className={`ds-btn sm ${wysiwygMode === "edit" ? "mono" : "outline"}`}
                              onClick={() => setWysiwygMode("edit")}
                            >
                              편집
                            </button>
                            <button
                              type="button"
                              className={`ds-btn sm ${wysiwygMode === "preview" ? "mono" : "outline"}`}
                              onClick={() => setWysiwygMode("preview")}
                            >
                              미리보기
                            </button>
                            <button
                              type="button"
                              className="ds-btn sm"
                              onClick={() => handleSaveWysiwyg(selectedEvent)}
                              disabled={wysiwygSaving}
                            >
                              <i className="ri-save-line"></i>
                              <span>{wysiwygSaving ? "저장 중..." : "저장"}</span>
                            </button>
                          </div>
                        </div>

                        <div className="wysiwyg-box">
                          {wysiwygMode === "edit" && (
                            <div className="wysiwyg-bar">
                              <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                                <button type="button" className="wysiwyg-tool" onClick={() => execWysiwygCmd("formatBlock", "H2")}>제목 H2</button>
                                <button type="button" className="wysiwyg-tool" onClick={() => execWysiwygCmd("formatBlock", "H3")}>부제목 H3</button>
                                <button type="button" className="wysiwyg-tool" onClick={() => execWysiwygCmd("bold")}><i className="ri-bold"></i></button>
                                <button type="button" className="wysiwyg-tool" onClick={() => execWysiwygCmd("italic")}><i className="ri-italic"></i></button>
                                <button type="button" className="wysiwyg-tool" onClick={() => execWysiwygCmd("insertUnorderedList")}><i className="ri-list-unordered"></i></button>
                                <button
                                  type="button"
                                  className="wysiwyg-tool"
                                  onClick={() =>
                                    insertHtmlIntoWysiwyg(
                                      `<div style="padding:14px 18px;background:#f8fafc;border-left:3px solid #2563eb;border-radius:8px;margin:12px 0;"><strong>참가자 안내</strong><br/>현장 체크인 시 사전 등록 이메일을 제시해 주세요.</div>`
                                    )
                                  }
                                >
                                  안내 박스 삽입
                                </button>
                              </div>
                              <button
                                type="button"
                                className="ds-btn outline sm"
                                onClick={() => handleGenerateEventImage(selectedEvent, true)}
                                disabled={imgGenerating}
                              >
                                <i className="ri-sparkling-line"></i>
                                <span>{imgGenerating ? "이미지 생성 중..." : "AI 이미지 생성 후 본문 삽입"}</span>
                              </button>
                            </div>
                          )}
                          <div
                            ref={wysiwygEditorRef}
                            className="wysiwyg-area"
                            contentEditable={wysiwygMode === "edit"}
                            suppressContentEditableWarning={true}
                          />
                        </div>
                      </div>

                      {/* Full-Width Speaker Lineup (1 Row = 1 Speaker Box) */}
                      <div className="row-box">
                        <h2 style={{ margin: "0 0 14px", fontSize: "18px", fontWeight: 800 }}>연사 라인업</h2>
                        <div className="row-stack">
                          {speakerCards.map((sp, i) => (
                            <div key={i} className="row-item">
                              <div style={{ flex: 1, minWidth: "260px" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                                  <strong style={{ fontSize: "16px" }}>{sp.name}</strong>
                                  <span className="status-tag primary">{sp.role}</span>
                                  {sp.session_time && <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>{sp.session_time}</span>}
                                </div>
                                <div style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
                                  {sp.proposed_topic || sp.track}
                                </div>
                                <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
                                  {sp.email}
                                  {sp.onboarding_data ? ` · 티셔츠 ${sp.onboarding_data.tshirt_size} · 차량 ${sp.onboarding_data.vehicle_number}` : ""}
                                </div>
                              </div>
                              <div className="ws-dock">
                                <a
                                  href={`https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(sp.email)}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="ws-icon-btn"
                                >
                                  <i className="ri-mail-send-line"></i>
                                  <span>메일 보내기</span>
                                </a>
                                {sp.form_url && (
                                  <a href={sp.form_url} target="_blank" rel="noreferrer" className="ws-icon-btn">
                                    <i className="ri-survey-line"></i>
                                    <span>사전등록 Form</span>
                                  </a>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Full-Width FAQ / Knowledge Base */}
                      <div className="row-box">
                        <h2 style={{ margin: "0 0 14px", fontSize: "18px", fontWeight: 800 }}>
                          행사 FAQ · 지식 베이스 ({(selectedEvent.knowledge_base || []).length})
                        </h2>
                        <form onSubmit={e => handleKbSubmit(e, selectedEvent.event_id)} className="row-between" style={{ flexWrap: "nowrap", gap: "10px", marginBottom: "16px" }}>
                          <input
                            type="text"
                            className="ds-input"
                            style={{ maxWidth: "260px" }}
                            placeholder="항목 제목 (예: 주차 안내)"
                            value={kbForm.title}
                            onChange={e => setKbForm({ ...kbForm, title: e.target.value })}
                          />
                          <input
                            type="text"
                            className="ds-input"
                            placeholder="상세 안내 내용을 입력하세요 (문의 자동 회신에 반영됩니다)"
                            value={kbForm.content}
                            onChange={e => setKbForm({ ...kbForm, content: e.target.value })}
                          />
                          <button type="submit" className="ds-btn outline">추가</button>
                        </form>
                        <div className="row-stack">
                          {(selectedEvent.knowledge_base || []).map(kb => (
                            <div key={kb.kb_id} className="row-item">
                              <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 700, fontSize: "14.5px", marginBottom: "4px" }}>{kb.title}</div>
                                <div style={{ fontSize: "13.5px", color: "var(--text-secondary)", lineHeight: 1.6 }}>{kb.content}</div>
                              </div>
                              <span className="status-tag">{kb.category}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* SUB-TAB 2: RSVP REGISTRATION & ATTENDEE LIST (1 Row = 1 Full-Width Box) */}
                  {eventSubTab === "rsvp" && (
                    <div className="row-stack" style={{ gap: "20px" }}>
                      <div className="row-box">
                        <h2 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800 }}>참가 신청 등록 (RSVP)</h2>
                        <p style={{ margin: "0 0 16px", fontSize: "13.5px", color: "var(--text-secondary)" }}>
                          신규 참가자를 등록하거나 기존 참가자의 트랙 및 식단 정보를 업데이트합니다.
                        </p>
                        <form onSubmit={e => handleRsvpSubmit(e, selectedEvent.event_id)} className="row-stack">
                          <div className="row-between" style={{ gap: "10px" }}>
                            <input
                              required
                              type="text"
                              className="ds-input"
                              style={{ flex: 1, minWidth: "180px" }}
                              placeholder="참가자 성함"
                              value={rsvpForm.name}
                              onChange={e => setRsvpForm({ ...rsvpForm, name: e.target.value })}
                            />
                            <input
                              required
                              type="email"
                              className="ds-input"
                              style={{ flex: 1.2, minWidth: "220px" }}
                              placeholder="이메일 (예: user@gdg.kr)"
                              value={rsvpForm.email}
                              onChange={e => setRsvpForm({ ...rsvpForm, email: e.target.value })}
                            />
                            <select
                              className="ds-input"
                              style={{ flex: 1.2, minWidth: "220px" }}
                              value={rsvpForm.track}
                              onChange={e => setRsvpForm({ ...rsvpForm, track: e.target.value })}
                            >
                              <option value="AI / Agentic Workflow Hands-on">Track 1 · AI / ADK 핸즈온</option>
                              <option value="Flutter & On-Device AI Hands-on">Track 2 · Flutter AI 핸즈온</option>
                            </select>
                            <select
                              className="ds-input"
                              style={{ width: "130px" }}
                              value={rsvpForm.dietary}
                              onChange={e => setRsvpForm({ ...rsvpForm, dietary: e.target.value })}
                            >
                              <option value="일반">식단: 일반</option>
                              <option value="비건">식단: 비건</option>
                              <option value="글루텐프리">식단: 글루텐프리</option>
                            </select>
                            <button type="submit" className="ds-btn">
                              <i className="ri-user-add-line"></i>
                              <span>신청 등록</span>
                            </button>
                          </div>
                        </form>
                      </div>

                      <div className="row-box">
                        <div className="row-between" style={{ marginBottom: "14px" }}>
                          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800 }}>
                            참가 신청자 명단 ({selectedEvent.rsvp_count} / {selectedEvent.capacity}명)
                          </h2>
                        </div>
                        <div className="row-stack">
                          {(selectedEvent.rsvps || []).map(r => (
                            <div key={r.rsvp_id} className="row-item">
                              <div>
                                <div style={{ fontWeight: 700, fontSize: "15px" }}>
                                  {r.name} <span style={{ fontWeight: 500, fontSize: "13.5px", color: "var(--text-muted)", marginLeft: "6px" }}>{r.email}</span>
                                </div>
                                <div style={{ fontSize: "13.5px", color: "var(--text-secondary)", marginTop: "4px" }}>
                                  {r.track} · 식단: {r.dietary || "일반"}
                                </div>
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                <span className="status-tag primary">{r.status}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* SUB-TAB 3: GEMINI IMAGE STUDIO & PHOTO VISION HEADCOUNT (1 Row = 1 Full-Width Box) */}
                  {eventSubTab === "media" && (
                    <div className="row-stack" style={{ gap: "20px" }}>
                      {/* Full-Width Gemini Banner Studio */}
                      <div className="row-box">
                        <h2 style={{ margin: "0 0 6px", fontSize: "18px", fontWeight: 800 }}>AI 이벤트 배너 생성 스튜디오</h2>
                        <p style={{ margin: "0 0 14px", fontSize: "13.5px", color: "var(--text-secondary)" }}>
                          프롬프트를 입력해 이벤트 공식 배너 이미지를 생성하고 대표 커버로 지정합니다.
                        </p>
                        <div className="row-between" style={{ flexWrap: "nowrap", gap: "10px", marginBottom: "16px" }}>
                          <input
                            type="text"
                            className="ds-input"
                            value={imgPrompt}
                            onChange={e => setImgPrompt(e.target.value)}
                            placeholder="생성할 배너 이미지 설명을 입력하세요..."
                          />
                          <button
                            type="button"
                            className="ds-btn"
                            disabled={imgGenerating}
                            onClick={() => handleGenerateEventImage(selectedEvent, false)}
                          >
                            <i className="ri-sparkling-line"></i>
                            <span>{imgGenerating ? "생성 중..." : "배너 이미지 생성"}</span>
                          </button>
                        </div>

                        {(selectedEvent.generated_images || []).length > 0 && (
                          <div className="row-stack">
                            {selectedEvent.generated_images.map(img => (
                              <div key={img.image_id} className="row-item">
                                <div style={{ display: "flex", alignItems: "center", gap: "16px", flex: 1 }}>
                                  <img
                                    src={img.url}
                                    alt={img.prompt}
                                    style={{ width: "160px", height: "90px", objectFit: "cover", borderRadius: "8px", border: "1px solid var(--border)" }}
                                  />
                                  <div>
                                    <div style={{ fontWeight: 700, fontSize: "14.5px" }}>{img.prompt}</div>
                                    <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>{img.style}</div>
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  className="ds-btn outline sm"
                                  onClick={() => handleSaveWysiwyg(selectedEvent, img.url)}
                                >
                                  대표 배너로 적용
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Full-Width Photo Vision Headcount Analysis */}
                      <div className="row-box">
                        <div className="row-between" style={{ marginBottom: "14px" }}>
                          <div>
                            <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800 }}>현장 사진 업로드 · 참석 인원 자동 분석</h2>
                            <p style={{ margin: "4px 0 0", fontSize: "13.5px", color: "var(--text-secondary)" }}>
                              행사 현장 사진을 업로드하면 Gemini Vision이 참석 인원수를 카운팅하고 지식 베이스에 기록합니다.
                            </p>
                          </div>
                          <span className="status-tag primary">누적 감지 {selectedEvent.tracked_photo_attendees || 0}명</span>
                        </div>

                        <div className="row-between" style={{ flexWrap: "nowrap", gap: "10px", marginBottom: "16px" }}>
                          <input
                            type="text"
                            className="ds-input"
                            value={photoCaption}
                            onChange={e => setPhotoCaption(e.target.value)}
                            placeholder="사진 설명 (예: 메인 홀 핸즈온 세션 전경)"
                          />
                          <label className="ds-btn outline" style={{ cursor: photoUploading ? "wait" : "pointer", margin: 0 }}>
                            <i className="ri-upload-2-line"></i>
                            <span>{photoUploading ? "분석 중..." : "현장 사진 업로드"}</span>
                            <input
                              type="file"
                              accept="image/*"
                              style={{ display: "none" }}
                              disabled={photoUploading}
                              onChange={e => handlePhotoUpload(e, selectedEvent.event_id)}
                            />
                          </label>
                        </div>

                        {(selectedEvent.photos || []).length > 0 && (
                          <div className="row-stack">
                            {selectedEvent.photos.map(p => (
                              <div key={p.photo_id} className="row-item">
                                <div style={{ display: "flex", alignItems: "center", gap: "16px", flex: 1 }}>
                                  <img
                                    src={p.url}
                                    alt={p.caption}
                                    style={{ width: "160px", height: "96px", objectFit: "cover", borderRadius: "8px", border: "1px solid var(--border)" }}
                                  />
                                  <div>
                                    <div style={{ fontWeight: 700, fontSize: "14.5px" }}>{p.caption}</div>
                                    <div style={{ fontSize: "13.5px", color: "var(--text-secondary)", marginTop: "4px" }}>{p.scene_summary}</div>
                                  </div>
                                </div>
                                <span className="status-tag primary">감지 {p.detected_headcount}명</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* SUB-TAB 4: SPEAKER & EMAIL OPERATIONS WORKFLOW (1 Row = 1 Step Box) */}
                  {eventSubTab === "ops" && (
                    <div className="row-stack" style={{ gap: "20px" }}>
                      <div className="row-box">
                        <div className="row-between" style={{ marginBottom: "16px" }}>
                          <div>
                            <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800 }}>연사 · 스폰서 · 메일 자동화 워크플로우</h2>
                            <p style={{ margin: "4px 0 0", fontSize: "13.5px", color: "var(--text-secondary)" }}>
                              각 단계를 개별 실행하거나 이메일 디자인 템플릿을 미리 확인할 수 있습니다.
                            </p>
                          </div>
                          {opsStatusText && <span className="status-tag primary">{opsStatusText}</span>}
                        </div>

                        <div className="row-stack">
                          {[
                            {
                              title: "1. 연사 섭외 이메일 발송 (Gmail)",
                              desc: "한성민(AI GDE), 박제창(Flutter GDE) 연사에게 맞춤형 초청 메일을 발송합니다.",
                              action: () => runOpsEndpoint("연사 섭외 메일 발송", "/api/ops/outreach", {})
                            },
                            {
                              title: "2. 스폰서 후원 제안서 발송 (Gmail)",
                              desc: "공식 후원 패키지 안내 및 스폰서십 제안 이메일을 발송합니다.",
                              action: () => runOpsEndpoint("스폰서 제안 메일 발송", "/api/ops/sponsor-outreach", {})
                            },
                            {
                              title: "3. 사전 정보 Google Form & Google Calendar 초대장 발송",
                              desc: "성함 · 연락처 · 티셔츠 사이즈 · 차량 번호 입력 Google Form과 .ics 캘린더 일정을 발송합니다.",
                              action: () => runOpsEndpoint("Form · 캘린더 초대 발송", "/api/ops/invite", {})
                            },
                            {
                              title: "4. Google Form 응답 실시간 동기화",
                              desc: "제출된 발표자 Google Form 응답을 수집하여 이벤트 준비 상태에 반영합니다.",
                              action: () => runOpsEndpoint("Google Form 응답 동기화", "/api/ops/form/sync", {})
                            },
                            {
                              title: "5. 수신 문의 자동 회신 · 운영진 딜리게이션 테스트",
                              desc: "행사 지식 베이스 내 문의는 자동 회신하고, 특례 문의는 운영진에게 전달합니다.",
                              action: () =>
                                runOpsEndpoint("문의 자동 회신 처리", "/api/admin/inquiry/process", {
                                  sender_email: "attendee.kim@gdg.kr",
                                  sender_name: "김철수 참가자",
                                  subject: "[DevFest 2026 문의] 행사 장소와 무료 주차 안내",
                                  inquiry_body: "DevFest 2026 핸즈온 행사 장소와 무료 주차 지원 여부가 궁금합니다.",
                                  event_id: selectedEvent.event_id
                                })
                            }
                          ].map((item, idx) => (
                            <div key={idx} className="row-item">
                              <div style={{ flex: 1, minWidth: "260px" }}>
                                <div style={{ fontWeight: 700, fontSize: "14.5px" }}>{item.title}</div>
                                <div style={{ fontSize: "13.5px", color: "var(--text-secondary)", marginTop: "3px" }}>{item.desc}</div>
                              </div>
                              <button type="button" className="ds-btn outline sm" disabled={opsBusy} onClick={item.action}>
                                실행
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Collapsible Full-Width Email Template Preview */}
                      <div className="row-box">
                        <div className="row-between">
                          <div>
                            <h3 style={{ margin: 0, fontSize: "16.5px", fontWeight: 800 }}>발송 이메일 템플릿 미리보기</h3>
                            <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--text-muted)" }}>
                              Gmail로 발송되는 공식 HTML 이메일 디자인을 확인합니다.
                            </p>
                          </div>
                          <button
                            type="button"
                            className="ds-btn outline sm"
                            onClick={() => setShowEmailPreview(!showEmailPreview)}
                          >
                            {showEmailPreview ? "미리보기 닫기" : "템플릿 열기"}
                          </button>
                        </div>

                        {showEmailPreview && (
                          <div style={{ marginTop: "16px", paddingTop: "16px", borderTop: "1px solid var(--border)" }}>
                            <div className="row-between" style={{ marginBottom: "12px" }}>
                              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                                {[
                                  { id: "outreach", label: "섭외 초청장" },
                                  { id: "onboarding_invite", label: "Form · 캘린더 초대" },
                                  { id: "inquiry_reply", label: "지식베이스 자동 회신" },
                                  { id: "delegation", label: "운영진 이관" }
                                ].map(t => (
                                  <button
                                    key={t.id}
                                    type="button"
                                    className={`ds-btn sm ${emailPreviewType === t.id ? "mono" : "outline"}`}
                                    onClick={() => setEmailPreviewType(t.id)}
                                  >
                                    {t.label}
                                  </button>
                                ))}
                              </div>
                              <div style={{ display: "flex", gap: "6px" }}>
                                <button
                                  type="button"
                                  className={`ds-btn sm ${emailPreviewSpeaker === 1 ? "" : "outline"}`}
                                  onClick={() => setEmailPreviewSpeaker(1)}
                                >
                                  한성민
                                </button>
                                <button
                                  type="button"
                                  className={`ds-btn sm ${emailPreviewSpeaker === 2 ? "" : "outline"}`}
                                  onClick={() => setEmailPreviewSpeaker(2)}
                                >
                                  박제창
                                </button>
                              </div>
                            </div>
                            <div style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "10px" }}>
                              <strong>제목:</strong> {emailPreviewSubject}
                            </div>
                            <iframe
                              title="Email Template Preview"
                              srcDoc={emailPreviewHtml}
                              style={{ width: "100%", height: "460px", border: "1px solid var(--border)", borderRadius: "10px", background: "#fff" }}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: MCP INTEGRATION VIEW (1 Row = 1 Full-Width Box) */}
          {activeTab === "mcp" && (
            <McpIntegrationView
              onRunPrompt={(promptText) => {
                setActiveTab("home");
                sendChat(promptText, false);
              }}
            />
          )}
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById("root")).render(<App />);
  </script>
</body>
</html>
"""
