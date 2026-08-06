#!/usr/bin/env python3
"""
generate_dashboard.py
Generates HTML dashboard from analytics JSON.
Displays times in Eastern Time (ET). Failure reasons as table (top 10).
Shows active filters (licensee_id, adapter_name) in header.
Shows licensee breakdown table when no licensee filter is active.
"""

import json
import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


def utc_to_est(utc_str):
    try:
        if utc_str.endswith(" UTC"):
            utc_str = utc_str[:-4]
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        et_dt = dt.astimezone(ET)
        return et_dt.strftime("%Y-%m-%d %I:%M:%S %p %Z")
    except Exception:
        return utc_str


def hourly_label_to_est(utc_str):
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        et_dt = dt.astimezone(ET)
        return et_dt.strftime("%m/%d %I%p")
    except Exception:
        return utc_str[-8:-3]


def generate_html(data):
    if data.get("status") == "error":
        return f"""<!DOCTYPE html><html><body>
        <h1 style="color:red">Error</h1><p>{data.get('error')}</p>
        </body></html>"""

    summary         = data["summary"]
    by_adapter      = data["by_adapter"]
    by_licensee     = data.get("by_licensee", [])
    hourly          = data["hourly_trend"]
    failure_reasons = data.get("top_failure_reasons", [])
    generated_at    = utc_to_est(data.get("generated_at", ""))
    interval_hours  = data.get("interval_hours", 24)
    filters         = data.get("filters", {"licensee_id": "all", "adapter_name": "all"})

    filter_licensee = filters.get("licensee_id",  "all")
    filter_adapter  = filters.get("adapter_name", "all")

    # Range label
    if interval_hours % 24 == 0:
        range_label = f"Last {interval_hours // 24} day{'s' if interval_hours > 24 else ''}"
    else:
        range_label = f"Last {interval_hours} hour{'s' if interval_hours > 1 else ''}"

    # Filter pills HTML
    filter_pills = ""
    if filter_licensee != "all":
        filter_pills += f'<span class="filter-pill">Licensee: {filter_licensee}</span>'
    if filter_adapter != "all":
        filter_pills += f'<span class="filter-pill">Adapter: {filter_adapter}</span>'
    if not filter_pills:
        filter_pills = '<span class="filter-pill filter-all">All licensees &amp; adapters</span>'

    adapter_labels  = [r["adapter"] for r in by_adapter]
    adapter_success = [r["successful"] for r in by_adapter]
    adapter_failed  = [r["failed"] for r in by_adapter]

    hourly_labels  = [hourly_label_to_est(r["hour"]) for r in hourly]
    hourly_success = [r["successful"] for r in hourly]
    hourly_failed  = [r["failed"] for r in hourly]

    failure_pct = summary["failure_pct"]
    color_gauge = "#ef4444" if failure_pct > 20 else "#f59e0b" if failure_pct > 5 else "#10b981"

    # Failure reasons table
    failure_rows_html = ""
    if failure_reasons:
        for i, r in enumerate(failure_reasons, 1):
            pct = round(r['count'] / summary['failed'] * 100, 1) if summary['failed'] > 0 else 0
            color = "#ef4444" if pct > 30 else "#f59e0b" if pct > 10 else "#94a3b8"
            adapters = r.get('adapters', '')
            failure_rows_html += f"""
            <tr>
                <td style="color:#64748b;font-size:0.75rem">{i}</td>
                <td style="color:#e2e8f0;word-break:break-word">{r['reason']}</td>
                <td style="color:#94a3b8;font-size:0.72rem;font-family:var(--mono)">{adapters}</td>
                <td style="text-align:right;color:{color};font-weight:500">{r['count']:,}</td>
                <td style="text-align:right;color:{color}">{pct}%</td>
            </tr>"""
    else:
        failure_rows_html = '<tr><td colspan="5" style="text-align:center;color:#64748b;padding:2rem">No failures in this period ✅</td></tr>'

    # Adapter breakdown table
    adapter_rows_html = ""
    for r in by_adapter:
        fp = r['failure_pct']
        bar_color = '#ef4444' if fp > 20 else '#f59e0b' if fp > 5 else '#10b981'
        adapter_rows_html += f"""
        <tr>
            <td style="color:#e2e8f0;font-weight:500">{r['adapter']}</td>
            <td>{r['total']:,}</td>
            <td style="color:#10b981">{r['successful']:,}</td>
            <td style="color:#ef4444">{r['failed']:,}</td>
            <td>
                <div class="pct-bar-wrap">
                    <div class="pct-bar"><div class="pct-bar-fill" style="width:{fp}%;background:{bar_color}"></div></div>
                    <span class="pct-label" style="color:{bar_color}">{fp}%</span>
                </div>
            </td>
        </tr>"""

    # Licensee breakdown table (only shown when not filtered to one licensee)
    licensee_section_html = ""
    if by_licensee:
        licensee_rows_html = ""
        for r in by_licensee:
            fp = r['failure_pct']
            bar_color = '#ef4444' if fp > 20 else '#f59e0b' if fp > 5 else '#10b981'
            licensee_rows_html += f"""
            <tr>
                <td style="color:#e2e8f0;font-weight:500;font-family:var(--mono)">{r['licensee_id']}</td>
                <td>{r['total']:,}</td>
                <td style="color:#10b981">{r['successful']:,}</td>
                <td style="color:#ef4444">{r['failed']:,}</td>
                <td>
                    <div class="pct-bar-wrap">
                        <div class="pct-bar"><div class="pct-bar-fill" style="width:{fp}%;background:{bar_color}"></div></div>
                        <span class="pct-label" style="color:{bar_color}">{fp}%</span>
                    </div>
                </td>
            </tr>"""

        licensee_section_html = f"""
        <div class="table-card">
          <div class="chart-title">Top 10 Licensees by Booking Volume</div>
          <table>
            <thead>
              <tr>
                <th>Licensee ID</th><th>Total</th><th>Successful</th><th>Failed</th><th>Failure Rate</th>
              </tr>
            </thead>
            <tbody>{licensee_rows_html}</tbody>
          </table>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TST Hotel Booking Analytics</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
  :root {{
    --bg:#0a0e1a; --surface:#111827; --surface2:#1a2235;
    --border:rgba(255,255,255,0.07); --text:#e2e8f0; --muted:#64748b;
    --success:#10b981; --danger:#ef4444; --warning:#f59e0b; --accent:#6366f1;
    --font:'DM Sans',sans-serif; --mono:'DM Mono',monospace;
  }}
  body {{ background:var(--bg); color:var(--text); font-family:var(--font); min-height:100vh; padding:2rem; }}

  .header {{ display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:1.5rem; padding-bottom:1.5rem; border-bottom:1px solid var(--border); }}
  .header-left h1 {{ font-size:1.6rem; font-weight:600; letter-spacing:-0.02em; color:#fff; }}
  .header-left p  {{ font-size:0.78rem; color:var(--muted); margin-top:4px; font-family:var(--mono); }}
  .header-right   {{ text-align:right; }}

  .filter-bar {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:1.5rem; }}
  .filter-bar-label {{ font-size:0.72rem; color:var(--muted); font-family:var(--mono); letter-spacing:0.05em; text-transform:uppercase; margin-right:4px; }}
  .filter-pill {{ display:inline-block; padding:3px 10px; border-radius:99px; font-size:0.72rem; font-family:var(--mono); background:rgba(99,102,241,0.15); color:#818cf8; border:1px solid rgba(99,102,241,0.3); }}
  .filter-all  {{ background:rgba(100,116,139,0.15); color:#94a3b8; border-color:rgba(100,116,139,0.3); }}
  .range-badge {{ display:inline-block; padding:4px 12px; border-radius:99px; font-size:0.72rem; font-family:var(--mono); background:rgba(99,102,241,0.15); color:#818cf8; border:1px solid rgba(99,102,241,0.3); margin-bottom:6px; }}
  .badge {{ display:inline-block; padding:4px 10px; border-radius:99px; font-size:0.7rem; font-weight:500; font-family:var(--mono); letter-spacing:0.05em; text-transform:uppercase; }}
  .badge-success {{ background:rgba(16,185,129,0.15); color:var(--success); border:1px solid rgba(16,185,129,0.3); }}
  .badge-danger  {{ background:rgba(239,68,68,0.15);  color:var(--danger);  border:1px solid rgba(239,68,68,0.3); }}
  .badge-warning {{ background:rgba(245,158,11,0.15); color:var(--warning); border:1px solid rgba(245,158,11,0.3); }}

  .kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1rem; margin-bottom:1.5rem; }}
  .kpi {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.25rem 1.5rem; position:relative; overflow:hidden; }}
  .kpi::before {{ content:''; position:absolute; top:0; left:0; right:0; height:2px; }}
  .kpi.total::before   {{ background:var(--accent); }}
  .kpi.success::before {{ background:var(--success); }}
  .kpi.failed::before  {{ background:var(--danger); }}
  .kpi.rate::before    {{ background:{color_gauge}; }}
  .kpi-label {{ font-size:0.72rem; font-weight:500; letter-spacing:0.08em; text-transform:uppercase; color:var(--muted); margin-bottom:0.5rem; }}
  .kpi-value {{ font-size:2.2rem; font-weight:600; font-family:var(--mono); letter-spacing:-0.03em; line-height:1; }}
  .kpi.total   .kpi-value {{ color:#fff; }}
  .kpi.success .kpi-value {{ color:var(--success); }}
  .kpi.failed  .kpi-value {{ color:var(--danger); }}
  .kpi.rate    .kpi-value {{ color:{color_gauge}; }}
  .kpi-sub {{ font-size:0.72rem; color:var(--muted); margin-top:6px; font-family:var(--mono); }}

  .charts-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem; }}
  .chart-card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.25rem 1.5rem; margin-bottom:1rem; }}
  .chart-title {{ font-size:0.78rem; font-weight:500; letter-spacing:0.06em; text-transform:uppercase; color:var(--muted); margin-bottom:1.25rem; }}
  .chart-wrap {{ position:relative; height:220px; }}
  .table-card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.25rem 1.5rem; margin-bottom:1rem; }}
  table {{ width:100%; border-collapse:collapse; }}
  thead th {{ font-size:0.68rem; font-weight:500; letter-spacing:0.1em; text-transform:uppercase; color:var(--muted); padding:0 0.75rem 0.75rem; text-align:left; border-bottom:1px solid var(--border); }}
  tbody tr {{ border-bottom:1px solid var(--border); transition:background 0.15s; }}
  tbody tr:hover {{ background:var(--surface2); }}
  tbody tr:last-child {{ border-bottom:none; }}
  tbody td {{ padding:0.75rem; font-size:0.85rem; font-family:var(--mono); }}
  .failure-table thead th:last-child,
  .failure-table thead th:nth-child(3) {{ text-align:right; }}
  .pct-bar-wrap {{ display:flex; align-items:center; gap:8px; }}
  .pct-bar {{ height:4px; border-radius:2px; flex:1; background:var(--surface2); overflow:hidden; }}
  .pct-bar-fill {{ height:100%; border-radius:2px; }}
  .pct-label {{ font-size:0.78rem; min-width:42px; text-align:right; }}
  .footer {{ text-align:center; font-size:0.72rem; color:var(--muted); font-family:var(--mono); margin-top:1.5rem; padding-top:1rem; border-top:1px solid var(--border); }}
  @media (max-width:900px) {{ .kpi-grid,.charts-grid {{ grid-template-columns:1fr 1fr; }} }}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="header-left">
    <h1>TST Hotel Booking Analytics</h1>
    <p>Generated: {generated_at}</p>
  </div>
  <div class="header-right">
    <div><span class="range-badge">{range_label}</span></div>
    <span class="badge {'badge-danger' if failure_pct > 20 else 'badge-warning' if failure_pct > 5 else 'badge-success'}">
      {'Critical' if failure_pct > 20 else 'Degraded' if failure_pct > 5 else 'Healthy'}
    </span>
  </div>
</div>

<!-- Active Filters -->
<div class="filter-bar">
  <span class="filter-bar-label">Filters:</span>
  {filter_pills}
</div>

<!-- Smart failure logic note -->
<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.2);border-radius:8px;padding:0.6rem 1rem;margin-bottom:1.25rem;font-size:0.75rem;font-family:var(--mono);color:#a5b4fc;line-height:1.6">
  <span style="font-weight:500">Smart failure logic:</span>
  Failures recovered by a successful retry (60s+ later, same session) are excluded.
  Multiple failed attempts with the same error are counted as one failure.
</div>

<!-- KPI Row -->
<div class="kpi-grid" style="grid-template-columns:repeat(6,1fr)">
  <div class="kpi total">
    <div class="kpi-label">Total Bookings</div>
    <div class="kpi-value">{summary['total']:,}</div>
    <div class="kpi-sub">hotel · {range_label.lower()}</div>
  </div>
  <div class="kpi success">
    <div class="kpi-label">Successful</div>
    <div class="kpi-value">{summary['successful']:,}</div>
    <div class="kpi-sub">{summary['success_pct']}% success rate</div>
  </div>
  <div class="kpi failed">
    <div class="kpi-label">Total Failures</div>
    <div class="kpi-value">{summary['failed']:,}</div>
    <div class="kpi-sub">unrecovered failures</div>
  </div>
  <div class="kpi rate">
    <div class="kpi-label">Total Failure Rate</div>
    <div class="kpi-value">{summary['failure_pct']}%</div>
    <div class="kpi-sub">{'↑ needs attention' if failure_pct > 5 else '↓ within normal range'}</div>
  </div>
  <div class="kpi failed">
    <div class="kpi-label">Total CC Failures</div>
    <div class="kpi-value">{summary['cc_failed']:,}</div>
    <div class="kpi-sub">{summary['cc_pct_of_failures']}% of all failures</div>
  </div>
  <div class="kpi rate">
    <div class="kpi-label">Failure Rate (excl. CC)</div>
    <div class="kpi-value">{summary['non_cc_failure_pct']}%</div>
    <div class="kpi-sub">{summary['non_cc_failed']:,} non-CC failures</div>
  </div>
</div>

<!-- Charts Row -->
<div class="charts-grid">
  <div class="chart-card">
    <div class="chart-title">Hourly Trend — Success vs Failed (ET)</div>
    <div class="chart-wrap"><canvas id="hourlyChart"></canvas></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Overall Success vs Failure</div>
    <div class="chart-wrap"><canvas id="donutChart"></canvas></div>
  </div>
</div>

<!-- Adapter Chart -->
<div class="chart-card">
  <div class="chart-title">Bookings by Adapter</div>
  <div class="chart-wrap"><canvas id="adapterChart"></canvas></div>
</div>

<!-- Top 10 Failure Reasons Table -->
<div class="table-card">
  <div class="chart-title">Top 10 Failure Reasons</div>
  <table class="failure-table">
    <thead><tr><th>#</th><th>Failure Reason</th><th>Adapters</th><th>Count</th><th>% of Failures</th></tr></thead>
    <tbody>{failure_rows_html}</tbody>
  </table>
</div>

<!-- Adapter Breakdown Table -->
<div class="table-card">
  <div class="chart-title">Adapter Breakdown</div>
  <table>
    <thead><tr><th>Adapter</th><th>Total</th><th>Successful</th><th>Failed</th><th>Failure Rate</th></tr></thead>
    <tbody>{adapter_rows_html}</tbody>
  </table>
</div>

<!-- Licensee Breakdown Table (only when not filtered) -->
{licensee_section_html}

<div class="footer">
  TST Hotel Booking Analytics &nbsp;·&nbsp; product_type=hotel &nbsp;·&nbsp;
  Times shown in ET
</div>

<script>
const C = {{ success:'#10b981', failed:'#ef4444', accent:'#6366f1', text:'#94a3b8' }};
Chart.defaults.color = C.text;
Chart.defaults.font.family = "'DM Mono', monospace";
Chart.defaults.font.size = 11;

new Chart(document.getElementById('hourlyChart'), {{
  type:'bar',
  data:{{
    labels:{json.dumps(hourly_labels)},
    datasets:[
      {{label:'Successful',data:{json.dumps(hourly_success)},backgroundColor:'rgba(16,185,129,0.7)',borderRadius:3,stack:'s'}},
      {{label:'Failed',    data:{json.dumps(hourly_failed)}, backgroundColor:'rgba(239,68,68,0.7)', borderRadius:3,stack:'s'}}
    ]
  }},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'top',labels:{{boxWidth:10,padding:12}}}}}},
    scales:{{
      x:{{grid:{{color:'rgba(255,255,255,0.04)'}},ticks:{{maxRotation:45}}}},
      y:{{grid:{{color:'rgba(255,255,255,0.04)'}},beginAtZero:true}}
    }}
  }}
}});

new Chart(document.getElementById('donutChart'), {{
  type:'doughnut',
  data:{{
    labels:['Successful','Failed'],
    datasets:[{{
      data:[{summary['successful']},{summary['failed']}],
      backgroundColor:['rgba(16,185,129,0.8)','rgba(239,68,68,0.8)'],
      borderColor:['#10b981','#ef4444'],borderWidth:1,hoverOffset:6
    }}]
  }},
  options:{{responsive:true,maintainAspectRatio:false,cutout:'72%',
    plugins:{{
      legend:{{position:'bottom',labels:{{padding:16,boxWidth:10}}}},
      tooltip:{{callbacks:{{label:(ctx)=>` ${{ctx.label}}: ${{ctx.parsed.toLocaleString()}} (${{((ctx.parsed/{summary['total']})*100).toFixed(1)}}%)`}}}}
    }}
  }}
}});

new Chart(document.getElementById('adapterChart'), {{
  type:'bar',
  data:{{
    labels:{json.dumps(adapter_labels)},
    datasets:[
      {{label:'Successful',data:{json.dumps(adapter_success)},backgroundColor:'rgba(16,185,129,0.7)',borderRadius:4}},
      {{label:'Failed',    data:{json.dumps(adapter_failed)}, backgroundColor:'rgba(239,68,68,0.7)', borderRadius:4}}
    ]
  }},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'top',labels:{{boxWidth:10,padding:12}}}}}},
    scales:{{
      x:{{grid:{{color:'rgba(255,255,255,0.04)'}}}},
      y:{{grid:{{color:'rgba(255,255,255,0.04)'}},beginAtZero:true}}
    }}
  }}
}});
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  default="/tmp/booking_analytics.json")
    parser.add_argument("--output", default="/tmp/booking_dashboard.html")
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    html = generate_html(data)

    with open(args.output, "w") as f:
        f.write(html)

    print(f"Dashboard saved to: {args.output}")
    print(f"Open in browser:    open {args.output}")


if __name__ == "__main__":
    main()
