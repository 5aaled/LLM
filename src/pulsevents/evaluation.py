"""Jeu de questions/réponses annoté + mesure simple de la qualité."""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from typing import Any

from pulsevents.config import ANNOTATED_QA_PATH, EVAL_RESULTS_PATH, EVALUATION_DIR
from pulsevents.preprocess import load_processed_events

logger = logging.getLogger(__name__)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip().lower()


def build_annotated_dataset(events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """
    Construit un jeu annoté à partir des événements réels (vérité terrain).
    Une réponse est considérée correcte si elle contient les mêmes informations
    (titre, lieu, période) que l'annotation humaine.
    """
    events = events if events is not None else load_processed_events()
    if len(events) < 8:
        raise RuntimeError("Pas assez d'événements pour construire le jeu de test annoté.")

    items: list[dict[str, Any]] = []

    def add(qid: str, question: str, event: dict[str, Any], extra_must_include: list[str] | None = None) -> None:
        must = [event["title"]]
        if event.get("venue"):
            must.append(event["venue"])
        must.extend(extra_must_include or [])
        items.append(
            {
                "id": qid,
                "question": question,
                "event_uid": event.get("uid"),
                "annotated_answer": (
                    f"{event['title']} se déroule à {event.get('venue') or 'Paris'}"
                    f"{', ' + event['address'] if event.get('address') else ''}"
                    f" ({event.get('city')}"
                    f"{' ' + event['postal_code'] if event.get('postal_code') else ''}). "
                    f"Période: {event.get('date_label') or event.get('date_start') or 'non précisée'}."
                    f"{' ' + (event.get('short_description') or '')[:240]}"
                ).strip(),
                "must_include": [m for m in must if m],
                "source_url": event.get("url"),
            }
        )

    # Questions ciblées sur des événements de lieux différents
    diverse: list[dict[str, Any]] = []
    seen_venues: set[str] = set()
    for event in events:
        venue = event.get("venue") or event["title"]
        if venue in seen_venues:
            continue
        seen_venues.add(venue)
        diverse.append(event)
        if len(diverse) >= 6:
            break
    for i, event in enumerate(diverse):
        title = event["title"]
        add(
            f"title-{i+1}",
            f"Peux-tu me parler de l'événement « {title} » à Paris ?",
            event,
        )

    # Questions thématiques si des mots-clés existent
    keyword_hits: dict[str, dict[str, Any]] = {}
    for event in events:
        for kw in event.get("keywords") or []:
            key = _fold(str(kw))
            if key and key not in keyword_hits:
                keyword_hits[key] = event
        if len(keyword_hits) >= 4:
            break
    for i, (kw, event) in enumerate(keyword_hits.items()):
        add(
            f"theme-{i+1}",
            f"Quels événements autour de « {kw} » me recommandes-tu à Paris ?",
            event,
            extra_must_include=[event["title"]],
        )

    # Question lieu
    venue_event = next((e for e in events if e.get("venue")), events[0])
    add(
        "venue-1",
        f"Que se passe-t-il à {venue_event['venue']} ?",
        venue_event,
    )

    # Question quartier / arrondissement via code postal
    postal_event = next((e for e in events if str(e.get("postal_code") or "").startswith("75")), events[0])
    postal = postal_event.get("postal_code") or "75000"
    add(
        "area-1",
        f"Propose-moi une sortie culturelle dans le {postal} à Paris.",
        postal_event,
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
    hits = []
    misses = []
    for fact in must_include:
        ok = _fold(fact) in pred
        (hits if ok else misses).append(fact)
    ratio = len(hits) / len(must_include) if must_include else 0.0
    # Correct selon le brief: même sens / mêmes informations clés
    correct = ratio >= 0.5 and len(misses) <= 1
    return {
        "correct": correct,
        "coverage": round(ratio, 3),
        "hits": hits,
        "misses": misses,
    }


def evaluate_retrieval(retrieve_fn) -> dict[str, Any]:
    """Mesure si les extraits FAISS contiennent les faits annotés (sans appeler le LLM)."""
    dataset = load_annotated_dataset()
    if not dataset:
        raise RuntimeError("Jeu annoté absent. Relancez rebuild_index.py")

    rows = []
    for item in dataset:
        docs = retrieve_fn(item["question"])
        context = "\n".join(getattr(doc, "page_content", str(doc)) for doc in docs)
        titles = " ".join(str((getattr(doc, "metadata", {}) or {}).get("title") or "") for doc in docs)
        venues = " ".join(str((getattr(doc, "metadata", {}) or {}).get("venue") or "") for doc in docs)
        blob = f"{titles}\n{venues}\n{context}"
        scored = score_answer(blob, item.get("must_include") or [])
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "annotated_answer": item["annotated_answer"],
                "predicted_answer": "[évaluation retrieval — extraits FAISS]",
                **scored,
            }
        )

    n = len(rows)
    accuracy = sum(1 for r in rows if r["correct"]) / n if n else 0.0
    mean_coverage = sum(r["coverage"] for r in rows) / n if n else 0.0
    summary = {
        "mode": "retrieval",
        "n_questions": n,
        "accuracy": round(accuracy, 3),
        "mean_coverage": round(mean_coverage, 3),
        "items": rows,
    }
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_RESULTS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Évaluation retrieval: accuracy=%s coverage=%s sur %s questions",
        summary["accuracy"],
        summary["mean_coverage"],
        n,
    )
    return summary


def evaluate_rag(ask_fn) -> dict[str, Any]:
    dataset = load_annotated_dataset()
    if not dataset:
        raise RuntimeError("Jeu annoté absent. Relancez rebuild_index.py")

    rows = []
    for i, item in enumerate(dataset):
        if i:
            time.sleep(2.0)
        last_error = None
        for attempt in range(5):
            try:
                result = ask_fn(item["question"])
                break
            except Exception as exc:
                last_error = exc
                wait = 4 * (attempt + 1)
                logger.warning("Évaluation %s échec (%s). Nouvelle tentative dans %ss.", item["id"], exc, wait)
                time.sleep(wait)
        else:
            raise RuntimeError(f"Échec d'évaluation pour {item['id']}: {last_error}") from last_error
        answer = result.answer if hasattr(result, "answer") else str(result)
        scored = score_answer(answer, item.get("must_include") or [])
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "annotated_answer": item["annotated_answer"],
                "predicted_answer": answer,
                **scored,
            }
        )

    n = len(rows)
    accuracy = sum(1 for r in rows if r["correct"]) / n if n else 0.0
    mean_coverage = sum(r["coverage"] for r in rows) / n if n else 0.0
    summary = {
        "mode": "generation",
        "n_questions": n,
        "accuracy": round(accuracy, 3),
        "mean_coverage": round(mean_coverage, 3),
        "items": rows,
    }
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_RESULTS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Évaluation: accuracy=%s coverage=%s sur %s questions", summary["accuracy"], summary["mean_coverage"], n)
    return summary
