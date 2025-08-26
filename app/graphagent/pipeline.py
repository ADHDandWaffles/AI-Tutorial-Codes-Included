# app/graphagent/pipeline.py
from __future__ import annotations
import os, yaml
from dataclasses import dataclass
from typing import Dict, List
from .core import State, NODE_REGISTRY


@dataclass
class PipelineSpec:
    start: str
    end: str
    edges: Dict[str, List[str]]


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_pipeline(name: str) -> PipelineSpec:
    here = os.path.dirname(__file__)
    p = os.path.join(here, "pipelines", f"{name}.yaml")
    data = _load_yaml(p)
    return PipelineSpec(
        start=data.get("start", "plan"),
        end=data.get("end", "end"),
        edges=data.get("edges", {}),
    )


def run_pipeline(task: str, pipeline: PipelineSpec) -> State:
    state = State(task=task)
    cur = pipeline.start
    max_steps = 24
    steps = 0
    while not state.done and steps < max_steps:
        steps += 1
        fn = NODE_REGISTRY.get(cur)
        if not fn:
            break
        nxt = fn(state)
        if nxt == pipeline.end or nxt == "end":
            state.done = True
            break
        valid = set(pipeline.edges.get(cur, []))
        cur = nxt if nxt in valid or not valid else list(valid)[0]
    return state


def ascii_from_spec(spec: PipelineSpec) -> str:
    lines = ["START -> " + spec.start]
    for k, vs in spec.edges.items():
        if not vs:
            continue
        lines.append(f"{k} -> {', '.join(vs)}")
    lines.append("... -> " + spec.end.upper())
    return "\n".join(lines)
