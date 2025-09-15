"""Vertex AI integration service for embeddings and chat."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from google import genai
from google.cloud import aiplatform

from app.lib.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

logger = structlog.get_logger()


class VertexAIService:
    """Vertex AI service for embeddings and chat completions."""

    def __init__(self) -> None:
        """Initialize Vertex AI service."""
        self.settings = get_settings()
        self._genai_client: genai.Client | None

        # Initialize Vertex AI
        if self.settings.vertex_ai.PROJECT_ID:
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

    async def get_text_embedding(self, text: str, model: str | None = None) -> list[float]:
        """Generate text embedding using Vertex AI.

        Args:
            text: Text to embed
            model: Optional model override

        Returns:
            Embedding vector

        Raises:
            RuntimeError: If Vertex AI not initialized
            ValueError: If embedding generation fails
        """
        if not self._initialized:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        model_name = model or self.settings.vertex_ai.EMBEDDING_MODEL

        try:
            embedding = await self._get_embedding_async(text, model_name)

            logger.debug(
                "Generated embedding",
                text_length=len(text),
                embedding_dimensions=len(embedding),
                model=model_name,
            )

        except Exception as e:
            logger.exception(
                "Failed to generate embedding",
                text=text[:100] + "..." if len(text) > 100 else text,  # noqa: PLR2004
                model=model_name,
                error=str(e),
            )
            msg = f"Failed to generate embedding: {e}"
            raise ValueError(msg) from e
        else:
            return embedding

    async def get_batch_embeddings(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Optional model override

        Returns:
            List of embedding vectors

        Raises:
            RuntimeError: If Vertex AI not initialized
            ValueError: If embedding generation fails
        """
        if not self._initialized:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        if not texts:
            return []

        model_name = model or self.settings.vertex_ai.EMBEDDING_MODEL

        try:
            embeddings = await self._get_batch_embeddings_async(texts, model_name)

            logger.debug(
                "Generated batch embeddings",
                count=len(texts),
                embedding_dimensions=len(embeddings[0]) if embeddings else 0,
                model=model_name,
            )

        except Exception as e:
            logger.exception(
                "Failed to generate batch embeddings",
                count=len(texts),
                model=model_name,
                error=str(e),
            )
            msg = f"Failed to generate batch embeddings: {e}"
            raise ValueError(msg) from e
        else:
            return embeddings

    async def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 1024,
    ) -> str:
        """Generate chat response using Vertex AI.

        Args:
            messages: List of chat messages with 'role' and 'content'
            model: Optional model override
            temperature: Response temperature (0.0-1.0)
            max_output_tokens: Maximum response tokens

        Returns:
            Generated response text

        Raises:
            RuntimeError: If Vertex AI not initialized
            ValueError: If response generation fails
        """
        if not self._initialized:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        model_name = model or self.settings.vertex_ai.CHAT_MODEL

        try:
            response = await self._generate_chat_response_async(
                messages, model_name, temperature, max_output_tokens
            )

            logger.debug(
                "Generated chat response",
                message_count=len(messages),
                response_length=len(response),
                model=model_name,
            )

        except Exception as e:
            logger.exception(
                "Failed to generate chat response",
                message_count=len(messages),
                model=model_name,
                error=str(e),
            )
            msg = f"Failed to generate chat response: {e}"
            raise ValueError(msg) from e
        else:
            return response

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
                messages, model_name, temperature, max_output_tokens
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
                if (hasattr(candidate, "content") and candidate.content and
                    hasattr(candidate.content, "parts") and candidate.content.parts):
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
            msg = "No embeddings returned from API"
            raise ValueError(msg)

        embedding_values = response.embeddings[0].values
        if embedding_values is None:
            msg = "Embedding values are None"
            raise ValueError(msg)
        return list(embedding_values)

    async def _get_batch_embeddings_async(self, texts: Sequence[str], model: str) -> list[list[float]]:
        """Asynchronous batch embedding generation using Google GenAI SDK."""
        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        # Google GenAI SDK supports batch embedding in a single call
        response = await self._genai_client.aio.models.embed_content(
            model=model,
            contents=list(texts),
        )

        # Extract embedding values from the response
        if not response.embeddings or len(response.embeddings) == 0:
            msg = "No embeddings returned from API"
            raise ValueError(msg)

        result = []
        for embedding in response.embeddings:
            if embedding.values is None:
                msg = "Embedding values are None"
                raise ValueError(msg)
            result.append(list(embedding.values))
        return result

    async def _generate_chat_response_async(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Asynchronous chat response generation using Google GenAI SDK."""
        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        # Convert messages to Google GenAI format
        formatted_messages = []
        for message in messages:
            role = "user" if message["role"] == "user" else "model"
            formatted_messages.append({"role": role, "parts": [{"text": message["content"]}]})

        # Generate response using Google GenAI SDK with proper async client
        response = await self._genai_client.aio.models.generate_content(
            model=model,
            contents=formatted_messages,
            config=genai.types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ),
        )

        # Extract text from response
        if not response.candidates or len(response.candidates) == 0:
            msg = "No candidates returned from API"
            raise ValueError(msg)

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts or len(candidate.content.parts) == 0:
            msg = "No content parts in response"
            raise ValueError(msg)

        text_content = candidate.content.parts[0].text
        if text_content is None:
            msg = "Text content is None"
            raise ValueError(msg)
        return text_content.strip()

    @property
    def is_initialized(self) -> bool:
        """Check if Vertex AI is initialized."""
        return self._initialized

    def get_embedding_dimensions(self) -> int:
        """Get embedding dimensions for current model."""
        return self.settings.vertex_ai.EMBEDDING_DIMENSIONS

    async def create_cache(
        self,
        contents: list[dict[str, str]],
        model: str | None = None,
        display_name: str | None = None,
        ttl_seconds: int | None = None,
        system_instruction: str | None = None,
    ) -> str:
        """Create a context cache for frequently used content.

        Args:
            contents: List of content to cache with role and text
            model: Model to use for caching (defaults to chat model)
            display_name: Optional display name for the cache
            ttl_seconds: Time to live in seconds (default: 1 hour)
            system_instruction: Optional system instruction

        Returns:
            Cache ID that can be used in subsequent requests

        Raises:
            RuntimeError: If Vertex AI not initialized
            ValueError: If cache creation fails
        """
        if not self._initialized:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        model_name = model or self.settings.vertex_ai.CHAT_MODEL
        cache_ttl = ttl_seconds or self.settings.vertex_ai.CACHE_TTL_SECONDS
        cache_name = display_name or f"{self.settings.vertex_ai.CACHE_PREFIX}-{int(time.time())}"

        try:
            # Convert contents to proper format
            formatted_contents = []
            for content in contents:
                role = "user" if content["role"] == "user" else "model"
                formatted_contents.append({"role": role, "parts": [{"text": content["content"]}]})

            # Create cache config
            config_kwargs = {
                "contents": formatted_contents,
                "display_name": cache_name,
                "ttl": f"{cache_ttl}s",
            }

            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            # Create the cache
            cache = await self._genai_client.aio.caches.create(
                model=model_name,
                config=genai.types.CreateCachedContentConfig(**config_kwargs),
            )

            logger.info(
                "Created context cache",
                cache_name=cache.name,
                model=model_name,
                ttl_seconds=cache_ttl,
            )

            return cache.name or f"cache-{int(time.time())}"

        except Exception as e:
            logger.exception(
                "Failed to create context cache",
                model=model_name,
                ttl_seconds=cache_ttl,
                error=str(e),
            )
            msg = f"Failed to create context cache: {e}"
            raise ValueError(msg) from e

    async def list_caches(self) -> list[dict[str, str]]:
        """List all available context caches.

        Returns:
            List of cache information dictionaries

        Raises:
            RuntimeError: If Vertex AI not initialized
        """
        if not self._initialized:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        try:
            caches = await self._genai_client.aio.caches.list()
            result = []
            for cache in caches:
                result.append({
                    "name": cache.name,
                    "display_name": getattr(cache, "display_name", ""),
                    "model": getattr(cache, "model", ""),
                    "create_time": str(getattr(cache, "create_time", "")),
                    "expire_time": str(getattr(cache, "expire_time", "")),
                })
            return result

        except Exception as e:
            logger.exception("Failed to list context caches", error=str(e))
            msg = f"Failed to list context caches: {e}"
            raise ValueError(msg) from e

    async def delete_cache(self, cache_name: str) -> bool:
        """Delete a context cache.

        Args:
            cache_name: Name of the cache to delete

        Returns:
            True if successful

        Raises:
            RuntimeError: If Vertex AI not initialized
            ValueError: If deletion fails
        """
        if not self._initialized:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        try:
            await self._genai_client.aio.caches.delete(name=cache_name)
            logger.info("Deleted context cache", cache_name=cache_name)
            return True

        except Exception as e:
            logger.exception("Failed to delete context cache", cache_name=cache_name, error=str(e))
            msg = f"Failed to delete context cache: {e}"
            raise ValueError(msg) from e

    async def generate_chat_response_with_cache(
        self,
        messages: list[dict[str, str]],
        cache_name: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 1024,
    ) -> str:
        """Generate chat response using cached content.

        Args:
            messages: List of new chat messages
            cache_name: Name of the cache to use
            model: Optional model override
            temperature: Response temperature (0.0-1.0)
            max_output_tokens: Maximum response tokens

        Returns:
            Generated response text

        Raises:
            RuntimeError: If Vertex AI not initialized
            ValueError: If response generation fails
        """
        if not self._initialized:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        if not self._genai_client:
            msg = "GenAI client not initialized"
            raise RuntimeError(msg)

        model_name = model or self.settings.vertex_ai.CHAT_MODEL

        try:
            # Convert messages to Google GenAI format
            formatted_messages = []
            for message in messages:
                role = "user" if message["role"] == "user" else "model"
                formatted_messages.append({"role": role, "parts": [{"text": message["content"]}]})

            # Generate response using cached content
            response = await self._genai_client.aio.models.generate_content(
                model=model_name,
                contents=formatted_messages,
                config=genai.types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    cached_content=cache_name,
                ),
            )

            # Extract text from response
            if not response.candidates or len(response.candidates) == 0:
                msg = "No candidates returned from API"
                raise ValueError(msg)

            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts or len(candidate.content.parts) == 0:
                msg = "No content parts in response"
                raise ValueError(msg)

            text_content = candidate.content.parts[0].text
            if text_content is None:
                msg = "Text content is None"
                raise ValueError(msg)

            logger.debug(
                "Generated cached chat response",
                message_count=len(messages),
                response_length=len(text_content),
                model=model_name,
                cache_name=cache_name,
            )

            return text_content.strip()

        except Exception as e:
            logger.exception(
                "Failed to generate cached chat response",
                message_count=len(messages),
                model=model_name,
                cache_name=cache_name,
                error=str(e),
            )
            msg = f"Failed to generate cached chat response: {e}"
            raise ValueError(msg) from e
