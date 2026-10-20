#!/usr/bin/env bash
# Post-deploy smoke test for the Render public demo.
#
# Usage: API_URL=https://careerpilot-api.onrender.com \
#        WEB_URL=https://careerpilot-web.onrender.com \
#        EXPECTED_COMMIT=<full 40-character SHA> bash ops/smoke-test-render.sh
#
# Release gate first: the API (/version, directly and through the web
# rewrite) and the static site (/version.json) must all report
# EXPECTED_COMMIT. Until they do, nothing else is checked; if they never do
# (deploy failed, still building, or the commit is unknown), the script
# fails. It can therefore never pass on a previous release.
#
# Read-only against the demo. It stops before any write probe unless the
# API reports public_demo read-only mode, and each write probe is a request
# that would change nothing even on a writable API; each must get 403.
# It sends one resume match through the web rewrite, plus
# a short burst to confirm rate limiting, so run it sparingly: it uses up
# part of the per-minute budget.
#
# Exit code 0 only if every check passes.

set -euo pipefail

: "${API_URL:?Set API_URL to the API's public https URL}"
: "${WEB_URL:?Set WEB_URL to the static site's public https URL}"
: "${EXPECTED_COMMIT:?Set EXPECTED_COMMIT to the full commit SHA being released}"
if ! [[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "FAIL: EXPECTED_COMMIT must be a full 40-character lowercase commit SHA"
  exit 1
fi
API_URL="${API_URL%/}"
WEB_URL="${WEB_URL%/}"

for url in "$API_URL" "$WEB_URL"; do
  case "$url" in
    https://*) ;;
    *) echo "FAIL: $url is not an https URL"; exit 1 ;;
  esac
done

failures=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; failures=$((failures + 1)); }

# status METHOD URL [BODY] -> prints the HTTP status code only.
status() {
  local args=(--silent --output /dev/null --write-out '%{http_code}' --max-time 30
              --request "$1")
  if [ "$#" -ge 3 ]; then
    args+=(--header 'Content-Type: application/json' --data "$3")
  fi
  # On a connection error curl already prints 000; never abort under set -e.
  curl "${args[@]}" "$2" || true
}

# Free Render services sleep when idle; allow up to ~10 minutes to wake.
echo "Waiting for $API_URL/health ..."
for attempt in $(seq 1 60); do
  if [ "$(status GET "$API_URL/health")" = "200" ]; then
    break
  fi
  if [ "$attempt" = "60" ]; then
    fail "API /health never returned 200"
    exit 1
  fi
  sleep 10
done
pass "API /health returns 200"

# --- Release gate: every surface must serve EXPECTED_COMMIT ----------------
# Exact JSON comparison, so a null, missing, or different commit never
# matches. Cache-busting query and no-cache header for the static file.
expected_json="{\"commit\":\"$EXPECTED_COMMIT\"}"
fetch() {
  curl --silent --max-time 30 --header 'Cache-Control: no-cache' "$1" || true
}
echo "Waiting for commit $EXPECTED_COMMIT to be live ..."
confirmed=false
for attempt in $(seq 1 80); do
  api_version=$(fetch "$API_URL/version")
  rewrite_version=$(fetch "$WEB_URL/api/version")
  web_version=$(fetch "$WEB_URL/version.json?t=$(date +%s)" | tr -d '\r\n')
  if [ "$api_version" = "$expected_json" ] \
     && [ "$rewrite_version" = "$expected_json" ] \
     && [ "$web_version" = "$expected_json" ]; then
    confirmed=true
    break
  fi
  sleep 15
done
if ! $confirmed; then
  fail "deployed commit could not be confirmed (API: ${api_version:-none}; via web rewrite: ${rewrite_version:-none}; web: ${web_version:-none})"
  echo "Aborting: refusing to check a release that is not $EXPECTED_COMMIT."
  exit 1
fi
pass "API, web rewrite, and static site all serve commit $EXPECTED_COMMIT"

config=$(curl --silent --max-time 30 "$API_URL/config" || true)
if [ "$config" = '{"mode":"public_demo","read_only":true}' ]; then
  pass "API reports public_demo read-only mode"
else
  # Stop before any write probe: an instance that is not confirmed
  # read-only must never receive one.
  fail "API /config is not public_demo read-only: $config"
  echo "Aborting before the write probes."
  exit 1
fi

# Write probes are built so that even a wrongly writable API changes
# nothing: an empty body fails validation (422) and id 0 is rejected
# before any lookup. The read-only layer must answer 403 before either.
probe='{}'
[ "$(status POST "$API_URL/applications" "$probe")" = "403" ] \
  && pass "POST /applications is refused (403)" \
  || fail "POST /applications was not refused with 403"
[ "$(status PATCH "$API_URL/applications/0" "$probe")" = "403" ] \
  && pass "PATCH /applications/0 is refused (403)" \
  || fail "PATCH /applications/0 was not refused with 403"
[ "$(status DELETE "$API_URL/applications/0")" = "403" ] \
  && pass "DELETE /applications/0 is refused (403)" \
  || fail "DELETE /applications/0 was not refused with 403"

[ "$(status GET "$API_URL/dashboard")" = "200" ] \
  && pass "API /dashboard returns 200 (the reader role can SELECT)" \
  || fail "API /dashboard did not return 200"

[ "$(status GET "$WEB_URL/")" = "200" ] \
  && pass "Web root returns 200" \
  || fail "Web root did not return 200"
[ "$(status GET "$WEB_URL/api/config")" = "200" ] \
  && pass "Web /api rewrite reaches the API (GET)" \
  || fail "Web /api rewrite failed for GET"

match='{"resume_text":"python docker","job_description":"python docker aws"}'
[ "$(status POST "$WEB_URL/api/resume/match" "$match")" = "200" ] \
  && pass "Web /api rewrite forwards POST /resume/match" \
  || fail "Web /api rewrite failed for POST /resume/match"
[ "$(status POST "$WEB_URL/api/applications" "$probe")" = "403" ] \
  && pass "Writes through the web rewrite are refused (403)" \
  || fail "Write through the web rewrite was not refused with 403"

# ~300 KB body, streamed on stdin (too large for a command-line argument).
oversized=$(
  { printf '{"resume_text":"'; head -c 300000 /dev/zero | tr '\0' 'a'
    printf '","job_description":"x"}'; } |
  curl --silent --output /dev/null --write-out '%{http_code}' --max-time 60 \
    --request POST --header 'Content-Type: application/json' \
    --data-binary @- "$API_URL/resume/match" || true
)
[ "$oversized" = "413" ] \
  && pass "Oversized body is refused (413)" \
  || fail "Oversized body returned $oversized, expected 413"

# Rate limit: the resume-match budget is 10 per client per minute. A 429
# within 12 more requests shows the limiter is active (it may be shared by
# all clients behind Render's proxy; see the deployment guide).
limited=false
for _ in $(seq 1 12); do
  if [ "$(status POST "$API_URL/resume/match" "$match")" = "429" ]; then
    limited=true
    break
  fi
done
$limited && pass "Resume matching is rate limited (429)" \
  || fail "No 429 after 12 rapid resume-match requests"

echo
if [ "$failures" -eq 0 ]; then
  echo "All smoke checks passed."
else
  echo "$failures smoke check(s) failed."
  exit 1
fi
