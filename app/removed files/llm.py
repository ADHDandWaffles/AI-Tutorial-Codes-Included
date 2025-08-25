from .config import LLM_ENDPOINT, LLM_API_KEY, LLM_MODEL
from openai import OpenAI

_client = OpenAI(base_url=LLM_ENDPOINT, api_key=LLM_API_KEY)

def list_models() -> list[str]:
    try:
        return sorted([m.id for m in _client.models.list().data])
    except Exception:
        return [LLM_MODEL]

def local_chat(prompt: str, *, system: str | None = None,
               temperature: float = 0.2, max_tokens: int = 512,
               model: str = LLM_MODEL) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        r = _client.chat.completions.create(
            model=model, messages=msgs, temperature=temperature, max_tokens=max_tokens
        )
        return r.choices[0].message.content.strip()

def make_caller(model_name: str = LLM_MODEL, *,
                system_text: str = ("You are GraphAgent, a principled planner-executor. "
                                    "Prefer structured, concise outputs; use provided tools when asked.")
               ):
    def _call(prompt: str, temperature: float = 0.2):
        return local_chat(prompt, system=system_text, temperature=temperature, model=model_name)
    return _call
