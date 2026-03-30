#!/bin/bash
#
# Validierungsplan Punkt 6: Human Review Gate – prüft ob die Pipeline
# nach dem Auditor stoppt und auf /resume wartet.
#
# Erwartung: Response enthält "status": "awaiting_approval", NICHT "completed".
#
# Usage: ./scripts/test_human_review_gate.sh [API_URL]
# Default API_URL: http://localhost:8000

API_URL="${1:-http://localhost:8000}"

echo "=============================================="
echo "Human Review Gate Test"
echo "API: $API_URL"
echo "=============================================="

RESPONSE=$(curl -s -X POST "$API_URL/ns-mas/run" \
  -H "Content-Type: application/json" \
  -d '{"target_organization":"Test AG","threat_profile":"APT29","scope_document":"Test scope"}')

echo ""
echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

if echo "$RESPONSE" | grep -q '"status": "awaiting_approval"'; then
  echo "✓ ERFOLG: Pipeline pausiert bei Human Review (status=awaiting_approval)"
  exit 0
elif echo "$RESPONSE" | grep -q '"status": "completed"'; then
  echo "✗ FEHLER: Pipeline lieferte sofort completed – Human Review Gate fehlt oder wurde übersprungen"
  exit 1
else
  echo "? Unklarer Status. Prüfe Response manuell."
  exit 2
fi
