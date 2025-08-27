# app/graphagent/tk_mini_ui.py
from __future__ import annotations
import os, sys, threading, webbrowser, traceback, re
from typing import Dict, Any, List, Tuple

# Ensure external rag_core is importable
RAG_HOME = os.environ.get("RAG_HOME", r"C:\Users\gmoores\Desktop\AI\RAG")
if RAG_HOME and RAG_HOME not in sys.path:
    sys.path.insert(0, RAG_HOME)

import tkinter as tk
from tkinter import ttk, messagebox

import requests
from app.graphagent import rag_integration
from rag_core import query_rag_system

# ------- LLM endpoint (OpenAI-compatible local server) -------
LLM_ENDPOINT = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "qwen/qwen2.5-vl-7b"

# ------- Superscript helpers -------
SUP_MAP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

def to_sup(n: int) -> str:
    return str(n).translate(SUP_MAP)

def strip_model_sources(answer: str) -> str:
    """
    Remove any 'Sources:' section the model printed. We will append our own canonical list.
    Matches 'Sources:' (optionally with preceding ###) to the end (case-insensitive).
    """
    pattern = re.compile(r'(?is)(?:^|\n)\s*(?:#{0,3}\s*)?Sources\s*:\s*.*\Z')
    return pattern.sub("", answer).rstrip()

def replace_bracket_citations_with_supers(answer: str, valid_nums: set[int]) -> str:
    """
    Turn [1] [2] ... into superscripts ¹ ² ... only if the number is in our citations.
    Leaves unknown tokens unchanged.
    """
    def _repl(m: re.Match) -> str:
        try:
            n = int(m.group(1))
        except ValueError:
            return m.group(0)
        return to_sup(n) if n in valid_nums else m.group(0)

    return re.sub(r'\[(\d{1,3})\]', _repl, answer)

