# Hotel Popularity Dashboard

Dashboard to monitor popular hotels that haven't received bookings recently.

## Overview

This dashboard identifies hotels with high popularity (based on booking weighting) that haven't received any bookings in a specified time period. This helps detect potential issues with popular hotels.

## Files

- `query_popularity.py` - Queries MySQL database for inactive popular hotels
- `generate_popularity_dashboard.py` - Generates HTML dashboard from query results
- `refresh_popularity_dashboard.sh` - Automation script to update the dashboard
- `data.json` - Query results (generated)
- `index.html` - Dashboard HTML (generated)

## Database Schema

### TST Database
- `HOTEL_POPULARITY` table
  - `hotel_id` - Hotel identifier
  - `weighting` - Booking popularity score (increments with each booking)

### book Database
- `TRAVEL_BOOKING` table
  - `id` - Booking ID
  - `create_date` - Booking creation timestamp
  - `product_type` - Product type (filter for 'hotel')

- `HOTEL_BOOKING_V2` table
  - `travel_booking_id` - FK to TRAVEL_BOOKING.id
  - `hotel_id` - Hotel identifier
  - `hotel_name` - Hotel name
  - `hotel_address_city` - Hotel city
  - `hotel_address_country_code` - Hotel country code

## Setup

### Environment Variables

Required environment variables (same as booking dashboard):

```bash
export TST_DB_HOST="your-mysql-host"
export TST_DB_USER="your-mysql-user"
export TST_DB_PASSWORD="your-mysql-password"
```

Note: TST_DB_NAME is not needed as we query both `TST` and `book` databases.

### Python Dependencies

```bash
pip install mysql-connector-python --break-system-packages
```

## Usage

### Manual Query

```bash
# Query with defaults (weighting >= 50, inactive for 2 months)
python3 query_popularity.py

# Custom thresholds
python3 query_popularity.py --min-weighting 100 --months-inactive 3

# Custom output file
python3 query_popularity.py --output custom_data.json
```

### Generate Dashboard

```bash
# Generate from data.json (default)
python3 generate_popularity_dashboard.py

# Custom input/output
python3 generate_popularity_dashboard.py --input custom_data.json --output custom.html
```

### Automated Refresh

```bash
# Run with defaults
./refresh_popularity_dashboard.sh

# Run with custom thresholds via environment variables
MIN_WEIGHTING=100 MONTHS_INACTIVE=3 ./refresh_popularity_dashboard.sh
```

## Dashboard Features

- **Summary Stats**: Total count of affected hotels
- **Hotel Table**: 
  - Hotel ID
  - Hotel Name
  - City
  - Country Code
  - Last Booking Date (with days ago)
  - Weighting (popularity score)
- **Sorting**: Hotels sorted by last booking date (oldest first) and weighting (highest first)
- **Visual Indicators**: Dates older than 60 days highlighted in red

## GitHub Pages Deployment

To publish this dashboard to GitHub Pages:

1. Create a new repository: `hotel-popularity-dashboard`
2. Initialize git in the dashboard directory:
   ```bash
   cd /home/claude/myExperements/hotel-popularity-dashboard
   git init
   git remote add origin https://github.com/jaykakkassery/hotel-popularity-dashboard.git
   ```
3. Push to GitHub:
   ```bash
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git push -u origin main
   ```
4. Enable GitHub Pages:
   - Go to repository Settings → Pages
   - Source: Deploy from branch `main`, root directory
   - Dashboard will be available at: `https://jaykakkassery.github.io/hotel-popularity-dashboard/`

## Automation with Cron

To run the dashboard refresh automatically:

```bash
# Edit crontab
crontab -e

# Add line to run daily at 6 AM
0 6 * * * cd /home/claude/myExperements/hotel-popularity-dashboard && ./refresh_popularity_dashboard.sh >> refresh.log 2>&1
```

## Troubleshooting

### No data returned
- Check database connections (TST_DB_HOST, TST_DB_USER, TST_DB_PASSWORD)
- Verify table names and schemas match
- Try lowering --min-weighting threshold
- Try increasing --months-inactive period

### MySQL errors
- Ensure both `TST` and `book` databases are accessible
- Verify cross-database query permissions
- Check that HOTEL_BOOKING_V2 has the required columns

### Empty dashboard
This is normal if no popular hotels are inactive — it means all popular hotels are receiving bookings regularly.
