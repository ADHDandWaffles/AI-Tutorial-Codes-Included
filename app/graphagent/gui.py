# app/gui.py
import os, time, tkinter as tk
from tkinter import scrolledtext, messagebox

from app.core import run_graph  # adjust import if needed

MODEL = os.getenv("LLM_MODEL", "qwen/qwen2.5-vl-7b")
ENDPOINT = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:1234/v1")

def run_task():
    task = entry.get("1.0", "end").strip()
    if not task:
        messagebox.showwarning("Missing task", "Please enter a task.")
        return
    btn.config(state="disabled")
    out.delete("1.0", "end")
    out.insert("end", f"Model: {MODEL}\nTask: {task}\n\nRunning...\n")
    root.update_idletasks()
    t0 = time.time()
    state = run_graph(task)
    dt = time.time() - t0
    out.insert("end", f"\n=== GRAPH === START -> plan -> route -> (research <-> route) & (math <-> route) -> write -> critic -> END\n\n")
    out.insert("end", f"✅ Result in {dt:.2f}s:\n{state.result or '(no result)'}\n\n")
    out.insert("end", "---- Evidence ----\n")
    for e in state.evidence:
        out.insert("end", e + "\n")
    out.insert("end", "\n---- Scratch (last 5) ----\n")
    for line in state.scratch[-5:]:
        out.insert("end", line + "\n")
    btn.config(state="normal")

root = tk.Tk()
root.title("GraphAgent")
frame = tk.Frame(root); frame.pack(fill="both", expand=True, padx=12, pady=12)

tk.Label(frame, text="Enter task:").pack(anchor="w")
entry = scrolledtext.ScrolledText(frame, height=5, width=80); entry.pack(fill="x")

btn = tk.Button(frame, text="Run", command=run_task)
btn.pack(pady=8, anchor="w")

out = scrolledtext.ScrolledText(frame, height=22, width=100)
out.pack(fill="both", expand=True)

root.mainloop()
