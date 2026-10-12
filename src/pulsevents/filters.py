

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from pulsevents.config import CITY, PARIS_BBOX, freshness_cutoff
from pulsevents.text_utils import normalize_city

_POSTAL_PARIS_RE = re.compile(r"^75\d{3}$")
_CITY_PARIS_RE = re.compile(r"^paris(\s|$|\d|'|-)", re.IGNORECASE)


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):    #“Because Z means UTC, and I replace it with +00:00, which is the UTC offset format that Python’s datetime.fromisoformat() can parse consistently.”
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)    # parses an ISO date/time string and converts it into a Python datetime object.
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def event_date_bounds(event: dict[str, Any]) -> tuple[Optional[datetime], Optional[datetime]]:

    starts: list[datetime] = []
    ends: list[datetime] = []

    for key in ("firstTiming", "lastTiming"):
        block = event.get(key) or {}
        begin = parse_iso_datetime(block.get("begin") or block.get("start"))
        end = parse_iso_datetime(block.get("end"))
        if begin:
            starts.append(begin)
        if end:
            ends.append(end)

    for timing in event.get("timings") or []:
        begin = parse_iso_datetime(timing.get("begin") or timing.get("start"))
        end = parse_iso_datetime(timing.get("end"))
        if begin:
            starts.append(begin)
        if end:
            ends.append(end)

    start = min(starts) if starts else None
    end = max(ends) if ends else start
    return start, end


def is_in_paris(event: dict[str, Any], city: str = CITY) -> bool:

    location = event.get("location") or {}
    city_value = (
        location.get("city")
        or location.get("adminLevel4")
        or event.get("city")
        or ""
    )
    city_norm = normalize_city(str(city_value))
    target = normalize_city(city)

    if target in city_norm or _CITY_PARIS_RE.match(city_value or ""):
        return True

    postal = str(location.get("postalCode") or location.get("postal_code") or "").strip()
    if _POSTAL_PARIS_RE.match(postal):
        return True

    department = str(
        location.get("department")
        or location.get("adminLevel6")
        or location.get("adminLevel3")
        or ""
    )
    if department.strip() in {"75", "Paris"}:
        return True

    lat = location.get("latitude") or location.get("lat")
    lon = location.get("longitude") or location.get("lng") or location.get("lon")
    try:
        if lat is not None and lon is not None:
            lat_f, lon_f = float(lat), float(lon)
            return (
                PARIS_BBOX["south"] <= lat_f <= PARIS_BBOX["north"]
                and PARIS_BBOX["west"] <= lon_f <= PARIS_BBOX["east"]
            )
    except (TypeError, ValueError):
        pass

    return False


def is_within_one_year(event: dict[str, Any], now: Optional[datetime] = None) -> bool:

    from datetime import timedelta

    start, end = event_date_bounds(event)
    if start is None and end is None:
        return False
    cutoff = freshness_cutoff() if now is None else now - timedelta(days=365)
    latest = end or start
    return latest >= cutoff


def filter_events(
    events,
    city: str = CITY,
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    kept = []
    for event in events:
        if is_in_paris(event, city=city) and is_within_one_year(event, now=now):
            kept.append(event)
    return kept
