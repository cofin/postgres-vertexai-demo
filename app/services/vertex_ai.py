"""Vertex AI integration service for embeddings and chat."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, NoReturn, overload

import structlog
from google import genai

from app.lib.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger()


class VertexAIService:
    """Vertex AI service for embeddings and chat completions."""

    def __init__(self, cache_service: object | None = None) -> None:
        """Initialize Vertex AI service.

        Args:
            cache_service: Optional cache service for embedding caching
        """
        from google import genai
        from google.cloud import aiplatform

        self.settings = get_settings()
        self._genai_client: genai.Client | None = None
        self._cache_service = cache_service

        # Initialize Vertex AI
        if self.settings.vertex_ai.PROJECT_ID:
            # Lazy import Google Cloud libraries

            aiplatform.init(
                project=self.settings.vertex_ai.PROJECT_ID,
                location=self.settings.vertex_ai.LOCATION,
            )
            # Initialize Google GenAI client
            self._genai_client = genai.Client()
            self._initialized = True
            logger.info(
                "Vertex AI initialized (private deployment)",
                project=self.settings.vertex_ai.PROJECT_ID,
                location=self.settings.vertex_ai.LOCATION,
            )
        else:
            self._initialized = False
            self._genai_client = None
            logger.warning("Vertex AI not initialized: PROJECT_ID not configured")

    def _handle_embedding_error(self, batch_index: int | None = None) -> NoReturn:
        if batch_index is not None:
            msg = f"No embeddings returned from Vertex AI for batch starting at index {batch_index}"
            raise ValueError(msg)
        msg = "No embeddings returned from API"
        raise ValueError(msg)

    async def _get_batch_text_embeddings(self, texts: list[str], model_name: str) -> list[list[float]]:
        """Handle batch embedding generation with rate limiting."""
        if not texts:
            return []

        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        batch_size = 5
        embeddings = []

        for i in range(0, len(texts), batch_size):
            if i > 0:
                await asyncio.sleep(1)  # Rate limiting

            batch = texts[i : i + batch_size]
            response = await self._genai_client.aio.models.embed_content(model=model_name, contents=batch)

            if not response.embeddings:
                self._handle_embedding_error(batch_index=i)

            batch_embeddings = [list(e.values) for e in response.embeddings if e.values is not None]
            embeddings.extend(batch_embeddings)

        logger.debug(
            "Generated batch embeddings",
            batch_count=len(texts),
            embedding_dimensions=len(embeddings[0]) if embeddings else 0,
            model=model_name,
        )
        return embeddings

    @overload
    async def get_text_embedding(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float]: ...

    @overload
    async def get_text_embedding(
        self,
        text: list[str],
        model: str | None = None,
    ) -> list[list[float]]: ...

    async def get_text_embedding(
        self,
        text: str | list[str],
        model: str | None = None,
    ) -> list[float] | list[list[float]]:
        """Generate text embedding(s) using Vertex AI."""
        if not self._initialized or not self._genai_client:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        model_name = model or self.settings.vertex_ai.EMBEDDING_MODEL

        try:
            if isinstance(text, list):
                return await self._get_batch_text_embeddings(text, model_name)

            # At this point, text must be str (not list)
            if not isinstance(text, str):
                msg = "Expected string input for single embedding"
                raise TypeError(msg)

            # Check cache first if available
            if self._cache_service and self.settings.cache.EMBEDDING_CACHE_ENABLED:
                cached = await self._cache_service.get_cached_embedding(text, model_name)
                if cached:
                    logger.debug(
                        "Retrieved cached embedding",
                        text_length=len(text),
                        embedding_dimensions=len(cached.embedding),
                        model=model_name,
                        hit_count=cached.hit_count,
                    )
                    return cached.embedding

            # Generate new embedding
            embedding = await self._get_embedding_async(text, model_name)

            # Cache the result if cache service is available
            if self._cache_service and self.settings.cache.EMBEDDING_CACHE_ENABLED:
                try:
                    await self._cache_service.set_cached_embedding(text, embedding, model_name)
                    logger.debug("Cached new embedding", text_length=len(text), model=model_name)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Failed to cache embedding", error=str(e))

        except Exception as e:
            logger.exception("Failed to generate embedding", model=model_name, error=str(e))
            msg = f"Failed to generate embedding: {e}"
            raise ValueError(msg) from e
        else:
            return embedding

    async def generate_chat_response_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming chat response using Vertex AI.

        Args:
            messages: List of chat messages with 'role' and 'content'
            model: Optional model override
            temperature: Response temperature (0.0-1.0)
            max_output_tokens: Maximum response tokens

        Yields:
            Text chunks from the streaming response

        Raises:
            RuntimeError: If Vertex AI not initialized
            ValueError: If streaming fails
        """
        if not self._initialized:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        model_name = model or self.settings.vertex_ai.CHAT_MODEL

        try:
            async for chunk in self._generate_chat_response_stream_async(
                messages,
                model_name,
                temperature,
                max_output_tokens,
            ):
                yield chunk

        except Exception as e:
            logger.exception(
                "Failed to generate streaming chat response",
                message_count=len(messages),
                model=model_name,
                error=str(e),
            )
            msg = f"Failed to generate streaming chat response: {e}"
            raise ValueError(msg) from e

    async def _generate_chat_response_stream_async(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Asynchronous streaming chat response generation using Google GenAI SDK."""
        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        # Convert messages to Google GenAI format
        formatted_messages = []
        for message in messages:
            role = "user" if message["role"] == "user" else "model"
            formatted_messages.append({"role": role, "parts": [{"text": message["content"]}]})

        # Generate streaming response using Google GenAI SDK
        async for chunk in await self._genai_client.aio.models.generate_content_stream(
            model=model,
            contents=formatted_messages,
            config=genai.types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ),
        ):
            # Extract text from chunk
            if hasattr(chunk, "candidates") and chunk.candidates:
                candidate = chunk.candidates[0]
                if (
                    hasattr(candidate, "content")
                    and candidate.content
                    and hasattr(candidate.content, "parts")
                    and candidate.content.parts
                ):
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            yield part.text

    async def _get_embedding_async(self, text: str, model: str) -> list[float]:
        """Asynchronous embedding generation using Google GenAI SDK."""
        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        response = await self._genai_client.aio.models.embed_content(
            model=model,
            contents=text,
        )
        if not response.embeddings or len(response.embeddings) == 0:
            self._handle_embedding_error()

        # At this point response.embeddings is guaranteed to exist and have at least one element
        first_embedding = response.embeddings[0]
        embedding_values = first_embedding.values
        if embedding_values is None:
            self._handle_embedding_error()

        # At this point embedding_values is guaranteed to be not None
        return list(embedding_values)

    @property
    def is_initialized(self) -> bool:
        """Check if Vertex AI is initialized."""
        return self._initialized

    def get_embedding_dimensions(self) -> int:
        """Get embedding dimensions for current model."""
        return self.settings.vertex_ai.EMBEDDING_DIMENSIONS
