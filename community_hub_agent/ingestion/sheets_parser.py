"""Google Sheets & Local Excel (.xlsx / .csv) parser for Korean GDG/GDE Organizer data.

Supports:
1. Google Sheets API v4 (fetches all worksheet tabs and rows)
2. HTTP CSV export (`/export?format=csv`) with optional Cookie header
3. Local Excel `.xlsx` fallback (`/Users/jaichang/Downloads/[External] GDG KR Communication.xlsx`
   or `data/raw/gdg_kr_communication.xlsx`), including:
   - Multi-tab parsing across all 11 tabs (`26 DevFest`, `26 IOEX`, `26 BwAI`,
     `25 Year-End Dinner`, `25 DevFest`, `25 IOEX`, `25 BwAI`, `24 DevFest`,
     `24 IOEX`, `24 BwAI`, `26 Active Rate`)
   - Embedded hyperlink target extraction (`cell.hyperlink.target`)
   - Forward-filling (`ffill`) of merged/grouped `Region` and `GDG Chapter` columns
   - Campaign policy & support guideline extraction from pre-header cells
4. Local CSV fallback in `data/raw/`
"""

from __future__ import annotations

import csv
import datetime
import io
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from community_hub_agent.config import settings
from community_hub_agent.ingestion.models import SheetDocument, SheetRowRecord

logger = logging.getLogger(__name__)

SHEET_ID_PATTERN = re.compile(
    r"https?://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]{20,})",
    re.IGNORECASE,
)


def extract_spreadsheet_id(url: str) -> str | None:
    """Extracts spreadsheetId from a Google Sheets URL."""
    match = SHEET_ID_PATTERN.search(url)
    return match.group(1) if match else None


def _clean_header(text: str) -> str:
    """Normalizes multi-line Excel column headers into clean single-line keys."""
    cleaned = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    return cleaned


def _format_cell_value(val: Any, hyperlink: str | None = None) -> str:
    """Formats an openpyxl cell value and merges its hyperlink target if present."""
    if val is None and not hyperlink:
        return ""
    if isinstance(val, datetime.datetime):
        text = val.strftime("%Y-%m-%d")
    elif isinstance(val, datetime.date):
        text = val.strftime("%Y-%m-%d")
    elif isinstance(val, float):
        if val.is_integer():
            text = str(int(val))
        else:
            text = str(val)
    else:
        text = str(val).strip()

    if hyperlink:
        hl = hyperlink.strip()
        if not text or text.lower() == "link":
            return hl
        if hl not in text:
            return f"{text} ({hl})"
    return text


