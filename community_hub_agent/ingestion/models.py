"""Data models for Community Hub, Google Slides, and Google Sheets ingestion."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

SourceCategory = Literal["devfest", "build_with_ai", "kr_organizer", "general"]
SourceType = Literal[
    "community_hub_web",
    "google_slides",
    "google_sheets",
    "local_file",
    "seed_data",
    "slack_channel",
]


class DocumentChunk(BaseModel):
    """A normalized chunk ready for embedding and indexing into Vector DB or Vertex AI Search."""

    chunk_id: str
    title: str
    content: str
    category: SourceCategory
    source_type: SourceType
    source_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class SlidePage(BaseModel):
    """Extracted content from a single slide in a Google Slides presentation."""

    slide_number: int
    object_id: str
    title: str = ""
    body_text: list[str] = Field(default_factory=list)
    tables: list[list[list[str]]] = Field(default_factory=list)
    speaker_notes: str = ""
    links: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines: list[str] = []
        header = f"### Slide {self.slide_number}"
        if self.title:
            header += f": {self.title}"
        lines.append(header)

        if self.body_text:
            lines.extend(self.body_text)

        for table in self.tables:
            if not table:
                continue
            lines.append("")
            header_row = " | ".join(cell.strip() for cell in table[0])
            sep_row = " | ".join("---" for _ in table[0])
            lines.append(f"| {header_row} |")
            lines.append(f"| {sep_row} |")
            for row in table[1:]:
                lines.append(f"| {' | '.join(cell.strip() for cell in row)} |")
            lines.append("")

        if self.speaker_notes:
            lines.append(f"\n**[Speaker Notes]**: {self.speaker_notes}")

        if self.links:
            lines.append("\n**[Included Links]**: " + ", ".join(self.links))

        return "\n".join(lines).strip()


class SlideDeckDocument(BaseModel):
    """A full parsed Google Slides presentation."""

    presentation_id: str
    resource_key: str | None = None
    title: str
    source_url: str
    parent_hub_url: str | None = None
    category: SourceCategory
    slides: list[SlidePage] = Field(default_factory=list)


class SheetRowRecord(BaseModel):
    """A single structured row from the Korean GDG/GDE Organizer Google Sheet."""

    sheet_title: str
    row_index: int
    values: dict[str, str]

    def to_text(self) -> str:
        pairs = [f"{k}: {v}" for k, v in self.values.items() if v.strip()]
        return f"[{self.sheet_title} - Row {self.row_index}] " + " | ".join(pairs)


class SheetDocument(BaseModel):
    """A full parsed Google Spreadsheet across all tabs."""

    spreadsheet_id: str
    title: str
    source_url: str
    category: SourceCategory = "kr_organizer"
    rows: list[SheetRowRecord] = Field(default_factory=list)


class WebPageDocument(BaseModel):
    """A parsed Community Hub web page and all discovered Google Slides links inside it."""

    url: str
    title: str
    category: SourceCategory
    sections: list[dict[str, str]] = Field(default_factory=list)
    discovered_slide_urls: list[str] = Field(default_factory=list)


# Alias for backward/forward compatibility
HubPageDocument = WebPageDocument


class SlackReplyRecord(BaseModel):
    """A single thread reply inside a Slack channel message thread."""

    ts: str
    datetime_kst: str
    author_id: str
    author_name: str
    text: str
    files: list[dict[str, str]] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class SlackThreadRecord(BaseModel):
    """A normalized Slack top-level message (or pinned announcement) with its thread replies."""

    ts: str
    datetime_kst: str
    author_id: str
    author_name: str
    title: str
    text: str
    permalink: str
    is_pinned: bool = False
    subtype: str = ""
    secondary_categories: list[SourceCategory] = Field(default_factory=list)
    chapters_mentioned: list[str] = Field(default_factory=list)
    people_mentioned: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    files: list[dict[str, str]] = Field(default_factory=list)
    reactions: list[str] = Field(default_factory=list)
    replies: list[SlackReplyRecord] = Field(default_factory=list)

    def to_markdown(self) -> str:
        pin_badge = "📌 [채널 고정 공지 (Pinned)] " if self.is_pinned else ""
        lines = [
            f"### {pin_badge}{self.title}",
            f"- **채널**: GDG Korea `#organizers` (`C04E1UAAY`)",
            f"- **작성자**: {self.author_name} | **일시(KST)**: {self.datetime_kst}",
            f"- **슬랙 원본 링크**: {self.permalink}",
            "",
            self.text,
        ]
        if self.files:
            lines.append("\n**[첨부 파일]**")
            for f in self.files:
                lines.append(f"- `{f.get('name', 'file')}` ({f.get('mimetype', '')}): {f.get('url', '')}")
        if self.links:
            lines.append("\n**[본문 및 스레드 포함 링크]**")
            for link in self.links:
                lines.append(f"- {link}")
        if self.reactions:
            lines.append(f"\n**[리액션]**: {', '.join(self.reactions)}")
        if self.replies:
            lines.append(f"\n#### 💬 스레드 댓글 ({len(self.replies)}건)")
            for r in self.replies:
                lines.append(f"- **{r.author_name}** ({r.datetime_kst}):\n  {r.text}")
                for rf in r.files:
                    lines.append(f"  - 📎 `{rf.get('name', 'file')}`: {rf.get('url', '')}")
        return "\n".join(lines).strip()


class SlackChannelDocument(BaseModel):
    """A full parsed Slack channel export including pinned messages, timeline threads, and user profiles."""

    channel_id: str
    channel_name: str
    workspace_url: str = "https://gdgkr.slack.com"
    source_url: str = "https://gdgkr.slack.com/archives/C04E1UAAY"
    category: SourceCategory = "kr_organizer"
    fetched_at: str = ""
    is_limited: bool = True
    users: dict[str, dict[str, Any]] = Field(default_factory=dict)
    threads: list[SlackThreadRecord] = Field(default_factory=list)
    discovered_slide_urls: list[tuple[str, SourceCategory]] = Field(default_factory=list)


