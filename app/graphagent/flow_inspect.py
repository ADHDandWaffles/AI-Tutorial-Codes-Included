# app/graphagent/flow_inspect.py
from __future__ import annotations
import argparse, importlib.util, os, ast, textwrap, json
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

@dataclass
class NodeInfo:
    node_name: str          # e.g., "plan"
    func_name: str          # e.g., "node_plan"
    doc: str                # short description from docstring (first line)
    returns: Set[str]       # literal return targets found in AST (e.g., {"route","end"})

def _find_module_source(modname: str) -> str:
    spec = importlib.util.find_spec(modname)
    if spec is None or not spec.origin:
        raise RuntimeError(f"Cannot find module: {modname}")
    return spec.origin

class _CoreVisitor(ast.NodeVisitor):
    def __init__(self):
        self.func_defs: Dict[str, ast.FunctionDef] = {}
        self.func_docs: Dict[str, str] = {}
        self.func_returns: Dict[str, Set[str]] = {}
        self.nodes_map: Dict[str, str] = {}  # "plan" -> "node_plan"
        self.start_node: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.func_defs[node.name] = node
        doc = ast.get_docstring(node) or ""
        if doc:
            # Use only the first line for a concise annotation
            self.func_docs[node.name] = doc.strip().splitlines()[0].strip()
        # Collect literal returns
        rs: Set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return):
                v = sub.value
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    rs.add(v.value)
        if rs:
            self.func_returns[node.name] = rs
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Parse NODES = {"plan": node_plan, ...}
        try:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "NODES":
                    if isinstance(node.value, ast.Dict):
                        for k, v in zip(node.value.keys, node.value.values):
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                if isinstance(v, ast.Name):
                                    self.nodes_map[k.value] = v.id
        except Exception:
            pass
        # Detect start node from assignments like: cur = "plan"
        try:
            if any(isinstance(t, ast.Name) and t.id == "cur" for t in node.targets):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    self.start_node = node.value.value
        except Exception:
            pass
        self.generic_visit(node)

def _inspect_core(modname: str) -> Tuple[str, List[NodeInfo], Dict[str, str]]:
    src_path = _find_module_source(modname)
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src, filename=src_path)
    v = _CoreVisitor()
    v.visit(tree)

    # Build node infos in the NODES order we find
    infos: List[NodeInfo] = []
    for node_name, func_name in v.nodes_map.items():
        doc = v.func_docs.get(func_name, "")
        returns = v.func_returns.get(func_name, set())
        infos.append(NodeInfo(node_name=node_name, func_name=func_name, doc=doc, returns=returns))

    start = v.start_node or ("plan" if "plan" in v.nodes_map else (next(iter(v.nodes_map.keys()), "")))
    return start, infos, v.nodes_map

def _as_text(start: str, infos: List[NodeInfo], nodes_map: Dict[str, str]) -> str:
    known = set(nodes_map.keys())
    lines: List[str] = []
    lines.append("FLOW DIAGRAM")
    lines.append(f"START -> {start}")
    for info in infos:
        lines.append("")
        header = f"[{info.node_name}]"
        if info.doc:
            header += f" — {info.doc}"
        lines.append(header)
        if not info.returns:
            lines.append("  (no explicit literal returns found; next step may be decided at runtime)")
            continue
        for r in sorted(info.returns):
            if r in known:
                lines.append(f"  └─→ {r}")
            elif r.lower() == "end":
                lines.append("  └─→ END")
            else:
                lines.append(f"  └─→ {r} (unknown target)")
    lines.append("")
    lines.append("END")
    return "\n".join(lines)

def _as_mermaid(start: str, infos: List[NodeInfo], nodes_map: Dict[str, str]) -> str:
    known = set(nodes_map.keys())
    out = ["flowchart TD", f"  START([START]) --> {start}"]
    # Node labels with docs
    for info in infos:
        label = info.node_name
        desc = info.doc.replace('"', r"\"") if info.doc else ""
        if desc:
            out.append(f'  {label}["{label}: {desc}"]')
        else:
            out.append(f'  {label}["{label}"]')
    out.append("  END([END])")
    # Edges
    for info in infos:
        if not info.returns:
            continue
        for r in info.returns:
            if r in known:
                out.append(f"  {info.node_name} --> {r}")
            elif r.lower() == "end":
                out.append(f"  {info.node_name} --> END")
            else:
                out.append(f'  %% {info.node_name} -> {r} (unknown)')
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(description="Inspect node flow and produce a simple diagram.")
    ap.add_argument("--module", default="app.graphagent.core", help="Python module path to inspect")
    ap.add_argument("--format", choices=["text","mermaid","json"], default="text")
    ap.add_argument("--out", default="", help="Optional output file")
    args = ap.parse_args()

    start, infos, nodes_map = _inspect_core(args.module)
    if args.format == "text":
        s = _as_text(start, infos, nodes_map)
    elif args.format == "mermaid":
        s = _as_mermaid(start, infos, nodes_map)
    else:
        s = json.dumps({
            "start": start,
            "nodes": [
                {
                    "name": i.node_name,
                    "func": i.func_name,
                    "doc": i.doc,
                    "returns": sorted(list(i.returns))
                } for i in infos
            ]
        }, indent=2)

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"[OK] Wrote {args.out}")
    else:
        print(s)

if __name__ == "__main__":
    main()

