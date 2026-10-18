# Genmunity MCP 빠른 연동 가이드

Genmunity의 에이전트 워크플로우(연사 탐색, 섭외 메일 발송, Google Form 사전 등록, 캘린더 초대, 이벤트 RSVP 관리)를 **Antigravity (`agy`)**, **Claude Code**, **OpenAI Codex**, **Cursor**, **Gemini CLI**에 바로 연결해 자연어로 사용할 수 있습니다.

---

## 1. 에이전트별 MCP 설치 스니펫

### Antigravity (`agy`)
`~/.gemini/config/mcp_config.json` 파일에 아래 설정을 추가합니다.

```json
{
  "mcpServers": {
    "genmunity": {
      "url": "https://genmunity-858263435030.asia-northeast3.run.app/mcp"
    }
  }
}
```

로컬 개발 환경을 직접 연결하려면 stdio 모드로 등록할 수 있습니다:

```json
{
  "mcpServers": {
    "genmunity-local": {
      "command": "/Users/pignose/Genmunity/.venv/bin/python",
      "args": ["-m", "genmunity_agent.mcp_a2a"],
      "cwd": "/Users/pignose/Genmunity"
    }
  }
}
```

---

### Claude Code (`claude`)
터미널에서 한 줄 명령어로 즉시 등록하거나 `.mcp.json`에 추가합니다.

```bash
claude mcp add --transport http genmunity https://genmunity-858263435030.asia-northeast3.run.app/mcp
```

```json
{
  "mcpServers": {
    "genmunity": {
      "type": "http",
      "url": "https://genmunity-858263435030.asia-northeast3.run.app/mcp"
    }
  }
}
```

---

### OpenAI Codex (`codex`)
`~/.codex/config.toml` 파일에 아래 블록을 추가합니다.

```toml
[mcp_servers.genmunity]
url = "https://genmunity-858263435030.asia-northeast3.run.app/mcp"
```

로컬 stdio 실행이 필요한 경우:

```toml
[mcp_servers.genmunity]
command = "/Users/pignose/Genmunity/.venv/bin/python"
args = ["-m", "genmunity_agent.mcp_a2a"]
cwd = "/Users/pignose/Genmunity"
```

---

### Cursor / Windsurf
프로젝트 루트의 `.cursor/mcp.json`에 아래 설정을 추가합니다.

```json
{
  "mcpServers": {
    "genmunity": {
      "url": "https://genmunity-858263435030.asia-northeast3.run.app/mcp"
    }
  }
}
```

---

## 2. 바로 복사해서 쓰는 실전 프롬프트

개별 함수 이름이나 파라미터를 외울 필요 없이, 연결된 에이전트에게 자연어로 목표만 지시하면 `GenmunityRootAgent`와 하위 워크플로우 도구가 자동으로 실행됩니다.

### 연사 추천 및 행사 예산·일정 확인
```text
DevFest 2026 핸즈온 세션에 적합한 AI / Flutter GDE 연사를 추천해주고, 올해 행사 마감 기한과 지원 가능한 예산 범위를 정리해줘.
```

### 연사 섭외부터 Google Form · 캘린더 초대까지 원스톱 실행
```text
한성민(sniper45han@gmail.com)과 박제창(aristojeff@gmail.com) 연사에게 초청 메일을 보내고, 발표자 사전 정보(티셔츠 사이즈, 차량 번호) 입력용 Google Form과 캘린더 초대장을 함께 발송해줘.
```

### 스폰서 후원 제안서 발송 및 수신 문의 자동 처리
```text
DevFest 2026 공식 스폰서십 제안 메일을 발송하고, 최근 수신된 행사 문의 메일을 확인해서 지식 베이스 기반으로 자동 회신하거나 운영진에게 전달해줘.
```

### 이벤트 생성 · 배너 디자인 · 참가자 RSVP 관리
```text
DevFest 2026 서울 행사의 현재 참가자 RSVP 현황과 현장 사진 분석 인원을 요약해주고, 신규 참가자 '박지훈(jihoon@gdg.kr, Flutter 트랙)'을 RSVP에 등록해줘.
```

---

## 3. 엔드포인트 요약

| 구분 | URL / 명령어 |
| --- | --- |
| **MCP HTTP Endpoint** | `https://genmunity-858263435030.asia-northeast3.run.app/mcp` |
| **MCP Local Stdio** | `python -m genmunity_agent.mcp_a2a` |
| **A2A AgentCard** | `https://genmunity-858263435030.asia-northeast3.run.app/.well-known/agent-card.json` |
| **Web Console** | `https://genmunity-858263435030.asia-northeast3.run.app` |
