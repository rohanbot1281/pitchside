"""RAG search tool — thin wrapper over the FAISS store."""

from ..rag import store


def search_knowledge(query: str, top_k: int = 4) -> dict:
    try:
        results = store.search(query, k=top_k)
    except FileNotFoundError as e:
        return {"error": str(e)}
    return {"query": query, "results": results}
