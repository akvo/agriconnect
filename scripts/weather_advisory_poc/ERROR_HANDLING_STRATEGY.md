# Error Handling Strategy for Rule Engine Integration

## Failure Points & Mitigation

### 1. Weather API Failures

#### Failure Scenarios
- Google Weather API down/timeout
- Invalid coordinates (out of bounds)
- No forecast data available
- Rate limit exceeded
- Malformed API response

#### Handling Strategy
```python
class WeatherAPIError(Exception):
    """Base exception for weather API failures"""
    pass

class WeatherDataUnavailable(WeatherAPIError):
    """Weather data could not be retrieved"""
    pass

def get_weather_data_with_fallback(location, lat, lon):
    """
    Get weather data with multiple fallback strategies.

    Returns:
        weather_data OR None (with logged error)
    """
    try:
        # Primary: Coordinates-based (more accurate)
        if lat and lon:
            weather_data = weather_service.get_current_raw(lat, lon)
            if weather_data:
                return weather_data

        # Fallback: Location name-based
        weather_data = weather_service.get_forecast_raw(location)
        if weather_data:
            return weather_data

        # No data available
        logger.error(f"No weather data for {location} ({lat}, {lon})")
        return None

    except requests.Timeout:
        logger.error(f"Weather API timeout for {location}")
        return None
    except requests.RequestException as e:
        logger.error(f"Weather API error for {location}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error fetching weather for {location}: {e}")
        return None
```

