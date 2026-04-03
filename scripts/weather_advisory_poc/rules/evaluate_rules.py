"""
Rule Evaluation Engine for Avocado Weather Advisory System.
Takes weather API output and evaluates it against the rule set to produce
a farmer-friendly advisory message.

The engine integrates two data sources:
  1. Weather rules (avocado_weather_rules.json) — triggered by weather conditions
  2. Crop calendar (avocado_crop_calendar.json) — provides growth stage context,
     seasonal management tasks, and pest/disease risk levels per month

Integration flow:
  Weather API → parse → enrich with calendar context → evaluate weather rules
                                                      → evaluate calendar rules
                                                      → merge, deduplicate, prioritize
"""

import json
from datetime import datetime
from pathlib import Path


def load_rules(path: str = None) -> dict:
    if path is None:
        path = Path(__file__).parent / "avocado_weather_rules.json"
    with open(path) as f:
        return json.load(f)


def load_calendar(path: str = None) -> dict:
    if path is None:
        path = Path(__file__).parent / "avocado_crop_calendar.json"
    with open(path) as f:
        return json.load(f)


def get_calendar_context(calendar: dict, month: int, variety: str = "Hass") -> dict:
    """Extract the current month's context from the crop calendar.

    Returns a dict with:
      - growth_stage: current phenological stage for this variety
      - management_due: list of management actions due this month
      - disease_risk: dict of disease → risk level
      - pest_risk: dict of pest → risk level
      - season: current Kenya season name
    """
    month_data = calendar.get("monthly_calendar", {}).get(str(month), {})
    if not month_data:
        return {}

    # Growth stage for the requested variety
    phenology = month_data.get("phenology", {})
    growth_stage = phenology.get(variety, "unknown")

    # All management actions due this month
    mgmt = month_data.get("management", {})
    management_due = []
    for activity, details in mgmt.items():
        if details.get("priority") in ("critical", "high"):
            management_due.append({
                "activity": activity,
                "priority": details["priority"],
                "action": details["action"],
            })

    return {
        "growth_stage": growth_stage,
        "season": month_data.get("season", "unknown"),
        "month_name": month_data.get("month_name", ""),
        "management_due": management_due,
        "disease_risk": month_data.get("disease_risk", {}),
        "pest_risk": month_data.get("pest_risk", {}),
        "phenology_all": phenology,
    }


def enrich_with_calendar(weather: dict, calendar_ctx: dict) -> dict:
    """Inject calendar context into the weather dict so rules can reference it."""
    weather["growth_stage"] = calendar_ctx.get("growth_stage", "unknown")
    weather["season_name"] = calendar_ctx.get("season", "unknown")

    # Map growth stage to the stage tags used in rules' applies_to_stages
    stage = calendar_ctx.get("growth_stage", "")
    stage_tags = set()
    stage_tags.add("all")
    if "flowering" in stage:
        stage_tags.update(["flowering", "pre_harvest"])
    if "fruit_set" in stage:
        stage_tags.update(["fruit_set", "fruit_enlargement"])
    if "fruit_development" in stage or "fruit_enlargement" in stage:
        stage_tags.update(["fruit_enlargement", "fruit_development"])
    if "harvest" in stage:
        stage_tags.update(["harvest", "pre_harvest"])
    if "post_harvest" in stage:
        stage_tags.add("post_harvest")
    if "dormancy" in stage:
        stage_tags.add("dormancy")
    if "vegetative" in stage or "flush" in stage:
        stage_tags.update(["vegetative", "vegetative_flush"])
    if "young" in stage or "transplant" in stage:
        stage_tags.update(["young_trees_1_3yr", "newly_transplanted"])
    weather["_active_stages"] = stage_tags

    # Inject disease/pest risk levels so rules could key off them
    for disease, level in calendar_ctx.get("disease_risk", {}).items():
        weather[f"disease_risk_{disease}"] = level
    for pest, level in calendar_ctx.get("pest_risk", {}).items():
        weather[f"pest_risk_{pest}"] = level

    return weather


