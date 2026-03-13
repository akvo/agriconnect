# Weather API Comparison

Comparison between OpenWeatherMap (current implementation), Windy Point Forecast API, and Google Weather API.

## API Overview

| Feature | OpenWeatherMap (Current) | Windy Point Forecast | Google Weather API |
|---------|-------------------------|---------------------|-------------------|
| **Endpoint** | `api.openweathermap.org` | `api.windy.com/api/point-forecast/v2` | `weather.googleapis.com/v1` |
| **Method** | GET | POST | GET |
| **Auth** | Query param `appid` | Request body `key` | Query param `key` |
| **Forecast Range** | 5 days (40 data points, 3h intervals) | ~10 days (80 data points, 3h intervals) | 10 days (hourly: 240h, daily: 10d) |
| **Models** | Single model | Multiple (gfs, iconEu, arome, etc.) | Single model |
| **Coverage** | Global | Global (gfs), Regional for others | Global |
| **Pricing** | Free tier (API 2.5), Paid (API 3.0) | Free tier available | Pay-as-you-go (Google Cloud) |

## Data Format Differences

| Data | OpenWeatherMap | Windy | Google Weather |
|------|----------------|-------|----------------|
| **Temperature** | Celsius (direct) | Kelvin (subtract 273.15) | Celsius (direct) |
| **Precipitation** | mm per 3h | meters (multiply by 1000) | mm (direct) |
| **Wind** | speed (m/s) + direction (deg) | u/v components in m/s | speed (m/s) + direction (deg + cardinal) |
| **Humidity** | % | % | % |
| **Pressure** | hPa | Pa (divide by 100) | hPa/millibars (direct) |
| **Clouds** | % coverage | Low/Mid/High layers separate | % coverage |
| **Visibility** | Not in forecast | Not available | km |
| **UV Index** | Not in free tier | Not available | Available |
| **Thunderstorm** | Via weather type | Via precip type | Probability % |

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

### Google Weather API - Current Conditions

```json
{
  "currentTime": "2024-03-13T10:00:00Z",
  "timeZone": {
    "id": "Africa/Nairobi"
  },
  "isDaytime": true,
  "weatherCondition": {
    "iconBaseUri": "https://...",
    "description": { "text": "Partly cloudy", "languageCode": "en" },
    "type": "PARTLY_CLOUDY"
  },
  "temperature": { "degrees": 24.5, "unit": "CELSIUS" },
  "feelsLikeTemperature": { "degrees": 25.1, "unit": "CELSIUS" },
  "dewPoint": { "degrees": 18.2, "unit": "CELSIUS" },
  "heatIndex": { "degrees": 25.3, "unit": "CELSIUS" },
  "relativeHumidity": 68,
  "uvIndex": 7,
  "precipitation": {
    "probability": { "percent": 20, "type": "RAIN" },
    "qpf": { "quantity": 0.5, "unit": "MILLIMETERS" }
  },
  "thunderstormProbability": 10,
  "airPressure": { "meanSeaLevelMillibars": 1015.2 },
  "wind": {
    "direction": { "degrees": 135, "cardinal": "SE" },
    "speed": { "value": 3.5, "unit": "METERS_PER_SECOND" },
    "gust": { "value": 5.2, "unit": "METERS_PER_SECOND" }
  },
  "visibility": { "distance": 10, "unit": "KILOMETERS" },
  "cloudCover": 45
}
```

### Google Weather API - Hourly Forecast

```json
{
  "forecastHours": [
    {
      "interval": {
        "startTime": "2024-03-13T10:00:00Z",
        "endTime": "2024-03-13T11:00:00Z"
      },
      "displayDateTime": {
        "year": 2024, "month": 3, "day": 13, "hours": 13,
        "utcOffset": "+03:00"
      },
      "isDaytime": true,
      "weatherCondition": {
        "description": { "text": "Sunny", "languageCode": "en" },
        "type": "SUNNY"
      },
      "temperature": { "degrees": 26.0, "unit": "CELSIUS" },
      "feelsLikeTemperature": { "degrees": 27.2, "unit": "CELSIUS" },
      "relativeHumidity": 55,
      "uvIndex": 8,
      "precipitation": {
        "probability": { "percent": 5, "type": "NONE" }
      },
      "wind": {
        "direction": { "degrees": 180, "cardinal": "S" },
        "speed": { "value": 4.0, "unit": "METERS_PER_SECOND" }
      }
    }
  ],
  "timeZone": { "id": "Africa/Nairobi" }
}
```

