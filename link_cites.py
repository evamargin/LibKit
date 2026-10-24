"""Fill `cites` in every note: library papers that appear in this paper's reference list.

  python3 code/link_cites.py            # all papers with text
  python3 code/link_cites.py key ...    # some

Matching is by DOI found in the text, else by first-author surname + year + a distinctive title fragment
appearing in the reference section. Conservative: a miss is better than a wrong edge.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libkit as L

def ref_section(txt: str) -> str:
    low = txt.lower()
    i = max(low.rfind("\n## references"), low.rfind("\n# references"), low.rfind("\nreferences\n"), low.rfind("\n## bibliography"), low.rfind("\n## literature cited"))
    return txt[i:] if i > 0 and i > len(txt) * 0.4 else txt[int(len(txt) * 0.6):]

def main(argv):
    notes = L.all_notes()
    targets = []
    for k, (m, _) in notes.items():
        sur = L.ascii_fold(L.first_surname(m.get("authors") or [])).lower()
        words = [w for w in L.norm_title(m.get("title", "")).split() if w not in L.STOP and len(w) > 3]
        frag = " ".join(words[:3])
        targets.append((k, (m.get("doi") or "").lower(), sur, str(m.get("year") or ""), frag))
    keys = argv or [k for k in notes if L.doc_path(k).exists()]
    changed = total = 0
    for k in keys:
        p = L.doc_path(k)
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        refs = ref_section(txt)
        refs_norm = L.norm_title(refs)
        refs_low = L.ascii_fold(refs).lower()
        found = []
        for k2, doi, sur, year, frag in targets:
            if k2 == k:
                continue
            if doi and len(doi) > 8 and doi in refs_low:
                found.append(k2)
            elif sur and year and frag and len(frag) > 14 and frag in refs_norm and re.search(re.escape(sur) + r"\b.{0,80}?\b" + year, refs_low, re.S):
                found.append(k2)
        found = sorted(set(found))
        m, b = notes[k]
        if (m.get("cites") or []) != found:
            m["cites"] = found
            L.write_note(L.NOTES / f"{k}.md", m, b)
            changed += 1
        total += len(found)
    L.build_index()
    print(f"{len(keys)} papers scanned, {changed} notes updated, {total} citation edges")

if __name__ == "__main__":
    main(sys.argv[1:])
