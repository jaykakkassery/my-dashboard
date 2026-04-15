#!/usr/bin/env python3
"""
Generate HTML dashboard for popular hotels with no recent bookings.
"""

import json
import argparse
from datetime import datetime


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Popular Hotels - No Recent Bookings</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1d29 0%, #2d3142 100%);
            min-height: 100vh;
            padding: 20px;
            color: #e8eaed;
        }}

        .container {{
            max-width: 1800px;
            margin: 0 auto;
        }}

        .header {{
            background: linear-gradient(135deg, #2d3142 0%, #1a1d29 100%);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            border: 2px solid #4a90e2;
        }}

        .header h1 {{
            color: #4a90e2;
            font-size: 32px;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
            font-weight: 300;
            letter-spacing: 1px;
        }}

        .header .subtitle {{
            color: #b0b4ba;
            font-size: 16px;
            margin-bottom: 20px;
            font-weight: 300;
        }}

        .meta-info {{
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
            font-size: 14px;
            color: #8a8f98;
        }}

        .meta-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .meta-label {{
            font-weight: 500;
            color: #4a90e2;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #2d3142 0%, #1a1d29 100%);
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            border: 1px solid #4a90e2;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 15px 40px rgba(74, 144, 226, 0.3);
        }}

        .stat-label {{
            color: #8a8f98;
            font-size: 14px;
            font-weight: 400;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .stat-value {{
            color: #4a90e2;
            font-size: 36px;
            font-weight: 300;
            letter-spacing: -1px;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .chart-card {{
            background: linear-gradient(135deg, #2d3142 0%, #1a1d29 100%);
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            border: 1px solid #4a90e2;
        }}

        .chart-title {{
            color: #4a90e2;
            font-size: 18px;
            font-weight: 400;
            margin-bottom: 20px;
            letter-spacing: 0.5px;
        }}

        .table-container {{
            background: linear-gradient(135deg, #2d3142 0%, #1a1d29 100%);
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            overflow-x: auto;
            border: 1px solid #4a90e2;
        }}

        .table-header {{
            margin-bottom: 20px;
        }}

        .table-header h2 {{
            color: #4a90e2;
            font-size: 24px;
            margin-bottom: 5px;
            font-weight: 300;
            letter-spacing: 1px;
        }}

        .table-header .count {{
            color: #8a8f98;
            font-size: 14px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        thead {{
            background: #1a1d29;
            position: sticky;
            top: 0;
        }}

        th {{
            text-align: left;
            padding: 15px;
            color: #4a90e2;
            font-weight: 500;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 2px solid #4a90e2;
        }}

        td {{
            padding: 15px;
            color: #b0b4ba;
            font-size: 14px;
            border-bottom: 1px solid #3a3d4a;
        }}

        tbody tr {{
            transition: background 0.2s;
        }}

        tbody tr:hover {{
            background: #3a3d4a;
        }}

        .hotel-id {{
            font-family: 'Courier New', monospace;
            background: #3a3d4a;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 13px;
            color: #6ba3e8;
        }}

        .hotel-name {{
            font-weight: 500;
            color: #e8eaed;
        }}

        .location {{
            color: #8a8f98;
        }}

        .country-code {{
            background: #4a90e2;
            color: white;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}

        .date {{
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #b0b4ba;
        }}

        .date-old {{
            color: #e74c3c;
            font-weight: 600;
        }}

        .weighting {{
            font-weight: 500;
            color: #4a90e2;
            font-size: 16px;
        }}

        .count-match {{
            color: #4caf50;
        }}

        .count-mismatch {{
            color: #e74c3c;
            font-weight: 600;
        }}

        .reason {{
            font-size: 13px;
            color: #ffa726;
            font-style: italic;
            max-width: 300px;
        }}

        .reason-empty {{
            color: #5a5d6a;
        }}

        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #8a8f98;
        }}

        .empty-state-icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}

        .empty-state-title {{
            font-size: 24px;
            font-weight: 400;
            color: #4caf50;
            margin-bottom: 10px;
        }}

        .empty-state-text {{
            font-size: 16px;
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 24px;
            }}

            .stat-value {{
                font-size: 28px;
            }}

            .table-container {{
                padding: 20px;
            }}

            th, td {{
                padding: 10px;
                font-size: 13px;
            }}

            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏨 Popular Hotels - No Recent Bookings</h1>
            <div class="subtitle">Hotels with high popularity that haven't received bookings recently</div>
            <div class="meta-info">
                <div class="meta-item">
                    <span class="meta-label">Last Updated:</span>
                    <span>{query_timestamp}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Min Weighting:</span>
                    <span>{min_weighting}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Inactive Period:</span>
                    <span>{months_inactive} months</span>
                </div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Hotels Affected</div>
                <div class="stat-value">{total_count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Popularity Weighting</div>
                <div class="stat-value">{total_weighting}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Actual Bookings</div>
                <div class="stat-value">{total_bookings}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Data Discrepancies</div>
                <div class="stat-value">{discrepancy_count}</div>
            </div>
        </div>

        {charts_html}

        <div class="table-container">
            <div class="table-header">
                <h2>Inactive Popular Hotels</h2>
                <div class="count">{total_count} hotels found</div>
            </div>

            {table_content}
        </div>
    </div>
</body>
</html>
"""


def format_days_ago(last_booking_date):
    """Calculate days since last booking."""
    try:
        last_date = datetime.strptime(last_booking_date, '%Y-%m-%d %H:%M:%S')
        days_ago = (datetime.now() - last_date).days
        return days_ago
    except:
        return 0


def generate_charts_html(hotels):
    """Generate charts HTML with Chart.js."""
    if not hotels or len(hotels) == 0:
        return ""
    
    # Top 10 hotels by weighting
    top_hotels = sorted(hotels, key=lambda x: x['weighting'], reverse=True)[:10]
    hotel_names = [h['hotel_name'][:30] + '...' if h['hotel_name'] and len(h['hotel_name']) > 30 else (h['hotel_name'] or 'N/A') for h in top_hotels]
    weightings = [h['weighting'] for h in top_hotels]
    
    # Weighting vs Actual Bookings for top 10
    actual_counts = [h.get('actual_booking_count', 0) for h in top_hotels]
    
    charts_html = """
        <div class="charts-grid">
            <div class="chart-card">
                <div class="chart-title">Top 10 Hotels by Popularity Weighting</div>
                <canvas id="weightingChart"></canvas>
            </div>
            <div class="chart-card">
                <div class="chart-title">Weighting vs Actual Bookings (Top 10)</div>
                <canvas id="comparisonChart"></canvas>
            </div>
        </div>
        <script>
            // Weighting Chart
            const ctx1 = document.getElementById('weightingChart').getContext('2d');
            new Chart(ctx1, {{
                type: 'bar',
                data: {{
                    labels: {hotel_labels},
                    datasets: [{{
                        label: 'Popularity Weighting',
                        data: {weighting_data},
                        backgroundColor: 'rgba(74, 144, 226, 0.8)',
                        borderColor: '#4a90e2',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ color: '#b0b4ba' }},
                            grid: {{ color: '#3a3d4a' }}
                        }},
                        x: {{
                            ticks: {{ color: '#b0b4ba', maxRotation: 45, minRotation: 45 }},
                            grid: {{ color: '#3a3d4a' }}
                        }}
                    }},
                    plugins: {{
                        legend: {{ labels: {{ color: '#b0b4ba' }} }}
                    }}
                }}
            }});

            // Comparison Chart
            const ctx2 = document.getElementById('comparisonChart').getContext('2d');
            new Chart(ctx2, {{
                type: 'bar',
                data: {{
                    labels: {hotel_labels},
                    datasets: [
                        {{
                            label: 'Popularity Weighting',
                            data: {weighting_data},
                            backgroundColor: 'rgba(74, 144, 226, 0.8)',
                            borderColor: '#4a90e2',
                            borderWidth: 1
                        }},
                        {{
                            label: 'Actual Bookings',
                            data: {actual_data},
                            backgroundColor: 'rgba(76, 175, 80, 0.8)',
                            borderColor: '#4caf50',
                            borderWidth: 1
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ color: '#b0b4ba' }},
                            grid: {{ color: '#3a3d4a' }}
                        }},
                        x: {{
                            ticks: {{ color: '#b0b4ba', maxRotation: 45, minRotation: 45 }},
                            grid: {{ color: '#3a3d4a' }}
                        }}
                    }},
                    plugins: {{
                        legend: {{ labels: {{ color: '#b0b4ba' }} }}
                    }}
                }}
            }});
        </script>
    """.format(
        hotel_labels=json.dumps(hotel_names),
        weighting_data=json.dumps(weightings),
        actual_data=json.dumps(actual_counts)
    )
    
    return charts_html


def generate_table_html(hotels):
    """Generate HTML table from hotel data."""
    if not hotels:
        return """
            <div class="empty-state">
                <div class="empty-state-icon">✅</div>
                <div class="empty-state-title">All Good!</div>
                <div class="empty-state-text">No popular hotels with missing bookings found.</div>
            </div>
        """
    
    rows_html = []
    for hotel in hotels:
        days_ago = format_days_ago(hotel['last_booking_date'])
        date_class = 'date-old' if days_ago > 60 else ''
        
        # Check if weighting matches actual booking count
        actual_count = hotel.get('actual_booking_count', 0)
        weighting = hotel['weighting']
        count_class = 'count-match' if actual_count == weighting else 'count-mismatch'
        
        # Get possible reason
        reason = hotel.get('possible_reason', '')
        reason_display = reason if reason else '<span class="reason-empty">-</span>'
        reason_class = 'reason' if reason else ''
        
        rows_html.append(f"""
            <tr>
                <td><span class="hotel-id">{hotel['hotel_id']}</span></td>
                <td><span class="hotel-name">{hotel['hotel_name'] or 'N/A'}</span></td>
                <td><span class="location">{hotel['hotel_address_city'] or 'N/A'}</span></td>
                <td><span class="country-code">{hotel['hotel_address_country_code'] or 'N/A'}</span></td>
                <td><span class="date {date_class}">{hotel['last_booking_date']}</span><br><small style="color: #8a8f98;">({days_ago} days ago)</small></td>
                <td><span class="weighting">{weighting}</span></td>
                <td><span class="{count_class}">{actual_count}</span></td>
                <td><span class="{reason_class}">{reason_display}</span></td>
            </tr>
        """)
    
    table_html = f"""
        <table>
            <thead>
                <tr>
                    <th>Hotel ID</th>
                    <th>Hotel Name</th>
                    <th>City</th>
                    <th>Country</th>
                    <th>Last Booking Date</th>
                    <th>Weighting</th>
                    <th>Actual Count</th>
                    <th>Possible Reason</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
    """
    
    return table_html


def generate_dashboard(data, output_file='index.html'):
    """Generate HTML dashboard from data."""
    # Calculate stats
    total_weighting = sum(h['weighting'] for h in data['hotels'])
    total_bookings = sum(h.get('actual_booking_count', 0) for h in data['hotels'])
    discrepancy_count = sum(1 for h in data['hotels'] if h['weighting'] != h.get('actual_booking_count', 0))
    
    table_content = generate_table_html(data['hotels'])
    charts_html = generate_charts_html(data['hotels'])
    
    html = HTML_TEMPLATE.format(
        query_timestamp=data['query_timestamp'],
        min_weighting=data['parameters']['min_weighting'],
        months_inactive=data['parameters']['months_inactive'],
        total_count=data['total_count'],
        total_weighting=total_weighting,
        total_bookings=total_bookings,
        discrepancy_count=discrepancy_count,
        table_content=table_content,
        charts_html=charts_html
    )
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"Dashboard generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate HTML dashboard for popular hotels with no recent bookings'
    )
    parser.add_argument(
        '--input',
        default='data.json',
        help='Input JSON file (default: data.json)'
    )
    parser.add_argument(
        '--output',
        default='index.html',
        help='Output HTML file (default: index.html)'
    )
    
    args = parser.parse_args()
    
    # Load data
    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found")
        return
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in '{args.input}'")
        return
    
    # Generate dashboard
    generate_dashboard(data, args.output)


if __name__ == '__main__':
    main()
