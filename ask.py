"""Question en ligne de commande (démo sans Streamlit)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pulsevents.rag import EventRAG


def main() -> None:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise SystemExit('Usage: python ask.py "Quels concerts à Paris ?"')
    rag = EventRAG()
    result = rag.ask(question)
    print(result.answer)
    print("\n--- Sources ---")
    for src in result.sources:
        print(f"- {src.get('title')} | {src.get('venue')} | {src.get('date_label')}")
        if src.get("url"):
            print(f"  {src['url']}")


if __name__ == "__main__":
    main()
