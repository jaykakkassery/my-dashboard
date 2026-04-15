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


def stable_prefix(raw_msg, min_len=20, max_len=100):
    """
    Extract the longest stable prefix of a message before any variable content
    (numbers, IDs, tokens, special chars) starts.
    Used for match_phrase checks against historical data.
    """
    if not raw_msg:
        return ""

    line = raw_msg.split("\n")[0].strip()

    match = re.search(
        r'[\[\(]|'           # opening bracket
        r'\b[0-9a-f]{8,}\b|' # long hex / UUID fragment
        r'\b\d+[.,]\d+\b|'   # decimal number
        r'(?<!\w)\d+(?!\w)|' # standalone integer
        r':\s*$|'            # trailing colon (before variable content)
        r'\$@',              # object reference
        line, flags=re.IGNORECASE
    )

    prefix = line[:match.start()].strip() if match else line.strip()
    prefix = re.sub(r'[\s:,\.]+$', '', prefix).strip()

    if len(prefix) < min_len:
        return ""

    return prefix[:max_len]


def normalize_message(msg):
    """
    Normalize a log message into a stable grouping key by:
    1. Taking only the first meaningful line (before HTML/stack traces/variable content)
    2. Stripping HTML tags
    3. Replacing variable parts (IDs, numbers, tokens) with placeholders
    """
    if not msg:
        return ""

    # Take only the first line — everything after a newline is usually variable detail
    first_line = msg.split("\n")[0].strip()

    # If first line contains HTML or looks like a full HTML page, truncate before it
    # Use the part before the first '<' tag
    if "<" in first_line:
        pre_html = first_line.split("<")[0].strip()
        if len(pre_html) > 15:
            first_line = pre_html
        else:
            # Strip all HTML tags and collapse whitespace
            first_line = re.sub(r"<[^>]+>", " ", first_line)
            first_line = re.sub(r"\s+", " ", first_line).strip()

    # For grouping: use stable prefix if message has variable content early on
    # This groups "Missing required credential for ORA.18..." and "...ORA.43..." together
    prefix = stable_prefix(first_line, min_len=20, max_len=200)
    if prefix and len(prefix) < len(first_line) * 0.8:
        # The prefix is significantly shorter — variable content detected early
        # Use prefix + "…" as the display pattern
        msg = prefix + " …"
    else:
        msg = first_line

    # Strip URLs — they contain variable paths/tokens
    msg = re.sub(r"https?://\S+", "{url}", msg)

    # UUIDs
    msg = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{uuid}", msg, flags=re.IGNORECASE)

    # Long hex strings (tokens, hashes)
    msg = re.sub(r"\b[0-9a-f]{16,}\b", "{hex}", msg, flags=re.IGNORECASE)

    # Decimal numbers
    msg = re.sub(r"\b\d+\.\d+\b", "{n}", msg)

    # Integers
    msg = re.sub(r"\b\d+\b", "{n}", msg)

    # Object references like ClassName$@3390e9a6 or ClassName@2dd0347e
    msg = re.sub(r'[$@][0-9a-f]{6,}', '', msg, flags=re.IGNORECASE)

    # Collapse whitespace
    msg = re.sub(r"\s+", " ", msg).strip()

    # Trim to 200 chars max
    if len(msg) > 200:
        msg = msg[:200].rsplit(" ", 1)[0] + " …"

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


def get_grouping_key(source: dict) -> tuple[str, str]:
    """
    Returns (pattern, raw_sample) for a log document.
    Uses stack_trace first line as primary grouping key if available,
    falls back to @message otherwise.
    The raw_sample is the original text used for match_phrase checks.
    """
    stack_trace = source.get("@fields", {}).get("stack_trace", "").strip()
    message     = source.get("@message", "").strip()

    if stack_trace:
        # Use first line of stack trace as the grouping key
        # e.g. "java.lang.Exception: Invalid Status Code: 400 Bad Request"
        first_line = stack_trace.split("\n")[0].strip()
        return normalize_message(first_line), first_line

    return normalize_message(message), message


