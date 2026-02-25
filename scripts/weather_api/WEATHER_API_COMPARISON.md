# Weather API Comparison

Comparison between OpenWeatherMap (current implementation) and Windy Point Forecast API.

## API Overview

| Feature | OpenWeatherMap (Current) | Windy Point Forecast |
|---------|-------------------------|---------------------|
| **Endpoint** | `api.openweathermap.org` | `api.windy.com/api/point-forecast/v2` |
| **Method** | GET | POST |
| **Auth** | Query param `appid` | Request body `key` |
| **Forecast Range** | 5 days (40 data points, 3h intervals) | ~10 days (80 data points, 3h intervals) |
| **Models** | Single model | Multiple (gfs, iconEu, arome, etc.) |
| **Coverage** | Global | Global (gfs), Regional for others |
| **Pricing** | Free tier (API 2.5), Paid (API 3.0) | Free tier available |

## Data Format Differences

| Data | OpenWeatherMap | Windy |
|------|----------------|-------|
| **Temperature** | Celsius (direct) | Kelvin (subtract 273.15) |
| **Precipitation** | mm per 3h | meters (multiply by 1000) |
| **Wind** | speed (m/s) + direction (deg) | u/v components in m/s |
| **Humidity** | % | % |
| **Pressure** | hPa | Pa (divide by 100) |
| **Clouds** | % coverage | Low/Mid/High layers separate |

## Response Structure

### OpenWeatherMap API 2.5

```json
{
  "cod": "200",
  "list": [
    {
      "dt": 1772020800,
      "main": {
        "temp": 23.93,
        "feels_like": 23.68,
        "temp_min": 23.93,
        "temp_max": 24.55,
        "pressure": 1009,
        "humidity": 50
      },
      "weather": [
        {
          "main": "Rain",
          "description": "light rain"
        }
      ],
      "wind": {
        "speed": 3.57,
        "deg": 71
      },
      "rain": {
        "3h": 1.24
      }
    }
  ],
  "city": {
    "name": "Nairobi",
    "coord": { "lat": -1.2833, "lon": 36.8167 }
  }
}
```

### Windy Point Forecast API

```json
{
  "ts": [1771988400000, 1771999200000, ...],
  "units": {
    "temp-surface": "K",
    "wind_u-surface": "m*s-1",
    "wind_v-surface": "m*s-1",
    "past3hprecip-surface": "m",
    "rh-surface": "%",
    "pressure-surface": "Pa"
  },
  "temp-surface": [290.38, 291.88, ...],
  "wind_u-surface": [-2.58, -1.13, ...],
  "wind_v-surface": [0.04, -0.33, ...],
  "past3hprecip-surface": [0.00027, 0.00032, ...],
  "rh-surface": [87.64, 89.38, ...],
  "pressure-surface": [100905.98, 101234.49, ...]
}
```

## Unit Conversions for Windy

```python
# Temperature: Kelvin to Celsius
temp_celsius = temp_kelvin - 273.15

# Precipitation: meters to mm
precip_mm = precip_meters * 1000

# Pressure: Pa to hPa
pressure_hpa = pressure_pa / 100

# Wind: u/v components to speed and direction
import math
wind_speed = math.sqrt(wind_u**2 + wind_v**2)
wind_direction = (math.degrees(math.atan2(-wind_u, -wind_v)) + 360) % 360
```

## Available Windy Models

| Model | Coverage | Resolution | Update Frequency |
|-------|----------|------------|------------------|
| `gfs` | Global | ~22km | Every 6 hours |
| `iconEu` | Europe | ~7km | Every 6 hours |
| `arome` | France | ~1.3km | Every 3 hours |
| `namConus` | USA (Continental) | ~3km | Every 6 hours |
| `namHawaii` | Hawaii | ~3km | Every 6 hours |
| `namAlaska` | Alaska | ~6km | Every 6 hours |

## Available Windy Parameters

- `temp` - Temperature
- `wind` - Wind (returns u and v components)
- `precip` - Precipitation (past 3 hours)
- `rh` - Relative humidity
- `dewpoint` - Dewpoint temperature
- `pressure` - Surface pressure
- `lclouds` - Low clouds
- `mclouds` - Medium clouds
- `hclouds` - High clouds
- `ptype` - Precipitation type

## Pros and Cons

### OpenWeatherMap

**Pros:**
- Already integrated in the codebase
- Ready-to-use units (Celsius, mm, hPa)
- Weather descriptions included ("light rain", "cloudy")
- City name resolution from coordinates

**Cons:**
- API 3.0 (OneCall) requires paid subscription
- Single forecast model
- 5-day forecast limit on free tier

### Windy

**Pros:**
- Longer forecast range (~10 days)
- Multiple forecast models available
- More granular wind data (u/v components)
- Separate cloud layer data (low/mid/high)
- Better for agricultural spraying decisions (wind vectors)

**Cons:**
- Requires unit conversions
- No weather descriptions (must derive from data)
- Test API returns shuffled data (production key needed)
- No city name resolution

## Recommendations for Agriculture

For agricultural weather broadcasts, consider:

1. **Keep OpenWeatherMap** for general forecasts and weather descriptions
2. **Add Windy** for:
   - Extended forecasts (7-10 days for crop planning)
   - Detailed wind data (spraying decisions)
   - Multiple model comparison for critical decisions

## Testing

Run the Windy API test:
```bash
./scripts/test_windy_api.sh              # Nairobi (default)
./scripts/test_windy_api.sh -0.4 36.9    # Custom coordinates
```
