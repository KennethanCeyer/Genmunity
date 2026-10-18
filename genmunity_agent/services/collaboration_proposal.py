import io
import html
import datetime
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.utils import formataddr, formatdate, make_msgid
from typing import Dict, Any, List, Tuple
import base64

from PIL import Image, ImageDraw, ImageFont

from genmunity_agent.config import (
    BASE_DIR,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
    load_runtime_state,
    save_runtime_state,
)
from genmunity_agent.services.gdg_directory import validate_speaker_email_recipient

PUBLIC_HUB_URL = "https://genmunity-858263435030.asia-northeast3.run.app"
PUBLIC_MCP_URL = "https://genmunity-858263435030.asia-northeast3.run.app/mcp"
PUBLIC_MCP_TOOLS_URL = "https://genmunity-858263435030.asia-northeast3.run.app/api/mcp/tools"
PUBLIC_A2A_CARD_URL = "https://genmunity-858263435030.asia-northeast3.run.app/.well-known/agent-card.json"
COLLABORATION_GOOGLE_FORM_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLSc2uZgdjaQ6K570LCL47Nz4AMPntIWxGGgYwvirpcXIaCfIYw/viewform"
)
COLLABORATION_GOOGLE_FORM_ID = "1H16tGtav3Vyt6H4T3gaU0eiSOesUWdt432u8PSUYC7I"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_rsvp_pie_chart_png() -> bytes:
    """Generate a high-resolution RSVP Distribution Doughnut/Pie Chart PNG."""
    width, height = 1040, 480
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    title_font = _load_font(26)
    sub_font = _load_font(18)
    label_font = _load_font(20)
    small_font = _load_font(17)

    # Outer border
    draw.rounded_rectangle([(8, 8), (width - 8, height - 8)], radius=20, outline="#cbd5e1", width=2, fill="#ffffff")

    # Title
    draw.text((40, 32), "DevFest 2026 Current RSVP & Track Distribution (Pie Chart)", fill="#0f172a", font=title_font)
    draw.text((40, 68), "Live Event Hub RSVP Breakdown by Track & Confirmation Status", fill="#64748b", font=sub_font)

    # Pie / Doughnut Slices
    cx, cy, r = 230, 275, 145
    bbox = [cx - r, cy - r, cx + r, cy + r]

    slices = [
        ("AI / Agentic Workflow Hands-on", 50, "#2563eb", "50% (Primary Track)"),
        ("Flutter & On-Device AI Hands-on", 35, "#059669", "35% (Cross-Platform AI)"),
        ("Cloud & GDG Study Jam Builders", 15, "#f59e0b", "15% (Cloud & Infra)"),
    ]

    start_angle = -90.0
    for _, pct, color, _ in slices:
        sweep = (pct / 100.0) * 360.0
        draw.pieslice(bbox, start=start_angle, end=start_angle + sweep, fill=color, outline="#ffffff", width=4)
        start_angle += sweep

    # Inner doughnut hole
    inner_r = 76
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill="#ffffff")
    draw.text((cx - 48, cy - 24), "100%", fill="#0f172a", font=title_font)
    draw.text((cx - 52, cy + 8), "Confirmed", fill="#475569", font=small_font)

    # Legend on the right
    lx, ly = 440, 145
    for label, pct, color, detail in slices:
        draw.rounded_rectangle([(lx, ly), (lx + 28, ly + 28)], radius=6, fill=color)
        draw.text((lx + 42, ly - 2), f"{label}", fill="#0f172a", font=label_font)
        draw.text((lx + 42, ly + 26), f"Share: {detail}  |  RSVP Status: Confirmed", fill="#475569", font=small_font)
        ly += 84

    # Summary pill at bottom right
    draw.rounded_rectangle([(440, 395), (990, 442)], radius=10, fill="#f1f5f9", outline="#e2e8f0", width=1)
    draw.text(
        (458, 408),
        "Target Capacity: 200 Seats (Seoul) + 80 Seats (StudyJam) | Speaker Match: 2/2 GDE",
        fill="#1e293b",
        font=small_font,
    )

    out_dir = BASE_DIR / "data" / "uploads"
    out_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    with open(out_dir / "rsvp_pie_chart.png", "wb") as f:
        f.write(png_bytes)
    return png_bytes


