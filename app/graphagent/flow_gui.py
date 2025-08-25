import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import yaml

class FlowGUI(tk.Tk):
    def __init__(self, flow_file: Path):
        super().__init__()
        self.title("GraphAgent Flow Viewer")
        self.geometry("800x600")
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

    def create_widgets(self):
        # Layout: left (nodes), right (edges)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        # Nodes tree
        node_frame = ttk.Frame(self)
        node_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        ttk.Label(node_frame, text="Nodes").pack(anchor="w")

        # Show NODE NAME instead of description
        self.node_tree = ttk.Treeview(node_frame, columns=("id",), show="headings", height=20)
        self.node_tree.heading("id", text="Node")
        self.node_tree.pack(fill="both", expand=True)

        for n in self.flow.get("nodes", []):
            self.node_tree.insert("", "end", iid=n["id"], values=(n["id"],))

        # Tooltip / description
        self.tooltip = tk.StringVar()
        self.tooltip_label = ttk.Label(node_frame, textvariable=self.tooltip, wraplength=250, foreground="gray")
        self.tooltip_label.pack(fill="x")

        def on_select(event):
            item = self.node_tree.selection()
            if item:
                node_id = item[0]
                node = next((n for n in self.flow.get("nodes", []) if n["id"] == node_id), None)
                if node:
                    self.tooltip.set(f"{node['id']}:\n{node.get('description','')}")
        self.node_tree.bind("<<TreeviewSelect>>", on_select)

        # Edges list
        edge_frame = ttk.Frame(self)
        edge_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ttk.Label(edge_frame, text="Edges").pack(anchor="w")

        self.edge_list = tk.Listbox(edge_frame)
        self.edge_list.pack(fill="both", expand=True)
        for e in self.flow.get("edges", []):
            self.edge_list.insert("end", f"{e['from']} -> {e['to']}")


if __name__ == "__main__":
    flow_path = Path(__file__).parent.parent / "flows" / "default.yaml"
    app = FlowGUI(flow_path)
    app.mainloop()
