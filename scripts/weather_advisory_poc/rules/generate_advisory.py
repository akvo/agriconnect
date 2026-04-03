"""
Generate a complete farmer-friendly advisory from weather data + rules.

Enriches the raw weather API output with reasonable defaults for fields
the API doesn't provide, and generates an advisory that accounts for
the current month/season in Kenya.
"""

import json
from datetime import datetime
from pathlib import Path
from evaluate_rules import (
    load_rules, parse_weather_data, evaluate_rules,
    prioritize_and_resolve
)


def enrich_weather_with_context(weather: dict) -> dict:
    """Add seasonal context and reasonable defaults for missing fields
    that the single-snapshot API doesn't provide."""

    # Kenya seasonal context for March
    month = weather.get("month", datetime.now().month)

    # March = onset of long rains in Kenya
    if month in [3, 4, 5]:
        weather.setdefault("season", "long_rains")
        weather.setdefault("days_until_rainy_season_onset", 0)  # we're in it
        weather.setdefault("rainy_season_onset", True)
        # During long rains, consecutive dry days are typically low
        weather.setdefault("consecutive_dry_days", 1)
        weather.setdefault("consecutive_wet_days", 3)
        weather.setdefault("cumulative_rain_72h_mm", weather.get("qpf_today_mm", 0) * 2.5)
        weather.setdefault("cumulative_rain_7d_mm", weather.get("qpf_today_mm", 0) * 4)
        weather.setdefault("cumulative_rain_14d_mm", weather.get("qpf_today_mm", 0) * 7)
        weather.setdefault("cumulative_rain_48h_mm", weather.get("qpf_today_mm", 0) * 1.8)
        weather.setdefault("hours_since_last_rain", 2)
        weather.setdefault("rain_probability_next_24h_pct", 70)
        weather.setdefault("rain_probability_next_48h_pct", 65)
    elif month in [6, 7, 8, 9]:
        weather.setdefault("season", "long_dry")
        weather.setdefault("consecutive_dry_days", 10)
        weather.setdefault("consecutive_wet_days", 0)
    elif month in [10, 11, 12]:
        weather.setdefault("season", "short_rains")
        weather.setdefault("days_until_rainy_season_onset", 0)
        weather.setdefault("consecutive_dry_days", 2)
    else:
        weather.setdefault("season", "short_dry")
        weather.setdefault("consecutive_dry_days", 12)

    # Growth stage — March in Kenya is typically:
    #   Fuerte: harvest season (Mar-May)
    #   Hass: fruit enlargement (flowering was Oct, harvest Jun-Sep)
    # We'll flag both
    weather.setdefault("growth_stage_fuerte", "harvest")
    weather.setdefault("growth_stage_hass", "fruit_enlargement")

    return weather


