from __future__ import annotations
import os, sys
from typing import List, Tuple
from .config import VECTOR_ROOT, TOP_K

# Ensure your central RAG module is importable:
#   VECTOR_ROOT/rag_core/query_rag_system.py   (you already have this)
RAG_CORE = os.path.join(VECTOR_ROOT, "rag_core")
if RAG_CORE not in sys.path:
    sys.path.append(RAG_CORE)

try:
    from query_rag_system import query_rag_system
except Exception as e:
    query_rag_system = None  # we'll guard below

def search_docs(query: str, k: int | None = None) -> List[str]:
    """
    Use your central vector DB via query_rag_system().
    Returns a small list of text snippets (with source URL when available).
    """
    topk = k or TOP_K
    if query_rag_system is None:
        return [f"[RAG_ERROR] query_rag_system not importable from: {RAG_CORE}"]

    try:
        # query_rag_system returns: (answer_text, unique_chunks)
        # where unique_chunks is a list of (chunk_text, metadata_dict)
        _answer, sources = query_rag_system(query, max_tokens=0, top_k=topk, temp=0.0, top_p=1.0)
        out: List[str] = []
        for chunk, meta in (sources or [])[:topk]:
            src = ""
            if isinstance(meta, dict):
                src = meta.get("source") or meta.get("url") or ""
            if src:
                out.append(f"{chunk.strip()}\n(Source: {src})")
            else:
                out.append(chunk.strip())
        return out or ["[RAG] No results."]
    except Exception as e:
        return [f"[RAG_ERROR] {e}"]
