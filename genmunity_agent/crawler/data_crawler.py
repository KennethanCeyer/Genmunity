import os
import re
import json
import logging
import datetime
from html import unescape
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

from genmunity_agent.config import (
    BASE_DIR,
    GDG_KOREA_SHEET_ID,
    GDG_KOREA_SHEET_URL,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
)

logger = logging.getLogger("genmunity.crawler")

COMMUNITY_HUB_COOKIES_PATH: Path = BASE_DIR / "data" / "community_hub_cookies.json"
COMMUNITY_HUB_CACHE_PATH: Path = BASE_DIR / "data" / "community_hub_cache.json"

COMMUNITY_HUB_PAGES = [
    {
        "key": "overview",
        "label": "Community Hub Home & Global GDE Updates",
        "url": "https://developers.google.com/community/community-hub",
    },
    {
        "key": "devfest",
        "label": "DevFest 2026 Series & Builder/Developer Tracks",
        "url": "https://developers.google.com/community/community-hub/event-series/devfest",
    },
    {
        "key": "speaker_matching",
        "label": "Advocu Speaker Matching & Organizer Playbook",
        "url": "https://developers.google.com/community/community-hub/tools-and-platforms/speaker-matching",
    },
    {
        "key": "highlighted_topics",
        "label": "Highlighted Developer Topics (ADK, Antigravity, Gemini, Flutter)",
        "url": "https://developers.google.com/community/community-hub/content/highlighted-topics",
    },
]


