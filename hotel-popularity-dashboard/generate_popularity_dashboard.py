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
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        }

        .header h1 {
            color: #2d3748;
            font-size: 32px;
            margin-bottom: 10px;
        }

        .header .subtitle {
            color: #718096;
            font-size: 16px;
            margin-bottom: 20px;
        }

        .meta-info {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
            font-size: 14px;
            color: #4a5568;
        }

        .meta-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .meta-label {
            font-weight: 600;
            color: #2d3748;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        }

        .stat-label {
            color: #718096;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
        }

        .stat-value {
            color: #2d3748;
            font-size: 36px;
            font-weight: 700;
        }

        .stat-unit {
            color: #718096;
            font-size: 16px;
            margin-left: 5px;
        }

        .table-container {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            overflow-x: auto;
        }

        .table-header {
            margin-bottom: 20px;
        }

        .table-header h2 {
            color: #2d3748;
            font-size: 24px;
            margin-bottom: 5px;
        }

        .table-header .count {
            color: #718096;
            font-size: 14px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        thead {
            background: #f7fafc;
            position: sticky;
            top: 0;
        }

        th {
            text-align: left;
            padding: 15px;
            color: #2d3748;
            font-weight: 600;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #e2e8f0;
        }

        td {
            padding: 15px;
            color: #4a5568;
            font-size: 14px;
            border-bottom: 1px solid #e2e8f0;
        }

        tbody tr:hover {
            background: #f7fafc;
        }

        .hotel-id {
            font-family: 'Courier New', monospace;
            background: #edf2f7;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 13px;
        }

        .hotel-name {
            font-weight: 600;
            color: #2d3748;
        }

        .location {
            color: #718096;
        }

        .country-code {
            background: #667eea;
            color: white;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }

        .date {
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }

        .date-old {
            color: #e53e3e;
            font-weight: 600;
        }

        .weighting {
            font-weight: 700;
            color: #667eea;
            font-size: 16px;
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #718096;
        }

        .empty-state-icon {
            font-size: 64px;
            margin-bottom: 20px;
        }

        .empty-state-title {
            font-size: 24px;
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 10px;
        }

        .empty-state-text {
            font-size: 16px;
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 24px;
            }

            .stat-value {
                font-size: 28px;
            }

            .table-container {
                padding: 20px;
            }

            th, td {
                padding: 10px;
                font-size: 13px;
            }
        }
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
        </div>

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
        
        rows_html.append(f"""
            <tr>
                <td><span class="hotel-id">{hotel['hotel_id']}</span></td>
                <td><span class="hotel-name">{hotel['hotel_name'] or 'N/A'}</span></td>
                <td><span class="location">{hotel['hotel_address_city'] or 'N/A'}</span></td>
                <td><span class="country-code">{hotel['hotel_address_country_code'] or 'N/A'}</span></td>
                <td><span class="date {date_class}">{hotel['last_booking_date']}</span><br><small style="color: #a0aec0;">({days_ago} days ago)</small></td>
                <td><span class="weighting">{hotel['weighting']}</span></td>
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
    table_content = generate_table_html(data['hotels'])
    
    html = HTML_TEMPLATE.format(
        query_timestamp=data['query_timestamp'],
        min_weighting=data['parameters']['min_weighting'],
        months_inactive=data['parameters']['months_inactive'],
        total_count=data['total_count'],
        table_content=table_content
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
