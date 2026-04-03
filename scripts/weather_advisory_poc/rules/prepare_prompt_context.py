"""
Prepares the template variables for the advisory prompt.

Takes a 5-day weather forecast, runs each day through the rule engine,
and produces the context dict that gets injected into the LLM prompt.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from evaluate_rules import (
    load_rules, parse_weather_data, evaluate_rules,
    prioritize_and_resolve,
)
from generate_advisory import enrich_weather_with_context


def evaluate_forecast(forecast_days: list[dict], rules_data: dict) -> list[dict]:
    """Evaluate rules for each day in the 5-day forecast.

    Args:
        forecast_days: List of 5 raw weather API dicts, one per day
        rules_data: The loaded rules JSON

    Returns:
        List of dicts, one per day, each containing:
          - date, day_name, weather (parsed), triggered (rules)
    """
    results = []
    cumulative_rain = 0
    consecutive_dry = 0
    consecutive_wet = 0

    for i, day_raw in enumerate(forecast_days):
        weather = parse_weather_data(day_raw)

        # Override month/date for each forecast day
        day_date = datetime.now() + timedelta(days=i)
        weather["month"] = day_date.month
        weather["day_of_week"] = day_date.strftime("%A")
        weather["date_str"] = day_date.strftime("%d %b")

        # Build rolling cumulative fields from the forecast sequence
        day_rain = weather.get("qpf_today_mm", 0)
        cumulative_rain += day_rain

        if day_rain < 1:
            consecutive_dry += 1
            consecutive_wet = 0
        else:
            consecutive_wet += 1
            consecutive_dry = 0

        weather["cumulative_rain_72h_mm"] = cumulative_rain if i < 3 else sum(
            parse_weather_data(forecast_days[j]).get("qpf_today_mm", 0)
            for j in range(max(0, i - 2), i + 1)
        )
        weather["cumulative_rain_7d_mm"] = cumulative_rain
        weather["cumulative_rain_14d_mm"] = cumulative_rain * 2  # rough estimate
        weather["cumulative_rain_48h_mm"] = sum(
            parse_weather_data(forecast_days[j]).get("qpf_today_mm", 0)
            for j in range(max(0, i - 1), i + 1)
        )
        weather["consecutive_dry_days"] = consecutive_dry
        weather["consecutive_wet_days"] = consecutive_wet

        # Hours since rain: 0 if raining today, else ~24 * consecutive dry days
        weather["hours_since_last_rain"] = 0 if day_rain > 0 else consecutive_dry * 24

        # Enrich with seasonal context
        weather = enrich_weather_with_context(weather)

        # Evaluate rules
        triggered = evaluate_rules(weather, rules_data)
        triggered = prioritize_and_resolve(triggered, rules_data)

        results.append({
            "day_index": i,
            "date": day_date,
            "day_name": "Today" if i == 0 else day_date.strftime("%A"),
            "date_str": weather["date_str"],
            "weather": weather,
            "triggered": triggered,
        })

    return results


def identify_best_spray_day(daily_results: list[dict]) -> int | None:
    """Find the best day for spraying across the 5-day forecast."""
    best_day = None
    best_score = -1

    for day in daily_results:
        w = day["weather"]
        rain_prob = w.get("rain_probability_today_pct", 50)
        wind = w.get("wind_speed_kmh", 0)
        rain_mm = w.get("qpf_today_mm", 0)

        # Score: lower rain + lower wind = better spray day
        if rain_mm < 2 and wind < 15:
            score = (100 - rain_prob) + (15 - wind)
            if score > best_score:
                best_score = score
                best_day = day["day_index"]

    return best_day


def identify_best_harvest_day(daily_results: list[dict]) -> int | None:
    """Find the best day for harvesting across the 5-day forecast."""
    best_day = None
    best_score = -1

    for day in daily_results:
        w = day["weather"]
        rain_prob = w.get("rain_probability_today_pct", 50)
        rain_mm = w.get("qpf_today_mm", 0)
        wind = w.get("wind_speed_kmh", 0)
        temp_max = w.get("temperature_max_c", 30)
        dry_hours = w.get("consecutive_dry_hours", 0)

        if rain_mm < 1 and wind < 20 and temp_max < 28:
            score = (100 - rain_prob) + dry_hours + (20 - wind)
            if score > best_score:
                best_score = score
                best_day = day["day_index"]

    return best_day


def build_prompt_context(
    daily_results: list[dict],
    rules_data: dict,
    location: str,
    language: str = "en",
    farmer_variety: str = "Hass",
    growth_stage: str = "fruit_enlargement",
) -> dict:
    """Build the full context dict for template injection into the LLM prompt."""

    best_spray = identify_best_spray_day(daily_results)
    best_harvest = identify_best_harvest_day(daily_results)

    # Collect all triggered rules across all 5 days, deduplicated
    all_triggered_ids = set()
    all_triggered = []
    for day in daily_results:
        for rule in day["triggered"]:
            if rule["id"] not in all_triggered_ids:
                all_triggered_ids.add(rule["id"])
                all_triggered.append(rule)

    # Format triggered rules for the prompt
    triggered_lines = []
    for rule in sorted(all_triggered, key=lambda r:
        {"critical": 0, "high": 1, "opportunity": 2, "medium": 3, "informational": 4, "low": 5}.get(r["priority"], 5)):

        # Which days does this rule fire?
        firing_days = []
        for day in daily_results:
            if any(r["id"] == rule["id"] for r in day["triggered"]):
                firing_days.append(day["day_name"])

        triggered_lines.append(
            f"[{rule['priority'].upper()}] {rule['id']} — {rule['name']}\n"
            f"  Fires on: {', '.join(firing_days)}\n"
            f"  Risk: {rule['risk']}\n"
            f"  Actions:\n" +
            "\n".join(f"    - {a}" for a in rule.get("actions", [])) +
            "\n"
        )

    # Format avoid actions
    avoid_lines = []
    for day in daily_results:
        w = day["weather"]
        day_label = day["day_name"]
        if w.get("qpf_today_mm", 0) > 3:
            avoid_lines.append(f"{day_label}: Do NOT harvest — wet conditions increase stem end rot risk")
            avoid_lines.append(f"{day_label}: Do NOT spray — rain will wash off product before it dries (needs 4-6 dry hours)")
        if w.get("relative_humidity_pct", 0) >= 80:
            avoid_lines.append(f"{day_label}: Do NOT use overhead irrigation — canopy already wet")
        if w.get("temperature_c", 20) < 16:
            avoid_lines.append(f"{day_label}: Do NOT spray insecticides near flowering trees — bees inactive in cold")

    # Format conflict resolutions
    conflict_lines = []
    for cr in rules_data.get("conflict_resolution", {}).get("rules", []):
        conflict_lines.append(f"- {cr['conflict']}: {cr['resolution']}")

    # Format 5-day weather summary
    weather_5day_lines = []
    for day in daily_results:
        w = day["weather"]
        weather_5day_lines.append(
            f"{day['day_name']} ({day['date_str']}): "
            f"{w.get('temperature_min_c', '?')}–{w.get('temperature_max_c', '?')}°C, "
            f"Rain: {w.get('qpf_today_mm', 0)}mm, "
            f"Wind: {w.get('wind_speed_kmh', 0)}km/h (gust {w.get('wind_gust_kmh', 0)}km/h), "
            f"Cloud: {w.get('cloud_cover_pct', 0)}%, "
            f"Humidity: ~{w.get('relative_humidity_pct', '?')}%"
        )

    # Spray/harvest window annotations
    if best_spray is not None:
        spray_note = f"Best spray day: {daily_results[best_spray]['day_name']} ({daily_results[best_spray]['date_str']})"
    else:
        spray_note = "No good spray window in the next 5 days — focus on drainage, scouting, and cultural controls"

    if best_harvest is not None:
        harvest_note = f"Best harvest day: {daily_results[best_harvest]['day_name']} ({daily_results[best_harvest]['date_str']})"
    else:
        harvest_note = "No ideal harvest day — if urgent, pick in the driest morning window and pre-cool immediately"

    weather_5day_lines.append("")
    weather_5day_lines.append(spray_note)
    weather_5day_lines.append(harvest_note)

    # Date range
    d0 = daily_results[0]["date"]
    d4 = daily_results[-1]["date"]
    date_range = f"{d0.strftime('%d %b')} – {d4.strftime('%d %b %Y')}"

    return {
        "location": location,
        "full_location_name": location,
        "language": language,
        "farmer_variety": farmer_variety,
        "growth_stage": growth_stage,
        "today_date": datetime.now().strftime("%Y-%m-%d"),
        "date_range": date_range,
        "weather_data_5day": "\n".join(weather_5day_lines),
        "triggered_rules": "\n".join(triggered_lines),
        "conflict_resolutions": "\n".join(conflict_lines),
        "avoid_actions": "\n".join(sorted(set(avoid_lines))),
    }


def render_prompt(template_path: str, context: dict) -> str:
    """Simple {{ var }} template rendering."""
    with open(template_path) as f:
        template = f.read()
    for key, value in context.items():
        template = template.replace("{{ " + key + " }}", str(value))
        template = template.replace("{{" + key + "}}", str(value))
    return template


# ── Demo with the user's sample weather data ──────────────────────────

def main():
    # Simulate 5-day forecast using the provided weather as day 1,
    # with realistic variations for days 2-5
    day1 = {
        "wind": {"speed": {"value": 2}, "gust": {"value": 3}},
        "cloudCover": 96,
        "currentConditionsHistory": {
            "temperatureChange": {"degrees": -1.7},
            "maxTemperature": {"degrees": 18.8},
            "minTemperature": {"degrees": 11},
            "qpf": {"quantity": 6.16},
            "snowQpf": {"quantity": 0}
        }
    }
    day2 = {
        "wind": {"speed": {"value": 5}, "gust": {"value": 8}},
        "cloudCover": 88,
        "currentConditionsHistory": {
            "temperatureChange": {"degrees": 0.5},
            "maxTemperature": {"degrees": 20.2},
            "minTemperature": {"degrees": 12.5},
            "qpf": {"quantity": 8.4},
            "snowQpf": {"quantity": 0}
        }
    }
    day3 = {
        "wind": {"speed": {"value": 3}, "gust": {"value": 6}},
        "cloudCover": 70,
        "currentConditionsHistory": {
            "temperatureChange": {"degrees": 1.2},
            "maxTemperature": {"degrees": 22.1},
            "minTemperature": {"degrees": 13.8},
            "qpf": {"quantity": 1.2},
            "snowQpf": {"quantity": 0}
        }
    }
    day4 = {
        "wind": {"speed": {"value": 4}, "gust": {"value": 7}},
        "cloudCover": 45,
        "currentConditionsHistory": {
            "temperatureChange": {"degrees": 2.0},
            "maxTemperature": {"degrees": 24.5},
            "minTemperature": {"degrees": 14.0},
            "qpf": {"quantity": 0},
            "snowQpf": {"quantity": 0}
        }
    }
    day5 = {
        "wind": {"speed": {"value": 6}, "gust": {"value": 10}},
        "cloudCover": 60,
        "currentConditionsHistory": {
            "temperatureChange": {"degrees": -0.5},
            "maxTemperature": {"degrees": 23.0},
            "minTemperature": {"degrees": 13.5},
            "qpf": {"quantity": 3.8},
            "snowQpf": {"quantity": 0}
        }
    }

    forecast = [day1, day2, day3, day4, day5]

    # Load rules
    rules_data = load_rules()

    # Evaluate all 5 days
    daily_results = evaluate_forecast(forecast, rules_data)

    # Build prompt context
    context = build_prompt_context(
        daily_results=daily_results,
        rules_data=rules_data,
        location="Kariara, Gatanga, Murang'a",
        language="en",
        farmer_variety="Hass",
        growth_stage="fruit_enlargement",
    )

    # Render the prompt
    prompt = render_prompt(
        str(Path(__file__).parent / "advisory_prompt.txt"),
        context
    )

    print("=" * 70)
    print("RENDERED PROMPT (what gets sent to the LLM):")
    print("=" * 70)
    print(prompt)

    # Also print key stats
    print("\n\n" + "=" * 70)
    print("STATS:")
    print("=" * 70)
    for day in daily_results:
        ids = [r["id"] for r in day["triggered"]]
        print(f"  {day['day_name']:>10} ({day['date_str']}): {len(ids)} rules — {', '.join(ids)}")

    best_spray = identify_best_spray_day(daily_results)
    best_harvest = identify_best_harvest_day(daily_results)
    print(f"\n  Best spray day:   {'Day ' + str(best_spray) + ' (' + daily_results[best_spray]['day_name'] + ')' if best_spray is not None else 'None'}")
    print(f"  Best harvest day: {'Day ' + str(best_harvest) + ' (' + daily_results[best_harvest]['day_name'] + ')' if best_harvest is not None else 'None'}")


if __name__ == "__main__":
    main()
