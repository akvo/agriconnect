#!/usr/bin/env python
"""
Weather API Comparison Script for Murang'a Districts.

Compares weather data from:
- OpenWeatherMap API
- Google Weather API

Usage:
    python compare_weather_apis.py                    # Current conditions, all wards
    python compare_weather_apis.py --limit=10         # Current conditions, 10 wards
    python compare_weather_apis.py --days=5           # 5-day forecast, all wards
    python compare_weather_apis.py --days=3 --limit=5 # 3-day forecast, 5 wards

Output:
    Current:  <datetime>-muranga.csv
    Forecast: <datetime>-muranga-forecast-<days>d.csv
"""

import argparse
import csv
import os
import requests
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Load environment variables
script_dir = Path(__file__).parent
env_file = script_dir.parent.parent.parent / ".env"
load_dotenv(env_file)

# API Keys
OPENWEATHER_KEY = os.getenv("OPENWEATHER")
GOOGLE_WEATHER_KEY = os.getenv("GOOGLE_WEATHER_API_KEY")

# Administrative data path
ADMIN_CSV = script_dir.parent.parent.parent / "backend" / "source" / "administrative.csv"


def load_muranga_wards(limit: int | None = None) -> list[dict]:
    """Load wards from Murang'a region with coordinates.

    Args:
        limit: Maximum number of wards to load. None means all wards.
    """
    wards = []
    with open(ADMIN_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Only wards in Murang'a (MUR prefix) with coordinates
            if (
                row["code"].startswith("MUR-")
                and row["level"] == "ward"
                and row["longitude"]
                and row["latitude"]
            ):
                wards.append({
                    "code": row["code"],
                    "name": row["name"],
                    "lon": float(row["longitude"]),
                    "lat": float(row["latitude"]),
                })
                if limit and len(wards) >= limit:
                    break
    return wards


def get_openweather_data(lat: float, lon: float) -> dict:
    """Get weather data from OpenWeatherMap API 2.5."""
    if not OPENWEATHER_KEY:
        return {"condition": "API key missing", "rain_mm": None}

    try:
        from weather.services import OpenWeatherMapService
        service = OpenWeatherMapService()
        # Use forecast endpoint with coordinates
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code != 200:
            return {"condition": f"Error: {data.get('message', 'Unknown')}", "rain_mm": None}

        # Get first forecast entry (current/nearest)
        if data.get("list"):
            entry = data["list"][0]
            condition = entry.get("weather", [{}])[0].get("description", "Unknown")
            rain_3h = entry.get("rain", {}).get("3h", 0)
            return {"condition": condition.title(), "rain_mm": rain_3h}

        return {"condition": "No data", "rain_mm": None}
    except ImportError:
        # Fallback to direct API call without library
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/forecast"
                f"?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
            )
            response = requests.get(url, timeout=10)
            data = response.json()

            if response.status_code != 200:
                return {"condition": f"Error: {data.get('message', 'Unknown')}", "rain_mm": None}

            if data.get("list"):
                entry = data["list"][0]
                condition = entry.get("weather", [{}])[0].get("description", "Unknown")
                rain_3h = entry.get("rain", {}).get("3h", 0)
                return {"condition": condition.title(), "rain_mm": rain_3h}

            return {"condition": "No data", "rain_mm": None}
        except Exception as e:
            return {"condition": f"Error: {str(e)}", "rain_mm": None}
    except Exception as e:
        return {"condition": f"Error: {str(e)}", "rain_mm": None}


