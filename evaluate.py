"""Évalue le RAG sur le jeu de questions/réponses annoté."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pulsevents.evaluation import evaluate_rag, evaluate_retrieval, load_annotated_dataset  # noqa: E402
from pulsevents.rag import EventRAG


def main() -> None:
    parser = argparse.ArgumentParser(description="Évalue le POC RAG Puls-Events.")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Évalue aussi les réponses générées (appels Mistral chat, sujet aux quotas).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    dataset = load_annotated_dataset()
    if not dataset:
        raise SystemExit("Jeu annoté introuvable. Lancez d'abord: python rebuild_index.py")

    rag = EventRAG()
    summary = evaluate_retrieval(rag.retrieve)
    print("Retrieval:", json.dumps({k: summary[k] for k in ("n_questions", "accuracy", "mean_coverage")}))

    if args.llm:
        summary = evaluate_rag(rag.ask)
        print("Génération:", json.dumps({k: summary[k] for k in ("n_questions", "accuracy", "mean_coverage")}))

    print("Détail: data/evaluation/results.json")


if __name__ == "__main__":
    main()
