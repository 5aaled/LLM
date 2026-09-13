"""Indexation FAISS + embeddings Mistral via LangChain."""

from __future__ import annotations

import logging
import shutil

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings

from pulsevents.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL,
    VECTOR_STORE_DIR,
    require_mistral_key,
)

logger = logging.getLogger(__name__)


def get_embeddings() -> MistralAIEmbeddings:
    return MistralAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=require_mistral_key(),
    )


def build_faiss_index(documents: list[Document]) -> FAISS:
    if not documents:
        raise ValueError("Aucun document à indexer.")

    embeddings = get_embeddings()
    logger.info("Création de l'index FAISS (%s chunks, modèle %s)...", len(documents), EMBEDDING_MODEL)

    first, rest = documents[:EMBEDDING_BATCH_SIZE], documents[EMBEDDING_BATCH_SIZE:]
    vectorstore = FAISS.from_documents(first, embeddings)
    for start in range(0, len(rest), EMBEDDING_BATCH_SIZE):
        batch = rest[start : start + EMBEDDING_BATCH_SIZE]
        vectorstore.add_documents(batch)
        logger.info("Index: %s / %s chunks.", min(start + EMBEDDING_BATCH_SIZE, len(rest)) + len(first), len(documents))

    save_faiss_index(vectorstore)
    return vectorstore


def save_faiss_index(vectorstore: FAISS) -> None:
    if VECTOR_STORE_DIR.exists():
        shutil.rmtree(VECTOR_STORE_DIR)
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(VECTOR_STORE_DIR))
    logger.info("Index FAISS sauvegardé dans %s", VECTOR_STORE_DIR)


def load_faiss_index() -> FAISS:
    index_file = VECTOR_STORE_DIR / "index.faiss"
    if not index_file.exists():
        raise FileNotFoundError(
            f"Index FAISS introuvable dans {VECTOR_STORE_DIR}. "
            "Lancez `python rebuild_index.py` pour le reconstruire."
        )
    embeddings = get_embeddings()
    return FAISS.load_local(
        str(VECTOR_STORE_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def index_exists() -> bool:
    return (VECTOR_STORE_DIR / "index.faiss").exists()
