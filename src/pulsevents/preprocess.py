"""Nettoyage, structuration et découpage des événements pour l'indexation."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pulsevents.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CITY,
    MAX_EVENTS,
    PROCESSED_EVENTS_PATH,
)
from pulsevents.filters import event_date_bounds, filter_events
from pulsevents.text_utils import localized, strip_html

logger = logging.getLogger(__name__)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    location = event.get("location") or {}
    start, end = event_date_bounds(event)
    keywords = event.get("keywords")
    if isinstance(keywords, dict):
        kw_list = keywords.get("fr") or keywords.get("en") or []
    else:
        kw_list = keywords or []
    if isinstance(kw_list, str):
        kw_list = [kw_list]

    title = strip_html(localized(event.get("title")))
    description = strip_html(
        localized(event.get("longDescription")) or localized(event.get("description"))
    )
    short = strip_html(localized(event.get("description")))
    venue = strip_html(localized(location.get("name")))
    address = strip_html(localized(location.get("address")))
    city = strip_html(localized(location.get("city")) or CITY)
    postal = str(location.get("postalCode") or "").strip()
    if not postal:
        match = re.search(r"\b(75\d{3})\b", address)
        if match:
            postal = match.group(1)
    conditions = strip_html(localized(event.get("conditions")))
    date_label = strip_html(localized(event.get("range")))
    slug = event.get("slug") or ""
    url = (
        event.get("canonicalUrl")
        or event.get("originalUrl")
        or (f"https://openagenda.com/events/{slug}" if slug else "")
    )

    text = "\n".join(
        part
        for part in (
            f"Titre: {title}" if title else "",
            f"Lieu: {venue}" if venue else "",
            f"Adresse: {address}, {city} {postal}".strip(", "),
            f"Dates: {date_label or _iso(start)}" if (date_label or start) else "",
            f"Début: {_iso(start)}" if start else "",
            f"Fin: {_iso(end)}" if end else "",
            f"Mots-clés: {', '.join(str(k) for k in kw_list)}" if kw_list else "",
            f"Tarif / conditions: {conditions}" if conditions else "",
            f"Résumé: {short}" if short else "",
            f"Description: {description}" if description else "",
        )
        if part
    )

    lat = location.get("latitude") or location.get("lat")
    lon = location.get("longitude") or location.get("lng") or location.get("lon")

    return {
        "uid": event.get("uid"),
        "title": title,
        "description": description or short,
        "short_description": short,
        "keywords": [str(k) for k in kw_list],
        "venue": venue,
        "address": address,
        "city": city,
        "postal_code": postal,
        "latitude": float(lat) if lat not in (None, "") else None,
        "longitude": float(lon) if lon not in (None, "") else None,
        "date_start": _iso(start),
        "date_end": _iso(end),
        "date_label": date_label,
        "url": url,
        "status": event.get("status"),
        "text": text,
    }


def structure_events(raw_events: list[dict[str, Any]], max_events: int = MAX_EVENTS) -> list[dict[str, Any]]:
    filtered = filter_events(raw_events)
    filtered.sort(
        key=lambda e: len(localized(e.get("longDescription") or e.get("description") or "")),
        reverse=True,
    )
    candidates = []
    seen = set()
    for event in filtered:
        item = normalize_event(event)
        uid = item.get("uid")
        if not uid or uid in seen:
            continue
        if not item["title"] or len(item["text"]) < 40:
            continue
        seen.add(uid)
        candidates.append(item)

    # Diversifier les lieux pour la démo (pas uniquement le premier agenda).
    by_venue: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        key = item.get("venue") or "autre"
        by_venue.setdefault(key, []).append(item)
    normalized: list[dict[str, Any]] = []
    while len(normalized) < max_events and by_venue:
        empty_keys = []
        for key, bucket in by_venue.items():
            if not bucket:
                empty_keys.append(key)
                continue
            normalized.append(bucket.pop(0))
            if len(normalized) >= max_events:
                break
        for key in empty_keys:
            by_venue.pop(key, None)

    PROCESSED_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_EVENTS_PATH.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("%s événements structurés écrits dans %s", len(normalized), PROCESSED_EVENTS_PATH)
    return normalized


def load_processed_events() -> list[dict[str, Any]]:
    if not PROCESSED_EVENTS_PATH.exists():
        return []
    return json.loads(PROCESSED_EVENTS_PATH.read_text(encoding="utf-8"))


def events_to_documents(events: list[dict[str, Any]]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    documents: list[Document] = []
    for event in events:
        metadata = {
            "uid": str(event.get("uid")),
            "title": event.get("title") or "",
            "venue": event.get("venue") or "",
            "city": event.get("city") or CITY,
            "postal_code": event.get("postal_code") or "",
            "date_start": event.get("date_start") or "",
            "date_end": event.get("date_end") or "",
            "date_label": event.get("date_label") or "",
            "url": event.get("url") or "",
            "keywords": ", ".join(event.get("keywords") or []),
        }
        base = Document(page_content=event["text"], metadata=metadata)
        chunks = splitter.split_documents([base])
        for index, chunk in enumerate(chunks):
            chunk.metadata = {**metadata, "chunk_index": index}
            documents.append(chunk)
    logger.info("%s chunks générés à partir de %s événements.", len(documents), len(events))
    return documents
