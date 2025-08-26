# app/graphagent/rag_integration.py
import sys
from pathlib import Path

# Path to your rag_core folder
RAG_CORE = Path(r"C:\Users\gmoores\Desktop\AI\RAG\rag_core")
if str(RAG_CORE) not in sys.path:
    sys.path.append(str(RAG_CORE))

try:
    from query_rag_system import query_rag_system
except ImportError as e:
    def query_rag_system(query: str, top_k: int = 5):
        return [f"[RAG_ERROR] query_rag_system not importable from: {RAG_CORE}"]

def search_docs(query: str, k: int = 5):
    """
    Wrapper for GraphAgent node_research calls.
    Returns top-k chunks from the RAG system.
    """
    try:
        hits = query_rag_system(query, top_k=k)
        if not hits:
            return [f"[RAG_EMPTY] No results for query: {query}"]
        return hits
    except Exception as e:
        return [f"[RAG_EXCEPTION] {e}"]
