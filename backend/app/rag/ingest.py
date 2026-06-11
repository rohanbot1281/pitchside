"""Build the FAISS knowledge index. Run once: python -m app.rag.ingest"""

from .store import build_index

if __name__ == "__main__":
    n = build_index()
    print(f"Indexed {n} chunks.")
