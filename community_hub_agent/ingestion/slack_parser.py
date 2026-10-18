"""Slack Channel (`#organizers` / `C04E1UAAY`) parser for GDG Korea Organizer & GDE knowledge base.

Parses the exported JSON from `https://gdgkr.slack.com/archives/C04E1UAAY`
(`data/raw/slack_gdgkr_organizers_C04E1UAAY.json`), including:
- Pinned campaign announcements (`pinned_messages`, e.g., Build with AI guidelines, speaker pool, TtT materials)
- Timeline top-level messages (`messages`) and full thread replies (`thread_replies_fetched`)
- User ID (`<@U...>`) resolution to Korean/English organizer & GDE names
- Slack mrkdwn link extraction (`<url|label>`) and Google Slides URL discovery
- Automatic classification into secondary campaign categories (`devfest`, `build_with_ai`)
"""

from __future__ import annotations

import datetime
import html
import json
import logging
import re
from pathlib import Path
from typing import Any

from community_hub_agent.config import settings
from community_hub_agent.ingestion.models import (
    SlackChannelDocument,
    SlackReplyRecord,
    SlackThreadRecord,
    SourceCategory,
)
from community_hub_agent.ingestion.slides_parser import discover_slide_urls_in_text

logger = logging.getLogger(__name__)

KST = datetime.timezone(datetime.timedelta(hours=9))

SLACK_LINK_PATTERN = re.compile(r"<(https?://[^>|]+)(?:\|([^>]+))?>")
SLACK_USER_MENTION_PATTERN = re.compile(r"<@(U[A-Z0-9]+)>")

# Explicit bilingual / canonical name overrides for Slack users in #organizers
SLACK_USER_CANONICAL_NAMES: dict[str, str] = {
    "U02S1C9DDH6": "권나현 (NaHyun Kwon, Google Community Manager)",
    "U03K3G0KLR2": "권나현 (NaHyun Kwon, Google Community Manager)",
    "U0K83RHT7": "강경완 (Kyeongwan Kang, GDG Android Korea)",
    "U05L2BY1QR5": "김수빈 (Subin Kim, GDG Campus Korea)",
    "U05MYV20TJ6": "조새벽 (SaeByeok Cho, GDG Incheon)",
    "U01M9BC6NCU": "이현우 (Hyunwoo Lee, GDG Android Korea)",
    "U0422S2CCH5": "이진석 (Jhinseok Lee / Jhin Lee)",
    "U07C48VHVS6": "고은진 (Eunjin Ko / Jinny, GDG Pangyo)",
    "U1VJZ8MQE": "박제창 (Jaichang Park / Dreamwalker, GDG Golang Korea)",
    "U09B6PWHXRR": "윤지원 (Giwon Yun, GDG Seoul)",
    "U09HP3YSEV6": "권준호 (Junho Kwon, GDG Busan)",
    "UGY6A6N5R": "천명기 (Jackie Cheon, GDG Busan)",
    "U06B8DDLMU0": "김마로 (Maro Kim, GDG Incheon)",
    "UB62CKS0P": "배필주 (PilJu Bae, GDG Android Korea)",
    "USJSMDV9P": "성기동 (Gidong Sung, GDG Busan)",
    "U0AFNSF8EPM": "이재훈 (Jaehun Lee, GDG Busan 신규 오거나이저)",
    "U0BSBLR8NMS": "황재웅 (Jaewoong Hwang, GDG Busan 신규 오거나이저)",
    "U06UWSKUTM4": "윤현서 (Hyeonseo Youn, GDG Campus Korea)",
    "U04F6QLUBLN": "최가인 (Ga-in Olivia Choi, GDG Daegu)",
    "U07L6NB98BB": "황지현 (JiHyeon Hwang, GDG Daegu)",
    "U01BP5Q0BNV": "김인철 (Inchul Kim, GDG Daejeon)",
    "U0810246Q74": "서보석 (Boseok Seo / Seoboseok, GDG Daejeon)",
    "UCB9R9C93": "변성윤 (Seongyun Byeon / 카일, AI/ML GDE)",
    "U989GPDEJ": "조희주 (Heeju Jo, GDG Pangyo)",
    "UBM6VE90A": "노경모 (Kyeongmo Noh / brightparagon)",
    "U01MMQ6F926": "김수현 (Suhyeon Kim, GDG Android Korea)",
    "U04JV3W8877": "이영빈 (Youngbin Lee, GDG Incheon)",
    "UJF3HD06T": "박해선 (Haesun Park, ML/Cloud GDE)",
    "U1CMGLAKX": "신정규 (Jeongkyu Shin / inureyes, AI/ML GDE)",
    "U0C7K8RC96J": "건주 (Geonju, GDG Incheon 신규 오거나이저)",
    "U0334K326EQ": "유광무 (GwangMoo You, GDG Incheon)",
    "U1J74LF3P": "이준범 (Junbum Lee / Beomi, AI GDE)",
}


