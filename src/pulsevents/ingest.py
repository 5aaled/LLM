"""Collecte des événements OpenAgenda pour Paris."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import requests

from pulsevents.config import (
    CITY,
    MAX_EVENTS,
    OPENAGENDA_BASE_URL,
    OPENAGENDA_PAGE_SIZE,
    PARIS_AGENDA_SLUGS,
    PARIS_BBOX,
    RAW_EVENTS_PATH,
    require_openagenda_key,
)
from pulsevents.text_utils import localized

logger = logging.getLogger(__name__)


def _session() -> requests.Session:
    key = require_openagenda_key()
    session = requests.Session()
    session.headers.update(
        {
            "key": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "PulsEvents-RAG-POC/0.1",
        }
    )
    return session


def _get_json(session: requests.Session, url: str, params: Optional[dict] = None) -> dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(4):
        try:
            response = session.get(url, params=params, timeout=30)
            if response.status_code in {429, 500, 502, 503, 504}:
                wait = 2 ** attempt
                logger.warning("OpenAgenda %s — nouvel essai dans %ss", response.status_code, wait)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Échec de l'appel OpenAgenda {url}: {last_error}") from last_error


def discover_paris_agendas(session: requests.Session) -> list[dict[str, Any]]:
    """Trouve des agendas officiels / pertinents pour Paris."""
    found: dict[int, dict[str, Any]] = {}

    for slug in PARIS_AGENDA_SLUGS:
        payload = _get_json(
            session,
            f"{OPENAGENDA_BASE_URL}/agendas",
            params={"slug": slug, "size": 5},
        )
        for agenda in payload.get("agendas") or []:
            uid = agenda.get("uid")
            if uid:
                found[int(uid)] = agenda

    for search in (CITY, f"Ville de {CITY}", f"que faire à {CITY}"):
        payload = _get_json(
            session,
            f"{OPENAGENDA_BASE_URL}/agendas",
            params={"search": search, "official": 1, "size": 20},
        )
        for agenda in payload.get("agendas") or []:
            title = localized(agenda.get("title")).lower()
            slug = str(agenda.get("slug") or "").lower()
            if CITY.lower() not in title and CITY.lower() not in slug:
                continue
            uid = agenda.get("uid")
            if uid:
                found[int(uid)] = agenda

    agendas = list(found.values())
    logger.info("%s agenda(s) Paris identifié(s).", len(agendas))
    return agendas


def _event_params(after: Optional[list] = None, rich: bool = True) -> dict[str, Any]:
    params: dict[str, Any] = {
        "size": OPENAGENDA_PAGE_SIZE,
        "relative[]": ["current", "upcoming"],
        "city[]": CITY,
    }
    if rich:
        params.update(
            {
                "adminLevel4[]": CITY,
                "geo[northEast][lat]": PARIS_BBOX["north"],
                "geo[northEast][lng]": PARIS_BBOX["east"],
                "geo[southWest][lat]": PARIS_BBOX["south"],
                "geo[southWest][lng]": PARIS_BBOX["west"],
            }
        )
    if after:
        params["after[]"] = after
    return params


def fetch_events_from_agenda(
    session: requests.Session,
    agenda_uid: int,
    max_events: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    after = None
    url = f"{OPENAGENDA_BASE_URL}/agendas/{agenda_uid}/events"
    rich = True
    while len(events) < max_events:
        try:
            payload = _get_json(session, url, params=_event_params(after, rich=rich))
        except RuntimeError:
            if rich:
                logger.warning("Filtres riches refusés pour l'agenda %s, repli simplifié.", agenda_uid)
                rich = False
                after = None
                continue
            raise
        batch = payload.get("events") or []
        if not batch:
            break
        events.extend(batch)
        after = payload.get("after")
        logger.info("Agenda %s — %s événements accumulés.", agenda_uid, len(events))
        if not after:
            break
        time.sleep(0.15)
    return events[:max_events]


def fetch_events_cross_agenda(session: requests.Session, max_events: int) -> list[dict[str, Any]]:
    """Recherche transverse (expérimentale) — utile si elle est ouverte sur la clé."""
    events: list[dict[str, Any]] = []
    after = None
    url = f"{OPENAGENDA_BASE_URL}/events"
    while len(events) < max_events:
        try:
            payload = _get_json(session, url, params=_event_params(after))
        except RuntimeError as exc:
            logger.warning("Recherche transverse indisponible: %s", exc)
            return []
        batch = payload.get("events") or []
        if not batch:
            break
        events.extend(batch)
        after = payload.get("after")
        if not after:
            break
        time.sleep(0.15)
    return events[:max_events]


def fetch_openagenda_events(max_events: int = MAX_EVENTS) -> list[dict[str, Any]]:
    """
    Récupère des événements Paris, dédupliqués par uid.
    Essaie d'abord la recherche transverse, puis les agendas découverts.
    """
    session = _session()
    by_uid: dict[int, dict[str, Any]] = {}

    cross = fetch_events_cross_agenda(session, max_events=max_events)
    for event in cross:
        uid = event.get("uid")
        if uid:
            by_uid[int(uid)] = event

    if len(by_uid) < max_events:
        agendas = discover_paris_agendas(session)
        remaining = max_events - len(by_uid)
        per_agenda = max(50, remaining // max(len(agendas), 1))
        for agenda in agendas:
            uid = agenda.get("uid")
            if not uid:
                continue
            batch = fetch_events_from_agenda(session, int(uid), max_events=per_agenda)
            for event in batch:
                event_uid = event.get("uid")
                if event_uid:
                    by_uid[int(event_uid)] = event
            if len(by_uid) >= max_events:
                break

    events = list(by_uid.values())
    logger.info("%s événements bruts récupérés.", len(events))
    RAW_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_EVENTS_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    return events


def load_raw_events() -> list[dict[str, Any]]:
    if not RAW_EVENTS_PATH.exists():
        return []
    return json.loads(RAW_EVENTS_PATH.read_text(encoding="utf-8"))
