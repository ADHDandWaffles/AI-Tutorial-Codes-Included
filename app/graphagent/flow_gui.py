import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from pathlib import Path
import yaml

# --- Prompt Templates ---
PROMPTS_FILE = Path(__file__).parent.parent / "flows" / "prompts.yaml"
with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATES = yaml.safe_load(f)


class FlowGUI(tk.Tk):
    def __init__(self, flow_file: Path):
        super().__init__()
        self.title("GraphAgent Flow Editor")
        self.geometry("1200x600")  # three columns
        self.flow_file = flow_file
        self.flow = self.load_flow()

        self.create_widgets()

    def load_flow(self):
        try:
            with open(self.flow_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load flow file:\n{e}")
            return {"nodes": [], "edges": []}

    def save_flow(self):
        try:
            with open(self.flow_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.flow, f, sort_keys=False, allow_unicode=True)
            messagebox.showinfo("Saved", f"Flow saved to {self.flow_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save flow:\n{e}")

    def create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.columnconfigure(2, weight=2)
        self.rowconfigure(0, weight=1)

        # --- Left pane: Nodes ---
        node_frame = ttk.Frame(self)
        node_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ttk.Label(node_frame, text="Nodes").pack(anchor="w")

        self.node_list = tk.Listbox(node_frame)
        self.node_list.pack(fill="both", expand=True)
        self.node_list.bind("<<ListboxSelect>>", self.show_node_editor)

        for n in self.flow.get("nodes", []):
            self.node_list.insert("end", n["id"])

        # --- Middle pane: Node editor ---
        self.editor_frame = ttk.Frame(self)
        self.editor_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ttk.Label(self.editor_frame, text="Node Editor").pack(anchor="w")

        self.node_id_var = tk.StringVar()
        self.node_desc_var = tk.StringVar()
        self.node_prompt_var = tk.StringVar()

        ttk.Label(self.editor_frame, text="Node ID").pack(anchor="w")
        ttk.Entry(self.editor_frame, textvariable=self.node_id_var).pack(fill="x")

        ttk.Label(self.editor_frame, text="Description").pack(anchor="w")
        ttk.Entry(self.editor_frame, textvariable=self.node_desc_var).pack(fill="x")

        ttk.Label(self.editor_frame, text="Prompt Version").pack(anchor="w")
        self.prompt_dropdown = ttk.Combobox(self.editor_frame, textvariable=self.node_prompt_var)
        self.prompt_dropdown.pack(fill="x")

        ttk.Label(self.editor_frame, text="Prompt Preview").pack(anchor="w")
        self.prompt_box = tk.Text(self.editor_frame, height=12, wrap="word")
        self.prompt_box.pack(fill="both", expand=True)

        # --- Right pane: ASCII Flow Diagram ---
        diagram_frame = ttk.Frame(self)
        diagram_frame.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        ttk.Label(diagram_frame, text="Flow Diagram").pack(anchor="w")

        self.diagram_box = tk.Text(diagram_frame, wrap="none")
        self.diagram_box.pack(fill="both", expand=True)

        self.refresh_diagram()

    # --- Node Editor ---
    def show_node_editor(self, event=None):
        sel = self.node_list.curselection()
        if not sel: 
            return
        node_id = self.node_list.get(sel[0])
        node = next((n for n in self.flow["nodes"] if n["id"] == node_id), None)
        if node:
            self.node_id_var.set(node["id"])
            self.node_desc_var.set(node.get("description", ""))
            current_prompt = node.get("prompt", node["id"])

            # Filter available prompts for this node ID
            options = [k for k in PROMPT_TEMPLATES.keys() if k.startswith(node_id)]
            self.prompt_dropdown["values"] = options
            self.node_prompt_var.set(current_prompt if current_prompt in options else options[0])

            # Update preview
            self.prompt_box.delete("1.0", "end")
            template = PROMPT_TEMPLATES.get(self.node_prompt_var.get(), "(No template found)")
            self.prompt_box.insert("end", template)

    # --- Diagram Refresh ---
    def refresh_diagram(self):
        self.diagram_box.delete("1.0", "end")
        for e in self.flow.get("edges", []):
            line = f"{e['from']} -> {e['to']}\n"
            self.diagram_box.insert("end", line)


if __name__ == "__main__":
    flow_path = Path(__file__).parent.parent / "flows" / "default.yaml"
    app = FlowGUI(flow_path)
    app.mainloop()

