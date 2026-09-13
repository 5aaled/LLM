"""Contrôle des bibliothèques imposées par le brief (LangChain, FAISS, Mistral)."""

def test_required_libraries_import():
    import faiss
    import langchain
    import mistralai
    from langchain_community.vectorstores import FAISS
    from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

    assert FAISS is not None
    assert ChatMistralAI is not None
    assert MistralAIEmbeddings is not None
    assert langchain.__version__
    assert faiss is not None
    assert mistralai is not None
