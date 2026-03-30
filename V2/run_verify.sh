#!/bin/bash
# Verifikationsskript ausführen (Backend-Venv + Neo4j erforderlich)
cd "$(dirname "$0")/backend"
.venv/bin/python -m scripts.verify_system
