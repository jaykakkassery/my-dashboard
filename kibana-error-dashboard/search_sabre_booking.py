#!/usr/bin/env python3
"""
search_sabre_booking.py
Search Kibana/ES for a Sabre booking request+response by confirmation number.

Usage:
    python search_sabre_booking.py --confirmation 3439272332 --date 2026-03-20
"""

import argparse
import json
import os
import sys

import requests
from requests.auth import HTTPBasicAuth
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KIBANA_HOST  = "https://kibana.infra.tstllc.net"
KIBANA_PROXY = f"{KIBANA_HOST}/api/console/proxy"
INDEX        = "logstash-*"

ES_USER     = os.environ.get("ES_USER")
ES_PASSWORD = os.environ.get("ES_PASSWORD")

if not ES_USER or not ES_PASSWORD:
    print("ERROR: ES_USER and ES_PASSWORD env vars must be set.", file=sys.stderr)
    sys.exit(1)

AUTH    = HTTPBasicAuth(ES_USER, ES_PASSWORD)
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}


def es_search(body):
    resp = requests.post(
        KIBANA_PROXY,
        params={"path": f"/{INDEX}/_search", "method": "GET"},
        headers=HEADERS,
        auth=AUTH,
        json=body,
        timeout=120,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()


def search_logs(date_str, terms, size=10):
    """Search logs for a given date. terms is a list of strings, all must match across any field."""
    must = [
        {"range": {"@timestamp": {
            "gte": f"{date_str}T00:00:00Z",
            "lte": f"{date_str}T23:59:59Z",
        }}}
    ]
    for term in terms:
        must.append({"multi_match": {"query": term, "fields": ["*"]}})
    body = {
        "size": size,
        "sort": [{"@timestamp": {"order": "asc"}}],
        "query": {"bool": {"must": must}},
        "_source": True,
    }
    return es_search(body)


def extract_uuid_from_source(source):
    """Try to find a UUID field in the document source."""
    import re
    uuid_pattern = re.compile(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        re.IGNORECASE
    )

    fields = source.get("@fields", {})
    args   = fields.get("args", {})

    # Primary: @fields.args.resp.uuid or @fields.args.req.uuid
    if isinstance(args, dict):
        for key in ("resp", "req"):
            obj = args.get(key, {})
            if isinstance(obj, dict):
                uuid = obj.get("uuid", "")
                if uuid and uuid_pattern.match(str(uuid)):
                    return f"@fields.args.{key}.uuid", str(uuid)

    # Fallback: other @fields keys
    for key in ["uuid", "request_id", "correlation_id", "trace_id", "session_id"]:
        val = fields.get(key, "")
        if val and uuid_pattern.match(str(val)):
            return f"@fields.{key}", str(val)

    # Fallback: scan @message
    message = source.get("@message", "")
    matches = uuid_pattern.findall(message)
    if matches:
        return "@message", matches[0]

    return None, None


def print_hit(hit, label):
    src = hit["_source"]
    ts      = src.get("@timestamp", "")
    message = src.get("@message", "")
    fields  = src.get("@fields", {})

    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"{'='*80}")
    print(f"  Timestamp  : {ts}")
    print(f"  Index      : {hit.get('_index', '')}")
    print(f"  App        : {fields.get('app', '')}")
    print(f"  Env        : {fields.get('environment', '')}")
    print(f"  Logger     : {fields.get('logger_name', '')}")
    print(f"  Method     : {fields.get('method', '')}")
    print(f"  Severity   : {fields.get('severity', '')}")

    # Print all @fields
    if fields:
        print(f"\n  --- @fields ---")
        for k, v in sorted(fields.items()):
            if k not in ("app", "environment", "logger_name", "method", "severity", "stack_trace"):
                print(f"    {k}: {v}")

    print(f"\n  --- @message ---")
    # Print full message (truncated at 3000 chars for readability)
    msg_display = message if len(message) <= 3000 else message[:3000] + "\n  ... [truncated]"
    for line in msg_display.split("\n"):
        print(f"    {line}")

    stack = fields.get("stack_trace", "")
    if stack:
        print(f"\n  --- stack_trace (first 500 chars) ---")
        print(f"    {stack[:500]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmation", required=True, help="Confirmation number to search for")
    parser.add_argument("--date", default="2026-03-20", help="Date to search (YYYY-MM-DD)")
    args = parser.parse_args()

    date_str     = args.date
    confirmation = args.confirmation

    print(f"\nSearching Kibana logs for date: {date_str}")
    print(f"Confirmation number: {confirmation}")
    print(f"Kibana: {KIBANA_HOST}\n")

    # ── Step 1: Find the response (contains confirmation number) ──────────────
    print(f"Step 1: Searching for SabreHotelCreatePNRRS with confirmation {confirmation}...")
    rs_result = search_logs(date_str, ["SabreHotelCreatePNRRS", confirmation], size=5)
    rs_hits   = rs_result.get("hits", {}).get("hits", [])

    if not rs_hits:
        print(f"  No SabreHotelCreatePNRRS found with confirmation {confirmation} on {date_str}")
        print("  Trying broader search (response only, no confirmation filter)...")
        rs_result = search_logs(date_str, ["SabreHotelCreatePNRRS"], size=5)
        rs_hits   = rs_result.get("hits", {}).get("hits", [])

    if not rs_hits:
        print("  No SabreHotelCreatePNRRS logs found at all on this date.")
    else:
        print(f"  Found {len(rs_hits)} response hit(s).")
        for i, hit in enumerate(rs_hits):
            print_hit(hit, f"RESPONSE [{i+1}] — SabreHotelCreatePNRRS")

    # ── Step 2: Extract UUID from response and find matching request ──────────
    uuid = None
    uuid_field = None
    if rs_hits:
        for hit in rs_hits:
            uuid_field, uuid = extract_uuid_from_source(hit["_source"])
            if uuid:
                break

    if uuid:
        print(f"\nStep 2: Found UUID '{uuid}' (from field: {uuid_field})")
        print(f"        Searching for SabreHotelCreatePNRRQ with same UUID...")
        rq_result = search_logs(date_str, ["SabreHotelCreatePNRRQ", uuid], size=5)
        rq_hits   = rq_result.get("hits", {}).get("hits", [])

        if not rq_hits:
            print(f"  No SabreHotelCreatePNRRQ found with UUID {uuid} on {date_str}")
        else:
            print(f"  Found {len(rq_hits)} request hit(s).")
            for i, hit in enumerate(rq_hits):
                print_hit(hit, f"REQUEST [{i+1}] — SabreHotelCreatePNRRQ")
    else:
        print("\nStep 2: Could not extract UUID from response — searching for request separately...")
        rq_result = search_logs(date_str, ["SabreHotelCreatePNRRQ"], size=5)
        rq_hits   = rq_result.get("hits", {}).get("hits", [])
        if not rq_hits:
            print("  No SabreHotelCreatePNRRQ logs found on this date.")
        else:
            print(f"  Found {len(rq_hits)} request hit(s) (unmatched — no UUID to correlate).")
            for i, hit in enumerate(rq_hits):
                print_hit(hit, f"REQUEST [{i+1}] — SabreHotelCreatePNRRQ")

    print("\nDone.")


if __name__ == "__main__":
    main()
