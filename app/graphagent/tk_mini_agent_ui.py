# app/graphagent/tk_mini_agent_ui.py
from __future__ import annotations

import os, sys, threading, webbrowser, subprocess, json, traceback
from typing import Dict, Any, List, Tuple

import tkinter as tk
from tkinter import ttk, messagebox

import re

# Debug: confirm we’re running the right file
print("[Tk UI] Using file:", __file__)

# --- Make external rag_core importable (your RAG_HOME on Desktop) ---
RAG_HOME = os.environ.get("RAG_HOME", r"C:\Users\gmoores\Desktop\AI\RAG")
if RAG_HOME and RAG_HOME not in sys.path:
    sys.path.insert(0, RAG_HOME)

# Local imports from your repos
from app.graphagent import rag_integration
from rag_core import query_rag_system

# Superscript helpers (for clickable ¹²³)
SUP_MAP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
REV_SUP = {c: i for i, c in enumerate("⁰¹²³⁴⁵⁶⁷⁸⁹")}

def to_sup(n: int) -> str:
    return "".join(ch.translate(SUP_MAP) for ch in str(n))


class AgentUI(tk.Tk):
    """
    Tk UI that:
      1) Runs your full Agent Pipeline via: python -m app.graphagent.cli --task "<question>"
      2) Uses rag_integration.search_docs(...) only to drive Tier-2 passages & clickable superscripts modal.
    """
    def __init__(self):
        super().__init__()
        self.title("Local RAG — Agent Pipeline UI (Tk)")
        self.geometry("1180x780")

        # Top bar: profile + rerank + refresh
        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Profile:").pack(side=tk.LEFT)
        self.profile_var = tk.StringVar()
        self.profile_cb = ttk.Combobox(top, textvariable=self.profile_var, state="readonly", width=28)
        self.profile_cb.pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Refresh", command=self.refresh_profiles).pack(side=tk.LEFT)

        self.use_rerank = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Reranker on", variable=self.use_rerank).pack(side=tk.LEFT, padx=10)

        # K controls
        ks = ttk.Frame(self, padding=(8, 0))
        ks.pack(side=tk.TOP, fill=tk.X)
        self.recall_k  = tk.IntVar(value=40)
        self.rerank_k  = tk.IntVar(value=12)
        self.context_k = tk.IntVar(value=8)

        for label, var, lo, hi in [
            ("Recall k",  self.recall_k,  10, 100),
            ("Rerank k",  self.rerank_k,   5,  40),
            ("Context k", self.context_k,  2,  12),
        ]:
            f = ttk.Frame(ks)
            f.pack(side=tk.LEFT, padx=10)
            ttk.Label(f, text=label).pack()
            s = ttk.Scale(f, from_=lo, to=hi, orient="horizontal",
                          command=lambda _v, v=var: v.set(int(float(_v))))
            s.pack(fill=tk.X, ipadx=70)
            ttk.Label(f, textvariable=var).pack()

        # Query row
        qf = ttk.Frame(self, padding=(8, 8, 8, 4))
        qf.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(qf, text="Your question:").pack(anchor="w")
        self.query_txt = tk.Text(qf, height=3, wrap="word")
        self.query_txt.pack(fill=tk.X)

        runbar = ttk.Frame(self, padding=(8, 4))
        runbar.pack(side=tk.TOP, fill=tk.X)
        self.run_btn = ttk.Button(runbar, text="Run Agent Pipeline", command=self.on_run)
        self.run_btn.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(runbar, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)

        # Split panes
        pan = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pan.pack(expand=True, fill=tk.BOTH, padx=8, pady=8)

        # Left: Agent Answer
        left = ttk.Frame(pan)
        pan.add(left, weight=3)
        ttk.Label(left, text="Agent Answer (click superscripts to view passages):").pack(anchor="w")
        self.answer_txt = tk.Text(left, wrap="word")
        self.answer_txt.pack(expand=True, fill=tk.BOTH)
        self.answer_txt.tag_configure("link", foreground="blue", underline=True)
        # Not strictly needed, but harmless. Real clicks handled by tag bindings.
        self.answer_txt.bind("<Button-1>", self._maybe_click_superscript)

        # Right: Tier-2 passages
        right = ttk.Frame(pan)
        pan.add(right, weight=2)
        ttk.Label(right, text="Passages (double-click a row to open the source):").pack(anchor="w")
        cols = ("#", "No.", "Title", "URL", "Text")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=20)
        widths = (50, 50, 260, 300, 600)
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor=tk.W)
        self.tree.pack(expand=True, fill=tk.BOTH)
        self.tree.bind("<Double-1>", self._open_selected_url)

        # Internal state to drive superscript dialogs
        self._num_to_url_title: Dict[int, Tuple[str, str]] = {}   # n -> (url, title)
        self._url_to_ctx: Dict[str, List[Dict[str, Any]]] = {}    # url -> [chunks]

        # Boot
        self.refresh_profiles()

    def _extract_evidence_citations(self, answer_text: str) -> Dict[int, Tuple[str, str]]:
        """
        Parse the CLI's '---- Evidence ----' section to build a 1-based map:
        { 1: (url, title), 2: (...), ... }
        Lines look like:
          Title — https://example.com :: snippet...
        """
        lines = answer_text.splitlines()
        try:
            start = lines.index("---- Evidence ----") + 1
        except ValueError:
            return {}

        evidence_lines: List[str] = []
        for ln in lines[start:]:
            s = ln.strip()
            # Stop at next block header or empty separator
            if not s or s.startswith("---- "):
                break
            evidence_lines.append(s)

        out: Dict[int, Tuple[str, str]] = {}
        n = 1
        for ln in evidence_lines:
            # Pull URL
            m = re.search(r"(https?://\S+)", ln)
            url = m.group(1) if m else ""
            # Title is before ' — ' if present
            title = ln.split(" — ", 1)[0].strip() if " — " in ln else (url or "Source")
            if url:
                out[n] = (url, title)
                n += 1
        return out


    # ---- Profile discovery ----
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

    # ---- Run Agent Pipeline + populate Tier-2 ----
    def on_run(self):
        prof = (self.profile_var.get() or "").strip()
        if not prof:
            messagebox.showwarning("No profile", "Select a collection profile (Refresh if needed).")
            return
        q = self.query_txt.get("1.0", "end").strip()
        if not q:
            messagebox.showwarning("No question", "Type a question to run.")
            return

        self.run_btn.config(state=tk.DISABLED)
        self.status_var.set("Running agent…")

        t = threading.Thread(
            target=self._run_background,
            args=(q, prof, self.recall_k.get(), self.rerank_k.get(), self.context_k.get(), self.use_rerank.get()),
            daemon=True
        )
        t.start()

    def _run_background(self, query: str, profile: str, recall_k: int, rerank_k: int, context_k: int, use_rerank: bool):
        # 1) Get passages/citations for Tier-2 (so the UI can show chunks)
        try:
            rag_out = rag_integration.search_docs(
                query=query,
                profile=profile,
                recall_k=recall_k,
                rerank_k=rerank_k,
                context_k=context_k,
                rerank=use_rerank,
            )
            # Normalize output: support dict or list
            if isinstance(rag_out, dict):
                ctx = rag_out.get("results", []) or []
                citations = rag_out.get("citations", {}) or {}
            else:
                ctx = rag_out or []
                citations = {}
                # Build a basic citation map if missing
                seen = {}
                n = 1
                for c in ctx:
                    url = (c or {}).get("canonical_url") or ""
                    if url and url not in seen:
                        seen[url] = (n, (c or {}).get("title") or url)
                        n += 1
                citations = {u: (num, title) for u, (num, title) in seen.items()}
        except Exception as e:
            tb = traceback.format_exc()
            self._ui_error(f"Retrieval failed:\n{e}\n\n{tb}")
            return

        # 2) Run the real Agent Pipeline via CLI (node graph), capture stdout as answer_text
        try:
            from pathlib import Path
            import tempfile, datetime

            # --- Child process env -------------------------------------------------
            env = os.environ.copy()
            # knobs for CLI (optional; your CLI can read these if desired)
            env["RAG_UI_PROFILE"]   = profile
            env["RAG_UI_RECALL_K"]  = str(recall_k)
            env["RAG_UI_RERANK_K"]  = str(rerank_k)
            env["RAG_UI_CONTEXT_K"] = str(context_k)
            env["RAG_UI_RERANK"]    = "1" if use_rerank else "0"

            # Force UTF-8 to avoid Windows cp1252 crashes on emojis/special chars
            env["PYTHONIOENCODING"] = "utf-8"

            # Repo root (folder that contains the "app" package)
            repo_root = Path(__file__).resolve().parents[2]
            # External RAG package home
            rag_home  = os.environ.get("RAG_HOME", r"C:\Users\gmoores\Desktop\AI\RAG")

            # Ensure both roots are importable by the child interpreter
            extra_paths = [str(repo_root)]
            if rag_home:
                extra_paths.append(rag_home)

            existing_pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = os.pathsep.join([p for p in (os.pathsep.join(extra_paths), existing_pp) if p])

            # --- Launch CLI as module ---------------------------------------------
            cmd = [sys.executable, "-m", "app.graphagent.cli", "--task", query]
            proc = subprocess.run(
                cmd,
                env=env,
                cwd=str(repo_root),
                capture_output=True,
                text=True,        # decode to str
                encoding="utf-8", # be explicit about decoding
                errors="replace", # never crash on weird bytes
            )

            if proc.returncode != 0:
                # Write a copy/paste-able log and open it in Notepad
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                log_path = Path(tempfile.gettempdir()) / f"agent_cli_error_{ts}.log"
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("COMMAND: " + " ".join(cmd) + "\n")
                    f.write("CWD: " + str(repo_root) + "\n")
                    f.write("RAG_HOME: " + str(rag_home) + "\n")
                    f.write("PYTHONPATH: " + env["PYTHONPATH"] + "\n\n")
                    f.write("---- STDOUT ----\n" + (proc.stdout or "") + "\n\n")
                    f.write("---- STDERR ----\n" + (proc.stderr or "") + "\n")
                try:
                    os.startfile(str(log_path))  # Open in Notepad on Windows
                except Exception:
                    pass
                raise RuntimeError(f"Agent CLI returned non-zero exit code. Log: {log_path}")

            # Heuristic: last non-empty chunk of stdout is the answer
            stdout = (proc.stdout or "").strip()
            answer_text = self._pick_answer_from_stdout(stdout)

        except Exception as e:
            tb = traceback.format_exc()
            self._ui_error(f"Agent pipeline error:\n{e}\n\n{tb}")
            return

        # 3) Update UI
        self.after(0, lambda: self._update_ui(answer_text, ctx, citations))

    # Try to grab the last non-empty block from CLI output as the final answer
    def _pick_answer_from_stdout(self, s: str) -> str:
        if not s:
            return ""
        parts = [p.strip() for p in s.splitlines()]
        for i, line in enumerate(parts):
            if line.lower().startswith("answer:"):
                return "\n".join(parts[i+1:]).strip()
        return s

    # ---- Build the visual result panes ----
    def _update_ui(self, answer_text: str, ctx: List[Dict[str, Any]], citations: Dict[str, Tuple[int, str]]):
        self.answer_txt.delete("1.0", "end")
        self._num_to_url_title.clear()
        self._url_to_ctx.clear()

        # 0) Prefer the CLI's "Evidence" ordering (matches [1],[2],...)
        ev_map = self._extract_evidence_citations(answer_text)  # Dict[int, (url, title)]

        # 1) Build url -> chunks map from ctx regardless
        for c in ctx:
            url = (c.get("canonical_url") or "").strip()
            if not url:
                continue
            self._url_to_ctx.setdefault(url, []).append(c)

        # 2) Number→(url,title) mapping:
        #    - If Evidence block exists, use it (keeps [n] aligned).
        #    - Else fall back to citations from rag_integration.search_docs.
        if ev_map:
            self._num_to_url_title.update(ev_map)
        else:
            for url, (n, title) in sorted(citations.items(), key=lambda x: x[1][0]):
                self._num_to_url_title[n] = (url, title or url)

        # 3) Insert agent answer
        self.answer_txt.insert("end", answer_text + "\n\n")

        # 4) Make [n]/¹ clickable
        self._tag_superscripts()

        # 5) If the agent answer does NOT include a 'sources' section, append one
        if "sources" not in answer_text.lower() and self._num_to_url_title:
            self.answer_txt.insert("end", "—" * 20 + "\nSources:\n")
            for n in sorted(self._num_to_url_title.keys()):
                url, title = self._num_to_url_title[n]
                line = f"[{n}] {title} — {url}\n"
                start_index = self.answer_txt.index("end")
                self.answer_txt.insert("end", line)
                # Tag the URL portion as a clickable link
                lstart = f"{float(start_index)-1} linestart"
                lend   = self.answer_txt.index("end-1c")
                textline = self.answer_txt.get(lstart, lend)
                pos = textline.rfind(url)
                if pos >= 0:
                    tag = f"url_{n}"
                    rng_start = f"{lstart}+{pos}c"
                    rng_end   = f"{lstart}+{pos+len(url)}c"
                    self.answer_txt.tag_add(tag, rng_start, rng_end)
                    self.answer_txt.tag_config(tag, foreground="blue", underline=True)
                    self.answer_txt.tag_bind(tag, "<Button-1>", lambda _e, u=url: webbrowser.open(u))

        # 6) Fill Tier-2 table
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, c in enumerate(ctx, 1):
            url = c.get("canonical_url", "") or ""
            title = c.get("title", "") or ""
            text = c.get("text", "") or ""
            sup_no = None
            # If we have an Evidence-derived number, use it; else try citations map
            if url:
                # Find number assigned to this URL (reverse-lookup)
                found_num = None
                for n, (u, _t) in self._num_to_url_title.items():
                    if u == url:
                        found_num = n
                        break
                if found_num is None:
                    tup = citations.get(url)
                    sup_no = tup[0] if tup else None
                else:
                    sup_no = found_num
            self.tree.insert("", "end", values=(i, sup_no, title, url, text))

        self.status_var.set("Done.")
        self.run_btn.config(state=tk.NORMAL)


    def _tag_superscripts(self):
        """
        Make both superscript digits (¹²³…) and bracketed tokens like [1] clickable.
        """
        text = self.answer_txt.get("1.0", "end-1c")
        if not text:
            return

        # 1) Superscript digits
        for i, ch in enumerate(text):
            n = REV_SUP.get(ch)
            if n is not None and n in self._num_to_url_title:
                tag = f"sup_{n}_{i}"
                start = f"1.0+{i}c"
                end   = f"1.0+{i+1}c"
                self.answer_txt.tag_add(tag, start, end)
                self.answer_txt.tag_config(tag, foreground="blue")
                self.answer_txt.tag_bind(tag, "<Button-1>", lambda _e, nn=n: self._open_passage_dialog_for_num(nn))

        # 2) Square-bracket citations like [1], [12]
        for m in re.finditer(r"\[(\d{1,3})\]", text):
            try:
                n = int(m.group(1))
            except Exception:
                continue
            if n in self._num_to_url_title:
                tag = f"br_{n}_{m.start()}"
                start = f"1.0+{m.start()}c"
                end   = f"1.0+{m.end()}c"
                self.answer_txt.tag_add(tag, start, end)
                self.answer_txt.tag_config(tag, foreground="blue")
                self.answer_txt.tag_bind(tag, "<Button-1>", lambda _e, nn=n: self._open_passage_dialog_for_num(nn))


    def _open_passage_dialog_for_num(self, n: int):
        url, title = self._num_to_url_title.get(n, ("", ""))
        chunks = self._url_to_ctx.get(url, [])
        if not url:
            return
        top = tk.Toplevel(self)
        top.title(f"[{n}] {title}")
        top.geometry("900x600")
        # Header with clickable title
        hf = ttk.Frame(top, padding=8)
        hf.pack(side=tk.TOP, fill=tk.X)
        tlabel = ttk.Label(hf, text=f"[{n}] {title}", foreground="blue", cursor="hand2")
        tlabel.pack(side=tk.LEFT)
        tlabel.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))
        ttk.Label(hf, text=f" ({url})").pack(side=tk.LEFT)

        # Body with all matched chunks
        body = tk.Text(top, wrap="word")
        body.pack(expand=True, fill=tk.BOTH)
        for i, c in enumerate(chunks, 1):
            body.insert("end", f"\n— Passage {i} —\n")
            body.insert("end", c.get("text", "") + "\n")

        # Buttons
        bf = ttk.Frame(top, padding=8)
        bf.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bf, text="Open Source", command=lambda u=url: webbrowser.open(u)).pack(side=tk.LEFT)

    def _open_selected_url(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        url = vals[3]
        if url:
            webbrowser.open(url)

    def _maybe_click_superscript(self, event):
        """No-op. Real clicks are handled by per-tag bindings in _tag_superscripts()."""
        return None

    def _ui_error(self, msg: str):
        def f():
            self.run_btn.config(state=tk.NORMAL)
            self.status_var.set("Error.")
            messagebox.showerror("Error", msg)
        self.after(0, f)


def main():
    AgentUI().mainloop()

if __name__ == "__main__":
    main()
