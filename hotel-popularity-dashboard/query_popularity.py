#!/usr/bin/env python3
"""
Query popular hotels with no recent bookings from MySQL database.
"""

import os
import sys
import json
import argparse
from datetime import datetime
import mysql.connector
from mysql.connector import Error


def get_db_connection():
    """Create database connection using environment variables."""
    try:
        connection = mysql.connector.connect(
            host=os.environ.get('TST_DB_HOST'),
            user=os.environ.get('TST_DB_USER'),
            password=os.environ.get('TST_DB_PASSWORD'),
            database='book'  # Start with book database
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}", file=sys.stderr)
        sys.exit(1)


def query_inactive_popular_hotels(min_weighting=50, months_inactive=2):
    """
    Query hotels with high popularity but no recent bookings.
    
    Args:
        min_weighting: Minimum weighting threshold (default: 50)
        months_inactive: Months without bookings (default: 2)
    
    Returns:
        List of dictionaries containing hotel data
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    query = f"""
        SELECT 
            hp.hotel_id,
            hb.hotel_name,
            hb.hotel_address_city,
            hb.hotel_address_country_code,
            MAX(tb.create_date) as last_booking_date,
            hp.weighting
        FROM TST.HOTEL_POPULARITY hp
        INNER JOIN book.HOTEL_BOOKING_V2 hb ON hp.hotel_id = hb.hotel_id
        INNER JOIN book.TRAVEL_BOOKING tb ON hb.travel_booking_id = tb.id
        WHERE hp.weighting >= %s
          AND tb.product_type = 'hotel'
        GROUP BY hp.hotel_id, hb.hotel_name, hb.hotel_address_city, 
                 hb.hotel_address_country_code, hp.weighting
        HAVING MAX(tb.create_date) < DATE_SUB(NOW(), INTERVAL %s MONTH)
        ORDER BY last_booking_date ASC, hp.weighting DESC
    """
    
    try:
        cursor.execute(query, (min_weighting, months_inactive))
        results = cursor.fetchall()
        
        # Convert datetime objects to strings for JSON serialization
        for row in results:
            if row['last_booking_date']:
                row['last_booking_date'] = row['last_booking_date'].strftime('%Y-%m-%d %H:%M:%S')
        
        return results
    except Error as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cursor.close()
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description='Query popular hotels with no recent bookings'
    )
    parser.add_argument(
        '--min-weighting',
        type=int,
        default=50,
        help='Minimum popularity weighting threshold (default: 50)'
    )
    parser.add_argument(
        '--months-inactive',
        type=int,
        default=2,
        help='Months without bookings (default: 2)'
    )
    parser.add_argument(
        '--output',
        default='data.json',
        help='Output JSON file (default: data.json)'
    )
    
    args = parser.parse_args()
    
    # Validate environment variables
    required_vars = ['TST_DB_HOST', 'TST_DB_USER', 'TST_DB_PASSWORD']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}", 
              file=sys.stderr)
        sys.exit(1)
    
    # Query data
    print(f"Querying popular hotels (weighting >= {args.min_weighting}) "
          f"with no bookings in the past {args.months_inactive} months...")
    
    results = query_inactive_popular_hotels(
        min_weighting=args.min_weighting,
        months_inactive=args.months_inactive
    )
    
    # Prepare output data
    output_data = {
        'query_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'parameters': {
            'min_weighting': args.min_weighting,
            'months_inactive': args.months_inactive
        },
        'total_count': len(results),
        'hotels': results
    }
    
    # Write to JSON file
    with open(args.output, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Found {len(results)} inactive popular hotels")
    print(f"Results written to {args.output}")


if __name__ == '__main__':
    main()
