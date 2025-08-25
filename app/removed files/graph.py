from typing import Callable, Dict, Optional
from .state import State
from .nodes import node_plan, node_route, node_research, node_math, node_write, node_critic
from .llm import make_caller
from .config import LLM_MODEL

NODES: Dict[str, Callable] = {
    "plan": node_plan, "route": node_route, "research": node_research,
    "math": node_math, "write": node_write, "critic": node_critic
}

def run_graph(task: str, model_name: str = LLM_MODEL, max_steps: int = 12,
              log: Optional[Callable[[str], None]] = None) -> State:
    model = make_caller(model_name)
    state = State(task=task)
    cur = "plan"
    while not state.done and state.step < max_steps:
        state.step += 1
        nxt = NODES[cur](state, model, log)
        if nxt == "end":
            break
        cur = nxt
    return state

def ascii_graph() -> str:
    return "START -> plan -> route -> (research <-> route) & (math <-> route) -> write -> critic -> END"
