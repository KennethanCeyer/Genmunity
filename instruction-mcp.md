# Genmunity MCP & A2A 에이전트 사용 가이드 (`instruction-mcp.md`)

이 문서는 새로운 **Antigravity (`agy`)** 세션이나 외부 에이전트(Claude Code, Cursor, Gemini CLI 등)에서 **Genmunity Multi-Agent 시스템(Google ADK + A2A + MCP)**을 즉시 호출하고 활용하기 위한 구체적인 명세서입니다.

---

## 1. 배포된 퍼블릭 엔드포인트 및 MCP 등록 현황

### 1.1 Cloud Run 퍼블릭 배포 정보 (`kr-devsummit26icn-501` / `devstar5011@gcplab.me`)
- **웹 대시보드 (React JS, Light Theme, 80px GNB, Remix Icon, Plus Jakarta Sans & Pretendard)**:
  - URL: `https://genmunity-858263435030.asia-northeast3.run.app`
- **Google ADK A2A (Agent-to-Agent) 엔드포인트**:
  - AgentCard Discovery: `GET https://genmunity-858263435030.asia-northeast3.run.app/.well-known/agent-card.json`
  - A2A JSON-RPC 2.0: `POST https://genmunity-858263435030.asia-northeast3.run.app/a2a`
- **MCP (Model Context Protocol) 서버 엔드포인트**:
  - Remote Streamable HTTP / JSON-RPC: `POST https://genmunity-858263435030.asia-northeast3.run.app/mcp`
  - MCP 도구 카탈로그 조회: `GET https://genmunity-858263435030.asia-northeast3.run.app/api/mcp/tools`

### 1.2 Antigravity (`agy`) 글로벌 MCP 등록 설정 (`~/.gemini/config/mcp_config.json`)
이미 현재 머신의 `~/.gemini/config/mcp_config.json`에 아래 두 MCP 서버가 등록되어 있어, 새로 띄운 `agy` 세션에서 즉시 도구를 사용할 수 있습니다:
- **`genmunity` (Local Stdio MCP Server)**:
  - Command: `/Users/pignose/Genmunity/.venv/bin/python -m genmunity_agent.mcp_a2a`
- **`genmunity-cloud` (Remote Cloud Run HTTP MCP Server)**:
  - URL: `https://genmunity-858263435030.asia-northeast3.run.app/mcp`

---

## 2. MCP를 통해 사용 가능한 전체 도구 (12종) 및 호출 방법

새로운 `agy` 세션에서 에이전트에게 명령할 때 아래 도구 이름과 파라미터를 그대로 지시하거나 자연어로 요청하면 됩니다.

### A. 통합 코디네이터 (`RootAgent`)
1. **`GenmunityRootAgent`**
   - **역할**: Google ADK `RootAgent`에 자연어 프롬프트를 전달하여 하위 `SearchAgent` 및 `OpsAgent`를 자동 라우팅/오케스트레이션합니다.
   - **입력 파라미터**:
     - `request` (string, 필수): 자연어 요청 문장
   - **예시 요청**:
     - `"DevFest 핸즈온 행사에 필요한 스피커 연사를 찾고 있어"`
     - `"올해 DevFest 행사는 언제까지?"`
     - `"DevFest 지원가능한 예산은?"`

