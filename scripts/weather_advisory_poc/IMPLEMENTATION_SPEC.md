# Avocado Weather Advisory System — Implementation Spec

## What This Is

A system that sends daily WhatsApp broadcasts to avocado farmers in Kenya with weather-based farming advice. The advice is grounded in published agronomic manuals (not LLM-generated), making it specific, accurate, and actionable.

## What the POC Proved

1. Rules CAN be derived from PDF manuals — 75 weather-triggered rules extracted from 4 sources
2. A Python rule engine evaluates rules against weather data without an LLM — fast, deterministic, cheap
3. The crop calendar filters advice by growth stage — Hass gets different advice than Fuerte in the same weather
4. The LLM's role is reduced to language translation only — formatting pre-matched rules into farmer-friendly WhatsApp text
5. Image cards (Pillow) render cleanly for WhatsApp and are scannable in 5 seconds

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Weather API     │     │  Farmer Profile   │     │  Crop Calendar  │
│  (5-day forecast │     │  - variety        │     │  (JSON, static) │
│   per location)  │     │  - location       │     │                 │
└────────┬────────┘     │  - tree age       │     └────────┬────────┘
         │              │  - language       │              │
         │              └────────┬──────────┘              │
         │                       │                         │
         ▼                       ▼                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                     RULE ENGINE (Python)                         │
│                                                                  │
│  1. Parse weather API → flat fields                              │
│  2. Look up crop calendar for month + variety → growth stage     │
│  3. Evaluate 75 weather rules against conditions                 │
│  4. Filter rules by growth stage (discard irrelevant ones)       │
│  5. Generate calendar-triggered management rules (weather-gated) │
│  6. Identify best spray day + best harvest day in forecast       │
│  7. Apply conflict resolution                                    │
│  8. Output: 5-10 triggered rules + metadata                     │
│                                                                  │
│  NO LLM CALL. Pure Python. Runs in <100ms.                      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
              ┌────────────┼────────────────┐
              ▼                             ▼
   ┌──────────────────┐          ┌──────────────────┐
   │  Image Card       │          │  Text Message     │
   │  (Pillow)         │          │  (LLM call)       │
   │                   │          │                   │
   │  - Rain bars      │          │  Prompt template  │
   │  - Do/Don't list  │          │  + triggered rules│
   │  - Best days      │          │  + avoid actions  │
   │  - Risk alerts    │          │  → LLM → text     │
   │                   │          │                   │
   │  Output: PNG      │          │  Output: ~500char │
   └────────┬─────────┘          └────────┬─────────┘
            │                             │
            └──────────┬──────────────────┘
                       ▼
             ┌──────────────────┐
             │  WhatsApp API     │
             │  (daily 9am)      │
             │                   │
             │  Message 1: Image │
             │  Message 2: Text  │
             └──────────────────┘