def generate_calendar_rules(calendar_ctx: dict, weather: dict) -> list[dict]:
    """Generate synthetic rules from calendar management actions, gated by weather.

    For example, if the calendar says 'pruning is critical this month',
    we generate a rule that fires only if today's weather is suitable for pruning.
    """
    rules = []
    rain = weather.get("qpf_today_mm", 0)
    wind = weather.get("wind_speed_kmh", 0)
    humidity = weather.get("relative_humidity_pct", 50)
    temp = weather.get("temperature_c", 20)

    for task in calendar_ctx.get("management_due", []):
        activity = task["activity"]
        action = task["action"]
        priority = task["priority"]

        # Gate each activity by whether today's weather allows it
        if activity == "pruning":
            if rain < 2 and humidity < 75:
                rules.append({
                    "id": f"CAL-{activity.upper()}",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Pruning due this month — good conditions today",
                    "priority": priority,
                    "risk": "none — scheduled management activity with suitable weather",
                    "actions": [action, "Sterilise tools between trees (20% bleach)", "Whitewash exposed cuts"],
                    "source": "crop_calendar",
                })
            else:
                rules.append({
                    "id": f"CAL-{activity.upper()}-WAIT",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Pruning due this month — wait for dry day",
                    "priority": "informational",
                    "risk": "Pruning in wet conditions risks wound infection (stem end rot, bacterial canker)",
                    "actions": [action, "Wait for a day with <2mm rain and <75% humidity"],
                    "source": "crop_calendar",
                })

        elif activity == "spraying":
            if rain < 2 and wind < 15:
                rules.append({
                    "id": f"CAL-{activity.upper()}",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Spray program due — good window today",
                    "priority": priority,
                    "risk": "none — scheduled spray with suitable weather",
                    "actions": [action, "Apply early morning or late evening", "Ensure 4-6 dry hours after application"],
                    "source": "crop_calendar",
                })
            else:
                rules.append({
                    "id": f"CAL-{activity.upper()}-WAIT",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Spray program due — no good window today",
                    "priority": "informational",
                    "risk": "Spraying in rain/wind is wasteful — product washes off or drifts",
                    "actions": [action, f"Today: {rain}mm rain, {wind}km/h wind — wait for dry, calm day"],
                    "source": "crop_calendar",
                })

        elif activity == "irrigation":
            if rain < 3:
                rules.append({
                    "id": f"CAL-{activity.upper()}",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Irrigation needed this month",
                    "priority": priority,
                    "risk": "Moisture stress reduces fruit size and causes drop",
                    "actions": [action],
                    "source": "crop_calendar",
                })
            # If it rained, no irrigation rule — suppress silently

        elif activity == "harvest":
            if rain < 1 and wind < 20:
                rules.append({
                    "id": f"CAL-{activity.upper()}",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Harvest season — good conditions today",
                    "priority": priority,
                    "risk": "none — harvest window with suitable weather",
                    "actions": [action, "Harvest in the morning when fruit is cool", "Pre-cool to 5-7°C within 6 hours"],
                    "source": "crop_calendar",
                })
            else:
                rules.append({
                    "id": f"CAL-{activity.upper()}-WAIT",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Harvest season — delay until dry",
                    "priority": "high",
                    "risk": "Wet-harvested fruit has higher rot and lenticel damage",
                    "actions": [action, "Do NOT harvest in wet conditions — wait for dry morning"],
                    "source": "crop_calendar",
                })

        elif activity == "pest_monitoring":
            rules.append({
                "id": f"CAL-{activity.upper()}",
                "category": "CALENDAR_MANAGEMENT",
                "name": f"Calendar: Pest scouting priority this month",
                "priority": priority,
                "risk": "Seasonal pest pressure elevated",
                "actions": [action],
                "source": "crop_calendar",
            })

        elif activity == "fertilizer":
            if rain > 0 or weather.get("soil_moisture") == "moist":
                rules.append({
                    "id": f"CAL-{activity.upper()}",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Fertilizer application due — soil is moist",
                    "priority": priority,
                    "risk": "none — suitable conditions for nutrient uptake",
                    "actions": [action, "Apply to moist soil, not immediately before heavy rain"],
                    "source": "crop_calendar",
                })
            else:
                rules.append({
                    "id": f"CAL-{activity.upper()}-WAIT",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": f"Calendar: Fertilizer due — wait for moist soil",
                    "priority": "informational",
                    "risk": "Fertilizer on dry soil volatilises or causes salt burn",
                    "actions": [action, "Irrigate first, then apply — or wait for rain"],
                    "source": "crop_calendar",
                })

        elif activity == "planting":
            rules.append({
                "id": f"CAL-{activity.upper()}",
                "category": "CALENDAR_MANAGEMENT",
                "name": f"Calendar: Planting window open",
                "priority": priority,
                "risk": "none — seasonal planting opportunity",
                "actions": [action],
                "source": "crop_calendar",
            })

        else:
            # Generic calendar task
            rules.append({
                "id": f"CAL-{activity.upper()}",
                "category": "CALENDAR_MANAGEMENT",
                "name": f"Calendar: {activity.replace('_', ' ').title()}",
                "priority": priority,
                "risk": "",
                "actions": [action],
                "source": "crop_calendar",
            })

    # Add seasonal disease/pest risk elevation as informational rules
    disease_risk = calendar_ctx.get("disease_risk", {})
    high_risk_diseases = [d for d, level in disease_risk.items() if level in ("high", "very_high")]
    if high_risk_diseases:
        rules.append({
            "id": "CAL-DISEASE-ALERT",
            "category": "CALENDAR_MANAGEMENT",
            "name": f"Calendar: Elevated disease risk this month",
            "priority": "high" if any(disease_risk[d] == "very_high" for d in high_risk_diseases) else "medium",
            "risk": f"Seasonal risk is HIGH for: {', '.join(high_risk_diseases)}",
            "actions": [
                f"Monitor closely for {', '.join(high_risk_diseases)} symptoms",
                "Ensure fungicide program is current (copper every 14 days in wet weather)",
            ],
            "source": "crop_calendar",
        })

    pest_risk = calendar_ctx.get("pest_risk", {})
    high_risk_pests = [p for p, level in pest_risk.items() if level in ("high", "rising")]
    if high_risk_pests:
        rules.append({
            "id": "CAL-PEST-ALERT",
            "category": "CALENDAR_MANAGEMENT",
            "name": f"Calendar: Elevated pest risk this month",
            "priority": "medium",
            "risk": f"Seasonal pest pressure elevated for: {', '.join(high_risk_pests)}",
            "actions": [
                f"Increase scouting frequency for {', '.join(high_risk_pests)}",
                "Check traps and replace lures if older than 4 weeks",
            ],
            "source": "crop_calendar",
        })

    return rules


