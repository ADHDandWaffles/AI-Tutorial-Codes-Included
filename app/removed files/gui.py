import time, threading, tkinter as tk
from tkinter import ttk, messagebox
from .graph import run_graph
from .llm import list_models
from .config import LLM_MODEL

def main():
    root = tk.Tk()
    root.title("GraphAgent (Local LLM)")
    root.minsize(800, 600)

    frm = ttk.Frame(root, padding=10); frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Model:").grid(row=0, column=0, sticky="w")
    models = list_models() or [LLM_MODEL]
    model_var = tk.StringVar(value=LLM_MODEL if LLM_MODEL in models else models[0])
    ttk.Combobox(frm, textvariable=model_var, values=models, state="readonly").grid(row=0, column=1, sticky="ew")

    ttk.Label(frm, text="Task:").grid(row=1, column=0, sticky="nw", pady=(8,0))
    task_txt = tk.Text(frm, height=4, wrap="word"); task_txt.grid(row=1, column=1, sticky="nsew", pady=(8,0))
    task_txt.insert("1.0", "Compare drought-tolerant vs traditional front-yard design in Colorado; compute 5*7")

    run_btn = ttk.Button(frm, text="Run"); run_btn.grid(row=2, column=1, sticky="e", pady=8)

    ttk.Label(frm, text="Result:").grid(row=3, column=0, sticky="nw")
    result = tk.Text(frm, height=10, wrap="word"); result.grid(row=3, column=1, sticky="nsew")
    ttk.Label(frm, text="Evidence:").grid(row=4, column=0, sticky="nw")
    ev = tk.Text(frm, height=6, wrap="word"); ev.grid(row=4, column=1, sticky="nsew")
    ttk.Label(frm, text="Scratch:").grid(row=5, column=0, sticky="nw")
    scratch = tk.Text(frm, height=8, wrap="word"); scratch.grid(row=5, column=1, sticky="nsew")

    for r, w in [(1,1),(3,1),(4,1),(5,1)]:
        frm.rowconfigure(r, weight=1)
    frm.columnconfigure(1, weight=1)

    def log(msg: str): scratch.insert("end", msg+"\n"); scratch.see("end")

    def do_run():
        t = task_txt.get("1.0","end").strip()
        if not t:
            messagebox.showwarning("Missing Task", "Please enter a task.")
            return
        m = model_var.get()
        run_btn.config(state="disabled")
        result.delete("1.0","end"); ev.delete("1.0","end"); scratch.delete("1.0","end")

        def worker():
            t0 = time.time()
            try:
                state = run_graph(t, model_name=m, log=log)
                dt = time.time()-t0
                root.after(0, lambda: (
                    result.insert("end", state.result or "(no result)"),
                    ev.insert("end", "\n".join(state.evidence) or "(no evidence)"),
                    log(f"Done in {dt:.2f}s"),
                    run_btn.config(state="normal")
                ))
            except Exception as e:
                root.after(0, lambda: (run_btn.config(state="normal"),
                                       messagebox.showerror("Error", f"{type(e).__name__}: {e}")))
        threading.Thread(target=worker, daemon=True).start()

    run_btn.config(command=do_run)
    root.mainloop()

if __name__ == "__main__":
    main()
