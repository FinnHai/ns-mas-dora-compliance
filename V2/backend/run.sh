#!/bin/bash
# Backend starten – OHNE Reload (verhindert "Operation canceled" / "app not found")
# Mit Reload: RELOAD=1 ./run.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo "[run.sh] Wechsle nach: $SCRIPT_DIR"
source .venv/bin/activate
echo "[run.sh] Venv aktiviert: $(which python)"
echo "[run.sh] Starte Uvicorn auf Port ${PORT:-8000}..."
echo "[run.sh] (Startup-Logs erscheinen unten – ns_mas kann 10–30 Sek dauern)"
echo ""

# Unbuffered: Logs sofort anzeigen
export PYTHONUNBUFFERED=1

if [ "${RELOAD:-0}" = "1" ]; then
  exec uvicorn app.main:app --reload --port "${PORT:-8000}" --reload-dir app --reload-exclude ".venv"
else
  exec uvicorn app.main:app --port "${PORT:-8000}"
fi