def filter_rules_by_growth_stage(triggered: list[dict], active_stages: set[str]) -> list[dict]:
    """Remove rules that don't apply to the current growth stage."""
    filtered = []
    for rule in triggered:
        crop_ctx = rule.get("crop_context", {})
        applies_to = crop_ctx.get("applies_to_stages")

        if applies_to is None:
            # No stage restriction — always include
            filtered.append(rule)
        elif "all" in applies_to:
            filtered.append(rule)
        elif active_stages.intersection(set(applies_to)):
            filtered.append(rule)
        # else: rule doesn't apply to current growth stage — skip

    return filtered


def parse_weather_data(raw: dict) -> dict:
    """Normalize weather API output into the flat fields the rules expect."""
    parsed = {}

    # Temperature
    hist = raw.get("currentConditionsHistory", {})
    temp_max = hist.get("maxTemperature", {}).get("degrees")
    temp_min = hist.get("minTemperature", {}).get("degrees")
    temp_change = hist.get("temperatureChange", {}).get("degrees", 0)

    if temp_max is not None and temp_min is not None:
        parsed["temperature_c"] = round((temp_max + temp_min) / 2, 1)
        parsed["temperature_max_c"] = temp_max
        parsed["temperature_min_c"] = temp_min
    parsed["temperature_change_24h_c"] = abs(temp_change)
    parsed["temperature_trend"] = "falling" if temp_change < 0 else "rising"

    # Wind
    wind = raw.get("wind", {})
    parsed["wind_speed_kmh"] = wind.get("speed", {}).get("value", 0)
    wind_gust = raw.get("windGust", wind)
    parsed["wind_gust_kmh"] = wind_gust.get("gust", {}).get("value",
                               wind_gust.get("value", parsed["wind_speed_kmh"]))

    # Cloud cover
    parsed["cloud_cover_pct"] = raw.get("cloudCover", 0)

    # Precipitation
    qpf = hist.get("qpf", {}).get("quantity", 0)
    parsed["qpf_today_mm"] = qpf
    parsed["cumulative_rain_24h_mm"] = qpf

    # Humidity — not in this API output, estimate from cloud cover + rain
    if qpf > 0 and parsed["cloud_cover_pct"] > 80:
        parsed["relative_humidity_pct"] = 85  # conservative estimate for rainy overcast
    elif parsed["cloud_cover_pct"] > 80:
        parsed["relative_humidity_pct"] = 75
    else:
        parsed["relative_humidity_pct"] = 55

    # Time of day (assume current observation)
    now = datetime.now()
    parsed["is_daytime"] = 6 <= now.hour <= 18
    parsed["is_early_morning_or_late_evening"] = (5 <= now.hour <= 8) or (17 <= now.hour <= 19)
    parsed["month"] = now.month
    parsed["hour"] = now.hour

    # Soil temperature proxy
    if parsed.get("temperature_c") is not None:
        parsed["soil_temp_estimate_c"] = parsed["temperature_c"] - 2

    # Rain probability estimate from current conditions
    if qpf > 5:
        parsed["rain_probability_today_pct"] = 80
        parsed["rain_probability_next_6h_pct"] = 60
        parsed["rain_probability_next_12h_pct"] = 60
    elif qpf > 1:
        parsed["rain_probability_today_pct"] = 60
        parsed["rain_probability_next_6h_pct"] = 40
        parsed["rain_probability_next_12h_pct"] = 40
    else:
        parsed["rain_probability_today_pct"] = 20
        parsed["rain_probability_next_6h_pct"] = 15
        parsed["rain_probability_next_12h_pct"] = 15

    # Consecutive dry hours — if it rained today, assume 0
    parsed["consecutive_dry_hours"] = 0 if qpf > 0 else 12

    return parsed


