"""Rebuild index.json from papers/notes.   python3 code/build_index.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libkit as L
idx = L.build_index()
print(f"{len(idx['papers'])} papers, {len(idx['unprocessed'])} unprocessed pdfs, {len(idx['missing_text'])} without text")
