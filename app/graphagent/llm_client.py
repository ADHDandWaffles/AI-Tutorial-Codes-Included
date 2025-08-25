from __future__ import annotations
from openai import OpenAI
from .config import API_BASE, API_KEY, MODEL, TEMPERATURE, MAX_TOKENS

_client = OpenAI(base_url=API_BASE, api_key=API_KEY)

SYSTEM_PROMPT = (
    "You are GraphAgent, a principled planner-executor. "
    "Prefer structured, concise outputs; use provided tools when asked."
)

def call_llm(prompt: str, temperature: float | None = None, system: str | None = SYSTEM_PROMPT) -> str:
    """
    Calls a local OpenAI-compatible /v1/chat/completions.
    Falls back to /v1/completions if chat isn't supported.
    """
    temp = TEMPERATURE if temperature is None else temperature
    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            temperature=temp,
            max_tokens=MAX_TOKENS,
            messages=(
                ([{"role": "system", "content": system}] if system else [])
                + [{"role": "user", "content": prompt}]
            ),
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        # Some local servers only implement /v1/completions
        resp = _client.completions.create(
            model=MODEL,
            temperature=temp,
            max_tokens=MAX_TOKENS,
            prompt=(f"[SYSTEM]\n{system}\n\n[USER]\n{prompt}" if system else prompt),
        )
        return (resp.choices[0].text or "").strip()