def evaluate_condition(condition: dict, weather: dict) -> bool:
    """Evaluate a single condition against weather data."""
    field = condition.get("field")
    op = condition.get("op")
    value = condition.get("value")

    if field not in weather:
        return False  # cannot evaluate — field missing

    actual = weather[field]

    if op == ">=":
        return actual >= value
    elif op == "<=":
        return actual <= value
    elif op == ">":
        return actual > value
    elif op == "<":
        return actual < value
    elif op == "==":
        return actual == value
    elif op == "!=":
        return actual != value
    elif op == "in":
        return actual in value
    else:
        return False


def evaluate_rule_conditions(weather_condition: dict, weather: dict) -> bool:
    """Recursively evaluate a rule's weather_condition block."""
    operator = weather_condition.get("operator", "AND")

    if operator == "ALWAYS":
        return True

    conditions = weather_condition.get("conditions", [])
    if not conditions:
        return False

    results = []
    for cond in conditions:
        if "operator" in cond and "conditions" in cond:
            # Nested condition group
            results.append(evaluate_rule_conditions(cond, weather))
        else:
            results.append(evaluate_condition(cond, weather))

    if operator == "AND":
        return all(results)
    elif operator == "OR":
        return any(results)
    return False


def evaluate_rules(weather: dict, rules_data: dict, calendar: dict = None,
                    variety: str = "Hass") -> list[dict]:
    """Evaluate all rules against current weather + calendar context.

    Steps:
      1. Load calendar context for current month + variety
      2. Enrich weather data with growth stage, disease/pest risk levels
      3. Evaluate weather-triggered rules
      4. Filter by growth stage relevance
      5. Generate calendar-triggered management rules (weather-gated)
      6. Merge and return
    """
    month = weather.get("month", datetime.now().month)

    # Step 1-2: Calendar enrichment
    calendar_ctx = {}
    if calendar:
        calendar_ctx = get_calendar_context(calendar, month, variety)
        weather = enrich_with_calendar(weather, calendar_ctx)

    # Step 3: Evaluate weather rules
    triggered = []
    for rule in rules_data["rules"]:
        wc = rule.get("weather_condition", {})
        if evaluate_rule_conditions(wc, weather):
            triggered.append(rule)

    # Step 4: Filter by growth stage
    active_stages = weather.get("_active_stages", {"all"})
    triggered = filter_rules_by_growth_stage(triggered, active_stages)

    # Step 5: Generate calendar rules
    if calendar_ctx:
        cal_rules = generate_calendar_rules(calendar_ctx, weather)
        triggered.extend(cal_rules)

    return triggered


