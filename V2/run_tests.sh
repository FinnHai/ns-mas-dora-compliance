#!/bin/bash
# pytest Test-Suite ausführen
#
# Nutzung:
#   ./run_tests.sh          # Alle Tests (inkl. Neo4j-Integration)
#   ./run_tests.sh --unit   # Nur Unit/Model/Sanity (ohne Neo4j)
#
cd "$(dirname "$0")"

if [[ ! -d backend/.venv ]]; then
  echo "Fehler: Backend-Virtualenv fehlt."
  echo "Führe aus: cd backend && python -m venv .venv && pip install -e '.[dev]'"
  exit 1
fi

case "${1:-}" in
  --unit)
    cd backend && MOCK_NEO4J=1 .venv/bin/python -m pytest tests/ -v -m "not integration and not slow"
    ;;
  *)
    cd backend && .venv/bin/python -m pytest tests/ -v "$@"
    ;;
esac
