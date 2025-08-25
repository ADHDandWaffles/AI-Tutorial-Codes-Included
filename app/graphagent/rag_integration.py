# app/graphagent/rag_integration.py
from __future__ import annotations
import os, sys

VECTOR_ROOT = os.environ.get("VECTOR_ROOT")
RAG_CORE = os.path.join(VECTOR_ROOT, "rag_core") if VECTOR_ROOT else None
if RAG_CORE and RAG_CORE not in sys.path:
    sys.path.append(RAG_CORE)

_rag_backend = None
_rag_err = None

def _normalize_hits(hits, top_k: int):
    out = []
    for h in (hits or [])[:top_k]:
        if isinstance(h, dict):
            title = (h.get("title") or "").strip()
            preview = (h.get("snippet") or h.get("text") or "").strip()
            src = (h.get("source") or h.get("url") or "").strip()
            piece = " — ".join([p for p in [title, preview[:180] + ("..." if len(preview) > 180 else "")] if p])
            if src:
                piece = (piece + f" ({src})").strip()
            out.append(piece or str(h))
        else:
            out.append(str(h))
    return out

try:
    # Prefer your thin shim if present
    import rag_query as rq
    def _query(q: str, top_k: int = 5):
        return rq.query_texts(q, top_k=top_k)
    _rag_backend = "rag_query"
except Exception as e1:
    try:
        import query_rag_system as qrs
        def _query(q: str, top_k: int = 5):
            return qrs.query_texts(q, top_k=top_k)
        _rag_backend = "query_rag_system"
    except Exception as e2:
        _rag_err = f"{e2.__class__.__name__}: {e2}"

def search_docs(query: str, k: int = 3):
    """
    Returns a list of short strings to cite. On failure, returns a single
    sentinel item like: "[RAG_ERROR] ...", so the agent can continue and annotate.
    """
    if _rag_backend:
        try:
            hits = _query(query, top_k=k)
            return _normalize_hits(hits, k)
        except Exception as e:
            return [f"[RAG_ERROR] {e.__class__.__name__}: {e}"]
    base = RAG_CORE or "<unset VECTOR_ROOT>/rag_core"
    msg = f"[RAG_ERROR] cannot import RAG backend from: {base}. {_rag_err or ''}".strip()
    return [msg]
