#!/usr/bin/env python3
"""CLI tool to crawl and index DevFest, Build with AI, Google Slides, and Korean Organizer Sheets.

Usage examples:
  # 1. Run ingestion (uses Google Workspace APIs / Cookies if configured + Seed data)
  uv run python scripts/ingest.py --source all

  # 2. Save interactive browser login session for Community Hub (GDG/GDE Google account)
  uv run python scripts/ingest.py --auth-login

  # 3. Run ingestion and upload JSONL to GCS for Vertex AI Search (Approach 1)
  uv run python scripts/ingest.py --source all --upload-gcs
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from community_hub_agent.config import settings
from community_hub_agent.ingestion.pipeline import CommunityHubIngestionPipeline


def save_playwright_login_session() -> None:
    """Opens an interactive browser window for the organizer to log into Google Community Hub."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright가 설치되어 있지 않습니다. `uv add --optional browser playwright && uv run playwright install chromium` 실행 후 다시 시도하세요."
        )
        sys.exit(1)

    settings.playwright_storage_state.parent.mkdir(parents=True, exist_ok=True)
    print(
        f"[Auth Login] 브라우저가 열리면 GDG/GDE 운영진 Google 계정으로 로그인하세요.\n"
        f"대상 URL: {settings.devfest_hub_url}"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(settings.devfest_hub_url)
        input("\n로그인 완료 후 터미널에서 [Enter] 키를 누르면 세션이 저장됩니다...")
        context.storage_state(path=str(settings.playwright_storage_state))
        browser.close()
    print(
        f"[성공] 브라우저 인증 세션이 저장되었습니다: {settings.playwright_storage_state}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest GDG/GDE Community Hub, Google Slides, and Korean Organizer Google Sheets into RAG."
    )
    parser.add_argument(
        "--source",
        default="all",
        choices=["all", "devfest", "build_with_ai", "kr_organizer", "slack"],
        help="Target data source to ingest.",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Optional Cookie header string for authenticated HTTP scraping.",
    )
    parser.add_argument(
        "--upload-gcs",
        "--sync-gcp",
        dest="upload_gcs",
        action="store_true",
        help="Auto-create GCS bucket & Vertex AI Search Data Store / RAG Corpus and upload all chunks.",
    )
    parser.add_argument(
        "--sync-gcp-only",
        action="store_true",
        help="Push already-indexed local chunks (data/indexed_chunks.json) directly to GCP Vertex AI & GCS.",
    )
    parser.add_argument(
        "--auth-login",
        action="store_true",
        help="Launch interactive browser to save Google login state for Community Hub.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.auth_login:
        save_playwright_login_session()
        return

    pipeline = CommunityHubIngestionPipeline(cookie_header=args.cookie)
    if args.sync_gcp_only:
        report = pipeline.sync_chunks_to_gcp()
        print("\n=== GCP Vertex AI Search & GCS Sync Report ===")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    report = pipeline.run_ingestion(
        source_filter=args.source,
        include_seed=True,
        upload_to_gcs=args.upload_gcs,
    )
    print("\n=== GDG/GDE Community Hub RAG Ingestion Report ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