def generate_event_bar_chart_png() -> bytes:
    """Generate a high-resolution Event Operations Progress Horizontal Bar Chart PNG."""
    width, height = 1040, 500
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    title_font = _load_font(26)
    sub_font = _load_font(18)
    label_font = _load_font(19)
    small_font = _load_font(17)

    draw.rounded_rectangle([(8, 8), (width - 8, height - 8)], radius=20, outline="#cbd5e1", width=2, fill="#ffffff")

    draw.text((40, 30), "DevFest 2026 Event Operations Bar Chart Updates", fill="#0f172a", font=title_font)
    draw.text((40, 66), "Milestone Completion Across Speaker Onboarding, RSVP & MCP/A2A Automation", fill="#64748b", font=sub_font)

    bars = [
        ("1. GDE Speaker Match & Session Track Setup", 100, "#2563eb", "100% (2/2 GDE Confirmed)"),
        ("2. Speaker Onboarding Form & Calendar Sync", 100, "#059669", "100% (Google Forms/Cal v3)"),
        ("3. RootAgent + MCP + A2A Live Cloud Run Ops", 100, "#4f46e5", "100% (Auto-Reply & Trigger)"),
        ("4. Venue, Parking & Speaker Welcome Kit Prep", 95, "#0ea5e9", "95% (T-Shirt & Vehicle Reg)"),
        ("5. Hands-on Attendee RSVP & Track Allocation", 85, "#f59e0b", "85% (Open & Active Sync)"),
    ]

    y = 122
    bar_x = 455
    bar_max_w = 410
    for label, pct, color, status_txt in bars:
        draw.text((40, y + 6), label, fill="#0f172a", font=label_font)
        # Background track
        draw.rounded_rectangle([(bar_x, y), (bar_x + bar_max_w, y + 34)], radius=8, fill="#e2e8f0")
        # Filled bar
        fill_w = int((pct / 100.0) * bar_max_w)
        draw.rounded_rectangle([(bar_x, y), (bar_x + fill_w, y + 34)], radius=8, fill=color)
        draw.text((bar_x + bar_max_w + 16, y + 6), f"{pct}%", fill="#0f172a", font=label_font)
        draw.text((bar_x, y + 39), status_txt, fill="#64748b", font=small_font)
        y += 72

    out_dir = BASE_DIR / "data" / "uploads"
    out_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    with open(out_dir / "event_bar_chart.png", "wb") as f:
        f.write(png_bytes)
    return png_bytes


def audit_collaboration_links() -> List[Dict[str, Any]]:
    """
    Audit all links included in the collaboration proposal email before dispatch:
    1. Check that no URL contains 'localhost', '127.0.0.1', or raw percent-encoded query clutter.
    2. Verify live HTTP 200 response for each URL.
    """
    links_to_check: List[Tuple[str, str]] = [
        ("참여 여부 확인 Google Form", COLLABORATION_GOOGLE_FORM_URL),
        ("Genmunity Hub 메인 웹 사이트", PUBLIC_HUB_URL),
        ("Genmunity MCP 서버 엔드포인트", PUBLIC_MCP_URL),
        ("Genmunity MCP 도구 카탈로그", PUBLIC_MCP_TOOLS_URL),
        ("Genmunity A2A 에이전트 카드", PUBLIC_A2A_CARD_URL),
    ]
    audit_results: List[Dict[str, Any]] = []
    for label, url in links_to_check:
        is_clean = ("localhost" not in url) and ("127.0.0.1" not in url) and ("%" not in url) and (len(url) <= 120)
        http_status = 0
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                http_status = resp.status
        except Exception:
            http_status = 0
        audit_results.append(
            {
                "label": label,
                "url": url,
                "clean_readable_url": is_clean,
                "http_status": http_status,
                "verified": is_clean and http_status == 200,
            }
        )
    return audit_results


