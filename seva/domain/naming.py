from __future__ import annotations

"""Naming helpers for deterministic identifiers shared between layers."""

import random
import re
import string

from .entities import ClientDateTime, GroupId, PlanMeta

_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
_RANDOM_ALPHABET = string.ascii_uppercase + string.digits


def _sanitize_component(raw: str) -> str:
    """Return a sanitized token containing only `[A-Za-z0-9_-]`, collapsing sequences."""

    cleaned = _SANITIZE_PATTERN.sub("_", raw.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    cleaned = cleaned.strip("-")
    return cleaned or "unnamed"


def _format_client_dt(client_dt: ClientDateTime) -> str:
    """Format the client-side timestamp for identifiers using local time."""

    localized = client_dt.value.astimezone()
    return localized.strftime("%Y%m%d_%H%M%S")


def make_group_id(meta: PlanMeta) -> GroupId:
    """Compose an identifier `{Experiment[_Subdir]}__{YYYYMMDD_HHMMSS}__{rnd4}`."""

    experiment_token = _sanitize_component(meta.experiment)
    if meta.subdir:
        subdir_token = _sanitize_component(meta.subdir)
        if subdir_token:
            experiment_token = f"{experiment_token}_{subdir_token}"

    timestamp_token = _format_client_dt(meta.client_dt)
    random_token = "".join(random.choices(_RANDOM_ALPHABET, k=4))
    identifier = f"{experiment_token}__{timestamp_token}__{random_token}"
    return GroupId(identifier)


__all__ = ["make_group_id"]
