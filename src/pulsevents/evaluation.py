"""Jeu de questions/réponses annoté + mesure simple de la qualité."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any, Callable

from pulsevents.config import ANNOTATED_QA_PATH, EVAL_RESULTS_PATH, EVALUATION_DIR
from pulsevents.preprocess import load_processed_events

logger = logging.getLogger(__name__)

N_QUESTIONS = 8


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip().lower()


def build_annotated_dataset(events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:

    events = events if events is not None else load_processed_events()

    picked: list[dict[str, Any]] = []
    seen_venues: set[str] = set()
    for event in events:
        title = event.get("title")
        venue = event.get("venue") or ""
        if not title or venue in seen_venues:
            continue
        seen_venues.add(venue)
        picked.append(event)
        if len(picked) >= N_QUESTIONS:
            break

    if not picked:
        raise RuntimeError("Pas assez d'événements pour construire le jeu de test annoté.")

    items: list[dict[str, Any]] = []
    for i, event in enumerate(picked, start=1):
        title = event["title"]
        venue = event.get("venue") or "Paris"
        date = event.get("date_start") or event.get("date_label") or "non précisée"
        address = f", {event['address']}" if event.get("address") else ""
        city = event.get("city") or "Paris"
        postal = f" {event['postal_code']}" if event.get("postal_code") else ""
        description = (event.get("short_description") or "")[:240]
        answer = (
            f"{title} se déroule à {venue}{address} ({city}{postal}). "
            f"Période: {date}."
        )
        if description:
            answer = f"{answer} {description}"

        must = [title]
        if event.get("venue"):
            must.append(event["venue"])

        items.append(
            {
                "id": f"q{i}",
                "question": f"Peux-tu me parler de l'événement « {title} » à Paris ?",
                "event_uid": event.get("uid"),
                "annotated_answer": answer.strip(),
                "must_include": must,
                "source_url": event.get("url"),
            }
        )

    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    ANNOTATED_QA_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("%s paires Q/R annotées écrites dans %s", len(items), ANNOTATED_QA_PATH)
    return items


def load_annotated_dataset() -> list[dict[str, Any]]:
    if not ANNOTATED_QA_PATH.exists():
        return []
    return json.loads(ANNOTATED_QA_PATH.read_text(encoding="utf-8"))


def score_answer(predicted: str, must_include: list[str]) -> dict[str, Any]:

    pred = _fold(predicted)
    hits = [fact for fact in must_include if _fold(fact) in pred]
    misses = [fact for fact in must_include if _fold(fact) not in pred]
    ratio = len(hits) / len(must_include) if must_include else 0.0
    return {
        "correct": len(misses) == 0,
        "coverage": round(ratio, 3),
        "hits": hits,
        "misses": misses,
    }


def _evaluate(get_text: Callable[[str], str], mode: str) -> dict[str, Any]:
    dataset = load_annotated_dataset()
    if not dataset:
        raise RuntimeError("Jeu annoté absent")

    rows = []
    for item in dataset:
        predicted = get_text(item["question"])
        scored = score_answer(predicted, item.get("must_include") or [])
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "annotated_answer": item["annotated_answer"],
                "predicted_answer": predicted,
                **scored,
            }
        )

    n = len(rows)
    accuracy = sum(1 for row in rows if row["correct"]) / n if n else 0.0
    mean_coverage = sum(row["coverage"] for row in rows) / n if n else 0.0
    summary = {
        "mode": mode,
        "n_questions": n,
        "accuracy": round(accuracy, 3),
        "mean_coverage": round(mean_coverage, 3),
        "items": rows,
    }
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_RESULTS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Évaluation %s: accuracy=%s coverage=%s sur %s questions",
        mode,
        summary["accuracy"],
        summary["mean_coverage"],
        n,
    )
    return summary


def evaluate_retrieval(retrieve_fn) -> dict[str, Any]:

    def get_text(question: str) -> str:
        docs = retrieve_fn(question)
        parts = []
        for doc in docs:
            meta = getattr(doc, "metadata", {}) or {}
            parts.append(str(meta.get("title") or ""))
            parts.append(str(meta.get("venue") or ""))
            parts.append(getattr(doc, "page_content", str(doc)))
        return "\n".join(parts)

    return _evaluate(get_text, "retrieval")


def evaluate_rag(ask_fn) -> dict[str, Any]:

    def get_text(question: str) -> str:
        result = ask_fn(question)
        return result.answer if hasattr(result, "answer") else str(result)

    return _evaluate(get_text, "generation")
