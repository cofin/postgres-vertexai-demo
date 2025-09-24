"""Vertex AI integration service for embeddings and chat."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from google import genai
from google.cloud import aiplatform

from app.lib.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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

    async def get_text_embedding(
        self, text: str | list[str], model: str | None = None
    ) -> list[float] | list[list[float]]:
        """Generate text embedding(s) using Vertex AI.

        Args:
            text: Text to embed or list of texts for batch processing
            model: Optional model override

        Returns:
            Embedding vector for single text, or list of embedding vectors for batch

        Raises:
            RuntimeError: If Vertex AI not initialized
            ValueError: If embedding generation fails
        """
        if not self._initialized or not self._genai_client:
            msg = "Vertex AI not initialized"
            raise RuntimeError(msg)

        model_name = model or self.settings.vertex_ai.EMBEDDING_MODEL

        try:
            if isinstance(text, list):
                if not text:
                    return []

                # Medium-scale approach: batches of 5 with rate limiting
                batch_size = 5
                embeddings = []

                for i in range(0, len(text), batch_size):
                    if i > 0:
                        await asyncio.sleep(1)  # Rate limiting

                    batch = text[i : i + batch_size]
                    response = await self._genai_client.aio.models.embed_content(model=model_name, contents=batch)

                    if not response.embeddings:

                        def _raise_batch_error(index: int = i) -> None:
                            msg = f"No embeddings returned for batch starting at index {index}"
                            raise ValueError(msg)

                        _raise_batch_error()

                    batch_embeddings = [list(e.values) for e in response.embeddings if e.values is not None]
                    embeddings.extend(batch_embeddings)

                logger.debug(
                    "Generated batch embeddings",
                    batch_count=len(text),
                    embedding_dimensions=len(embeddings[0]) if embeddings else 0,
                    model=model_name,
                )
            # Single text embedding
            embedding = await self._get_embedding_async(text, model_name)

            logger.debug(
                "Generated embedding",
                text_length=len(text),
                embedding_dimensions=len(embedding),
                model=model_name,
            )

        except Exception as e:
            if isinstance(text, list):
                logger.exception(
                    "Failed to generate batch embeddings",
                    batch_size=len(text),
                    model=model_name,
                    error=str(e),
                )
            else:
                logger.exception(
                    "Failed to generate embedding",
                    text=text[:100] + "..." if len(text) > 100 else text,  # noqa: PLR2004
                    model=model_name,
                    error=str(e),
                )
            msg = f"Failed to generate embedding: {e}"
            raise ValueError(msg) from e
        else:
            if isinstance(text, list):
                return embeddings
            return embedding

    async def get_batch_text_embeddings(self, texts: list[str], gcs_input_uri: str, gcs_output_uri: str) -> str:
        """Generate large-scale batch embeddings using batch_predict.

        This method is designed for processing large datasets (thousands to millions of texts)
        using Vertex AI's batch prediction capability with GCS storage.

        Args:
            texts: List of texts to embed (for reference, actual processing uses GCS)
            gcs_input_uri: GCS URI for input JSONL file
            gcs_output_uri: GCS URI prefix for output location

        Returns:
            Batch job resource name for tracking

        Raises:
            NotImplementedError: This feature requires GCS integration
        """
        msg = (
            "Large-scale batch prediction not yet implemented. "
            f"For {len(texts)} texts, use get_text_embedding() with rate limiting instead. "
            "Batch prediction requires GCS bucket setup and JSONL file preparation."
        )
        raise NotImplementedError(msg)

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
            msg = "No embeddings returned from API"
            raise ValueError(msg)

        embedding_values = response.embeddings[0].values
        if embedding_values is None:
            msg = "Embedding values are None"
            raise ValueError(msg)
        return list(embedding_values)

    @property
    def is_initialized(self) -> bool:
        """Check if Vertex AI is initialized."""
        return self._initialized

    def get_embedding_dimensions(self) -> int:
        """Get embedding dimensions for current model."""
        return self.settings.vertex_ai.EMBEDDING_DIMENSIONS

    async def embed_product_descriptions(self, products: list[dict[str, Any]]) -> list[list[float]]:
        """Generate embeddings for product descriptions.

        Args:
            products: List of product dicts with 'name' and 'description'

        Returns:
            List of embedding vectors
        """
        # Create combined text for each product
        texts = []
        for product in products:
            combined_text = f"{product['name']}: {product['description']}"
            if product.get("category"):
                combined_text += f" (Category: {product['category']})"
            texts.append(combined_text)

        result = await self.get_text_embedding(texts)
        # Ensure we return list[list[float]] for batch embedding
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
            return result
        else:
            # This shouldn't happen with batch input, but handle gracefully
            raise ValueError("Expected batch embedding result but got single embedding")

    async def get_search_embedding(self, query: str) -> list[float]:
        """Get embedding optimized for similarity search.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        # For search queries, we might want to add context
        search_text = f"Search query: {query}"

        result = await self.get_text_embedding(search_text)
        # Ensure we return list[float] for single embedding
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], float):
            return result
        # This shouldn't happen with single input, but handle gracefully
        msg = "Expected single embedding result but got batch embedding"
        raise ValueError(msg)
