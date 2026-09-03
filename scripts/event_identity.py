#!/usr/bin/env python3
"""Stable schedule-event identity shared by refresh and live reconciliation."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime, timezone


def normalize_text(value: object) -> str:
    text = str(value or "").lower().replace("&", " and ")
    text = re.sub(r"\b(at|vs\.?|versus)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_start(value: object) -> str:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def event_identity(league: object, title: object, start: object) -> str:
    canonical = "|".join((normalize_text(league), normalize_text(title), normalize_start(start)))
    return "evt_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def provider_identity(provider: object, provider_event_id: object) -> str:
    provider = normalize_text(provider)
    provider_event_id = str(provider_event_id or "").strip()
    if not provider or not provider_event_id:
        return ""
    return f"{provider}:{provider_event_id}"
