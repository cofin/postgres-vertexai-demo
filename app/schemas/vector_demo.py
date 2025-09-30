"""Request schemas for API endpoints."""

from app.schemas.base import CamelizedBaseStruct

__all__ = ("VectorDemoRequest",)


class VectorDemoRequest(CamelizedBaseStruct, omit_defaults=True):
    """Vector search demo request."""

    query: str