def generate_farmer_advisory(weather: dict, triggered: list[dict]) -> str:
    """Generate a natural-language advisory optimized for farmers."""
    lines = []

    month = weather.get("month", 3)
    season = weather.get("season", "unknown")
    season_label = {
        "long_rains": "Long Rains Season",
        "long_dry": "Long Dry Season",
        "short_rains": "Short Rains Season",
        "short_dry": "Short Dry Season"
    }.get(season, "")

    lines.append("=" * 60)
    lines.append("     DAILY AVOCADO FARM ADVISORY")
    lines.append(f"     {datetime.now().strftime('%A, %d %B %Y')}")
    lines.append(f"     Season: {season_label}")
    lines.append("=" * 60)
    lines.append("")

    # Weather summary in plain language
    temp_min = weather.get("temperature_min_c", "?")
    temp_max = weather.get("temperature_max_c", "?")
    rain = weather.get("qpf_today_mm", 0)
    wind = weather.get("wind_speed_kmh", 0)
    clouds = weather.get("cloud_cover_pct", 0)
    humidity = weather.get("relative_humidity_pct", "?")

    lines.append("WEATHER SUMMARY")
    lines.append("-" * 40)

    # Temperature description
    avg_temp = weather.get("temperature_c", 15)
    if avg_temp < 15:
        temp_desc = "Cool"
    elif avg_temp < 20:
        temp_desc = "Mild"
    elif avg_temp < 28:
        temp_desc = "Warm"
    else:
        temp_desc = "Hot"

    lines.append(f"  {temp_desc} day: {temp_min}°C to {temp_max}°C")

    if rain > 10:
        lines.append(f"  Heavy rain: {rain} mm")
    elif rain > 3:
        lines.append(f"  Moderate rain: {rain} mm")
    elif rain > 0:
        lines.append(f"  Light rain: {rain} mm")
    else:
        lines.append("  No rain")

    if wind < 5:
        lines.append(f"  Calm winds: {wind} km/h")
    elif wind < 20:
        lines.append(f"  Light winds: {wind} km/h")
    else:
        lines.append(f"  Strong winds: {wind} km/h — take care")

    lines.append(f"  Cloud cover: {clouds}% | Humidity: ~{humidity}%")
    lines.append("")

    # Seasonal context
    lines.append("SEASONAL CONTEXT")
    lines.append("-" * 40)
    if month == 3:
        lines.append("  March marks the start of the Long Rains in Kenya.")
        lines.append("  Fuerte: HARVEST SEASON — check fruit maturity")
        lines.append("  Hass: Fruit enlargement stage — protect developing fruit")
        lines.append("")

    # Group rules by actionability
    critical = [r for r in triggered if r["priority"] == "critical"]
    high = [r for r in triggered if r["priority"] == "high"]
    opportunities = [r for r in triggered if r["priority"] == "opportunity"]
    medium = [r for r in triggered if r["priority"] == "medium"]
    info = [r for r in triggered if r["priority"] in ("informational", "low")]

    # URGENT
    if critical:
        lines.append("!!" + "=" * 56 + "!!")
        lines.append("  URGENT — ACT TODAY")
        lines.append("!!" + "=" * 56 + "!!")
        for rule in critical:
            lines.append("")
            lines.append(f"  >> {rule['name'].upper()}")
            # Summarize risk in 1 line
            risk = rule.get("risk", "")
            if len(risk) > 120:
                risk = risk[:117] + "..."
            lines.append(f"     Why: {risk}")
            lines.append("     What to do:")
            for action in rule.get("actions", []):
                lines.append(f"       * {action}")
        lines.append("")

    # HIGH
    if high:
        lines.append("=" * 60)
        lines.append("  IMPORTANT — TAKE ACTION")
        lines.append("=" * 60)
        for rule in high:
            lines.append("")
            lines.append(f"  >> {rule['name']}")
            risk = rule.get("risk", "")
            if len(risk) > 150:
                risk = risk[:147] + "..."
            lines.append(f"     Why: {risk}")
            lines.append("     What to do:")
            for action in rule.get("actions", []):
                lines.append(f"       * {action}")
        lines.append("")

    # OPPORTUNITIES
    if opportunities:
        lines.append("=" * 60)
        lines.append("  GOOD NEWS — OPPORTUNITIES TODAY")
        lines.append("=" * 60)
        for rule in opportunities:
            lines.append("")
            lines.append(f"  >> {rule['name']}")
            lines.append("     Actions:")
            for action in rule.get("actions", []):
                lines.append(f"       * {action}")
        lines.append("")

    # MONITOR
    if medium:
        lines.append("=" * 60)
        lines.append("  KEEP AN EYE ON")
        lines.append("=" * 60)
        for rule in medium:
            lines.append("")
            lines.append(f"  >> {rule['name']}")
            risk = rule.get("risk", "")
            if len(risk) > 120:
                risk = risk[:117] + "..."
            lines.append(f"     {risk}")
            lines.append("     Suggested:")
            for a in rule.get("actions", [])[:3]:
                lines.append(f"       * {a}")
        lines.append("")

    # INFO
    if info:
        lines.append("-" * 60)
        lines.append("  REMINDERS")
        lines.append("-" * 60)
        for rule in info:
            lines.append(f"  - {rule['name']}")
            if rule.get("actions"):
                lines.append(f"    {rule['actions'][0]}")
        lines.append("")

    # What NOT to do today
    lines.append("=" * 60)
    lines.append("  AVOID TODAY")
    lines.append("=" * 60)
    avoid = []
    if rain > 3:
        avoid.append("Do NOT harvest in wet conditions — wait for a dry day (stem end rot risk)")
    if rain > 0:
        avoid.append("Do NOT spray fungicides/pesticides — rain will wash off the product")
    if avg_temp < 16:
        avoid.append("Do NOT spray insecticides near flowering trees — bees are already less active in cool weather")
    if humidity >= 80:
        avoid.append("Do NOT use overhead irrigation — canopy is already wet, promoting fungal disease")

    if avoid:
        for a in avoid:
            lines.append(f"  * {a}")
    else:
        lines.append("  No specific restrictions today.")
    lines.append("")

    # Coming days outlook
    lines.append("=" * 60)
    lines.append("  LOOK AHEAD")
    lines.append("=" * 60)
    if season == "long_rains":
        lines.append("  The Long Rains are underway. Expect continued wet conditions.")
        lines.append("  Priority actions for the coming week:")
        lines.append("    1. Check ALL drainage channels are clear — Phytophthora risk rises")
        lines.append("       with every day of wet soil")
        lines.append("    2. Watch for the first dry window (4+ hours no rain, low wind)")
        lines.append("       to apply copper fungicide for anthracnose prevention")
        lines.append("    3. If Fuerte is at harvest maturity, pick on the first dry morning")
        lines.append("    4. Monitor Hass fruit for cercospora spots — wet + warm conditions")
        lines.append("       favour the disease")
    lines.append("")

    lines.append("=" * 60)
    lines.append(f"  {len(triggered)} rules triggered from 75 evaluated")
    lines.append("  Sources: COLEAD, BIF-CDAAC, Griesbach/ICRAF, KALRO")
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

    # Parse and enrich weather data
    weather = parse_weather_data(weather_api_output)
    weather = enrich_weather_with_context(weather)

    # Evaluate rules
    rules_data = load_rules()
    triggered = evaluate_rules(weather, rules_data)
    triggered = prioritize_and_resolve(triggered, rules_data)

    # Generate advisory
    advisory = generate_farmer_advisory(weather, triggered)
    print(advisory)

    print("\n\nDEBUG — All triggered rules:")
    for r in triggered:
        print(f"  [{r['priority']:>13}] {r['id']:>10} — {r['name']}")


if __name__ == "__main__":
    main()
