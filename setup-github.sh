#!/bin/bash
# Skript zum Hochladen des BA-Projekts auf GitHub

set -e
cd "$(dirname "$0")"

echo "=== BA-Projekt auf GitHub vorbereiten ==="

# Falls .git beschädigt ist, neu initialisieren
if [ ! -f .git/HEAD ] || [ ! -s .git/HEAD ]; then
    echo "Git-Repository wird neu initialisiert..."
    rm -rf .git
    git init
fi

# V1 hatte ein eigenes Git-Repo - entfernen falls noch vorhanden
if [ -d V1/.git ]; then
    echo "V1/.git wird entfernt (wird Teil des Haupt-Repos)..."
    rm -rf V1/.git
fi

# Lock-Datei entfernen falls vorhanden
rm -f .git/index.lock

# Dateien in Batches hinzufügen (vermeidet Timeouts bei großen Projekten)
echo "Dateien werden zum Staging hinzugefügt..."
git add .gitignore setup-github.sh
git add V1/ V2/ 2>/dev/null || true
git add "Projekt Latex BA/" 2>/dev/null || true
git add Clean/ NACHLM/ Paper/ 2>/dev/null || true
git add "Artefakte Claude/" Bewerbung/ LOgs/ LiteraturStringErgebnisse/ 2>/dev/null || true
git add BIBTEX.bib forensic_trace.jsonl "Initial Infos.pdf" "Masterplan Bachelorarbeit Finn.docx" 2>/dev/null || true

# Status anzeigen
echo ""
echo "Gestagte Dateien:"
git status --short | head -30
echo "..."
git status --short | wc -l
echo "Dateien insgesamt"

# Ersten Commit erstellen
if ! git diff --cached --quiet 2>/dev/null || ! git rev-parse --verify HEAD >/dev/null 2>&1; then
    echo ""
    echo "Erster Commit wird erstellt..."
    git commit -m "Initial commit: Bachelorarbeit Projekt"
fi

echo ""
echo "=== Nächste Schritte ==="
echo "1. Gehe zu https://github.com/new"
echo "2. Erstelle ein neues Repository (z.B. 'BA' oder 'Bachelorarbeit')"
echo "3. Wähle 'Public' und erstelle KEIN README (Repo ist nicht leer)"
echo "4. Führe dann aus:"
echo ""
echo "   git remote add origin https://github.com/DEIN-USERNAME/REPO-NAME.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "Ersetze DEIN-USERNAME und REPO-NAME mit deinen Werten!"