### Google Weather API - Daily Forecast

```json
{
  "forecastDays": [
    {
      "interval": {
        "startTime": "2024-03-13T00:00:00Z",
        "endTime": "2024-03-14T00:00:00Z"
      },
      "displayDate": { "year": 2024, "month": 3, "day": 13 },
      "daytimeForecast": {
        "weatherCondition": {
          "description": { "text": "Partly cloudy", "languageCode": "en" },
          "type": "PARTLY_CLOUDY"
        },
        "precipitation": { "probability": { "percent": 30, "type": "RAIN" } }
      },
      "nighttimeForecast": {
        "weatherCondition": {
          "description": { "text": "Clear", "languageCode": "en" },
          "type": "CLEAR"
        }
      },
      "maxTemperature": { "degrees": 28.0, "unit": "CELSIUS" },
      "minTemperature": { "degrees": 16.0, "unit": "CELSIUS" },
      "sunrise": "06:32:00",
      "sunset": "18:45:00",
      "moonPhase": "WAXING_CRESCENT"
    }
  ],
  "timeZone": { "id": "Africa/Nairobi" }
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

## Google Weather API - No Conversions Needed

Google Weather API returns data in standard units:
- Temperature: Celsius
- Precipitation: Millimeters
- Pressure: Millibars (hPa)
- Wind: m/s with direction in degrees and cardinal
- Visibility: Kilometers

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

## Google Weather API Endpoints

| Endpoint | URL | Description |
|----------|-----|-------------|
| Current Conditions | `/v1/currentConditions:lookup` | Real-time weather data |
| Hourly Forecast | `/v1/forecast/hours:lookup` | Up to 240 hours (10 days) |
| Daily Forecast | `/v1/forecast/days:lookup` | Up to 10 days |
| Hourly History | `/v1/history/hours:lookup` | Past 24 hours (cached) |

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

### Google Weather API

**Pros:**
- No unit conversions needed (metric by default)
- Rich weather descriptions with icons
- Up to 10-day forecasts (hourly and daily)
- UV Index included (important for agriculture)
- Thunderstorm probability (useful for farming alerts)
- Sunrise/sunset/moon phase data
- Cardinal wind directions included
- Well-structured JSON responses
- Part of Google Cloud ecosystem

**Cons:**
- Pay-as-you-go pricing (no permanent free tier)
- Single forecast model
- Requires Google Cloud project setup
- Relatively new API (may have fewer third-party integrations)

## Recommendations for Agriculture

For agricultural weather broadcasts, consider:

1. **Keep OpenWeatherMap** for general forecasts and weather descriptions (free tier)
2. **Add Windy** for:
   - Extended forecasts (7-10 days for crop planning)
   - Detailed wind data (spraying decisions)
   - Multiple model comparison for critical decisions
3. **Consider Google Weather API** for:
   - UV Index data (crop protection, worker safety)
   - Thunderstorm probability (urgent farming alerts)
   - Sunrise/sunset times (irrigation scheduling)
   - Clean, ready-to-use data without conversions
   - When budget allows for pay-as-you-go pricing

## Testing

Run the API tests:
```bash
# Windy API
./scripts/weather_api/test_windy_api.sh              # Nairobi (default)
./scripts/weather_api/test_windy_api.sh -0.4 36.9    # Custom coordinates

# Google Weather API
./scripts/weather_api/test_google_weather_api.sh              # Nairobi (default)
./scripts/weather_api/test_google_weather_api.sh -0.4 36.9    # Custom coordinates
```
