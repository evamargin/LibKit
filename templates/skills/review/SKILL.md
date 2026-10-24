---
name: review
description: Write an HTML review of the papers in reviews/<name>/ following the owner's brief. Use when the user types /review <name> or asks for a review of a review folder.
---

# /review <name>

Input: `reviews/<name>/brief.md` (the owner's question, focus, what to skip, length and audience; may be mostly empty) and `reviews/<name>/papers/` (symlinks: `<key>.pdf`, `<key>.md` note with frontmatter, `<key>/text.md` full text with `figures/`).

Output: `reviews/<name>/<name>.html` built from `code/review_template.html`, plus `reviews/<name>/figures/` with the figures you use.

## Procedure
1. Read `brief.md`. If the Question heading is empty, derive the question from the folder name and the shared tags of the papers, and state it in the lead.
2. Read every note (`papers/<key>.md`) for metadata and abstract. Read `papers/<key>/text.md` for the papers that carry the argument; skim the rest. Respect "Skip" in the brief.
3. Plan 4 to 7 sections that answer the question. Order by logic, not by paper. A typical shape: what is known, how it was shown (methods that matter), where papers disagree, what is missing, what to do next. Follow the brief when it gives a structure.
4. Write. Short sentences. One idea per sentence. Every claim carries a key citation `<span class="cite">[<a href="#ref-KEY">Author Year</a>]</span>`. One `<mark>` sentence per section: the thing to remember. Disagreements and caveats in `<div class="note red">`, replicated findings in `<div class="note green">`. No filler, no hedging phrases.
5. Figures: pick at most one per section where it carries the point. Copy `papers/<key>/figures/<file>` to `reviews/<name>/figures/<key>_<file>`; `<img src="figures/...">` with a caption that says what to see and cites the key. Figures with a base64 payload or under 5 KB are usually icons; skip them.
6. Reference list: one `<li id="ref-KEY">` per cited paper, formatted in the citation style from `config.yaml` (nature: Authors. Title. Journal Year;doi). Also write `reviews/<name>/<name>.bib` with `python3 code/export_bib.py <keys>`.
7. Fill the template placeholders: TITLE, DATE (today), N (papers read), LEAD (two sentences: the question and the answer), SECTIONS, REFERENCES. Keep the `<link rel="stylesheet" href="../../code/style.css">` path.
8. Open nothing, change no notes, add no tags. Report in two lines: the file path, and which papers you leaned on most. Mention papers in the folder you did not use and why.

## Length
Default 1200 to 2000 words. The brief's "Length and audience" overrides.