def fetch_patterns(severity, must_clauses):
    """
    Two-level aggregation: logger → method → top_hits(100 samples).
    Groups by stack_trace first line (if present) else @message.
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
                                "top_hits": {
                                    "size": 100,
                                    "_source": ["@message", "@fields.stack_trace"]
                                }
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
            rows.append({"pattern": logger.split(".")[-1], "count": lb["doc_count"], "logger": logger, "method": "", "raw_sample": ""})
            continue

        for mb in method_buckets:
            method       = mb["key"]
            bucket_count = mb["doc_count"]
            hits         = mb.get("sample", {}).get("hits", {}).get("hits", [])

            if not hits:
                rows.append({"pattern": f"{logger.split('.')[-1]}.{method}", "count": bucket_count, "logger": logger, "method": method, "raw_sample": ""})
                continue

            # Collect distinct patterns using stack_trace first line if available
            pattern_to_raw = {}  # normalized_pattern → raw_sample for match_phrase
            for h in hits:
                src = h["_source"]
                p, raw_sample = get_grouping_key(src)
                if not p:
                    continue
                if p not in pattern_to_raw:
                    pattern_to_raw[p] = raw_sample

            distinct_patterns = list(pattern_to_raw.keys())

            if len(distinct_patterns) <= 1:
                # Single pattern — assign full bucket count exactly
                pattern    = distinct_patterns[0] if distinct_patterns else f"{logger.split('.')[-1]}.{method}"
                raw_sample = pattern_to_raw.get(pattern, "")
                rows.append({"pattern": pattern, "count": bucket_count, "logger": logger, "method": method, "raw_sample": raw_sample})
            else:
                # Multiple patterns — get exact counts via filter aggs
                filters = {}
                for p, raw in pattern_to_raw.items():
                    first_line = raw.split("\n")[0].strip()[:200]
                    if not first_line:
                        continue
                    # If raw looks like a stack trace (starts with java/scala/net class name)
                    # match on @fields.stack_trace, otherwise @message
                    if re.match(r'^(java|scala|net|com|org)\.', first_line):
                        filters[p] = {"match_phrase": {"@fields.stack_trace": first_line}}
                    else:
                        filters[p] = {"match_phrase": {"@message": first_line}}

                if not filters:
                    rows.append({"pattern": distinct_patterns[0], "count": bucket_count, "logger": logger, "method": method, "raw_sample": pattern_to_raw.get(distinct_patterns[0], "")})
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
                        rows.append({"pattern": p, "count": count, "logger": logger, "method": method, "raw_sample": pattern_to_raw.get(p, "")})

    # ── Merge rows with identical patterns across different logger/method buckets ──
    from collections import defaultdict
    merged = defaultdict(lambda: {"count": 0, "logger": "", "method": "", "raw_sample": ""})
    for r in rows:
        key = r["pattern"]
        merged[key]["count"]      += r["count"]
        merged[key]["raw_sample"] = merged[key]["raw_sample"] or r["raw_sample"]
        merged[key]["logger"]     = merged[key]["logger"]     or r["logger"]
        merged[key]["method"]     = merged[key]["method"]     or r["method"]

    return sorted(
        [{"pattern": k, **v} for k, v in merged.items()],
        key=lambda x: x["count"],
        reverse=True
    )


def fetch_severity_counts(hours):
    body = {
        "size": 0,
        "query": {"bool": {"must": base_must(hours)}},
        "aggs": {"by_severity": {"terms": {"field": "@fields.severity.keyword", "size": 20}}}
    }
    result  = es_request("GET", f"/{INDEX}/_search", body)
    buckets = result.get("aggregations", {}).get("by_severity", {}).get("buckets", [])
    return {b["key"]: b["doc_count"] for b in buckets}


def pattern_existed_before(logger, method, severity, raw_first_line, cutoff_hours):
    """
    Returns True if this specific logger+method+message existed in the
    90-day window ending cutoff_hours ago.
    Uses raw first line (not normalized) for match_phrase so {n} placeholders
    don't break the search.
    Falls back to logger+method only if no raw_first_line provided.
    """
    must_clauses = [
        time_range(hours=90 * 24, offset_hours=cutoff_hours),
        {"term":  {"@fields.app.keyword":          APP}},
        {"terms": {"@fields.environment.keyword":  ENVS}},
        {"term":  {"@fields.severity.keyword":     severity}},
        {"term":  {"@fields.logger_name.keyword":  logger}},
        {"term":  {"@fields.method.keyword":       method}},
    ]
    if raw_first_line:
        # If it looks like a stack trace line, search in @fields.stack_trace
        if re.match(r'^(java|scala|net|com|org)\.', raw_first_line):
            must_clauses.append({"match_phrase": {"@fields.stack_trace": raw_first_line}})
        else:
            must_clauses.append({"match_phrase": {"@message": raw_first_line}})

    body = {"query": {"bool": {"must": must_clauses}}}
    result = es_request("GET", f"/{INDEX}/_count", body)
    return result.get("count", 0) > 0


def fetch_new_patterns(severity, hours):
    """
    Patterns that FIRST appeared within the last 7 days.
    Checks logger+method+raw message together using _count for exact results.
    """
    recent_rows = fetch_patterns(severity, base_must(hours=7 * 24))

    new = []
    for r in recent_rows:
        raw = r.get("raw_sample", "")
        # Use stable prefix — part before any variable content — for match_phrase
        search_phrase = stable_prefix(raw)

        if not pattern_existed_before(r["logger"], r["method"], severity, search_phrase, cutoff_hours=7 * 24):
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