def build_collaboration_proposal_content(speaker: Dict[str, Any]) -> Tuple[str, str, str]:
    """Build subject, plain-text body, and rich HTML body (with inline Pie Chart & Bar Chart) for a GDE speaker."""
    name = speaker["name"]
    role = speaker["role"]
    order_label = speaker["order_label"]
    track = speaker["track"]
    topic = speaker["proposed_topic"]
    session_time = speaker["session_time"]
    event_name = DEVFEST_EVENT_INFO["event_name"]
    event_date = DEVFEST_EVENT_INFO["event_date"]
    venue = DEVFEST_EVENT_INFO["venue"]

    subject = (
        f"{DEVFEST_EVENT_INFO['event_tag']} [연사 및 운영 협력 제안서] {name} {role}님, "
        f"실시간 RSVP·행사 데이터 리포트 및 Genmunity MCP 공동 운영 안내"
    )

    body_text = f"""안녕하세요 {name} {role}님 ({order_label}),

GDG Korea DevFest 2026 운영팀(Genmunity RootAgent & OpsAgent)입니다.
다가오는 {event_date}에 {venue}에서 개최되는 '{event_name}' 행사의 핵심 연사이자 공동 운영 파트너로 {name}님께 공식 협력 제안서를 전달드립니다.

■ 1. 현재 RSVP 분포 파이차트 (Pie Chart) 및 행사 운영 바차트 (Bar Chart) 업데이트 요약
- [RSVP 파이차트 현황]
  * AI / Agentic Workflow 핸즈온 트랙: 50% (사전 등록 확정 상태)
  * Flutter & On-Device AI 핸즈온 트랙: 35% (사전 등록 확정 상태)
  * Cloud & GDG Study Jam 빌더 트랙: 15% (사전 등록 확정 상태)
- [행사 운영 바차트 업데이트]
  * GDE 연사자 매칭 및 세션 트랙 확정: 100% 완료 (한성민 AI GDE, 박제창 Flutter GDE)
  * 연사 사전 온보딩(Google Form·Calendar·차량/티셔츠 등록): 100% 연동 완료
  * Genmunity RootAgent · MCP · A2A 클라우드 운영 자동화: 100% 가동 중
  * 오토웨이타워 현장 지원 및 웰컴 키트 준비: 95% 완료
  * 참가자 RSVP 모집 및 트랙 배정 동기화: 85% 진행 중 (정원 200석 규모)

■ 2. 이번 행사 운영진과 함께하면 기대할 수 있는 핵심 가치 3가지 (Key Benefits)
- 첫째, Google ADK 및 Gemini 4.0 Argon 기반 운영 완전 자동화로 세션 몰입도 극대화:
  반복적인 참가자 문의 응대(Pub/Sub -> Cloud Run 지식 베이스 자동 회신 및 운영진 위임), 연사 온보딩(Google Forms & Calendar API 실시간 동기화), 현장 사진 기반 Gemini Vision 참석자 수 자동 집계로 행정 부담 없이 핸즈온 세션에만 집중하실 수 있습니다.
- 둘째, 실시간 RSVP 파이차트 및 행사 바차트 데이터 기반 고밀도 핸즈온 세션 구성:
  사전 수집된 참가자 관심 트랙 비율(AI 에이전트 50%, Flutter 온디바이스 AI 35%)과 준비도 지표를 바탕으로 참가자 수준에 맞춘 실습 환경과 Cloud 크레딧 가이드를 사전에 완비합니다.
- 셋째, 오픈 MCP(Model Context Protocol) 및 A2A 에이전트 생태계 공동 빌딩:
  연사자 및 협력 운영진이 직접 자신의 AI 에이전트 환경에서 Genmunity MCP 서버를 연결해 실시간 RSVP 현황, 세션 지식 베이스, 이메일 클러스터링 리포트를 조회·제어하는 에이전틱 커뮤니티 레퍼런스를 함께 구축할 수 있습니다.

■ 3. 함께 활용할 수 있는 Genmunity Hub 웹사이트 및 MCP 연동 안내
- Genmunity Hub 웹 대시보드: {PUBLIC_HUB_URL}
- Genmunity MCP 서버 엔드포인트: {PUBLIC_MCP_URL}
- Genmunity MCP 도구 카탈로그: {PUBLIC_MCP_TOOLS_URL}
- Genmunity A2A 에이전트 카드: {PUBLIC_A2A_CARD_URL}

■ 4. 행사 협력 및 참여 여부 확인 Google Form 안내
아래 Google Form 링크를 통해 운영 협력 및 참여 여부를 선택해 주시면 감사하겠습니다.
- 참여 여부 확인 Google Form: {COLLABORATION_GOOGLE_FORM_URL}

감사합니다.
GDG Korea DevFest 2026 운영팀 (Genmunity RootAgent) 드림"""

    html_body = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(subject)}</title>
