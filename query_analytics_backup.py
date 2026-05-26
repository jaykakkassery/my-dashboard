#!/usr/bin/env python3
"""
query_analytics.py
Reads TST DB credentials from environment variables (never from args).
Queries TRAVEL_BOOKING for hotel booking success/failure.
Supports --hours/--days, --licensee-id, --adapter-name filters.

True failure logic:
  - A failed booking is only counted as a TRUE failure if there is NO
    subsequent successful booking (status_reason IS NULL) with the same
    session_id, itinerary_name, product_type, branch_id that happened
    60+ seconds later (i.e. user retried and succeeded = not a failure).
  - Multiple failed attempts with the same session_id, itinerary_name,
    branch_id, status_reason are counted as ONE failure (not N failures).
"""

import os
import sys
import json
import argparse
from decimal import Decimal
from datetime import datetime, timezone


def get_credentials():
    missing = []
    creds = {
        "host":     os.environ.get("TST_DB_HOST"),
        "port":     os.environ.get("TST_DB_PORT", "3306"),
        "user":     os.environ.get("TST_DB_USER"),
        "password": os.environ.get("TST_DB_PASSWORD", ""),
        "database": os.environ.get("TST_DB_NAME"),
    }
    for key in ["host", "user", "database"]:
        if not creds[key]:
            missing.append(f"TST_DB_{key.upper()}")

    if missing:
        print(json.dumps({
            "error": "missing_env_vars",
            "missing": missing,
            "setup_instructions": (
                "Please set the following environment variables:\n\n"
                "  export TST_DB_HOST=localhost\n"
                "  export TST_DB_PORT=3306\n"
                "  export TST_DB_USER=root\n"
                "  export TST_DB_PASSWORD=\n"
                "  export TST_DB_NAME=book\n"
            )
        }, indent=2))
        sys.exit(1)

    return creds


class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return super().default(obj)


def build_filters(licensee_id=None, adapter_name=None):
    """Return extra AND clauses and params for optional filters."""
    clauses = []
    params  = []
    if licensee_id:
        clauses.append("AND failed.licensee_id = %s")
        params.append(licensee_id)
    if adapter_name:
        clauses.append("AND failed.adapter_name = %s")
        params.append(adapter_name)
    return " ".join(clauses), params


# ─────────────────────────────────────────────────────────────────
# TRUE FAILURE CTE
# Produces one row per unique true failure (session+itinerary+branch
# +error) within the requested time window.
# ─────────────────────────────────────────────────────────────────
TRUE_FAILURES_CTE = """
    WITH true_failures AS (
        SELECT
            failed.adapter_name,
            failed.licensee_id,
            failed.session_id,
            failed.itinerary_name,
            failed.branch_id,
            failed.status_reason,
            MIN(failed.create_date) AS first_attempt,
            MAX(failed.create_date) AS last_attempt,
            DATE_FORMAT(MIN(failed.create_date), '%Y-%m-%d %H:00:00') AS hour_bucket
        FROM TRAVEL_BOOKING failed
        WHERE
            failed.product_type = 'hotel'
            AND failed.status_reason IS NOT NULL
            AND failed.status_reason != ''
            AND failed.create_date >= UTC_TIMESTAMP() - INTERVAL {interval_hours} HOUR
            {extra_filters}
            AND NOT EXISTS (
                SELECT 1
                FROM TRAVEL_BOOKING success
                WHERE
                    success.product_type   = 'hotel'
                    AND success.session_id     = failed.session_id
                    AND success.itinerary_name = failed.itinerary_name
                    AND success.branch_id      = failed.branch_id
                    AND success.status_reason  IS NULL
                    AND TIMESTAMPDIFF(SECOND, failed.create_date, success.create_date) >= 60
            )
        GROUP BY
            failed.adapter_name,
            failed.licensee_id,
            failed.session_id,
            failed.itinerary_name,
            failed.branch_id,
            failed.status_reason
    )
"""


