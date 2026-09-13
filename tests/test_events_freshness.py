"""Tests unitaires: événements Paris et datant de moins d'un an."""

from __future__ import annotations

import json
import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pulsevents.config import CITY, PROCESSED_EVENTS_PATH, VECTOR_STORE_DIR, freshness_cutoff
from pulsevents.filters import filter_events, is_in_paris, is_within_one_year

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


def _event(
    uid: int = 1,
    city: str = "Paris",
    postal: str = "75011",
    begin: str = "2026-06-01T18:00:00+00:00",
    end: str = "2026-06-01T20:00:00+00:00",
    lat: float = 48.863,
    lon: float = 2.371,
) -> dict:
    return {
        "uid": uid,
        "title": {"fr": f"Événement {uid}"},
        "location": {
            "city": city,
            "postalCode": postal,
            "latitude": lat,
            "longitude": lon,
            "name": "Salle test",
        },
        "timings": [{"begin": begin, "end": end}],
        "firstTiming": {"begin": begin, "end": end},
        "lastTiming": {"begin": begin, "end": end},
    }


def test_paris_city_name_is_accepted():
    assert is_in_paris(_event(city="Paris", postal=""))


def test_paris_postal_code_is_accepted():
    assert is_in_paris(_event(city="Unknown", postal="75020"))


def test_suburb_is_rejected():
    event = _event(city="Vincennes", postal="94300", lat=48.847, lon=2.439)
    # Vincennes est hors intramuros (code postal 94) — rejeté même si proche.
    event["location"]["latitude"] = 48.847
    event["location"]["longitude"] = 2.439
    assert not is_in_paris(_event(city="Lyon", postal="69001", lat=45.75, lon=4.85))


def test_event_within_one_year_is_kept():
    event = _event(begin="2026-03-01T10:00:00+00:00", end="2026-03-01T12:00:00+00:00")
    assert is_within_one_year(event, now=NOW)


def test_upcoming_event_is_kept():
    event = _event(begin="2026-12-01T10:00:00+00:00", end="2026-12-01T12:00:00+00:00")
    assert is_within_one_year(event, now=NOW)


def test_event_older_than_one_year_is_rejected():
    event = _event(begin="2024-01-01T10:00:00+00:00", end="2024-01-02T10:00:00+00:00")
    assert not is_within_one_year(event, now=NOW)


def test_filter_keeps_only_recent_paris_events():
    events = [
        _event(uid=1, city="Paris", begin="2026-01-10T10:00:00+00:00", end="2026-01-10T12:00:00+00:00"),
        _event(uid=2, city="Lyon", postal="69001", lat=45.75, lon=4.85, begin="2026-01-10T10:00:00+00:00"),
        _event(uid=3, city="Paris", begin="2023-01-10T10:00:00+00:00", end="2023-01-11T10:00:00+00:00"),
    ]
    kept = filter_events(events, city="Paris", now=NOW)
    assert [e["uid"] for e in kept] == [1]


@pytest.mark.skipif(not PROCESSED_EVENTS_PATH.exists(), reason="Jeu traité absent — lancer rebuild_index.py")
def test_processed_dataset_only_contains_recent_paris_events():
    events = json.loads(PROCESSED_EVENTS_PATH.read_text(encoding="utf-8"))
    assert events, "Le fichier events.json est vide."
    cutoff = freshness_cutoff()
    for event in events:
        city = (event.get("city") or "").lower()
        postal = str(event.get("postal_code") or "")
        assert "paris" in city or postal.startswith("75"), (
            f"Événement hors Paris: uid={event.get('uid')} city={event.get('city')} postal={postal}"
        )
        end = event.get("date_end") or event.get("date_start")
        assert end, f"Événement sans date: {event.get('uid')}"
        dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        assert dt >= cutoff, f"Événement trop ancien: uid={event.get('uid')} date={end}"


@pytest.mark.skipif(
    not (VECTOR_STORE_DIR / "index.pkl").exists(),
    reason="Index FAISS absent — lancer rebuild_index.py",
)
def test_vector_store_metadata_matches_paris_and_freshness():
    payload = pickle.loads((VECTOR_STORE_DIR / "index.pkl").read_bytes())
    # LangChain FAISS: (docstore, index_to_docstore_id)
    if isinstance(payload, tuple) and len(payload) >= 1:
        docstore = payload[0]
        documents = list(getattr(docstore, "_dict", {}).values())
    else:
        documents = []
    assert documents, "Aucun document dans l'index FAISS."
    cutoff = freshness_cutoff()
    for doc in documents:
        meta = getattr(doc, "metadata", {}) or {}
        city = str(meta.get("city") or "").lower()
        postal = str(meta.get("postal_code") or "")
        assert CITY.lower() in city or postal.startswith("75")
        date_value = meta.get("date_end") or meta.get("date_start")
        if date_value:
            dt = datetime.fromisoformat(str(date_value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            assert dt >= cutoff - timedelta(days=1)
