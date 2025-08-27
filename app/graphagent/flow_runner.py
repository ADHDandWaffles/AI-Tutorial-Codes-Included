import yaml
from pathlib import Path
from . import core

NODE_MAP = {
    "plan": core.node_plan,
    "route": core.node_route,
    "research": core.node_research,
    "math": core.node_math,
    "write": core.node_write,
    "critic": core.node_critic,
}

class FlowRunner:
    def __init__(self, flow_path: str):
        self.flow_path = Path(flow_path)
        with open(self.flow_path, "r", encoding="utf-8") as f:
            self.flow = yaml.safe_load(f)

    def diagram(self) -> str:
        """Return a human-readable diagram of the flow."""
        lines = []
        for edge in self.flow.get("edges", []):
            lines.append(f"{edge['from']} -> {edge['to']}")
        return "\n".join(lines)

    def run(self, task: str):
        """Run the graph dynamically using the YAML definition."""
        state = core.State(task=task)
        cur = "plan"
        max_steps = 12

        while not state.done and state.step < max_steps:
            state.step += 1

            if cur not in NODE_MAP:
                # Log and continue to next edge if available
                state.scratch.append(f"[ERROR] No handler for node: {cur}")
                # try to find a fallback in YAML edges
                next_edges = [e["to"] for e in self.flow.get("edges", []) if e["from"] == cur]
                cur = next_edges[0] if next_edges else "end"
                continue

            try:
                nxt = NODE_MAP[cur](state)
            except Exception as e:
                state.scratch.append(f"[ERROR] Exception in {cur}: {e}")
                nxt = "end"

            if nxt == "end":
                break
            cur = nxt

        return state


if __name__ == "__main__":
    flow_file = Path(__file__).parent.parent / "flows" / "default.yaml"
    runner = FlowRunner(flow_file)
    print("=== FLOW DIAGRAM ===")
    print(runner.diagram())
    print("\n=== SAMPLE RUN ===")
    state = runner.run("Compare xeriscaping vs. traditional lawns in Colorado; compute 5*7")
    print("Result:", state.result)
    print("\nScratch (last 3):", state.scratch[-3:])

