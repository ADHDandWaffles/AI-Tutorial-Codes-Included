# app/graphagent/diagram.py
from __future__ import annotations
import re
from importlib import import_module

FALLBACK_EDGES = {
    "START": ["plan"],
    "plan": ["route"],
    "route": ["research", "math", "write"],
    "research": ["route"],
    "math": ["route"],
    "write": ["critic"],
    "critic": ["END"],
}

def _extract_next(doc: str) -> list[str]:
    if not doc:
        return []
    m = re.search(r"@next:\s*([^\n]+)", doc)
    if not m:
        return []
    raw = m.group(1).strip()
    # allow "a|b|c" or "a, b, c"
    parts = re.split(r"[|,]\s*", raw)
    return [p.strip() for p in parts if p.strip()]

def main():
    core = import_module("app.graphagent.core")
    nodes = getattr(core, "NODES", {})
    edges = {"START": set(), "END": set()}
    # START always points to plan if available
    if "plan" in nodes:
        edges["START"].add("plan")
    # Parse docstrings
    for name, fn in nodes.items():
        doc = (fn.__doc__ or "")
        nxts = _extract_next(doc)
        if not nxts:
            # fallback for this node
            nxts = FALLBACK_EDGES.get(name, [])
        for n in nxts:
            edges.setdefault(name, set()).add(n)
    # Ensure final END edge from critic if missing
    edges.setdefault("critic", set()).update(FALLBACK_EDGES.get("critic", []))

    # Print diagram
    print("FLOW DIAGRAM")
    print("START -> " + ", ".join(sorted(edges.get("START", []))) + "\n")
    visited = set()
    order = ["plan", "route", "research", "math", "write", "critic"]
    for n in order:
        if n in edges:
            outs = ", ".join(sorted(edges[n])) if edges[n] else "(none)"
            print(f"{n} -> {outs}")
            visited.add(n)
    print("\nEND")

    # Optional: print short annotations
    print("\nNOTES")
    for n in order:
        fn = nodes.get(n)
        if not fn: continue
        doc = (fn.__doc__ or "").strip().splitlines()
        if doc:
            # show first non-tag line
            line = next((ln for ln in doc if not ln.strip().startswith("@")), "").strip()
            if line:
                print(f"- {n}: {line}")

if __name__ == "__main__":
    main()
