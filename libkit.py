"""libkit: shared helpers for the library. Standard library + pyyaml only.

Layout (relative to the library root):
  config.yaml, tags.yaml, CLAUDE.md, README.md
  papers/pdf/<key>.pdf          originals
  papers/doc/<key>/text.md      docling full text, figures/ next to it
  papers/notes/<key>.md         frontmatter (metadata, tags) + your notes
  books/<subject>/*.pdf
  reviews/<name>/
"""
from __future__ import annotations
import json, os, re, unicodedata, yaml
from pathlib import Path

ROOT = Path(os.environ.get("LIB_ROOT", Path(__file__).resolve().parent.parent))
PDF, DOC, NOTES, BOOKS, REVIEWS = (ROOT / "papers/pdf", ROOT / "papers/doc", ROOT / "papers/notes", ROOT / "books", ROOT / "reviews")

DEFAULT_CONFIG = {
    "key_format": "{author}-{year}-{title2}",
    "max_tags": 5,
    "pdf_opener": "xdg-open",
    "citation_style": "nature",
    "graph_edges": "tags",
    "port": 8765,
}

def config() -> dict:
    p = ROOT / "config.yaml"
    c = dict(DEFAULT_CONFIG)
    if p.exists():
        c.update(yaml.safe_load(p.read_text()) or {})
    return c

# ---------- text helpers ----------
STOP = set("a an the of on in for and or to from with by at into as is are be via its their our this that these those using toward towards between during after before over under without within how what why when does do".split())

def ascii_fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).encode("ascii", "ignore").decode()

def norm_title(t: str) -> str:
    t = ascii_fold(t).lower()
    t = re.sub(r"[{}\\]", "", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def slug(s: str) -> str:
    s = ascii_fold(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

def make_key(first_author_surname: str, year, title: str, fmt: str = DEFAULT_CONFIG["key_format"]) -> str:
    words = [w for w in norm_title(title).split() if w not in STOP and len(w) >= 3]
    if not words:
        words = norm_title(title).split() or ["untitled"]
    title2 = "-".join(words[:2])
    author = slug(first_author_surname) or "anon"
    y = str(year) if year else "nd"
    return fmt.format(author=author, year=y, title2=title2)

# ---------- bibtex ----------
def parse_bibtex(text: str) -> list[dict]:
    """Minimal BibTeX parser: handles {..} with nesting and ".." values, multi-line fields, @comment."""
    entries, i, n = [], 0, len(text)
    while True:
        at = text.find("@", i)
        if at < 0:
            break
        m = re.match(r"@(\w+)\s*\{", text[at:])
        if not m:
            i = at + 1
            continue
        etype = m.group(1).lower()
        j = at + m.end()
        if etype in ("comment", "preamble", "string"):
            depth, k = 1, j
            while k < n and depth:
                depth += (text[k] == "{") - (text[k] == "}")
                k += 1
            i = k
            continue
        # key
        comma = text.find(",", j)
        key = text[j:comma].strip()
        k = comma + 1
        fields = {}
        while k < n:
            # skip whitespace and commas
            while k < n and text[k] in " \t\r\n,":
                k += 1
            if k >= n or text[k] == "}":
                k += 1
                break
            eq = text.find("=", k)
            name = text[k:eq].strip().lower()
            k = eq + 1
            while k < n and text[k] in " \t\r\n":
                k += 1
            if text[k] == "{":
                depth, start = 1, k + 1
                k += 1
                while k < n and depth:
                    depth += (text[k] == "{") - (text[k] == "}")
                    k += 1
                val = text[start:k - 1]
            elif text[k] == '"':
                start = k + 1
                k += 1
                depth = 0
                while k < n:
                    if text[k] == "{":
                        depth += 1
                    elif text[k] == "}":
                        depth -= 1
                    elif text[k] == '"' and depth == 0:
                        break
                    k += 1
                val = text[start:k]
                k += 1
            else:
                end = k
                while end < n and text[end] not in ",}\n#":
                    end += 1
                val = text[k:end]
                k = end
            # skip any '# "..."' concatenation up to the field separator
            while k < n and text[k] not in ",}":
                if text[k] == '"':
                    k = text.find('"', k + 1) + 1
                    if k == 0:
                        k = n
                else:
                    k += 1
            fields[name] = clean_bib_value(val)
        entries.append({"type": etype, "bibkey": key, **fields})
        i = k
    return entries

LATEX_MAP = {r"\&": "&", r"\%": "%", r"\$": "$", r"\_": "_", r"\#": "#", "--": "–", "---": "—", "~": " "}

def clean_bib_value(v: str) -> str:
    v = re.sub(r"\s+", " ", v).strip()
    for a, b in LATEX_MAP.items():
        v = v.replace(a, b)
    v = re.sub(r"\\['`^\"~=.uvHtcdb]\{?(\w)\}?", r"\1", v)  # accents like \'e
    v = v.replace("{", "").replace("}", "")
    return v.strip()

def split_authors(a: str) -> list[str]:
    """'Last, First and Last2, First2' -> ['Last, First', 'Last2, First2']; 'First Last' -> 'Last, First'."""
    out = []
    for part in re.split(r"\s+and\s+", a):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            out.append(re.sub(r"\s+", " ", part))
        else:
            bits = part.split()
            out.append(f"{bits[-1]}, {' '.join(bits[:-1])}" if len(bits) > 1 else part)
    return out

def first_surname(authors: list[str]) -> str:
    if not authors:
        return ""
    sur = authors[0].split(",")[0].strip()
    return sur.replace(" ", "")

def split_keywords(k: str) -> list[str]:
    return [x.strip() for x in re.split(r"[;,]", k) if x.strip()]

# ---------- notes (frontmatter) ----------
FM_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.S)

def read_note(path: Path) -> tuple[dict, str]:
    txt = path.read_text(encoding="utf-8")
    m = FM_RE.match(txt)
    if not m:
        return {}, txt
    meta = yaml.safe_load(m.group(1)) or {}
    return meta, m.group(2)

def write_note(path: Path, meta: dict, body: str = "") -> None:
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=10**6, default_flow_style=None)
    path.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")

def all_notes() -> dict[str, tuple[dict, str]]:
    out = {}
    for p in sorted(NOTES.glob("*.md")):
        meta, body = read_note(p)
        out[meta.get("key", p.stem)] = (meta, body)
    return out

def doc_path(key: str) -> Path:
    return DOC / key / "text.md"

def build_index() -> dict:
    """index.json: what the page and agents read first. Derived from notes + what exists on disk."""
    papers = []
    for key, (meta, body) in all_notes().items():
        papers.append({
            **{k: meta.get(k) for k in ("key", "title", "authors", "year", "journal", "doi", "type", "tags", "cites", "old_labels")},
            "abstract": meta.get("abstract") or "",
            "pdf": (PDF / f"{key}.pdf").exists(),
            "doc": doc_path(key).exists(),
            "note_len": len(body.strip()),
        })
    unprocessed = sorted(p.name for p in PDF.glob("*.pdf") if not (NOTES / f"{p.stem}.md").exists())
    missing_text = sorted(p.stem for p in PDF.glob("*.pdf") if (NOTES / f"{p.stem}.md").exists() and not doc_path(p.stem).exists())
    tags = {}
    tp = ROOT / "tags.yaml"
    if tp.exists():
        tags = yaml.safe_load(tp.read_text()) or {}
    idx = {"papers": papers, "unprocessed": unprocessed, "missing_text": missing_text, "tags": tags}
    (ROOT / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=0), encoding="utf-8")
    return idx
