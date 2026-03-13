#!/bin/bash
# Test script for Google Weather API
# Documentation: https://developers.google.com/maps/documentation/weather/overview
#
# Usage: ./test_google_weather_api.sh [lat] [lon]
# Example: ./test_google_weather_api.sh -1.2921 36.8219  (Nairobi)
#
# API Notes:
# - Base URL: https://weather.googleapis.com/v1
# - Endpoints: currentConditions, forecast/hours, forecast/days
# - Auth: API key via query parameter
# - Units: Metric by default (Celsius, km, mm)

set -e

# Load API key from .env file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../../.env"

if [ -f "$ENV_FILE" ]; then
    GOOGLE_WEATHER_API_KEY=$(grep -E '^GOOGLE_WEATHER_API_KEY=' "$ENV_FILE" | cut -d'=' -f2)
fi

if [ -z "$GOOGLE_WEATHER_API_KEY" ]; then
    echo "Error: GOOGLE_WEATHER_API_KEY not found in .env file"
    exit 1
fi

# Default coordinates (Nairobi, Kenya)
LAT="${1:--1.2921}"
LON="${2:-36.8219}"

echo "=============================================="
echo "Google Weather API Test"
echo "=============================================="
echo "Location: lat=$LAT, lon=$LON"
echo "Base URL: https://weather.googleapis.com/v1"
echo ""

# Test 1: Current Conditions
echo "=== Current Conditions ==="
echo "Endpoint: /currentConditions:lookup"
echo ""
curl -s -X GET "https://weather.googleapis.com/v1/currentConditions:lookup?key=$GOOGLE_WEATHER_API_KEY&location.latitude=$LAT&location.longitude=$LON" | python3 -m json.tool 2>/dev/null || cat

echo ""
echo ""

# Test 2: Hourly Forecast (next 24 hours)
echo "=== Hourly Forecast (24 hours) ==="
echo "Endpoint: /forecast/hours:lookup"
echo ""
curl -s -X GET "https://weather.googleapis.com/v1/forecast/hours:lookup?key=$GOOGLE_WEATHER_API_KEY&location.latitude=$LAT&location.longitude=$LON&hours=24" | python3 -m json.tool 2>/dev/null || cat

echo ""
echo ""

# Test 3: Daily Forecast (10 days)
echo "=== Daily Forecast (10 days) ==="
echo "Endpoint: /forecast/days:lookup"
echo ""
curl -s -X GET "https://weather.googleapis.com/v1/forecast/days:lookup?key=$GOOGLE_WEATHER_API_KEY&location.latitude=$LAT&location.longitude=$LON&days=10" | python3 -m json.tool 2>/dev/null || cat

echo ""
echo ""
echo "=============================================="
echo "Test Complete"
echo "=============================================="
echo ""
echo "Note: Google Weather API returns data in:"
echo "  - Temperature: Celsius (direct, no conversion)"
echo "  - Precipitation: mm (direct, no conversion)"
echo "  - Pressure: millibars/hPa (direct, no conversion)"
echo "  - Wind: speed in m/s, direction in degrees + cardinal"
echo "  - Visibility: km"
