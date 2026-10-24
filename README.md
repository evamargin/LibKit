# LibKit

The code behind a local, offline paper library: PDFs in, markdown text out, tags and notes in plain files, one local page to filter, tag, open and graph, and a terminal (Claude Code) for questions and reviews. Standard library Python plus pyyaml; docling for PDF conversion.

```
git clone <this repo> ~/lib/code
~/lib/code/init.sh          creates the folders, config.yaml, tags.yaml, CLAUDE.md, README.md
~/lib/code/start.sh         helper on http://localhost:8765 and opens the page
```

Then copy PDFs into `~/lib/papers/pdf/`, open the inbox on the page, pick tags, convert.

Layout it creates
```
lib/
  config.yaml  tags.yaml  CLAUDE.md  README.md  index.json
  papers/pdf/<key>.pdf       papers/doc/<key>/text.md + figures/      papers/notes/<key>.md
  books/<subject>/           reviews/<name>/brief.md + papers/ + <name>.html
```

Files here
- `helper.py` local server behind the page (open pdf, save tags and notes, convert, export .bib, review folders, duplicates)
- `library.html`, `style.css`, `vendor/` the page, offline fonts and d3
- `import_paperpile.py` one-time import from a Paperpile BibTeX export and its PDF folder
- `place_docs.py` move docling output into place; `link_cites.py` citation edges; `build_index.py`; `retag.py`; `export_bib.py`
- `review_template.html` and `templates/skills/review` the /review skill for Claude Code
- `backup.sh` rclone sync of pdfs, books, notes, reviews to a remote named in config.yaml

Requirements: Python 3.11+, `pip install pyyaml docling`, poppler-utils (pdftotext), rclone for backup. No GPU needed; conversion is a few minutes per paper on CPU.
