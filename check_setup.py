"""Vérifie que LangChain, FAISS et Mistral s'importent correctement."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    import faiss
    import langchain
    import mistralai
    from langchain_community.vectorstores import FAISS
    from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

    from pulsevents.config import CHAT_MODEL, EMBEDDING_MODEL, MISTRAL_API_KEY, OPENAGENDA_API_KEY

    print("Python        :", sys.version.split()[0])
    print("langchain     :", langchain.__version__)
    print("faiss         :", getattr(faiss, "__version__", "ok"))
    print("mistralai     :", getattr(mistralai, "__version__", "ok"))
    print("FAISS class   :", FAISS.__name__)
    print("Embeddings    :", MistralAIEmbeddings.__name__, "→", EMBEDDING_MODEL)
    print("Chat model    :", ChatMistralAI.__name__, "→", CHAT_MODEL)
    print("MISTRAL key   :", "présente" if MISTRAL_API_KEY else "MANQUANTE")
    print("OpenAgenda key:", "présente" if OPENAGENDA_API_KEY else "MANQUANTE")
    print("Environnement OK.")


if __name__ == "__main__":
    main()