def prioritize_and_resolve(triggered: list[dict], rules_data: dict) -> list[dict]:
    """Sort by priority and apply conflict resolution."""
    priority_order = {"critical": 0, "high": 1, "opportunity": 2, "medium": 3, "informational": 4, "low": 5}
    triggered.sort(key=lambda r: priority_order.get(r.get("priority", "low"), 5))

    # Deduplicate: if a calendar rule duplicates a weather rule's advice, keep the weather rule
    seen_categories = set()
    deduplicated = []
    for rule in triggered:
        # Weather rules take precedence over calendar rules for the same topic
        cat = rule.get("category", "")
        rule_id = rule.get("id", "")

        if cat == "CALENDAR_MANAGEMENT" and rule_id.endswith("-WAIT"):
            # Check if a corresponding weather opportunity rule already covers this
            base_activity = rule_id.replace("CAL-", "").replace("-WAIT", "").lower()
            if any(base_activity in r.get("id", "").lower() for r in deduplicated if r.get("category") != "CALENDAR_MANAGEMENT"):
                continue

        deduplicated.append(rule)

    return deduplicated


def format_advisory(triggered: list[dict], weather: dict) -> str:
    """Format triggered rules into a farmer-friendly advisory message."""
    if not triggered:
        return "No specific weather alerts for today. Continue standard orchard management."

    lines = []
    lines.append("=" * 60)
    lines.append("  AVOCADO FARM WEATHER ADVISORY")
    lines.append(f"  Date: {datetime.now().strftime('%A, %d %B %Y')}")
    lines.append("=" * 60)

    # Weather summary
    lines.append("")
    lines.append("TODAY'S CONDITIONS:")
    lines.append(f"  Temperature: {weather.get('temperature_min_c', '?')}°C - {weather.get('temperature_max_c', '?')}°C")
    lines.append(f"  Rainfall today: {weather.get('qpf_today_mm', 0)} mm")
    lines.append(f"  Wind: {weather.get('wind_speed_kmh', '?')} km/h (gusts: {weather.get('wind_gust_kmh', '?')} km/h)")
    lines.append(f"  Cloud cover: {weather.get('cloud_cover_pct', '?')}%")
    lines.append(f"  Est. humidity: {weather.get('relative_humidity_pct', '?')}%")
    lines.append("")

    # Group by priority
    critical = [r for r in triggered if r["priority"] == "critical"]
    high = [r for r in triggered if r["priority"] == "high"]
    opportunities = [r for r in triggered if r["priority"] == "opportunity"]
    medium = [r for r in triggered if r["priority"] == "medium"]
    info = [r for r in triggered if r["priority"] in ("informational", "low")]

    if critical:
        lines.append("-" * 60)
        lines.append("!! CRITICAL ALERTS !!")
        lines.append("-" * 60)
        for rule in critical:
            lines.append("")
            lines.append(f"  [{rule['id']}] {rule['name']}")
            lines.append(f"  Risk: {rule['risk']}")
            lines.append("  Actions:")
            for action in rule.get("actions", []):
                lines.append(f"    - {action}")

    if high:
        lines.append("")
        lines.append("-" * 60)
        lines.append(">> HIGH PRIORITY")
        lines.append("-" * 60)
        for rule in high:
            lines.append("")
            lines.append(f"  [{rule['id']}] {rule['name']}")
            lines.append(f"  Risk: {rule['risk']}")
            lines.append("  Actions:")
            for action in rule.get("actions", []):
                lines.append(f"    - {action}")

    if opportunities:
        lines.append("")
        lines.append("-" * 60)
        lines.append("++ OPPORTUNITIES")
        lines.append("-" * 60)
        for rule in opportunities:
            lines.append("")
            lines.append(f"  [{rule['id']}] {rule['name']}")
            lines.append("  Actions:")
            for action in rule.get("actions", []):
                lines.append(f"    - {action}")

    if medium:
        lines.append("")
        lines.append("-" * 60)
        lines.append("-- MONITOR")
        lines.append("-" * 60)
        for rule in medium:
            lines.append("")
            lines.append(f"  [{rule['id']}] {rule['name']}")
            lines.append(f"  Risk: {rule['risk']}")
            lines.append("  Actions:")
            for a in rule.get("actions", [])[:3]:
                lines.append(f"    - {a}")

    if info:
        lines.append("")
        lines.append("-" * 60)
        lines.append("   INFORMATION")
        lines.append("-" * 60)
        for rule in info:
            lines.append("")
            lines.append(f"  [{rule['id']}] {rule['name']}")
            lines.append("  Notes:")
            for a in rule.get("actions", [])[:2]:
                lines.append(f"    - {a}")

    lines.append("")
    lines.append("=" * 60)
    lines.append(f"  Rules evaluated: {len(triggered)} triggered")
    lines.append(f"  Sources: COLEAD, BIF-CDAAC, Griesbach/ICRAF, KALRO")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    weather_api_output = {
        "wind": {
            "speed": {"value": 2, "unit": "KILOMETERS_PER_HOUR"},
            "gust": {"value": 3, "unit": "KILOMETERS_PER_HOUR"}
        },
        "visibility": {"distance": 16, "unit": "KILOMETERS"},
        "cloudCover": 96,
        "currentConditionsHistory": {
            "temperatureChange": {"degrees": -1.7, "unit": "CELSIUS"},
            "maxTemperature": {"degrees": 18.8, "unit": "CELSIUS"},
            "minTemperature": {"degrees": 11, "unit": "CELSIUS"},
            "snowQpf": {"quantity": 0, "unit": "MILLIMETERS"},
            "qpf": {"quantity": 6.16, "unit": "MILLIMETERS"}
        }
    }

    # Parse weather
    weather = parse_weather_data(weather_api_output)

    # Load rules AND calendar
    rules_data = load_rules()
    calendar = load_calendar()

    # Run for both main varieties
    for variety in ["Hass", "Fuerte"]:
        print(f"\n{'='*60}")
        print(f"  ADVISORY FOR {variety.upper()} GROWERS")
        print(f"{'='*60}")

        # Get calendar context
        cal_ctx = get_calendar_context(calendar, weather["month"], variety)
        print(f"\n  Month: {cal_ctx.get('month_name')} | Season: {cal_ctx.get('season')}")
        print(f"  Growth stage ({variety}): {cal_ctx.get('growth_stage')}")
        print(f"  Disease risk: {cal_ctx.get('disease_risk')}")
        print(f"  Pest risk: {cal_ctx.get('pest_risk')}")

        # Evaluate with calendar integration
        weather_copy = weather.copy()  # don't mutate across varieties
        triggered = evaluate_rules(weather_copy, rules_data, calendar, variety)
        triggered = prioritize_and_resolve(triggered, rules_data)

        # Separate weather rules from calendar rules for display
        weather_rules = [r for r in triggered if r.get("source") != "crop_calendar"]
        calendar_rules = [r for r in triggered if r.get("source") == "crop_calendar"]

        print(f"\n  Weather rules triggered: {len(weather_rules)}")
        for r in weather_rules:
            print(f"    [{r['priority']:>13}] {r['id']:>10} — {r['name']}")

        print(f"\n  Calendar rules triggered: {len(calendar_rules)}")
        for r in calendar_rules:
            print(f"    [{r['priority']:>13}] {r['id']:>20} — {r['name']}")

        print(f"\n  TOTAL: {len(triggered)} rules")


if __name__ == "__main__":
    main()
