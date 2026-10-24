"""The local helper behind the page. Standard library only.

  python3 code/helper.py            serves http://localhost:8765 (port from config.yaml)

Routes (all JSON unless noted):
  GET  /                      the page (code/library.html)
  GET  /code/<file>           style.css, vendor files
  GET  /api/index             index.json, rebuilt from notes on every call
  GET  /api/note?key=         {meta, body}
  POST /api/tags              {key, tags[]}             -> writes frontmatter
  POST /api/note              {key, body}               -> writes the free-text part
  POST /api/open              {key} | {file}            -> opens pdf with config.pdf_opener
  GET  /pdf/<key>.pdf         the pdf itself (browser viewer fallback)
  GET  /doc/<key>             text.md rendered as plain text/markdown
  GET  /api/export.bib?keys=a,b   BibTeX for the selection (text/plain)
  POST /api/review            {name, keys[]}            -> reviews/<name>/ with symlinks + brief.md
  GET  /api/unprocessed       pdfs in papers/pdf without note or doc, with match suggestions
  POST /api/convert           {files:[{file, tags[], attach_to?}]} -> background docling + note
  GET  /api/convert/status
  GET  /api/dupes             suspected duplicate notes
  POST /api/merge             {keep, drop}
  POST /api/tagdef            {kind, tag, meaning}  add a tag to tags.yaml;  DELETE semantics via {tag, delete:true}
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, threading, time, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libkit as L
import yaml

CODE = Path(__file__).resolve().parent
CFG = L.config()
STATE = {"convert": {"running": False, "queue": [], "done": [], "failed": [], "current": None, "log": []}}
LOCK = threading.Lock()

# ---------- helpers ----------
def note_path(key: str) -> Path:
    return L.NOTES / f"{key}.md"

def safe_key(k: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,120}", k or ""):
        raise ValueError("bad key")
    return k

def tags_vocab() -> dict:
    p = L.ROOT / "tags.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}

def flat_tags(v: dict) -> set:
    return {t for kind in v.values() if isinstance(kind, dict) for t in kind}

def bib_entry(meta: dict) -> str:
    key = meta["key"]
    authors = " and ".join(meta.get("authors") or [])
    f = {"title": meta.get("title", ""), "author": authors, "journal": meta.get("journal", ""), "year": meta.get("year", ""),
         "doi": meta.get("doi", ""), "url": meta.get("url", ""), "pmid": meta.get("pmid", "")}
    etype = {"article": "article", "book": "book", "phdthesis": "phdthesis", "misc": "misc"}.get(meta.get("type") or "article", "misc")
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in f.items() if v)
    return f"@{etype}{{{key},\n{body}\n}}\n"

def pdf_text_first_page(pdf: Path) -> str:
    try:
        return subprocess.run(["pdftotext", "-l", "2", str(pdf), "-"], capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ""

def find_doi(text: str) -> str:
    m = re.search(r"10\.\d{4,9}/[^\s\"'<>]+", text)
    return m.group(0).rstrip(".,;)") if m else ""

def suggest_match(pdf: Path, notes: dict) -> dict | None:
    """Suggest an existing note for an unprocessed pdf: by DOI on the first pages, then by title words."""
    txt = pdf_text_first_page(pdf)
    doi = find_doi(txt).lower()
    if doi:
        for k, (m, _) in notes.items():
            if (m.get("doi") or "").lower() == doi:
                return {"key": k, "title": m.get("title"), "how": "doi", "has_pdf": (L.PDF / f"{k}.pdf").exists()}
    stem_t = L.norm_title(pdf.stem.split(" - ", 1)[-1])
    best = None
    for k, (m, _) in notes.items():
        t = L.norm_title(m.get("title", ""))
        if len(t) > 15 and (t[:40] in stem_t or stem_t[:40] in t):
            best = {"key": k, "title": m.get("title"), "how": "title", "has_pdf": (L.PDF / f"{k}.pdf").exists()}
            break
    return best

def crossref(doi: str) -> dict | None:
    try:
        import urllib.request
        req = urllib.request.Request(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}", headers={"User-Agent": "lib-helper (mailto:local@localhost)"})
        with urllib.request.urlopen(req, timeout=8) as r:
            msg = json.load(r)["message"]
        authors = [f"{a.get('family','')}, {a.get('given','')}".strip(", ") for a in msg.get("author", [])]
        year = (msg.get("issued", {}).get("date-parts") or [[None]])[0][0]
        return {"title": (msg.get("title") or [""])[0], "authors": authors, "year": year,
                "journal": (msg.get("container-title") or [""])[0], "doi": doi, "abstract": re.sub(r"<[^>]+>", "", msg.get("abstract", "")),
                "type": "article"}
    except Exception:
        return None

def meta_from_filename(pdf: Path) -> dict:
    m = re.match(r"(.+?)\s+(?:et al\.?\s+)?(\d{4})\s+-\s+(.+)", pdf.stem)
    if m:
        return {"title": m.group(3), "authors": [m.group(1)], "year": int(m.group(2)), "journal": "", "doi": "", "type": "article"}
    return {"title": pdf.stem, "authors": [], "year": None, "journal": "", "doi": "", "type": "article"}

# ---------- conversion worker ----------
def convert_worker():
    while True:
        with LOCK:
            if not STATE["convert"]["queue"]:
                STATE["convert"]["running"] = False
                STATE["convert"]["current"] = None
                return
            job = STATE["convert"]["queue"].pop(0)
            STATE["convert"]["current"] = job["file"]
        try:
            convert_one(job)
            with LOCK:
                STATE["convert"]["done"].append(job["file"])
        except Exception as e:  # noqa
            with LOCK:
                STATE["convert"]["failed"].append({"file": job["file"], "error": str(e)[:300]})

def convert_one(job: dict):
    src = L.PDF / job["file"]
    if not src.exists():
        raise FileNotFoundError(job["file"])
    notes = L.all_notes()
    key = job.get("attach_to")
    if key and key in notes:
        meta, body = notes[key]
    else:
        txt = pdf_text_first_page(src)
        doi = find_doi(txt)
        meta = (crossref(doi) if doi else None) or meta_from_filename(src)
        if doi and not meta.get("doi"):
            meta["doi"] = doi
        surname = (meta["authors"][0].split(",")[0] if meta.get("authors") else "anon")
        key = L.make_key(surname, meta.get("year"), meta.get("title") or src.stem, CFG["key_format"])
        base, suf = key, "b"
        while key in notes or note_path(key).exists():
            key = f"{base}-{suf}"; suf = chr(ord(suf) + 1)
        meta = {"key": key, "title": meta.get("title", ""), "authors": meta.get("authors", []), "year": meta.get("year"),
                "journal": meta.get("journal", ""), "doi": meta.get("doi", ""), "type": meta.get("type", "article"),
                "tags": [], "old_labels": [], "cites": [], "abstract": meta.get("abstract", ""), "imported": "inbox"}
        body = "\n"
    meta["tags"] = [t for t in dict.fromkeys((meta.get("tags") or []) + job.get("tags", []))][:CFG["max_tags"]]
    L.write_note(note_path(key), meta, body)
    dst_pdf = L.PDF / f"{key}.pdf"
    if src != dst_pdf:
        if dst_pdf.exists():
            dst_pdf.unlink()
        src.rename(dst_pdf)
    # docling
    out = L.DOC / key
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "text.md").exists():
        tmp = out / "_tmp"
        tmp.mkdir(exist_ok=True)
        r = subprocess.run(["docling", "convert", "--to", "md", "--image-export-mode", "referenced", "--output", ".", "--device", "cpu",
                            "--num-threads", str(max(2, os.cpu_count() // 2)), "--no-abort-on-error", str(dst_pdf)],
                           cwd=tmp, capture_output=True, text=True, timeout=3600)
        md = tmp / f"{key}.md"
        if not md.exists():
            shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError("docling produced no markdown: " + r.stderr[-300:])
        txt = md.read_text(encoding="utf-8")
        art = tmp / f"{key}_artifacts"
        fig = out / "figures"
        fig.mkdir(exist_ok=True)
        if art.exists():
            for p in art.iterdir():
                shutil.move(str(p), fig / p.name)
        txt = re.sub(r"\]\([^)]*?_artifacts/([^)]+)\)", lambda m: f"](figures/{urllib.parse.unquote(m.group(1))})", txt)
        (out / "text.md").write_text(txt, encoding="utf-8")
        shutil.rmtree(tmp, ignore_errors=True)

# ---------- http ----------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def js(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode())

    def file(self, path: Path, ctype: str):
        if not path.exists() or not path.is_file():
            return self._send(404, b"not found", "text/plain")
        self._send(200, path.read_bytes(), ctype)

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        try:
            if p == "/" or p == "/index.html":
                return self.file(CODE / "library.html", "text/html; charset=utf-8")
            if p.startswith("/code/"):
                rel = p[len("/code/"):]
                if ".." in rel:
                    return self._send(403, b"no", "text/plain")
                ct = {"css": "text/css", "js": "application/javascript", "woff2": "font/woff2", "html": "text/html; charset=utf-8"}.get(rel.rsplit(".", 1)[-1], "application/octet-stream")
                return self.file(CODE / rel, ct)
            if p == "/api/index":
                return self.js(L.build_index())
            if p == "/api/note":
                key = safe_key(q.get("key", [""])[0])
                if not note_path(key).exists():
                    return self.js({"error": "no note"}, 404)
                meta, body = L.read_note(note_path(key))
                return self.js({"meta": meta, "body": body})
            if p.startswith("/pdf/"):
                key = safe_key(urllib.parse.unquote(p[5:]).removesuffix(".pdf"))
                return self.file(L.PDF / f"{key}.pdf", "application/pdf")
            if p.startswith("/doc/"):
                key = safe_key(urllib.parse.unquote(p[5:]))
                return self.file(L.doc_path(key), "text/plain; charset=utf-8")
            if p.startswith("/figures/"):
                # /figures/<key>/<file>
                key, _, name = urllib.parse.unquote(p[9:]).partition("/")
                if ".." in name:
                    return self._send(403, b"no", "text/plain")
                return self.file(L.DOC / safe_key(key) / "figures" / name, "image/png")
            if p == "/api/export.bib":
                keys = [k for k in q.get("keys", [""])[0].split(",") if k]
                notes = L.all_notes()
                out = "".join(bib_entry(notes[k][0]) for k in keys if k in notes)
                return self._send(200, out.encode(), "text/plain; charset=utf-8")
            if p == "/api/unprocessed":
                notes = L.all_notes()
                items = []
                with_text = q.get("all", ["0"])[0] == "1"
                for f in sorted(L.PDF.glob("*.pdf")):
                    k = f.stem
                    has_note, has_doc = (k in notes), L.doc_path(k).exists()
                    if has_note and (has_doc or not with_text):
                        continue
                    item = {"file": f.name, "has_note": has_note, "has_doc": has_doc, "size_mb": round(f.stat().st_size / 1e6, 1)}
                    if not has_note:
                        item["suggest"] = suggest_match(f, notes)
                    items.append(item)
                return self.js({"items": items})
            if p == "/api/convert/status":
                with LOCK:
                    return self.js(STATE["convert"])
            if p == "/api/dupes":
                notes = L.all_notes()
                by_doi, by_title, pairs = {}, {}, []
                for k, (m, _) in notes.items():
                    d = (m.get("doi") or "").lower()
                    t = L.norm_title(m.get("title", ""))
                    if d:
                        if d in by_doi:
                            pairs.append({"a": by_doi[d], "b": k, "how": "doi"})
                        else:
                            by_doi[d] = k
                    if len(t) > 15:
                        if t in by_title and not any(x["b"] == k for x in pairs):
                            pairs.append({"a": by_title[t], "b": k, "how": "title"})
                        else:
                            by_title.setdefault(t, k)
                return self.js({"pairs": pairs})
            if p == "/api/tags":
                return self.js(tags_vocab())
            return self._send(404, b"not found", "text/plain")
        except ValueError as e:
            return self.js({"error": str(e)}, 400)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            d = self.body()
            if p == "/api/tags":
                key = safe_key(d["key"])
                vocab = flat_tags(tags_vocab())
                tags = [t for t in dict.fromkeys(d.get("tags", [])) if t in vocab][:CFG["max_tags"]]
                meta, body = L.read_note(note_path(key))
                meta["tags"] = tags
                L.write_note(note_path(key), meta, body)
                return self.js({"ok": True, "tags": tags})
            if p == "/api/note":
                key = safe_key(d["key"])
                meta, _ = L.read_note(note_path(key))
                L.write_note(note_path(key), meta, d.get("body", ""))
                return self.js({"ok": True})
            if p == "/api/open":
                if d.get("key"):
                    f = L.PDF / f"{safe_key(d['key'])}.pdf"
                else:
                    name = Path(d.get("file", "")).name
                    f = L.PDF / name
                if not f.exists():
                    return self.js({"error": "no pdf"}, 404)
                subprocess.Popen([CFG["pdf_opener"], str(f)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return self.js({"ok": True})
            if p == "/api/review":
                name = L.slug(d.get("name", ""))[:60]
                if not name:
                    return self.js({"error": "name"}, 400)
                keys = [safe_key(k) for k in d.get("keys", [])]
                rd = L.REVIEWS / name
                (rd / "papers").mkdir(parents=True, exist_ok=True)
                notes = L.all_notes()
                for k in keys:
                    for src, dst in ((L.PDF / f"{k}.pdf", rd / "papers" / f"{k}.pdf"), (L.DOC / k, rd / "papers" / k), (note_path(k), rd / "papers" / f"{k}.md")):
                        if src.exists() and not dst.exists():
                            os.symlink(os.path.relpath(src, dst.parent), dst)
                brief = rd / "brief.md"
                if not brief.exists():
                    lst = "\n".join(f"- {k}: {notes[k][0].get('title','')}" for k in keys if k in notes)
                    brief.write_text(f"# {name}\n\n## Question\n\n\n## Focus on\n\n\n## Skip\n\n\n## Length and audience\n\n\n## Papers ({len(keys)})\n{lst}\n")
                return self.js({"ok": True, "path": str(rd), "n": len(keys)})
            if p == "/api/convert":
                files = d.get("files", [])
                with LOCK:
                    for it in files:
                        name = Path(it.get("file", "")).name
                        if (L.PDF / name).exists():
                            STATE["convert"]["queue"].append({"file": name, "tags": it.get("tags", []), "attach_to": it.get("attach_to")})
                    if not STATE["convert"]["running"]:
                        STATE["convert"]["running"] = True
                        threading.Thread(target=convert_worker, daemon=True).start()
                    return self.js(STATE["convert"])
            if p == "/api/merge":
                keep, drop = safe_key(d["keep"]), safe_key(d["drop"])
                mk, kb = L.read_note(note_path(keep))
                md_, db = L.read_note(note_path(drop))
                for f in ("doi", "abstract", "journal", "url", "pmid"):
                    if not mk.get(f) and md_.get(f):
                        mk[f] = md_[f]
                mk["tags"] = list(dict.fromkeys((mk.get("tags") or []) + (md_.get("tags") or [])))[:CFG["max_tags"]]
                mk["old_labels"] = list(dict.fromkeys((mk.get("old_labels") or []) + (md_.get("old_labels") or [])))
                mk.setdefault("merged_from", []).append(drop)
                L.write_note(note_path(keep), mk, kb + (("\n\n" + db) if db.strip() else ""))
                if not (L.PDF / f"{keep}.pdf").exists() and (L.PDF / f"{drop}.pdf").exists():
                    (L.PDF / f"{drop}.pdf").rename(L.PDF / f"{keep}.pdf")
                if not L.doc_path(keep).exists() and L.doc_path(drop).exists():
                    shutil.move(str(L.DOC / drop), str(L.DOC / keep))
                for pth in (note_path(drop), L.PDF / f"{drop}.pdf"):
                    if pth.exists():
                        pth.unlink()
                if (L.DOC / drop).exists():
                    shutil.rmtree(L.DOC / drop)
                return self.js({"ok": True})
            if p == "/api/tagdef":
                v = tags_vocab()
                tag = L.slug(d.get("tag", ""))
                if not tag:
                    return self.js({"error": "tag"}, 400)
                if d.get("delete"):
                    for kind in v.values():
                        if isinstance(kind, dict):
                            kind.pop(tag, None)
                    for k, (m, b) in L.all_notes().items():
                        if tag in (m.get("tags") or []):
                            m["tags"] = [t for t in m["tags"] if t != tag]
                            L.write_note(note_path(k), m, b)
                else:
                    kind = d.get("kind") if d.get("kind") in ("topic", "method", "object") else "topic"
                    v.setdefault(kind, {})[tag] = d.get("meaning", "")
                (L.ROOT / "tags.yaml").write_text(yaml.safe_dump(v, sort_keys=False, allow_unicode=True))
                return self.js({"ok": True, "tags": v})
            return self._send(404, b"not found", "text/plain")
        except (KeyError, ValueError) as e:
            return self.js({"error": str(e)}, 400)
        except Exception as e:  # noqa
            return self.js({"error": repr(e)[:300]}, 500)

def main():
    port = int(CFG.get("port", 8765))
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"lib helper at http://localhost:{port}  (root {L.ROOT})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
