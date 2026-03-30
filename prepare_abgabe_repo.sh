#!/usr/bin/env bash
# Erzeugt einen Ordner mit V2 (+ README, .gitignore) für ein schlankes Git-Repository.
# Aufruf aus dem Repository-Root: ./prepare_abgabe_repo.sh /pfad/zum/Zielordner
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-}"

if [[ -z "$DEST" ]]; then
  echo "Usage: $0 /pfad/zum/Zielordner" >&2
  exit 1
fi

mkdir -p "$DEST"

RSYNC=(rsync -a --delete --ignore-errors
  --exclude __pycache__
  --exclude '*.pyc'
  --exclude .venv
  --exclude venv
  --exclude node_modules
  --exclude .env
  --exclude .env.local
  --exclude dist
  --exclude .pytest_cache
  --exclude .DS_Store
  --exclude .git
  --exclude 'entwicklung_archiv/'
)

"${RSYNC[@]}" "$ROOT/V2/" "$DEST/V2/"
# Entwicklungsarchiv nicht abgeben (rsync --exclude entfernt es im Ziel nicht zuverlässig)
rm -rf "$DEST/V2/backend/evaluation/entwicklung_archiv"

for f in README.md .gitignore prepare_abgabe_repo.sh; do
  if [[ -f "$ROOT/$f" ]]; then
    cp "$ROOT/$f" "$DEST/$f"
  fi
done

chmod +x "$DEST/prepare_abgabe_repo.sh"

echo "Fertig: $DEST"
