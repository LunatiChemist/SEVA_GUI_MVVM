from __future__ import annotations

import logging
import os
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DEFAULT_DATEFMT = "%H:%M:%S"
_LEVEL_ENV_VARS = ("SEVA_LOG_LEVEL", "SEVA_GUI_LOG_LEVEL")
_DEBUG_FLAGS = ("SEVA_DEBUG_LOGGING", "SEVA_GUI_DEBUG", "SEVA_DEBUG")


def _coerce_level(value: Optional[str], fallback: int) -> int:
    if not value:
        return fallback
    text = value.strip()
    if not text:
        return fallback
    if text.isdigit():
        try:
            return int(text)
        except ValueError:
            return fallback
    upper = text.upper()
    if hasattr(logging, upper):
        candidate = getattr(logging, upper)
        if isinstance(candidate, int):
            return candidate
    return fallback


def _env_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_env_level() -> Optional[int]:
    for var in _LEVEL_ENV_VARS:
        value = os.getenv(var)
        if value:
            return _coerce_level(value, logging.INFO)
    if any(_env_truthy(os.getenv(flag)) for flag in _DEBUG_FLAGS):
        return logging.DEBUG
    return None


def configure_root(default_level: int | str = logging.INFO) -> int:
    """
    Configure the root logger with a compact format.

    Environment overrides:
      - SEVA_LOG_LEVEL / SEVA_GUI_LOG_LEVEL: explicit log level
      - SEVA_DEBUG_LOGGING / SEVA_GUI_DEBUG / SEVA_DEBUG: truthy -> DEBUG
    """
    fallback = (
        _coerce_level(default_level, logging.INFO)
        if isinstance(default_level, str)
        else int(default_level)
    )
    effective = _resolve_env_level() or fallback

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=effective, format=_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT)
    root.setLevel(effective)
    return effective


def apply_gui_preferences(debug_enabled: bool) -> int:
    """
    Update root log level based on GUI settings while honoring env overrides.
    Returns the effective level after the update.
    """
    env_level = _resolve_env_level()
    level = env_level if env_level is not None else (logging.DEBUG if debug_enabled else logging.INFO)
    logging.getLogger().setLevel(level)
    return level


def level_name(level: int) -> str:
    """Return logging level name for diagnostics."""
    return logging.getLevelName(level)


def env_requests_debug() -> bool:
    """Return True if environment variables force DEBUG logging."""
    env_level = _resolve_env_level()
    if env_level is None:
        return False
    return env_level <= logging.DEBUG