```

## What Exists (from POC)

All in `/rules/`:

| File | Status | What it is |
|---|---|---|
| `avocado_weather_rules.json` | **Done** | 75 weather-triggered rules with thresholds, actions, sources |
| `avocado_crop_calendar.json` | **Done** | 12-month calendar with growth stages, management tasks, pest/disease risk |
| `avocado_weather_rules.md` | **Done** | Human-readable version for agronomist review |
| `avocado_crop_calendar.md` | **Done** | Human-readable calendar for agronomist review |
| `evaluate_rules.py` | **POC quality** | Rule engine — needs production hardening |
| `generate_advisory.py` | **POC quality** | Enriches weather with seasonal context |
| `prepare_prompt_context.py` | **POC quality** | Builds prompt template variables from triggered rules |
| `advisory_prompt.txt` | **Done** | LLM prompt template for text message generation |
| `generate_card.py` | **POC quality** | Pillow image card generator |

## What Needs to Be Built

### 1. Weather API Parser (adapt to your actual API)

The POC used a generic parser. Your production parser needs to handle the actual API response format (Google Weather API based on the sample data).

**Input:** Raw forecast JSON with `forecastDays[].daytimeForecast`, `nighttimeForecast`, `maxTemperature`, `minTemperature`, etc.

**Output:** Per-day flat dict with these fields:
```python
{
    "temperature_c": float,        # average of max and min
    "temperature_max_c": float,
    "temperature_min_c": float,
    "relative_humidity_pct": int,   # average of day/night
    "wind_speed_kmh": float,       # daytime speed
    "wind_gust_kmh": float,        # daytime gust
    "cloud_cover_pct": int,        # daytime
    "qpf_today_mm": float,        # day + night precipitation combined
    "rain_probability_today_pct": int,  # max of day/night probability
    "rain_probability_next_6h_pct": int,
    "is_daytime": bool,
    "month": int,
}
```

**Derived fields** (computed from the 5-day sequence, not single-day):
```python
{
    "cumulative_rain_72h_mm": float,     # sum of last 3 days rain
    "cumulative_rain_7d_mm": float,
    "consecutive_dry_days": int,          # count days with rain < 1mm
    "consecutive_wet_days": int,
    "hours_since_last_rain": int,         # 0 if rained today, else 24 * dry days
    "soil_temp_estimate_c": float,        # air temp - 2
}
```

See `avocado_weather_rules.json` → `derived_fields` section for the full list.

### 2. Farmer Profile Store

Each farmer/group needs:
```json
{
    "farmer_id": "f123",
    "phone": "+254...",
    "location": "Kariara, Gatanga, Murang'a",
    "lat": -1.05,
    "lon": 36.88,
    "altitude_m": 1600,
    "variety": "Hass",
    "tree_age_years": 6,
    "language": "en"
}
```

The `variety` and `month` determine the growth stage via the crop calendar. The `altitude_m` is used for variety suitability rules (ALT-001/002/003). The `language` switches the LLM output to Swahili when "sw".

### 3. Daily Pipeline (Cron Job — runs at ~8:30am EAT)

```
for each location_group:
    1. Fetch 5-day weather forecast for (lat, lon)
    2. For each farmer in location_group:
        a. Parse weather → flat fields
        b. Compute derived fields from 5-day sequence
        c. Load crop calendar, look up month + farmer.variety → growth stage
        d. Evaluate 75 rules + calendar rules → triggered rules (5-10)
        e. Identify best spray day + best harvest day
        f. Generate image card (Pillow) → PNG → upload to storage → get URL
        g. Build LLM prompt context (triggered rules, avoid actions, conflicts)
        h. Call LLM with prompt template + context → ~500 char text message
        i. Send via WhatsApp API: image first, then text
```

**Optimization:** Group farmers by location. Weather fetch + rule evaluation + image card can be shared across all farmers at the same location with the same variety. Only the LLM call and language may differ.

### 4. LLM Call

**Model:** Claude Haiku (cheapest, fastest — the LLM is just formatting, not reasoning)

**Prompt:** Use `advisory_prompt.txt` as template. Inject:
- `{{ triggered_rules }}` — the 5-10 rules that fired, with priority + actions
- `{{ avoid_actions }}` — things NOT to do today
- `{{ conflict_resolutions }}` — from the JSON, only the ones relevant to triggered rules
- `{{ weather_data_5day }}` — one-line summary per day
- `{{ location }}`, `{{ farmer_variety }}`, `{{ growth_stage }}`, `{{ language }}`

**Token usage per call:** ~800 input + ~200 output = ~1,000 tokens per farmer per day.

**Output format:** The daily text message, two sections:
1. Today + Tomorrow (detailed, 2-3 actions each)
2. Rest of week (1-2 sentence summary)

Target: ~500 characters.

### 5. Image Card Generator

Use the POC `generate_card.py` as a starting point. Production needs:

- **Input:** Triggered rules, 5-day forecast summary, best spray/harvest day, risk alerts
- **Output:** 720px wide PNG, white background, ~700px tall
- **Sections:** Header (location + date + variety stage) → Rain forecast strip (6 days) → This Week checklist (green) → Avoid checklist (red) → Best days + Risk alerts (yellow)
- **No emoji dependency** — all icons are drawn (clouds, raindrops, checkmarks, X marks, warning triangles)
- **Upload** to cloud storage (S3, GCS) and pass URL to WhatsApp API

### 6. WhatsApp Integration

Send two messages per broadcast, in order:
1. Image card (as media message with image URL)
2. Text message (~500 chars)

WhatsApp Business API or a provider like Twilio/360dialog/WATI.

## What NOT to Build

- **RAG / Vector DB** — Not needed right now. The rule engine handles the known patterns. RAG is the next iteration for handling edge cases and farmer questions. Don't build it yet.
- **Farmer input collection** — Growth stage is derived from calendar + variety. Don't ask the farmer what stage their trees are in. They may not know, and the calendar is accurate enough.
- **Rule editor UI** — The agronomist edits the JSON directly (or reviews the MD and tells you what to change). A UI is premature.
- **Multi-crop support** — Avocado only for now. Don't abstract the rule engine for "any crop."

## Data Files to Deploy

These are static files that change only when the agronomist reviews and updates them:

1. `avocado_weather_rules.json` — the 75 rules (check into git, version-controlled)
2. `avocado_crop_calendar.json` — the 12-month calendar (check into git)
3. `advisory_prompt.txt` — the LLM prompt template (check into git)

## Testing

### Rule Engine Tests

For each rule, write a test that:
1. Constructs weather data that SHOULD trigger the rule
2. Asserts the rule fires
3. Constructs weather data that should NOT trigger the rule
4. Asserts the rule does NOT fire

Example:
```python
def test_phytophthora_high_risk():
    weather = {
        "cumulative_rain_72h_mm": 25,  # >= 20 ✓
        "soil_temp_estimate_c": 20,     # 15-33 ✓
        "relative_humidity_pct": 90,    # >= 85 ✓
    }
    triggered = evaluate_rules(weather, rules_data)
    assert any(r["id"] == "PHYT-001" for r in triggered)

