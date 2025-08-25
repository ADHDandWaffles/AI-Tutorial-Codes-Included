from __future__ import annotations
from ..registry import register_node
from ..core import State
from ..llm_client import call_llm

@register_node("tx_load")
def node_load_text(state: State) -> str:
    # Expect the task to contain raw text or a path reference.
    # Keep it simple: store the raw task text into scratch as the "doc".
    state.scratch.append("DOC:" + state.task)
    return "tx_classify"

@register_node("tx_classify")
def node_classify(state: State) -> str:
    doc = next((s[4:] for s in state.scratch if s.startswith("DOC:")), "")
    prompt = f"""Classify the following text into the taxonomy [HowTo, Opinion, News, Product, Other].
Return JSON: {{"label":"...", "rationale":"..."}}.
Text:
{doc[:4000]}"""
    js = call_llm(prompt)
    state.scratch.append("TX_JSON:" + js)
    return "tx_write"

@register_node("tx_write")
def node_write_summary(state: State) -> str:
    js = next((s[8:] for s in state.scratch if s.startswith("TX_JSON:")), "{}")
    prompt = f"""Summarize the classification for a non-technical user.
Input JSON:
{js}
Return a concise paragraph."""
    state.result = (call_llm(prompt) or "").strip()
    return "end"
