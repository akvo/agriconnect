#!/usr/bin/env python
"""
Weather API Comparison Script for Murang'a Districts.

Compares weather data from:
- OpenWeatherMap (via akvo-weather-info library)
- Google Weather API

Usage:
    python compare_weather_apis.py

Output:
    <datetime>-muranga.csv in the same directory
"""

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


def load_muranga_wards(limit: int = 10) -> list[dict]:
    """Load first N wards from Murang'a region with coordinates."""
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
                if len(wards) >= limit:
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


def main():
    """Main comparison function."""
    print("=" * 60)
    print("Weather API Comparison - Murang'a Wards")
    print("=" * 60)

    # Check API keys
    print("\nAPI Key Status:")
    print(f"  OpenWeatherMap: {'✓' if OPENWEATHER_KEY else '✗'}")
    print(f"  Google Weather: {'✓' if GOOGLE_WEATHER_KEY else '✗'}")
    print()

    # Load wards
    wards = load_muranga_wards(limit=10)
    print(f"Loaded {len(wards)} wards from Murang'a\n")

    # Collect data
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

    # Create DataFrame
    df = pd.DataFrame(results)

    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = script_dir / f"{timestamp}-muranga.csv"

    # Save to CSV
    df.to_csv(output_file, index=False)

    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(df.to_string(index=False))
    print(f"\nSaved to: {output_file}")


if __name__ == "__main__":
    main()
