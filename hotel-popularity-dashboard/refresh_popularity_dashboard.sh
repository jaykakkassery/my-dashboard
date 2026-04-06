#!/bin/bash

# Refresh hotel popularity dashboard
# This script queries the database and regenerates the HTML dashboard

set -e

# Change to script directory
cd "$(dirname "$0")"

# Default parameters
MIN_WEIGHTING=${MIN_WEIGHTING:-50}
MONTHS_INACTIVE=${MONTHS_INACTIVE:-2}

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
echo "Querying database..."
python3 query_popularity.py \
    --min-weighting "$MIN_WEIGHTING" \
    --months-inactive "$MONTHS_INACTIVE" \
    --output data.json

# Generate dashboard
echo "Generating dashboard..."
python3 generate_popularity_dashboard.py \
    --input data.json \
    --output index.html

echo ""
echo "Dashboard updated successfully!"
echo "File: $(pwd)/index.html"
echo ""

# Git operations (if in a git repo)
if [ -d .git ]; then
    echo "Committing and pushing to GitHub..."
    git add index.html data.json
    git commit -m "Update hotel popularity dashboard - $(date '+%Y-%m-%d %H:%M:%S')" || true
    git push || true
    echo "Pushed to GitHub"
fi

echo "=========================================="
echo "Complete!"
echo "=========================================="
