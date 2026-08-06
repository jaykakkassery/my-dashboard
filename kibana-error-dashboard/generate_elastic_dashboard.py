#!/usr/bin/env python3
"""
generate_elastic_dashboard.py
Reads elastic_data.json and generates a polished HTML dashboard.
"""

import json
import sys
import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def load_data(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def severity_bar(error: int, warn: int, info: int) -> str:
    total = error + warn + info or 1
    ep = round(error / total * 100, 1)
    wp = round(warn / total * 100, 1)
    ip = round(info / total * 100, 1)
    return f"""
    <div class="sev-bar-wrap">
      <div class="sev-segment seg-error" style="width:{ep}%" title="Error {ep}%"></div>
      <div class="sev-segment seg-warn"  style="width:{wp}%" title="Warn {wp}%"></div>
      <div class="sev-segment seg-info"  style="width:{ip}%" title="Info {ip}%"></div>
    </div>
    <div class="sev-legend">
      <span class="dot dot-error"></span>Error {ep}%&nbsp;&nbsp;
      <span class="dot dot-warn"></span>Warn {wp}%&nbsp;&nbsp;
      <span class="dot dot-info"></span>Info {ip}%
    </div>"""


def table_rows(items: list[dict], badge_class: str) -> str:
    if not items:
        return '<tr><td colspan="2" class="empty">No data found</td></tr>'
    rows = []
    max_count = items[0]["count"] if items else 1
    for i, item in enumerate(items):
        pct = round(item["count"] / max_count * 100)
        rows.append(f"""
        <tr>
          <td class="rank">#{i+1}</td>
          <td class="msg-cell">
            <div class="msg-text">{_escape(item['pattern'])}</div>
            <div class="bar-bg"><div class="bar-fill {badge_class}" style="width:{pct}%"></div></div>
          </td>
          <td><span class="badge {badge_class}">{item['count']:,}</span></td>
        </tr>""")
    return "\n".join(rows)


def new_table_rows(items: list[dict], badge_class: str) -> str:
    if not items:
        return '<tr><td colspan="2" class="empty">✓ No new patterns detected</td></tr>'
    rows = []
    for i, item in enumerate(items):
        rows.append(f"""
        <tr>
          <td class="rank">#{i+1}</td>
          <td class="msg-cell">
            <div class="msg-text">{_escape(item['pattern'])}</div>
          </td>
          <td><span class="badge {badge_class}">{item['count']:,}</span></td>
        </tr>""")
    return "\n".join(rows)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_size(gb, method="exact") -> str:
    if gb is None:
        return "N/A"
    if gb >= 1000:
        label = f"{gb/1000:.2f} TB"
    else:
        label = f"{gb:.2f} GB"
    if method == "estimated":
        label += " ~est"
    return label


def generate(data: dict) -> str:
    meta = data["meta"]
    sc = data.get("severity_counts", {})
    errors = sc.get("error", 0)
    warns  = sc.get("warn", 0)
    infos  = sc.get("info", 0)
    total  = errors + warns + infos

    now_est = datetime.now(ZoneInfo("America/New_York"))
    generated = now_est.strftime("%Y-%m-%d %H:%M %Z")

    # Size display
    size_gb     = data.get("index_size_gb")
    size_method = data.get("index_size_method", "exact")
    size_label  = fmt_size(size_gb, size_method)

    # Doc count from _count query (stored in meta via total counts)
    doc_count = data.get("total_doc_count", None)

    top_error_rows = table_rows(data.get("top_errors", []), "badge-error")
    top_warn_rows  = table_rows(data.get("top_warns", []), "badge-warn")
    top_info_rows  = table_rows(data.get("top_infos", []), "badge-info")
    new_error_rows = new_table_rows(data.get("new_errors", []), "badge-error")
    new_warn_rows  = new_table_rows(data.get("new_warns", []), "badge-warn")
    sev_bar        = severity_bar(errors, warns, infos)

    # Build size card content — show doc count when size is estimated
    if size_method == "estimated" and doc_count:
        size_card_value = f'{size_label}<div class="stat-sub">{doc_count:,} docs</div>'
    else:
        size_card_value = size_label

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Hotel Log Dashboard · {meta['period_label']}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap" rel="stylesheet"/>
<style>
  :root {{
    --bg:       #0d0f14;
    --surface:  #141720;
    --border:   #1e2330;
    --text:     #c8cdd8;
    --muted:    #5a6072;
    --accent:   #4f7cff;
    --error:    #ff4f4f;
    --warn:     #ffb547;
    --info:     #47c1bf;
    --success:  #3ecf8e;
    --mono:     'IBM Plex Mono', monospace;
    --sans:     'IBM Plex Sans', sans-serif;
  }}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.6;
    min-height: 100vh;
  }}

  /* ── Header ── */
  header {{
    background: linear-gradient(135deg, #0a0c10 0%, #111827 100%);
    border-bottom: 1px solid var(--border);
    padding: 28px 40px 24px;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .header-left h1 {{
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.3px;
    color: #fff;
  }}
  .header-left h1 span {{ color: var(--accent); }}
  .header-left .sub {{
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }}
  .header-right {{
    text-align: right;
  }}
  .period-pill {{
    display: inline-block;
    background: rgba(79,124,255,.15);
    border: 1px solid rgba(79,124,255,.3);
    color: var(--accent);
    font-family: var(--mono);
    font-size: 11px;
    padding: 4px 12px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }}
  .gen-time {{
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    margin-top: 6px;
  }}

  /* ── Layout ── */
  main {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 24px;
    display: grid;
    gap: 24px;
  }}

  /* ── Stat cards row ── */
  .stat-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    position: relative;
    overflow: hidden;
  }}
  .stat-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
  }}
  .stat-card.c-error::before {{ background: var(--error); }}
  .stat-card.c-warn::before  {{ background: var(--warn); }}
  .stat-card.c-info::before  {{ background: var(--info); }}
  .stat-card.c-total::before {{ background: var(--accent); }}
  .stat-card.c-size::before  {{ background: var(--success); }}
  .stat-label {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    font-family: var(--mono);
  }}
  .stat-value {{
    font-size: 32px;
    font-weight: 700;
    color: #fff;
    line-height: 1.1;
    margin-top: 6px;
  }}
  .stat-sub {{
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    margin-top: 4px;
    letter-spacing: 0.3px;
  }}
  .stat-card.c-error .stat-value {{ color: var(--error); }}
  .stat-card.c-warn  .stat-value {{ color: var(--warn); }}
  .stat-card.c-info  .stat-value {{ color: var(--info); }}
  .stat-card.c-size  .stat-value {{ color: var(--success); font-size: 24px; }}

  /* ── Severity bar ── */
  .sev-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 24px;
  }}
  .sev-card h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 14px; font-family: var(--mono); }}
  .sev-bar-wrap {{
    display: flex;
    height: 20px;
    border-radius: 4px;
    overflow: hidden;
    gap: 2px;
    background: var(--bg);
  }}
  .sev-segment {{ transition: width .4s ease; }}
  .seg-error {{ background: var(--error); }}
  .seg-warn  {{ background: var(--warn); }}
  .seg-info  {{ background: var(--info); }}
  .sev-legend {{
    margin-top: 10px;
    font-size: 12px;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }}
  .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; }}
  .dot-error {{ background: var(--error); }}
  .dot-warn  {{ background: var(--warn); }}
  .dot-info  {{ background: var(--info); }}

  /* ── Section ── */
  .section {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }}
  .section-header {{
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .section-header h2 {{
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
    color: #fff;
  }}
  .section-header .icon {{
    width: 28px; height: 28px;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px;
  }}
  .icon-error {{ background: rgba(255,79,79,.15); }}
  .icon-warn  {{ background: rgba(255,181,71,.15); }}
  .icon-info  {{ background: rgba(71,193,191,.15); }}
  .icon-new   {{ background: rgba(79,124,255,.15); }}

  /* ── Table ── */
  table {{
    width: 100%;
    border-collapse: collapse;
  }}
  th {{
    padding: 10px 16px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    font-family: var(--mono);
    text-align: left;
    border-bottom: 1px solid var(--border);
    background: rgba(255,255,255,.02);
  }}
  tr {{ transition: background .15s; }}
  tr:hover td {{ background: rgba(255,255,255,.03); }}
  td {{
    padding: 10px 16px;
    border-bottom: 1px solid rgba(255,255,255,.04);
    vertical-align: middle;
  }}
  td.rank {{
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    width: 36px;
  }}
  td.msg-cell {{ max-width: 700px; }}
  .msg-text {{
    font-family: var(--mono);
    font-size: 12px;
    color: var(--text);
    word-break: break-word;
    line-height: 1.5;
    margin-bottom: 5px;
  }}
  .bar-bg {{
    background: rgba(255,255,255,.05);
    border-radius: 2px;
    height: 3px;
    overflow: hidden;
  }}
  .bar-fill {{ height: 100%; border-radius: 2px; transition: width .4s ease; }}
  .bar-fill.badge-error {{ background: var(--error); opacity: .6; }}
  .bar-fill.badge-warn  {{ background: var(--warn);  opacity: .6; }}
  .bar-fill.badge-info  {{ background: var(--info);  opacity: .6; }}
  .badge {{
    display: inline-block;
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 4px;
    white-space: nowrap;
  }}
  .badge-error {{ background: rgba(255,79,79,.15);  color: var(--error); }}
  .badge-warn  {{ background: rgba(255,181,71,.15); color: var(--warn); }}
  .badge-info  {{ background: rgba(71,193,191,.15); color: var(--info); }}
  .badge-new   {{ background: rgba(79,124,255,.15); color: var(--accent); }}
  .empty {{
    text-align: center;
    padding: 32px;
    color: var(--success);
    font-family: var(--mono);
    font-size: 12px;
  }}

  /* ── Two-col grid ── */
  .two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }}
  @media (max-width: 860px) {{
    .two-col {{ grid-template-columns: 1fr; }}
    header {{ padding: 20px; }}
    main {{ padding: 16px; }}
  }}

  /* ── Footer ── */
  footer {{
    text-align: center;
    padding: 24px;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    border-top: 1px solid var(--border);
    letter-spacing: 0.5px;
  }}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <h1>🏨 Hotel Log <span>Analytics</span></h1>
    <div class="sub">TST · Elasticsearch · {meta['app'].upper()} · Production</div>
  </div>
  <div class="header-right">
    <div class="period-pill">{meta['period_label']}</div>
    <div class="gen-time">Generated {generated}</div>
  </div>