def run_query(creds, interval_hours, licensee_id=None, adapter_name=None):
    try:
        import mysql.connector
    except ImportError:
        print(json.dumps({"error": "missing_package",
                          "message": "Run: pip install mysql-connector-python"}))
        sys.exit(1)

    try:
        conn = mysql.connector.connect(
            host=creds["host"],
            port=int(creds["port"]),
            user=creds["user"],
            password=creds["password"],
            database=creds["database"],
            connection_timeout=10
        )
        cursor = conn.cursor(dictionary=True)

        extra_filters, filter_params = build_filters(licensee_id, adapter_name)

        cte = TRUE_FAILURES_CTE.format(
            interval_hours=interval_hours,
            extra_filters=extra_filters
        )

        # ── 1. Total successful bookings (unchanged — a success is a success)
        success_where_parts = [
            "product_type = 'hotel'",
            f"create_date >= UTC_TIMESTAMP() - INTERVAL {interval_hours} HOUR",
            "(status_reason IS NULL OR status_reason = '')"
        ]
        success_params = []
        if licensee_id:
            success_where_parts.append("licensee_id = %s")
            success_params.append(licensee_id)
        if adapter_name:
            success_where_parts.append("adapter_name = %s")
            success_params.append(adapter_name)
        success_where = "WHERE " + " AND ".join(success_where_parts)

        cursor.execute(f"""
            SELECT COUNT(*) AS successful
            FROM TRAVEL_BOOKING
            {success_where}
        """, success_params)
        successful = int(cursor.fetchone()["successful"])

        # ── 2. True failure count (deduplicated)
        cursor.execute(f"""
            {cte}
            SELECT COUNT(*) AS true_failed
            FROM true_failures
        """, filter_params)
        true_failed = int(cursor.fetchone()["true_failed"])

        total       = successful + true_failed
        failure_pct = round((true_failed / total * 100), 2) if total > 0 else 0

        # ── 3. Per-adapter breakdown
        cursor.execute(f"""
            {cte},
            adapter_success AS (
                SELECT
                    adapter_name,
                    COUNT(*) AS successful
                FROM TRAVEL_BOOKING
                {success_where}
                GROUP BY adapter_name
            )
            SELECT
                COALESCE(f.adapter_name, s.adapter_name) AS adapter_name,
                COALESCE(s.successful, 0)                AS successful,
                COALESCE(f.true_failed, 0)               AS failed
            FROM (
                SELECT adapter_name, COUNT(*) AS true_failed
                FROM true_failures
                GROUP BY adapter_name
            ) f
            LEFT JOIN adapter_success s ON s.adapter_name = f.adapter_name
            UNION
            SELECT
                s.adapter_name,
                s.successful,
                COALESCE(f.true_failed, 0)
            FROM adapter_success s
            LEFT JOIN (
                SELECT adapter_name, COUNT(*) AS true_failed
                FROM true_failures
                GROUP BY adapter_name
            ) f ON f.adapter_name = s.adapter_name
            WHERE f.adapter_name IS NULL
            ORDER BY (successful + failed) DESC
        """, filter_params + success_params)
        adapter_rows = cursor.fetchall()

        # ── 4. Hourly trend
        cursor.execute(f"""
            {cte},
            hourly_success AS (
                SELECT
                    DATE_FORMAT(create_date, '%Y-%m-%d %H:00:00') AS hour_bucket,
                    COUNT(*) AS successful
                FROM TRAVEL_BOOKING
                {success_where}
                GROUP BY hour_bucket
            )
            SELECT
                COALESCE(f.hour_bucket, s.hour_bucket) AS hour_bucket,
                COALESCE(s.successful, 0)              AS successful,
                COALESCE(f.true_failed, 0)             AS failed
            FROM (
                SELECT hour_bucket, COUNT(*) AS true_failed
                FROM true_failures
                GROUP BY hour_bucket
            ) f
            LEFT JOIN hourly_success s ON s.hour_bucket = f.hour_bucket
            UNION
            SELECT
                s.hour_bucket,
                s.successful,
                COALESCE(f.true_failed, 0)
            FROM hourly_success s
            LEFT JOIN (
                SELECT hour_bucket, COUNT(*) AS true_failed
                FROM true_failures
                GROUP BY hour_bucket
            ) f ON f.hour_bucket = s.hour_bucket
            WHERE f.hour_bucket IS NULL
            ORDER BY hour_bucket ASC
        """, filter_params + success_params)
        hourly_rows = cursor.fetchall()

        # ── 5. Top 10 failure reasons (deduplicated)
        cursor.execute(f"""
            {cte}
            SELECT
                status_reason,
                COUNT(*) AS count
            FROM true_failures
            GROUP BY status_reason
            ORDER BY count DESC
            LIMIT 10
        """, filter_params)
        failure_reasons = cursor.fetchall()

        # ── 6. Per-licensee breakdown
        if not licensee_id:
            licensee_success_where = success_where  # already built above
            cursor.execute(f"""
                {cte},
                licensee_success AS (
                    SELECT
                        licensee_id,
                        COUNT(*) AS successful
                    FROM TRAVEL_BOOKING
                    {licensee_success_where}
                    GROUP BY licensee_id
                )
                SELECT
                    COALESCE(f.licensee_id, s.licensee_id) AS licensee_id,
                    COALESCE(s.successful, 0)              AS successful,
                    COALESCE(f.true_failed, 0)             AS failed
                FROM (
                    SELECT licensee_id, COUNT(*) AS true_failed
                    FROM true_failures
                    GROUP BY licensee_id
                ) f
                LEFT JOIN licensee_success s ON s.licensee_id = f.licensee_id
                UNION
                SELECT
                    s.licensee_id,
                    s.successful,
                    COALESCE(f.true_failed, 0)
                FROM licensee_success s
                LEFT JOIN (
                    SELECT licensee_id, COUNT(*) AS true_failed
                    FROM true_failures
                    GROUP BY licensee_id
                ) f ON f.licensee_id = s.licensee_id
                WHERE f.licensee_id IS NULL
                ORDER BY (successful + failed) DESC
                LIMIT 10
            """, filter_params + success_params)
            licensee_rows = cursor.fetchall()
        else:
            licensee_rows = []

        cursor.close()
        conn.close()

        return {
            "status":         "ok",
            "generated_at":   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "interval_hours": interval_hours,
            "filters": {
                "licensee_id":  licensee_id  or "all",
                "adapter_name": adapter_name or "all"
            },
            "summary": {
                "total":       total,
                "successful":  successful,
                "failed":      true_failed,
                "failure_pct": failure_pct,
                "success_pct": round(100 - failure_pct, 2)
            },
            "by_adapter": [
                {
                    "adapter":     r["adapter_name"] or "Unknown",
                    "total":       int(r["successful"]) + int(r["failed"]),
                    "successful":  int(r["successful"]),
                    "failed":      int(r["failed"]),
                    "failure_pct": round(int(r["failed"]) / (int(r["successful"]) + int(r["failed"])) * 100, 2)
                                   if (int(r["successful"]) + int(r["failed"])) > 0 else 0
                }
                for r in adapter_rows
            ],
            "by_licensee": [
                {
                    "licensee_id": r["licensee_id"] or "Unknown",
                    "total":       int(r["successful"]) + int(r["failed"]),
                    "successful":  int(r["successful"]),
                    "failed":      int(r["failed"]),
                    "failure_pct": round(int(r["failed"]) / (int(r["successful"]) + int(r["failed"])) * 100, 2)
                                   if (int(r["successful"]) + int(r["failed"])) > 0 else 0
                }
                for r in licensee_rows
            ],
            "hourly_trend": [
                {
                    "hour":       str(r["hour_bucket"]),
                    "total":      int(r["successful"]) + int(r["failed"]),
                    "successful": int(r["successful"]),
                    "failed":     int(r["failed"])
                }
                for r in hourly_rows
            ],
            "top_failure_reasons": [
                {"reason": r["status_reason"], "count": int(r["count"])}
                for r in failure_reasons
            ]
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="TST Booking Analytics Query")
    parser.add_argument("--output",       default="/tmp/booking_analytics.json")
    parser.add_argument("--hours",        type=int, default=None, help="Hours back")
    parser.add_argument("--days",         type=int, default=None, help="Days back")
    parser.add_argument("--licensee-id",  type=str, default=None, help="Filter by licensee_id")
    parser.add_argument("--adapter-name", type=str, default=None, help="Filter by adapter_name")
    args = parser.parse_args()

    if args.days:
        interval_hours = args.days * 24
    elif args.hours:
        interval_hours = args.hours
    else:
        interval_hours = 24

    creds = get_credentials()
    result = run_query(
        creds,
        interval_hours,
        licensee_id=args.licensee_id,
        adapter_name=args.adapter_name
    )

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2, cls=SafeEncoder)

    print(json.dumps(result, indent=2, cls=SafeEncoder))


if __name__ == "__main__":
    main()
