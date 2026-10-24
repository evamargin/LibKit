# lib — how an agent works in this folder

This is a personal paper library. Plain files, no database. Read this first, then `index.json`.

## Layout
- `index.json` — one record per paper: key, title, authors, year, journal, doi, tags, pdf (bool), doc (bool), abstract. Rebuilt by `python3 code/build_index.py`. Start here for any question.
- `papers/notes/<key>.md` — YAML frontmatter (the metadata above, `tags`, `cites`, `old_labels`) followed by the owner's free notes. **The body below the frontmatter belongs to the owner. Never rewrite or summarise into it unless asked in the current conversation.** Changing `tags` is fine when asked.
- `papers/doc/<key>/text.md` — full text from docling, figures in `figures/`. Read this when a question needs more than the abstract.
- `papers/pdf/<key>.pdf` — the original. A pdf whose stem is not a key is unprocessed inbox.
- `books/<subject>/` — books as PDFs, not converted.
- `reviews/<name>/` — `brief.md` (the owner's instructions), `papers/` (symlinks to the chosen pdf, doc and note), and the generated review html.
- `tags.yaml` — the whole vocabulary, grouped in topic / method / object. Max 5 tags per paper. Use only these tags; propose a new one instead of inventing it.
- `config.yaml` — key format, citation style, pdf opener.
- `code/` — the kit (LibKit): helper.py (local page server), build_index.py, link_cites.py, retag.py, export_bib.py, import_paperpile.py, place_docs.py, style.css, review_template.html.

## Keys
`<firstauthor>-<year>-<two-title-words>`, e.g. `english-2017-pyramidal-interneuron`. Same stem for pdf, doc and note. Cite papers by key in answers.

## Answering questions
1. `grep -il <words> papers/notes/*.md` or filter `index.json` by tag; abstracts are in the notes.
2. Open `papers/doc/<key>/text.md` only for the papers that matter. Quote the key with every claim.
3. Say which papers in the library are relevant and what the library lacks. Do not invent papers.

## Writing a review: `/review <name>`
The skill in `.claude/skills/review/` has the procedure. In short: read `reviews/<name>/brief.md`, read the notes and texts linked in `reviews/<name>/papers/`, write `reviews/<name>/<name>.html` from `code/review_template.html` (Fira Mono, white sheet, three pens: red warning / green confirmed / blue action, yellow mark for the one sentence to remember). Reference list from the frontmatter in the style named in `config.yaml`. Figures: copy from `papers/doc/<key>/figures/` into `reviews/<name>/figures/` and reference relatively.

## Rules
- Never delete or move pdfs, docs or notes. Merging duplicates is done on the page by the owner.
- Tags only from `tags.yaml`. To add a tag, add it to `tags.yaml` with a one-line meaning and say so.
- Keep prose short. The owner prefers laconic output and no over-engineering.
