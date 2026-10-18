"""Ingestion package for GDG/GDE Community Hub, Google Slides, and Google Sheets."""

from community_hub_agent.ingestion.chunker import CommunityHubChunker
from community_hub_agent.ingestion.hub_crawler import CommunityHubCrawler
from community_hub_agent.ingestion.models import (
    DocumentChunk,
    SheetDocument,
    SheetRowRecord,
    SlideDeckDocument,
    SlidePage,
    WebPageDocument,
)
from community_hub_agent.ingestion.pipeline import CommunityHubIngestionPipeline
from community_hub_agent.ingestion.sheets_parser import (
    GoogleSheetsParser,
    extract_spreadsheet_id,
)
from community_hub_agent.ingestion.slides_parser import (
    GoogleSlidesParser,
    extract_google_slides_links,
    parse_slide_url_metadata,
)

__all__ = [
    "CommunityHubChunker",
    "CommunityHubCrawler",
    "CommunityHubIngestionPipeline",
    "DocumentChunk",
    "GoogleSheetsParser",
    "GoogleSlidesParser",
    "SheetDocument",
    "SheetRowRecord",
    "SlideDeckDocument",
    "SlidePage",
    "WebPageDocument",
    "extract_google_slides_links",
    "extract_spreadsheet_id",
    "parse_slide_url_metadata",
]
