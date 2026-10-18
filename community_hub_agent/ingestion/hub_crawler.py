"""Community Hub web page crawler & embedded Google Slides link extractor.

Crawls GDG/GDE Community Hub pages (DevFest, Build with AI) using:
1. Playwright authenticated browser session (`.auth/storage_state.json`)
2. HTTPX with `COMMUNITY_HUB_COOKIE_HEADER`
3. Local exported HTML files in `data/raw/`

Automatically discovers and extracts ALL Google Slides URLs embedded or linked
within the Community Hub page so every linked presentation deck is also parsed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from community_hub_agent.config import settings
from community_hub_agent.ingestion.models import SourceCategory, WebPageDocument
from community_hub_agent.ingestion.slides_parser import extract_google_slides_links

logger = logging.getLogger(__name__)


class CommunityHubCrawler:
    """Fetches and parses Google Developer Community Hub pages and discovers internal Google Slides."""

    def __init__(self, cookie_header: str | None = None) -> None:
        self.cookie_header = (
            cookie_header
            if cookie_header is not None
            else settings.community_hub_cookie_header
        )

    def fetch_html_via_http(self, url: str) -> str | None:
        """Fetches Community Hub HTML via HTTPX using optional session cookies."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header

        try:
            with httpx.Client(follow_redirects=True, timeout=20.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.info(
                        "Community Hub %s returned HTTP %d (requires GDG/GDE login or cookie).",
                        url,
                        resp.status_code,
                    )
                    return None
                if "ServiceLogin" in resp.url.path or "accounts.google.com" in str(resp.url):
                    logger.info("Community Hub %s redirected to Google Login.", url)
                    return None
                return resp.text
        except Exception as exc:
            logger.debug("HTTP fetch failed for %s: %s", url, exc)
            return None

    def fetch_html_via_playwright(self, url: str) -> str | None:
        """Fetches Community Hub HTML using a saved Playwright storage_state session."""
        if not settings.playwright_storage_state.exists():
            return None
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    storage_state=str(settings.playwright_storage_state)
                )
                page = context.new_page()
                resp = page.goto(url, wait_until="networkidle", timeout=30000)
                if not resp or resp.status >= 400:
                    browser.close()
                    return None
                html = page.content()
                browser.close()
                return html
        except Exception as exc:
            logger.debug("Playwright fetch failed for %s: %s", url, exc)
            return None

    def fetch_html_from_local(self, category: SourceCategory) -> str | None:
        """Checks `data/raw/` for locally saved HTML pages (e.g., devfest.html, build_with_ai.html)."""
        raw_dir = settings.data_dir / "raw"
        candidates = [
            raw_dir / f"{category}.html",
            raw_dir / f"{category.replace('_', '-')}.html",
        ]
        for path in candidates:
            if path.exists():
                logger.info("Loading Community Hub HTML from local file: %s", path)
                return path.read_text(encoding="utf-8")
        return None

    def parse_html(
        self, html: str, url: str, category: SourceCategory
    ) -> WebPageDocument:
        """Parses Community Hub HTML into structured sections and extracts all Google Slides links."""
        soup = BeautifulSoup(html, "html.parser")

        # 1. Discover all Google Slides URLs from href, iframe src, data-* attributes, and raw HTML
        slide_candidates: list[str] = []
        for tag in soup.find_all(["a", "iframe", "embed"]):
            for attr in ("href", "src", "data-src", "data-href"):
                val = tag.get(attr)
                if isinstance(val, str) and "docs.google.com/presentation" in val:
                    slide_candidates.append(urljoin(url, val))

        combined_slide_source = "\n".join(slide_candidates) + "\n" + html
        discovered_slides = extract_google_slides_links(combined_slide_source)

        # 2. Extract page title
        title_tag = soup.find("h1") or soup.find("title")
        page_title = (
            title_tag.get_text(strip=True)
            if title_tag
            else f"Community Hub ({category})"
        )

        # 3. Remove script/style/nav clutter before sectioning
        for noise in soup.find_all(["script", "style", "noscript", "svg"]):
            noise.decompose()

        main_container = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_="devsite-article-body")
            or soup.body
            or soup
        )

        sections: list[dict[str, str]] = []
        current_heading = page_title
        current_lines: list[str] = []

        for elem in main_container.find_all(
            ["h1", "h2", "h3", "h4", "p", "li", "table", "iframe", "a"]
        ):
            tag_name = elem.name
            if tag_name in ("h1", "h2", "h3", "h4"):
                if current_lines:
                    sections.append(
                        {
                            "heading": current_heading,
                            "content": "\n".join(current_lines).strip(),
                        }
                    )
                    current_lines = []
                heading_text = elem.get_text(" ", strip=True)
                if heading_text:
                    current_heading = heading_text
            elif tag_name == "iframe":
                src = elem.get("src") or elem.get("data-src") or ""
                if isinstance(src, str) and "docs.google.com/presentation" in src:
                    current_lines.append(f"- [Embedded Google Slides]: {src}")
            elif tag_name == "a":
                # Only capture standalone <a> tags not already inside <p>, <li>, or <table>
                if elem.find_parent(["p", "li", "table"]) is None:
                    href = elem.get("href", "")
                    label = elem.get_text(" ", strip=True) or "Link"
                    if isinstance(href, str) and href.startswith("http"):
                        current_lines.append(f"- [{label}]({href})")
            elif tag_name == "table":
                rows_md: list[str] = []
                for tr in elem.find_all("tr"):
                    cells = [
                        td.get_text(" ", strip=True)
                        for td in tr.find_all(["th", "td"])
                    ]
                    if any(cells):
                        rows_md.append("| " + " | ".join(cells) + " |")
                if rows_md:
                    current_lines.append("\n".join(rows_md))
            else:
                # Preserve inline links in paragraph/list items
                text = elem.get_text(" ", strip=True)
                if not text:
                    continue
                links_in_elem = [
                    a.get("href")
                    for a in elem.find_all("a", href=True)
                    if isinstance(a.get("href"), str)
                    and a.get("href").startswith("http")
                ]
                if links_in_elem:
                    text += " (링크: " + ", ".join(sorted(set(links_in_elem))) + ")"
                prefix = "- " if tag_name == "li" else ""
                current_lines.append(f"{prefix}{text}")

        if current_lines:
            sections.append(
                {
                    "heading": current_heading,
                    "content": "\n".join(current_lines).strip(),
                }
            )

        return WebPageDocument(
            url=url,
            title=page_title,
            category=category,
            sections=sections,
            discovered_slide_urls=discovered_slides,
        )

    def crawl_hub_page(
        self, url: str, category: SourceCategory
    ) -> WebPageDocument | None:
        """Crawls a Community Hub page via Playwright -> HTTP Cookie -> Local HTML file."""
        html = (
            self.fetch_html_via_playwright(url)
            or self.fetch_html_via_http(url)
            or self.fetch_html_from_local(category)
        )
        if not html:
            return None
        doc = self.parse_html(html=html, url=url, category=category)
        logger.info(
            "Parsed Community Hub page '%s' (%d sections, %d embedded Google Slides discovered)",
            doc.title,
            len(doc.sections),
            len(doc.discovered_slide_urls),
        )
        return doc