# ------- Prompt + LLM -------
def llm_answer(prompt: str, system: str = "You are a helpful assistant.") -> str:
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.3,
    }
    r = requests.post(LLM_ENDPOINT, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()

def assemble_prompt(query: str, ctx: List[Dict[str, Any]], citations: Dict[str, Tuple[int, str]]) -> str:
    """
    We now ask the model to use inline [n] markers, and NOT to print a Sources section.
    UI will append canonical footnotes.
    """
    lines = [
        "Answer the question using only the provided context excerpts.",
        "Cite claims inline using bracketed numbers like [1], [2].",
        "If multiple sources support a sentence, you may use [1][3].",
        "Do NOT print a 'Sources' section; the application will append sources.",
        "",
        "Question:",
        query,
        "",
        "Context excerpts:",
    ]
    # Provide excerpts without [CTX] tokens (to avoid echoing them)
    for i, c in enumerate(ctx, 1):
        lines.append(f"Excerpt {i}: {c.get('text','')}")
    # Provide a numbered key -> title + URL so the model knows numbering,
    # but again tell it not to print this section out.
    lines += [
        "",
        "Source key (for your reference; do not print):",
    ]
    for url, (n, title) in sorted(citations.items(), key=lambda x: x[1][0]):
        lines.append(f"[{n}] {title} — {url}")
    return "\n".join(lines)

# ============================================================
#                          TK APP
# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Local RAG — Tk UI")
        self.geometry("1180x760")

        # runtime storage for last results (for Tier-2 dialogs)
        self._last_ctx: List[Dict[str, Any]] = []
        self._last_citations: Dict[str, Tuple[int, str]] = {}

        # clickable link maps (answer area)
        self._url_tag_map: Dict[str, str] = {}       # tag -> url  (for sources list at bottom)
        self._inline_tag_map: Dict[str, str] = {}    # tag -> url  (for superscripts in body)

        # ---------- Top controls ----------
        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Profile:").pack(side=tk.LEFT)
        self.profile_var = tk.StringVar()
        self.profile_cb = ttk.Combobox(top, textvariable=self.profile_var, width=28, state="readonly")
        self.profile_cb.pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Refresh", command=self.refresh_profiles).pack(side=tk.LEFT)

        self.use_rerank = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Reranker on", variable=self.use_rerank).pack(side=tk.LEFT, padx=10)

        # ---------- k sliders ----------
        ks = ttk.Frame(self, padding=(8,0))
        ks.pack(side=tk.TOP, fill=tk.X)
        self.recall_k = tk.IntVar(value=40)
        self.rerank_k = tk.IntVar(value=12)
        self.context_k = tk.IntVar(value=8)
        for label, var, frm, to in [
            ("Recall k", self.recall_k, 10, 100),
            ("Rerank k", self.rerank_k, 5, 40),
            ("Context k", self.context_k, 2, 12),
        ]:
            f = ttk.Frame(ks)
            f.pack(side=tk.LEFT, padx=10)
            ttk.Label(f, text=label).pack()
            ttk.Scale(f, from_=frm, to=to, orient="horizontal",
                      command=lambda _v, v=var: v.set(int(float(_v)))).pack(fill=tk.X, ipadx=70)
            ttk.Label(f, textvariable=var).pack()

        # ---------- Query ----------
        qrow = ttk.Frame(self, padding=8)
        qrow.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(qrow, text="Your question:").pack(anchor="w")
        self.query_txt = tk.Text(qrow, height=3)
        self.query_txt.pack(fill=tk.X)
        runbar = ttk.Frame(self, padding=(8,4))
        runbar.pack(side=tk.TOP, fill=tk.X)
        self.run_btn = ttk.Button(runbar, text="Search & Answer", command=self.on_run)
        self.run_btn.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(runbar, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)

        # ---------- Paned: left answer / right passages ----------
        pan = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pan.pack(expand=True, fill=tk.BOTH, padx=8, pady=8)

        # Answer pane
        left = ttk.Frame(pan)
        pan.add(left, weight=3)
        ttk.Label(left, text="Answer (click inline ¹, ², … to view passages):").pack(anchor="w")
        self.answer_txt = tk.Text(left, wrap="word")
        self.answer_txt.pack(expand=True, fill=tk.BOTH)
        # styles + click binding
        self.answer_txt.tag_configure("link", foreground="blue", underline=True)
        self.answer_txt.bind("<Button-1>", self._on_answer_click)

        # Passages pane (Tier-2 table)
        right = ttk.Frame(pan)
        pan.add(right, weight=2)
        ttk.Label(right, text="Passages (double-click to open source):").pack(anchor="w")
        cols = ("#", "Title", "Open", "Text")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=20)
        for c, w in zip(cols, (50, 280, 280, 600)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor=tk.W)
        self.tree.pack(expand=True, fill=tk.BOTH)
        self.tree.bind("<Double-1>", self._open_selected_url)
        ttk.Button(right, text="View Passage", command=self._view_passage).pack(pady=4)

        # Initial profiles
        self.refresh_profiles()

    # --------------------- Profile discovery ---------------------
    def refresh_profiles(self):
        try:
            profs = query_rag_system.list_profiles()
            choices = [p.get("profile") for p in profs]
            self.profile_cb["values"] = choices
            if choices and not self.profile_var.get():
                self.profile_var.set(choices[0])
            self.status_var.set(f"Profiles: {choices or 'none found'}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list profiles:\n{e}")
            self.status_var.set("Profile discovery failed.")

    # --------------------- Run pipeline ---------------------
    def on_run(self):
        profile = self.profile_var.get().strip()
        if not profile:
            messagebox.showwarning("No profile", "Select a collection profile (Refresh if needed).")
            return
        query = self.query_txt.get("1.0", "end").strip()
        if not query:
            messagebox.showwarning("No question", "Type a question to search.")
            return

        self.run_btn.config(state=tk.DISABLED)
        self.status_var.set("Running…")
        threading.Thread(
            target=self._run_pipeline,
            args=(query, profile, self.recall_k.get(), self.rerank_k.get(), self.context_k.get(), self.use_rerank.get()),
            daemon=True
        ).start()

    def _run_pipeline(self, query: str, profile: str, recall_k: int, rerank_k: int, context_k: int, use_rerank: bool):
        try:
            out = rag_integration.search_docs(
                query=query,
                profile=profile,
                recall_k=recall_k,
                rerank_k=rerank_k,
                context_k=context_k,
                rerank=use_rerank,
            )
        except Exception as e:
            tb = traceback.format_exc()
            self._ui_error(f"Retrieval error:\n{e}\n\n{tb}")
            return

        ctx = out.get("results", [])
        citations: Dict[str, Tuple[int, str]] = out.get("citations", {})
        self._last_ctx = ctx
        self._last_citations = citations

        prompt = assemble_prompt(query, ctx, citations)
        try:
            raw_answer = llm_answer(prompt)
        except Exception as e:
            tb = traceback.format_exc()
            self._ui_error(f"LLM error (check 127.0.0.1:1234):\n{e}\n\n{tb}")
            return

        # ---- Prepare final answer text (string) ----
        # 1) remove any model-made Sources section
        cleaned = strip_model_sources(raw_answer)
        # 2) convert [n] -> superscripts, if they belong to our key
        valid_nums = {n for (_url, (n, _t)) in citations.items()}
        cleaned = replace_bracket_citations_with_supers(cleaned, valid_nums)

        # ---- UI update on main thread ----
        def update_ui():
            self._url_tag_map.clear()
            self._inline_tag_map.clear()

            self.answer_txt.delete("1.0", "end")

            # 1) Insert processed answer (no auto-injected superscripts spam)
            self.answer_txt.insert("end", cleaned + "\n\n")

            # 2) Tag inline superscripts in the body so they open Tier-2 dialog
            self._tag_inline_superscripts(valid_nums)

            # 3) Append canonical Sources list (single copy)
            if citations:
                self.answer_txt.insert("end", "—" * 20 + "\n")
                self.answer_txt.insert("end", "Sources:\n")
                for url, (n, title) in sorted(citations.items(), key=lambda x: x[1][0]):
                    line = f"[{n}] {title} — {url}\n"
                    line_start = self.answer_txt.index("end")
                    self.answer_txt.insert("end", line)

                    # tag only the URL range
                    ls = f"{line_start} linestart"
                    le = f"{line_start} lineend"
                    content = self.answer_txt.get(ls, le)
                    pos = content.rfind(url)
                    if pos >= 0:
                        tag = f"src_url_{n}"
                        rng_start = f"{ls}+{pos}c"
                        rng_end = f"{ls}+{pos+len(url)}c"
                        self.answer_txt.tag_add(tag, rng_start, rng_end)
                        self.answer_txt.tag_config(tag, foreground="blue", underline=True)
                        self.answer_txt.tag_bind(tag, "<Button-1>", self._on_source_url_click)
                        self._url_tag_map[tag] = url

            # 4) Fill passages table (Title instead of ChunkID)
            for row in self.tree.get_children():
                self.tree.delete(row)
            for i, c in enumerate(ctx, 1):
                url = c.get("canonical_url", "")
                n = citations.get(url, (None, None))[0] if citations else None
                vals = (f"{i} ({to_sup(n) if n else ''})",
                        c.get("title",""),
                        url,
                        c.get("text",""))
                self.tree.insert("", "end", values=vals)

            self.status_var.set("Done.")
            self.run_btn.config(state=tk.NORMAL)

        self.after(0, update_ui)

    # --------------------- Inline superscript tagging ---------------------
    def _build_num_to_url(self) -> Dict[int, str]:
        num_to_url: Dict[int, str] = {}
        for url, (n, _title) in self._last_citations.items():
            if n not in num_to_url:
                num_to_url[n] = url
        return num_to_url

    def _tag_inline_superscripts(self, valid_nums: set[int]):
        """
        Find and tag superscript numerals (¹, ², …) in the body so that clicking
        opens a Tier-2 passage dialog for that source.
        We search only before the 'Sources:' section we appended.
        """
        if not self._last_citations:
            return

        # search region: everything before the "Sources:" we appended
        end_index = self.answer_txt.search("Sources:\n", "1.0", stopindex="end")
        search_end = end_index if end_index else "end"

        num_to_url = self._build_num_to_url()

        for n in sorted(valid_nums):
            sup = to_sup(n)
            start = "1.0"
            while True:
                idx = self.answer_txt.search(sup, start, stopindex=search_end)
                if not idx:
                    break
                end = f"{idx}+{len(sup)}c"
                tag = f"inline_sup_{n}_{idx.replace('.', '_')}"
                self.answer_txt.tag_add(tag, idx, end)
                self.answer_txt.tag_config(tag, foreground="blue", underline=True)
                self.answer_txt.tag_bind(tag, "<Button-1>", self._on_inline_citation_click)
                self._inline_tag_map[tag] = num_to_url.get(n, "")

                # move past this match
                start = end

    # --------------------- Click handlers ---------------------
    def _on_source_url_click(self, event):
        # bottom sources list: open URL directly
        for tag in self.answer_txt.tag_names("current"):
            url = self._url_tag_map.get(tag)
            if url:
                webbrowser.open(url)
                return

    def _on_inline_citation_click(self, event):
        # inline superscript: open Tier-2 passage dialog for that source
        for tag in self.answer_txt.tag_names("current"):
            url = self._inline_tag_map.get(tag)
            if url:
                self._open_passages_dialog_for_url(url)
                return

    def _on_answer_click(self, event):
        # Required so tag_bind callbacks fire reliably on Windows
        pass

    # --------------------- Tier-2 dialog helpers ---------------------
    def _open_passages_dialog_for_url(self, url: str):
        matches = [c for c in self._last_ctx if c.get("canonical_url", "") == url]
        if not matches:
            messagebox.showinfo("No passages", "No passages found for this source in the current context.")
            return

        top = tk.Toplevel(self)
        top.title("Source passages")
        top.geometry("980x560")

        # header
        n, title = self._last_citations.get(url, (None, url))
        hdr = ttk.Frame(top, padding=8)
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text=f"[{n}] {title}", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Button(hdr, text="Open Source", command=lambda u=url: webbrowser.open(u)).pack(side=tk.RIGHT)

        # passages list: Title + Text (no ChunkID)
        cols = ("#", "Title", "Text")
        tree = ttk.Treeview(top, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (60, 360, 520)):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor=tk.W)
        tree.pack(expand=True, fill=tk.BOTH, padx=8, pady=4)

        for i, c in enumerate(matches, 1):
            tree.insert("", "end", values=(i, c.get("title",""), c.get("text","")))

        # open URL on double-click row
        tree.bind("<Double-1>", lambda _e, u=url: webbrowser.open(u))

        ttk.Button(top, text="Close", command=top.destroy).pack(pady=6)

    # --------------------- Passages table actions ---------------------
    def _open_selected_url(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        url = vals[2]  # "Open" column (URL)
        if url:
            webbrowser.open(url)

    def _view_passage(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Select a passage to view.")
            return
        vals = self.tree.item(sel[0], "values")
        top = tk.Toplevel(self)
        top.title(f"Passage — #{vals[0]} / {vals[1]}")
        txt = tk.Text(top, wrap="word")
        txt.pack(expand=True, fill=tk.BOTH)
        txt.insert("end", vals[3])  # Text column
        ttk.Button(top, text="Open Source", command=lambda u=vals[2]: webbrowser.open(u) if u else None).pack(pady=4)

    # --------------------- Errors ---------------------
    def _ui_error(self, msg: str):
        def f():
            self.run_btn.config(state=tk.NORMAL)
            self.status_var.set("Error.")
            messagebox.showerror("Error", msg)
        self.after(0, f)

# --------------------- Entrypoint ---------------------
def main():
    print("[tk_mini_ui] main() starting...")
    App().mainloop()
    print("[tk_mini_ui] mainloop() exited.")

if __name__ == "__main__":
    try:
        print("[tk_mini_ui] __main__ entry")
        main()
    except Exception as e:
        tb = traceback.format_exc()
        print("[tk_mini_ui] FATAL:", e)
        print(tb)
        try:
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("Fatal error in tk_mini_ui", f"{e}\n\n{tb}")
        except Exception:
            pass
        sys.exit(1)
