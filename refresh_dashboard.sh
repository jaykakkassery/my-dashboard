#!/bin/bash
# refresh_dashboard.sh
#
# Usage:
#   ./refresh_dashboard.sh                                    → last 24 hrs, all licensees, all adapters
#   ./refresh_dashboard.sh 3 days                             → last 3 days, all licensees, all adapters
#   ./refresh_dashboard.sh 12 hrs                             → last 12 hours, all licensees, all adapters
#   ./refresh_dashboard.sh 3 days --licensee-id 1001          → last 3 days, licensee 1001 only
#   ./refresh_dashboard.sh 12 hrs --adapter-name Expedia      → last 12 hrs, Expedia only
#   ./refresh_dashboard.sh 1 days --licensee-id 1001 --adapter-name Sabre

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANALYTICS_JSON="/tmp/booking_analytics.json"
DASHBOARD_REPO="${DASHBOARD_REPO:-$HOME/my-dashboard}"
DASHBOARD_OUT="$DASHBOARD_REPO/index.html"

# ── Parse time range (positional args 1 & 2) ──────────────────
AMOUNT=${1:-24}
UNIT=${2:-hrs}
PYTHON_ARGS=""
LABEL=""

case "$UNIT" in
  hrs|hr|hours|hour)
    PYTHON_ARGS="--hours $AMOUNT"
    LABEL="Last $AMOUNT hour(s)"
    ;;
  days|day)
    PYTHON_ARGS="--days $AMOUNT"
    LABEL="Last $AMOUNT day(s)"
    ;;
  *)
    echo "ERROR: Unknown unit '$UNIT'. Use 'hrs' or 'days'."
    echo ""
    echo "Usage examples:"
    echo "  ./refresh_dashboard.sh"
    echo "  ./refresh_dashboard.sh 3 days"
    echo "  ./refresh_dashboard.sh 12 hrs --licensee-id 1001"
    echo "  ./refresh_dashboard.sh 1 days --adapter-name Expedia"
    echo "  ./refresh_dashboard.sh 3 days --licensee-id 1001 --adapter-name Sabre"
    exit 1
    ;;
esac

# ── Parse optional named args (--licensee-id, --adapter-name) ─
LICENSEE_ID=""
ADAPTER_NAME=""
shift 2 2>/dev/null || true  # remove first two positional args

while [[ $# -gt 0 ]]; do
  case "$1" in
    --licensee-id)
      LICENSEE_ID="$2"
      PYTHON_ARGS="$PYTHON_ARGS --licensee-id $2"
      shift 2
      ;;
    --adapter-name)
      ADAPTER_NAME="$2"
      PYTHON_ARGS="$PYTHON_ARGS --adapter-name $2"
      shift 2
      ;;
    *)
      echo "ERROR: Unknown argument '$1'"
      exit 1
      ;;
  esac
done

# ── Build filter label ─────────────────────────────────────────
FILTER_LABEL=""
[ -n "$LICENSEE_ID"  ] && FILTER_LABEL="$FILTER_LABEL · Licensee: $LICENSEE_ID"
[ -n "$ADAPTER_NAME" ] && FILTER_LABEL="$FILTER_LABEL · Adapter: $ADAPTER_NAME"
[ -z "$FILTER_LABEL" ] && FILTER_LABEL=" · All licensees & adapters"

echo "============================================"
echo " TST Booking Dashboard - Refreshing..."
echo " Range  : $LABEL"
echo " Filters:$FILTER_LABEL"
echo "============================================"

# ── Check env vars ─────────────────────────────────────────────
if [ -z "$TST_DB_HOST" ] || [ -z "$TST_DB_USER" ] || [ -z "$TST_DB_NAME" ]; then
  echo ""
  echo "ERROR: Missing environment variables. Please set:"
  echo "  export TST_DB_HOST=localhost"
  echo "  export TST_DB_PORT=3306"
  echo "  export TST_DB_USER=root"
  echo "  export TST_DB_PASSWORD="
  echo "  export TST_DB_NAME=book"
  echo "  export DASHBOARD_REPO=~/myExperements/my-dashboard"
  echo ""
  exit 1
fi

# ── Check dashboard repo ───────────────────────────────────────
if [ ! -d "$DASHBOARD_REPO" ]; then
  echo "ERROR: Dashboard repo not found at $DASHBOARD_REPO"
  echo "Set: export DASHBOARD_REPO=~/myExperements/my-dashboard"
  exit 1
fi

# ── Step 1: Query ──────────────────────────────────────────────
echo "[1/4] Querying database ($LABEL$FILTER_LABEL)..."
python3 "$SCRIPT_DIR/query_analytics.py" $PYTHON_ARGS --output "$ANALYTICS_JSON"

# ── Archive existing index.html ────────────────────────────────
if [ -f "$DASHBOARD_OUT" ]; then
  ARCHIVE_TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
  ARCHIVE_OUT="${DASHBOARD_REPO}/index_${ARCHIVE_TIMESTAMP}.html"
  mv "$DASHBOARD_OUT" "$ARCHIVE_OUT"
  echo "Archived existing dashboard → index_${ARCHIVE_TIMESTAMP}.html"
fi

# ── Step 2: Generate dashboard ─────────────────────────────────
echo "[2/4] Generating dashboard..."
python3 "$SCRIPT_DIR/generate_dashboard.py" \
  --input "$ANALYTICS_JSON" \
  --output "$DASHBOARD_OUT"

# ── Step 3: Push to GitHub ─────────────────────────────────────
echo "[3/4] Pushing to GitHub Pages..."
cd "$DASHBOARD_REPO"
git add index.html index_*.html
git commit -m "Dashboard refresh ($LABEL$FILTER_LABEL) - $(date '+%Y-%m-%d %H:%M:%S')"
git push origin gh-pages

# ── Step 4: Done ───────────────────────────────────────────────
echo "[4/4] Done!"
echo ""
echo "============================================"
echo " Dashboard live at:"
echo " https://$(git remote get-url origin | sed 's/.*github.com[:/]\([^/]*\)\/.*/\1/').github.io/my-dashboard"
echo " Range  : $LABEL"
echo " Filters:$FILTER_LABEL"
echo " Updated: $(date)"
echo "============================================"
