"""BibTeX for a set of keys, or for a tag.   python3 code/export_bib.py key1 key2 ...  |  --tag remapping  > out.bib"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libkit as L

def entry(meta: dict) -> str:
    f = {"title": meta.get("title", ""), "author": " and ".join(meta.get("authors") or []), "journal": meta.get("journal", ""),
         "year": meta.get("year", ""), "doi": meta.get("doi", ""), "url": meta.get("url", ""), "pmid": meta.get("pmid", "")}
    etype = meta.get("type") if meta.get("type") in ("article", "book", "phdthesis", "misc", "incollection") else "misc"
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in f.items() if v)
    return f"@{etype}{{{meta['key']},\n{body}\n}}\n"

def main(argv):
    notes = L.all_notes()
    if argv[:1] == ["--tag"]:
        keys = [k for k, (m, _) in notes.items() if argv[1] in (m.get("tags") or [])]
    else:
        keys = argv
    sys.stdout.write("".join(entry(notes[k][0]) for k in keys if k in notes))

if __name__ == "__main__":
    main(sys.argv[1:])
