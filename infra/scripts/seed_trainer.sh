#!/usr/bin/env bash
# Usage: ./seed_trainer.sh <username> <password> <email>
# Creates the first trainer account via the API.
# Only works if no trainer exists yet.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
USERNAME="${1:-trainer}"
PASSWORD="${2:-changeme}"
EMAIL="${3:-trainer@xperts26.local}"

echo "Creating trainer account: $USERNAME"
curl -sf -X POST "$API_URL/api/users/seed-trainer" \
  -G \
  --data-urlencode "username=$USERNAME" \
  --data-urlencode "password=$PASSWORD" \
  --data-urlencode "email=$EMAIL" | python3 -m json.tool

echo ""
echo "Done. Login at $API_URL with username='$USERNAME'"
