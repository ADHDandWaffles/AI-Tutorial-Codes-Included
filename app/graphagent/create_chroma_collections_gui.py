# =============================
# app/graphagent/create_chroma_collections_gui.py
# Embed Markdown -> Chroma (progress) + Inspect existing collections (manifests)
# =============================

from __future__ import annotations

import os, sys, glob, hashlib, json, socket
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

import gradio as gr
import chromadb
import yaml
from sentence_transformers import SentenceTransformer

# ---- Locate your external rag_core data dirs (same defaults as your scripts) ----
RAG_HOME = os.environ.get("RAG_HOME", r"C:\Users\gmoores\Desktop\AI\RAG")

DEFAULT_MD_DIR = os.environ.get("RAG_MD_DIR", r"C:\Users\gmoores\Desktop\AI\RAG\data\markdown_files")
DEFAULT_DB_DIR = os.environ.get("RAG_DB_DIR", r"C:\Users\gmoores\Desktop\AI\RAG\vector_store")
DEFAULT_BASE   = os.environ.get("RAG_BASE", "markdown_chunks")

# Optional NLTK sentence tokenizer (falls back to simple split if missing)
try:
    import nltk
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt")
except Exception:
    nltk = None


# ---------------- Embedding helpers (mirrors your CLI script) ----------------

def read_markdown_with_frontmatter(path: Path) -> Tuple[Dict, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            fm_raw = parts[0].replace("---\n", "")
            body = parts[1]
            try:
                fm = yaml.safe_load(fm_raw) or {}
            except Exception:
                fm = {}
            return fm, body
    return {}, text

def sentence_chunks(text: str, chunk_size: int, overlap_pct: float) -> List[str]:
    overlap_chars = int(chunk_size * overlap_pct)
    chunks: List[str] = []

    if nltk is not None:
        try:
            sents = nltk.sent_tokenize(text)
        except Exception:
            sents = [text]
    else:
        sents = [s.strip() for s in text.replace("\r", "").split(". ")]

    buf = ""
    for s in sents:
        if not s:
            continue
        candidate = (buf + (" " if buf and not buf.endswith("\n") else "") + s) if buf else s
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            if buf:
                chunks.append(buf.strip())
            if chunks and overlap_chars > 0:
                tail = chunks[-1][-overlap_chars:]
                buf = (tail + " " + s).strip()
            else:
                buf = s
    if buf:
        chunks.append(buf.strip())
    return [c for c in chunks if c]

def ensure_semicolon_list(val) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return "; ".join(str(x) for x in val)
    return str(val)

def stable_doc_id(canonical_url: str, file_path: Path) -> str:
    if canonical_url:
        return hashlib.sha1(canonical_url.encode("utf-8")).hexdigest()[:16]
    return hashlib.sha1(str(file_path).encode("utf-8")).hexdigest()[:16]

def build_embedder(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)

def embed_passages(model: SentenceTransformer, texts: List[str], model_name: str):
    lower = model_name.lower()
    if "bge" in lower or "e5" in lower:
        texts = [f"passage: {t}" for t in texts]
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=64)

