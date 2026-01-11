# Weather Subscription Feature Progress

## Overview

Weather subscription allows farmers to opt-in to receive daily weather forecast messages for their administrative area via WhatsApp.

## Current Status: Phase 1 Complete

### Phase 1: Message Generation (DONE)

Implemented the ability to fetch weather data and generate farmer-friendly broadcast messages.

#### Key Files

| File | Purpose |
|------|---------|
| `services/weather_broadcast_service.py` | Core service for weather data retrieval and message generation |
| `services/weather_subscription_service.py` | Manages subscription preferences (subscribe/decline) |
| `routers/weather.py` | Admin test endpoint for message generation |
| `schemas/weather.py` | Request schema with location and language enum |
| `templates/weather_broadcast.txt` | Prompt template for OpenAI message generation |
| `tests/test_weather_broadcast_service.py` | Service tests (20 tests) |
| `tests/test_weather_router.py` | Router tests (9 tests) |

#### Configuration

Environment variables (in `.env`):
```
OPENWEATHER=your_openweather_api_key
```

Config.json:
```json
{
  "weather": {
    "broadcast_enabled": true
  }
}
```

#### How It Works

1. `WeatherBroadcastService.get_forecast_raw(location)` - Fetches raw weather data from OpenWeatherMap using `akvo-weather-info` library
2. `WeatherBroadcastService.generate_message(location, language, weather_data)` - Uses OpenAI to generate a farmer-friendly message based on the prompt template

#### Test Endpoint

```
POST /api/admin/weather/test-message
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "location": "Nairobi",
  "language": "en"  // or "sw" for Swahili
}
```

Returns plain text message.

#### Message Format

The generated message follows this structure:
1. Short title
2. Simple weather summary (2-3 lines) with temperature range and rainfall
3. "What to do today" section with bullet points (spraying, field work, watering)
4. One short reminder sentence

Max 1000 characters, WhatsApp-friendly formatting, no technical terms.

---

### Phase 2: Broadcast to Subscribers (TODO)

Send weather messages to all subscribed farmers in each administrative area.

#### Required Components

1. **Celery Task** (`tasks/weather_tasks.py`)
   - `send_weather_broadcasts()` - Scheduled task to run daily (e.g., 6 AM)
   - Query customers where `weather_subscribed = True`
   - Group by administrative area
   - Generate message for each area
   - Send via WhatsApp

2. **Integration with Existing Broadcast System**
   - Option A: Use existing `BroadcastService` to create dynamic groups and send
   - Option B: Direct WhatsApp sending without broadcast tracking

3. **Scheduling**
   - Add Celery Beat schedule for daily execution
   - Configure broadcast time in config.json

#### Database Queries Needed

```python
# Get all subscribed customers grouped by administrative area
customers = db.query(Customer).join(
    CustomerAdministrative
).filter(
    Customer.weather_subscribed == True
).all()

# Group by administrative area
from collections import defaultdict
by_area = defaultdict(list)
for customer in customers:
    area = customer.customer_administrative[0].administrative
    by_area[area.name].append(customer)
```

#### Considerations

- Rate limiting for WhatsApp API
- Error handling for failed deliveries
- Logging/tracking of sent messages
- Time zone handling for broadcast time
- Retry mechanism for failed sends

---

### Phase 3: Admin Management (TODO)

Admin interface to manage weather broadcasts.

#### Potential Features

1. View subscription statistics by area
2. Manual trigger for weather broadcast
3. Preview message before sending
4. View broadcast history/logs
5. Enable/disable broadcasts per area

---

## Existing Subscription Flow

Already implemented in `weather_subscription_service.py`:

1. After onboarding completion + admin area assignment
2. System asks: "Would you like to receive daily weather updates for {area_name}?"
3. Customer responds Yes/No via WhatsApp buttons
4. Preference stored in `customer.profile_data`:
   - `weather_subscription_asked: bool`
   - `weather_subscribed: bool | null`

Button payloads configured in `config.py`:
- `weather_yes_payload`: "weather_yes"
- `weather_no_payload`: "weather_no"

---

## Dependencies

- `akvo-weather-info>=0.1.0` - OpenWeatherMap API wrapper
- OpenAI API - Message generation
- Existing services: `openai_service.py`, `whatsapp_service.py`, `broadcast_service.py`
