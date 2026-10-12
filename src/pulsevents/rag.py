
from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser   # it takes the output coming from the LLM and turns it into  python string
from langchain_core.prompts import ChatPromptTemplate  # class used to create reusable chat prompt templates with placeholders for dynamic values like the user's question and the retrieved context.
from langchain_mistralai import ChatMistralAI  #LangChain class used to connect the application to a Mistral chat model and generate responses.

from pulsevents.config import CHAT_MODEL, SEARCH_K, require_mistral_key
from pulsevents.index import load_faiss_index

SYSTEM_PROMPT = """Tu es l'assistant culturel de Puls-Events, spécialisé dans les événements à Paris.
Tu recommandes des sorties à partir UNIQUEMENT du CONTEXTE fourni (base vectorielle OpenAgenda).

Règles:
- Réponds en français, de façon claire et utile.
- Ne mentionne que des événements présents dans le CONTEXTE.
- Indique le titre, le lieu, les dates et l'URL s'ils sont disponibles.
- Si plusieurs événements conviennent, proposes-en 2 à 5, classés du plus pertinent au moins pertinent.
- Si le CONTEXTE est insuffisant, dis-le explicitement et ne invente rien.
- N'utilise pas de connaissances générales pour inventer des dates, salles ou tarifs.
"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        (
            "human",
            "Question de l'utilisateur:\n{question}\n\n"
            "CONTEXTE (extraits d'événements):\n{context}\n\n"
            "Réponse:",
        ),
    ]
)


def format_docs(docs: list[Document]) -> str:   # Take the documents/chunks retrieved from FAISS and turn them into one well-organized text string that can be inserted into the {context} placeholder of the prompt.
    blocks = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        header = (
            f"[Extrait {i}] {meta.get('title', '')} | "
            f"{meta.get('venue', '')} | {meta.get('city', '')} {meta.get('postal_code', '')} | "
            f"{meta.get('date_start') or meta.get('date_label', '')} | {meta.get('url', '')}"
        )
        blocks.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks) if blocks else "Aucun extrait pertinent."


class RAGResult:  # The main goal of RAG Result is to create a simple object that stores the final result of one user question.
    """Résultat d'une question : texte + sources."""

    def __init__(
        self,
        question: str,
        answer: str,
        sources: list[dict[str, Any]] | None = None,
    ):
        self.question = question
        self.answer = answer
        self.sources = sources if sources is not None else []


class EventRAG:   # responsible for running the whole RAG process when the user asks a question.


    def __init__(self, k: int = SEARCH_K):
        self.k = k
        self.vectorstore = load_faiss_index()
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": k})
        self.llm = ChatMistralAI(
            model=CHAT_MODEL,
            api_key=require_mistral_key(),
            temperature=0.2,   # Temperature controls how much randomness/variation the LLM uses when generating its answer.
            max_retries=8,
        )

    def retrieve(self, question: str) -> list[Document]:
        return self.retriever.invoke(question)

    def ask(self, question: str) -> RAGResult:
        docs = self.retrieve(question)
        context = format_docs(docs)
        answer = (PROMPT | self.llm | StrOutputParser()).invoke(
            {"question": question, "context": context}
        )
        sources = []
        seen = set()
        for doc in docs:
            uid = str(doc.metadata.get("uid"))
            if uid in seen:
                continue
            seen.add(uid)
            sources.append(
                {
                    "uid": uid,
                    "title": doc.metadata.get("title"),
                    "venue": doc.metadata.get("venue"),
                    "date_label": doc.metadata.get("date_start") or doc.metadata.get("date_label"),
                    "url": doc.metadata.get("url"),
                    "city": doc.metadata.get("city"),
                    "excerpt": doc.page_content[:400],
                }
            )
        return RAGResult(question=question, answer=answer, sources=sources)
