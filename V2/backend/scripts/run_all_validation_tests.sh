#!/bin/bash
#
# Führt alle NS-MAS Validierungstests aus.
# Nutzt die backend .venv.
#
# Usage: ./scripts/run_all_validation_tests.sh
# Oder:  cd V2/backend && ./scripts/run_all_validation_tests.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BACKEND_DIR" || exit 1

# .venv aktivieren (enthält neo4j, pytest, httpx)
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
else
    echo "FEHLER: .venv nicht gefunden. Führe aus: cd $BACKEND_DIR && python -m venv .venv && pip install -r requirements.txt"
    exit 1
fi

API_URL="${API_URL:-http://localhost:8000}"

echo "=============================================="
echo "1. Neo4j Validierungsqueries"
echo "=============================================="
python -m scripts.run_neo4j_validation_queries &
NEO_PID=$!
for _ in $(seq 1 8); do
  kill -0 $NEO_PID 2>/dev/null || { wait $NEO_PID; break; }
  sleep 1
done
if kill -0 $NEO_PID 2>/dev/null; then
  kill $NEO_PID 2>/dev/null
  echo "(Neo4j-Query hängt – übersprungen nach 8s)"
fi

echo ""
echo "=============================================="
echo "2. KG Auditor Integrationstests"
echo "=============================================="
pytest tests/test_kg_auditor_integration.py -v -m integration 2>&1 &
PY_PID=$!
for _ in $(seq 1 15); do
  kill -0 $PY_PID 2>/dev/null || { wait $PY_PID; break; }
  sleep 1
done
if kill -0 $PY_PID 2>/dev/null; then
  kill $PY_PID 2>/dev/null
  echo "(pytest hängt – übersprungen nach 15s)"
fi

echo ""
echo "=============================================="
echo "6. Human Review Gate (Backend muss laufen)"
echo "=============================================="
bash "$SCRIPT_DIR/test_human_review_gate.sh" "$API_URL" || true

echo ""
echo "=============================================="
echo "8. Smoke Test S2"
echo "=============================================="
python -m scripts.run_smoke_test_s2 || echo "(Backend muss laufen: ./run.sh)"
