# app/graphagent/rag_integration.py
import os, sys

# --- Ensure rag_core is on the path ---
VECTOR_ROOT = os.environ.get("VECTOR_ROOT", r"C:\Users\gmoores\Desktop\AI\RAG")
rag_core_path = os.path.join(VECTOR_ROOT, "rag_core")
if rag_core_path not in sys.path:
    sys.path.append(rag_core_path)

try:
    from query_rag_system import query_texts
except ImportError as e:
    def search_docs(query: str, k: int = 3) -> list[str]:
        return [f"[RAG_ERROR] query_rag_system not importable from: {rag_core_path}"]
else:
    def search_docs(query: str, k: int = 3) -> list[str]:
        try:
            hits = query_texts(query, top_k=k)
            # hits is probably a list of dicts {"text": ..., "metadata": ...}
            results = []
            for h in hits:
                if isinstance(h, dict):
                    results.append(h.get("text") or str(h))
                else:
                    results.append(str(h))
            return results
        except Exception as e:
            return [f"[RAG_ERROR] {e}"]
