"""Semantic and structural chunker for Community Hub pages, Google Slides, Google Sheets, and Slack channels."""

from __future__ import annotations

import hashlib
from typing import Iterable

from community_hub_agent.ingestion.models import (
    DocumentChunk,
    SheetDocument,
    SlackChannelDocument,
    SlideDeckDocument,
    WebPageDocument,
)


def _make_chunk_id(prefix: str, unique_key: str) -> str:
    digest = hashlib.sha1(unique_key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


class CommunityHubChunker:
    """Converts parsed WebPages, SlideDecks, Sheets, and SlackChannels into RAG-ready DocumentChunks."""

    def __init__(self, max_chars: int = 1200, overlap_chars: int = 180) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk_web_page(self, page: WebPageDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for sec_idx, section in enumerate(page.sections, start=1):
            heading = section.get("heading", page.title)
            body = section.get("content", "").strip()
            if not body:
                continue

            sub_texts = self._split_text(body)
            for part_idx, text_part in enumerate(sub_texts, start=1):
                chunk_id = _make_chunk_id(
                    f"hub_{page.category}",
                    f"{page.url}::{sec_idx}::{part_idx}",
                )
                full_title = f"{page.title} - {heading}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        title=full_title,
                        content=f"## {full_title}\n\n{text_part}",
                        category=page.category,
                        source_type="community_hub_web",
                        source_url=page.url,
                        metadata={
                            "page_title": page.title,
                            "section_heading": heading,
                            "section_index": sec_idx,
                            "part_index": part_idx,
                            "discovered_slide_urls": page.discovered_slide_urls,
                        },
                    )
                )
        return chunks

    def chunk_slide_deck(self, deck: SlideDeckDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for slide in deck.slides:
            md = slide.to_markdown()
            if not md:
                continue
            chunk_id = _make_chunk_id(
                f"slide_{deck.category}",
                f"{deck.presentation_id}::slide_{slide.slide_number}",
            )
            slide_title = (
                f"{deck.title} (Slide {slide.slide_number}: {slide.title})"
                if slide.title
                else f"{deck.title} (Slide {slide.slide_number})"
            )
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    title=slide_title,
                    content=f"# [Google Slides] {deck.title}\n{md}",
                    category=deck.category,
                    source_type="google_slides",
                    source_url=deck.source_url,
                    metadata={
                        "presentation_id": deck.presentation_id,
                        "resource_key": deck.resource_key or "",
                        "deck_title": deck.title,
                        "slide_number": slide.slide_number,
                        "slide_title": slide.title,
                        "parent_hub_url": deck.parent_hub_url or "",
                        "links": slide.links,
                    },
                )
            )
        return chunks

    def chunk_sheet(
        self, sheet: SheetDocument, rows_per_chunk: int = 5
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        # Group rows by sheet_title first
        by_tab: dict[str, list[str]] = {}
        for row in sheet.rows:
            by_tab.setdefault(row.sheet_title, []).append(row.to_text())

        for tab_title, row_texts in by_tab.items():
            for i in range(0, len(row_texts), rows_per_chunk):
                batch = row_texts[i : i + rows_per_chunk]
                start_row = i + 2
                end_row = start_row + len(batch) - 1
                chunk_id = _make_chunk_id(
                    "sheet_kr_org",
                    f"{sheet.spreadsheet_id}::{tab_title}::{start_row}-{end_row}",
                )
                title = f"{sheet.title} [{tab_title}] (Rows {start_row}~{end_row})"
                content = (
                    f"# [Google Sheets] {sheet.title} - 탭: {tab_title}\n"
                    + "\n".join(batch)
                )
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        title=title,
                        content=content,
                        category=sheet.category,
                        source_type="google_sheets",
                        source_url=sheet.source_url,
                        metadata={
                            "spreadsheet_id": sheet.spreadsheet_id,
                            "sheet_title": tab_title,
                            "start_row": start_row,
                            "end_row": end_row,
                        },
                    )
                )
        return chunks

    def chunk_slack_channel(
        self, doc: SlackChannelDocument
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []

        # 1. Executive Summary Chunk for the #organizers Slack channel
        overview_id = _make_chunk_id(
            "slack_kr_org", f"{doc.channel_id}::overview"
        )
        overview_content = (
            f"# [Slack] GDG Korea #{doc.channel_name} ({doc.channel_id}) 종합 요약\n"
            f"- 채널 URL: {doc.source_url}\n"
            f"- 수집된 주요 스레드/공지 수: {len(doc.threads)}개 (고정 공지 포함)\n"
            f"- 주요 공지 및 의사결정 내역:\n"
            f"  1. **2026 DevFest 예산 및 스폰서십 정책 (권나현 CM 공지)**:\n"
            f"     - 참석자 1인당 지원금 **25,000원**으로 증액 확정 (기존 20,000원 → 25,000원 확대, 인플레이션 반영)\n"
            f"     - 행사 45일 전 스폰서십 신청 필수, 1개 챕터당 연 1회 DevFest만 지원\n"
            f"     - **AI Studio** 또는 **Antigravity** 핸즈온 워크샵 포함 시 추가 예산 및 운영진 특별 SWAG 우대\n"
            f"  2. **2026 상반기 무료 대관 안내 (권나현 CM 공지)**:\n"
            f"     - **서울 AI 허브 (양재)** 상반기 무료 대관 선착순 신청 및 이벤터스 안영학 대표 'AI로 행사 기획 및 운영 자동화하기' 안내\n"
            f"     - 주차 불가(대중교통 권장), 케이터링/다과 반입 금지\n"
            f"  3. **2026 KR Developer Community Summit & 설문조사 (10/17~10/18, 구글 스타트업 캠퍼스)**:\n"
            f"     - 참가 신청 오거나이저 웰컴 기프트로 **리바이스 데님 자켓 (Levi's Denim Jacket)** 증정\n"
            f"     - 성기동, 윤지원, 조희주, 노경모, 권진겸 등 참가 확인 및 `#26-summit` 전용 채널 안내\n"
            f"  4. **GDG Incheon(인천) 에이전트톤 결과물 공유 (조새벽 공유)**:\n"
            f"     - 참가자 전 팀(1조~7조) 인천 로컬 AI 에이전트 웹서비스 배포 URL 전체 목록 공유\n"
            f"  5. **Google Cloud AI Builder Cup 2026 (권나현 CM 공지)**:\n"
            f"     - JAPAC 하이브리드 해커톤 (총 상금 $30,000+, 싱가포르 결선 항공/숙박 지원), 오거나이저 우선 선발 혜택\n"
            f"     - 신청 댓글: 김인철(GDG Daejeon), 서보석(GDG Daejeon), 윤지원(GDG Seoul), 조새벽(GDG Incheon), 변성윤(GDE)\n"
            f"  6. **신규 오거나이저 합류 및 변동**:\n"
            f"     - **GDG Busan 신규 합류**: 황재웅 (Jaewoong Hwang), 이재훈 (Jaehun Lee) (성기동, 권준호, 배필주 환영)\n"
            f"     - **GDG Incheon 신규 합류**: 건주 (Geonju, 유광무 소개)\n"
            f"     - **채널 퇴장 기록**: 최가인 (Ga-in Olivia Choi, GDG Daegu), 황지현 (JiHyeon Hwang, GDG Daegu)\n"
            f"  7. **I/O Extended 및 커뮤니티 주요 소식**:\n"
            f"     - GDG Busan I/O Extended (권준호, 천명기, 배필주 참관기 발표, 성기동 후기 및 호두 알레르기 다과 팁)\n"
            f"     - GDG Campus Korea I/O Extended (김수빈, 윤현서, 강인영, 컬리 후원)\n"
            f"     - GDG Android Korea I/O Extended (강경완 공유) 및 안드로이드 소소밋업 (이현우)\n"
            f"     - 박해선 GDE 도서 나눔 ('핸즈온 머신러닝 3판', '파이토치로 배우는 LLM&AI' 각 4권 선착순)\n"
            f"  8. **Build with AI 고정 공지 (권나현 CM 핀 고정 3건)**:\n"
            f"     - 추천 연사: 이준범(AI GDE, Gemma 2 한국어 튜닝), 박진형(서울대, Gemini 웹앱), 정명훈(Google Cloud Partner Engineer, Gemini 2.0 Live API 실시간 영상 챗봇), Sasha Denisov(멀티 GDE, flutter_gemma)\n"
            f"     - 지원 조건: 시트 마감 기한 준수 및 행사 D-15 클라우드 크레딧 신청"
        )
        chunks.append(
            DocumentChunk(
                chunk_id=overview_id,
                title=f"[Slack #{doc.channel_name}] GDG Korea 오거나이저 슬랙 채널 전체 핵심 요약",
                content=overview_content,
                category=doc.category,
                source_type="slack_channel",
                source_url=doc.source_url,
                metadata={
                    "channel_id": doc.channel_id,
                    "channel_name": doc.channel_name,
                    "workspace_url": doc.workspace_url,
                    "is_overview": True,
                    "secondary_categories": ["devfest", "build_with_ai"],
                },
            )
        )

        # 2. Individual Thread / Pinned Notice Chunks
        for thread in doc.threads:
            chunk_id = _make_chunk_id(
                "slack_kr_org",
                f"{doc.channel_id}::{thread.ts}",
            )
            md_body = thread.to_markdown()
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    title=thread.title,
                    content=md_body,
                    category="kr_organizer",
                    source_type="slack_channel",
                    source_url=thread.permalink,
                    metadata={
                        "channel_id": doc.channel_id,
                        "channel_name": doc.channel_name,
                        "thread_ts": thread.ts,
                        "posted_at": thread.datetime_kst,
                        "author_id": thread.author_id,
                        "author_name": thread.author_name,
                        "is_pinned": thread.is_pinned,
                        "reply_count": len(thread.replies),
                        "chapters_mentioned": thread.chapters_mentioned,
                        "people_mentioned": thread.people_mentioned,
                        "links": thread.links,
                        "secondary_categories": thread.secondary_categories,
                    },
                )
            )

        return chunks

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]
        parts: list[str] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(start + self.max_chars, length)
            if end < length:
                # Try breaking on newline or period
                newline_pos = text.rfind("\n", start, end)
                if newline_pos > start + (self.max_chars // 2):
                    end = newline_pos
            parts.append(text[start:end].strip())
            if end >= length:
                break
            start = max(0, end - self.overlap_chars)
        return [p for p in parts if p]
