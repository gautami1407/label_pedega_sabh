"""
Backward compatibility module for lps.gateway.config.

DEPRECATED: Use lps.core.config instead.

This module re-exports settings from lps.core.config for backward compatibility
with code that still imports from the old location.
"""
from __future__ import annotations

import warnings

# Re-export from new location
from lps.core.config import Settings, get_settings

warnings.warn(
    "lps.gateway.config is deprecated. Use lps.core.config instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Settings", "get_settings"]
