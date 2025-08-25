# app/graphagent/gui.py
from __future__ import annotations
import os, threading, traceback
import tkinter as tk
from tkinter import ttk, messagebox

# Internal imports (reuse your existing modules)
from .pipeline import load_pipeline, run_pipeline, ascii_from_spec
from .profile import apply_profile

# ---- helpers ----
HERE = os.path.dirname(__file__)
PIPELINES_DIR = os.path.join(HERE, "pipelines")
PROFILES_DIR = os.path.join(HERE, "profiles")

def _list_yaml_names(folder: str) -> list[str]:
    try:
        names = []
        for f in os.listdir(folder):
            if f.lower().endswith((".yml", ".yaml")):
                names.append(os.path.splitext(f)[0])
        return sorted(names)
    except Exception:
        return []

class GraphAgentGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GraphAgent")
        self.geometry("900x650")
        self.minsize(760, 520)

        # state
        self._run_thread: threading.Thread | None = None
        self._is_running = False

        # top controls
        top = ttk.Frame(self, padding=10)
        top.pack(side="top", fill="x")

        ttk.Label(top, text="Pipeline:").grid(row=0, column=0, sticky="w", padx=(0,6))
        self.pipeline_cbx = ttk.Combobox(top, state="readonly", width=28)
        self.pipeline_cbx.grid(row=0, column=1, sticky="w")

        ttk.Label(top, text="Profile:").grid(row=0, column=2, sticky="w", padx=(16,6))
        self.profile_cbx = ttk.Combobox(top, state="readonly", width=28)
        self.profile_cbx.grid(row=0, column=3, sticky="w")

        self.refresh_btn = ttk.Button(top, text="Refresh lists", command=self.refresh_lists)
        self.refresh_btn.grid(row=0, column=4, sticky="w", padx=(16,0))

        # env display
        env = ttk.Frame(self, padding=(10,0,10,10))
        env.pack(side="top", fill="x")
        self.endpoint_var = tk.StringVar(value=os.environ.get("LLM_ENDPOINT", ""))
        self.model_var = tk.StringVar(value=os.environ.get("LLM_MODEL", ""))

        ttk.Label(env, text="Endpoint:").grid(row=0, column=0, sticky="w")
        self.endpoint_lbl = ttk.Label(env, textvariable=self.endpoint_var, foreground="#555")
        self.endpoint_lbl.grid(row=0, column=1, sticky="w", padx=(4,0))

        ttk.Label(env, text="Model:").grid(row=0, column=2, sticky="w", padx=(16,6))
        self.model_lbl = ttk.Label(env, textvariable=self.model_var, foreground="#555")
        self.model_lbl.grid(row=0, column=3, sticky="w")

        # task input
        task_frame = ttk.LabelFrame(self, text="Task", padding=10)
        task_frame.pack(side="top", fill="x", padx=10, pady=(0,10))
        self.task_txt = tk.Text(task_frame, height=4, wrap="word")
        self.task_txt.pack(fill="x")
        self.task_txt.insert("1.0", "Compare xeriscape vs traditional lawn in Colorado; compute 5*7")

        # run buttons
        btns = ttk.Frame(self, padding=(10,0,10,10))
        btns.pack(side="top", fill="x")
        self.run_btn = ttk.Button(btns, text="Run", command=self.on_run_clicked)
        self.run_btn.pack(side="left")
        self.preview_btn = ttk.Button(btns, text="Preview Graph", command=self.on_preview_graph)
        self.preview_btn.pack(side="left", padx=8)
        self.copy_btn = ttk.Button(btns, text="Copy Result", command=self.copy_result)
        self.copy_btn.pack(side="left", padx=8)

        # notebook with outputs
        self.nb = ttk.Notebook(self)
        self.nb.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        self.result_txt = self._make_tab("Result")
        self.evidence_txt = self._make_tab("Evidence")
        self.scratch_txt = self._make_tab("Scratch")
        self.graph_txt = self._make_tab("Graph")

        # status bar
        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(8,4))
        status.pack(side="bottom", fill="x")

        self.refresh_lists()

    def _make_tab(self, title: str) -> tk.Text:
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text=title)
        txt = tk.Text(frame, wrap="word")
        txt.pack(side="left", fill="both", expand=True)
        ys = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        ys.pack(side="right", fill="y")
        txt.config(yscrollcommand=ys.set)
        txt.configure(font=("Consolas", 10))
        txt.insert("1.0", "")
        txt.config(state="disabled")
        return txt

    def set_text(self, widget: tk.Text, data: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", data or "")
        widget.config(state="disabled")

    def refresh_lists(self):
        pipelines = _list_yaml_names(PIPELINES_DIR) or ["default"]
        profiles = _list_yaml_names(PROFILES_DIR) or ["default"]
        self.pipeline_cbx["values"] = pipelines
        self.profile_cbx["values"] = profiles

        # default selections
        if not self.pipeline_cbx.get() and "default" in pipelines:
            self.pipeline_cbx.set("default")
        elif pipelines:
            self.pipeline_cbx.set(pipelines[0])

        if not self.profile_cbx.get() and "default" in profiles:
            self.profile_cbx.set("default")
        elif profiles:
            self.profile_cbx.set(profiles[0])

    def on_preview_graph(self):
        try:
            name = self.pipeline_cbx.get().strip() or "default"
            spec = load_pipeline(name)
            ascii_graph = ascii_from_spec(spec)
            self.set_text(self.graph_txt, ascii_graph)
            self.status_var.set(f"Previewed pipeline '{name}'.")
            self.nb.select(self.graph_txt.master)
        except Exception as e:
            messagebox.showerror("Preview failed", str(e))

    def on_run_clicked(self):
        if self._is_running:
            messagebox.showinfo("Running", "A run is already in progress.")
            return

        task = self.task_txt.get("1.0", "end").strip()
        if not task:
            messagebox.showinfo("Missing task", "Please enter a task.")
            return

        pipeline_name = self.pipeline_cbx.get().strip() or "default"
        profile_name = self.profile_cbx.get().strip() or "default"

        # disable run button while running
        self._is_running = True
        self.run_btn.config(state="disabled")
        self.status_var.set("Running…")

        def _worker():
            try:
                # apply profile (sets env vars if present)
                apply_profile(profile_name)
                # reflect environment to UI
                self.endpoint_var.set(os.environ.get("LLM_ENDPOINT", ""))
                self.model_var.set(os.environ.get("LLM_MODEL", ""))

                spec = load_pipeline(pipeline_name)
                state = run_pipeline(task, spec)

                # push outputs back to UI thread
                self.after(0, lambda: self._render_outputs(spec, state))
            except Exception as e:
                tb = traceback.format_exc()
                def _show_err():
                    self.status_var.set("Error.")
                    self.set_text(self.result_txt, "")
                    self.set_text(self.evidence_txt, "")
                    self.set_text(self.scratch_txt, "")
                    self.set_text(self.graph_txt, tb)
                    messagebox.showerror("Run failed", str(e))
                self.after(0, _show_err)
            finally:
                self.after(0, self._end_run)

        threading.Thread(target=_worker, daemon=True).start()

    def _render_outputs(self, spec, state):
        self.set_text(self.result_txt, state.result or "(no result)")
        self.set_text(self.evidence_txt, "\n".join(str(e) for e in state.evidence) or "(no evidence)")
        self.set_text(self.scratch_txt, "\n".join(state.scratch) or "(no scratch)")
        self.set_text(self.graph_txt, ascii_from_spec(spec))
        self.nb.select(self.result_txt.master)
        self.status_var.set("Done.")

    def _end_run(self):
        self._is_running = False
        self.run_btn.config(state="normal")

    def copy_result(self):
        try:
            txt = self.result_txt.get("1.0", "end").strip()
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.status_var.set("Result copied to clipboard.")
        except Exception:
            pass

def main():
    try:
        import yaml  # Ensure pyyaml is present for pipeline/profile loading
    except Exception:
        messagebox.showerror(
            "Missing dependency",
            "PyYAML is required.\nInstall in your venv:\n\npip install pyyaml"
        )
        return
    app = GraphAgentGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
