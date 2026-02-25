#!/bin/bash
# Test script for Windy Point Forecast API v2
# Documentation: https://api.windy.com/point-forecast/docs
#
# Usage: ./test_windy_api.sh [lat] [lon]
# Example: ./test_windy_api.sh -1.2921 36.8219  (Nairobi)
#
# API Notes:
# - Endpoint: POST https://api.windy.com/api/point-forecast/v2
# - Models: gfs (global), iconEu (Europe), arome (France), etc.
# - Units: temp in Kelvin, wind in m/s, precip in meters, pressure in Pa

set -e

# Load API key from .env file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [ -f "$ENV_FILE" ]; then
    WINDYCOM=$(grep -E '^WINDYCOM=' "$ENV_FILE" | cut -d'=' -f2)
fi

if [ -z "$WINDYCOM" ]; then
    echo "Error: WINDYCOM API key not found in .env file"
    exit 1
fi

# Default coordinates (Nairobi, Kenya)
LAT="${1:--1.2921}"
LON="${2:-36.8219}"

echo "=============================================="
echo "Windy Point Forecast API Test"
echo "=============================================="
echo "Location: lat=$LAT, lon=$LON"
echo "API Endpoint: https://api.windy.com/api/point-forecast/v2"
echo ""

# Test: GFS Model - All agriculture-relevant parameters
echo "=== GFS Model - Agriculture Parameters ==="
echo "Parameters: temp, wind, precip, rh (humidity), dewpoint, pressure"
echo "Levels: surface"
echo ""
curl -s -X POST 'https://api.windy.com/api/point-forecast/v2' \
    -H 'Content-Type: application/json' \
    -d "{
        \"lat\": $LAT,
        \"lon\": $LON,
        \"model\": \"gfs\",
        \"parameters\": [\"temp\", \"wind\", \"precip\", \"rh\", \"dewpoint\", \"pressure\"],
        \"levels\": [\"surface\"],
        \"key\": \"$WINDYCOM\"
    }"

echo ""
echo ""
echo "=============================================="
echo "Test Complete"
echo "=============================================="
echo ""
echo "Note: Units conversion needed:"
echo "  - Temperature: Kelvin to Celsius (subtract 273.15)"
echo "  - Precipitation: meters to mm (multiply by 1000)"
echo "  - Pressure: Pa to hPa (divide by 100)"
echo "  - Wind: Use sqrt(u^2 + v^2) for speed, atan2 for direction"
