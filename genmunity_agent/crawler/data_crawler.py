import logging
from typing import Dict, Any, List, Optional
import requests

from genmunity_agent.config import (
    GDG_KOREA_SHEET_ID,
    GDG_KOREA_SHEET_URL,
    HARDCODED_SPEAKERS,
    DEVFEST_EVENT_INFO,
)

logger = logging.getLogger("genmunity.crawler")


class DataCrawler:
    """
    Crawls and aggregates community knowledge from:
    1. GDG Korea Domestic Organizers & GDE Google Sheet
    2. Advocu Speaker & Event Directory
    3. CommunityHub Event Playbook (DevFest Schedule & Budget Guidelines)
    4. GDG/GDE Slack Archive (#devfest-2026-organizers, #gde-korea-speakers)
    """

    def __init__(self) -> None:
        self._sheet_cache: Optional[str] = None

    def fetch_gdg_korea_sheet_notice(self) -> Dict[str, Any]:
        """Fetch live public notice/rows from the GDG Korea Organizers Google Sheet."""
        csv_url = f"https://docs.google.com/spreadsheets/d/{GDG_KOREA_SHEET_ID}/export?format=csv"
        try:
            resp = requests.get(csv_url, timeout=6)
            if resp.status_code == 200 and resp.text.strip():
                self._sheet_cache = resp.text.strip()
                return {
                    "status": "live_fetched",
                    "sheet_url": GDG_KOREA_SHEET_URL,
                    "content": self._sheet_cache,
                }
        except Exception as exc:
            logger.warning(f"Failed to fetch live GDG Sheet CSV: {exc}")

        fallback = (
            "Google for Developers - 이 시트는 구글 개발자 커뮤니티 간의 원활한 연락, 소통, "
            "그리고 연합 이벤트 등을 위해 내부적으로 공유되는 시트입니다. "
            "타 GDG운영진/GDE 에게 연락할 때는 정중하게 예의를 갖추고 챕터 소개 및 자기소개를 포함해주세요."
        )
        return {
            "status": "cached_fallback",
            "sheet_url": GDG_KOREA_SHEET_URL,
            "content": self._sheet_cache or fallback,
        }

    def crawl_speakers(self, query: str = "") -> List[Dict[str, Any]]:
        """
        Return matched speakers from Advocu & GDG Korea GDE Directory.
        Always includes the two primary DevFest Hands-on GDE speakers:
        1. 한성민 (sniper45han@gmail.com) - AI GDE (첫번째 연사자)
        2. 박제창 (aristojeff@gmail.com) - Flutter GDE (두번째 연사자)
        """
        q = (query or "").lower()
        speakers = list(HARDCODED_SPEAKERS)
        if not q or any(k in q for k in ["devfest", "핸즈온", "연사", "스피커", "전체", "추천", "gde"]):
            return speakers

        filtered = [
            s
            for s in speakers
            if q in s["name"].lower()
            or q in s["role"].lower()
            or q in s["track"].lower()
            or q in s["email"].lower()
        ]
        return filtered or speakers

    def crawl_slack_messages(self, query: str = "") -> List[Dict[str, Any]]:
        """Simulate/retrieve GDG/GDE Slack channel threads relevant to DevFest planning."""
        messages = [
            {
                "channel": "#devfest-2026-organizers",
                "author": "권나현 (Google Dev Ecosystem Community Manager)",
                "timestamp": "2026-10-12 10:15 KST",
                "text": (
                    "안녕하세요 운영진 여러분! 올해 DevFest 2026 시즌은 12월 31일까지 진행됩니다. "
                    "예산 지원은 규모별로 $1,500 ~ $5,000까지 신청 가능하며 행사 6주 전까지 신청서를 제출해주세요."
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
                    "DevFest 2026 크로스플랫폼 & 온디바이스 AI(Flutter + Gemini) 핸즈온 코드랩 연사 지원 가능합니다. "
                    "섭외 문의는 aristojeff@gmail.com 으로 메일 주세요!"
                ),
            },
            {
                "channel": "#devfest-2026-ops",
                "author": "GDG Seoul Lead",
                "timestamp": "2026-10-17 16:40 KST",
                "text": (
                    "연사자 확정 후에는 Gmail로 섭외 메일 발송 -> 회신 클러스터링 -> "
                    "발표자 정보 입력 Form(성함, 이메일, 연락처, 티셔츠 사이즈, 차량 번호) 및 캘린더 초대를 OpsAgent로 자동화합시다."
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

    def crawl_all_sources(self, query: str = "") -> Dict[str, Any]:
        """Aggregate CommunityHub, Advocu, GDG Korea Sheet, and Slack data for RAGSearch."""
        return {
            "event_info": DEVFEST_EVENT_INFO,
            "speakers": self.crawl_speakers(query),
            "gdg_korea_sheet": self.fetch_gdg_korea_sheet_notice(),
            "slack_threads": self.crawl_slack_messages(query),
        }


_crawler_instance: Optional[DataCrawler] = None


def get_data_crawler() -> DataCrawler:
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = DataCrawler()
    return _crawler_instance
