#!/usr/bin/env python3
"""Kurzer Test: Ist die OpenAI API erreichbar?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings

key = getattr(settings, "openai_api_key", "") or ""
if not key:
    print("OPENAI_API_KEY: nicht gesetzt in .env")
    sys.exit(1)

print("OPENAI_API_KEY: gesetzt (Länge:", len(key), ")")
try:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini", api_key=key, temperature=0)
    r = llm.invoke("Say only: OK")
    print("OpenAI API: OK -", r.content[:80])
    sys.exit(0)
except Exception as e:
    print("OpenAI API Fehler:", e)
    sys.exit(1)