class GoogleSheetsParser:
    """Parses the Korean GDG/GDE Organizer Google Spreadsheet or local .xlsx into structured rows."""

    def __init__(self, cookie_header: str | None = None) -> None:
        self.cookie_header = (
            cookie_header
            if cookie_header is not None
            else settings.community_hub_cookie_header
        )

    def _get_google_credentials(self) -> Any:
        try:
            import os
            import google.auth
            from google.oauth2.credentials import Credentials

            if settings.oauth_token_path.exists():
                return Credentials.from_authorized_user_file(
                    str(settings.oauth_token_path),
                    scopes=[
                        "https://www.googleapis.com/auth/spreadsheets.readonly",
                        "https://www.googleapis.com/auth/drive.readonly",
                    ],
                )
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                creds, _ = google.auth.default(
                    scopes=[
                        "https://www.googleapis.com/auth/spreadsheets.readonly",
                        "https://www.googleapis.com/auth/drive.readonly",
                    ]
                )
                return creds
            return None
        except Exception as exc:
            logger.debug("Google Sheets API credentials not configured: %s", exc)
            return None

    def parse_from_sheets_api(
        self, spreadsheet_id: str, source_url: str
    ) -> SheetDocument | None:
        """Reads all worksheet tabs and rows using Google Sheets API v4."""
        creds = self._get_google_credentials()
        if not creds:
            return None

        try:
            from googleapiclient.discovery import build

            service = build(
                "sheets", "v4", credentials=creds, cache_discovery=False
            )
            meta = (
                service.spreadsheets()
                .get(spreadsheetId=spreadsheet_id, includeGridData=False)
                .execute()
            )
            doc_title = meta.get("properties", {}).get(
                "title", "국내 GDG/GDE 운영진 시트"
            )
            sheet_titles = [
                s.get("properties", {}).get("title", "Sheet1")
                for s in meta.get("sheets", [])
            ]
            if not sheet_titles:
                sheet_titles = ["Sheet1"]

            batch = (
                service.spreadsheets()
                .values()
                .batchGet(spreadsheetId=spreadsheet_id, ranges=sheet_titles)
                .execute()
            )
        except Exception as exc:
            logger.warning(
                "Google Sheets API v4 failed for %s: %s", spreadsheet_id, exc
            )
            return None

        all_rows: list[SheetRowRecord] = []
        for idx, value_range in enumerate(batch.get("valueRanges", [])):
            tab_title = (
                sheet_titles[idx] if idx < len(sheet_titles) else f"Tab_{idx+1}"
            )
            values: list[list[str]] = value_range.get("values", [])
            all_rows.extend(self._matrix_to_records(tab_title, values))

        return SheetDocument(
            spreadsheet_id=spreadsheet_id,
            title=doc_title,
            source_url=source_url,
            rows=all_rows,
        )

    def parse_from_csv_export(
        self, spreadsheet_id: str, source_url: str
    ) -> SheetDocument | None:
        """Fallback parser using Google Sheets `/export?format=csv` endpoint."""
        export_url = (
            f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
        )
        headers = {
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
                        "Spreadsheet %s requires Google login (received login page).",
                        spreadsheet_id,
                    )
                    return None
                csv_text = resp.text.strip()
                if not csv_text or "<html" in csv_text[:200].lower():
                    return None
        except Exception as exc:
            logger.debug("CSV export failed for %s: %s", spreadsheet_id, exc)
            return None

        reader = csv.reader(io.StringIO(csv_text))
        matrix = list(reader)
        rows = self._matrix_to_records("국내 운영진 데이터", matrix)
        return SheetDocument(
            spreadsheet_id=spreadsheet_id,
            title="국내 GDG/GDE 운영진 데이터",
            source_url=source_url,
            rows=rows,
        )

    def parse_from_local_xlsx(
        self, file_path: Path, spreadsheet_id: str, source_url: str
    ) -> SheetDocument | None:
        """Parses the local Excel `.xlsx` file (`[External] GDG KR Communication.xlsx`).

        Handles all worksheet tabs, extracts cell hyperlinks, captures campaign policy
        headers, and forward-fills grouped Region/GDG Chapter rows in `26 Active Rate`.
        """
        if not file_path.exists():
            return None

        try:
            import openpyxl

            wb = openpyxl.load_workbook(str(file_path), data_only=True)
        except Exception as exc:
            logger.warning("Failed to load Excel file %s: %s", file_path, exc)
            return None

        all_rows: list[SheetRowRecord] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            tab_rows = self._parse_xlsx_worksheet(sheet_name, ws)
            all_rows.extend(tab_rows)

        logger.info(
            "Parsed %d structured records across %d tabs from %s",
            len(all_rows),
            len(wb.sheetnames),
            file_path,
        )
        return SheetDocument(
            spreadsheet_id=spreadsheet_id,
            title=f"국내 GDG/GDE 운영진 및 캠페인 커뮤니케이션 시트 ({file_path.name})",
            source_url=source_url,
            rows=all_rows,
        )

    def _parse_xlsx_worksheet(
        self, sheet_name: str, ws: Any
    ) -> list[SheetRowRecord]:
        """Parses an individual openpyxl worksheet based on its layout structure."""
        max_r = min(ws.max_row, 350)
        max_c = min(ws.max_column, 35)

        grid: list[list[str]] = []
        for r in range(1, max_r + 1):
            row_vals: list[str] = []
            for c in range(1, max_c + 1):
                cell = ws.cell(r, c)
                hl = cell.hyperlink.target if cell.hyperlink else None
                row_vals.append(_format_cell_value(cell.value, hl))
            grid.append(row_vals)

        if sheet_name == "26 Active Rate":
            return self._parse_active_rate_tab(sheet_name, grid)
        if sheet_name in ("Home", "GDE", "GDG", "GDGoC"):
            return self._parse_leads_directory_tab(sheet_name, grid)

        # Find the header row (looks for '주최 GDG 챕터명', 'GDG Chapter', 'GDG chapter', 'Date')
        header_row_idx = 0
        for idx, row in enumerate(grid[:10]):
            joined = " ".join(row).lower()
            if (
                "주최 gdg 챕터명" in joined
                or "gdg chapter" in joined
                or ("date" in joined and "gdg" in joined)
            ):
                header_row_idx = idx
                break

        records: list[SheetRowRecord] = []

        # Capture any campaign guideline / support notes above the header row
        if header_row_idx > 0:
            guideline_notes: list[str] = []
            for r_idx in range(header_row_idx):
                for cell_text in grid[r_idx]:
                    if cell_text and len(cell_text.strip()) > 10:
                        guideline_notes.append(cell_text.strip())
            if guideline_notes:
                records.append(
                    SheetRowRecord(
                        sheet_title=sheet_name,
                        row_index=1,
                        values={
                            "구분": "캠페인 운영 가이드 및 지원 조건",
                            "캠페인 탭": sheet_name,
                            "안내사항": " | ".join(guideline_notes),
                        },
                    )
                )

        headers = [
            _clean_header(h) if _clean_header(h) else f"col_{i+1}"
            for i, h in enumerate(grid[header_row_idx])
        ]

        for r_offset, row in enumerate(grid[header_row_idx + 1 :]):
            actual_row_num = header_row_idx + 2 + r_offset
            if not any(cell.strip() for cell in row):
                continue
            # Skip example row `(예시)` in 2026 campaign sheets
            if row[0].strip() == "(예시)" or (
                len(row) > 1 and row[1].strip() == "GDG 독도"
            ):
                continue

            row_dict: dict[str, str] = {"캠페인 탭": sheet_name}
            for col_idx, cell_val in enumerate(row):
                val = cell_val.strip()
                if not val or val == "-":
                    continue
                key = (
                    headers[col_idx]
                    if col_idx < len(headers)
                    else f"col_{col_idx+1}"
                )
                row_dict[key] = val

            # Skip summary-only footer rows that have only a single total number in an unlabelled column
            meaningful_keys = [
                k
                for k in row_dict
                if k != "캠페인 탭" and not k.startswith("col_")
            ]
            if not meaningful_keys:
                continue

            records.append(
                SheetRowRecord(
                    sheet_title=sheet_name,
                    row_index=actual_row_num,
                    values=row_dict,
                )
            )
        return records

    def _parse_active_rate_tab(
        self, sheet_name: str, grid: list[list[str]]
    ) -> list[SheetRowRecord]:
        """Parses the `26 Active Rate` tab with policy header and forward-filled Region/Chapter."""
        records: list[SheetRowRecord] = []

        # Row 1 (index 0) contains the 2026 Active Rate policy
        if grid and grid[0] and grid[0][0].strip():
            records.append(
                SheetRowRecord(
                    sheet_title=sheet_name,
                    row_index=1,
                    values={
                        "구분": "2026 GDG 운영진 활동성(Active Rate) 및 오프보딩 정책",
                        "캠페인 탭": sheet_name,
                        "안내사항": grid[0][0].strip(),
                    },
                )
            )

        # Composite header from Row 4 (index 3) and Row 5 (index 4)
        row4 = grid[3] if len(grid) > 3 else []
        row5 = grid[4] if len(grid) > 4 else []
        max_cols = max(len(row4), len(row5))
        headers: list[str] = []
        for c in range(max_cols):
            h5 = _clean_header(row5[c]) if c < len(row5) else ""
            h4 = _clean_header(row4[c]) if c < len(row4) else ""
            headers.append(h5 or h4 or f"col_{c+1}")

        current_region = ""
        current_chapter = ""

        for r_idx in range(5, len(grid)):
            row = grid[r_idx]
            if not any(cell.strip() for cell in row):
                continue

            # Col 2 (index 1) = Region, Col 3 (index 2) = GDG Chapter, Col 4 (index 3) = Name
            region_val = row[1].strip() if len(row) > 1 else ""
            chapter_val = row[2].strip() if len(row) > 2 else ""
            name_val = row[3].strip() if len(row) > 3 else ""

            if region_val:
                current_region = region_val
            if chapter_val:
                current_chapter = chapter_val

            if not name_val:
                continue

            row_dict: dict[str, str] = {
                "캠페인 탭": sheet_name,
                "Region": current_region,
                "GDG Chapter": current_chapter,
                "Name": name_val,
            }
            for col_idx in range(4, min(len(row), len(headers))):
                val = row[col_idx].strip()
                if val:
                    row_dict[headers[col_idx]] = val

            records.append(
                SheetRowRecord(
                    sheet_title=sheet_name,
                    row_index=r_idx + 1,
                    values=row_dict,
                )
            )
        return records

    def _parse_leads_directory_tab(
        self, sheet_name: str, grid: list[list[str]]
    ) -> list[SheetRowRecord]:
        """Parses the `Home`, `GDE`, `GDG`, and `GDGoC` tabs from `[DevCommunity Leads Only] GDG_GDE_GDGoC List in Korea.xlsx`."""
        records: list[SheetRowRecord] = []
        if not grid:
            return records

        if sheet_name == "Home":
            notes = [
                row[0].strip()
                for row in grid
                if row and row[0].strip()
            ]
            if notes:
                records.append(
                    SheetRowRecord(
                        sheet_title="Home",
                        row_index=1,
                        values={
                            "구분": "국내 GDG/GDE/GDGoC 리드 디렉토리 안내 및 소통 가이드",
                            "캠페인 탭": "Home",
                            "안내사항": " | ".join(notes),
                        },
                    )
                )
            return records

        headers = [
            _clean_header(h) if _clean_header(h) else f"col_{i+1}"
            for i, h in enumerate(grid[0])
        ]
        current_group = ""  # Forward-filled 분야 (GDE), Chapter (GDG), or Class (GDGoC)

        for r_idx in range(1, len(grid)):
            row = grid[r_idx]
            if not any(cell.strip() for cell in row):
                continue

            first_col = row[0].strip() if len(row) > 0 else ""
            if first_col.startswith("*"):
                continue
            if first_col:
                current_group = first_col

            # Check if row has a valid person name in col 2 or col 3 or col 4
            col2 = row[1].strip() if len(row) > 1 else ""
            col3 = row[2].strip() if len(row) > 2 else ""
            col4 = row[3].strip() if len(row) > 3 else ""
            if not (col2 or col3 or col4):
                continue

            row_dict: dict[str, str] = {"디렉토리 탭": sheet_name}
            if current_group and headers:
                row_dict[headers[0]] = current_group

            for col_idx in range(1, min(len(row), len(headers))):
                val = row[col_idx].strip()
                if val and not headers[col_idx].startswith("col_"):
                    row_dict[headers[col_idx]] = val

            if len(row_dict) > 1:
                records.append(
                    SheetRowRecord(
                        sheet_title=sheet_name,
                        row_index=r_idx + 1,
                        values=row_dict,
                    )
                )
        return records

    def parse_from_local_csv(
        self, file_path: Path, spreadsheet_id: str, source_url: str
    ) -> SheetDocument | None:
        """Parses a local exported `.csv` file for the Korean Organizer Sheet."""
        if not file_path.exists():
            return None
        csv_text = file_path.read_text(encoding="utf-8").strip()
        if not csv_text:
            return None
        reader = csv.reader(io.StringIO(csv_text))
        matrix = list(reader)
        rows = self._matrix_to_records(file_path.stem, matrix)
        return SheetDocument(
            spreadsheet_id=spreadsheet_id,
            title="국내 GDG/GDE 운영진 데이터 (Local CSV)",
            source_url=source_url,
            rows=rows,
        )

    @staticmethod
    def _matrix_to_records(
        sheet_title: str, matrix: list[list[str]]
    ) -> list[SheetRowRecord]:
        if not matrix:
            return []
        headers = [
            h.strip() if h.strip() else f"col_{i+1}"
            for i, h in enumerate(matrix[0])
        ]
        records: list[SheetRowRecord] = []
        for row_idx, row in enumerate(matrix[1:], start=2):
            if not any(cell.strip() for cell in row):
                continue
            row_dict: dict[str, str] = {}
            for col_idx, cell_val in enumerate(row):
                key = (
                    headers[col_idx]
                    if col_idx < len(headers)
                    else f"col_{col_idx+1}"
                )
                if cell_val.strip():
                    row_dict[key] = cell_val.strip()
            if row_dict:
                records.append(
                    SheetRowRecord(
                        sheet_title=sheet_title,
                        row_index=row_idx,
                        values=row_dict,
                    )
                )
        return records

    def parse_sheet_url(self, url: str) -> SheetDocument | None:
        """Orchestrates parsing a Google Sheets URL across:
        1. Google Sheets API v4
        2. HTTP CSV Export
        3. Local Excel `.xlsx` fallback
        4. Local CSV Fallback
        """
        spreadsheet_id = extract_spreadsheet_id(url) or "gdg_kr_communication"

        # 1. Try Google Sheets API v4
        doc = self.parse_from_sheets_api(spreadsheet_id, url)
        if doc and doc.rows:
            logger.info(
                "Parsed %d rows via Sheets API for %s",
                len(doc.rows),
                spreadsheet_id,
            )
            return doc

        # 2. Try Multi-Tab Local Excel (.xlsx) (preserves all tabs, hyperlinks, and merged headers)
        raw_dir = settings.data_dir / "raw"
        if "1tC31_8IuWH" in spreadsheet_id or "leads" in url.lower():
            xlsx_candidates = [
                raw_dir / "gdg_gde_gdgoc_list_korea.xlsx",
                settings.kr_leads_xlsx_path,
                raw_dir / f"{spreadsheet_id}.xlsx",
            ]
        else:
            xlsx_candidates = [
                raw_dir / "gdg_kr_communication.xlsx",
                settings.kr_organizer_xlsx_path,
                raw_dir / f"{spreadsheet_id}.xlsx",
            ]
        for xlsx_path in xlsx_candidates:
            if xlsx_path.exists():
                doc = self.parse_from_local_xlsx(xlsx_path, spreadsheet_id, url)
                if doc and doc.rows:
                    logger.info(
                        "Parsed %d rows from local Excel %s",
                        len(doc.rows),
                        xlsx_path,
                    )
                    return doc

        # 3. Try HTTP CSV Export (single-tab fallback)
        doc = self.parse_from_csv_export(spreadsheet_id, url)
        if doc and doc.rows:
            logger.info(
                "Parsed %d rows via CSV export for %s",
                len(doc.rows),
                spreadsheet_id,
            )
            return doc

        # 4. Try Local CSV Fallback
        for candidate in (
            raw_dir / f"{spreadsheet_id}.csv",
            raw_dir / "kr_organizer_sheet.csv",
        ):
            doc = self.parse_from_local_csv(candidate, spreadsheet_id, url)
            if doc and doc.rows:
                logger.info(
                    "Parsed %d rows from local CSV %s",
                    len(doc.rows),
                    candidate,
                )
                return doc

        return None
