"""Démo live Streamlit — assistant Puls-Events (Paris)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from pulsevents.config import CHAT_MODEL, CITY, SEARCH_K
from pulsevents.index import index_exists
from pulsevents.rag import EventRAG

st.set_page_config(page_title="Puls-Events — Assistant culturel", page_icon="🎭", layout="wide")

st.title("Puls-Events — assistant culturel")
st.caption(
    f"POC RAG · événements à {CITY} · LangChain + FAISS + {CHAT_MODEL}. "
    "Chaque question est traitée indépendamment (pas de mémoire de conversation)."
)

if not index_exists():
    st.error("Index FAISS introuvable. Dans le dossier `project`, lancez :")
    st.code("source .venv/bin/activate\npython rebuild_index.py")
    st.stop()


@st.cache_resource(show_spinner="Chargement de l'index FAISS…")
def get_rag() -> EventRAG:
    return EventRAG(k=SEARCH_K)


rag = get_rag()

with st.sidebar:
    st.header("Exemples")
    examples = [
        "Quels concerts me recommandes-tu ce mois-ci à Paris ?",
        "Je cherche une expo d'art contemporain.",
        "Propose-moi une sortie familiale gratuite.",
        "Quels spectacles de théâtre à Paris ?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["prefill"] = ex
    st.markdown("---")
    st.markdown("Pour reconstruire la base : `python rebuild_index.py`")

question = st.chat_input("Votre recherche culturelle…", key="chat")
prefill = st.session_state.pop("prefill", None)
if prefill:
    question = prefill

if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Recherche dans la base vectorielle…"):
            result = rag.ask(question)
        st.write(result.answer)
        if result.sources:
            st.markdown("**Sources (extraits OpenAgenda)**")
            for src in result.sources:
                with st.expander(src.get("title") or src.get("uid")):
                    st.write(f"{src.get('venue')} — {src.get('date_label')}")
                    if src.get("url"):
                        st.write(src["url"])
                    st.write(src.get("excerpt"))
