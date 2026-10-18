"""Vertex AI / Gemini Embeddings service with deterministic local multilingual fallback."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Sequence

import numpy as np

from community_hub_agent.config import settings

logger = logging.getLogger(__name__)


from concurrent.futures import ThreadPoolExecutor


class EmbeddingService:
    """Generates embeddings using `gemini-embedding-2` (Vertex AI / Gemini API) with local fallback."""

    def __init__(self, model_name: str | None = None, dimension: int = 768) -> None:
        self.model_name = model_name or settings.embedding_model
        self.dimension = dimension
        self._client = None
        self._client_unavailable = False

    @staticmethod
    def _is_gemini_embedding_2(model_name: str) -> bool:
        return "gemini-embedding-2" in model_name

    def format_document(self, title: str | None, content: str) -> str:
        """Formats a document chunk using the asymmetric retrieval template for `gemini-embedding-2`."""
        clean_title = (title or "").strip() or "none"
        if self._is_gemini_embedding_2(self.model_name):
            return f"title: {clean_title} | text: {content}"
        return f"{clean_title}\n{content}" if title else content

    def format_query(self, query: str) -> str:
        """Formats a search query using the asymmetric retrieval task instruction for `gemini-embedding-2`."""
        if self._is_gemini_embedding_2(self.model_name) and not query.startswith(
            "task:"
        ):
            return f"task: search result | query: {query}"
        return query

    def _prepare_text_for_model(
        self, text: str, model_to_use: str, is_query: bool = False
    ) -> str:
        if not self._is_gemini_embedding_2(model_to_use):
            return text
        if text.startswith("task:") or text.startswith("title:"):
            return text
        if is_query:
            return f"task: search result | query: {text}"
        if "\n" in text:
            first_line, rest = text.split("\n", 1)
            return f"title: {first_line.strip() or 'none'} | text: {rest}"
        return f"title: none | text: {text}"

    def _get_genai_client(self):
        if self._client_unavailable:
            return None
        if self._client is not None:
            return self._client

        api_key = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        has_real_key = bool(api_key and api_key != "your-gemini-api-key")
        has_vertex = bool(
            settings.use_vertexai
            and settings.gcp_project
            and settings.gcp_project != "your-gcp-project-id"
        )
        if not (has_real_key or has_vertex):
            self._client_unavailable = True
            return None

        try:
            from google import genai

            if has_vertex:
                import google.auth

                google.auth.default()
                # Vertex AI serves stable `gemini-embedding-2` on `global` and `gemini-embedding-2-preview` on `us-central1`
                if self.model_name == "gemini-embedding-2":
                    embed_location = os.getenv("EMBEDDING_LOCATION", "global")
                elif self.model_name == "gemini-embedding-2-preview":
                    embed_location = os.getenv("EMBEDDING_LOCATION", "us-central1")
                else:
                    embed_location = os.getenv(
                        "EMBEDDING_LOCATION", settings.gcp_location
                    )
                self._client = genai.Client(
                    vertexai=True,
                    project=settings.gcp_project,
                    location=embed_location,
                )
            else:
                self._client = genai.Client(vertexai=False, api_key=api_key)
            return self._client
        except Exception as exc:
            logger.debug("GenAI embedding client init skipped: %s", exc)
            self._client_unavailable = True
            return None

    def _normalize_vector(self, values: Sequence[float]) -> list[float]:
        arr = np.asarray(values, dtype=np.float32)
        norm = float(np.linalg.norm(arr))
        if norm > 0 and abs(norm - 1.0) > 1e-3:
            arr = arr / norm
        return arr.tolist()

    def embed_texts(
        self, texts: Sequence[str], *, is_query: bool = False
    ) -> list[list[float]]:
        """Embeds a batch of texts via `gemini-embedding-2` (Vertex AI / Gemini API) or local fallback."""
        if not texts:
            return []

        client = self._get_genai_client()
        if client is not None:
            try:
                from google.genai import types

                model_to_use = self.model_name
                if not settings.use_vertexai and "text-embedding" in model_to_use:
                    model_to_use = "gemini-embedding-2"

                embed_config = types.EmbedContentConfig(
                    output_dimensionality=self.dimension
                )

                if self._is_gemini_embedding_2(model_to_use):
                    prepared = [
                        self._prepare_text_for_model(t, model_to_use, is_query=is_query)
                        for t in texts
                    ]

                    def _embed_single(item: str) -> list[float]:
                        resp = client.models.embed_content(
                            model=model_to_use,
                            contents=item,
                            config=embed_config,
                        )
                        if resp and resp.embeddings:
                            return self._normalize_vector(resp.embeddings[0].values)
                        raise RuntimeError("Empty embedding response")

                    if len(prepared) == 1:
                        return [_embed_single(prepared[0])]
                    with ThreadPoolExecutor(
                        max_workers=min(8, len(prepared))
                    ) as executor:
                        return list(executor.map(_embed_single, prepared))

                all_vectors: list[list[float]] = []
                batch_size = 8
                for idx in range(0, len(texts), batch_size):
                    batch = list(texts[idx : idx + batch_size])
                    resp = client.models.embed_content(
                        model=model_to_use,
                        contents=batch,
                        config=embed_config,
                    )
                    if resp and resp.embeddings:
                        all_vectors.extend(
                            self._normalize_vector(e.values) for e in resp.embeddings
                        )
                if len(all_vectors) == len(texts):
                    return all_vectors
            except Exception as exc:
                logger.warning(
                    "Cloud embedding API failed (%s); using local multilingual fallback.",
                    exc,
                )
                self._client_unavailable = True

        return [self._local_deterministic_embedding(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """Embeds a single search query with asymmetric task instruction."""
        formatted_query = self.format_query(query)
        res = self.embed_texts([formatted_query], is_query=True)
        return res[0] if res else [0.0] * self.dimension

    def _local_deterministic_embedding(self, text: str) -> list[float]:
        """Feature-hashing multilingual n-gram embedding for instant offline & test execution."""
        vec = np.zeros(self.dimension, dtype=np.float32)
        normalized = text.lower()
        # Extract word tokens (Korean + English + numbers) and character bigrams/trigrams
        words = re.findall(r"[가-힣a-z0-9_]+", normalized)
        features: list[tuple[str, float]] = [(w, 2.0) for w in words]
        compact = "".join(words)
        for n in (2, 3):
            for i in range(max(0, len(compact) - n + 1)):
                features.append((compact[i : i + n], 1.0))

        for token, weight in features:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[idx] += sign * weight

        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec.tolist()
