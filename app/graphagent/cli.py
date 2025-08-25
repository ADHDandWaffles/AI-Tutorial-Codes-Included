# app/graphagent/cli.py
from __future__ import annotations
import argparse, time
from .pipeline import load_pipeline, run_pipeline, ascii_from_spec
from .profile import apply_profile

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=str, default="")
    ap.add_argument("--pipeline", type=str, default="default")
    ap.add_argument("--profile", type=str, default="default")
    args = ap.parse_args()

    apply_profile(args.profile)
    spec = load_pipeline(args.pipeline)

    task = args.task.strip() or input("Enter your task: ").strip() or "Compare xeriscape vs turf; compute 5*7"
    t0 = time.time()
    state = run_pipeline(task, spec)
    dt = time.time() - t0

    print("\n=== GRAPH ===")
    print(ascii_from_spec(spec))
    print(f"\n✅ Result in {dt:.2f}s:\n{state.result}\n")
    print("---- Evidence ----")
    for e in state.evidence:
        print(e)
    print("\n---- Scratch (last 5) ----")
    for s in state.scratch[-5:]:
        print(s)

if __name__ == "__main__":
    main()
