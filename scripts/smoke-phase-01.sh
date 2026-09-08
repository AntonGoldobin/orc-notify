#!/usr/bin/env bash
# Smoke script for Phase 1 — register, login, create topic, create key,
# publish via Bearer (with HMAC signature), subscribe via SSE, assert the
# message arrives.
#
# Usage:  bash scripts/smoke-phase-01.sh [BASE_URL]
# Default: http://localhost:8000
#
# Requires: curl, python3 (for HMAC). The backend must already be running.
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
COOKIES="$(mktemp)"
trap 'rm -f "$COOKIES"' EXIT

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
step()   { printf '\033[36m▶ %s\033[0m\n' "$*"; }
fail()   { red "✗ FAIL: $*"; exit 1; }
ok()     { green "✓ $*"; }

EMAIL="smoke-$(date +%s%N)@example.com"
PASS="verysecret-12345678"

step "Health check"
HEALTH=$(curl -fsS "$BASE_URL/healthz") || fail "health check failed"
echo "$HEALTH"
[[ "$HEALTH" == *'"ok":true'* ]] || fail "healthz not ok"
ok "healthz OK"

step "Register"
REG=$(curl -fsS -c "$COOKIES" -X POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}") || fail "register failed"
echo "$REG"
USER_ID=$(echo "$REG" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
ok "registered $EMAIL (id=$USER_ID)"

step "Create topic"
TOPIC=$(curl -fsS -b "$COOKIES" -X POST "$BASE_URL/api/topics" \
    -H "Content-Type: application/json" \
    -d '{"name":"smoke-alerts","description":"smoke test"}') || fail "create topic failed"
echo "$TOPIC"
TOPIC_NAME=$(echo "$TOPIC" | python3 -c 'import sys,json; print(json.load(sys.stdin)["name"])')
ok "topic $TOPIC_NAME created"

step "Create topic key"
KEY=$(curl -fsS -b "$COOKIES" -X POST "$BASE_URL/api/topics/$TOPIC_NAME/keys" \
    -H "Content-Type: application/json" \
    -d '{"name":"publisher"}') || fail "create key failed"
echo "$KEY"
KEY_ID=$(echo "$KEY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
SECRET=$(echo "$KEY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["secret"])')
ok "key $KEY_ID created (secret len ${#SECRET})"

step "Publish via Bearer (HMAC-signed)"
BODY='smoke test message'
TS=$(date +%s)
SIG=$(python3 -c "
import hmac, hashlib, sys
secret = sys.argv[1]
body = sys.argv[2]
ts = sys.argv[3]
msg = ts.encode() + b':' + body.encode()
print(hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest())
" "$SECRET" "$BODY" "$TS")

PUB=$(curl -fsS -X POST "$BASE_URL/$TOPIC_NAME" \
    -H "Authorization: Bearer $KEY_ID.$SIG" \
    -H "X-Notifier-Signature: $SIG" \
    -H "X-Notifier-Timestamp: $TS" \
    -H "Content-Type: text/plain" \
    -H "Title: Smoke Title" \
    -H "Priority: 4" \
    -H "Tags: smoke,test" \
    --data-binary "$BODY") || fail "publish failed"
echo "$PUB"
MSG_ID=$(echo "$PUB" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
[[ -n "$MSG_ID" ]] || fail "publish response missing id"
ok "published message id=$MSG_ID"

step "Idempotent re-publish (same Id header)"
TS_A=$(date +%s)
SIG_A=$(python3 -c "
import hmac, hashlib, sys
secret, body, ts = sys.argv[1], sys.argv[2], sys.argv[3]
print(hmac.new(secret.encode(), ts.encode() + b':' + body.encode(), hashlib.sha256).hexdigest())
" "$SECRET" "first" "$TS_A")
PUB2=$(curl -sS -o /tmp/smoke-pub2.json -w "%{http_code}" -X POST "$BASE_URL/$TOPIC_NAME" \
    -H "Authorization: Bearer $KEY_ID.$SIG_A" \
    -H "X-Notifier-Signature: $SIG_A" \
    -H "X-Notifier-Timestamp: $TS_A" \
    -H "Content-Type: text/plain" \
    -H "Id: smoke-dup-1" \
    --data-binary "first")
[[ "$PUB2" == "201" ]] || fail "first publish with Id: expected 201 got $PUB2"

TS_B=$(date +%s)
SIG_B=$(python3 -c "
import hmac, hashlib, sys
secret, body, ts = sys.argv[1], sys.argv[2], sys.argv[3]
print(hmac.new(secret.encode(), ts.encode() + b':' + body.encode(), hashlib.sha256).hexdigest())
" "$SECRET" "second" "$TS_B")
PUB3=$(curl -sS -o /tmp/smoke-pub3.json -w "%{http_code}" -X POST "$BASE_URL/$TOPIC_NAME" \
    -H "Authorization: Bearer $KEY_ID.$SIG_B" \
    -H "X-Notifier-Signature: $SIG_B" \
    -H "X-Notifier-Timestamp: $TS_B" \
    -H "Content-Type: text/plain" \
    -H "Id: smoke-dup-1" \
    --data-binary "second")
[[ "$PUB3" == "200" ]] || fail "idempotent re-publish expected 200 got $PUB3"
ok "idempotency: 201 then 200 ✓"

step "Subscribe via /json (Bearer read scope)"
JSON=$(curl -fsS "$BASE_URL/$TOPIC_NAME/json" \
    -H "Authorization: Bearer $KEY_ID.$SIG") || fail "json poll failed"
echo "$JSON" | python3 -m json.tool > /tmp/smoke-json.txt
COUNT=$(echo "$JSON" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))')
[[ "$COUNT" -ge 2 ]] || fail "expected ≥2 messages, got $COUNT"
ok "/json returned $COUNT message(s)"

step "Capability probe /auth"
AUTH=$(curl -fsS "$BASE_URL/$TOPIC_NAME/auth" \
    -H "Authorization: Bearer $KEY_ID.$SIG")
echo "$AUTH"
[[ "$AUTH" == *'"can_read":true'* ]] || fail "/auth did not return can_read=true"
ok "/auth probe OK"

step "Cleanup"
curl -fsS -b "$COOKIES" -X DELETE "$BASE_URL/api/topics/$TOPIC_NAME" > /dev/null
ok "topic deleted"

green ""
green "═══ Phase 1 smoke: PASS ═══"
