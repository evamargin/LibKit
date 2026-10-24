#!/usr/bin/env bash
# Start the helper and open the page. Safe to run twice: reuses a running helper.
cd "$(dirname "$0")/.." || exit 1
PORT=$(python3 -c "import sys; sys.path.insert(0,'code'); import libkit; print(libkit.config().get('port',8765))")
if ! curl -s "http://localhost:$PORT/api/tags" >/dev/null 2>&1; then
  nohup python3 code/helper.py >> .helper.log 2>&1 &
  for i in 1 2 3 4 5 6 7 8 9 10; do sleep 0.3; curl -s "http://localhost:$PORT/api/tags" >/dev/null 2>&1 && break; done
fi
echo "lib at http://localhost:$PORT"
command -v xdg-open >/dev/null && xdg-open "http://localhost:$PORT" >/dev/null 2>&1 &
