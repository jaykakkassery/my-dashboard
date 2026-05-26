#!/usr/bin/env python3
"""
query_elastic_logs.py
Queries Elasticsearch via Kibana Dev Tools proxy for hotel app logs.

Strategy:
  - Double terms agg: logger_name.keyword → method.keyword → top_hits(1 sample message)
  - Each logger+method bucket = one distinct error type with exact server-side count
  - Fast, accurate, no pagination

Usage:
    python query_elastic_logs.py --hours 24
    python query_elastic_logs.py --days 7
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta

import requests
from requests.auth import HTTPBasicAuth
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ────────────────────────────────────────────────────────────────────
KIBANA_HOST   = "https://kibana.infra.tstllc.net"
KIBANA_PROXY  = f"{KIBANA_HOST}/api/console/proxy"
INDEX         = "logstash-*"
APP           = "hotel"
ENVS          = ["green", "blue"]
TOP_N         = 10
LOGGER_LIMIT  = 200   # max distinct loggers
METHOD_LIMIT  = 20    # max distinct methods per logger
NEW_LOOKBACK  = 7     # days for "new pattern" detection (fixed window, independent of report)

# ── Auth ──────────────────────────────────────────────────────────────────────
ES_USER     = os.environ.get("ES_USER")
ES_PASSWORD = os.environ.get("ES_PASSWORD")

if not ES_USER or not ES_PASSWORD:
    print("ERROR: ES_USER and ES_PASSWORD env vars must be set.", file=sys.stderr)
    sys.exit(1)

AUTH    = HTTPBasicAuth(ES_USER, ES_PASSWORD)
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}


def es_request(method, path, body):
    resp = requests.post(
        KIBANA_PROXY,
        params={"path": path, "method": method},
        headers=HEADERS,
        auth=AUTH,
        json=body,
        timeout=120,
        verify=False,
    )
    if resp.status_code in (401, 403):
        print(f"\nERROR: {resp.status_code} — {resp.text[:300]}", file=sys.stderr)
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


def normalize_message(msg):
    """Strip variable parts so similar messages display cleanly."""
    msg = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{uuid}", msg, flags=re.IGNORECASE)
    msg = re.sub(r"\b[0-9a-f]{16,}\b", "{hex}", msg, flags=re.IGNORECASE)
    msg = re.sub(r"\b\d+\.\d+\b", "{n}", msg)
    msg = re.sub(r"\b\d+\b", "{n}", msg)
    msg = re.sub(r"\s+", " ", msg).strip()
    # Trim very long messages
    if len(msg) > 250:
        msg = msg[:250].rsplit(" ", 1)[0] + " …"
    return msg


def time_range(hours, offset_hours=0):
    now   = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    since = now - timedelta(hours=hours)
    return {"range": {"@timestamp": {
        "gte": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lte": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }}}


def base_must(hours, offset_hours=0):
    return [
        time_range(hours, offset_hours),
        {"term":  {"@fields.app.keyword":         APP}},
        {"terms": {"@fields.environment.keyword": ENVS}},
    ]


def fetch_patterns(severity, must_clauses):
    """
    Two-level aggregation: logger → method → top_hits(100 samples).
    For buckets with multiple distinct message patterns, run exact
    match counts per pattern using filter aggregations.
    """
    body = {
        "size": 0,
        "query": {"bool": {"must": must_clauses + [
            {"term": {"@fields.severity.keyword": severity}}
        ]}},
        "aggs": {
            "by_logger": {
                "terms": {
                    "field": "@fields.logger_name.keyword",
                    "size":  LOGGER_LIMIT,
                    "order": {"_count": "desc"},
                },
                "aggs": {
                    "by_method": {
                        "terms": {
                            "field": "@fields.method.keyword",
                            "size":  METHOD_LIMIT,
                            "order": {"_count": "desc"},
                        },
                        "aggs": {
                            "sample": {
                                "top_hits": {"size": 100, "_source": ["@message"]}
                            }
                        }
                    }
                }
            }
        }
    }

    result         = es_request("GET", f"/{INDEX}/_search", body)
    logger_buckets = result.get("aggregations", {}).get("by_logger", {}).get("buckets", [])

    rows = []
    for lb in logger_buckets:
        logger         = lb["key"]
        method_buckets = lb.get("by_method", {}).get("buckets", [])

        if not method_buckets:
            rows.append({"pattern": logger.split(".")[-1], "count": lb["doc_count"], "logger": logger, "method": ""})
            continue

        for mb in method_buckets:
            method       = mb["key"]
            bucket_count = mb["doc_count"]
            hits         = mb.get("sample", {}).get("hits", {}).get("hits", [])

            if not hits:
                rows.append({"pattern": f"{logger.split('.')[-1]}.{method}", "count": bucket_count, "logger": logger, "method": method})
                continue

            # Collect distinct normalized patterns from samples
            pattern_to_raw = {}  # normalized → one raw example for match query
            for h in hits:
                raw_msg = h["_source"].get("@message", "").strip()
                if not raw_msg:
                    continue
                p = normalize_message(raw_msg)
                if p not in pattern_to_raw:
                    pattern_to_raw[p] = raw_msg

            distinct_patterns = list(pattern_to_raw.keys())

            if len(distinct_patterns) <= 1:
                # Single pattern — assign full bucket count exactly
                pattern = distinct_patterns[0] if distinct_patterns else f"{logger.split('.')[-1]}.{method}"
                rows.append({"pattern": pattern, "count": bucket_count, "logger": logger, "method": method})
            else:
                # Multiple patterns — get exact counts via filter aggs on first line of message
                filters = {}
                for p, raw in pattern_to_raw.items():
                    # Match on the first meaningful line of the message
                    first_line = raw.split("\n")[0].strip()[:200]
                    if first_line:
                        filters[p] = {"match_phrase": {"@message": first_line}}

                if not filters:
                    rows.append({"pattern": distinct_patterns[0], "count": bucket_count, "logger": logger, "method": method})
                    continue

                count_body = {
                    "size": 0,
                    "query": {"bool": {"must": must_clauses + [
                        {"term": {"@fields.severity.keyword": severity}},
                        {"term": {"@fields.logger_name.keyword": logger}},
                        {"term": {"@fields.method.keyword": method}},
                    ]}},
                    "aggs": {
                        "by_pattern": {
                            "filters": {"filters": filters}
                        }
                    }
                }
                count_result = es_request("GET", f"/{INDEX}/_search", count_body)
                pattern_buckets = count_result.get("aggregations", {}).get("by_pattern", {}).get("buckets", {})

                for p, pbucket in pattern_buckets.items():
                    count = pbucket.get("doc_count", 0)
                    if count > 0:
                        rows.append({"pattern": p, "count": count, "logger": logger, "method": method})

    return sorted(rows, key=lambda x: x["count"], reverse=True)


def fetch_severity_counts(hours):
    body = {
        "size": 0,
        "query": {"bool": {"must": base_must(hours)}},
        "aggs": {"by_severity": {"terms": {"field": "@fields.severity.keyword", "size": 20}}}
    }
    result  = es_request("GET", f"/{INDEX}/_search", body)
    buckets = result.get("aggregations", {}).get("by_severity", {}).get("buckets", [])
    return {b["key"]: b["doc_count"] for b in buckets}


def pattern_existed_before(logger, method, severity, cutoff_hours):
    """
    Returns True if this logger+method+severity combination had any docs
    in the 90-day window ending cutoff_hours ago.
    """
    body = {
        "query": {"bool": {"must": [
            time_range(hours=90 * 24, offset_hours=cutoff_hours),
            {"term":  {"@fields.app.keyword":          APP}},
            {"terms": {"@fields.environment.keyword":  ENVS}},
            {"term":  {"@fields.severity.keyword":     severity}},
            {"term":  {"@fields.logger_name.keyword":  logger}},
            {"term":  {"@fields.method.keyword":       method}},
        ]}}
    }
    result = es_request("GET", f"/{INDEX}/_count", body)
    return result.get("count", 0) > 0


def fetch_new_patterns(severity, hours):
    """
    Patterns that FIRST appeared within the last 7 days.
    For each recent logger+method, does an exact _count check against
    the prior 90 days. Only shows patterns with zero prior occurrences.
    """
    recent_rows = fetch_patterns(severity, base_must(hours=7 * 24))

    new = []
    for r in recent_rows:
        if not pattern_existed_before(r["logger"], r["method"], severity, cutoff_hours=7 * 24):
            new.append(r)

    return sorted(new, key=lambda x: x["count"], reverse=True)[:TOP_N]


def fetch_index_size_gb():
    try:
        r = es_request("GET", f"/{INDEX}/_stats/store", {})
        b = r.get("_all", {}).get("total", {}).get("store", {}).get("size_in_bytes", 0)
        if b > 0:
            return round(b / 1024**3, 2), "exact", None
    except Exception:
        pass
    try:
        r = es_request("GET", f"/_cat/indices/{INDEX}?h=store.size&bytes=b&format=json", {})
        if isinstance(r, list):
            b = sum(int(i.get("store.size", 0) or 0) for i in r)
            if b > 0:
                return round(b / 1024**3, 2), "exact", None
    except Exception:
        pass
    try:
        r = es_request("GET", f"/{INDEX}/_count", {"query": {"bool": {"must": [
            {"term":  {"@fields.app.keyword":         APP}},
            {"terms": {"@fields.environment.keyword": ENVS}},
        ]}}})
        n = r.get("count", 0)
        if n > 0:
            return round(n * 1200 / 1024**3, 2), "estimated", n
    except Exception:
        pass
    return None, "unavailable", None


def main():
    parser = argparse.ArgumentParser()
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--hours", type=int)
    grp.add_argument("--days",  type=int)
    parser.add_argument("--output", default="elastic_data.json")
    args = parser.parse_args()

    hours        = args.hours if args.hours else args.days * 24
    period_label = f"Last {args.hours} hours" if args.hours else f"Last {args.days} days"

    print(f"Querying hotel logs: {period_label}")

    print("  → Severity counts...")
    severity_counts = fetch_severity_counts(hours)

    print("  → Top error patterns (logger × method)...")
    error_groups = fetch_patterns("error", base_must(hours))

    print("  → Top warn patterns (logger × method)...")
    warn_groups = fetch_patterns("warn", base_must(hours))

    print("  → New error patterns (first seen in last 7 days)...")
    new_errors = fetch_new_patterns("error", hours)

    print("  → New warn patterns (first seen in last 7 days)...")
    new_warns = fetch_new_patterns("warn", hours)

    print("  → Top info patterns (logger × method)...")
    info_groups = fetch_patterns("info", base_must(hours))

    print("  → Index size...")
    size_gb, size_method, doc_count = fetch_index_size_gb()
    print(f"    {'✓' if size_method == 'exact' else '~'} {size_gb} GB ({size_method})")

    data = {
        "meta": {
            "period_label": period_label,
            "hours":        hours,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "app":          APP,
        },
        "severity_counts":   severity_counts,
        "top_errors":        error_groups[:TOP_N],
        "top_warns":         warn_groups[:TOP_N],
        "top_infos":         info_groups[:TOP_N],
        "new_errors":        new_errors,
        "new_warns":         new_warns,
        "index_size_gb":     size_gb,
        "index_size_method": size_method,
        "total_doc_count":   doc_count,
        "total_error_count": severity_counts.get("error", 0),
        "total_warn_count":  severity_counts.get("warn", 0),
    }

    with open(args.output, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nDone → {args.output}")
    print(f"  Errors: {data['total_error_count']:,} ({len(error_groups)} distinct patterns)")
    print(f"  Warns:  {data['total_warn_count']:,} ({len(warn_groups)} distinct patterns)")
    print(f"  Infos:  {severity_counts.get('info', 0):,} ({len(info_groups)} distinct patterns)")
    print(f"  New errors: {len(new_errors)}, New warns: {len(new_warns)}")


if __name__ == "__main__":
    main()
