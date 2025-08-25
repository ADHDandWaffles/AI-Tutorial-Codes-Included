import time, argparse
from .graph import run_graph, ascii_graph
from .config import LLM_MODEL

def main():
    p = argparse.ArgumentParser(description="GraphAgent CLI (local LLM)")
    p.add_argument("--task", type=str, required=True,
                   help="Task, e.g., 'Compare drought-tolerant vs traditional; compute 5*7'")
    p.add_argument("--model", type=str, default=LLM_MODEL, help="Model ID")
    p.add_argument("--max-steps", type=int, default=12)
    args = p.parse_args()

    print("Model:", args.model)
    print("Task:", args.task)
    t0 = time.time()
    state = run_graph(args.task, model_name=args.model, max_steps=args.max_steps)
    dt = time.time() - t0

    print("\n=== GRAPH ===", ascii_graph())
    print(f"\n✅ Result in {dt:.2f}s:\n{state.result}\n")
    print("---- Evidence ----")
    print("\n".join(state.evidence))
    print("\n---- Scratch (last 5) ----")
    print("\n".join(state.scratch[-5:]))

if __name__ == "__main__":
    main()
