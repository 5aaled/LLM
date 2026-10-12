"""Utilitaires de nettoyage des champs OpenAgenda."""

from __future__ import annotations

import html
import re
from typing import Any

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def localized(value: Any, lang: str = "fr") -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        picked = value.get(lang) or value.get("en") or list(value.values())[0]
        return localized(picked, lang)
    if isinstance(value, list):
        return ", ".join(localized(item, lang) for item in value if item)
    return str(value)


def strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = _HTML_TAG_RE.sub(" ", text)
    cleaned = html.unescape(cleaned)
    return _WS_RE.sub(" ", cleaned).strip()


def normalize_city(city: str) -> str:
    return _WS_RE.sub(" ", (city or "").strip().lower()).replace("é", "e")