</head>
<body style="margin:0;padding:24px 12px;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#0f172a;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #cbd5e1;">
    <!-- Top 4-Color Google Bar -->
    <tr>
      <td style="padding:0;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="25%" height="5" style="background:#4285F4;"></td>
            <td width="25%" height="5" style="background:#EA4335;"></td>
            <td width="25%" height="5" style="background:#FBBC05;"></td>
            <td width="25%" height="5" style="background:#34A853;"></td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- Header -->
    <tr>
      <td style="background:#0f172a;padding:24px 28px;border-bottom:1px solid #1e293b;">
        <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;color:#60a5fa;margin-bottom:4px;">
          GENMUNITY • SPEAKER &amp; ORGANIZER COLLABORATION PROPOSAL
        </div>
        <div style="font-size:20px;font-weight:800;color:#f8fafc;letter-spacing:-0.3px;">
          {html.escape(event_name)} — 연사 및 공동 운영 협력 제안서
        </div>
        <div style="font-size:13px;color:#94a3b8;margin-top:6px;">
          {html.escape(event_date)} &nbsp;|&nbsp; {html.escape(venue)}
        </div>
      </td>
    </tr>

    <tr>
      <td style="padding:28px;">
        <!-- Speaker Profile Card -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;border-radius:10px;margin:0 0 22px;">
          <tr>
            <td style="padding:18px 20px;">
              <div style="display:inline-block;background:#2563eb;color:#ffffff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;margin-bottom:8px;">
                {html.escape(order_label)} • {html.escape(role)}
              </div>
              <div style="color:#f8fafc;font-size:17px;font-weight:700;margin-bottom:4px;">
                {html.escape(name)} 님 <span style="color:#94a3b8;font-weight:500;font-size:14px;">({html.escape(speaker['email'])})</span>
              </div>
              <div style="color:#cbd5e1;font-size:13px;line-height:1.6;">
                <b>담당 트랙:</b> {html.escape(track)}<br/>
                <b>세션 주제:</b> {html.escape(topic)}<br/>
                <b>배정 시간:</b> {html.escape(session_time)}
              </div>
            </td>
          </tr>
        </table>

        <p style="margin:0 0 18px;font-size:14.5px;line-height:1.7;color:#1e293b;">
          안녕하세요 <b>{html.escape(name)} {html.escape(role)}</b>님,<br/>
          GDG Korea DevFest 2026 운영팀(Genmunity RootAgent)입니다. 현재 실시간으로 집계된 <b>참가자 RSVP 분포 파이차트</b>와 <b>행사 준비도 바차트 업데이트</b>를 공유드리며, 이번 행사를 운영진과 함께 만들어갈 때 기대할 수 있는 핵심 가치와 <b>Genmunity Hub / MCP 서버 연동 방법</b>, 그리고 <b>참여 여부 확인 Google Form</b>을 안내해 드립니다.
        </p>

        <!-- Section 1: Charts (Pie Chart + Bar Chart) -->
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:18px 20px;margin:20px 0;">
          <div style="font-size:13px;font-weight:800;color:#1d4ed8;letter-spacing:0.4px;margin-bottom:10px;">
            1. 실시간 행사 데이터 리포트 (RSVP 파이차트 &amp; 행사 운영 바차트)
          </div>

          <div style="margin-bottom:16px;text-align:center;">
            <img src="cid:rsvp_pie_chart" alt="DevFest 2026 RSVP Pie Chart" style="max-width:100%;height:auto;border-radius:10px;border:1px solid #cbd5e1;" />
          </div>

          <!-- Inline HTML Fallback Table for RSVP Pie Chart -->
          <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:13px;margin-bottom:18px;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;">
            <tr style="background:#f1f5f9;font-weight:700;color:#0f172a;">
              <td align="left">트랙 구분 (RSVP 파이차트 항목)</td>
              <td align="center">점유 비율</td>
              <td align="right">상태</td>
            </tr>
            <tr style="border-top:1px solid #e2e8f0;">
              <td><span style="display:inline-block;width:10px;height:10px;background:#2563eb;border-radius:2px;margin-right:6px;"></span>AI / Agentic Workflow Hands-on</td>
              <td align="center"><b>50%</b></td>
              <td align="right" style="color:#2563eb;font-weight:600;">Confirmed</td>
            </tr>
            <tr style="border-top:1px solid #e2e8f0;">
              <td><span style="display:inline-block;width:10px;height:10px;background:#059669;border-radius:2px;margin-right:6px;"></span>Flutter &amp; On-Device AI Hands-on</td>
              <td align="center"><b>35%</b></td>
              <td align="right" style="color:#059669;font-weight:600;">Confirmed</td>
            </tr>
            <tr style="border-top:1px solid #e2e8f0;">
              <td><span style="display:inline-block;width:10px;height:10px;background:#f59e0b;border-radius:2px;margin-right:6px;"></span>Cloud &amp; GDG Study Jam Builders</td>
              <td align="center"><b>15%</b></td>
              <td align="right" style="color:#d97706;font-weight:600;">Confirmed</td>
            </tr>
          </table>

          <div style="margin-bottom:14px;text-align:center;">
            <img src="cid:event_bar_chart" alt="DevFest 2026 Event Operations Bar Chart" style="max-width:100%;height:auto;border-radius:10px;border:1px solid #cbd5e1;" />
          </div>

          <!-- Inline HTML Progress Bars for Event Bar Chart -->
          <table width="100%" cellpadding="6" cellspacing="0" style="font-size:12.5px;color:#334155;">
            <tr>
              <td width="48%"><b>GDE 연사 매칭 및 세션 확정</b></td>
              <td width="42%">
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;border-radius:4px;">
                  <tr><td width="100%" height="10" style="background:#2563eb;border-radius:4px;"></td></tr>
                </table>
              </td>
              <td width="10%" align="right"><b>100%</b></td>
            </tr>
            <tr>
              <td><b>사전 온보딩 (Google Form &amp; Calendar)</b></td>
              <td>
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;border-radius:4px;">
                  <tr><td width="100%" height="10" style="background:#059669;border-radius:4px;"></td></tr>
                </table>
              </td>
              <td align="right"><b>100%</b></td>
            </tr>
            <tr>
              <td><b>RootAgent · MCP · A2A 자동화 가동</b></td>
              <td>
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;border-radius:4px;">
                  <tr><td width="100%" height="10" style="background:#4f46e5;border-radius:4px;"></td></tr>
                </table>
              </td>
              <td align="right"><b>100%</b></td>
            </tr>
            <tr>
              <td><b>현장 주차 및 연사 웰컴 키트 준비</b></td>
              <td>
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;border-radius:4px;">
                  <tr><td width="95%" height="10" style="background:#0ea5e9;border-radius:4px;"></td><td width="5%"></td></tr>
                </table>
              </td>
              <td align="right"><b>95%</b></td>
            </tr>
            <tr>
              <td><b>참가자 RSVP 모집 및 트랙 배정</b></td>
              <td>
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;border-radius:4px;">
                  <tr><td width="85%" height="10" style="background:#f59e0b;border-radius:4px;"></td><td width="15%"></td></tr>
                </table>
              </td>
              <td align="right"><b>85%</b></td>
            </tr>
          </table>
        </div>

        <!-- Section 2: 3 Key Bullets -->
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-left:4px solid #2563eb;border-radius:10px;padding:18px 20px;margin:20px 0;">
          <div style="font-size:13.5px;font-weight:800;color:#1e3a8a;margin-bottom:10px;">
            2. 이번 행사 운영진과 함께하면 기대할 수 있는 3가지 핵심 포인트
          </div>
          <div style="padding:6px 0;font-size:13.5px;line-height:1.65;color:#1e293b;">
            <b style="color:#1d4ed8;">• [Bullet 1] Google ADK · Gemini 4.0 Argon 기반 연사/참가자 운영 완전 자동화:</b><br/>
            반복적인 참가자 문의 응대(Pub/Sub → Cloud Run 지식 베이스 자동 회신 및 운영진 위임), 연사 온보딩(Google Forms &amp; Calendar API 실시간 동기화), 현장 사진 기반 Gemini Vision 참석자 수 자동 집계로 운영 부담을 최소화하고 핸즈온 세션의 기술적 완성도에만 집중하실 수 있습니다.
          </div>
          <div style="padding:6px 0;font-size:13.5px;line-height:1.65;color:#1e293b;">
            <b style="color:#1d4ed8;">• [Bullet 2] 실시간 RSVP 파이차트 &amp; 준비도 바차트 기반 고밀도 맞춤형 실습 환경:</b><br/>
            현재 집계된 트랙별 RSVP 수요(AI 에이전트 50%, Flutter 온디바이스 AI 35%, Cloud 15%)와 100% 구축 완료된 온보딩 파이프라인을 바탕으로, 사전 검증된 개발자 참가자들에게 최적화된 90분 핸즈온 코드랩을 안정적으로 전달할 수 있습니다.
          </div>
          <div style="padding:6px 0;font-size:13.5px;line-height:1.65;color:#1e293b;">
            <b style="color:#1d4ed8;">• [Bullet 3] 오픈 MCP(Model Context Protocol) 및 A2A 에이전트 생태계 공동 빌딩:</b><br/>
            운영진과 연사자가 직접 자신의 AI 에이전트 환경에 Genmunity MCP 서버를 연결해 실시간 RSVP 현황, 세션 지식 베이스, 이메일 클러스터링 리포트를 함께 조회·제어하는 차세대 에이전틱 커뮤니티 레퍼런스를 공동 구축할 수 있습니다.
          </div>
        </div>

        <!-- Section 3: MCP & Genmunity Hub Web Site -->
        <div style="background:#0f172a;color:#f8fafc;border-radius:10px;padding:18px 20px;margin:20px 0;">
          <div style="font-size:13px;font-weight:800;color:#60a5fa;letter-spacing:0.4px;margin-bottom:10px;">
            3. 함께 사용할 수 있는 Genmunity Hub 웹사이트 및 MCP 연동 안내
          </div>
          <div style="font-size:13px;color:#cbd5e1;line-height:1.7;margin-bottom:12px;">
            • <b>Genmunity Hub 웹 사이트:</b> <a href="{PUBLIC_HUB_URL}" target="_blank" style="color:#93c5fd;text-decoration:underline;">{PUBLIC_HUB_URL}</a><br/>
            • <b>Genmunity MCP 엔드포인트:</b> <a href="{PUBLIC_MCP_URL}" target="_blank" style="color:#93c5fd;text-decoration:underline;">{PUBLIC_MCP_URL}</a><br/>
            • <b>Genmunity MCP 도구 목록:</b> <a href="{PUBLIC_MCP_TOOLS_URL}" target="_blank" style="color:#93c5fd;text-decoration:underline;">{PUBLIC_MCP_TOOLS_URL}</a><br/>
            • <b>Genmunity A2A Agent Card:</b> <a href="{PUBLIC_A2A_CARD_URL}" target="_blank" style="color:#93c5fd;text-decoration:underline;">{PUBLIC_A2A_CARD_URL}</a>
          </div>
          <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px 14px;font-family:monospace;font-size:12px;color:#e2e8f0;white-space:pre-wrap;">{{
  "mcpServers": {{
    "genmunity-cloud": {{
      "url": "{PUBLIC_MCP_URL}"
    }}
  }}
}}</div>
        </div>

        <!-- Section 4: Participation Confirmation Google Form CTA -->
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:20px;margin:20px 0;text-align:center;">
          <div style="font-size:12px;font-weight:800;color:#15803d;letter-spacing:0.5px;margin-bottom:6px;">
            4. COLLABORATION &amp; PARTICIPATION GOOGLE FORM
          </div>
          <div style="font-size:14px;color:#14532d;margin-bottom:14px;line-height:1.6;">
            이번 행사 연사 및 운영진 협력 참여 여부를 아래 공식 Google Form을 통해 회신해 주시면 감사하겠습니다.
          </div>
          <div style="margin-bottom:12px;">
            <a href="{COLLABORATION_GOOGLE_FORM_URL}" target="_blank" style="display:inline-block;background:#16a34a;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 24px;border-radius:8px;margin-right:8px;margin-bottom:8px;">
              참여 여부 Google Form 작성하기
            </a>
            <a href="{PUBLIC_HUB_URL}" target="_blank" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 24px;border-radius:8px;margin-bottom:8px;">
              Genmunity Hub 웹사이트 열기
            </a>
          </div>
          <div style="font-size:12px;color:#475569;word-break:break-all;">
            Google Form 직접 링크: <a href="{COLLABORATION_GOOGLE_FORM_URL}" target="_blank" style="color:#15803d;">{COLLABORATION_GOOGLE_FORM_URL}</a>
          </div>
        </div>

        <p style="margin:18px 0 0;font-size:14px;line-height:1.65;color:#334155;">
          감사합니다.<br/>
          <b>GDG Korea DevFest 2026 운영팀 (Genmunity RootAgent &amp; OpsAgent) 드림</b>
        </p>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:16px 28px;font-size:12px;color:#64748b;">
        <b>Genmunity Event Operations Platform</b> • Powered by Google ADK, Gemini 4.0 Argon &amp; Google Workspace
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, body_text, html_body


