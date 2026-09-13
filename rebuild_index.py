"""Pipeline de reconstruction de la base vectorielle (prétraitement + vectorisation)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pulsevents.config import (  # noqa: E402
    CITY,
    MAX_EVENTS,
    PROCESSED_EVENTS_PATH,
    VECTOR_STORE_DIR,
)

from pulsevents.evaluation import build_annotated_dataset  # noqa: E402
from pulsevents.index import build_faiss_index  # noqa: E402
from pulsevents.ingest import fetch_openagenda_events, load_raw_events  # noqa: E402
from pulsevents.preprocess import events_to_documents, structure_events  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstruit la base vectorielle FAISS à partir d'OpenAgenda (Paris)."
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Réutilise data/raw/openagenda_events.json sans rappeler l'API.",
    )
    parser.add_argument("--max-events", type=int, default=MAX_EVENTS)
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Arrête après le prétraitement (pas d'appels embeddings Mistral).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.skip_fetch:
        raw = load_raw_events()
        if not raw:
            raise SystemExit("Aucune donnée brute. Relancez sans --skip-fetch.")
    else:
        raw = fetch_openagenda_events(max_events=max(args.max_events * 3, 200))

    events = structure_events(raw, max_events=args.max_events)
    if not events:
        raise SystemExit(
            "Aucun événement Paris < 1 an après filtrage. Vérifiez la clé OpenAgenda et le périmètre."
        )

    build_annotated_dataset(events)

    if args.skip_index:
        logging.info("Index FAISS non reconstruit (--skip-index).")
        return

    documents = events_to_documents(events)
    build_faiss_index(documents)

    meta = {
        "city": CITY,
        "n_raw": len(raw),
        "n_events": len(events),
        "n_chunks": len(documents),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "processed_path": str(PROCESSED_EVENTS_PATH),
        "vector_store": str(VECTOR_STORE_DIR),
    }
    (VECTOR_STORE_DIR / "build_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logging.info("Base vectorielle prête: %s événements, %s chunks.", len(events), len(documents))


if __name__ == "__main__":
    main()
