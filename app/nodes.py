import json
from typing import Callable, Optional
from .state import State
from .docs import search_docs
from .math_tools import safe_eval_math

ModelCall = Callable[[str, float], str]   # (prompt, temperature) -> str
Logger = Optional[Callable[[str], None]]

def node_plan(state: State, model: ModelCall, log: Logger=None) -> str:
    prompt = f"""Plan step-by-step to solve the user task.
Task: {state.task}
Return JSON: {{"subtasks": ["..."], "tools": {{"search": true/false, "math": true/false}}, "success_criteria": ["..."]}}"""
    js = model(prompt, 0.2)
    try:
        plan = json.loads(js[js.find("{"): js.rfind("}")+1])
    except Exception:
        plan = {"subtasks": ["Research", "Synthesize"], "tools": {"search": True, "math": False}, "success_criteria": ["clear answer"]}
    state.plan = json.dumps(plan, indent=2)
    state.scratch.append("PLAN:\n"+state.plan)
    if log: log("PLAN created")
    return "route"

def node_route(state: State, model: ModelCall, log: Logger=None) -> str:
    prompt = f"""You are a router. Decide next node.
Context scratch:\n{chr(10).join(state.scratch[-5:])}
If math needed -> 'math', if research needed -> 'research', if ready -> 'write'.
Return one token from [research, math, write]. Task: {state.task}"""
    choice = (model(prompt, 0.1) or "").lower()
    if "math" in choice and any(ch.isdigit() for ch in state.task):
        if log: log("ROUTE -> math"); return "math"
    if "research" in choice or not state.evidence:
        if log: log("ROUTE -> research"); return "research"
    if log: log("ROUTE -> write")
    return "write"

def node_research(state: State, model: ModelCall, log: Logger=None) -> str:
    prompt = f"""Generate 3 focused search queries for:
Task: {state.task}
Return as JSON list of strings."""
    qjson = model(prompt, 0.2)
    try:
        queries = json.loads(qjson[qjson.find("["): qjson.rfind("]")+1])[:3]
    except Exception:
        queries = [state.task, "background "+state.task, "pros cons "+state.task]
    hits = []
    for q in queries:
        hits.extend(search_docs(q, k=2))
    # de-dupe both new hits and total evidence
    hits = list(dict.fromkeys(hits))
    state.evidence = list(dict.fromkeys(state.evidence + hits))
    state.scratch.append("EVIDENCE:\n- " + "\n- ".join(hits))
    if log: log(f"RESEARCH added {len(hits)} hits")
    return "route"

def node_math(state: State, model: ModelCall, log: Logger=None) -> str:
    prompt = "Extract a single arithmetic expression from this task:\n"+state.task
    expr = model(prompt, 0.0)
    expr = "".join(ch for ch in expr if ch in "0123456789+-*/().%^ ")
    try:
        val = safe_eval_math(expr)
        state.scratch.append(f"MATH: {expr} = {val}")
        if log: log(f"MATH: {expr} = {val}")
    except Exception as e:
        state.scratch.append(f"MATH-ERROR: {expr} ({e})")
        if log: log(f"MATH-ERROR: {expr} ({e})")
    return "route"

def node_write(state: State, model: ModelCall, log: Logger=None) -> str:
    prompt = f"""Write the final answer.
Task: {state.task}
Use the evidence and any math results below, cite inline like [1],[2].
Evidence:\n{chr(10).join(f'[{i+1}] '+e for i,e in enumerate(state.evidence))}
Notes:\n{chr(10).join(state.scratch[-5:])}
Return a concise, structured answer (<= 250 words)."""
    draft = model(prompt, 0.3)
    state.result = draft
    state.scratch.append("DRAFT:\n"+draft)
    if log: log("WRITE produced draft")
    return "critic"

def node_critic(state: State, model: ModelCall, log: Logger=None) -> str:
    prompt = f"""Critique and improve the answer for factuality, missing steps, and clarity.
If fix needed, return improved answer. Else return 'OK'.
Answer:\n{state.result}\nCriteria:\n{state.plan}"""
    crit = model(prompt, 0.2)
    if crit.strip().upper() != "OK" and len(crit) > 30:
        state.result = crit.strip()
        state.scratch.append("REVISED")
        if log: log("CRITIC revised the draft")
    else:
        if log: log("CRITIC OK")
    state.done = True
    return "end"
