#!/usr/bin/env bash
# Jina Reader engine/cache fidelity matrix — reproducible harness.
#
# The API key is NEVER stored in this script, its output, or any artifact.
# Provide it via the environment:
#     export JINA_KEY="jina_..."            # or, on macOS with the key in the login keychain:
#     export JINA_KEY="$(security find-generic-password -s 'Jina Reader API key' -w)"
# then:  bash tests/run_engine_matrix.sh
#
# Ground truth: quotes.toscrape.com page 1 renders 10 quotes from 8 distinct
# authors. The /js variant injects them via JavaScript at runtime; the root
# variant is server-rendered. Recall = distinct authors recovered / 8.
set -u
JD="$(cd "$(dirname "$0")/.." && pwd)/artifacts/raw"
mkdir -p "$JD"
: "${JINA_KEY:?set JINA_KEY in the environment (never commit it)}"
AUTH="Authorization: Bearer $JINA_KEY"
AUTHORS=(Einstein Rowling Austen Monroe Gide Edison Roosevelt Martin)

recall () { local f="$1" n=0 a; for a in "${AUTHORS[@]}"; do grep -qi "$a" "$f" && n=$((n+1)); done; echo "$n"; }

# fetch <label> <target-url> [extra curl -H args...]
fetch () {
  local label="$1" url="$2"; shift 2
  local m; m=$(curl -s --max-time 120 -o "$JD/$label.md" \
    -w "%{http_code}|%{time_total}|%{size_download}" \
    -H "$AUTH" -H "Accept: text/markdown" "$@" "$url")
  local cached; cached=$(grep -qi "cached snapshot" "$JD/$label.md" && echo true || echo false)
  local notloaded; notloaded=$(grep -qi "not.*fully loaded" "$JD/$label.md" && echo true || echo false)
  printf '{"label":"%s","http":%s,"time_s":%s,"bytes":%s,"recall_of_8":%s,"cached_snapshot":%s,"not_fully_loaded":%s}\n' \
    "$label" "${m%%|*}" "$(echo "$m"|cut -d'|' -f2)" "${m##*|}" "$(recall "$JD/$label.md")" "$cached" "$notloaded"
}

JS="https://r.jina.ai/https://quotes.toscrape.com/js"
ST="https://r.jina.ai/https://quotes.toscrape.com/"
{
  echo '['
  # JS page, cache bypassed — engine choice takes effect
  fetch nc_js_default      "$JS" -H "X-No-Cache: true"
  fetch nc_js_direct       "$JS" -H "X-No-Cache: true" -H "X-Engine: direct"
  fetch nc_js_browser      "$JS" -H "X-No-Cache: true" -H "X-Engine: browser"
  fetch nc_js_browser_wait "$JS" -H "X-No-Cache: true" -H "X-Engine: browser" -H "X-Wait-For-Selector: .quote"
  # Static baseline + direct-on-static (isolates: direct = plain HTTP fetch)
  fetch nc_static_default  "$ST" -H "X-No-Cache: true"
  fetch nc_static_direct   "$ST" -H "X-No-Cache: true" -H "X-Engine: direct"
  # Warm-cache cell: same JS page WITHOUT the X-No-Cache opt-out. Shipped result is a
  # warm, FULL snapshot (8/8, 1193 B); a cold stale quote-less 0/8 snapshot was observed
  # once but could NOT be reproduced after warming, so this pack makes no cache-trap claim.
  fetch cached_js          "$JS"
  echo ']'
} | tee "$JD/engine-matrix.ndjson"
