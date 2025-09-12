"""Request schemas for API endpoints."""

from __future__ import annotations

import msgspec

__all__ = ("VectorDemoRequest",)


class VectorDemoRequest(msgspec.Struct, gc=False, array_like=True, omit_defaults=True):
    """Vector search demo request."""

    query: str
