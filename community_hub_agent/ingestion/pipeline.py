"""End-to-end Ingestion Pipeline for GDG/GDE Community Hub, Google Slides, and Korean Organizer Excel/Sheets.

1. Crawls DevFest & Build with AI Community Hub pages.
2. Automatically discovers and parses ALL Google Slides linked inside the Community Hub pages AND inside the Korean Organizer Excel workbook.
3. Parses the explicit Build with AI Google Slides presentation (with `resourcekey`).
4. Parses the Korean GDG/GDE Organizer Google Spreadsheet or local `.xlsx` (`/Users/jaichang/Downloads/[External] GDG KR Communication.xlsx`) across all 11 tabs.
5. Loads pre-built seed knowledge (`data/seed/community_hub_seed.json`).
6. Indexes chunks with embeddings into the Vector Store (`data/indexed_chunks.json` + optional GCP Vector DB)
   AND builds the multi-relational **Knowledge Graph** (`data/knowledge_graph.json`) for GraphRAG.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from community_hub_agent.config import settings
from community_hub_agent.ingestion.chunker import CommunityHubChunker
from community_hub_agent.ingestion.hub_crawler import CommunityHubCrawler
from community_hub_agent.ingestion.models import (
    DocumentChunk,
    HubPageDocument,
    SheetDocument,
    SlackChannelDocument,
    SlideDeckDocument,
    SourceCategory,
)
from community_hub_agent.ingestion.sheets_parser import GoogleSheetsParser
from community_hub_agent.ingestion.slack_parser import SlackChannelParser
from community_hub_agent.ingestion.slides_parser import (
    GoogleSlidesParser,
    discover_slide_urls_in_text,
    parse_slide_url_metadata,
)

logger = logging.getLogger(__name__)


class CommunityHubIngestionPipeline:
    """Orchestrates multi-source ingestion and indexing into Vector RAG & GraphRAG."""

    def __init__(self, cookie_header: str | None = None) -> None:
        self.crawler = CommunityHubCrawler(cookie_header=cookie_header)
        self.slides_parser = GoogleSlidesParser(cookie_header=cookie_header)
        self.sheets_parser = GoogleSheetsParser(cookie_header=cookie_header)
        self.slack_parser = SlackChannelParser()
        self.chunker = CommunityHubChunker()

    def load_seed_chunks(self) -> list[DocumentChunk]:
        """Loads baseline seed chunks for DevFest, Build with AI, and Korean Organizers."""
        if not settings.seed_file.exists():
            return []
        try:
            raw_list = json.loads(
                settings.seed_file.read_text(encoding="utf-8")
            )
            return [DocumentChunk.model_validate(item) for item in raw_list]
        except Exception as exc:
            logger.warning("Failed to load seed chunks: %s", exc)
            return []

    def run_ingestion(
        self,
        source_filter: str = "all",
        include_seed: bool = True,
        upload_to_gcs: bool = False,
    ) -> dict[str, Any]:
        """Runs the ingestion pipeline for both Vector RAG and GraphRAG."""
        collected_chunks: list[DocumentChunk] = []
        parsed_hub_pages: list[HubPageDocument] = []
        parsed_slide_decks: list[SlideDeckDocument] = []
        parsed_sheet_docs: list[SheetDocument] = []
        parsed_slack_docs: list[SlackChannelDocument] = []
        discovered_slide_urls: list[tuple[str, SourceCategory, str | None]] = []

        stats: dict[str, Any] = {
            "hub_pages_parsed": 0,
            "slides_discovered": 0,
            "slide_decks_parsed": 0,
            "sheet_rows_parsed": 0,
            "slack_threads_parsed": 0,
            "seed_chunks_loaded": 0,
            "total_chunks_indexed": 0,
            "knowledge_graph": {},
            "gcs_uploaded_files": 0,
            "sources_status": {},
        }

        # 1. DevFest Community Hub Page + All Internal Google Slides
        if source_filter in ("all", "devfest"):
            devfest_page = self.crawler.crawl_hub_page(
                url=settings.devfest_hub_url, category="devfest"
            )
            if devfest_page:
                parsed_hub_pages.append(devfest_page)
                stats["hub_pages_parsed"] += 1
                page_chunks = self.chunker.chunk_web_page(devfest_page)
                collected_chunks.extend(page_chunks)
                stats["sources_status"]["devfest_hub"] = (
                    f"live_parsed ({len(page_chunks)} chunks, "
                    f"{len(devfest_page.discovered_slide_urls)} slides discovered)"
                )
                for slide_url in devfest_page.discovered_slide_urls:
                    discovered_slide_urls.append(
                        (slide_url, "devfest", settings.devfest_hub_url)
                    )
            else:
                stats["sources_status"]["devfest_hub"] = (
                    "auth_required_using_seed_fallback"
                )

        # 2. Build with AI Community Hub Page (?hl=ko) + Internal Google Slides
        if source_filter in ("all", "build_with_ai", "buildwithai"):
            bwai_page = self.crawler.crawl_hub_page(
                url=settings.build_with_ai_hub_url, category="build_with_ai"
            )
            if bwai_page:
                parsed_hub_pages.append(bwai_page)
                stats["hub_pages_parsed"] += 1
                page_chunks = self.chunker.chunk_web_page(bwai_page)
                collected_chunks.extend(page_chunks)
                stats["sources_status"]["build_with_ai_hub"] = (
                    f"live_parsed ({len(page_chunks)} chunks, "
                    f"{len(bwai_page.discovered_slide_urls)} slides discovered)"
                )
                for slide_url in bwai_page.discovered_slide_urls:
                    discovered_slide_urls.append(
                        (
                            slide_url,
                            "build_with_ai",
                            settings.build_with_ai_hub_url,
                        )
                    )
            else:
                stats["sources_status"]["build_with_ai_hub"] = (
                    "auth_required_using_seed_fallback"
                )

            # Explicit Build with AI Google Slides Deck (with resourcekey)
            discovered_slide_urls.append(
                (
                    settings.build_with_ai_slide_url,
                    "build_with_ai",
                    settings.build_with_ai_hub_url,
                )
            )

        # 3. Korean GDG/GDE Organizer Google Sheets / Local Excel (.xlsx)
        if source_filter in ("all", "kr_organizer", "sheets"):
            sheet_sources = [
                ("kr_organizer_sheet", settings.kr_organizer_sheet_url),
                ("kr_leads_directory_sheet", settings.kr_leads_sheet_url),
            ]
            for status_key, sheet_url in sheet_sources:
                sheet_doc = self.sheets_parser.parse_sheet_url(sheet_url)
                if sheet_doc and sheet_doc.rows:
                    parsed_sheet_docs.append(sheet_doc)
                    stats["sheet_rows_parsed"] += len(sheet_doc.rows)
                    sheet_chunks = self.chunker.chunk_sheet(sheet_doc)
                    collected_chunks.extend(sheet_chunks)
                    stats["sources_status"][status_key] = (
                        f"parsed ({len(sheet_doc.rows)} rows, {len(sheet_chunks)} chunks)"
                    )
                    # Also discover any Google Slides URLs embedded in the sheet notes
                    for row in sheet_doc.rows:
                        joined_vals = " ".join(row.values.values())
                        for s_url in discover_slide_urls_in_text(joined_vals):
                            cat: SourceCategory = (
                                "build_with_ai"
                                if "bwai" in row.sheet_title.lower()
                                else "devfest"
                            )
                            discovered_slide_urls.append(
                                (s_url, cat, sheet_url)
                            )
                else:
                    stats["sources_status"][status_key] = (
                        "auth_required_using_seed_fallback"
                    )

        # 3b. Korean GDG/GDE Organizer Slack Channel (#organizers, C04E1UAAY)
        if source_filter in ("all", "kr_organizer", "slack"):
            slack_doc = self.slack_parser.parse()
            if slack_doc and slack_doc.threads:
                parsed_slack_docs.append(slack_doc)
                stats["slack_threads_parsed"] += len(slack_doc.threads)
                slack_chunks = self.chunker.chunk_slack_channel(slack_doc)
                collected_chunks.extend(slack_chunks)
                stats["sources_status"]["kr_slack_organizers"] = (
                    f"parsed ({len(slack_doc.threads)} threads, {len(slack_chunks)} chunks)"
                )
                for s_url, s_cat in slack_doc.discovered_slide_urls:
                    discovered_slide_urls.append(
                        (s_url, s_cat, slack_doc.source_url)
                    )
            else:
                stats["sources_status"]["kr_slack_organizers"] = "not_found"

        # 4. Parse all discovered & explicit Google Slides decks (deduplicated by presentation_id)
        stats["slides_discovered"] = len(discovered_slide_urls)
        seen_presentations: set[str] = set()
        for slide_url, category, parent_url in discovered_slide_urls:
            pres_id, _ = parse_slide_url_metadata(slide_url)
            if not pres_id or pres_id in seen_presentations:
                continue
            seen_presentations.add(pres_id)

            deck = self.slides_parser.parse_slide_url(
                url=slide_url, category=category, parent_hub_url=parent_url
            )
            if deck and deck.slides:
                parsed_slide_decks.append(deck)
                stats["slide_decks_parsed"] += 1
                slide_chunks = self.chunker.chunk_slide_deck(deck)
                collected_chunks.extend(slide_chunks)
                stats["sources_status"][f"slide_{pres_id}"] = (
                    f"live_parsed ({len(slide_chunks)} slides)"
                )
            else:
                stats["sources_status"][f"slide_{pres_id}"] = (
                    "auth_required_using_seed_fallback"
                )

        # 5. Merge Seed Knowledge Base (ensures complete coverage even offline / pre-auth)
        if include_seed:
            seed_chunks = self.load_seed_chunks()
            existing_ids = {c.chunk_id for c in collected_chunks}
            for sc in seed_chunks:
                if sc.chunk_id not in existing_ids:
                    collected_chunks.append(sc)
                    stats["seed_chunks_loaded"] += 1

        # 6. Index into Vector Store (Vector RAG) AND Build Knowledge Graph (GraphRAG)
        from community_hub_agent.rag.retriever import get_rag_retriever

        retriever = get_rag_retriever()
        indexed_count = retriever.index_chunks(collected_chunks)
        stats["total_chunks_indexed"] = indexed_count

        if (
            parsed_sheet_docs
            or parsed_slide_decks
            or parsed_hub_pages
            or parsed_slack_docs
        ):
            graph_stats = retriever.knowledge_graph.build_from_sources(
                sheet_docs=parsed_sheet_docs,
                slide_decks=parsed_slide_decks,
                hub_pages=parsed_hub_pages,
                slack_docs=parsed_slack_docs,
            )
            stats["knowledge_graph"] = graph_stats

        # 7. GCP Cloud Sync: GCS Bucket + Vertex AI Search Data Store + Vertex AI RAG Engine
        if upload_to_gcs:
            gcp_sync_report = self.sync_chunks_to_gcp(collected_chunks)
            stats["gcp_sync"] = gcp_sync_report
            stats["gcs_uploaded_files"] = gcp_sync_report.get(
                "gcs_uploaded_files", 0
            )

        return stats

    def sync_chunks_to_gcp(
        self, chunks: list[DocumentChunk] | None = None
    ) -> dict[str, Any]:
        """Provisions GCS Bucket, Vertex AI Search Data Store, and Vertex AI RAG Engine Corpus, and uploads all chunks."""
        from community_hub_agent.rag.retriever import get_rag_retriever

        retriever = get_rag_retriever()
        target_chunks = chunks or list(retriever.local_store.chunks.values())
        report: dict[str, Any] = {
            "project_id": settings.gcp_project,
            "total_chunks": len(target_chunks),
            "gcs_uploaded_files": 0,
            "gcs_bucket": settings.gcs_raw_bucket_name,
            "vertex_ai_search": {},
            "vertex_rag_engine": {},
        }

        if settings.gcs_raw_bucket_name:
            report["gcs_uploaded_files"] = self._upload_chunks_to_gcs(
                target_chunks, settings.gcs_raw_bucket_name
            )

        report["vertex_ai_search"] = retriever.vertex_search.upsert_chunks(
            target_chunks
        )
        report["vertex_rag_engine"] = (
            retriever.vertex_search.sync_to_vertex_rag_engine(target_chunks)
        )
        return report

    def _upload_chunks_to_gcs(
        self, chunks: list[DocumentChunk], bucket_name: str
    ) -> int:
        """Auto-creates the GCS bucket if missing and uploads JSONL + Knowledge Graph for Vertex AI."""
        try:
            from google.cloud import storage

            client = storage.Client(project=settings.gcp_project or None)
            bucket = client.bucket(bucket_name)
            if not bucket.exists():
                logger.info(
                    "Creating GCS bucket gs://%s in %s...",
                    bucket_name,
                    settings.gcp_location or "us-central1",
                )
                bucket = client.create_bucket(
                    bucket_or_name=bucket_name,
                    location=settings.gcp_location or "us-central1",
                )

            jsonl_lines = []
            for chunk in chunks:
                record = {
                    "id": chunk.chunk_id,
                    "structData": {
                        "chunk_id": chunk.chunk_id,
                        "title": chunk.title,
                        "content": chunk.content,
                        "category": chunk.category,
                        "source_type": chunk.source_type,
                        "source_url": chunk.source_url,
                        "metadata": chunk.metadata,
                    },
                }
                jsonl_lines.append(json.dumps(record, ensure_ascii=False))

            uploaded = 0
            blob = bucket.blob("community_hub/community_hub_chunks.jsonl")
            blob.upload_from_string(
                "\n".join(jsonl_lines), content_type="application/jsonl"
            )
            uploaded += 1

            if settings.knowledge_graph_file.exists():
                kg_blob = bucket.blob("community_hub/knowledge_graph.json")
                kg_blob.upload_from_filename(
                    str(settings.knowledge_graph_file),
                    content_type="application/json",
                )
                uploaded += 1

            return uploaded
        except Exception as exc:
            logger.warning("GCS upload skipped or failed: %s", exc)
            return 0