def parse_annot_lines(lines: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in (lines or "").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" in raw:
            k, v = raw.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def write_collection_manifest(db_dir: str, collection_name: str, data: Dict):
    mdir = os.path.join(db_dir, "_collections")
    os.makedirs(mdir, exist_ok=True)
    with open(os.path.join(mdir, f"{collection_name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_collection_manifest(db_dir: str, collection_name: str) -> Dict:
    path = os.path.join(db_dir, "_collections", f"{collection_name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ---------------- Inspect collections (new) ----------------

def load_collections_with_manifests(db_dir: str, base: str) -> List[Dict]:
    """
    Returns a list of dicts:
      {profile, collection, model_name, chunk_size, overlap, run_label, annotations, count, updated_at, manifest_path}
    Falls back gracefully if manifest is missing.
    """
    client = chromadb.PersistentClient(path=db_dir)
    names = [c.name for c in client.list_collections()]

    rows: List[Dict] = []
    prefix = f"{base}_"

    for name in names:
        if name == base:
            profile = "_legacy"
        elif name.startswith(prefix):
            profile = name[len(prefix):]
        else:
            # unrelated collection; show but mark unknown base
            profile = "(unknown)"
        man = read_collection_manifest(db_dir, name)
        # try to get count from Chroma even if manifest missing
        try:
            coll = client.get_collection(name)
            count = coll.count()
        except Exception:
            count = man.get("count")

        rows.append({
            "profile": profile,
            "collection": name,
            "model_name": man.get("model_name", "(unknown)"),
            "chunk_size": man.get("chunk_size", "(unknown)"),
            "overlap": man.get("overlap", "(unknown)"),
            "run_label": man.get("run_label", ""),
            "annotations": man.get("annotations", {}),
            "count": count,
            "updated_at": man.get("updated_at", ""),
            "manifest_path": os.path.join(db_dir, "_collections", f"{name}.json"),
        })
    # Newest first if timestamps are there
    rows.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return rows

def rows_to_table(rows: List[Dict]) -> List[List]:
    cols = ["profile", "collection", "model_name", "chunk_size", "overlap", "run_label", "annotations", "count", "updated_at", "manifest_path"]
    table: List[List] = []
    for r in rows:
        table.append([r.get(k, "") for k in cols])
    return table


# ---------------- Embedding core (yields progress updates) ----------------

def run_embed(
    md_dir: str,
    db_dir: str,
    base: str,
    profile: str,
    model_name: str,
    chunk_size: int,
    overlap: float,
    batch: int,
    run_label: str,
    annotations_text: str,
    progress: gr.Progress = gr.Progress(track_tqdm=False),
):
    log_lines: List[str] = []

    def log(msg: str):
        log_lines.append(msg)
        return "\n".join(log_lines[-500:])

    if not os.path.isdir(md_dir):
        yield ("❌ Markdown folder not found.", "", 0, 0, "", [])
        return
    if not os.path.isdir(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    collection_name = f"{base}_{profile}"
    client = chromadb.PersistentClient(path=db_dir)
    try:
        coll = client.create_collection(collection_name, metadata={"profile": profile})
    except Exception:
        coll = client.get_collection(collection_name)

    log(f"🔧 Loading embedder: {model_name}")
    model = build_embedder(model_name)

    md_files = glob.glob(os.path.join(md_dir, "**", "*.md"), recursive=True)
    total_files = len(md_files)
    if total_files == 0:
        yield ("❌ No .md files found in md_dir.", collection_name, 0, 0, "", rows_to_table(load_collections_with_manifests(db_dir, base)))
        return

    ids_batch: List[str] = []
    docs_batch: List[str] = []
    metas_batch: List[Dict] = []
    total_chunks = 0

    annots = parse_annot_lines(annotations_text)

    yield (log(f"📁 Files to process: {total_files}"), collection_name, 0, total_files, "", rows_to_table(load_collections_with_manifests(db_dir, base)))

    for idx, fp in enumerate(md_files, 1):
        progress(idx / total_files)

        p = Path(fp)
        fm, body = read_markdown_with_frontmatter(p)
        title = str(fm.get("title") or p.stem)
        canonical_url = str(fm.get("url") or "")
        tags = ensure_semicolon_list(fm.get("tags"))
        doc_id = stable_doc_id(canonical_url, p)

        chunks = sentence_chunks(body, chunk_size, overlap)
        for i, ch in enumerate(chunks):
            chunk_id = f"{doc_id}#c{i:05d}"
            meta = {
                "title": title,
                "canonical_url": canonical_url,
                "tags": tags,
                "source_path": str(p),
                "doc_id": doc_id,
                "chunk_index": i,
                "profile": profile,
                "model_name": model_name,
                "chunk_size": chunk_size,
                "overlap": overlap,
                "run_label": run_label,
            }
            meta.update(annots)

            ids_batch.append(chunk_id)
            docs_batch.append(ch)
            metas_batch.append(meta)

            if len(docs_batch) >= batch:
                embs = embed_passages(model, docs_batch, model_name)
                coll.add(ids=ids_batch, documents=docs_batch, metadatas=metas_batch, embeddings=embs)
                total_chunks += len(docs_batch)
                ids_batch, docs_batch, metas_batch = [], [], []

        if idx % 20 == 0 or idx == total_files:
            yield (log(f"📦 Processed {idx}/{total_files} files… (chunks so far: {total_chunks})"),
                   collection_name, idx, total_files, "", rows_to_table(load_collections_with_manifests(db_dir, base)))

    if docs_batch:
        embs = embed_passages(model, docs_batch, model_name)
        coll.add(ids=ids_batch, documents=docs_batch, metadatas=metas_batch, embeddings=embs)
        total_chunks += len(docs_batch)

    # Manifest write/refresh
    manifest = {
        "collection": collection_name,
        "base": base,
        "profile": profile,
        "model_name": model_name,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "run_label": run_label,
        "annotations": annots,
        "db_dir": db_dir,
        "md_dir": md_dir,
        "host": socket.gethostname(),
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "count": coll.count(),
    }
    mdir = os.path.join(db_dir, "_collections")
    os.makedirs(mdir, exist_ok=True)
    mpath = os.path.join(mdir, f"{collection_name}.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    yield (log(f"✅ Done. Collection '{collection_name}' now has {coll.count()} items.\nManifest: {mpath}"),
           collection_name, total_files, total_files, mpath, rows_to_table(load_collections_with_manifests(db_dir, base)))


# ---------------- Utility to list collections ----------------

def list_collections(db_dir: str, base: str):
    rows = load_collections_with_manifests(db_dir, base)
    return rows_to_table(rows)


# ---------------- Build the GUI ----------------

def build_ui():
    with gr.Blocks(title="Chroma Collections — Create & Inspect", css=".small{font-size:0.9em}") as demo:
        gr.Markdown("# Chroma Collections — Create & Inspect")

        with gr.Tab("Create new collection"):
            with gr.Row():
                md_dir = gr.Textbox(value=DEFAULT_MD_DIR, label="Markdown folder (md_dir)")
                db_dir = gr.Textbox(value=DEFAULT_DB_DIR, label="Chroma DB folder (db_dir)")
            with gr.Row():
                base = gr.Textbox(value=DEFAULT_BASE, label="Base collection name (base)")
                profile = gr.Textbox(value="bge_s650_o15", label="Profile (suffix)")
                model = gr.Dropdown(
                    choices=[
                        "BAAI/bge-base-en-v1.5",
                        "BAAI/bge-small-en-v1.5",
                        "intfloat/e5-large-v2",
                        "sentence-transformers/all-MiniLM-L6-v2",
                    ],
                    value="BAAI/bge-base-en-v1.5",
                    label="Embedding model"
                )
            with gr.Row():
                chunk_size = gr.Slider(300, 1200, value=650, step=10, label="Chunk size (chars)")
                overlap = gr.Slider(0.0, 0.30, value=0.15, step=0.01, label="Overlap (ratio)")
                batch = gr.Slider(8, 256, value=64, step=8, label="Batch add size")
            run_label = gr.Textbox(value="BGE v1.5 / 650c / 15% overlap", label="Run label (free text)")
            annotations = gr.Textbox(
                value="corpus=wordpress\nnotes=first_run",
                lines=3,
                label="Annotations (KEY=VALUE per line)"
            )

            with gr.Row():
                start = gr.Button("Start embedding ▶️", variant="primary")
                # Also show current collections after embedding
                refresh_after = gr.Button("Refresh collections")

            with gr.Row():
                log_md = gr.Markdown("Logs will appear here…", elem_classes=["small"])
            with gr.Row():
                coll_out = gr.Textbox(label="Collection name")
                prog_now = gr.Number(label="Processed files")
                prog_total = gr.Number(label="Total files")
                manifest_out = gr.Textbox(label="Manifest path")

            collist_create = gr.Dataframe(
                headers=["profile","collection","model_name","chunk_size","overlap","run_label","annotations","count","updated_at","manifest_path"],
                label="Collections in db_dir",
                wrap=True
            )

            start.click(
                fn=run_embed,
                inputs=[md_dir, db_dir, base, profile, model, chunk_size, overlap, batch, run_label, annotations],
                outputs=[log_md, coll_out, prog_now, prog_total, manifest_out, collist_create],
                show_progress=True,
                queue=True,  # enable streaming yields
            )
            refresh_after.click(
                fn=list_collections,
                inputs=[db_dir, base],
                outputs=[collist_create]
            )

        with gr.Tab("Inspect collections"):
            db_dir_i = gr.Textbox(value=DEFAULT_DB_DIR, label="Chroma DB folder (db_dir)")
            base_i   = gr.Textbox(value=DEFAULT_BASE, label="Base collection name (base)")
            refresh = gr.Button("Refresh list")

            table = gr.Dataframe(
                headers=["profile","collection","model_name","chunk_size","overlap","run_label","annotations","count","updated_at","manifest_path"],
                label="Discovered collections (with parameters)",
                wrap=True
            )
            refresh.click(
                fn=list_collections,
                inputs=[db_dir_i, base_i],
                outputs=[table]
            )

        # Initial load
        demo.load(list_collections, inputs=[DEFAULT_DB_DIR, DEFAULT_BASE], outputs=[table])

    return demo


if __name__ == "__main__":
    ui = build_ui()
    # Port 0 = auto-free port; set inbrowser=True to auto-open
    ui.launch(server_name="127.0.0.1", server_port=0, inbrowser=True, show_error=True, quiet=True)
