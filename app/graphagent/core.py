# app/graphagent/core.py
from __future__ import annotations
import ast, json, math
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Any
from .llm_client import call_llm
from .rag_integration import search_docs
from .registry import register_node

# --- math sandbox ---
def safe_eval_math(expr: str) -> str:
    """
    @node: math_sandbox
    Safely evaluate a simple arithmetic expression (no names/calls).
    @next: route
    """
    node = ast.parse(expr, mode="eval")
    allowed = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
        ast.USub, ast.UAdd, ast.FloorDiv
    )
    def check(n):
        if not isinstance(n, allowed): raise ValueError("Unsafe expression")
        for c in ast.iter_child_nodes(n): check(c)
    check(node)
    return str(eval(compile(node, "<math>", "eval"), {"__builtins__": {}}, {}))

# --- agent state ---
@dataclass
class State:
    """
    @node: state
    Lightweight state container passed between nodes.
    @next: plan
    """
    task: str
    plan: str = ""
    scratch: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    result: str = ""
    step: int = 0
    done: bool = False

# --- nodes ---
@register_node("plan")
def node_plan(state: State) -> str:
    """
    @node: plan
    Plan the approach; output JSON of subtasks + tool flags.
    @next: route
    """
    prompt = f"""Plan step-by-step to solve the user task.
Task: {state.task}
Return JSON only: {{"subtasks":["..."],"tools":{{"search":true/false,"math":true/false}},"success_criteria":["..."]}}"""
    js = call_llm(prompt)
    try:
        plan = json.loads(js[js.find("{"): js.rfind("}")+1])
    except Exception:
        plan = {"subtasks": ["Research","Synthesize"], "tools": {"search": True, "math": False}, "success_criteria": ["clear answer"]}
    state.plan = json.dumps(plan, indent=2)
    state.scratch.append("PLAN:\n"+state.plan)
    return "route"

@register_node("route")
def node_route(state: State) -> str:
    """
    @node: route
    Decide next step based on scratch/evidence.
    @next: research|math|write
    """
    prompt = f"""You are a router. Decide next node.
Context scratch (last 3):\n{chr(10).join(state.scratch[-3:])}
If math needed -> 'math'; if research needed -> 'research'; if ready -> 'write'.
Return one token from [research, math, write].
Task: {state.task}"""
    choice = (call_llm(prompt) or "").lower()

    if "math" in choice and any(ch.isdigit() for ch in state.task):
        return "math"

    if "research" in choice:
        recent_scratch = "\n".join(state.scratch[-4:])
        if "[RAG_ERROR]" in recent_scratch:
            return "write"
        if not state.evidence:
            return "research"
        return "write"

    if not state.evidence:
        return "research"
    return "write"

@register_node("research")
def node_research(state: State) -> str:
    """
    @node: research
    Generate search queries and fetch evidence from RAG; de-dupe.
    @next: route
    """
    prompt = f"""Generate 3 focused search queries for:
Task: {state.task}
Return as a JSON list of strings."""
    qjson = call_llm(prompt)
    try:
        queries = json.loads(qjson[qjson.find("["): qjson.rfind("]")+1])[:3]
    except Exception:
        queries = [state.task, "background "+state.task, "pros cons "+state.task]

    hits = []
    for q in queries:
        hits.extend(search_docs(q, k=2))
    seen = set(); uniq = []
    for h in hits:
        if h not in seen:
            seen.add(h); uniq.append(h)
    state.evidence.extend(uniq)
    state.scratch.append("EVIDENCE:\n- " + "\n- ".join(uniq[:6]))
    return "route"

@register_node("math")
def node_math(state: State) -> str:
    """
    @node: math
    Extract and safely evaluate one arithmetic expression.
    @next: route
    """
    prompt = "Extract a single arithmetic expression from this task:\n"+state.task
    expr = call_llm(prompt)
    expr = "".join(ch for ch in expr if ch in "0123456789+-*/().%^ ")
    try:
        val = safe_eval_math(expr)
        state.scratch.append(f"MATH: {expr} = {val}")
    except Exception as e:
        state.scratch.append(f"MATH-ERROR: {expr} ({e})")
    return "route"

@register_node("write")
def node_write(state: State) -> str:
    """
    @node: write
    Draft the final answer using evidence and notes; if no RAG evidence, preface that it uses model knowledge.
    @next: critic
    """
    has_real_evidence = any(e and not str(e).startswith("[RAG_ERROR]") for e in state.evidence)

    preface = ""
    if not has_real_evidence:
        preface = (
            "Note: The local RAG index returned no documents for this query. "
            "The following answer is based on general model knowledge and may require verification.\n\n"
        )

    prompt = f"""Write the final answer.
{preface}Task: {state.task}
Use the evidence and any math results below, cite inline like [1],[2] when evidence exists.
Evidence:\n{chr(10).join(f'[{i+1}] '+e for i,e in enumerate(state.evidence[:8]))}
Notes:\n{chr(10).join(state.scratch[-5:])}
Return a concise, structured answer."""
    draft = call_llm(prompt, temperature=0.3)
    state.result = (draft or "").strip()
    state.scratch.append("DRAFT:\n"+state.result)
    return "critic"

@register_node("critic")
def node_critic(state: State) -> str:
    """
    @node: critic
    Improve/verify the draft for clarity and factuality; finish.
    @next: end
    """
    prompt = f"""Critique and improve the answer for factuality, missing steps, and clarity.
If fix needed, return improved answer. Else return 'OK'.
Answer:\n{state.result}\nCriteria:\n{state.plan}"""
    crit = (call_llm(prompt) or "").strip()
    if crit.upper() != "OK" and len(crit) > 20:
        state.result = crit
        state.scratch.append("REVISED")
    state.done = True
    return "end"

NODES: Dict[str, Callable[[State], str]] = {
    "plan": node_plan, "route": node_route, "research": node_research,
    "math": node_math, "write": node_write, "critic": node_critic
}

def run_graph(task: str) -> State:
    """
    @node: runner
    Orchestrate node execution until 'end' or max steps.
    @next: end
    """
    state = State(task=task)
    cur = "plan"
    max_steps = 12
    while not state.done and state.step < max_steps:
        state.step += 1
        nxt = NODES[cur](state)
        if nxt == "end": break
        cur = nxt
    return state

def ascii_graph() -> str:
    """
    @node: ascii_graph
    Simple ASCII summary of the flow.
    @next: end
    """
    return "START -> plan -> route -> (research <-> route) & (math <-> route) -> write -> critic -> END"
