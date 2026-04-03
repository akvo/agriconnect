# Weather Advisory POC - Rule-Based Avocado Farming Advisories

**Status:** Proof of Concept (POC)
**Created:** March 2026
**Issue:** [#154](https://github.com/akvo/agriconnect/issues/154)

## Overview

This POC demonstrates a **rule-based weather advisory system** for avocado farmers in Kenya. Unlike generic LLM-generated advice, this system:

- ✅ Uses **75 weather-triggered rules** derived from published agronomic manuals
- ✅ Filters advice by **growth stage** (Hass vs Fuerte get different recommendations)
- ✅ Provides **source-backed actions** (every rule traces to COLEAD, BIF-CDAAC, ICRAF, or KALRO)
- ✅ Uses **deterministic rule evaluation** (no LLM hallucination)
- ✅ LLM only formats the output (translation to farmer-friendly language)

## What's Inside

### Core Files

| File | Status | Description |
|------|--------|-------------|
| `rules/avocado_weather_rules.json` | ✅ Production-ready | 75 weather-triggered rules with conditions, actions, sources |
| `rules/avocado_crop_calendar.json` | ✅ Production-ready | 12-month calendar with growth stages, pest/disease risk |
| `rules/advisory_prompt.txt` | ✅ Production-ready | LLM prompt template for WhatsApp message formatting |
| `rules/evaluate_rules.py` | ⚠️ POC quality | Rule engine - needs production hardening |
| `rules/prepare_prompt_context.py` | ⚠️ POC quality | Builds advisory data JSON from triggered rules |
| `rules/generate_advisory.py` | ⚠️ POC quality | Enriches weather with seasonal context |
| `rules/format_advisory_data.py` | 📝 Helper | Formats context into advisory_data string |

### Documentation

| File | Description |
|------|-------------|
| `IMPLEMENTATION_SPEC.md` | Full architecture, integration guide, cost estimates |
| `ERROR_HANDLING_STRATEGY.md` | Comprehensive error handling for production |
| `ERROR_HANDLING_FLOW.md` | Visual decision tree for failure scenarios |
| `ADVISORY_DATA_EXAMPLE.md` | Example of JSON structure passed to LLM |
| `rules/avocado_weather_rules.md` | Human-readable rules for agronomist review |
| `rules/avocado_crop_calendar.md` | Human-readable calendar for agronomist review |

### Source Materials (Not Committed)

The rules were extracted from these agronomic manuals (stored in `PDFs/`, gitignored due to size):

- **COLEAD** - Sustainable Avocado Production Guide (2023, 254 pages)
- **BIF-CDAAC** - Avocado Production Manual, Kenya (2019, 34 pages)
- **Griesbach/ICRAF** - Avocado Growing in Kenya (2005, 118 pages)
- **KALRO** - Persea Mite Management (2025, 25 pages)

## How It Works

### Rule Engine Flow

```
Weather Data → Rule Engine → JSON Advisory Data → LLM → WhatsApp Message
```

1. **Fetch weather**: Google Weather API (5-day forecast)
2. **Parse & enrich**: Extract fields (temp, rain, humidity, etc.)
3. **Get growth stage**: From crop calendar (month + variety → stage)
4. **Evaluate rules**: 75 rules checked, filter by growth stage
5. **Build context**: Format triggered rules + weather summary
6. **LLM formatting**: Convert to farmer-friendly WhatsApp message (~500 chars)

### Example

**Input weather:**
- Location: Kariara, Gatanga, Murang'a
- Rain: 6mm/day for 5 days
- Temp: 11-18°C
- Humidity: 85%

**Triggered rules:**
- `PHYT-002` (HIGH): Phytophthora pre-season prevention
- `SPR-003` (HIGH): Prophylactic fungicide before wet season
- `PM-002` (OPPORTUNITY): Mite suppression window

**Output message:**
```
*Weather Alert - Kariara, Gatanga, Murang'a*
*Hass Avocado - Fruit Enlargement*

*Today (Thu):* Rain 6mm, 11-18°C

*URGENT:*
1. Apply Ridomil soil drench NOW (root rot risk)
2. Clear ALL drainage channels
3. Apply copper fungicide (pre-season)

*Tomorrow (Fri):* Similar conditions - focus on drainage

*Rest of week:* Rain continues. No spray window. Monitor fruit for disease.

*AVOID:* No harvesting (wet), no spraying (rain washes off), no overhead irrigation
```

## Key Advantages

### vs Current Generic System

| Aspect | Current | POC Rule Engine |
|--------|---------|-----------------|
| Advice source | LLM generates | Manual-backed rules |
| Accuracy | Generic, may hallucinate | Specific, source-cited |
| Growth stage | Ignored | Filtered by stage |
| Variety-aware | No | Yes (Hass ≠ Fuerte) |
| Cost per farmer | ~$0.0005 | ~$0.0005 (same) |
| Traceability | None | Every action → manual page |

### Cost Analysis

- **Weather API**: Free (included in Google Cloud)
- **Rule engine**: <1ms CPU (negligible)
- **LLM formatting**: ~1,000 tokens × $0.25/1M = **$0.00025 per farmer**
- **WhatsApp**: ~$0.02-0.05 per message (2 messages)
- **Total**: **~$0.04-0.10 per farmer/day**

For 1,000 farmers: **~$40-100/day** (WhatsApp is 99% of cost)

## Integration Requirements

### Backend Changes Needed

1. **Add farmer profile fields**:
   - `variety` (Hass/Fuerte/Pinkerton)
   - `tree_age_years` (optional, defaults to 6)
   - `altitude_m` (derive from lat/lon, no user input needed)

2. **Port POC code to backend**:
   - Copy `rules/*.json` → `backend/data/`
   - Create `backend/services/weather_advisory_service.py`
   - Replace `backend/templates/weather_broadcast.txt` with `advisory_prompt.txt`

3. **Update broadcast task**:
   - Group by (location, variety) instead of just (location, crop)
   - Use rule engine instead of generic LLM prompt
   - Add error handling (see `ERROR_HANDLING_STRATEGY.md`)

4. **Database migration**:
   - Add columns to `customers` table
   - Set defaults for existing farmers (`variety="Hass"`, `tree_age_years=6`)

### Testing Checklist

- [ ] Rule engine loads JSON files without error
- [ ] Each rule can be evaluated independently (no crashes)
- [ ] Growth stage filtering works (Hass ≠ Fuerte advice)
- [ ] Missing weather fields don't crash evaluation
- [ ] LLM fallback works (template formatting when API fails)
- [ ] WhatsApp message fits in 600 chars
- [ ] Swahili translation works correctly
- [ ] Error handling: Weather API timeout → skip location
- [ ] Error handling: LLM timeout → use template
- [ ] Error handling: Missing variety → default to Hass

## Next Steps

1. **Review rules with agronomist** (validate thresholds and actions)
2. **Backend integration** (see `IMPLEMENTATION_SPEC.md`)
3. **Pilot test** with 50-100 farmers in Murang'a
4. **Iterate based on feedback**

## Notes

- **Image cards**: Not implemented in this POC (text-only messages for simplicity)
- **Multi-crop support**: Avocado only for now (don't abstract prematurely)
- **RAG/Vector DB**: Not needed yet (rule engine handles known patterns)
- **Rule editor UI**: Not needed (agronomist edits JSON directly)

## Contact

For questions about this POC, refer to issue #154 or the implementation spec.