def get_google_weather_data(lat: float, lon: float) -> dict:
    """Get weather data from Google Weather API."""
    if not GOOGLE_WEATHER_KEY:
        return {"condition": "API key missing", "rain_mm": None}

    try:
        url = (
            f"https://weather.googleapis.com/v1/currentConditions:lookup"
            f"?key={GOOGLE_WEATHER_KEY}"
            f"&location.latitude={lat}&location.longitude={lon}"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code != 200:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            return {"condition": f"Error: {error_msg}", "rain_mm": None}

        # Extract condition and precipitation
        condition = (
            data.get("weatherCondition", {})
            .get("description", {})
            .get("text", "Unknown")
        )
        precip = data.get("precipitation", {}).get("qpf", {}).get("quantity", 0)

        return {"condition": condition, "rain_mm": round(precip, 2) if precip else 0}
    except Exception as e:
        return {"condition": f"Error: {str(e)}", "rain_mm": None}


def get_openweather_forecast(lat: float, lon: float, days: int) -> list[dict]:
    """Get multi-day forecast from OpenWeatherMap API."""
    if not OPENWEATHER_KEY:
        return [{"date": "N/A", "condition": "API key missing", "rain_mm": None}]

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code != 200:
            return [{
                "date": "N/A",
                "condition": f"Error: {data.get('message', 'Unknown')}",
                "rain_mm": None
            }]

        # Group by date and get daily summary (noon forecast)
        daily_forecasts = {}
        for entry in data.get("list", []):
            dt = datetime.fromtimestamp(entry["dt"])
            date_str = dt.strftime("%Y-%m-%d")

            if date_str not in daily_forecasts:
                # Use first entry of the day as representative
                condition = entry.get("weather", [{}])[0].get("description", "Unknown")
                rain_3h = entry.get("rain", {}).get("3h", 0)
                daily_forecasts[date_str] = {
                    "date": date_str,
                    "condition": condition.title(),
                    "rain_mm": rain_3h,
                }

            if len(daily_forecasts) >= days:
                break

        return list(daily_forecasts.values())[:days]
    except Exception as e:
        return [{"date": "N/A", "condition": f"Error: {str(e)}", "rain_mm": None}]


def get_google_weather_forecast(lat: float, lon: float, days: int) -> list[dict]:
    """Get multi-day forecast from Google Weather API."""
    if not GOOGLE_WEATHER_KEY:
        return [{"date": "N/A", "condition": "API key missing", "rain_mm": None}]

    try:
        url = (
            f"https://weather.googleapis.com/v1/forecast/days:lookup"
            f"?key={GOOGLE_WEATHER_KEY}"
            f"&location.latitude={lat}&location.longitude={lon}"
            f"&days={days}"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code != 200:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            return [{
                "date": "N/A",
                "condition": f"Error: {error_msg}",
                "rain_mm": None
            }]

        forecasts = []
        for day_forecast in data.get("forecastDays", [])[:days]:
            # Get date from interval
            interval = day_forecast.get("interval", {})
            start_time = interval.get("startTime", "")
            date_str = start_time[:10] if start_time else "N/A"

            # Get day condition
            day_part = day_forecast.get("daytimeForecast", {})
            condition = (
                day_part.get("weatherCondition", {})
                .get("description", {})
                .get("text", "Unknown")
            )

            # Get precipitation
            precip = (
                day_part.get("precipitation", {})
                .get("qpf", {})
                .get("quantity", 0)
            )

            forecasts.append({
                "date": date_str,
                "condition": condition,
                "rain_mm": round(precip, 2) if precip else 0,
            })

        return forecasts
    except Exception as e:
        return [{"date": "N/A", "condition": f"Error: {str(e)}", "rain_mm": None}]


def run_current_conditions(wards: list[dict]) -> pd.DataFrame:
    """Run current conditions comparison."""
    results = []
    for ward in wards:
        print(f"Fetching data for {ward['name']}...")

        owm = get_openweather_data(ward["lat"], ward["lon"])
        google = get_google_weather_data(ward["lat"], ward["lon"])

        results.append({
            "Location": ward["name"],
            "OWM_Condition": owm["condition"],
            "OWM_Rain_MM": owm["rain_mm"],
            "Google_Condition": google["condition"],
            "Google_Rain_MM": google["rain_mm"],
        })

    return pd.DataFrame(results)


def format_date_with_day(date_str: str) -> str:
    """Format date string to include day name (e.g., '2024-03-16 (Saturday)')."""
    if date_str == "N/A":
        return date_str
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{date_str} ({dt.strftime('%A')})"
    except ValueError:
        return date_str


def run_forecast(wards: list[dict], days: int) -> pd.DataFrame:
    """Run multi-day forecast comparison."""
    results = []
    for ward in wards:
        print(f"Fetching {days}-day forecast for {ward['name']}...")

        owm_forecast = get_openweather_forecast(ward["lat"], ward["lon"], days)
        google_forecast = get_google_weather_forecast(ward["lat"], ward["lon"], days)

        for i in range(days):
            owm = owm_forecast[i] if i < len(owm_forecast) else {
                "date": "N/A", "condition": "No data", "rain_mm": None
            }
            google = google_forecast[i] if i < len(google_forecast) else {
                "date": "N/A", "condition": "No data", "rain_mm": None
            }

            date_str = owm.get("date", google.get("date", "N/A"))
            results.append({
                "Location": ward["name"],
                "Date": format_date_with_day(date_str),
                "_sort_date": date_str,  # For sorting
                "OWM_Condition": owm["condition"],
                "OWM_Rain_MM": owm["rain_mm"],
                "Google_Condition": google["condition"],
                "Google_Rain_MM": google["rain_mm"],
            })

    # Sort by date, then by location
    df = pd.DataFrame(results)
    df = df.sort_values(["_sort_date", "Location"]).drop(columns=["_sort_date"])
    return df.reset_index(drop=True)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare weather APIs for Murang'a wards"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Number of forecast days (0 = current conditions only)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of wards to process (default: all)"
    )
    return parser.parse_args()


def main():
    """Main comparison function."""
    args = parse_args()

    mode = "Forecast" if args.days > 0 else "Current Conditions"
    print("=" * 60)
    print(f"Weather API Comparison - Murang'a Wards ({mode})")
    print("=" * 60)

    # Check API keys
    print("\nAPI Key Status:")
    print(f"  OpenWeatherMap: {'✓' if OPENWEATHER_KEY else '✗'}")
    print(f"  Google Weather: {'✓' if GOOGLE_WEATHER_KEY else '✗'}")
    print()

    # Load wards
    wards = load_muranga_wards(limit=args.limit)
    print(f"Loaded {len(wards)} wards from Murang'a\n")

    # Run comparison
    if args.days > 0:
        df = run_forecast(wards, args.days)
        suffix = f"-forecast-{args.days}d"
    else:
        df = run_current_conditions(wards)
        suffix = ""

    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = script_dir / f"{timestamp}-muranga{suffix}.csv"

    # Save to CSV
    df.to_csv(output_file, index=False)

    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(df.to_string(index=False))
    print(f"\nSaved to: {output_file}")


if __name__ == "__main__":
    main()
