# app/graphagent/rag_integration.py
import os, sys
RAG_HOME = os.environ.get("RAG_HOME", r"C:\Users\gmoores\Desktop\AI\RAG")
if RAG_HOME and RAG_HOME not in sys.path:
    sys.path.insert(0, RAG_HOME)

from typing import Dict, Any
from rag_core import query_rag_system

def search_docs(
    query: str,
    profile: str,
    recall_k: int,
    rerank_k: int,
    context_k: int,
    rerank: bool = True,
) -> Dict[str, Any]:
    """Thin shim around rag_core.query_rag_system.search."""
    return query_rag_system.search(
        query=query,
        profile=profile,
        recall_k=recall_k,
        rerank_k=rerank_k,
        context_k=context_k,
        rerank=rerank,
    )
