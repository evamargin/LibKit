#!/usr/bin/env bash
# Set up a new library around this code folder:  git clone <LibKit> ~/lib/code && ~/lib/code/init.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p papers/pdf papers/doc papers/notes books reviews import
[ -f config.yaml ] || cp code/templates/config.yaml config.yaml
[ -f tags.yaml ]   || cp code/templates/tags.yaml tags.yaml
[ -f CLAUDE.md ]   || cp code/templates/CLAUDE.md CLAUDE.md
[ -f README.md ]   || cp code/templates/README.md README.md
[ -f .gitignore ]  || cp code/templates/gitignore .gitignore
mkdir -p .claude/skills && [ -d .claude/skills/review ] || cp -r code/templates/skills/review .claude/skills/review
python3 -c "import yaml" 2>/dev/null || pip install --user pyyaml
command -v docling >/dev/null || echo "docling not found: pip install docling   (needed for convert)"
command -v pdftotext >/dev/null || echo "pdftotext not found: install poppler-utils (used to read DOIs from new PDFs)"
python3 code/build_index.py
echo "ready. start with: code/start.sh"
