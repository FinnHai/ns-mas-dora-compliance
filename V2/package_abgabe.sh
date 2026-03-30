#!/usr/bin/env bash
# Optional: kompaktes ZIP aus Backend + kanonischen Eval-JSONs (aus dem V2-Verzeichnis ausführen).
# Vollständiges Repository vs. ZIP-Inhalt: siehe ABGABE.md im selben Verzeichnis.
#
#   ./package_abgabe.sh  →  DORA-Szenario-Plattform-V2-abgabe.zip
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
STAGE="$(mktemp -d)"
cleanup() { rm -rf "${STAGE}"; }
trap cleanup EXIT

ARCHIVE_NAME="DORA-Szenario-Plattform-V2-abgabe"
OUT_ZIP="${ROOT}/${ARCHIVE_NAME}.zip"
PKG="${STAGE}/${ARCHIVE_NAME}"

mkdir -p "${PKG}/backend"

RSYNC_EX="--exclude __pycache__ --exclude '*.pyc'"
rsync -a ${RSYNC_EX} "${ROOT}/backend/app/" "${PKG}/backend/app/"

mkdir -p "${PKG}/backend/scripts"
cp "${ROOT}/backend/scripts/__init__.py" "${PKG}/backend/scripts/"
cp "${ROOT}/backend/scripts/seed_mitre.py" "${PKG}/backend/scripts/"

for f in requirements.txt pyproject.toml run.sh run2.sh VALIDIERUNGSTESTS_ERGEBNISSE.md; do
  cp "${ROOT}/backend/${f}" "${PKG}/backend/"
done
cp "${ROOT}/backend/.env.example" "${PKG}/backend/.env.example"

mkdir -p "${PKG}/backend/evaluation/n10" "${PKG}/backend/evaluation/comparison"
cp "${ROOT}/backend/evaluation/README.md" "${PKG}/backend/evaluation/README.md"
cp "${ROOT}/backend/evaluation/n10/eval_n10_results.json" "${PKG}/backend/evaluation/n10/"
cp "${ROOT}/backend/evaluation/n10/eval_n10_results_backup_20260323_1027.json" "${PKG}/backend/evaluation/n10/"
cp "${ROOT}/backend/evaluation/comparison/eval_comparison.json" "${PKG}/backend/evaluation/comparison/"

rsync -a "${ROOT}/config/" "${PKG}/config/"

cp "${ROOT}/README.md" "${PKG}/"
cp "${ROOT}/ABGABE.md" "${PKG}/"
cp "${ROOT}/ERGEBNISSE.md" "${PKG}/"
cp "${ROOT}/.gitignore" "${PKG}/"
chmod +x "${PKG}/backend/run.sh" "${PKG}/backend/run2.sh"

rm -f "${OUT_ZIP}"
( cd "${STAGE}" && zip -rq "${OUT_ZIP}" "${ARCHIVE_NAME}" )

SIZE="$(du -h "${OUT_ZIP}" | cut -f1)"
echo "Optional ZIP: ${OUT_ZIP} (${SIZE})"
echo "Hinweis: Frontend, docs/, tests/ und Eval-Repro-Skripte nur im vollständigen Repository (siehe ABGABE.md)."
