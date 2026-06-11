"""FAISS-backed knowledge store.

Markdown docs in data/knowledge/ are chunked by heading, embedded with a
local sentence-transformer (all-MiniLM-L6-v2 — no API cost, runs on CPU),
and indexed with FAISS inner-product search over normalised vectors
(cosine similarity). The model and index load lazily on first query.
"""

import json
import re
from pathlib import Path

import numpy as np

from ..config import settings

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model = None
_index = None
_chunks: list[dict] = []


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split on h2/h3 headings; keep the heading with its body."""
    parts = re.split(r"\n(?=#{2,3} )", text)
    chunks = []
    for part in parts:
        body = part.strip()
        if len(body) < 40:
            continue
        heading = body.splitlines()[0].lstrip("# ").strip()
        chunks.append({"source": source, "heading": heading, "text": body})
    return chunks


def _embed(texts: list[str]) -> np.ndarray:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    vecs = _model.encode(texts, normalize_embeddings=True)
    return np.asarray(vecs, dtype="float32")


def build_index() -> int:
    """Embed every knowledge doc and persist the FAISS index. Returns chunk count."""
    import faiss

    docs_dir = settings.data_dir / "knowledge"
    chunks: list[dict] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(chunk_markdown(path.read_text(), path.name))

    vecs = _embed([c["text"] for c in chunks])
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)

    settings.index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(settings.index_dir / "kb.faiss"))
    (settings.index_dir / "chunks.json").write_text(json.dumps(chunks))
    return len(chunks)


def _load():
    global _index, _chunks
    if _index is not None:
        return
    import faiss

    idx_path = settings.index_dir / "kb.faiss"
    if not idx_path.exists():
        raise FileNotFoundError(
            "Knowledge index not built. Run: python -m app.rag.ingest"
        )
    _index = faiss.read_index(str(idx_path))
    _chunks = json.loads((settings.index_dir / "chunks.json").read_text())


def search(query: str, k: int = 4) -> list[dict]:
    _load()
    qvec = _embed([query])
    scores, ids = _index.search(qvec, k)
    results = []
    for score, i in zip(scores[0], ids[0]):
        if i == -1:
            continue
        chunk = _chunks[i]
        results.append(
            {
                "source": chunk["source"],
                "heading": chunk["heading"],
                "text": chunk["text"],
                "score": round(float(score), 4),
            }
        )
    return results
