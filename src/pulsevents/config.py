
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
OPENAGENDA_API_KEY = os.getenv("OPENAGENDA_API_KEY", "").strip()

CITY = os.getenv("CITY", "Paris").strip()
COUNTRY_CODE = os.getenv("COUNTRY_CODE", "FR").strip()
MAX_EVENTS = int(os.getenv("MAX_EVENTS", "350"))


EMBEDDING_MODEL = "mistral-embed"
CHAT_MODEL = "ministral-8b-latest"

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
SEARCH_K = 5
EMBEDDING_BATCH_SIZE = 16


PARIS_BBOX = {
    "south": 48.8156,
    "north": 48.9022,
    "west": 2.2241,
    "east": 2.4699,
}

DATA_DIR = PROJECT_ROOT / "data"
RAW_EVENTS_PATH = DATA_DIR / "raw" / "openagenda_events.json"
PROCESSED_EVENTS_PATH = DATA_DIR / "processed" / "events.json"
EVALUATION_DIR = DATA_DIR / "evaluation"
ANNOTATED_QA_PATH = EVALUATION_DIR / "annotated_qa.json"
EVAL_RESULTS_PATH = EVALUATION_DIR / "results.json"

VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store" / "faiss_paris"
DOCS_DIR = PROJECT_ROOT / "docs"

OPENAGENDA_BASE_URL = "https://api.openagenda.com/v2"
OPENAGENDA_PAGE_SIZE = 100


PARIS_AGENDA_SLUGS = (
    "que-faire-a-paris",
    "que-faire-a-paris-1",
    "paris",
    "ville-de-paris",
    "culture-a-paris",
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def freshness_cutoff() -> datetime:

    return now_utc() - timedelta(days=365)


def require_mistral_key() -> str:
    if not MISTRAL_API_KEY:
        raise RuntimeError(
            "MISTRAL_API_KEY manquante. Ajoutez-la dans le fichier .env "
            "(voir .env.example)."
        )
    return MISTRAL_API_KEY


def require_openagenda_key() -> str:
    if not OPENAGENDA_API_KEY:
        raise RuntimeError(
            "OPENAGENDA_API_KEY manquante. Ajoutez-la dans le fichier .env "
            "(voir .env.example)."
        )
    return OPENAGENDA_API_KEY