</header>

<main>

  <!-- Stat Cards -->
  <div class="stat-row">
    <div class="stat-card c-error">
      <div class="stat-label">Errors</div>
      <div class="stat-value">{errors:,}</div>
    </div>
    <div class="stat-card c-warn">
      <div class="stat-label">Warnings</div>
      <div class="stat-value">{warns:,}</div>
    </div>
    <div class="stat-card c-info">
      <div class="stat-label">Info</div>
      <div class="stat-value">{infos:,}</div>
    </div>
    <div class="stat-card c-total">
      <div class="stat-label">Total Logs</div>
      <div class="stat-value">{total:,}</div>
    </div>
    <div class="stat-card c-size">
      <div class="stat-label">Index Size</div>
      <div class="stat-value">{size_card_value}</div>
    </div>
  </div>

  <!-- Severity Bar -->
  <div class="sev-card">
    <h3>Log Volume Breakdown</h3>
    {sev_bar}
  </div>

  <!-- Top Errors + Top Warns side by side -->
  <div class="two-col">

    <div class="section">
      <div class="section-header">
        <div class="icon icon-error">🔴</div>
        <h2>Top 10 Error Patterns</h2>
      </div>
      <table>
        <thead><tr><th>#</th><th>Pattern</th><th>Count</th></tr></thead>
        <tbody>{top_error_rows}</tbody>
      </table>
    </div>

    <div class="section">
      <div class="section-header">
        <div class="icon icon-warn">🟡</div>
        <h2>Top 10 Warn Patterns</h2>
      </div>
      <table>
        <thead><tr><th>#</th><th>Pattern</th><th>Count</th></tr></thead>
        <tbody>{top_warn_rows}</tbody>
      </table>
    </div>

  </div>

  <!-- Top Info — full width -->
  <div class="section">
    <div class="section-header">
      <div class="icon icon-info">🔵</div>
      <h2>Top 10 Info Patterns</h2>
    </div>
    <table>
      <thead><tr><th>#</th><th>Pattern</th><th>Count</th></tr></thead>
      <tbody>{top_info_rows}</tbody>
    </table>
  </div>

  <!-- New Errors + New Warns side by side -->
  <div class="two-col">

    <div class="section">
      <div class="section-header">
        <div class="icon icon-new">🆕</div>
        <h2>New Error Patterns (vs prior 7 days)</h2>
      </div>
      <table>
        <thead><tr><th>#</th><th>Pattern</th><th>Count</th></tr></thead>
        <tbody>{new_error_rows}</tbody>
      </table>
    </div>

    <div class="section">
      <div class="section-header">
        <div class="icon icon-new">🆕</div>
        <h2>New Warn Patterns (vs prior 7 days)</h2>
      </div>
      <table>
        <thead><tr><th>#</th><th>Pattern</th><th>Count</th></tr></thead>
        <tbody>{new_warn_rows}</tbody>
      </table>
    </div>

  </div>

</main>

<footer>TST Hotel Log Dashboard · Auto-generated · {generated} · @fields.app: hotel · env: green / blue</footer>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate Elastic log dashboard HTML")
    parser.add_argument("--input",  default="elastic_data.json", help="Input JSON file")
    parser.add_argument("--output", default="elastic_dashboard.html", help="Output HTML file")
    args = parser.parse_args()

    data = load_data(args.input)
    html = generate(data)

    with open(args.output, "w") as f:
        f.write(html)

    print(f"Dashboard written to: {args.output}")


if __name__ == "__main__":
    main()
