---
name: booking-analytics
description: >
  Connects to the TST MySQL database using environment variables (no credentials
  in chat), queries TRAVEL_BOOKING for hotel booking success/failure stats in
  the last 24 hours, and generates a beautiful HTML dashboard with charts.
  Use this skill whenever the user says things like "show booking analytics",
  "booking dashboard", "how many bookings failed", "show me booking stats",
  "success vs failure report", "booking health dashboard", or any variation
  of wanting to see booking performance data. Always use this skill proactively
  when the user asks about booking success rates, failure rates, or adapter performance.
compatibility:
  tools: []
  dependencies:
    - python3
    - pip packages: mysql-connector-python
---

# Booking Analytics Skill...

Queries TST MySQL TRAVEL_BOOKING table for hotel booking success/failure
in the last 24 hours and generates an HTML dashboard with charts.
Credentials are read from environment variables — never passed in chat.

## Required environment variables

The user must have these set on their machine before running:

```bash
export TST_DB_HOST=localhost
export TST_DB_PORT=3306
export TST_DB_USER=root
export TST_DB_PASSWORD=
export TST_DB_NAME=book
```

Or in a `.env` file loaded before running.

If env vars are missing, the script will print a clear error message.

## Step-by-step

### Step 1 — Run the query script

```bash
python3 /home/claude/booking-analytics-skill/scripts/query_analytics.py \
  --output /tmp/booking_analytics.json
```

The script reads credentials from environment, runs the query, outputs JSON.

### Step 2 — Generate the dashboard

```bash
python3 /home/claude/booking-analytics-skill/scripts/generate_dashboard.py \
  --input /tmp/booking_analytics.json \
  --output /tmp/booking_dashboard.html
```

### Step 3 — Tell the user

Tell the user:
- Total bookings in last 24h
- Successful vs failed count
- Failure percentage
- Which adapter has the most failures
- Path to the HTML dashboard file to open in browser

If env vars are missing, show the user exactly which ones to set and how.

## Query logic

```sql
SELECT
  adapter_name,
  COUNT(*) AS total,
  SUM(CASE WHEN (status_reason IS NULL OR status_reason = '') THEN 1 ELSE 0 END) AS successful,
  SUM(CASE WHEN (status_reason IS NOT NULL AND status_reason != '') THEN 1 ELSE 0 END) AS failed
FROM TRAVEL_BOOKING
WHERE
  product_type = 'hotel'
  AND create_date >= UTC_TIMESTAMP() - INTERVAL 24 HOUR
GROUP BY adapter_name
ORDER BY total DESC;
```

## Error handling

- Missing env vars → show setup instructions, do not proceed
- DB connection error → show error, suggest checking credentials
- No data found → show empty dashboard with "No bookings in last 24h" message
