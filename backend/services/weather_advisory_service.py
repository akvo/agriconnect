"""
Weather Advisory Service

Rule-based weather advisory system for avocado cultivation.
Evaluates 75 agronomic rules against weather conditions and crop calendar.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

# Path to data files
DATA_DIR = Path(__file__).parent.parent / "data"


class WeatherAdvisoryService:
    """Service for evaluating weather rules and generating advisories."""

    def __init__(self):
        self._rules_cache = {}  # Cache by crop type
        self._calendar_cache = {}  # Cache by crop type

    def load_rules(self, crop: str = "avocado") -> dict:
        """
        Load weather rules JSON for specific crop.

        Args:
            crop: Crop type (avocado, potato)

        Returns:
            Rules data dict
        """
        crop = crop.lower()
        if crop not in self._rules_cache:
            rules_file = DATA_DIR / f"{crop}_weather_rules.json"
            try:
                with open(rules_file, "r", encoding="utf-8") as f:
                    self._rules_cache[crop] = json.load(f)
                rule_count = len(self._rules_cache[crop].get('rules', []))
                logger.info(
                    f"Loaded {rule_count} {crop} weather rules"
                )
            except Exception as e:
                logger.error(f"Failed to load {crop} rules: {e}")
                self._rules_cache[crop] = {"rules": []}
        return self._rules_cache[crop]

    def load_calendar(self, crop: str = "avocado") -> dict:
        """
        Load crop calendar JSON for specific crop.

        Args:
            crop: Crop type (avocado, potato)

        Returns:
            Calendar data dict
        """
        crop = crop.lower()
        if crop not in self._calendar_cache:
            calendar_file = DATA_DIR / f"{crop}_crop_calendar.json"
            try:
                with open(calendar_file, "r", encoding="utf-8") as f:
                    self._calendar_cache[crop] = json.load(f)
                logger.info(f"Loaded {crop} crop calendar")
            except Exception as e:
                logger.error(f"Failed to load {crop} calendar: {e}")
                self._calendar_cache[crop] = {"monthly_calendar": {}}
        return self._calendar_cache[crop]

    def get_growth_stage(
        self, month: int, crop: str = "avocado", variety: str = None
    ) -> dict:
        """
        Get current growth stages from crop calendar for ALL varieties.

        Args:
            month: Month number (1-12)
            crop: Crop type (avocado, potato)
            variety: Ignored - returns all varieties

        Returns:
            Dict of variety -> growth stage
        """
        calendar = self.load_calendar(crop)
        month_data = calendar.get("monthly_calendar", {}).get(str(month), {})
        phenology = month_data.get("phenology", {})
        return phenology

    def get_calendar_context(
        self, month: int, crop: str = "avocado", variety: str = None
    ) -> dict:
        """
        Extract month context from crop calendar.

        Args:
            month: Month number (1-12)
            crop: Crop type (avocado, potato)
            variety: Ignored - returns context for ALL varieties
        """
        calendar = self.load_calendar(crop)
        month_data = calendar.get("monthly_calendar", {}).get(str(month), {})

        if not month_data:
            return {}

        phenology = month_data.get("phenology", {})

        # Get all growth stages for all varieties (don't filter)
        all_growth_stages = phenology

        # Extract high-priority management tasks
        mgmt = month_data.get("management", {})
        management_due = []
        for activity, details in mgmt.items():
            if details.get("priority") in ("critical", "high"):
                management_due.append(
                    {
                        "activity": activity,
                        "priority": details["priority"],
                        "action": details["action"],
                    }
                )

        return {
            "growth_stages_all": all_growth_stages,  # All varieties' stages
            "season": month_data.get("season", "unknown"),
            "month_name": month_data.get("month_name", ""),
            "management_due": management_due,
            "disease_risk": month_data.get("disease_risk", {}),
            "pest_risk": month_data.get("pest_risk", {}),
            "phenology_all": phenology,
        }

    def _map_growth_stage_to_tags(self, growth_stage: str) -> Set[str]:
        """Map calendar growth stage to rule stage tags."""
        stage_tags = {"all"}
        stage = growth_stage.lower()

        if "flowering" in stage:
            stage_tags.update(["flowering", "pre_harvest"])
        if "fruit_set" in stage:
            stage_tags.update(["fruit_set", "fruit_enlargement"])
        if "fruit_development" in stage or "fruit_enlargement" in stage:
            stage_tags.update(
                ["fruit_enlargement", "fruit_development"]
            )
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

        return stage_tags

    def _enrich_weather_with_calendar(
        self, weather: dict, calendar_ctx: dict
    ) -> dict:
        """Inject calendar context into weather data."""
        # Get all growth stages from all varieties
        all_stages = calendar_ctx.get("growth_stages_all", {})
        weather["growth_stages_all"] = all_stages
        weather["season_name"] = calendar_ctx.get("season", "unknown")

        # Collect all unique stage tags across ALL varieties
        all_stage_tags = set()
        for variety, stage in all_stages.items():
            tags = self._map_growth_stage_to_tags(stage)
            all_stage_tags.update(tags)

        weather["_active_stages"] = all_stage_tags

        # Inject disease/pest risk levels
        for disease, level in calendar_ctx.get("disease_risk", {}).items():
            weather[f"disease_risk_{disease}"] = level
        for pest, level in calendar_ctx.get("pest_risk", {}).items():
            weather[f"pest_risk_{pest}"] = level

        return weather

    def _evaluate_condition(
        self, condition: dict, weather: dict
    ) -> bool:
        """Evaluate a single condition against weather data."""
        try:
            field = condition.get("field")
            op = condition.get("op")
            value = condition.get("value")

            if field not in weather:
                return False

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
        except Exception as e:
            logger.debug(f"Condition evaluation error: {e}")
            return False

    def _evaluate_rule_conditions(
        self, weather_condition: dict, weather: dict
    ) -> bool:
        """Recursively evaluate rule's weather_condition block."""
        try:
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
                    results.append(
                        self._evaluate_rule_conditions(cond, weather)
                    )
                else:
                    results.append(self._evaluate_condition(cond, weather))

            if operator == "AND":
                return all(results)
            elif operator == "OR":
                return any(results)
            return False
        except Exception as e:
            logger.debug(f"Rule condition evaluation error: {e}")
            return False

    def _filter_by_growth_stage(
        self, triggered: List[dict], active_stages: Set[str]
    ) -> List[dict]:
        """Filter rules by current growth stage."""
        filtered = []
        for rule in triggered:
            crop_ctx = rule.get("crop_context", {})
            applies_to = crop_ctx.get("applies_to_stages")

            if applies_to is None:
                filtered.append(rule)
            elif "all" in applies_to:
                filtered.append(rule)
            elif active_stages.intersection(set(applies_to)):
                filtered.append(rule)

        return filtered

    def _generate_calendar_rules(
        self, calendar_ctx: dict, weather: dict
    ) -> List[dict]:
        """Generate management task rules from calendar, gated by weather."""
        rules = []
        rain = weather.get("qpf_today_mm", 0)
        wind = weather.get("wind_speed_kmh", 0)
        humidity = weather.get("relative_humidity_pct", 50)

        for task in calendar_ctx.get("management_due", []):
            activity = task["activity"]
            action = task["action"]
            priority = task["priority"]

            try:
                if activity == "pruning":
                    if rain < 2 and humidity < 75:
                        rules.append(
                            {
                                "id": f"CAL-{activity.upper()}",
                                "category": "CALENDAR_MANAGEMENT",
                                "name": (
                                    "Calendar: Pruning due — "
                                    "good conditions today"
                                ),
                                "priority": priority,
                                "risk": "none",
                                "actions": [
                                    action,
                                    "Sterilise tools (20% bleach)",
                                ],
                                "source": "crop_calendar",
                            }
                        )

                elif activity == "spraying":
                    if rain < 2 and wind < 15:
                        rules.append(
                            {
                                "id": f"CAL-{activity.upper()}",
                                "category": "CALENDAR_MANAGEMENT",
                                "name": (
                                    "Calendar: Spray program due — "
                                    "good window today"
                                ),
                                "priority": priority,
                                "risk": "none",
                                "actions": [
                                    action,
                                    "Apply early morning or late evening",
                                ],
                                "source": "crop_calendar",
                            }
                        )

                elif activity == "irrigation":
                    if rain < 3:
                        rules.append(
                            {
                                "id": f"CAL-{activity.upper()}",
                                "category": "CALENDAR_MANAGEMENT",
                                "name": "Calendar: Irrigation needed",
                                "priority": priority,
                                "risk": "Moisture stress reduces fruit size",
                                "actions": [action],
                                "source": "crop_calendar",
                            }
                        )

                elif activity == "harvest":
                    if rain < 1 and wind < 20:
                        rules.append(
                            {
                                "id": f"CAL-{activity.upper()}",
                                "category": "CALENDAR_MANAGEMENT",
                                "name": (
                                    "Calendar: Harvest season — "
                                    "good conditions"
                                ),
                                "priority": priority,
                                "risk": "none",
                                "actions": [
                                    action,
                                    "Harvest when fruit is cool",
                                ],
                                "source": "crop_calendar",
                            }
                        )

                elif activity == "fertilizer":
                    if rain > 0:
                        rules.append(
                            {
                                "id": f"CAL-{activity.upper()}",
                                "category": "CALENDAR_MANAGEMENT",
                                "name": (
                                    "Calendar: Fertilizer due — "
                                    "soil is moist"
                                ),
                                "priority": priority,
                                "risk": "none",
                                "actions": [action],
                                "source": "crop_calendar",
                            }
                        )

                else:
                    # Generic calendar task
                    activity_name = activity.replace('_', ' ').title()
                    rules.append(
                        {
                            "id": f"CAL-{activity.upper()}",
                            "category": "CALENDAR_MANAGEMENT",
                            "name": f"Calendar: {activity_name}",
                            "priority": priority,
                            "risk": "",
                            "actions": [action],
                            "source": "crop_calendar",
                        }
                    )
            except Exception as e:
                logger.warning(
                    f"Error generating calendar rule for {activity}: {e}"
                )
                continue

        # Add disease/pest alerts
        disease_risk = calendar_ctx.get("disease_risk", {})
        high_diseases = [
            d
            for d, level in disease_risk.items()
            if level in ("high", "very_high")
        ]
        if high_diseases:
            rules.append(
                {
                    "id": "CAL-DISEASE-ALERT",
                    "category": "CALENDAR_MANAGEMENT",
                    "name": "Elevated disease risk this month",
                    "priority": "high",
                    "risk": f"High risk: {', '.join(high_diseases)}",
                    "actions": [
                        f"Monitor for {', '.join(high_diseases)} symptoms"
                    ],
                    "source": "crop_calendar",
                }
            )

        return rules

    def _prioritize_rules(self, triggered: List[dict]) -> List[dict]:
        """Sort rules by priority."""
        priority_order = {
            "critical": 0,
            "high": 1,
            "opportunity": 2,
            "medium": 3,
            "informational": 4,
            "low": 5,
        }
        triggered.sort(
            key=lambda r: priority_order.get(r.get("priority", "low"), 5)
        )
        return triggered

    def parse_weather_data(self, raw: dict) -> dict:
        """Parse weather API output into normalized format."""
        parsed = {}

        try:
            # Temperature
            hist = raw.get("currentConditionsHistory", {})
            temp_max = hist.get("maxTemperature", {}).get("degrees")
            temp_min = hist.get("minTemperature", {}).get("degrees")

            if temp_max is not None and temp_min is not None:
                parsed["temperature_c"] = round((temp_max + temp_min) / 2, 1)
                parsed["temperature_max_c"] = temp_max
                parsed["temperature_min_c"] = temp_min

            # Wind
            wind = raw.get("wind", {})
            parsed["wind_speed_kmh"] = wind.get("speed", {}).get("value", 0)

            # Cloud cover
            parsed["cloud_cover_pct"] = raw.get("cloudCover", 0)

            # Precipitation
            qpf = hist.get("qpf", {}).get("quantity", 0)
            parsed["qpf_today_mm"] = qpf

            # Estimate humidity
            if qpf > 0 and parsed.get("cloud_cover_pct", 0) > 80:
                parsed["relative_humidity_pct"] = 85
            elif parsed.get("cloud_cover_pct", 0) > 80:
                parsed["relative_humidity_pct"] = 75
            else:
                parsed["relative_humidity_pct"] = 55

            # Time
            now = datetime.now()
            parsed["month"] = now.month
            parsed["hour"] = now.hour

        except Exception as e:
            logger.error(f"Weather data parsing error: {e}")

        return parsed

    def evaluate_rules(
        self,
        weather_data: dict,
        crop: str = "avocado",
        variety: str = None,
        month: Optional[int] = None,
    ) -> List[dict]:
        """
        Evaluate weather rules against current conditions for ALL varieties.

        Args:
            weather_data: Parsed weather data dict
            crop: Crop type (avocado, potato)
            variety: Ignored - evaluates for ALL varieties
            month: Current month (1-12), defaults to current month

        Returns:
            List of triggered rules (covering all varieties)
        """
        if month is None:
            month = datetime.now().month

        # Load crop-specific data
        rules_data = self.load_rules(crop)

        # Get calendar context for ALL varieties
        calendar_ctx = self.get_calendar_context(month, crop, variety=None)

        # Enrich weather with calendar context
        weather = weather_data.copy()
        weather = self._enrich_weather_with_calendar(weather, calendar_ctx)

        # Evaluate weather rules
        triggered = []
        for rule in rules_data.get("rules", []):
            try:
                wc = rule.get("weather_condition", {})
                if self._evaluate_rule_conditions(wc, weather):
                    triggered.append(rule)
            except Exception as e:
                logger.warning(
                    f"Error evaluating rule {rule.get('id', 'unknown')}: {e}"
                )
                continue

        # Filter by growth stage (includes ALL varieties' stages)
        active_stages = weather.get("_active_stages", {"all"})
        triggered = self._filter_by_growth_stage(triggered, active_stages)

        # Generate calendar rules
        cal_rules = self._generate_calendar_rules(calendar_ctx, weather)
        triggered.extend(cal_rules)

        # Prioritize
        triggered = self._prioritize_rules(triggered)

        month_name = calendar_ctx.get('month_name')
        logger.info(
            f"Evaluated rules for {crop} (all varieties) in {month_name}: "
            f"{len(triggered)} triggered"
        )

        return triggered

    def build_advisory_data(
        self,
        triggered_rules: List[dict],
        weather_data: dict,
        location: str,
        variety: str = None,
        growth_stage: str = None,
    ) -> dict:
        """
        Build structured advisory data for LLM prompt.

        Returns a dict with:
        - location, all varieties, all growth stages
        - weather summary
        - rules grouped by priority
        - source citations
        """
        # Group rules by priority
        critical = [r for r in triggered_rules if r["priority"] == "critical"]
        high = [r for r in triggered_rules if r["priority"] == "high"]
        opportunities = [
            r for r in triggered_rules if r["priority"] == "opportunity"
        ]
        medium = [r for r in triggered_rules if r["priority"] == "medium"]
        info = [
            r
            for r in triggered_rules
            if r["priority"] in ("informational", "low")
        ]

        # Get all growth stages from weather data
        all_growth_stages = weather_data.get("growth_stages_all", {})

        return {
            "location": location,
            "varieties_all": all_growth_stages,  # All varieties with their stages
            "date": datetime.now().strftime("%A, %d %B %Y"),
            "weather": {
                "temperature_min": weather_data.get("temperature_min_c", "?"),
                "temperature_max": weather_data.get("temperature_max_c", "?"),
                "rainfall": weather_data.get("qpf_today_mm", 0),
                "wind_speed": weather_data.get("wind_speed_kmh", "?"),
                "cloud_cover": weather_data.get("cloud_cover_pct", "?"),
                "humidity": weather_data.get("relative_humidity_pct", "?"),
            },
            "rules": {
                "critical": critical,
                "high": high,
                "opportunities": opportunities,
                "medium": medium,
                "informational": info,
            },
            "rules_count": len(triggered_rules),
            "sources": "COLEAD, BIF-CDAAC, Griesbach/ICRAF, KALRO",
        }


# Singleton instance
_weather_advisory_service = None


def get_weather_advisory_service() -> WeatherAdvisoryService:
    """Get singleton WeatherAdvisoryService instance."""
    global _weather_advisory_service
    if _weather_advisory_service is None:
        _weather_advisory_service = WeatherAdvisoryService()
    return _weather_advisory_service
