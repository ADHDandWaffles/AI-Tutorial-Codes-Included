# app/graphagent/pipeline.py
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Callable

# --- Pull in the real State and node registry from core -----------------------
try:
    from app.graphagent.core import State, NODE_REGISTRY  # nodes live in core.py
except ImportError:
    # Fallback State (matches core.State fields that the CLI relies on)
    @dataclass
    class State:
        task: str
        plan: str = ""
        scratch: List[str] = field(default_factory=list)
        evidence: List[str] = field(default_factory=list)
        result: str = ""
        step: int = 0
        done: bool = False

    NODE_REGISTRY: Dict[str, Callable[[Any], str]] = {}

# Type alias for readability
NodeFn = Callable[[State], str]

# ------------------------------------------------------------------------------
# ----- Citation rendering helpers (you already had these) ---------------------
# ------------------------------------------------------------------------------

SUP_TMPL = '<sup><a href="#fn{n}" id="fnref{n}">{n}</a></sup>'

def build_footnotes_html(citations: Dict[str, Tuple[int, str]]) -> str:
    # Sort by assigned number
    items = sorted(
        ((n, title, url) for url, (n, title) in citations.items()),
        key=lambda x: x[0]
    )
    lis = [
        f'<li id="fn{n}"><a href="{url}" target="_blank" rel="noopener noreferrer">{title or url}</a></li>'
        for n, title, url in items
    ]
    return '<hr/><ol class="footnotes">' + "\n".join(lis) + "</ol>"

def inject_superscripts(text: str, citations: Dict[str, Tuple[int, str]]) -> str:
    """
    Minimal heuristic: append superscripts for all citations after each paragraph.
    If the LLM already inserted [1], [2] markers, you could enhance this to map/replace.
    """
    if not citations:
        return text
    supers = ''.join(
        SUP_TMPL.format(n=n)
        for _, (n, _) in sorted(citations.items(), key=lambda x: x[1][0])
    )
    paras = [p.strip() for p in text.split("\n\n")]
    paras = [p + " " + supers if p else p for p in paras]
    return "\n\n".join(paras)

# ------------------------------------------------------------------------------
# ----- Optional RAG-enrich node (safe even if State lacks fields) -------------
# ------------------------------------------------------------------------------

class RAGEnrich:
    """Prepares citation registry & (optionally) injects superscripts and footnotes.
    Place this BEFORE 'write' so the writer can use the numbering in its prompt.
    Optionally call postprocess() AFTER 'write' to enforce footnotes.
    """

    def __call__(self, state: State) -> State:
        # Build citation registry from state.retrieved (unique canonical URLs)
        # Only run if the attribute exists
        retrieved = getattr(state, "retrieved", None)
        if retrieved is None:
            return state

        reg: Dict[str, Tuple[int, str]] = {}
        n = 1
        for item in retrieved:
            url = (item.get("canonical_url") or "") if isinstance(item, dict) else ""
            title = (item.get("title") or url) if isinstance(item, dict) else url
            if url and url not in reg:
                reg[url] = (n, title)
                n += 1

        setattr(state, "citations", reg)
        return state

    @staticmethod
    def postprocess(state: State) -> State:
        # If the writer didn't add footnotes, append them and inject superscripts at paragraph ends.
        # Only operate when the expected attributes exist.
        final = getattr(state, "final", None)
        citations = getattr(state, "citations", None)
        if final and citations:
            with_sups = inject_superscripts(final, citations)
            foot = build_footnotes_html(citations)
            setattr(state, "final", with_sups + "\n\n" + foot)
        return state

# ------------------------------------------------------------------------------
# ----- Functions that cli.py imports -----------------------------------------
# ------------------------------------------------------------------------------

def load_pipeline(name: str = "default") -> Dict[str, Any]:
    """
    Returns a minimal 'spec' the rest of this file understands.
    Nodes themselves are in app.graphagent.core (NODE_REGISTRY).
    """
    if not NODE_REGISTRY:
        raise RuntimeError("NODE_REGISTRY is empty. Did core.py import correctly?")
    return {
        "name": name,
        "start": "plan",
        "nodes": NODE_REGISTRY,   # dict[str, NodeFn]
        # You can stash options here later if desired.
    }

def run_pipeline(task: str, spec: Dict[str, Any], max_steps: int = 50) -> State:
    """
    Simple driver: start at 'plan' and follow the node names returned by each node
    until a node returns 'end' (or state.done is set).
    """
    nodes: Dict[str, NodeFn] = spec["nodes"]
    current = spec.get("start", "plan")
    state = State(task=task)

    while not getattr(state, "done", False) and state.step < max_steps:
        fn = nodes.get(current)
        if fn is None:
            raise RuntimeError(f"Unknown node '{current}' in pipeline.")
        next_name = (fn(state) or "").strip().lower()
        state.step += 1

        if next_name in ("", "end", "done", "stop"):
            break
        current = next_name

    return state

def ascii_from_spec(spec: Dict[str, Any]) -> str:
    """
    Tiny ASCII sketch of the default graph this spec implies.
    (Static because branching is decided at runtime by 'route'.)
    """
    lines = [
        "plan  --> route",
        "route --> research | math | write",
        "research --> route",
        "math --> route",
        "write --> critic",
        "critic --> end",
    ]
    return "\n".join(lines)

# ------------------------------------------------------------------------------
# Example wiring (if you later add RAGEnrich around write):
# pipeline = [plan -> route -> research/math/write -> critic -> end]
# After write, you could call RAGEnrich.postprocess(state) before returning.
# ------------------------------------------------------------------------------
