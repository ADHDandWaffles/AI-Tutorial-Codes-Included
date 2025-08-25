# app/cli.py

import os, sys, argparse, time

def main(argv=None):
    parser = argparse.ArgumentParser(description="GraphAgent CLI")
    parser.add_argument("--task", type=str, default=None, help="Task text. If omitted, you will be prompted.")
    parser.add_argument("--interactive", action="store_true",
                        help="Force interactive prompt loop (ask repeatedly until blank).")
    parser.add_argument("--model", type=str, default=os.getenv("LLM_MODEL", "qwen/qwen2.5-vl-7b"))
    parser.add_argument("--endpoint", type=str, default=os.getenv("LLM_ENDPOINT", "http://127.0.0.1:1234/v1"))
    args = parser.parse_args(argv)

    # ---- import your core runner (adjust the import path to match your project) ----
    # Example if you put it under app/core.py:
    try:
        from app.core import run_graph   # <-- change if your function lives elsewhere
    except Exception:
        # Fallbacks you may have:
        try:
            from graphagent.core import run_graph  # if you named the package differently
        except Exception as e:
            print(f"[ERROR] Couldn't import run_graph: {e}", file=sys.stderr)
            return 1

    # Make endpoint/model available to your core if it reads env vars
    os.environ["LLM_ENDPOINT"] = args.endpoint
    os.environ["LLM_MODEL"] = args.model

    def handle_one(task_text: str):
        print(f"Model: {args.model}")
        print(f"Task: {task_text}\n")
        t0 = time.time()
        state = run_graph(task_text)  # your core function should not require an API key now
        dt = time.time() - t0
        print("\n=== GRAPH === START -> plan -> route -> (research <-> route) & (math <-> route) -> write -> critic -> END\n")
        print(f"✅ Result in {dt:.2f}s:\n{state.result or '(no result)'}\n")
        print("---- Evidence ----")
        for e in state.evidence:
            print(e)
        print("\n---- Scratch (last 5) ----")
        for line in state.scratch[-5:]:
            print(line)

    # Interactive mode (explicit or no task provided)
    if args.interactive or not args.task:
        print("GraphAgent interactive mode. Press ENTER on an empty line to quit.\n")
        while True:
            try:
                task = input("📝 Enter your task: ").strip()
            except EOFError:
                break
            if not task:
                break
            handle_one(task)
            print("\n" + "-"*60 + "\n")
        return 0

    # Single one-shot
    handle_one(args.task)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