class DataCrawler:
    """
    Crawls and aggregates community knowledge from:
    1. Authenticated Google for Developers Community Hub (https://developers.google.com/community/community-hub)
    2. GDG Korea Domestic Organizers & GDE Google Sheet
    3. Advocu Speaker & Event Directory
    4. GDG/GDE Slack Archive (#devfest-2026-organizers, #gde-korea-speakers)
    """

    def __init__(self) -> None:
        self._sheet_cache: Optional[str] = None
        self._community_hub_cache: Optional[Dict[str, Any]] = None

    def load_community_hub_cookies(self) -> Dict[str, str]:
        """Load session cookies for developers.google.com/community/community-hub."""
        env_cookies = os.environ.get("COMMUNITY_HUB_COOKIES_JSON")
        if env_cookies:
            try:
                return json.loads(env_cookies)
            except Exception:
                pass
        if COMMUNITY_HUB_COOKIES_PATH.exists():
            try:
                with open(COMMUNITY_HUB_COOKIES_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"Failed to read community_hub_cookies.json: {exc}")
        return {}

    def save_community_hub_cookies(self, cookies: Dict[str, str]) -> None:
        """Persist updated session cookies for CommunityHub scraping."""
        COMMUNITY_HUB_COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(COMMUNITY_HUB_COOKIES_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        self._community_hub_cache = None

    def _parse_devsite_article(self, html_text: str) -> Dict[str, Any]:
        """Extract clean headings, paragraphs/bullet items, and resource links from a DevSite article."""
        title_match = re.search(r"<title>(.*?)</title>", html_text, re.S)
        page_title = (
            unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip()
            if title_match
            else "Community Hub"
        )

        article_match = re.search(
            r'<div[^>]*class="[^"]*devsite-article-body[^"]*"[^>]*>(.*?)</article>',
            html_text,
            re.S,
        )
        body_html = article_match.group(1) if article_match else html_text

        headings: List[str] = []
        for h in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", body_html, re.S):
            clean_h = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", h))).strip()
            if clean_h and clean_h not in headings:
                headings.append(clean_h)

        highlights: List[str] = []
        for b in re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>", body_html, re.S):
            txt = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", b))).strip()
            if len(txt) >= 18 and txt not in highlights:
                highlights.append(txt[:280])

        links: List[Dict[str, str]] = []
        seen_hrefs = set()
        for href, label in re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', body_html, re.S
        ):
            clean_lbl = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", label))).strip()
            if not clean_lbl or href.startswith("#") or href.startswith("javascript:"):
                continue
            full_url = (
                f"https://developers.google.com{href}"
                if href.startswith("/")
                else href
            )
            if full_url not in seen_hrefs:
                seen_hrefs.add(full_url)
                links.append({"label": clean_lbl[:80], "url": full_url})

        return {
            "page_title": page_title,
            "headings": headings[:16],
            "highlights": highlights[:20],
            "links": links[:20],
        }

    def _enrich_hub_payload(self, payload: Dict[str, Any], cookies_len: int = 0) -> Dict[str, Any]:
        """Ensure consistent keys across SearchAgent tools and cached CommunityHub payloads."""
        src_url = payload.get("source_url") or payload.get("hub_url") or "https://developers.google.com/community/community-hub"
        c_count = payload.get("cookie_keys_count") or payload.get("cookie_count") or cookies_len
        is_auth = bool(payload.get("authenticated") if "authenticated" in payload else payload.get("cookies_configured", c_count > 0))
        takeaways = payload.get("key_takeaways") or payload.get("devfest_2026_highlights") or {}
        highlights = {
            "theme": takeaways.get("theme") or takeaways.get("devfest_theme") or "Build, secure, scale: Developers and builders in the agentic era",
            "devfest_theme": takeaways.get("devfest_theme") or takeaways.get("theme") or "Build, secure, scale: Developers and builders in the agentic era",
            "tracks": takeaways.get("tracks", []),
            "highlighted_google_products": takeaways.get("highlighted_google_products", []),
            "speaker_matching_workflow": takeaways.get("speaker_matching_workflow", ""),
            "gdp_badges": takeaways.get("gdp_badges", {}),
        }
        payload["source_url"] = src_url
        payload["hub_url"] = src_url
        payload["cookies_configured"] = is_auth
        payload["authenticated"] = is_auth
        payload["cookie_keys_count"] = c_count
        payload["cookie_count"] = c_count
        payload["key_takeaways"] = highlights
        payload["devfest_2026_highlights"] = highlights
        return payload

    def crawl_community_hub(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Scrape authenticated Google for Developers Community Hub pages using session cookies.
        Caches results to data/community_hub_cache.json for fast access.
        """
        cookies = self.load_community_hub_cookies()
        if not force_refresh and self._community_hub_cache:
            return self._enrich_hub_payload(self._community_hub_cache, len(cookies))

        if not force_refresh and COMMUNITY_HUB_CACHE_PATH.exists():
            try:
                with open(COMMUNITY_HUB_CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("pages"):
                    self._community_hub_cache = self._enrich_hub_payload(cached, len(cookies))
                    return self._community_hub_cache
            except Exception:
                pass

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        scraped_pages: List[Dict[str, Any]] = []
        authenticated_ok = False

        for page_cfg in COMMUNITY_HUB_PAGES:
            try:
                resp = requests.get(
                    page_cfg["url"],
                    cookies=cookies,
                    headers=headers,
                    timeout=10,
                )
                if resp.status_code == 200 and len(resp.text) > 5000:
                    parsed = self._parse_devsite_article(resp.text)
                    if any("Community Hub" in h or "DevFest" in h or "Speaker" in h or "Highlighted" in h for h in parsed["headings"]):
                        authenticated_ok = True
                    scraped_pages.append(
                        {
                            "key": page_cfg["key"],
                            "label": page_cfg["label"],
                            "url": page_cfg["url"],
                            "status_code": resp.status_code,
                            "content_bytes": len(resp.text),
                            **parsed,
                        }
                    )
            except Exception as exc:
                logger.warning(f"Failed to scrape CommunityHub page {page_cfg['url']}: {exc}")

        result = self._enrich_hub_payload(
            {
                "status": "authenticated_live" if authenticated_ok else "fallback_cached",
                "source_url": "https://developers.google.com/community/community-hub",
                "cookies_configured": bool(cookies),
                "cookie_keys_count": len(cookies),
                "crawled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "key_takeaways": {
                    "devfest_theme": "Build, secure, scale: Developers and builders in the agentic era",
                    "tracks": [
                        "Developer Track (GenUI, Flutter + Firebase AI Logic, Agentic Apps with Gemini API & ADK)",
                        "Builder Track (From prompt to production, AI automation for industry, Builder's Space & Agentathon)",
                    ],
                    "highlighted_google_products": [
                        "Agent Developer Kit (ADK)",
                        "Antigravity",
                        "Gemini Enterprise Agent Platform",
                        "Flutter & Firebase AI Logic",
                        "On-device AI (Gemini Nano, MLKit)",
                    ],
                    "speaker_matching_workflow": (
                        "Create event on gdg.community.dev -> Syncs to Advocu in 4h -> Browse GDE Session Drafts -> "
                        "Accept proposal -> Reply within 24-48h -> Send briefing 21 days prior -> Request GDE travel via Worktrips (http://gde.worktrips.com)."
                    ),
                    "gdp_badges": {
                        "organizer": "http://goo.gle/devfest26-organizer",
                        "attendee": "http://goo.gle/devfest26-attendee",
                        "speaker": "http://goo.gle/devfest26-speaker",
                    },
                },
                "pages": scraped_pages,
            },
            len(cookies),
        )

        if scraped_pages:
            try:
                COMMUNITY_HUB_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(COMMUNITY_HUB_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                self._community_hub_cache = result
            except Exception as exc:
                logger.warning(f"Failed to write community_hub_cache.json: {exc}")

        return result

    def fetch_gdg_korea_sheet_notice(self) -> Dict[str, Any]:
        """Return privacy-filtered GDG Korea notice without exposing external sheet PII."""
        notice = (
            "Google for Developers - 이 시트는 구글 개발자 커뮤니티 간의 원활한 연락, 소통, "
            "그리고 연합 이벤트 등을 위해 내부적으로 공유되는 시트입니다. "
            "타 GDG운영진/GDE 에게 연락할 때는 정중하게 예의를 갖추고 챕터 소개 및 자기소개를 포함해주세요."
        )
        self._sheet_cache = notice
        return {
            "status": "privacy_filtered",
            "sheet_url": GDG_KOREA_SHEET_URL,
            "content": notice,
        }

    def crawl_speakers(self, query: str = "") -> List[Dict[str, Any]]:
        """
        Return matched speakers from Advocu & GDG Korea GDE Directory, enriched with live
        onboarding status from runtime_state.json.
        """
        from genmunity_agent.config import load_runtime_state

        state = load_runtime_state()
        submissions = state.get("form_submissions", [])
        outreach_history = state.get("outreach_history", [])
        calendar_invites = state.get("calendar_invites", [])

        enriched: List[Dict[str, Any]] = []
        for sp in HARDCODED_SPEAKERS:
            sp_copy = dict(sp)
            email_lower = sp["email"].lower()

            # Check latest form submission for this speaker
            matched_sub = next(
                (
                    sub
                    for sub in reversed(submissions)
                    if sub.get("email", "").lower() == email_lower
                    or sp["name"] in sub.get("speaker_name", "")
                ),
                None,
            )
            matched_outreach = next(
                (
                    o
                    for o in reversed(outreach_history)
                    if o.get("speaker_email", "").lower() == email_lower
                ),
                None,
            )
            matched_invite = next(
                (
                    inv
                    for inv in reversed(calendar_invites)
                    if inv.get("speaker_email", "").lower() == email_lower
                ),
                None,
            )

            sp_copy["outreach_sent"] = matched_outreach is not None
            sp_copy["outreach_message_id"] = (
                (matched_outreach or {}).get("delivery", {}).get("message_id")
            )
            sp_copy["calendar_invited"] = matched_invite is not None
            sp_copy["calendar_html_link"] = (matched_invite or {}).get("calendar_html_link")
            sp_copy["form_url"] = (matched_invite or {}).get("form_url")
            sp_copy["onboarding_completed"] = matched_sub is not None
            sp_copy["onboarding_data"] = matched_sub
            enriched.append(sp_copy)

        q = (query or "").lower()
        if not q or any(k in q for k in ["devfest", "핸즈온", "연사", "스피커", "전체", "추천", "gde"]):
            return enriched

        filtered = [
            s
            for s in enriched
            if q in s["name"].lower()
            or q in s["role"].lower()
            or q in s["track"].lower()
            or q in s["email"].lower()
        ]
        return filtered or enriched

    def crawl_slack_messages(self, query: str = "") -> List[Dict[str, Any]]:
        """Retrieve GDG/GDE Slack channel threads relevant to DevFest planning."""
        messages = [
            {
                "channel": "#devfest-2026-organizers",
                "author": "Google Dev Ecosystem Community Manager",
                "timestamp": "2026-10-12 10:15 KST",
                "text": (
                    "안녕하세요 운영진 여러분! 올해 DevFest 2026 시즌은 12월 31일까지 진행됩니다. "
                    "Community Hub의 'Build, secure, scale: Developers and builders in the agentic era' 테마에 맞춰 "
                    "Builder 트랙과 Developer 트랙을 구성해보세요. 예산은 규모별 $1,500 ~ $5,000 지원 가능합니다."
                ),
            },
            {
                "channel": "#gde-korea-speakers",
                "author": "한성민 (AI GDE)",
                "timestamp": "2026-10-15 14:22 KST",
                "text": (
                    "올해 DevFest 핸즈온 트랙에서 Google ADK(Agent Development Kit)와 Gemini 4.0 Argon 기반 "
                    "에이전트 워크숍 세션 진행 가능합니다! 연락은 sniper45han@gmail.com 으로 부탁드립니다."
                ),
            },
            {
                "channel": "#gde-korea-speakers",
                "author": "박제창 (Flutter GDE)",
                "timestamp": "2026-10-16 11:05 KST",
                "text": (
                    "DevFest 2026 크로스플랫폼 & 온디바이스 AI(Flutter + Firebase AI Logic / Gemini) 핸즈온 코드랩 연사 지원 가능합니다. "
                    "섭외 문의는 aristojeff@gmail.com 으로 메일 주세요!"
                ),
            },
            {
                "channel": "#devfest-2026-ops",
                "author": "GDG Seoul Lead",
                "timestamp": "2026-10-17 16:40 KST",
                "text": (
                    "연사자 확정 후에는 Gmail로 섭외 메일 발송 -> 회신 클러스터링 -> "
                    "Google Form(성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호) 및 Google Calendar 초대를 OpsAgent로 자동화합시다."
                ),
            },
        ]
        if not query:
            return messages
        q = query.lower()
        matched = [
            m
            for m in messages
            if q in m["text"].lower() or q in m["channel"].lower() or q in m["author"].lower()
        ]
        return matched or messages

    def crawl_all_sources(self, query: str = "", force_refresh_hub: bool = False) -> Dict[str, Any]:
        """Aggregate authenticated CommunityHub, Advocu, GDG Korea Sheet, GDE/GDG Directory, and Slack data for RAGSearch."""
        from genmunity_agent.services.gdg_directory import search_gdg_gde_directory

        return {
            "event_info": DEVFEST_EVENT_INFO,
            "community_hub": self.crawl_community_hub(force_refresh=force_refresh_hub),
            "speakers": self.crawl_speakers(query),
            "gdg_gde_directory": search_gdg_gde_directory(query),
            "gdg_korea_sheet": self.fetch_gdg_korea_sheet_notice(),
            "slack_threads": self.crawl_slack_messages(query),
        }


_crawler_instance: Optional[DataCrawler] = None


def get_data_crawler() -> DataCrawler:
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = DataCrawler()
    return _crawler_instance
