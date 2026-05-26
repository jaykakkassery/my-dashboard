#!/usr/bin/env python3
"""
Research top inactive hotels using OpenAI API and update the dashboard with findings.
"""

import json
import sys
import argparse
import time
import os
from openai import OpenAI


def research_hotel(client, hotel_name, city, country_code, hotel_id):
    """
    Research a specific hotel to find out why it stopped receiving bookings.
    Returns a brief summary or empty string if nothing found.
    """
    if not hotel_name or hotel_name == 'N/A':
        return ""
    
    search_prompt = f"""Search the web for information about '{hotel_name}' located in {city}, {country_code}. 

Has this hotel:
- Closed permanently?
- Been renovated or under construction?
- Rebranded or renamed?
- Changed ownership?

Provide a very brief 1-2 sentence summary if you find anything relevant. If you find nothing, respond with exactly: "No information found"

Be concise and factual."""
    
    try:
        # Use GPT-3.5-turbo (cheapest option)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful research assistant. Provide brief, factual summaries."},
                {"role": "user", "content": search_prompt}
            ],
            max_tokens=150,
            temperature=0.3
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean up response
        if "No information found" in response_text or not response_text:
            return ""
        
        # Keep only first 150 characters for brevity
        summary = response_text[:150]
        if len(response_text) > 150:
            summary += "..."
        
        return summary
        
    except Exception as e:
        print(f"Error researching {hotel_name}: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser(
        description='Research top inactive hotels and update dashboard'
    )
    parser.add_argument(
        '--input',
        default='data.json',
        help='Input JSON file (default: data.json)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=50,
        help='Number of top hotels to research (default: 50)'
    )
    parser.add_argument(
        '--api-key',
        help='OpenAI API key (or use OPENAI_API_KEY env var)'
    )
    
    args = parser.parse_args()
    
    # Load data
    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found")
        sys.exit(1)
    
    hotels = data.get('hotels', [])
    if not hotels:
        print("No hotels found in data file")
        return
    
    # Get API key
    api_key = args.api_key or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("Error: OpenAI API key required. Set OPENAI_API_KEY env var or use --api-key")
        sys.exit(1)
    
    client = OpenAI(api_key=api_key)
    
    # Research top N hotels
    top_hotels = hotels[:args.top_n]
    print(f"Researching top {len(top_hotels)} hotels by weighting...")
    print("This may take several minutes...")
    print()
    
    for i, hotel in enumerate(top_hotels):
        hotel_name = hotel.get('hotel_name', 'N/A')
        city = hotel.get('hotel_address_city', '')
        country = hotel.get('hotel_address_country_code', '')
        hotel_id = hotel.get('hotel_id', '')
        
        print(f"[{i+1}/{len(top_hotels)}] Researching: {hotel_name} ({city}, {country})")
        
        reason = research_hotel(client, hotel_name, city, country, hotel_id)
        hotel['possible_reason'] = reason
        
        if reason:
            print(f"  → Found: {reason}")
        else:
            print(f"  → No information found")
        
        # Rate limiting - wait 2 seconds between requests
        if i < len(top_hotels) - 1:
            time.sleep(2)
    
    # Save updated data
    with open(args.input, 'w') as f:
        json.dump(data, f, indent=2)
    
    print()
    print(f"Research complete! Updated {args.input}")
    print("Now regenerate the dashboard with: python3 generate_popularity_dashboard.py")


if __name__ == '__main__':
    main()
