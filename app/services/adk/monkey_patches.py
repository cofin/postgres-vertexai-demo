"""Monkey patches for ADK backward compatibility.

This module contains temporary fixes for google-adk 1.16.0 issues.
See: https://github.com/google/adk-python/issues/3197
"""

from __future__ import annotations

import functools

import structlog
from google.adk.events.event_actions import EventActions

logger = structlog.get_logger()


def apply_event_actions_patch() -> None:
    """Apply monkey patch for EventActions backward compatibility.

    Google ADK 1.16.0 added new attributes (agent_state, end_of_agent, etc.)
    to EventActions, but persisted sessions from older versions don't have these.
    This causes AttributeError when the runner tries to access them.

    This patch makes __getattr__ return None for known missing fields instead
    of raising AttributeError, maintaining backward compatibility with old sessions.

    Reference: https://github.com/google/adk-python/issues/3197#issuecomment-3415894433
    """
    # Known field attributes that should return None when missing (for backward compatibility)
    SAFE_FIELD_ATTRIBUTES = {
        "agent_state",
        "end_of_agent",
        "compaction",
        "rewind_before_invocation_id",
    }

    original_getattr = EventActions.__getattr__

    @functools.wraps(original_getattr)
    def safe_getattr(self, name: str):
        try:
            return original_getattr(self, name)
        except AttributeError:
            # Only handle known field attributes that should have safe defaults
            if name in SAFE_FIELD_ATTRIBUTES:
                logger.debug(
                    f"EventActions missing field attribute '{name}', returning None for backward compatibility"
                )
                return None

            # For all other attributes (like methods, special attributes), re-raise the AttributeError
            # This ensures that SQLAlchemy and other systems get proper AttributeError for missing methods
            raise

    EventActions.__getattr__ = safe_getattr