#### Fallback Actions When Weather API Fails
1. **Skip broadcast for this location** (don't send stale/wrong data)
2. **Send generic seasonal reminder** (from crop calendar only)
3. **Retry after 1 hour** (queue for next batch)
4. **Alert admin** if failures exceed 20%

---

### 2. Rule Engine Failures

#### Failure Scenarios
- Missing/corrupted rules JSON file
- Invalid rule condition syntax
- Division by zero in rule evaluation
- Missing weather fields referenced by rules
- Invalid growth stage mapping

#### Handling Strategy
```python
class RuleEngineError(Exception):
    """Base exception for rule engine failures"""
    pass

class RulesFileCorrupted(RuleEngineError):
    """Rules JSON file is invalid"""
    pass

class RuleEvaluationError(RuleEngineError):
    """Error evaluating a specific rule"""
    pass

def load_rules_with_validation():
    """Load rules with validation and caching."""
    try:
        rules_data = load_rules()

        # Validate structure
        if not rules_data.get("rules"):
            raise RulesFileCorrupted("No 'rules' key in rules JSON")

        if not isinstance(rules_data["rules"], list):
            raise RulesFileCorrupted("'rules' must be a list")

        # Validate each rule has required fields
        required_fields = ["id", "category", "name", "weather_condition", "priority"]
        for i, rule in enumerate(rules_data["rules"]):
            for field in required_fields:
                if field not in rule:
                    logger.warning(f"Rule {i} missing field '{field}', skipping")

        return rules_data

    except json.JSONDecodeError as e:
        logger.exception(f"Rules JSON is corrupted: {e}")
        raise RulesFileCorrupted(f"Invalid JSON: {e}")
    except FileNotFoundError:
        logger.exception("Rules file not found")
        raise RulesFileCorrupted("Rules file missing")

def evaluate_rules_safe(weather, rules_data, variety="Hass"):
    """
    Evaluate rules with per-rule error handling.

    If a rule fails, log it and skip, don't crash entire evaluation.
    """
    triggered = []
    failed_rules = []

    for rule in rules_data.get("rules", []):
        try:
            # Evaluate this rule
            if evaluate_single_rule(weather, rule, variety):
                triggered.append(rule)
        except KeyError as e:
            # Weather data missing field referenced by rule
            logger.warning(
                f"Rule {rule['id']} references missing field {e}, skipping"
            )
            failed_rules.append((rule["id"], f"Missing field: {e}"))
        except (ValueError, TypeError, ZeroDivisionError) as e:
            # Calculation error in rule
            logger.warning(
                f"Rule {rule['id']} evaluation error: {e}, skipping"
            )
            failed_rules.append((rule["id"], str(e)))
        except Exception as e:
            # Unexpected error
            logger.exception(
                f"Unexpected error evaluating rule {rule['id']}: {e}"
            )
            failed_rules.append((rule["id"], f"Unexpected: {e}"))

    # Log summary
    if failed_rules:
        logger.warning(
            f"Rule evaluation: {len(triggered)} triggered, "
            f"{len(failed_rules)} failed: {failed_rules}"
        )

    return triggered
```

#### Fallback Actions When Rules Fail
1. **Partial results**: Send advisory with successfully triggered rules
2. **Minimum viable message**: If all rules fail, send basic weather forecast only
3. **Alert developer**: Log failed rules for investigation
4. **Graceful degradation**: Never crash the entire broadcast

---

### 3. Missing Farmer Profile Data

#### Failure Scenarios
- `variety` field is NULL/empty
- `administrative_id` missing (no location)
- `lat`/`lon` are NULL (can't get accurate weather)
- `crop_type != "Avocado"` (rules only support avocado)

#### Handling Strategy
```python
def validate_farmer_profile(customer):
    """
    Validate farmer has minimum required data for rule engine.

    Returns:
        (is_valid, issues) tuple
    """
    issues = []

    # Required: location
    if not customer.customer_administrative or not customer.customer_administrative[0].administrative:
        issues.append("no_location")
        return (False, issues)

    admin_area = customer.customer_administrative[0].administrative

    # Preferred: coordinates for accurate weather
    if not admin_area.lat or not admin_area.lon:
        issues.append("no_coordinates")
        # Not fatal - can use location name

    # Required: crop type must be avocado
    if customer.crop_type and customer.crop_type.lower() != "avocado":
        issues.append(f"unsupported_crop_{customer.crop_type}")
        return (False, issues)

    # Optional: variety (can default to Hass)
    if not customer.variety:
        issues.append("no_variety")
        # Not fatal - default to Hass

    return (True, issues)

def get_farmer_variety_safe(customer):
    """Get variety with safe fallback."""
    if customer.variety and customer.variety in ["Hass", "Fuerte", "Pinkerton"]:
        return customer.variety

    # Default to Hass (70% market share in Kenya)
    logger.info(f"Customer {customer.id} has no variety, defaulting to Hass")
    return "Hass"

def get_growth_stage_safe(calendar, month, variety):
    """Get growth stage with error handling."""
    try:
        month_data = calendar.get("monthly_calendar", {}).get(str(month), {})
        if not month_data:
            logger.warning(f"No calendar data for month {month}")
            return "unknown"

        phenology = month_data.get("phenology", {})
        stage = phenology.get(variety, "unknown")

        if stage == "unknown":
            logger.warning(f"No growth stage for {variety} in month {month}")

        return stage

    except Exception as e:
        logger.exception(f"Error getting growth stage: {e}")
        return "unknown"
```

#### Fallback Actions
1. **No location**: Skip farmer (can't get weather)
2. **No variety**: Default to "Hass"
3. **No coordinates**: Use location name for weather
4. **Wrong crop**: Skip farmer (rules are avocado-specific)

---

### 4. LLM Failures

#### Failure Scenarios
- OpenAI API timeout/rate limit
- Empty/invalid response
- Response exceeds 500 characters
- Response in wrong language
- Non-UTF8 characters (WhatsApp incompatible)

#### Handling Strategy
```python
class LLMError(Exception):
    """LLM generation failed"""
    pass

async def generate_whatsapp_message_safe(advisory_data, language="en", max_retries=3):
    """
    Generate WhatsApp message with retries and validation.
    """
    for attempt in range(max_retries):
        try:
            # Call LLM
            response = await openai_service.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a friendly agricultural weather advisor..."},
                    {"role": "user", "content": advisory_data}
                ],
                temperature=0.7,
                max_tokens=500,
                timeout=30,  # 30s timeout
            )

            if not response or not response.content:
                raise LLMError("Empty LLM response")

            message = response.content.strip()

            # Validate length
            if len(message) > 600:
                logger.warning(f"LLM message too long ({len(message)} chars), truncating")
                message = message[:597] + "..."

            # Validate language (basic check)
            if language == "sw" and not any(word in message.lower() for word in ["na", "ya", "wa", "kwa"]):
                logger.warning("LLM response may not be in Swahili")

            # Validate WhatsApp compatibility
            try:
                message.encode('utf-8')
            except UnicodeEncodeError:
                logger.error("Message contains non-UTF8 characters")
                message = message.encode('utf-8', errors='ignore').decode('utf-8')

            return message

        except asyncio.TimeoutError:
            logger.warning(f"LLM timeout on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise LLMError("LLM timeout after retries")

        except Exception as e:
            logger.warning(f"LLM error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise LLMError(f"LLM failed: {e}")

    raise LLMError("Max retries exceeded")
```

#### Fallback Actions When LLM Fails
1. **Use template-based message**: Pre-formatted message from triggered rules (no LLM)
2. **Send previous day's message**: If available (better than nothing)
3. **Send generic weather**: Basic forecast without rule-based advice
4. **Skip this farmer**: Only if all fallbacks fail

---

### 5. Crop Calendar Issues

#### Failure Scenarios
- Invalid month (13, 0, etc.)
- Missing variety in calendar
- Corrupted JSON structure

#### Handling Strategy
```python
def load_calendar_safe():
    """Load crop calendar with validation."""
    try:
        calendar = load_calendar()

        # Validate structure
        if "monthly_calendar" not in calendar:
            raise ValueError("Missing 'monthly_calendar' key")

        # Validate all 12 months exist
        for month in range(1, 13):
            if str(month) not in calendar["monthly_calendar"]:
                logger.warning(f"Calendar missing month {month}")

        return calendar

    except Exception as e:
        logger.exception(f"Error loading calendar: {e}")
        # Return minimal fallback calendar
        return {
            "monthly_calendar": {
                str(m): {"phenology": {"Hass": "unknown", "Fuerte": "unknown"}}
                for m in range(1, 13)
            }
        }
```

---

### 6. Broadcast Task Failures

#### Failure Scenarios
- Database connection lost during broadcast
- Celery worker crashes mid-broadcast
- Memory exhaustion (10k+ farmers)
- Partial completion (500/1000 sent)

#### Handling Strategy
```python
@celery_app.task(
    name="tasks.weather_tasks.send_weather_broadcasts_with_recovery",
    autoretry_for=(DatabaseError,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    soft_time_limit=3600,  # 1 hour soft limit
    time_limit=3900,  # Hard limit
)
def send_weather_broadcasts_safe():
    """
    Send broadcasts with transaction-level recovery.
    """
    db = SessionLocal()
    processed = 0
    failed = 0

    try:
        # Get all area+variety groups
        groups = get_broadcast_groups(db)
        total = len(groups)

        logger.info(f"Starting broadcast for {total} groups")

        for i, (area_id, variety, customer_ids) in enumerate(groups):
            try:
                # Process this group in its own transaction
                with db.begin_nested():
                    broadcast = create_and_send_broadcast(
                        db, area_id, variety, customer_ids
                    )
                    db.commit()
                    processed += 1

            except Exception as e:
                logger.error(
                    f"Failed to process group {area_id}/{variety}: {e}",
                    exc_info=True
                )
                db.rollback()
                failed += 1
                # Continue to next group - don't stop entire broadcast

            # Progress logging
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{total} groups processed")

        logger.info(
            f"Broadcast complete: {processed} succeeded, {failed} failed"
        )

        return {
            "total": total,
            "succeeded": processed,
            "failed": failed,
        }

    except Exception as e:
        logger.exception(f"Critical error in broadcast task: {e}")
        raise
    finally:
        db.close()
```

---

## Monitoring & Alerts

### Metrics to Track
1. **Success rate**: % of farmers who received broadcast
2. **Rule trigger rate**: Average rules per broadcast
3. **LLM failure rate**: % of LLM calls that failed
4. **Weather API uptime**: % of successful weather fetches
5. **Processing time**: Time to complete full broadcast

### Alert Thresholds
- ⚠️ Warning: >5% failure rate
- 🚨 Critical: >20% failure rate
- 🚨 Critical: Weather API down for >30 minutes
- ⚠️ Warning: LLM response time >10 seconds

### Logging Strategy
```python
# Structured logging for easy querying
logger.info(
    "Broadcast result",
    extra={
        "area_id": area_id,
        "variety": variety,
        "customer_count": len(customer_ids),
        "rules_triggered": len(triggered_rules),
        "weather_source": "coordinates" if lat else "location",
        "llm_tokens": token_count,
        "duration_ms": duration,
        "status": "success",
    }
)
```

---

## Error Response Messages

### When Broadcast Fails Completely
- **Option 1**: Don't send anything (better than wrong data)
- **Option 2**: Send apology: "Weather advisory unavailable today due to technical issues. Check back tomorrow."

### When Partial Data Available
- **Option 3**: Send basic weather only: "Weather for Murang'a: Rain expected 6mm, 11-18°C. Check drainage channels."

### When LLM Fails but Rules Work
- **Option 4**: Template-based formatting:
```
*Weather Alert - Kariara*
*Today:* Rain 6mm, 11-18°C

*URGENT:*
• Apply Ridomil around tree bases (root rot risk)
• Clear all drainage channels

*AVOID:*
• No spraying (rain will wash off)
• No harvesting (wet conditions)
```

---

## Testing Strategy

### Unit Tests
```python
def test_weather_api_timeout():
    """Rule engine handles weather timeout gracefully."""
    with mock.patch('weather_service.get_current_raw', side_effect=Timeout):
        result = get_weather_data_with_fallback("Nairobi", -1.29, 36.82)
        assert result is None

def test_missing_variety_defaults_to_hass():
    """Missing variety defaults to Hass."""
    customer = Customer(variety=None)
    variety = get_farmer_variety_safe(customer)
    assert variety == "Hass"

def test_rule_evaluation_with_missing_field():
    """Rule engine skips rules with missing weather fields."""
    weather = {"temperature_c": 20}  # Missing humidity
    rules_data = load_rules()
    triggered = evaluate_rules_safe(weather, rules_data)
    # Should not crash, just skip rules needing humidity
    assert isinstance(triggered, list)
```

### Integration Tests
```python
def test_end_to_end_with_api_failure():
    """Full broadcast continues even if some areas fail."""
    # Mock API to fail for area 1, succeed for area 2
    with mock.patch('weather_service.get_current_raw') as mock_weather:
        mock_weather.side_effect = [None, valid_weather_data]

        result = send_weather_broadcasts_safe()

        assert result["succeeded"] >= 1  # At least area 2 succeeded
        assert result["failed"] >= 1     # Area 1 failed
```

---

## Summary

**Key Principles:**
1. **Fail gracefully**: Never crash entire broadcast for one error
2. **Partial success**: Send what you can, skip what fails
3. **Sensible defaults**: Hass variety, mature trees, location-based weather
4. **Comprehensive logging**: Every failure logged with context
5. **Retry with backoff**: Transient errors (API timeout) get 3 retries
6. **Alert on patterns**: Single failure = log, >20% failure = alert admin
7. **Degrade gracefully**: LLM fails → template, template fails → generic, generic fails → skip

**Never send:**
- ❌ Stale weather data (>24h old)
- ❌ Wrong variety advice (Hass rules for Fuerte farmer)
- ❌ Partially rendered messages (template with {{ variables }})
- ❌ Error messages visible to farmer (keep technical details hidden)
