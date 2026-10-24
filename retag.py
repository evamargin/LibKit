"""Rename or drop a tag across every note (and tags.yaml).

  python3 code/retag.py rename old-tag new-tag
  python3 code/retag.py drop some-tag
  python3 code/retag.py check          # tags used in notes that are not in tags.yaml
"""
import sys, yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libkit as L

def main(argv):
    vocab_p = L.ROOT / "tags.yaml"
    vocab = yaml.safe_load(vocab_p.read_text()) if vocab_p.exists() else {}
    flat = {t: k for k, m in vocab.items() if isinstance(m, dict) for t in m}
    notes = L.all_notes()
    if not argv or argv[0] == "check":
        bad = {}
        for k, (m, _) in notes.items():
            for t in m.get("tags") or []:
                if t not in flat:
                    bad.setdefault(t, []).append(k)
        for t, ks in bad.items():
            print(f"{t}: {len(ks)} notes, e.g. {ks[:3]}")
        print("ok" if not bad else f"{len(bad)} unknown tags")
        return
    op = argv[0]
    old = argv[1]
    new = argv[2] if op == "rename" else None
    n = 0
    for k, (m, b) in notes.items():
        tags = m.get("tags") or []
        if old not in tags:
            continue
        tags = [t for t in tags if t != old]
        if new and new not in tags:
            tags.append(new)
        m["tags"] = tags[:L.config()["max_tags"]]
        L.write_note(L.NOTES / f"{k}.md", m, b)
        n += 1
    kind = flat.get(old)
    if kind:
        meaning = vocab[kind].pop(old)
        if new:
            vocab.setdefault(kind, {})[new] = meaning
        vocab_p.write_text(yaml.safe_dump(vocab, sort_keys=False, allow_unicode=True))
    L.build_index()
    print(f"{op} {old}{' -> ' + new if new else ''}: {n} notes changed")

if __name__ == "__main__":
    main(sys.argv[1:])
