"""One-time import from a Paperpile BibTeX export + its PDF folder.

  python3 code/import_paperpile.py --bib "<file.bib>" --pdfdir "<folder containing 'All Papers'>" [--books books.tsv] [--apply]

Without --apply it only reports. With --apply it writes papers/notes/<key>.md, copies PDFs to papers/pdf/<key>.pdf,
books to books/<subject>/, and saves import/pdf_map.json (pdf stem -> key) for placing docling output later.
"""
from __future__ import annotations
import argparse, collections, json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libkit as L

def load_books(path: Path | None) -> dict[str, str]:
    """books.tsv: <subject>\t<pdf basename>  -> {basename: subject}"""
    if not path or not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if "\t" in line and not line.startswith("#"):
            subj, name = line.split("\t", 1)
            out[name.strip()] = subj.strip()
    return out

def merge(a: dict, b: dict) -> dict:
    """Merge duplicate bib entries: keep longer values, union keywords, prefer the one with an existing pdf."""
    out = dict(a)
    for k, v in b.items():
        if k in ("keywords",):
            out[k] = "; ".join(dict.fromkeys(L.split_keywords(a.get(k, "")) + L.split_keywords(v)))
        elif k == "_pdf":
            out[k] = a.get("_pdf") or v
        elif not out.get(k) or (isinstance(v, str) and len(v) > len(str(out.get(k, "")))):
            out[k] = v
    out.setdefault("_merged_from", []).append(b["bibkey"])
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bib", required=True)
    ap.add_argument("--pdfdir", required=True)
    ap.add_argument("--books", default=None)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    pdfdir, books = Path(a.pdfdir), load_books(Path(a.books) if a.books else None)
    entries = L.parse_bibtex(Path(a.bib).read_text(encoding="utf-8"))
    print(f"bib entries: {len(entries)}")

    # attach pdf paths
    all_pdfs = sorted(pdfdir.rglob("*.pdf"))
    by_stem = {L.norm_title(p.stem): p for p in all_pdfs}
    claimed = set()
    for e in entries:
        e["_pdf"] = None
        for f in [x.strip() for x in e.get("file", "").split(";") if x.strip()]:
            p = pdfdir / f
            if p.exists():
                e["_pdf"] = p
                claimed.add(p)
                break
    # fallback: match remaining pdfs by title words in the file name (Paperpile sanitises names on disk)
    for e in entries:
        if e["_pdf"] or not e.get("title"):
            continue
        t = L.norm_title(e["title"])
        probe = " ".join(t.split()[:6])
        if len(probe) < 15:
            continue
        for stem, p in by_stem.items():
            if p not in claimed and probe in stem:
                e["_pdf"] = p
                claimed.add(p)
                break

    # dedupe by doi, then normalised title
    by_doi, by_title, merged = {}, {}, []
    for e in entries:
        doi = (e.get("doi") or "").lower().strip()
        t = L.norm_title(e.get("title", ""))
        tgt = None
        if doi and doi in by_doi:
            tgt = by_doi[doi]
        elif t and len(t) > 12 and t in by_title:
            tgt = by_title[t]
        if tgt is not None:
            merged.append((tgt["bibkey"], e["bibkey"]))
            if e["_pdf"]:
                claimed.add(e["_pdf"])  # duplicate copy of the pdf, not an orphan
            tgt.update(merge(tgt, e))
            continue
        if doi:
            by_doi[doi] = e
        if t:
            by_title[t] = e
        e["_keep"] = True
    kept = [e for e in entries if e.get("_keep")]
    print(f"after merging duplicates: {len(kept)}  (merged {len(merged)} pairs)")

    # books vs papers
    paper_entries, book_entries = [], []
    for e in kept:
        is_book = e["type"] in ("book",) or (e["_pdf"] and e["_pdf"].name in books)
        (book_entries if is_book else paper_entries).append(e)
    print(f"papers: {len(paper_entries)}  books: {len(book_entries)}")

    # keys
    used, records = {}, []
    for e in sorted(paper_entries, key=lambda x: (x.get("year", ""), x.get("title", ""))):
        authors = L.split_authors(e.get("author", "")) if e.get("author") else []
        key = L.make_key(L.first_surname(authors), e.get("year"), e.get("title", "untitled"))
        base, suffix = key, "b"
        while key in used:
            key = f"{base}-{suffix}"
            suffix = chr(ord(suffix) + 1)
        used[key] = e
        meta = {
            "key": key,
            "title": e.get("title", ""),
            "authors": authors,
            "year": int(e["year"]) if str(e.get("year", "")).isdigit() else (e.get("year") or None),
            "journal": e.get("journal") or e.get("booktitle") or e.get("publisher") or "",
            "doi": e.get("doi", ""),
            "pmid": e.get("pmid", ""),
            "url": e.get("url", ""),
            "type": e["type"],
            "tags": [],
            "old_labels": L.split_keywords(e.get("keywords", "")),
            "cites": [],
            "abstract": e.get("abstract", ""),
            "imported": "paperpile",
        }
        if e.get("_merged_from"):
            meta["merged_from"] = e["_merged_from"]
        records.append((meta, e["_pdf"]))

    # report
    with_pdf = sum(1 for m, p in records if p)
    print(f"papers with pdf: {with_pdf}  without: {len(records) - with_pdf}")
    claimed_stems = {re.sub(r"\(\d+\)$", "", q.stem) for q in claimed}
    dup_copies = [q for q in set(all_pdfs) - claimed if re.sub(r"\(\d+\)$", "", q.stem) in claimed_stems and q.stem != re.sub(r"\(\d+\)$", "", q.stem)]
    orphans = sorted(set(all_pdfs) - claimed - set(dup_copies))
    print(f"duplicate pdf copies ignored: {len(dup_copies)}")
    print(f"pdfs in export with no bib entry: {len(orphans)}")
    for p in orphans[:30]:
        print("   orphan:", p.name)
    for e in book_entries:
        print("   book:", (e["_pdf"].name if e["_pdf"] else "(no pdf)"), "->", books.get(e["_pdf"].name if e["_pdf"] else "", "?"))
    if merged:
        print("merged pairs (first 60):")
        for x, y in merged[:60]:
            print(f"   {x} <- {y}")

    if not a.apply:
        print("\n(dry run; add --apply to write)")
        return

    L.NOTES.mkdir(parents=True, exist_ok=True); L.PDF.mkdir(parents=True, exist_ok=True)
    pdf_map = {}
    for meta, p in records:
        L.write_note(L.NOTES / f"{meta['key']}.md", meta, "\n")
        if p:
            dst = L.PDF / f"{meta['key']}.pdf"
            if not dst.exists():
                shutil.copy2(p, dst)
            pdf_map[p.stem] = meta["key"]
    wanted = []
    for e in book_entries:
        if e["_pdf"]:
            subj = books.get(e["_pdf"].name, "other")
            d = L.BOOKS / subj
            d.mkdir(parents=True, exist_ok=True)
            dst = d / e["_pdf"].name
            if not dst.exists():
                shutil.copy2(e["_pdf"], dst)
        else:
            wanted.append(f"- {e.get('author','')} ({e.get('year','')}). {e.get('title','')}")
    if wanted:
        (L.BOOKS / "wanted.md").write_text("# Books in Paperpile without a PDF\n\n" + "\n".join(wanted) + "\n")
    # orphan pdfs: copy under original name as unprocessed
    for p in orphans:
        if p.name in books:
            d = L.BOOKS / books[p.name]; d.mkdir(parents=True, exist_ok=True)
            if not (d / p.name).exists():
                shutil.copy2(p, d / p.name)
        else:
            dst = L.PDF / p.name
            if not dst.exists():
                shutil.copy2(p, dst)
    (L.ROOT / "import").mkdir(exist_ok=True)
    (L.ROOT / "import/pdf_map.json").write_text(json.dumps(pdf_map, ensure_ascii=False, indent=1))
    (L.ROOT / "import/merged_pairs.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1))
    L.build_index()
    print("written.")

if __name__ == "__main__":
    main()