def test_phytophthora_not_triggered_dry():
    weather = {
        "cumulative_rain_72h_mm": 5,   # < 20 ✗
        "soil_temp_estimate_c": 20,
        "relative_humidity_pct": 90,
    }
    triggered = evaluate_rules(weather, rules_data)
    assert not any(r["id"] == "PHYT-001" for r in triggered)
```

### Growth Stage Filter Tests

```python
def test_pollination_rule_filtered_for_hass_in_march():
    # Hass is in fruit_enlargement in March, NOT flowering
    # POL-001 should NOT fire even if temp < 16
    weather = {"temperature_c": 14, "is_daytime": True, "month": 3}
    calendar = load_calendar()
    triggered = evaluate_rules(weather, rules_data, calendar, variety="Hass")
    assert not any(r["id"] == "POL-001" for r in triggered)

def test_pollination_rule_fires_for_fuerte_in_september():
    # Fuerte IS flowering in September
    weather = {"temperature_c": 14, "is_daytime": True, "month": 9}
    calendar = load_calendar()
    triggered = evaluate_rules(weather, rules_data, calendar, variety="Fuerte")
    assert any(r["id"] == "POL-001" for r in triggered)
```

### End-to-End Test

Feed the same weather JSON from the POC and assert:
- Correct number of rules trigger
- Image card generates without error
- LLM output is under 600 characters
- LLM output contains at least one named product (e.g., "Ridomil", "copper")
- LLM output does NOT contain scientific names (e.g., "Phytophthora cinnamomi")

## Cost Estimate

| Component | Per farmer per day | 1,000 farmers/day |
|---|---|---|
| Weather API | Shared per location (~free) | ~free |
| Rule engine | <1ms CPU | negligible |
| Image generation | ~50ms CPU | negligible |
| LLM call (Haiku) | ~1,000 tokens | ~$0.25/day |
| WhatsApp messages (2) | ~$0.01-0.05 per msg | ~$20-50/day |
| **Total** | | **~$20-50/day** |

The LLM is the cheapest part. WhatsApp messaging is the real cost.

## Iteration Roadmap

| Phase | What | Why |
|---|---|---|
| **Now** | Ship rule engine + image card + text message | Get the pipeline working end-to-end |
| **Month 2** | Agronomist reviews rules MD + calendar MD, corrects thresholds | Accuracy before scale |
| **Month 3** | Add Swahili support, test with farmer focus group | Comprehension validation |
| **Month 4** | Add RAG (ChromaDB + PDF embeddings) for edge cases and farmer Q&A | Handle the long tail the rule engine can't cover |
| **Month 5** | Feedback loop — log which rules fire, survey farmers on usefulness | Data-driven rule refinement |

## Key Design Decisions

1. **Rule engine runs BEFORE the LLM, not inside it.** The LLM never decides what advice to give — it only formats pre-matched, source-backed rules into farmer language. This makes the advice deterministic, auditable, and cheap.

2. **The crop calendar is static, not farmer-reported.** Growth stage is derived from variety + month. This is accurate to ±2 weeks for Kenya's central highlands, which is good enough. Asking farmers to report their growth stage adds friction and is often inaccurate.

3. **Image + text, not text alone.** The image card is the primary content. The text is supplementary detail. Design for the farmer who only looks at the image.

4. **Daily broadcast, weekly framing.** The message goes out daily at 9am but frames advice as "this week" because farmers plan in weeks, not days. Today + tomorrow get detail; rest of week gets a summary.

5. **No generic advice.** Every action in the output traces to a rule, every rule traces to a published manual. If the rule engine can't match a condition, the system says nothing rather than hallucinating advice.
