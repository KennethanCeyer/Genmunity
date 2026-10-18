"""Google Slides parser supporting Slides API v1, resourcekey headers, export endpoints, and local files.

Handles both direct Google Slides URLs (such as the Build with AI deck with `resourcekey`)
and all Google Slides links discovered inside Community Hub pages (such as DevFest).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from community_hub_agent.config import settings
from community_hub_agent.ingestion.models import (
    SlideDeckDocument,
    SlidePage,
    SourceCategory,
)

logger = logging.getLogger(__name__)

# Matches https://docs.google.com/presentation/d/{PRESENTATION_ID}/...
SLIDES_URL_PATTERN = re.compile(
    r"https?://docs\.google\.com/presentation/d/([a-zA-Z0-9_-]{20,})(?:/[^\s\"'<>)]*)?",
    re.IGNORECASE,
)


def parse_slide_url_metadata(url: str) -> tuple[str | None, str | None]:
    """Extracts (presentation_id, resourcekey) from a Google Slides URL."""
    match = SLIDES_URL_PATTERN.search(url)
    if not match:
        return None, None
    presentation_id = match.group(1)
    # Ignore published /d/e/ prefix if captured accidentally
    if presentation_id == "e":
        return None, None

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    resource_key = None
    for key in ("resourcekey", "resourceKey"):
        if key in qs and qs[key]:
            resource_key = qs[key][0]
            break
    return presentation_id, resource_key


def extract_google_slides_links(html_or_text: str) -> list[str]:
    """Finds and normalizes all unique Google Slides URLs embedded or linked in HTML/text."""
    # Unescape HTML entities like &amp; so resourcekey query params stay intact
    cleaned = html_or_text.replace("&amp;", "&")
    raw_urls = re.findall(
        r"https?://docs\.google\.com/presentation/d/[a-zA-Z0-9_-]{20,}[^\s\"'<>)]*",
        cleaned,
    )
    seen: dict[str, str] = {}
    for raw_url in raw_urls:
        pres_id, res_key = parse_slide_url_metadata(raw_url)
        if not pres_id:
            continue
        canonical = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        if res_key:
            canonical += f"?usp=sharing&resourcekey={res_key}"
        # Prefer URL with resourcekey if seen multiple times
        if pres_id not in seen or (res_key and "resourcekey=" not in seen[pres_id]):
            seen[pres_id] = canonical
    return list(seen.values())


discover_slide_urls_in_text = extract_google_slides_links



class GoogleSlidesParser:
    """Parses Google Slides presentations via Google Slides API, HTTP export, or local files."""

    def __init__(self, cookie_header: str | None = None) -> None:
        self.cookie_header = (
            cookie_header
            if cookie_header is not None
            else settings.community_hub_cookie_header
        )

    def _get_google_credentials(self) -> Any:
        """Loads Google OAuth / Service Account / ADC credentials if available."""
        try:
            import os
            import google.auth
            from google.oauth2.credentials import Credentials

            if settings.oauth_token_path.exists():
                return Credentials.from_authorized_user_file(
                    str(settings.oauth_token_path),
                    scopes=[
                        "https://www.googleapis.com/auth/presentations.readonly",
                        "https://www.googleapis.com/auth/drive.readonly",
                    ],
                )
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                creds, _ = google.auth.default(
                    scopes=[
                        "https://www.googleapis.com/auth/presentations.readonly",
                        "https://www.googleapis.com/auth/drive.readonly",
                    ]
                )
                return creds
            return None
        except Exception as exc:
            logger.debug("Google API credentials not configured: %s", exc)
            return None

    def parse_from_slides_api(
        self,
        presentation_id: str,
        resource_key: str | None,
        source_url: str,
        category: SourceCategory,
        parent_hub_url: str | None = None,
    ) -> SlideDeckDocument | None:
        """Fetches structured slides, tables, speaker notes, and links via Google Slides API v1."""
        creds = self._get_google_credentials()
        if not creds:
            return None

        try:
            from googleapiclient.discovery import build

            service = build(
                "slides", "v1", credentials=creds, cache_discovery=False
            )
            request = service.presentations().get(presentationId=presentation_id)
            if resource_key:
                # Required header for resourcekey-protected Google Drive/Slides files
                request.headers["X-Goog-Drive-Resource-Keys"] = (
                    f"{presentation_id}/{resource_key}"
                )
            presentation = request.execute()
        except Exception as exc:
            logger.warning(
                "Slides API v1 failed for %s: %s", presentation_id, exc
            )
            return None

        title = presentation.get("title", f"Presentation {presentation_id}")
        slides_data: list[SlidePage] = []

        for idx, slide in enumerate(presentation.get("slides", []), start=1):
            slide_page = self._parse_single_api_slide(idx, slide)
            slides_data.append(slide_page)

        return SlideDeckDocument(
            presentation_id=presentation_id,
            resource_key=resource_key,
            title=title,
            source_url=source_url,
            parent_hub_url=parent_hub_url,
            category=category,
            slides=slides_data,
        )

    def _parse_single_api_slide(
        self, slide_number: int, slide: dict[str, Any]
    ) -> SlidePage:
        object_id = slide.get("objectId", f"slide_{slide_number}")
        title = ""
        body_lines: list[str] = []
        tables: list[list[list[str]]] = []
        links: list[str] = []

        for element in slide.get("pageElements", []):
            shape = element.get("shape")
            if shape:
                placeholder_type = (
                    shape.get("placeholder", {}).get("type", "")
                )
                text_str, found_links = self._extract_text_from_elements(
                    shape.get("text", {}).get("textElements", [])
                )
                links.extend(found_links)
                if text_str:
                    if placeholder_type in ("TITLE", "CENTERED_TITLE") and not title:
                        title = text_str.splitlines()[0].strip()
                    else:
                        body_lines.append(text_str)

            table = element.get("table")
            if table:
                parsed_rows: list[list[str]] = []
                for row in table.get("tableRows", []):
                    parsed_cells: list[str] = []
                    for cell in row.get("tableCells", []):
                        cell_text, found_links = self._extract_text_from_elements(
                            cell.get("text", {}).get("textElements", [])
                        )
                        links.extend(found_links)
                        parsed_cells.append(cell_text.replace("\n", " ").strip())
                    parsed_rows.append(parsed_cells)
                if parsed_rows:
                    tables.append(parsed_rows)

        # Extract Speaker Notes
        notes_text = ""
        notes_page = slide.get("slideProperties", {}).get("notesPage", {})
        for element in notes_page.get("pageElements", []):
            shape = element.get("shape", {})
            if shape.get("placeholder", {}).get("type") == "BODY":
                extracted_notes, found_links = self._extract_text_from_elements(
                    shape.get("text", {}).get("textElements", [])
                )
                links.extend(found_links)
                if extracted_notes:
                    notes_text = extracted_notes

        if not title and body_lines:
            first_line = body_lines[0].splitlines()[0].strip()
            if len(first_line) < 120:
                title = first_line

        return SlidePage(
            slide_number=slide_number,
            object_id=object_id,
            title=title,
            body_text=body_lines,
            tables=tables,
            speaker_notes=notes_text,
            links=sorted(set(links)),
        )

    @staticmethod
    def _extract_text_from_elements(
        text_elements: list[dict[str, Any]],
    ) -> tuple[str, list[str]]:
        chunks: list[str] = []
        links: list[str] = []
        for elem in text_elements:
            text_run = elem.get("textRun")
            if not text_run:
                continue
            content = text_run.get("content", "")
            if content:
                chunks.append(content)
            link_url = (
                text_run.get("style", {}).get("link", {}).get("url")
            )
            if link_url:
                links.append(link_url)
        return "".join(chunks).strip(), links

    def parse_from_export_txt(
        self,
        presentation_id: str,
        resource_key: str | None,
        source_url: str,
        category: SourceCategory,
        parent_hub_url: str | None = None,
    ) -> SlideDeckDocument | None:
        """Fallback parser that uses Google Slides `/export/txt` endpoint with optional cookies."""
        export_url = (
            f"https://docs.google.com/presentation/d/{presentation_id}/export/txt"
        )
        if resource_key:
            export_url += f"?resourcekey={resource_key}"

        headers: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header

        try:
            with httpx.Client(follow_redirects=True, timeout=20.0) as client:
                resp = client.get(export_url, headers=headers)
                if resp.status_code != 200:
                    return None
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type and "ServiceLogin" in resp.text:
                    logger.info(
                        "Slide %s requires Google login (received login page).",
                        presentation_id,
                    )
                    return None
                raw_text = resp.text.strip()
                if not raw_text:
                    return None
        except Exception as exc:
            logger.debug("Slide export/txt failed for %s: %s", presentation_id, exc)
            return None

        return self._text_to_slide_deck(
            raw_text=raw_text,
            presentation_id=presentation_id,
            resource_key=resource_key,
            source_url=source_url,
            category=category,
            parent_hub_url=parent_hub_url,
        )

    def parse_from_local_file(
        self,
        file_path: Path,
        presentation_id: str,
        resource_key: str | None,
        source_url: str,
        category: SourceCategory,
        parent_hub_url: str | None = None,
    ) -> SlideDeckDocument | None:
        """Parses a local exported `.txt` or `.md` file for a Google Slides deck."""
        if not file_path.exists():
            return None
        raw_text = file_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return None
        return self._text_to_slide_deck(
            raw_text=raw_text,
            presentation_id=presentation_id,
            resource_key=resource_key,
            source_url=source_url,
            category=category,
            parent_hub_url=parent_hub_url,
        )

    def _text_to_slide_deck(
        self,
        raw_text: str,
        presentation_id: str,
        resource_key: str | None,
        source_url: str,
        category: SourceCategory,
        parent_hub_url: str | None = None,
    ) -> SlideDeckDocument:
        blocks = [
            b.strip()
            for b in re.split(r"\n{2,}|\r\n{2,}|---\n", raw_text)
            if b.strip()
        ]
        slides: list[SlidePage] = []
        for idx, block in enumerate(blocks, start=1):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            title = lines[0]
            body = lines[1:] if len(lines) > 1 else [lines[0]]
            links = re.findall(r"https?://[^\s\"'<>)]+", block)
            slides.append(
                SlidePage(
                    slide_number=idx,
                    object_id=f"slide_{idx}",
                    title=title[:120],
                    body_text=body,
                    links=sorted(set(links)),
                )
            )

        deck_title = (
            slides[0].title if slides else f"Google Slides ({presentation_id})"
        )
        return SlideDeckDocument(
            presentation_id=presentation_id,
            resource_key=resource_key,
            title=deck_title,
            source_url=source_url,
            parent_hub_url=parent_hub_url,
            category=category,
            slides=slides,
        )

    def parse_slide_url(
        self,
        url: str,
        category: SourceCategory,
        parent_hub_url: str | None = None,
    ) -> SlideDeckDocument | None:
        """Orchestrates parsing a Google Slides URL across API -> Export -> Local File."""
        presentation_id, resource_key = parse_slide_url_metadata(url)
        if not presentation_id:
            logger.warning("Could not extract presentation_id from URL: %s", url)
            return None

        # 1. Try Google Slides API v1
        deck = self.parse_from_slides_api(
            presentation_id=presentation_id,
            resource_key=resource_key,
            source_url=url,
            category=category,
            parent_hub_url=parent_hub_url,
        )
        if deck and deck.slides:
            logger.info(
                "Parsed %d slides via Slides API for %s",
                len(deck.slides),
                presentation_id,
            )
            return deck

        # 2. Try HTTP Export (/export/txt) with resourcekey & cookies
        deck = self.parse_from_export_txt(
            presentation_id=presentation_id,
            resource_key=resource_key,
            source_url=url,
            category=category,
            parent_hub_url=parent_hub_url,
        )
        if deck and deck.slides:
            logger.info(
                "Parsed %d slides via /export/txt for %s",
                len(deck.slides),
                presentation_id,
            )
            return deck

        # 3. Try Local Raw File Fallback (data/raw/{presentation_id}.txt or .md)
        raw_dir = settings.data_dir / "raw"
        for ext in (".txt", ".md"):
            candidate = raw_dir / f"{presentation_id}{ext}"
            deck = self.parse_from_local_file(
                file_path=candidate,
                presentation_id=presentation_id,
                resource_key=resource_key,
                source_url=url,
                category=category,
                parent_hub_url=parent_hub_url,
            )
            if deck and deck.slides:
                logger.info(
                    "Parsed %d slides from local file %s",
                    len(deck.slides),
                    candidate,
                )
                return deck

        return None
