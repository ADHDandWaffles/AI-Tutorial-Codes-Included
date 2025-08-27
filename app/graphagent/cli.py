# app/graphagent/cli.py
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

# --- Make external rag_core importable (your RAG_HOME on Desktop) ---
RAG_HOME = os.environ.get("RAG_HOME", r"C:\Users\gmoores\Desktop\AI\RAG")
if RAG_HOME and RAG_HOME not in sys.path:
    sys.path.insert(0, RAG_HOME)

# --- Keep stdout/stderr UTF-8 friendly to avoid UnicodeEncodeError in pipes/console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from .pipeline import load_pipeline, run_pipeline, ascii_from_spec

# Optional: rag_core may not always be present
try:
    from rag_core import query_rag_system  # noqa: F401
except Exception:
    query_rag_system = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=str, default="")
    ap.add_argument("--pipeline", type=str, default="default")
    args = ap.parse_args()

    spec = load_pipeline(args.pipeline)

    task = args.task.strip() or input("Enter your task: ").strip() or \
        "Compare xeriscape vs turf; compute 5*7"

    t0 = time.time()
    try:
        state = run_pipeline(task, spec)
    except Exception as e:
        tb = traceback.format_exc()
        print("\n[ERROR] Pipeline failed:", e, "\n", tb)
        return
    dt = time.time() - t0

    print("\n=== GRAPH ===")
    print(ascii_from_spec(spec))
    print(f"\nResult in {dt:.2f}s:\n{state.result}\n")

    if getattr(state, "evidence", None):
        print("---- Evidence ----")
        for e in state.evidence:
            print(e)

    if getattr(state, "scratch", None):
        print("\n---- Scratch (last 5) ----")
        for s in state.scratch[-5:]:
            print(s)


if __name__ == "__main__":
    main()
