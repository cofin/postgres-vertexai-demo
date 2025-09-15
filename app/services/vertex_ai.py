"""Vertex AI integration service for embeddings and chat."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from google.cloud import aiplatform
from sqlspec.utils.sync_tools import async_

from app.lib.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger()


class VertexAIService:
    """Vertex AI service for embeddings and chat completions."""

    def __init__(self) -> None:
        """Initialize Vertex AI service."""
        self.settings = get_settings()

        # Initialize Vertex AI
        if self.settings.vertex_ai.PROJECT_ID:
            aiplatform.init(
                project=self.settings.vertex_ai.PROJECT_ID,
                location=self.settings.vertex_ai.LOCATION,
            )
            self._initialized = True
            logger.info(
                "Vertex AI initialized (private deployment)",
                project=self.settings.vertex_ai.PROJECT_ID,
                location=self.settings.vertex_ai.LOCATION,
            )
        else:
            self._initialized = False
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
            # Run in thread pool since Vertex AI SDK is synchronous
            embedding = await async_(self._get_embedding_sync)(text, model_name)

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
            # Run in thread pool since Vertex AI SDK is synchronous
            embeddings = await async_(self._get_batch_embeddings_sync)(texts, model_name)

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
            # Run in thread pool since Vertex AI SDK is synchronous
            response = await async_(self._generate_chat_response_sync)(
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

    def _get_embedding_sync(self, text: str, model: str) -> list[float]:
        """Synchronous embedding generation using Vertex AI (private deployment)."""
        from vertexai.language_models import TextEmbeddingModel

        # This uses your private Vertex AI deployment, not public endpoints
        embedding_model = TextEmbeddingModel.from_pretrained(model)
        embeddings = embedding_model.get_embeddings([text])

        return list(embeddings[0].values)

    def _get_batch_embeddings_sync(self, texts: Sequence[str], model: str) -> list[list[float]]:
        """Synchronous batch embedding generation using Vertex AI (private deployment)."""
        from vertexai.language_models import TextEmbeddingModel

        # This uses your private Vertex AI deployment, not public endpoints
        embedding_model = TextEmbeddingModel.from_pretrained(model)
        embeddings = embedding_model.get_embeddings(list(texts))

        return [list(embedding.values) for embedding in embeddings]

    def _generate_chat_response_sync(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Synchronous chat response generation."""
        from vertexai.generative_models import GenerativeModel

        # Convert messages to Vertex AI format
        formatted_messages = []
        for message in messages:
            if message["role"] == "user":
                formatted_messages.append(f"Human: {message['content']}")
            elif message["role"] == "assistant":
                formatted_messages.append(f"Assistant: {message['content']}")

        prompt = "\n".join(formatted_messages)
        if not prompt.endswith("\nAssistant:"):
            prompt += "\nAssistant:"

        # Initialize generative model
        generative_model = GenerativeModel(model)

        # Generate response
        response = generative_model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            },
        )

        return response.text.strip()

    @property
    def is_initialized(self) -> bool:
        """Check if Vertex AI is initialized."""
        return self._initialized

    def get_embedding_dimensions(self) -> int:
        """Get embedding dimensions for current model."""
        return self.settings.vertex_ai.EMBEDDING_DIMENSIONS
