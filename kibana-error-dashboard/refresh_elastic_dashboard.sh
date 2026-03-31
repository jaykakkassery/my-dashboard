#!/usr/bin/env bash
# refresh_elastic_dashboard.sh
# Usage:
#   ./refresh_elastic_dashboard.sh --hours 24
#   ./refresh_elastic_dashboard.sh --days 7
#
# Requires:  ES_USER and ES_PASSWORD env vars set
# Publishes: jaykakkassery.github.io/my-dashboard/kibana-error-dashboard/

set -euo pipefail

# ── Resolve directories ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # parent = my-dashboard repo root
cd "$SCRIPT_DIR"

# ── Parse args ────────────────────────────────────────────────────────────────
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 --hours <N>  OR  $0 --days <N>"
  exit 1
fi

ARG_FLAG="$1"
ARG_VAL="$2"

if [[ "$ARG_FLAG" != "--hours" && "$ARG_FLAG" != "--days" ]]; then
  echo "ERROR: First argument must be --hours or --days"
  exit 1
fi

# ── Validate env vars ─────────────────────────────────────────────────────────
if [ -z "${ES_USER:-}" ] || [ -z "${ES_PASSWORD:-}" ]; then
  echo "ERROR: ES_USER and ES_PASSWORD must be exported in your environment."
  exit 1
fi

DATA_FILE="elastic_data.json"
HTML_FILE="index.html"   # publish as index.html so GitHub Pages serves it

echo "╔══════════════════════════════════════════════╗"
echo "║    TST Hotel · Elastic Log Dashboard         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "▶ Period  : $ARG_FLAG $ARG_VAL"
echo "▶ User    : $ES_USER"
echo "▶ Publish : jaykakkassery.github.io/my-dashboard/kibana-error-dashboard/"
echo ""

# ── Step 1: Query Elasticsearch ───────────────────────────────────────────────
echo "[ 1/3 ] Querying Elasticsearch..."
python3 query_elastic_logs.py "$ARG_FLAG" "$ARG_VAL" --output "$DATA_FILE"

# ── Step 2: Generate Dashboard ────────────────────────────────────────────────
echo ""
echo "[ 2/3 ] Generating dashboard HTML..."
python3 generate_elastic_dashboard.py --input "$DATA_FILE" --output "$HTML_FILE"

# ── Step 3: Publish to GitHub Pages ───────────────────────────────────────────
echo ""
echo "[ 3/3 ] Publishing to GitHub Pages..."
cd "$REPO_DIR"
git add kibana-error-dashboard/index.html
git commit -m "chore: refresh elastic log dashboard ($ARG_FLAG $ARG_VAL) $(date '+%Y-%m-%d %H:%M EST')"
git push origin gh-pages

echo ""
echo "✅  Done!"
echo "   Local  : $SCRIPT_DIR/$HTML_FILE"
echo "   Public : https://jaykakkassery.github.io/my-dashboard/kibana-error-dashboard/"
echo ""

# ── Auto-open in browser ──────────────────────────────────────────────────────
if command -v open &>/dev/null; then
  open "$SCRIPT_DIR/$HTML_FILE"
elif command -v xdg-open &>/dev/null; then
  xdg-open "$SCRIPT_DIR/$HTML_FILE"
fi
