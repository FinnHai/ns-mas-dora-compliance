#!/bin/bash
# Backend starten – nur app/ überwachen (verhindert Reload-Sturm durch .venv)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
source .venv/bin/activate
# Port: 8000 Standard, bei "Address already in use": PORT=8002 ./run.sh
exec uvicorn app.main:app --reload --port "${PORT:-8000}" \
  --reload-dir app \
  --reload-exclude ".venv"
