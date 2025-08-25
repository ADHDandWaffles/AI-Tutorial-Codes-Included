import os

LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:1234/v1")
LLM_API_KEY  = os.getenv("LLM_API_KEY", "sk-local")  # any non-empty string for local servers
LLM_MODEL    = os.getenv("LLM_MODEL", "qwen/qwen2.5-vl-7b")