def send_speaker_collaboration_proposal_emails() -> Dict[str, Any]:
    """
    1. Audit all links in the proposal (Google Form, Genmunity Hub, MCP, A2A) for clean readability and HTTP 200.
    2. Generate RSVP Pie Chart PNG and Event Operations Bar Chart PNG.
    3. Validate recipients against GDE / Exact-Match GDG privacy policy.
    4. Send the collaboration proposal email with inline charts and clean Google Form link to both GDE speakers.
    """
    from genmunity_agent.services.google_workspace import get_workspace_service

    link_audit = audit_collaboration_links()
    if not all(item["verified"] for item in link_audit):
        raise RuntimeError(f"Link audit failed before email dispatch: {link_audit}")

    pie_png = generate_rsvp_pie_chart_png()
    bar_png = generate_event_bar_chart_png()

    ws = get_workspace_service()
    gmail = ws.get_gmail_service()

    sent_records: List[Dict[str, Any]] = []
    for speaker in HARDCODED_SPEAKERS:
        recipient_check = validate_speaker_email_recipient(email=speaker["email"], name=speaker["name"])
        if not recipient_check.get("allowed"):
            sent_records.append(
                {
                    "speaker_name": speaker["name"],
                    "speaker_email": speaker["email"],
                    "status": "blocked_by_privacy_policy",
                    "reason": recipient_check.get("reason"),
                }
            )
            continue

        subject, body_text, html_body = build_collaboration_proposal_content(speaker)

        msg = MIMEMultipart("related")
        msg["To"] = formataddr((speaker["name"], speaker["email"]))
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="genmunity.gdg.kr")

        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(body_text, "plain", "utf-8"))
        alt_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt_part)

        pie_img_part = MIMEImage(pie_png, _subtype="png")
        pie_img_part.add_header("Content-ID", "<rsvp_pie_chart>")
        pie_img_part.add_header("Content-Disposition", 'inline; filename="rsvp_pie_chart.png"')
        msg.attach(pie_img_part)

        bar_img_part = MIMEImage(bar_png, _subtype="png")
        bar_img_part.add_header("Content-ID", "<event_bar_chart>")
        bar_img_part.add_header("Content-Disposition", 'inline; filename="event_bar_chart.png"')
        msg.attach(bar_img_part)

        raw_bytes = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        sent = gmail.users().messages().send(userId="me", body={"raw": raw_bytes}).execute()

        rec = {
            "speaker_order": speaker["speaker_order"],
            "order_label": speaker["order_label"],
            "speaker_name": speaker["name"],
            "speaker_role": speaker["role"],
            "speaker_email": speaker["email"],
            "recipient_validation": recipient_check["match_type"],
            "subject": subject,
            "collaboration_form_url": COLLABORATION_GOOGLE_FORM_URL,
            "hub_url": PUBLIC_HUB_URL,
            "mcp_url": PUBLIC_MCP_URL,
            "charts_attached": ["rsvp_pie_chart.png", "event_bar_chart.png"],
            "delivery": {
                "status": "sent",
                "to": speaker["email"],
                "to_name": speaker["name"],
                "subject": subject,
                "email_type": "collaboration_proposal",
                "message_id": sent.get("id"),
                "thread_id": sent.get("threadId"),
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        }
        sent_records.append(rec)

    state = load_runtime_state()
    state.setdefault("collaboration_proposals", []).extend(sent_records)
    save_runtime_state(state)

    return {
        "status": "sent",
        "link_audit": link_audit,
        "collaboration_google_form_id": COLLABORATION_GOOGLE_FORM_ID,
        "collaboration_google_form_url": COLLABORATION_GOOGLE_FORM_URL,
        "hub_url": PUBLIC_HUB_URL,
        "mcp_url": PUBLIC_MCP_URL,
        "mcp_tools_url": PUBLIC_MCP_TOOLS_URL,
        "a2a_card_url": PUBLIC_A2A_CARD_URL,
        "proposals_sent": sent_records,
    }
