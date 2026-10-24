"""Place docling output into papers/doc/<key>/text.md + figures/.

  python3 code/place_docs.py --staging <dir with <stem>/<stem>.md> [--map import/pdf_map.json] [--only done.txt]

Idempotent: a key whose text.md exists is skipped. Image links '<stem>_artifacts/x.png' become 'figures/x.png'.
Stems with no key in the map get a key from the file name (unprocessed orphans).
"""
from __future__ import annotations
import argparse, json, re, shutil, sys
from pathlib import Path
from urllib.parse import unquote
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libkit as L

def key_from_stem(stem: str) -> str:
    m = re.match(r"(.+?)\s+(?:et al\.?\s+)?(\d{4})\s+-\s+(.+)", stem)
    if m:
        return L.make_key(m.group(1).split()[0], m.group(2), m.group(3))
    return L.slug(stem)[:60]

def place(src_md: Path, key: str) -> bool:
    dst_dir = L.DOC / key
    dst = dst_dir / "text.md"
    if dst.exists():
        return False
    stem = src_md.stem
    art = src_md.parent / f"{stem}_artifacts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    txt = src_md.read_text(encoding="utf-8")
    if art.exists():
        fig = dst_dir / "figures"
        fig.mkdir(exist_ok=True)
        for p in art.iterdir():
            if not (fig / p.name).exists():
                shutil.copy2(p, fig / p.name)
    # rewrite links: ![Image](<anything>_artifacts/<file>) -> figures/<file>
    txt = re.sub(r"\]\([^)]*?_artifacts/([^)]+)\)", lambda m: f"](figures/{unquote(m.group(1))})", txt)
    dst.write_text(txt, encoding="utf-8")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", required=True)
    ap.add_argument("--map", default=str(L.ROOT / "import/pdf_map.json"))
    ap.add_argument("--only", default=None, help="done.txt: only stems listed there (finished conversions)")
    a = ap.parse_args()
    staging = Path(a.staging)
    pdf_map = json.loads(Path(a.map).read_text()) if Path(a.map).exists() else {}
    only = None
    if a.only:
        only = {line.split("\t")[-1].strip() for line in Path(a.only).read_text().splitlines() if line.startswith("OK")}
    placed, skipped, nokey = 0, 0, []
    notes = L.all_notes()
    for d in sorted(staging.iterdir()):
        md = d / f"{d.name}.md"
        if not d.is_dir() or not md.exists() or md.stat().st_size == 0:
            continue
        if only is not None and d.name not in only:
            continue
        key = pdf_map.get(d.name) or pdf_map.get(re.sub(r"\(\d+\)$", "", d.name))
        if not key:
            # last resort: a note whose title starts like the file name's title part
            t = L.norm_title(d.name.split(" - ", 1)[-1])[:40]
            for k2, (m2, _) in notes.items():
                if t and L.norm_title(m2.get("title", "")).startswith(t):
                    key = k2
                    break
        if not key:
            # orphan pdf copied under its original name -> note will be created by the helper on convert; use stem key
            key = key_from_stem(d.name)
            nokey.append((d.name, key))
        if place(md, key):
            placed += 1
        else:
            skipped += 1
    print(f"placed {placed}, already there {skipped}, no key in map {len(nokey)}")
    for s, k in nokey:
        print("   no-key:", s, "->", k)
    L.build_index()

if __name__ == "__main__":
    main()
