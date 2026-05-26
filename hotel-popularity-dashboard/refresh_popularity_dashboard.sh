#!/bin/bash

# Refresh hotel popularity dashboard with OpenAI research
# Research is OPTIONAL - only runs if you pass --research flag

set -e

cd "$(dirname "$0")"

# Default parameters
MIN_WEIGHTING=${MIN_WEIGHTING:-200}
MONTHS_INACTIVE=${MONTHS_INACTIVE:-2}
RESEARCH_TOP_N=${RESEARCH_TOP_N:-50}
RUN_RESEARCH=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --research)
            RUN_RESEARCH=1
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo "=========================================="
echo "Hotel Popularity Dashboard Refresh"
echo "=========================================="
echo "Min Weighting: $MIN_WEIGHTING"
echo "Months Inactive: $MONTHS_INACTIVE"
echo "Time: $(date)"
echo ""

# Check for required environment variables
if [ -z "$TST_DB_HOST" ] || [ -z "$TST_DB_USER" ] || [ -z "$TST_DB_PASSWORD" ]; then
    echo "Error: Missing required environment variables"
    echo "Required: TST_DB_HOST, TST_DB_USER, TST_DB_PASSWORD"
    exit 1
fi

# Query database
echo "Step 1: Querying database..."
python3 query_popularity.py \
    --min-weighting "$MIN_WEIGHTING" \
    --months-inactive "$MONTHS_INACTIVE" \
    --output data.json

# Research hotels (only if --research flag was passed)
if [ $RUN_RESEARCH -eq 1 ]; then
    if [ -z "$OPENAI_API_KEY" ]; then
        echo ""
        echo "ERROR: --research flag requires OPENAI_API_KEY"
        echo "Set OPENAI_API_KEY environment variable to enable research"
        exit 1
    fi
    
    echo ""
    echo "Step 2: Researching top $RESEARCH_TOP_N hotels with OpenAI..."
    echo "⚠️  This will consume OpenAI API tokens"
    python3 research_hotels_openai.py \
        --input data.json \
        --top-n "$RESEARCH_TOP_N"
else
    echo ""
    echo "Step 2: Skipping research (use --research flag to enable)"
fi

# Archive existing index.html
if [ -f "index.html" ]; then
    ARCHIVE_TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    ARCHIVE_FILE="index_${ARCHIVE_TIMESTAMP}.html"
    mv "index.html" "$ARCHIVE_FILE"
    echo "Archived existing dashboard → $ARCHIVE_FILE"
fi

# Generate dashboard
echo ""
echo "Step 3: Generating dashboard..."
python3 generate_popularity_dashboard.py \
    --input data.json \
    --output index.html

echo ""
echo "Dashboard updated successfully!"
echo ""

# Git operations
echo "Step 4: Publishing to GitHub..."
if [ -d ../.git ]; then
    cd ..
    git add hotel-popularity-dashboard/index.html hotel-popularity-dashboard/index_*.html hotel-popularity-dashboard/data.json
    git commit -m "Update hotel popularity dashboard - $(date '+%Y-%m-%d %H:%M:%S')" || echo "No changes to commit"
    git push origin gh-pages || echo "Push failed"
    echo "Pushed to GitHub"
fi

echo ""
echo "=========================================="
echo "Complete!"
echo "=========================================="
echo ""
echo "📊 Dashboard published at:"
echo "https://jaykakkassery.github.io/my-dashboard/hotel-popularity-dashboard/"
echo ""

if [ $RUN_RESEARCH -eq 0 ]; then
    echo "💡 Tip: Run with --research flag to add hotel status research"
    echo "   Example: ./refresh_popularity_dashboard.sh --research"
fi