def ts_to_kst_str(ts: str | float | int) -> str:
    """Converts a Slack Unix timestamp string into `YYYY-MM-DD HH:MM:SS` KST."""
    try:
        dt = datetime.datetime.fromtimestamp(float(ts), tz=KST)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


class SlackChannelParser:
    """Parses exported Slack channel JSON into structured `SlackChannelDocument` records."""

    def __init__(self, export_path: Path | None = None) -> None:
        self.export_path = export_path or settings.kr_slack_export_path

    def resolve_user(
        self, user_id: str, users_map: dict[str, dict[str, Any]]
    ) -> str:
        """Resolves a Slack user ID (`U...`) to a descriptive Korean/English name."""
        if not user_id:
            return "Unknown"
        if user_id in SLACK_USER_CANONICAL_NAMES:
            return SLACK_USER_CANONICAL_NAMES[user_id]
        u = users_map.get(user_id, {})
        disp = (u.get("display_name") or "").strip()
        real = (u.get("real_name") or "").strip()
        name = (u.get("name") or "").strip()
        if disp and real and disp != real:
            return f"{disp} ({real})"
        return disp or real or name or user_id

    def clean_slack_text(
        self, raw_text: str, users_map: dict[str, dict[str, Any]]
    ) -> tuple[str, list[str], list[str]]:
        """Formats Slack mrkdwn text, resolving `<@U...>` mentions and extracting URLs."""
        if not raw_text:
            return "", [], []

        people_mentioned: list[str] = []
        links: list[str] = []

        def _replace_user(match: re.Match[str]) -> str:
            uid = match.group(1)
            resolved = self.resolve_user(uid, users_map)
            short_name = resolved.split(",")[0].strip()
            if not short_name.endswith(")"):
                pass
            if resolved not in people_mentioned:
                people_mentioned.append(resolved)
            return f"@{short_name}"

        text = SLACK_USER_MENTION_PATTERN.sub(_replace_user, raw_text)

        def _replace_link(match: re.Match[str]) -> str:
            url = html.unescape(match.group(1).strip())
            label = html.unescape(match.group(2).strip()) if match.group(2) else ""
            if url not in links:
                links.append(url)
            if label and label != url:
                return f"[{label}]({url})"
            return url

        text = SLACK_LINK_PATTERN.sub(_replace_link, text)
        text = html.unescape(text)
        return text.strip(), links, people_mentioned

    @staticmethod
    def infer_thread_metadata(
        ts: str,
        datetime_kst: str,
        author_name: str,
        cleaned_text: str,
        replies_text: str,
        is_pinned: bool,
    ) -> tuple[str, list[SourceCategory], list[str]]:
        """Infers a rich semantic title, secondary categories, and mentioned chapters for a Slack thread."""
        combined = f"{cleaned_text}\n{replies_text}".lower()
        secondary_cats: list[SourceCategory] = []
        if "devfest" in combined or "데브페스트" in combined or "서울 ai 허브" in combined:
            secondary_cats.append("devfest")
        if "build with ai" in combined or "bwai" in combined:
            secondary_cats.append("build_with_ai")

        chapters: list[str] = []
        chapter_keywords = {
            "GDG Android Korea": ["android korea", "안드로이드 소소밋업"],
            "GDG Busan": ["gdg 부산", "gdg busan", "부산 i/o", "부산 챕터"],
            "GDG Campus Korea": ["gdg campus korea", "gdg 캠퍼스"],
            "GDG Incheon": ["gdg인천", "gdg incheon", "인천여행", "동인천", "차이나타운"],
            "GDG Seoul": ["서울, 인천", "gdg seoul"],
            "GDG Daejeon": ["inchul kim", "서보석"],
            "GDG Daegu": ["olivia choi", "최가인", "황지현"],
            "GDG Pangyo": ["고은진", "조희주"],
        }
        for ch_name, kws in chapter_keywords.items():
            if any(kw in combined for kw in kws):
                chapters.append(ch_name)

        date_short = datetime_kst[:10]

        # Explicit high-signal titles for key threads
        if is_pinned and "1741603565" in ts:
            title = (
                f"[Slack #organizers 고정 공지] 2025 Build with AI 캠페인 운영진 가이드, "
                f"지원 조건(3/24 시트 마감, D-15 클라우드 크레딧 신청) 및 Train the Trainer 자료 ({date_short})"
            )
        elif is_pinned and "1741848740" in ts:
            title = (
                f"[Slack #organizers 고정 공지] Build with AI 추천 연사 및 핸즈온 진행자 안내 "
                f"(이준범 AI GDE, 박진형, 정명훈 Google Cloud Partner Engineer) ({date_short})"
            )
        elif is_pinned and "1743146063" in ts:
            title = (
                f"[Slack #organizers 고정 공지] Build with AI Train the Trainer 온라인 세션 녹화본 "
                f"(정명훈 - Gemini 2.0 Live API 실시간 영상 챗봇) 및 슬라이드/Lab 문서 ({date_short})"
            )
        elif "서울 ai 허브" in combined:
            title = (
                f"[Slack #organizers 공지] 2026 DevFest 사전 기획 안내, 서울 AI 허브(양재) 무료 대관 공간 안내 "
                f"및 이벤터스 안영학 대표 'AI로 행사 기획 및 운영 자동화하기(300명 행사 1.8명 운영)' ({date_short})"
            )
        elif "gdg bursa" in combined or "캠핑과 해커톤" in combined:
            title = (
                f"[Slack #organizers 공지] 글로벌 DevFest 기획 참고 사례 — 튀르키예 GDG Bursa "
                f"150명 야외 캠핑 해커톤 및 인천 야외 행사 논의 ({date_short})"
            )
        elif "티저 페이지 오픈" in combined or "신규 탭 오픈" in combined:
            title = (
                f"[Slack #organizers 공지] Community Hub 'Train the Trainer' 신규 탭 오픈, "
                f"DevFest 2026 티저 페이지 배지 및 구글러 연사 섭외 안내 ({date_short})"
            )
        elif "sasha denisov" in combined:
            title = (
                f"[Slack #organizers 소식] 멀티 카테고리 GDE Sasha Denisov(flutter_gemma 저자) 방한 및 "
                f"Flutter/Cloud/AI 소소밋업 제안 — 이현우, 이진석 ({date_short})"
            )
        elif "사전 설문 요청 (10/17-10/18)" in cleaned_text:
            title = (
                f"[Slack #organizers 공지] 2026 GDG x GDE Summit (10/17~10/18, 구글 스타트업 캠퍼스) "
                f"Save the Date 및 사전 설문 안내 ({date_short})"
            )
        elif "i/o connect china" in combined and "리마인드" not in combined:
            title = (
                f"[Slack #organizers 안내] 권나현 매니저 및 국내 GDE 상해 I/O Connect China & "
                f"APAC GDE Summit (8/11~8/14) 참석 안내 ({date_short})"
            )
        elif "i/o connect china" in combined and "리마인드" in combined:
            title = (
                f"[Slack #organizers 공지] 2026 Summit 사전 설문 리마인드 및 "
                f"상해 I/O Connect China 2026 & APAC GDE Summit 단체 사진 공유 ({date_short})"
            )
        elif "gdg 부산 i/o extended" in combined or "필주님께서 진행" in combined:
            title = (
                f"[Slack #organizers 행사 후기] GDG Busan I/O Extended 2026 개최 완료 "
                f"(권준호, 천명기, 배필주 참관기 발표, 성기동 후기 및 호두 알레르기 다과 운영 팁) ({date_short})"
            )
        elif "gdg busan에 새롭게" in combined or "부산 챕터" in combined:
            title = (
                f"[Slack #organizers 신규 운영진] GDG Busan(부산) 신규 오거나이저 합류 및 인사 — "
                f"황재웅, 이재훈 (성기동, 권준호, 배필주 환영) ({date_short})"
            )
        elif "올해의 핵심 화두" in combined or "aja hammerly" in combined:
            title = (
                f"[Slack #organizers 공지] 2026 DevFest 글로벌 뉴스레터 핵심 요약 — "
                f"올해의 화두 'Builder'(Aja Hammerly), Vibe Lounge, GDG Basilicata/DevFest Atlanta 에이전트톤 사례 ({date_short})"
            )
        elif "gdg campus korea i/o extended" in combined:
            title = (
                f"[Slack #organizers 행사 소식] GDG Campus Korea I/O Extended 2026 개최 및 마무리 "
                f"(김수빈, 윤현서, 강인영, 컬리 Kurly 후원) ({date_short})"
            )
        elif "ai builder cup" in combined:
            title = (
                f"[Slack #organizers 해커톤 공지] Google Cloud AI Builder Cup 2026 (JAPAC 하이브리드 해커톤, "
                f"상금 $30,000+, 싱가포르 결선 지원) 안내 및 국내 오거나이저 신청 현황 (김인철, 서보석, 윤지원, 조새벽, 변성윤) ({date_short})"
            )
        elif "참가 신청 오픈" in combined and "리바이스" in combined:
            title = (
                f"[Slack #organizers 공지] 2026 KR Developer Community Summit (10/17~10/18) 참가 신청 오픈, "
                f"리바이스 데님 자켓 웰컴 기프트 및 신청 확인 스레드 (성기동, 윤지원, 조희주, 노경모, 권진겸) ({date_short})"
            )
        elif "안드로이드 소소밋업" in combined:
            title = f"[Slack #organizers 행사 소식] GDG Android Korea 안드로이드 소소밋업 개최 (이현우) ({date_short})"
        elif "월간 미팅은 부득이하게 취소" in combined:
            title = (
                f"[Slack #organizers 공지] 9월 월간 미팅 취소 안내 및 9/30까지 DevFest 계획 시트 업데이트 요청 ({date_short})"
            )
        elif "지원금 증액 확정" in combined or "25,000원으로 확대" in combined:
            title = (
                f"[Slack #organizers 특급 공지] 2026 DevFest 지원금 증액 확정 (참가자 1인당 20,000원 → 25,000원 확대) "
                f"및 추가 예산/운영진 특별 SWAG 지원 조건 (150~250명 규모, AI Studio/Antigravity 핸즈온 세션) ({date_short})"
            )
        elif "핸즈온 머신러닝 3판" in combined:
            title = (
                f"[Slack #organizers 도서 나눔] 박해선(Haesun Park) GDE 도서 나눔 이벤트 — "
                f"'핸즈온 머신러닝 3판', '파이토치로 배우는 LLM&AI' 각 4권 선착순 나눔 (신정규, 조새벽 댓글) ({date_short})"
            )
        elif (
            "medi-guard" in combined
            or "gdg인천 에이전트톤" in combined
            or "gdg 인천" in combined and "에이전트톤" in combined
        ):
            title = (
                f"[Slack #organizers 행사 및 결과물] GDG Incheon(인천) 에이전트톤(Agentathon) 개최 및 참가자 전 팀(1조~7조) "
                f"인천 로컬 AI 에이전트 웹서비스 배포 링크(URL) 전체 목록 공유 (조새벽) ({date_short})"
            )
        elif "부재 일정 및 문의 답변 안내" in combined:
            title = (
                f"[Slack #organizers 공지] DevFest 계획 시트 9/30 마감 리마인드 및 "
                f"권나현 커뮤니티 매니저 부재 일정 안내 (9/17~10/5) ({date_short})"
            )
        elif "cerebralvalley.ai" in combined or "구글딥마인드 ai해커톤" in combined:
            title = f"[Slack #organizers 소식] Google DeepMind AI Hackathon (Cerebral Valley) 개최 소식 공유 (성기동) ({date_short})"
        elif "낚시 가는데 익숙한 로고" in combined:
            title = f"[Slack #organizers 일상] GDGoC (구) 오거나이저 모임 소식 (이현우) ({date_short})"
        elif "gdg incheon 오거나이저로 새롭게" in combined or "건주" in combined:
            title = (
                f"[Slack #organizers 신규 운영진] GDG Incheon(인천) 신규 오거나이저 건주(Geonju) 합류 안내 (유광무 소개) ({date_short})"
            )
        elif "#26-summit" in combined or "2026 kr developer summit 안내" in combined:
            title = (
                f"[Slack #organizers 공지] 2026 KR Developer Summit (10/17~10/18) 최종 안내 및 전용 슬랙 채널(#26-summit) 공지 ({date_short})"
            )
        elif "i/o extended android korea" in combined:
            title = f"[Slack #organizers 행사 소식] GDG Android Korea I/O Extended 2026 현장 사진 및 시작 알림 (강경완) ({date_short})"
        else:
            first_line = cleaned_text.split("\n")[0].strip()[:70]
            title = f"[Slack #organizers] {author_name.split('(')[0].strip()}: {first_line} ({date_short})"

        return title, secondary_cats, chapters

    def parse(self, file_path: Path | None = None) -> SlackChannelDocument | None:
        """Parses the Slack channel JSON export into a structured `SlackChannelDocument`."""
        target = file_path or self.export_path
        if not target.exists():
            logger.warning("Slack export file not found at %s", target)
            return None

        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to parse Slack JSON %s: %s", target, exc)
            return None

        channel_id = raw.get("channel_id", "C04E1UAAY")
        channel_name = raw.get("channel_name", "organizers")
        users_map: dict[str, dict[str, Any]] = raw.get("users", {})
        discovered_slides: list[tuple[str, SourceCategory]] = []

        threads: list[SlackThreadRecord] = []

        # 1. Process Pinned Messages (`pinned_messages`)
        for pmsg in raw.get("pinned_messages", []):
            record = self._build_thread_record(
                pmsg, channel_id, users_map, is_pinned=True
            )
            if record:
                threads.append(record)
                for link in record.links:
                    for s_url in discover_slide_urls_in_text(link):
                        cat: SourceCategory = (
                            record.secondary_categories[0]
                            if record.secondary_categories
                            else "build_with_ai"
                        )
                        discovered_slides.append((s_url, cat))

        # 2. Process Timeline Messages (`messages`) with intelligent grouping for multi-post events & join/leave
        raw_messages: list[dict[str, Any]] = raw.get("messages", [])
        consumed_ts: set[str] = set()

        # Group 1: GDG Busan I/O Extended (2026-08-22 messages 1787375188, 1787380365, 1787393817)
        busan_ioex_msgs = [
            m
            for m in raw_messages
            if m.get("ts", "").startswith(("1787375188", "1787380365", "1787393817"))
        ]
        if len(busan_ioex_msgs) >= 2:
            for m in busan_ioex_msgs:
                consumed_ts.add(m["ts"])
            primary_m = busan_ioex_msgs[-1]  # The closing thread with 4 replies (including 성기동 & 배필주)
            combined_parts: list[str] = []
            combined_files: list[dict[str, str]] = []
            for m in busan_ioex_msgs:
                m_author = self.resolve_user(m.get("user", ""), users_map)
                m_dt = ts_to_kst_str(m.get("ts", ""))
                m_txt, _, _ = self.clean_slack_text(m.get("text", ""), users_map)
                combined_parts.append(f"- **{m_author}** ({m_dt}): {m_txt}")
                for f in m.get("files", []):
                    combined_files.append(
                        {
                            "name": f.get("name", ""),
                            "mimetype": f.get("mimetype", ""),
                            "url": f.get("permalink", ""),
                        }
                    )
            merged_msg = dict(primary_m)
            merged_msg["text"] = "\n".join(combined_parts)
            merged_msg["_premerged_files"] = combined_files
            rec = self._build_thread_record(
                merged_msg, channel_id, users_map, is_pinned=False
            )
            if rec:
                threads.append(rec)

        # Group 2: GDG Busan New Organizers 황재웅 & 이재훈 (2026-08-24~25 messages)
        busan_join_msgs = [
            m
            for m in raw_messages
            if m.get("ts", "").startswith(
                ("1787567275", "1787567284", "1787575330", "1787619739")
            )
        ]
        if busan_join_msgs:
            for m in busan_join_msgs:
                consumed_ts.add(m["ts"])
            intro_parent = busan_join_msgs[0]
            rec = self._build_thread_record(
                intro_parent, channel_id, users_map, is_pinned=False
            )
            if rec:
                threads.append(rec)

        # Group 3: Channel leave (offboarding) on 2026-08-31 (Olivia Choi / 최가인 & 황지현)
        leave_msgs = [
            m for m in raw_messages if m.get("subtype") == "channel_leave"
        ]
        if leave_msgs:
            for m in leave_msgs:
                consumed_ts.add(m["ts"])
            leavers = [
                self.resolve_user(m.get("user", ""), users_map)
                for m in leave_msgs
            ]
            ts0 = leave_msgs[0].get("ts", "1788138075.112049")
            dt0 = ts_to_kst_str(ts0)
            p_slug = "p" + ts0.replace(".", "")
            threads.append(
                SlackThreadRecord(
                    ts=ts0,
                    datetime_kst=dt0,
                    author_id=leave_msgs[0].get("user", ""),
                    author_name=", ".join(leavers),
                    title=(
                        f"[Slack #organizers 채널 퇴장/오프보딩] GDG Daegu 최가인(Olivia Choi), "
                        f"황지현(JiHyeon Hwang) #organizers 채널 퇴장 ({dt0[:10]})"
                    ),
                    text=(
                        f"2026-08-31 GDG Korea `#organizers` 채널에서 아래 인원이 퇴장(`channel_leave`)하였습니다:\n"
                        + "\n".join(f"- **{lv}**" for lv in leavers)
                    ),
                    permalink=f"https://gdgkr.slack.com/archives/{channel_id}/{p_slug}",
                    subtype="channel_leave",
                    chapters_mentioned=["GDG Daegu"],
                    people_mentioned=leavers,
                )
            )

        # Group 4: GDG Campus Korea I/O Extended (2026-08-29 & 2026-08-30)
        campus_msgs = [
            m
            for m in raw_messages
            if m.get("ts", "").startswith(("1787973124", "1788059978"))
        ]
        if len(campus_msgs) == 2:
            for m in campus_msgs:
                consumed_ts.add(m["ts"])
            m1, m2 = campus_msgs[0], campus_msgs[1]
            rec1 = self._build_thread_record(m1, channel_id, users_map)
            rec2 = self._build_thread_record(m2, channel_id, users_map)
            if rec1 and rec2:
                rec1.title = (
                    "[Slack #organizers 행사 소식] GDG Campus Korea I/O Extended 2026 개최 및 마무리 "
                    "(김수빈, 윤현서, 강인영, 컬리 Kurly 후원) (2026-08-29 ~ 2026-08-30)"
                )
                rec1.text = (
                    f"**[Day 1 — {rec1.author_name} ({rec1.datetime_kst})]**\n{rec1.text}\n\n"
                    f"**[Day 2 마무리 — {rec2.author_name} ({rec2.datetime_kst})]**\n{rec2.text}"
                )
                rec1.files.extend(rec2.files)
                rec1.replies.extend(rec2.replies)
                for p in rec2.people_mentioned:
                    if p not in rec1.people_mentioned:
                        rec1.people_mentioned.append(p)
                threads.append(rec1)

        # Group 5: GDG Incheon New Organizer 건주 (2026-10-08 join + 유광무 intro)
        incheon_join_msgs = [
            m
            for m in raw_messages
            if m.get("ts", "").startswith(("1791424001", "1791433333"))
        ]
        if incheon_join_msgs:
            for m in incheon_join_msgs:
                consumed_ts.add(m["ts"])
            intro_m = incheon_join_msgs[-1]
            rec = self._build_thread_record(intro_m, channel_id, users_map)
            if rec:
                threads.append(rec)

        # Remaining messages
        for m in raw_messages:
            ts = m.get("ts", "")
            if ts in consumed_ts:
                continue
            if m.get("subtype") in ("channel_join", "channel_leave"):
                continue
            rec = self._build_thread_record(
                m, channel_id, users_map, is_pinned=False
            )
            if rec:
                threads.append(rec)
                for link in rec.links:
                    for s_url in discover_slide_urls_in_text(link):
                        cat = (
                            rec.secondary_categories[0]
                            if rec.secondary_categories
                            else "devfest"
                        )
                        discovered_slides.append((s_url, cat))

        # Sort threads: pinned first, then chronological
        threads.sort(key=lambda r: (0 if r.is_pinned else 1, float(r.ts)))

        logger.info(
            "Parsed %d semantic Slack threads (including %d pinned) from %s",
            len(threads),
            sum(1 for t in threads if t.is_pinned),
            target,
        )
        return SlackChannelDocument(
            channel_id=channel_id,
            channel_name=channel_name,
            workspace_url=raw.get("workspace_url", "https://gdgkr.slack.com"),
            source_url=raw.get(
                "channel_url", f"https://gdgkr.slack.com/archives/{channel_id}"
            ),
            fetched_at=raw.get("fetched_at", ""),
            is_limited=bool(raw.get("is_limited", True)),
            users=users_map,
            threads=threads,
            discovered_slide_urls=discovered_slides,
        )

    def _build_thread_record(
        self,
        msg: dict[str, Any],
        channel_id: str,
        users_map: dict[str, dict[str, Any]],
        is_pinned: bool = False,
    ) -> SlackThreadRecord | None:
        ts = msg.get("ts", "")
        if not ts:
            return None
        dt_kst = ts_to_kst_str(ts)
        author_id = msg.get("user", "")
        author_name = self.resolve_user(author_id, users_map)

        cleaned_text, links, people = self.clean_slack_text(
            msg.get("text", ""), users_map
        )
        if author_name and author_name not in people:
            people.insert(0, author_name)

        files: list[dict[str, str]] = list(msg.get("_premerged_files", []))
        if not files:
            for f in msg.get("files", []):
                files.append(
                    {
                        "name": f.get("name", ""),
                        "mimetype": f.get("mimetype", ""),
                        "url": f.get("permalink", ""),
                    }
                )

        reactions = [
            f":{r.get('name', '')}: ({r.get('count', 0)})"
            for r in msg.get("reactions", [])
        ]

        replies: list[SlackReplyRecord] = []
        replies_text_parts: list[str] = []
        raw_replies = (
            msg.get("thread_replies_fetched")
            or msg.get("replies_full")
            or []
        )
        for rep in raw_replies:
            rep_ts = rep.get("ts", "")
            rep_dt = ts_to_kst_str(rep_ts)
            rep_uid = rep.get("user", "")
            rep_author = self.resolve_user(rep_uid, users_map)
            rep_text, rep_links, rep_people = self.clean_slack_text(
                rep.get("text", ""), users_map
            )
            for lk in rep_links:
                if lk not in links:
                    links.append(lk)
            for p in rep_people:
                if p not in people:
                    people.append(p)
            if rep_author and rep_author not in people:
                people.append(rep_author)

            rep_files = [
                {
                    "name": rf.get("name", ""),
                    "mimetype": rf.get("mimetype", ""),
                    "url": rf.get("permalink", ""),
                }
                for rf in rep.get("files", [])
            ]
            replies.append(
                SlackReplyRecord(
                    ts=rep_ts,
                    datetime_kst=rep_dt,
                    author_id=rep_uid,
                    author_name=rep_author,
                    text=rep_text,
                    files=rep_files,
                    links=rep_links,
                )
            )
            replies_text_parts.append(f"{rep_author}: {rep_text}")

        title, secondary_cats, chapters = self.infer_thread_metadata(
            ts=ts,
            datetime_kst=dt_kst,
            author_name=author_name,
            cleaned_text=cleaned_text,
            replies_text="\n".join(replies_text_parts),
            is_pinned=is_pinned,
        )

        p_slug = "p" + ts.replace(".", "")
        permalink = msg.get(
            "permalink",
            f"https://gdgkr.slack.com/archives/{channel_id}/{p_slug}",
        )

        return SlackThreadRecord(
            ts=ts,
            datetime_kst=dt_kst,
            author_id=author_id,
            author_name=author_name,
            title=title,
            text=cleaned_text,
            permalink=permalink,
            is_pinned=is_pinned,
            subtype=msg.get("subtype", ""),
            secondary_categories=secondary_cats,
            chapters_mentioned=chapters,
            people_mentioned=people,
            links=links,
            files=files,
            reactions=reactions,
            replies=replies,
        )
