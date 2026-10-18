import html
from typing import Dict, Any, Optional
from genmunity_agent.config import DEVFEST_EVENT_INFO


def _format_paragraphs_html(body_text: str) -> str:
    """Convert plain text email body into clean, well-spaced HTML paragraphs and bullet lists."""
    blocks = [b.strip() for b in body_text.strip().split("\n\n") if b.strip()]
    rendered = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        # Check if block is a section box or bullet list
        if lines[0].startswith("[") or lines[0].startswith("■"):
            header = html.escape(lines[0])
            items_html = ""
            for line in lines[1:]:
                clean_line = html.escape(line.lstrip("-•* "))
                items_html += (
                    f"<div style='padding:4px 0;font-size:13.5px;color:#334155;'>"
                    f"<span style='color:#2563eb;font-weight:700;margin-right:6px;'>•</span>{clean_line}</div>"
                )
            rendered.append(
                f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #2563eb;"
                f"border-radius:8px;padding:14px 16px;margin:16px 0;'>"
                f"<div style='font-weight:700;font-size:13.5px;color:#0f172a;margin-bottom:6px;'>{header}</div>"
                f"{items_html}</div>"
            )
        else:
            escaped = "<br/>".join(html.escape(line) for line in lines)
            rendered.append(
                f"<p style='margin:0 0 14px;font-size:14.5px;line-height:1.72;color:#1e293b;'>{escaped}</p>"
            )
    return "\n".join(rendered)


def render_genmunity_email_html(
    subject: str,
    body_text: str,
    speaker: Optional[Dict[str, Any]] = None,
    email_type: str = "outreach",
    form_url: Optional[str] = None,
    calendar_url: Optional[str] = None,
    calendar_link: Optional[str] = None,
    meet_link: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Render a cohesive, brand-aligned HTML email following the Genmunity Design System.
    """
    calendar_url = calendar_url or calendar_link
    event_name = html.escape(DEVFEST_EVENT_INFO["event_name"])
    event_date = html.escape(DEVFEST_EVENT_INFO["event_date"])
    venue = html.escape(DEVFEST_EVENT_INFO["venue"])

    speaker_badge = "GDG KOREA • DEVFEST 2026 SPEAKER"
    speaker_name = ""
    speaker_role = ""
    speaker_track = ""
    speaker_topic = ""
    speaker_time = ""
    accent_color = "#2563eb"

    if speaker:
        speaker_name = html.escape(speaker.get("name", ""))
        speaker_role = html.escape(speaker.get("role", ""))
        speaker_badge = html.escape(f"{speaker.get('order_label', '')} • {speaker_role}")
        speaker_track = html.escape(speaker.get("track", ""))
        speaker_topic = html.escape(speaker.get("proposed_topic", ""))
        speaker_time = html.escape(speaker.get("session_time", ""))
        if "Flutter" in speaker_role:
            accent_color = "#059669"

    if email_type == "outreach":
        type_kicker = "OFFICIAL SPEAKER INVITATION"
    elif email_type == "sponsor_outreach":
        type_kicker = "OFFICIAL SPONSORSHIP PROPOSAL"
    elif email_type == "inquiry_reply":
        type_kicker = "EVENT KNOWLEDGE BASE AUTO-REPLY"
    elif email_type in ("organizer_delegation", "delegation"):
        type_kicker = "ORGANIZER INQUIRY DELEGATION"
    else:
        type_kicker = "SPEAKER ONBOARDING & CALENDAR INVITE"

    speaker_card_html = ""
    if speaker:
        speaker_card_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;border-radius:10px;margin:0 0 22px;overflow:hidden;">
          <tr>
            <td style="padding:18px 20px;">
              <div style="display:inline-block;background:{accent_color};color:#ffffff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;letter-spacing:0.4px;margin-bottom:8px;">
                {speaker_badge}
              </div>
              <div style="color:#f8fafc;font-size:17px;font-weight:700;margin-bottom:4px;">
                {speaker_name} <span style="color:#94a3b8;font-weight:500;font-size:14px;">({speaker_role})</span>
              </div>
              <div style="color:#cbd5e1;font-size:13px;line-height:1.55;">
                <b>Track:</b> {speaker_track}<br/>
                <b>Topic:</b> {speaker_topic}<br/>
                <b>Session Slot:</b> {event_date} • {speaker_time}
              </div>
            </td>
          </tr>
        </table>
        """

    cta_section_html = ""
    if form_url or calendar_url:
        form_btn = ""
        if form_url:
            safe_form_url = html.escape(form_url)
            form_btn = f"""
            <a href="{safe_form_url}" target="_blank" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 22px;border-radius:8px;margin-right:10px;margin-bottom:8px;">
              발표자 사전 정보 등록 Form 작성하기 →
            </a>
            """
        cal_btn = ""
        if calendar_url and calendar_url.startswith("http"):
            safe_cal_url = html.escape(calendar_url)
            cal_btn = f"""
            <a href="{safe_cal_url}" target="_blank" style="display:inline-block;background:#0f172a;color:#f8fafc;text-decoration:none;font-weight:600;font-size:13.5px;padding:12px 18px;border-radius:8px;border:1px solid #334155;margin-bottom:8px;">
              Google Calendar 일정 확인 ↗
            </a>
            """
        cta_section_html = f"""
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:18px 20px;margin:20px 0;">
          <div style="font-size:12px;font-weight:700;color:#1d4ed8;letter-spacing:0.5px;margin-bottom:6px;">
            ACTION REQUIRED • SPEAKER ONBOARDING
          </div>
          <div style="font-size:13.5px;color:#1e3a8a;margin-bottom:14px;line-height:1.55;">
            원활한 현장 지원(웰컴 티셔츠 사이즈 및 오토웨이타워 무료 주차 차량 번호 등록)을 위해 아래 버튼을 눌러 정보를 제출해 주세요.
          </div>
          <div>
            {form_btn}
            {cal_btn}
          </div>
        </div>
        """

    paragraphs_html = _format_paragraphs_html(body_text)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(subject)}</title>
</head>
<body style="margin:0;padding:24px 12px;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #cbd5e1;box-shadow:0 8px 24px rgba(15,23,42,0.06);">
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

    <!-- Genmunity Dark Header -->
    <tr>
      <td style="background:#0f172a;padding:22px 28px;border-bottom:1px solid #1e293b;">
        <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;color:#60a5fa;margin-bottom:4px;">
          GENMUNITY • {type_kicker}
        </div>
        <div style="font-size:19px;font-weight:800;color:#f8fafc;letter-spacing:-0.3px;">
          {event_name}
        </div>
        <div style="font-size:12.5px;color:#94a3b8;margin-top:4px;">
          {event_date} &nbsp;|&nbsp; {venue}
        </div>
      </td>
    </tr>

    <!-- Main Content Body -->
    <tr>
      <td style="padding:28px;">
        {speaker_card_html}
        {cta_section_html}
        {paragraphs_html}
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:18px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="font-size:12px;color:#64748b;line-height:1.5;">
              <b style="color:#0f172a;">Genmunity Event Operations Platform</b><br/>
              Powered by Google ADK • Gemini • Google Workspace (Gmail, Forms, Calendar)
            </td>
            <td align="right" style="font-size:11.5px;color:#94a3b8;">
              GDG Korea CommunityHub
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
