# lib

A local, offline paper library. PDFs, their text, your tags and notes, one page to see it all, and a terminal for questions and reviews.

```
install    git clone <LibKit repo> ~/lib/code && ~/lib/code/init.sh      (once; this folder is already set up)
start      code/start.sh                 opens http://localhost:8765
add        copy PDFs into papers/pdf/, open inbox on the page, pick tags, convert
tag        click a title on the page, toggle tags (max 5); "+ tag" adds one to the vocabulary
review     filter → select → "make review folder" → fill reviews/<name>/brief.md → in terminal: /review <name>
ask        claude  (in this folder) and ask; CLAUDE.md tells it where things are
export     select papers → export .bib
backup     code/backup.sh                rclone to Google Drive: pdf, books, notes, reviews, tags, config
update     cd code && git pull
```

First time only
```
rclone config                 pick Google Drive, name the remote "gdrive"   (backup_remote in config.yaml)
pip install docling           PDF → markdown converter used by convert
```

Layout: `papers/pdf/<key>.pdf`, `papers/doc/<key>/text.md`, `papers/notes/<key>.md`, `books/<subject>/`, `reviews/<name>/`. Key = `author-year-twowords`. Settings in `config.yaml`, vocabulary in `tags.yaml`, agent rules in `CLAUDE.md`.
