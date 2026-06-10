#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8765}"
OPEN_BROWSER="${OPEN_BROWSER:-1}"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

VENV_PYTHON=".venv/bin/python"
"$VENV_PYTHON" -m pip install -r requirements.txt

URL="http://127.0.0.1:${PORT}"
echo "Starting Running Dinner Web App at ${URL}"

if [ "${OPEN_BROWSER}" != "0" ]; then
  (
    sleep 2
    "$VENV_PYTHON" - <<PY
import webbrowser
webbrowser.open("${URL}")
PY
  ) &
fi

"$VENV_PYTHON" -m uvicorn web_app:app --host 127.0.0.1 --port "${PORT}"
