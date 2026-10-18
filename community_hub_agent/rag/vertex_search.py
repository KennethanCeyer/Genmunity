"""Approach 1: Fully Managed GCP RAG via Vertex AI Search (Agent Builder Data Stores), Vertex AI RAG Engine & Grounding."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from community_hub_agent.config import settings

if TYPE_CHECKING:
    from community_hub_agent.ingestion.models import DocumentChunk

logger = logging.getLogger(__name__)


class VertexAISearchService:
    """Interfaces with Vertex AI Search (Agent Builder Data Store), Vertex AI RAG Engine, and Gemini Grounding."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        data_store_id: str | None = None,
        engine_id: str | None = None,
    ) -> None:
        self.project_id = project_id or settings.gcp_project
        self.location = location or settings.vertex_search_location
        self.data_store_id = data_store_id or settings.vertex_search_data_store_id
        self.engine_id = engine_id or settings.vertex_search_engine_id
        self._runtime_unavailable: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(
            not self._runtime_unavailable
            and self.project_id
            and self.project_id != "your-gcp-project-id"
            and self.data_store_id
            and self.data_store_id != "your-datastore-id"
        )

    @property
    def collection_parent(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/collections/default_collection"
        )

    @property
    def datastore_resource_name(self) -> str:
        return f"{self.collection_parent}/dataStores/{self.data_store_id}"

    @property
    def branch_resource_name(self) -> str:
        return f"{self.datastore_resource_name}/branches/default_branch"

    def _client_options(self):
        from google.api_core.client_options import ClientOptions

        return (
            ClientOptions(
                api_endpoint=f"{self.location}-discoveryengine.googleapis.com"
            )
            if self.location != "global"
            else None
        )

    def ensure_data_store_and_engine(self) -> dict[str, Any]:
        """Auto-provisions the Vertex AI Search Data Store and Search App (Engine) if they do not exist."""
        if not self.is_configured:
            return {
                "status": "skipped",
                "reason": "GOOGLE_CLOUD_PROJECT or VERTEX_SEARCH_DATA_STORE_ID is not set.",
            }

        from google.api_core.exceptions import AlreadyExists, NotFound
        from google.cloud import discoveryengine_v1 as discoveryengine

        client_options = self._client_options()
        ds_client = discoveryengine.DataStoreServiceClient(
            client_options=client_options
        )
        status_info: dict[str, Any] = {
            "project_id": self.project_id,
            "location": self.location,
            "data_store_id": self.data_store_id,
            "datastore_resource": self.datastore_resource_name,
        }

        # 1. Ensure DataStore exists
        try:
            ds = ds_client.get_data_store(name=self.datastore_resource_name)
            status_info["data_store_status"] = "existing"
            status_info["data_store_display_name"] = ds.display_name
        except NotFound:
            logger.info(
                "Creating Vertex AI Search Data Store: %s",
                self.datastore_resource_name,
            )
            data_store = discoveryengine.DataStore(
                display_name="GDG Community Hub RAG Data Store",
                industry_vertical=discoveryengine.IndustryVertical.GENERIC,
                solution_types=[
                    discoveryengine.SolutionType.SOLUTION_TYPE_SEARCH
                ],
                content_config=discoveryengine.DataStore.ContentConfig.NO_CONTENT,
            )
            operation = ds_client.create_data_store(
                request=discoveryengine.CreateDataStoreRequest(
                    parent=self.collection_parent,
                    data_store=data_store,
                    data_store_id=self.data_store_id,
                )
            )
            ds = operation.result(timeout=180)
            status_info["data_store_status"] = "created"
            status_info["data_store_display_name"] = ds.display_name
        except AlreadyExists:
            status_info["data_store_status"] = "existing"

        # 2. Ensure Search Engine (App) exists so it shows in Agent Builder -> Apps and enables Enterprise/LLM search
        if self.engine_id:
            engine_name = f"{self.collection_parent}/engines/{self.engine_id}"
            eng_client = discoveryengine.EngineServiceClient(
                client_options=client_options
            )
            try:
                eng_client.get_engine(name=engine_name)
                status_info["engine_status"] = "existing"
                status_info["engine_resource"] = engine_name
            except NotFound:
                try:
                    logger.info(
                        "Creating Vertex AI Search Engine App: %s", engine_name
                    )
                    engine = discoveryengine.Engine(
                        display_name="GDG Community Hub Search App",
                        solution_type=discoveryengine.SolutionType.SOLUTION_TYPE_SEARCH,
                        industry_vertical=discoveryengine.IndustryVertical.GENERIC,
                        data_store_ids=[self.data_store_id],
                        search_engine_config=discoveryengine.Engine.SearchEngineConfig(
                            search_tier=discoveryengine.SearchTier.SEARCH_TIER_ENTERPRISE,
                            search_add_ons=[
                                discoveryengine.SearchAddOn.SEARCH_ADD_ON_LLM
                            ],
                        ),
                    )
                    op = eng_client.create_engine(
                        request=discoveryengine.CreateEngineRequest(
                            parent=self.collection_parent,
                            engine=engine,
                            engine_id=self.engine_id,
                        )
                    )
                    op.result(timeout=180)
                    status_info["engine_status"] = "created"
                    status_info["engine_resource"] = engine_name
                except Exception as eng_exc:
                    logger.warning(
                        "Search Engine App creation warning (Data Store still usable): %s",
                        eng_exc,
                    )
                    status_info["engine_status"] = f"warning: {eng_exc}"

        return status_info

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> dict[str, Any]:
        """Provisions the Vertex AI Search Data Store (if needed) and imports all chunks via InlineSource."""
        if not self.is_configured:
            return {
                "status": "skipped",
                "reason": "Vertex AI Search is not configured (set GOOGLE_CLOUD_PROJECT).",
            }
        if not chunks:
            return {"status": "empty", "imported_documents": 0}

        try:
            from google.cloud import discoveryengine_v1 as discoveryengine

            provision_info = self.ensure_data_store_and_engine()
            doc_client = discoveryengine.DocumentServiceClient(
                client_options=self._client_options()
            )

            documents: list[discoveryengine.Document] = []
            for chunk in chunks:
                safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", chunk.chunk_id)[:128]
                payload = {
                    "id": safe_id,
                    "chunk_id": chunk.chunk_id,
                    "title": chunk.title,
                    "content": chunk.content,
                    "category": chunk.category,
                    "source_type": chunk.source_type,
                    "source_url": chunk.source_url,
                    "metadata": chunk.metadata,
                }
                documents.append(
                    discoveryengine.Document(
                        id=safe_id,
                        json_data=json.dumps(payload, ensure_ascii=False),
                    )
                )

            imported_total = 0
            failed_total = 0
            batch_size = 100
            for start in range(0, len(documents), batch_size):
                batch = documents[start : start + batch_size]
                request = discoveryengine.ImportDocumentsRequest(
                    parent=self.branch_resource_name,
                    inline_source=discoveryengine.ImportDocumentsRequest.InlineSource(
                        documents=batch
                    ),
                    reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
                )
                operation = doc_client.import_documents(request=request)
                operation.result(timeout=180)
                meta = getattr(operation, "metadata", None)
                if meta and hasattr(meta, "success_count"):
                    imported_total += int(meta.success_count)
                    failed_total += int( getattr(meta, "failure_count", 0))
                else:
                    imported_total += len(batch)

            return {
                "status": "ok",
                "provision": provision_info,
                "imported_documents": imported_total,
                "failed_documents": failed_total,
                "console_url": (
                    f"https://console.cloud.google.com/gen-app-builder/data-stores"
                    f"?project={self.project_id}"
                ),
            }
        except Exception as exc:
            logger.warning("Vertex AI Search document import failed: %s", exc)
            return {
                "status": "error",
                "error": str(exc),
                "datastore": self.datastore_resource_name,
            }

    def sync_to_vertex_rag_engine(
        self,
        chunks: list[DocumentChunk],
        markdown_output_path: Path | None = None,
    ) -> dict[str, Any]:
        """Creates/reuses a Vertex AI RAG Engine Corpus (`vertexai.preview.rag`) and uploads the knowledge base."""
        if not self.project_id or self.project_id == "your-gcp-project-id":
            return {
                "status": "skipped",
                "reason": "GOOGLE_CLOUD_PROJECT is not set.",
            }

        try:
            import vertexai
            from vertexai.preview import rag

            candidate_locations = []
            for loc in [
                settings.gcp_location or "asia-northeast3",
                "asia-northeast3",
                "us-west1",
                "europe-west4",
                "us-central1",
            ]:
                if loc not in candidate_locations:
                    candidate_locations.append(loc)

            corpus_display_name = settings.vertex_rag_corpus_display_name
            target_corpus = None
            active_location = candidate_locations[0]
            last_err: Exception | None = None

            for loc in candidate_locations:
                try:
                    vertexai.init(project=self.project_id, location=loc)
                    for existing in rag.list_corpora():
                        if existing.display_name == corpus_display_name:
                            target_corpus = existing
                            active_location = loc
                            break
                    if target_corpus is None:
                        rag_model = settings.embedding_model
                        if rag_model == "gemini-embedding-2":
                            rag_model = "gemini-embedding-2-preview"
                        embedding_model_config = rag.EmbeddingModelConfig(
                            publisher_model=f"publishers/google/models/{rag_model}"
                        )
                        target_corpus = rag.create_corpus(
                            display_name=corpus_display_name,
                            description=(
                                "GDG/GDE Community Hub RAG & GraphRAG Knowledge Base "
                                "(DevFest, Build with AI, Google Slides, Korean Organizer Sheets)"
                            ),
                            embedding_model_config=embedding_model_config,
                        )
                        active_location = loc
                    break
                except Exception as region_exc:
                    last_err = region_exc
                    logger.info(
                        "RAG Engine in %s unavailable (%s), trying next region...",
                        loc,
                        region_exc,
                    )

            if target_corpus is None and last_err is not None:
                raise last_err

            md_path = markdown_output_path or (
                settings.data_dir / "community_hub_rag_corpus.md"
            )
            md_path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                "# GDG/GDE Community Hub RAG Knowledge Base",
                "",
                f"Total Indexed Chunks: {len(chunks)}",
                "",
            ]
            for chunk in chunks:
                lines.extend(
                    [
                        f"## [{chunk.category.upper()}] {chunk.title} (`{chunk.chunk_id}`)",
                        f"- **Source Type**: `{chunk.source_type}`",
                        f"- **Source URL**: {chunk.source_url}",
                        f"- **Metadata**: `{json.dumps(chunk.metadata, ensure_ascii=False)}`",
                        "",
                        chunk.content,
                        "",
                        "---",
                        "",
                    ]
                )
            md_path.write_text("\n".join(lines), encoding="utf-8")

            rag_file = rag.upload_file(
                corpus_name=target_corpus.name,
                path=str(md_path),
                display_name="gdg_gde_community_hub_knowledge_base.md",
                description="Full DevFest, Build with AI, Google Slides, and Korean Organizer Sheets corpus",
            )
            return {
                "status": "ok",
                "corpus_name": target_corpus.name,
                "corpus_display_name": target_corpus.display_name,
                "uploaded_rag_file": getattr(rag_file, "name", str(md_path)),
                "console_url": (
                    f"https://console.cloud.google.com/vertex-ai/rag"
                    f"?project={self.project_id}"
                ),
            }
        except Exception as exc:
            logger.warning("Vertex AI RAG Engine sync skipped or failed: %s", exc)
            return {
                "status": "error",
                "error": str(exc),
            }

    def search_datastore(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Queries Vertex AI Search Data Store directly via `google-cloud-discoveryengine`."""
        if not self.is_configured:
            logger.debug("Vertex AI Search Data Store is not configured.")
            return []

        try:
            import google.auth
            from google.api_core.client_options import ClientOptions
            from google.cloud import discoveryengine_v1 as discoveryengine

            google.auth.default()
            client_options = (
                ClientOptions(
                    api_endpoint=f"{self.location}-discoveryengine.googleapis.com"
                )
                if self.location != "global"
                else None
            )
            client = discoveryengine.SearchServiceClient(
                client_options=client_options
            )
            serving_config = (
                f"{self.datastore_resource_name}/servingConfigs/default_search"
            )

            content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
                snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                    return_snippet=True
                ),
            )

            request = discoveryengine.SearchRequest(
                serving_config=serving_config,
                query=query,
                page_size=top_k,
                content_search_spec=content_search_spec,
                query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
                    condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO,
                ),
                spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
                    mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO
                ),
            )

            response = client.search(request)
            results: list[dict[str, Any]] = []
            for rank, result in enumerate(response.results, start=1):
                doc_data = (
                    dict(result.document.struct_data)
                    if result.document.struct_data
                    else {}
                )
                if not doc_data and getattr(result.document, "json_data", ""):
                    try:
                        doc_data = json.loads(result.document.json_data)
                    except Exception:
                        doc_data = {}
                derived = (
                    dict(result.document.derived_struct_data)
                    if result.document.derived_struct_data
                    else {}
                )

                snippets: list[str] = []
                for s in derived.get("snippets", []):
                    if isinstance(s, dict) and s.get("snippet"):
                        snippets.append(s["snippet"])
                for seg in derived.get("extractive_segments", []):
                    if isinstance(seg, dict) and seg.get("content"):
                        snippets.append(seg["content"])

                content_text = str(
                    doc_data.get("content", "")
                ) or "\n".join(snippets)
                results.append(
                    {
                        "chunk_id": doc_data.get(
                            "chunk_id", result.document.id
                        ),
                        "title": doc_data.get(
                            "title",
                            derived.get("title", "Vertex AI Search Result"),
                        ),
                        "content": content_text,
                        "category": doc_data.get("category", "general"),
                        "source_type": str(
                            doc_data.get("source_type") or "vertex_ai_search"
                        ),
                        "source_url": doc_data.get(
                            "source_url", derived.get("link", "")
                        ),
                        "score": 1.0 / (rank + 1),
                        "metadata": doc_data.get("metadata", doc_data),
                    }
                )
            return results
        except Exception as exc:
            self._runtime_unavailable = True
            logger.debug("Vertex AI Search query unavailable (falling back to local/custom vector store): %s", exc)
            return []

    def generate_grounded_answer(self, query: str) -> dict[str, Any]:
        """Calls Vertex AI Gemini with VertexAISearch Grounding Tool (Approach 1 Turnkey pattern)."""
        if not self.is_configured:
            return {
                "status": "not_configured",
                "message": (
                    "VERTEX_SEARCH_DATA_STORE_ID 및 GOOGLE_CLOUD_PROJECT가 설정되지 않아 "
                    "로컬/커스텀 Vector RAG 결과를 대신 사용합니다."
                ),
                "datastore": self.datastore_resource_name,
            }

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=settings.gcp_location,
            )
            grounding_tool = types.Tool(
                retrieval=types.Retrieval(
                    vertex_ai_search=types.VertexAISearch(
                        datastore=self.datastore_resource_name
                    )
                )
            )
            response = client.models.generate_content(
                model=settings.root_model,
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[grounding_tool],
                    temperature=0.2,
                ),
            )
            citations: list[dict[str, str]] = []
            if response.candidates:
                gm = getattr(response.candidates[0], "grounding_metadata", None)
                if gm and getattr(gm, "grounding_chunks", None):
                    for gc in gm.grounding_chunks:
                        rc = getattr(gc, "retrieved_context", None)
                        if rc:
                            citations.append(
                                {
                                    "title": getattr(rc, "title", ""),
                                    "uri": getattr(rc, "uri", ""),
                                }
                            )
            return {
                "status": "ok",
                "answer": response.text,
                "citations": citations,
                "datastore": self.datastore_resource_name,
            }
        except Exception as exc:
            logger.warning("Vertex AI Search Grounding call failed: %s", exc)
            return {
                "status": "error",
                "message": str(exc),
                "datastore": self.datastore_resource_name,
            }
