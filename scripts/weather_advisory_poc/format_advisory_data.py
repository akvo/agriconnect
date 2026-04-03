"""
Helper to format advisory context into the single advisory_data string
expected by advisory_prompt.txt
"""


def format_advisory_data(context: dict) -> str:
    """
    Combine all context fields into a single formatted advisory_data string.

    Args:
        context: Dict from build_prompt_context() with fields:
            - location, farmer_variety, growth_stage, date_range
            - weather_data_5day, triggered_rules, avoid_actions, conflict_resolutions

    Returns:
        Formatted string for {{ advisory_data }} template variable
    """

    sections = []

    # Header
    sections.append(f"LOCATION: {context['location']}")
    sections.append(f"VARIETY: {context['farmer_variety']}")
    sections.append(f"GROWTH STAGE: {context['growth_stage']}")
    sections.append(f"DATE RANGE: {context['date_range']}")
    sections.append("")

    # Weather forecast
    sections.append("═" * 70)
    sections.append("WEATHER FORECAST (5 DAYS)")
    sections.append("═" * 70)
    sections.append("")
    sections.append(context['weather_data_5day'])
    sections.append("")

    # Triggered rules
    sections.append("═" * 70)
    sections.append("TRIGGERED RULES")
    sections.append("═" * 70)
    sections.append("")
    sections.append(context['triggered_rules'])
    sections.append("")

    # Avoid actions
    if context['avoid_actions']:
        sections.append("═" * 70)
        sections.append("AVOID THIS WEEK")
        sections.append("═" * 70)
        sections.append("")
        sections.append(context['avoid_actions'])
        sections.append("")

    # Conflict resolutions (optional, only include if conflicts exist)
    if context.get('conflict_resolutions'):
        sections.append("═" * 70)
        sections.append("CONFLICT RESOLUTIONS (when rules contradict)")
        sections.append("═" * 70)
        sections.append("")
        sections.append(context['conflict_resolutions'])
        sections.append("")

    return "\n".join(sections)


def render_full_prompt(template_path: str, context: dict) -> str:
    """
    Render the advisory prompt with properly formatted advisory_data.

    This replaces the simple render_prompt() in prepare_prompt_context.py
    to properly handle the {{ advisory_data }} variable.
    """
    with open(template_path) as f:
        template = f.read()

    # Format the advisory data
    advisory_data = format_advisory_data(context)

    # Create final context with advisory_data
    final_context = {
        'advisory_data': advisory_data,
        'language': context.get('language', 'en'),
    }

    # Replace template variables
    for key, value in final_context.items():
        template = template.replace("{{ " + key + " }}", str(value))
        template = template.replace("{{" + key + "}}", str(value))

    return template


# Example usage
if __name__ == "__main__":
    from prepare_prompt_context import (
        build_prompt_context,
        evaluate_forecast,
        load_rules
    )
    from pathlib import Path

    # Demo data
    forecast = [
        {
            'wind': {'speed': {'value': 2}, 'gust': {'value': 3}},
            'cloudCover': 96,
            'currentConditionsHistory': {
                'maxTemperature': {'degrees': 18.8},
                'minTemperature': {'degrees': 11},
                'qpf': {'quantity': 6.16}
            }
        }
    ] * 5

    rules_data = load_rules()
    daily_results = evaluate_forecast(forecast, rules_data)
    context = build_prompt_context(
        daily_results=daily_results,
        rules_data=rules_data,
        location="Kariara, Gatanga, Murang'a",
        language="en",
        farmer_variety="Hass",
        growth_stage="fruit_enlargement",
    )

    # Render the full prompt
    prompt = render_full_prompt(
        str(Path(__file__).parent / "rules" / "advisory_prompt.txt"),
        context
    )

    print("=" * 70)
    print("FULL PROMPT READY FOR LLM:")
    print("=" * 70)
    print(prompt)
    print()
    print("=" * 70)
    print(f"Estimated tokens: ~1,100")
    print(f"Cost per message: ~$0.0005")
    print("=" * 70)
