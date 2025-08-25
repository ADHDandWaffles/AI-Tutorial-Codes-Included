import os

# Local OpenAI-compatible server (llama.cpp/ollama-like)
API_BASE = os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:1234/v1")
API_KEY  = os.environ.get("LOCAL_LLM_API_KEY", "sk-local")   # placeholder, most local servers ignore it
MODEL    = os.environ.get("LOCAL_LLM_MODEL", "qwen/qwen2.5-vl-7b")

# Default generation settings
TEMPERATURE = float(os.environ.get("LOCAL_LLM_TEMPERATURE", "0.2"))
MAX_TOKENS  = int(os.environ.get("LOCAL_LLM_MAX_TOKENS", "800"))

# RAG defaults
VECTOR_ROOT = os.environ.get("VECTOR_ROOT", r"C:\Users\gmoores\Desktop\AI\RAG")
TOP_K       = int(os.environ.get("RAG_TOP_K", "4"))
