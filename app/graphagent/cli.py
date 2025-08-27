# app/graphagent/cli.py
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

from .pipeline import load_pipeline, run_pipeline, ascii_from_spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=str, default="")
    ap.add_argument("--pipeline", type=str, default="default")
    ap.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON (graph, result, evidence, scratch, elapsed_sec)",
    )
    args = ap.parse_args()

    # Load pipeline spec
    try:
        spec = load_pipeline(args.pipeline)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] Failed to load pipeline '{args.pipeline}': {e}\n{tb}")
        sys.exit(1)

    # Determine task
    task = (args.task or "").strip()
    if not task:
        try:
            task = input("Enter your task: ").strip()
        except EOFError:
            task = ""
    if not task:
        task = "Compare xeriscape vs turf; compute 5*7"

    want_json = args.json or os.environ.get("RAG_UI_JSON", "").lower() in ("1", "true", "yes", "y")

    t0 = time.time()
    try:
        state = run_pipeline(task, spec)
    except Exception as e:
        tb = traceback.format_exc()
        if want_json:
            err_payload = {
                "error": f"Pipeline failed: {e}",
                "traceback": tb,
            }
            print(json.dumps(err_payload, ensure_ascii=False))
        else:
            print(f"\n[ERROR] Pipeline failed: {e}\n{tb}")
        sys.exit(1)

    dt = time.time() - t0

    # Build structured payload
    payload = {
        "graph": ascii_from_spec(spec),
        "result": getattr(state, "result", ""),
        "evidence": list(getattr(state, "evidence", [])),
        "scratch": list(getattr(state, "scratch", []))[-5:],
        "elapsed_sec": dt,
    }

    if want_json:
        print(json.dumps(payload, ensure_ascii=False))
        return

    # Legacy pretty text output
    print("\n=== GRAPH ===")
    print(payload["graph"])
    print(f"\nResult in {dt:.2f}s:\n{payload['result']}\n")

    if payload["evidence"]:
        print("---- Evidence ----")
        for e in payload["evidence"]:
            print(e)

    if payload["scratch"]:
        print("\n---- Scratch (last 5) ----")
        for s in payload["scratch"]:
            print(s)


if __name__ == "__main__":
    main()
