# app/graphagent/core.py
from __future__ import annotations

import ast, json, os
from dataclasses import dataclass, field
from typing import List, Dict, Callable

from .llm_client import call_llm
from .rag_integration import search_docs  # correct import


# --- math sandbox ---
def safe_eval_math(expr: str) -> str:
    node = ast.parse(expr, mode="eval")
    allowed = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
        ast.USub, ast.UAdd, ast.FloorDiv
    )

    def check(n):
        if not isinstance(n, allowed):
            raise ValueError("Unsafe expression")
        for c in ast.iter_child_nodes(n):
            check(c)

    check(node)
    return str(eval(compile(node, "<math>", "eval"), {"__builtins__": {}}, {}))


# --- agent state ---
@dataclass
class State:
    task: str
    plan: str = ""
    scratch: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)  # "Title — URL :: snippet"
    result: str = ""
    step: int = 0
    done: bool = False


# --- nodes ---
def node_plan(state: State) -> str:
    prompt = f"""Plan step-by-step to solve the user task.
Task: {state.task}
Return JSON only: {{"subtasks":["..."],"tools":{{"search":true/false,"math":true/false}},"success_criteria":["..."]}}"""
    js = call_llm(prompt)
    try:
        plan = json.loads(js[js.find("{"): js.rfind("}") + 1])
    except Exception:
        plan = {
            "subtasks": ["Research", "Synthesize"],
            "tools": {"search": True, "math": False},
            "success_criteria": ["clear answer"]
        }
    state.plan = json.dumps(plan, indent=2)
    state.scratch.append("PLAN:\n" + state.plan)
    return "route"


def node_route(state: State) -> str:
    prompt = f"""You are a router. Decide next node.
Context scratch (last 3):\n{chr(10).join(state.scratch[-3:])}
If math needed -> 'math'; if research needed -> 'research'; if ready -> 'write'.
Return one token from [research, math, write].
Task: {state.task}"""
    choice = (call_llm(prompt) or "").lower()

    if "math" in choice and any(ch.isdigit() for ch in state.task):
        return "math"
    if "research" in choice and not state.evidence:
        return "research"
    return "write"


def node_research(state: State) -> str:
    """
    Combine pipeline query expansion + your local RAG:
    - Generate 3 focused queries (LLM)
    - RAG for each query + one baseline call on the original task
    - Merge by canonical_url into doc-level evidence lines (used for [1],[2] in Answer)
    """
    prompt = f"""Generate 3 focused search queries for:
Task: {state.task}
Return as a JSON list of strings."""
    qjson = call_llm(prompt)
    try:
        queries = json.loads(qjson[qjson.find("["): qjson.rfind("]") + 1])[:3]
    except Exception:
        queries = [state.task, "background " + state.task, "pros cons " + state.task]

    # knobs passed from the Tk UI (with safe defaults)
    prof       = os.environ.get("RAG_UI_PROFILE", "") or ""
    recall_k   = int(os.environ.get("RAG_UI_RECALL_K",  "40"))
    rerank_k   = int(os.environ.get("RAG_UI_RERANK_K",  "12"))
    context_k  = int(os.environ.get("RAG_UI_CONTEXT_K", "8"))
    use_rerank = os.environ.get("RAG_UI_RERANK", "1").lower() in ("1","true","yes","y")

    def run_rag(q: str):
        try:
            out = search_docs(
                query=q,
                profile=prof,
                recall_k=recall_k,
                rerank_k=rerank_k,
                context_k=context_k,
                rerank=use_rerank,
            )
            return (out or {}).get("results", []) or []
        except TypeError:
            try:
                return search_docs(q) or []
            except Exception:
                return []

    ctx_all = []
    for q in queries:
        ctx_all.extend(run_rag(q))
    ctx_all.extend(run_rag(state.task))  # baseline

    seen_urls = set()
    lines = []
    for c in ctx_all:
        url = (c or {}).get("canonical_url") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title = (c or {}).get("title") or url
        snip  = ((c or {}).get("text") or "").replace("\n", " ").strip()
        if len(snip) > 240:
            snip = snip[:240].rstrip() + "…"
        lines.append(f"{title} — {url} :: {snip}")

    if lines:
        state.evidence.extend(lines[:12])
        state.scratch.append("EVIDENCE:\n- " + "\n- ".join(lines[:6]))
    return "route"


def node_math(state: State) -> str:
    prompt = "Extract a single arithmetic expression from this task:\n" + state.task
    expr = call_llm(prompt)
    expr = "".join(ch for ch in expr if ch in "0123456789+-*/().%^ ")
    try:
        val = safe_eval_math(expr)
        state.scratch.append(f"MATH: {expr} = {val}")
    except Exception as e:
        state.scratch.append(f"MATH-ERROR: {expr} ({e})")
    return "route"


def node_write(state: State) -> str:
    has_real_evidence = any(" — http" in e for e in state.evidence)
    preface = ""
    if not has_real_evidence:
        preface = (
            "Note: The local RAG index returned no documents. "
            "The following answer is based on general model knowledge and may require verification.\n\n"
        )

    src_lines = [f"[{i+1}] {e}" for i, e in enumerate(state.evidence[:8])]

    prompt = f"""Write the final answer.
{preface}Task: {state.task}
Use the evidence and any math results below, cite inline like [1],[2].
Evidence:
{chr(10).join(src_lines)}
Notes:
{chr(10).join(state.scratch[-5:])}
Return a concise, structured answer."""
    draft = call_llm(prompt, temperature=0.3)
    state.result = (draft or "").strip()
    state.scratch.append("DRAFT:\n" + state.result)
    return "critic"


def node_critic(state: State) -> str:
    prompt = f"""Critique and improve the answer for factuality, missing steps, and clarity.
If fix needed, return improved answer. Else return 'OK'.
Answer:
{state.result}
Criteria:
{state.plan}"""
    crit = (call_llm(prompt) or "").strip()
    if crit.upper() != "OK" and len(crit) > 20:
        state.result = crit
        state.scratch.append("REVISED")
    state.done = True
    return "end"


# Registry consumed by pipeline.py
NODE_REGISTRY: Dict[str, Callable[[State], str]] = {
    "plan": node_plan,
    "route": node_route,
    "research": node_research,
    "math": node_math,
    "write": node_write,
    "critic": node_critic,
}
