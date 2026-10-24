#!/usr/bin/env bash
# Sync the parts of the library that git does not hold (pdfs, books, converted text) plus notes to the rclone remote
# named in config.yaml (backup_remote, e.g. gdrive:lib). One-way: local -> remote. Deleted local files are removed remotely.
cd "$(dirname "$0")/.." || exit 1
REMOTE=$(python3 -c "import sys; sys.path.insert(0,'code'); import libkit; print(libkit.config().get('backup_remote','gdrive:lib'))")
command -v rclone >/dev/null || { echo "rclone not found. Install: https://rclone.org/install/  then: rclone config"; exit 1; }
for d in papers/pdf books papers/notes reviews; do
  [ -d "$d" ] && rclone sync "$d" "$REMOTE/$d" --progress --exclude ".*" || true
done
rclone copy tags.yaml config.yaml index.json "$REMOTE/" 2>/dev/null
[ "$1" = "--with-text" ] && rclone sync papers/doc "$REMOTE/papers/doc" --progress
echo "backup done -> $REMOTE  (add --with-text to include papers/doc, which can be regenerated)"