### B. 커뮤니티 검색 & 행사 지식 베이스 (`SearchAgent`)
2. **`rag_search_tool`**
   - **역할**: `CommunityHub`, `Advocu`, [국내 GDG/GDE 운영진 시트](https://docs.google.com/spreadsheets/d/1tC31_8IuWH-2TIeX0t84nyRI0YyaBSI52n97acG32-c/edit?usp=sharing), 그리고 행사 지식 베이스를 통합 RAG 검색합니다.
   - **반환 데이터**:
     - 추천 핸즈온 연사자 2명:
       1. **첫번째 연사자**: **한성민** (`sniper45han@gmail.com`) — **AI GDE**
       2. **두번째 연사자**: **박제창** (`aristojeff@gmail.com`) — **Flutter GDE**
     - 올해 DevFest 시즌 마감일 (2026년 12월 31일) 및 예산 정책 ($1,500 ~ $5,000)
   - **입력 파라미터**:
     - `query` (string, 필수): 검색어 (예: `"DevFest 핸즈온 스피커"`, `"DevFest 예산"`)

3. **`search_event_knowledge_base_tool`**
   - **역할**: 등록된 모든 이벤트의 상태, RSVP 현황, **현장 사진 업로드로 Gemini Vision이 자동 카운팅한 참가 인원수 통계(`tracked_photo_attendees`)**, 그리고 행사 지식 베이스 문서를 검색합니다.
   - **입력 파라미터**:
     - `query` (string, 선택): 이벤트 ID(`devfest-2026-seoul`) 또는 키워드 (예: `"참석자 수"`, `"주차"`)

4. **`slack_search_tool`**
   - **역할**: GDG/GDE Slack 채널(`#devfest-2026-organizers`, `#gde-korea-speakers`, `#devfest-2026-ops`) 스레드를 검색합니다.
   - **입력 파라미터**:
     - `query` (string, 필수): 검색 키워드 (예: `"핸즈온"`, `"한성민"`, `"박제창"`)

### C. 이벤트 운영 자동화 워크플로우 (`OpsAgent` Step 1 ~ Step 5)
5. **`get_target_speakers_tool`** *(Step 1)*
   - **역할**: SearchAgent에서 매칭된 두 연사자(`한성민` AI GDE `sniper45han@gmail.com`, `박제창` Flutter GDE `aristojeff@gmail.com`) 정보를 로드합니다.
   - **입력 파라미터**: 없음 (`{}`)

6. **`generate_and_send_speaker_emails_tool`** *(Step 2)*
   - **역할**: Gemini(`GenContent`)로 연사별 맞춤형 섭외 이메일을 생성하고 **Gmail API**를 통해 `sniper45han@gmail.com`, `aristojeff@gmail.com`으로 실제 발송합니다.
   - **입력 파라미터**:
     - `custom_context` (string, 선택): 메일 작성 시 추가할 안내 문구

7. **`collect_and_cluster_event_emails_tool`** *(Step 3)*
   - **역할**: Gmail에서 해당 이벤트 및 연사 관련 메일 수신 여부를 확인하고, 수집된 메일들을 Gemini로 의미별 클러스터(`연사 섭외 발송 및 수신 확인`, `연사 회신 및 세션 조율`, `발표자 온보딩 Form 및 캘린더 초대`)로 분류합니다.
   - **입력 파라미터**:
     - `max_results` (integer, 기본값 `20`)

8. **`create_speaker_onboarding_form_tool`** *(Step 4)*
   - **역할**: 발표자 사전 정보를 수집하는 온보딩 Form을 생성합니다.
   - **수집 항목**: **발표자 성함**, **이메일**, **연락처**, **티셔츠 사이즈(`S`~`3XL`)**, **차량 번호(무료 주차 등록용)**, **핸즈온 세션 제목**
   - **입력 파라미터**:
     - `form_title` (string, 선택): 커스텀 폼 제목

9. **`invite_speakers_with_form_and_calendar_tool`** *(Step 5)*
   - **역할**: 생성된 온보딩 Form 링크와 Google Calendar 일정 초대장(`.ics` `METHOD:REQUEST`)을 두 연사자(`sniper45han@gmail.com`, `aristojeff@gmail.com`)에게 이메일로 발송합니다.
   - **입력 파라미터**:
     - `form_id` (string, 선택): 비워두면 가장 최근 생성된 Form을 자동 사용

### D. 이벤트 생성/수정, 참가자 RSVP 관리, 행사 지식 베이스 등록 (`EventHub`)
10. **`manage_event_rsvp_tool`**
    - **역할**: 특정 이벤트의 참가자 RSVP를 신규 생성(`create`), 기존 정보 수정(`modify`), 또는 취소(`cancel`)합니다.
    - **입력 파라미터**:
      - `attendee_name` (string, 필수): 참가자 이름 (예: `"김민수"`, `"최유진"`)
      - `attendee_email` (string, 기본값 `"attendee@gdg.kr"`): 참가자 이메일
      - `event_id` (string, 기본값 `"devfest-2026-seoul"`): 대상 이벤트 ID 또는 제목
      - `action` (string, `"create"` | `"modify"` | `"cancel"`, 기본값 `"create"`)
      - `role` (string, 기본값 `"Developer"`)
      - `track` (string, 기본값 `"AI / Agentic Workflow Hands-on"`)
      - `dietary` (string, 기본값 `"일반"`, 예: `"비건"`)

11. **`create_or_modify_event_tool`**
    - **역할**: 새로운 커뮤니티 이벤트를 생성하거나 기존 이벤트의 제목, 일정, 장소, 상태, 정원, 예산을 수정합니다.
    - **입력 파라미터**:
      - `title` (string, 필수): 이벤트 제목
      - `event_id` (string, 선택): 수정할 이벤트 ID (비워두면 신규 생성 또는 제목 매칭)
      - `date` (string, 예: `"2026-11-21"`)
      - `venue` (string, 예: `"구글 스타트업 캠퍼스 서울"`)
      - `status` (string, 예: `"참가자 모집 중 (RSVP 오픈)"`)
      - `capacity` (integer, 예: `200`)
      - `budget` (string, 예: `"$3,000"`)
      - `description` (string, 선택)

12. **`add_event_knowledge_tool`**
    - **역할**: 특정 이벤트의 지식 베이스(Knowledge Base)에 운영 매뉴얼, FAQ, 현장 기록을 추가하여 `SearchAgent`가 RAG 검색에 즉시 활용하도록 합니다.
    - **입력 파라미터**:
      - `title` (string, 필수): 지식 항목 제목
      - `content` (string, 필수): 상세 내용
      - `event_id` (string, 기본값 `"devfest-2026-seoul"`)
      - `category` (string, 기본값 `"Event Knowledge"`)

---

## 3. 새 `agy` 세션에서 바로 복사해서 쓸 수 있는 프롬프트 예시

새로 띄운 `agy` 창에서 아래와 같이 요청해 보세요:

1. **스피커 검색 및 예산/일정 확인**:
   > "genmunity MCP의 `rag_search_tool`을 사용해서 DevFest 핸즈온 행사에 필요한 스피커 연사와 올해 DevFest 마감 기한, 지원 가능한 예산을 조회해줘."

2. **OpsAgent 연사 섭외 -> 클러스터링 -> Form 생성 -> 초대 발송**:
   > "genmunity MCP 도구들을 순서대로 호출해서 한성민(sniper45han@gmail.com, AI GDE)과 박제창(aristojeff@gmail.com, Flutter GDE) 연사에게 섭외 메일을 발송(`generate_and_send_speaker_emails_tool`)하고, 수신 메일을 클러스터링(`collect_and_cluster_event_emails_tool`)한 뒤, 발표자 온보딩 Form을 생성(`create_speaker_onboarding_form_tool`)해서 캘린더 초대장과 함께 발송(`invite_speakers_with_form_and_calendar_tool`)해줘."

3. **이벤트 RSVP 생성 및 수정**:
   > "genmunity MCP의 `manage_event_rsvp_tool`을 호출해서 `devfest-2026-seoul` 이벤트에 참가자 '박지훈'(`jihoon@gdg.kr`, Flutter 트랙)을 RSVP 등록하고, 기존 참가자 '김민수'(`minsu.kim@gdg.kr`)의 식단을 '비건'으로 수정(`action='modify'`)해줘."

4. **행사 지식 베이스 추가 및 사진 기반 참석자 통계 검색**:
   > "genmunity MCP의 `add_event_knowledge_tool`로 `devfest-2026-seoul`에 '케이터링 및 다과 안내: 오후 3시 10분 오토웨이타워 로비에서 제공' 지식을 등록하고, `search_event_knowledge_base_tool`로 전체 이벤트 지식과 사진 추적 참석자 수를 조회해줘."
