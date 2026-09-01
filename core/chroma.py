import os
import logging
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger=logging.getLogger("agrosafety.chroma")

@lru_cache(maxsize=32)
def get_embeddings():
    """
    Singleton/cache de embeddings.
    Los embeddings son iguales para todos los tenants.
    """
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001"
    )

@lru_cache(maxsize=32)
def get_vector_store(slug:str)->Chroma:
    """
    Devuelve el vector store correspondiente al tenant.

    Cada tenant tiene su propia colección de Chroma.
    """
    embeddings=get_embeddings()
    persist_dir=os.environ.get(
        "CHROMA_DIR",
        "db_agro_docs"
    )
    collection_name=f"agro_{slug}"
    logger.info(
        "Inicializando Chroma | tenant=%s | collection=%s | dir=%s",
        slug,
        collection_name,
        persist_dir,
    )
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )

@lru_cache(maxsize=32)
def get_retriever(slug:str):
    """
    Devuelve el retriever correspondiente al tenant.
    """
    vector_store=get_vector_store(slug)
    return vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 8,
            "fetch_k": 20,
        },
    )