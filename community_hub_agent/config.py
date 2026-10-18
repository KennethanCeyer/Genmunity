"""Configuration module for the GDG/GDE Community Hub ADK & A2A Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)
os.environ.setdefault("NO_GCE_CHECK", "true")

RagMode = Literal["hybrid", "custom", "vertex_search"]
VectorBackend = Literal["local", "pgvector", "vertex_vector_search"]


@dataclass
class AgentSettings:
    """Centralized settings loaded from environment variables."""

    # Project & Model Settings
    gcp_project: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", "")
    )
    gcp_location: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    use_vertexai: bool = field(
        default_factory=lambda: os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").upper()
        == "TRUE"
    )
    root_model: str = field(
        default_factory=lambda: os.getenv("ADK_ROOT_MODEL", "gemini-2.5-flash")
    )
    sub_model: str = field(
        default_factory=lambda: os.getenv("ADK_SUB_MODEL", "gemini-2.5-flash")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
    )

    # RAG Architecture Mode:
    # - "hybrid": Uses both Vertex AI Search (if configured) and Custom Vector Store
    # - "custom": Approach 2 - Modular Custom RAG Pipeline (Embeddings + Vector DB)
    # - "vertex_search": Approach 1 - Fully Managed Vertex AI Search (Agent Builder)
    rag_mode: RagMode = field(
        default_factory=lambda: os.getenv("RAG_MODE", "hybrid")  # type: ignore[return-value]
    )

    # Approach 1: Vertex AI Search (Agent Builder Data Store) & Vertex AI RAG Engine
    vertex_search_data_store_id: str = field(
        default_factory=lambda: os.getenv(
            "VERTEX_SEARCH_DATA_STORE_ID", "gdg-community-hub-datastore"
        )
    )
    vertex_search_engine_id: str = field(
        default_factory=lambda: os.getenv(
            "VERTEX_SEARCH_ENGINE_ID", "gdg-community-hub-search-app"
        )
    )
    vertex_search_location: str = field(
        default_factory=lambda: os.getenv("VERTEX_SEARCH_LOCATION", "global")
    )
    vertex_rag_corpus_display_name: str = field(
        default_factory=lambda: os.getenv(
            "VERTEX_RAG_CORPUS_DISPLAY_NAME", "gdg-community-hub-rag-corpus"
        )
    )
    gcs_raw_bucket_name: str = field(
        default_factory=lambda: os.getenv(
            "GCS_RAW_BUCKET_NAME",
            f"{os.getenv('GOOGLE_CLOUD_PROJECT', '')}-gdg-community-hub-rag"
            if os.getenv("GOOGLE_CLOUD_PROJECT", "")
            and os.getenv("GOOGLE_CLOUD_PROJECT", "") != "your-gcp-project-id"
            else "",
        )
    )

    # Approach 2: Modular Custom RAG Vector Backend
    vector_backend: VectorBackend = field(
        default_factory=lambda: os.getenv("VECTOR_BACKEND", "local")  # type: ignore[return-value]
    )
    pgvector_connection_string: str = field(
        default_factory=lambda: os.getenv("PGVECTOR_CONNECTION_STRING", "")
    )
    pgvector_table_name: str = field(
        default_factory=lambda: os.getenv(
            "PGVECTOR_TABLE_NAME", "community_hub_chunks"
        )
    )
    vertex_vector_index_endpoint: str = field(
        default_factory=lambda: os.getenv("VERTEX_VECTOR_INDEX_ENDPOINT", "")
    )
    vertex_vector_deployed_index_id: str = field(
        default_factory=lambda: os.getenv(
            "VERTEX_VECTOR_DEPLOYED_INDEX_ID", "community_hub_deployed_index"
        )
    )

    # Target Data Sources
    devfest_hub_url: str = field(
        default_factory=lambda: os.getenv(
            "DEVFEST_HUB_URL",
            "https://developers.google.com/community/community-hub/event-series/devfest",
        )
    )
    build_with_ai_hub_url: str = field(
        default_factory=lambda: os.getenv(
            "BUILD_WITH_AI_HUB_URL",
            "https://developers.google.com/community/community-hub/event-series/build-with-ai?hl=ko",
        )
    )
    build_with_ai_slide_url: str = field(
        default_factory=lambda: os.getenv(
            "BUILD_WITH_AI_SLIDE_URL",
            "https://docs.google.com/presentation/d/1CiGLGl91Nh_6kZOxeoHcH9hblmdx2Rt0oF5qX6jjEwE/edit?usp=sharing&resourcekey=0-x_2s2Y1o88-1mNOmoQipTA",
        )
    )
    kr_organizer_sheet_url: str = field(
        default_factory=lambda: os.getenv(
            "KR_ORGANIZER_SHEET_URL",
            "https://docs.google.com/spreadsheets/d/146hMwkpdORd9njiWo2Yg6yZ7X40igZ3EiIk_kO0PJ34/edit?usp=sharing",
        )
    )
    kr_organizer_xlsx_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "KR_ORGANIZER_XLSX_PATH",
                "/Users/jaichang/Downloads/[External] GDG KR Communication.xlsx",
            )
        )
    )
    kr_leads_sheet_url: str = field(
        default_factory=lambda: os.getenv(
            "KR_LEADS_SHEET_URL",
            "https://docs.google.com/spreadsheets/d/1tC31_8IuWH-2TIeX0t84nyRI0YyaBSI52n97acG32-c/edit?usp=sharing",
        )
    )
    kr_leads_xlsx_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "KR_LEADS_XLSX_PATH",
                "/Users/jaichang/Downloads/[DevCommunity Leads Only] GDG_GDE_GDGoC List in Korea.xlsx",
            )
        )
    )
    kr_slack_channel_url: str = field(
        default_factory=lambda: os.getenv(
            "KR_SLACK_CHANNEL_URL",
            "https://gdgkr.slack.com/archives/C04E1UAAY",
        )
    )
    kr_slack_export_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "KR_SLACK_EXPORT_PATH",
                str(
                    BASE_DIR
                    / "data"
                    / "raw"
                    / "slack_gdgkr_organizers_C04E1UAAY.json"
                ),
            )
        )
    )

    # Auth & Storage Paths
    oauth_token_path: Path = field(
        default_factory=lambda: BASE_DIR
        / os.getenv("GOOGLE_OAUTH_TOKEN_PATH", ".auth/google_token.json")
    )
    playwright_storage_state: Path = field(
        default_factory=lambda: BASE_DIR
        / os.getenv("PLAYWRIGHT_STORAGE_STATE", ".auth/storage_state.json")
    )
    community_hub_cookie_header: str = field(
        default_factory=lambda: os.getenv("COMMUNITY_HUB_COOKIE_HEADER", "")
    )
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")
    seed_file: Path = field(
        default_factory=lambda: BASE_DIR / "data" / "seed" / "community_hub_seed.json"
    )
    local_index_file: Path = field(
        default_factory=lambda: BASE_DIR / "data" / "indexed_chunks.json"
    )
    knowledge_graph_file: Path = field(
        default_factory=lambda: BASE_DIR / "data" / "knowledge_graph.json"
    )

    # A2A Server Settings
    a2a_host: str = field(default_factory=lambda: os.getenv("A2A_HOST", "0.0.0.0"))
    a2a_port: int = field(
        default_factory=lambda: int(os.getenv("A2A_PORT", "8001"))
    )
    a2a_public_url: str = field(
        default_factory=lambda: os.getenv("A2A_PUBLIC_URL", "http://localhost:8001")
    )


settings = AgentSettings()
