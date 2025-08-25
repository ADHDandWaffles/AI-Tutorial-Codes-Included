# app/graphagent/rag_integration.py
import sys
from pathlib import Path

# Add rag_core to sys.path
RAG_PATH = Path(r"C:\Users\gmoores\Desktop\AI\RAG\rag_core")
if str(RAG_PATH) not in sys.path:
    sys.path.append(str(RAG_PATH))

try:
    from query_rag_system import query_texts
except ImportError as e:
    def search_docs(query: str, k: int = 3):
        return [f"[RAG_ERROR] query_rag_system not importable: {e}"]
else:
    def search_docs(query: str, k: int = 3):
        try:
            return query_texts(query, top_k=k)
        except Exception as e:
            return [f"[RAG_ERROR] query failed: {e}"]
