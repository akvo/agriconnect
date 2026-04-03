# Example Advisory Data Structure

This shows what the `{{ advisory_data }}` variable should contain when passed to the LLM prompt.

## Full Advisory Data Example

```
LOCATION: Kariara, Gatanga, Murang'a
VARIETY: Hass
GROWTH STAGE: fruit_enlargement
DATE RANGE: 03 Apr – 07 Apr 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WEATHER FORECAST (5 DAYS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Today (03 Apr): 11–18.8°C, Rain: 6.16mm, Wind: 2km/h (gust 3km/h), Cloud: 96%, Humidity: ~85%
Saturday (04 Apr): 11–18.8°C, Rain: 6.16mm, Wind: 2km/h (gust 3km/h), Cloud: 96%, Humidity: ~85%
Sunday (05 Apr): 11–18.8°C, Rain: 6.16mm, Wind: 2km/h (gust 3km/h), Cloud: 96%, Humidity: ~85%
Monday (06 Apr): 11–18.8°C, Rain: 6.16mm, Wind: 2km/h (gust 3km/h), Cloud: 96%, Humidity: ~85%
Tuesday (07 Apr): 11–18.8°C, Rain: 6.16mm, Wind: 2km/h (gust 3km/h), Cloud: 96%, Humidity: ~85%

Best spray window: No good spray window in the next 5 days — focus on drainage, scouting, and cultural controls
Best harvest window: No ideal harvest day — if urgent, pick in the driest morning window and pre-cool immediately

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIGGERED RULES (4 rules fired)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[HIGH] PHYT-002 — Phytophthora - Pre-Season Prevention
  Fires on: Today, Saturday, Sunday, Monday, Tuesday
  Risk: Zoospores become active and mobile at season onset. Prevention timing is critical.
  Actions:
    - Apply first mefenoxam soil drench now — should coincide with new growth before rains
    - Ensure all drainage infrastructure is functional before rains begin
    - Apply Ridomil (Metalaxyl) granules to soil around susceptible trees

[HIGH] SPR-003 — Prophylactic Fungicide Before Wet Season
  Fires on: Today, Saturday, Sunday, Monday, Tuesday
  Risk: Prophylactic spraying before wet periods is far more effective than reactive treatment after infection establishes.
  Actions:
    - Apply copper-based fungicide now (pre-season coverage)
    - For anthracnose: apply from early fruit set, repeat every 14 days during wet weather
    - For cercospora: apply from end of flowering to harvest during wet weather
    - For Phytophthora: apply mefenoxam soil drench before rains
    - Ensure thorough coverage of all susceptible plant parts

[OPPORTUNITY] PM-002 — Persea Mite - Cold/Rainy Suppression Window
  Fires on: Monday, Tuesday
  Risk: none — this is a natural suppression window
  Actions:
    - Mite populations are naturally suppressed — use this window for cultural controls
    - Prune and thin canopy to reduce mite habitat before dry season
    - Remove alternate host weeds (milkweed, sow thistle) near orchards
    - Sanitise tools and equipment to prevent spread
    - Prepare biological control inputs for dry season rebound

[INFORMATIONAL] PRN-002 — Pruning for Disease Prevention - Humid Season
  Fires on: Tuesday
  Risk: Dense unpruned canopy maintains high humidity at leaf and fruit surfaces, promoting fungal disease. Also reduces spray penetration.
  Actions:
    - If canopy is dense and not recently pruned, schedule pruning for next dry window
    - An open canopy benefits from natural sun and air movement to prevent disease buildup
    - Post-rain canopy flush (after high-rainfall season) increases mite habitat — prune before dry season

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVOID THIS WEEK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Today: Do NOT harvest — wet conditions increase stem end rot risk
Today: Do NOT spray — rain will wash off product before it dries (needs 4-6 dry hours)
Today: Do NOT use overhead irrigation — canopy already wet
Today: Do NOT spray insecticides near flowering trees — bees inactive in cold

Saturday: Do NOT harvest — wet conditions increase stem end rot risk
Saturday: Do NOT spray — rain will wash off product before it dries (needs 4-6 dry hours)
Saturday: Do NOT use overhead irrigation — canopy already wet

Sunday: Do NOT harvest — wet conditions increase stem end rot risk
Sunday: Do NOT spray — rain will wash off product before it dries (needs 4-6 dry hours)

Monday: Do NOT harvest — wet conditions increase stem end rot risk
Monday: Do NOT spray — rain will wash off product before it dries (needs 4-6 dry hours)

Tuesday: Do NOT harvest — wet conditions increase stem end rot risk
Tuesday: Do NOT spray — rain will wash off product before it dries (needs 4-6 dry hours)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONFLICT RESOLUTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- SPRAY rule fires but WIND rule says don't spray: Wind rule wins — delay spray until wind calms. Never spray in wind > 15 km/h.
- SPRAY rule fires but FLOWERING rule says no insecticides: Flowering rule wins for insecticides. Fungicides can still be applied if bee-safe.
- IRRIGATION rule fires but WATERLOGGING rule says don't irrigate: Waterlogging rule wins. Never irrigate saturated soil.
- HARVEST opportunity fires but WET HARVEST warning also fires: Wet harvest warning wins. Delay harvest.
- Multiple disease rules fire simultaneously: Use a single integrated spray recommendation that covers all active diseases. Copper-based fungicides cover anthracnose + cercospora + scab.
- PERSEA MITE rule fires with broad-spectrum spray recommendation from another pest: Avoid broad-spectrum pesticides — they kill mite natural enemies. Use targeted/biological control.
```

## Token Count Estimate

- Weather forecast: ~150 tokens
- Triggered rules (4 rules): ~400 tokens
- Avoid actions: ~200 tokens
- Conflict resolutions: ~150 tokens
- **Total input: ~900 tokens**
- **Expected output: ~200 tokens (500 char WhatsApp message)**
- **Total per message: ~1,100 tokens**

## Cost Implications

With Claude Haiku pricing (~$0.25 per 1M input tokens, ~$1.25 per 1M output tokens):
- Input cost: 900 tokens × $0.25/1M = **$0.000225**
- Output cost: 200 tokens × $1.25/1M = **$0.00025**
- **Total per message: ~$0.00048**
- **1,000 farmers/day: ~$0.48/day**

Even with 3x variety grouping: **$1.44/day for LLM**
WhatsApp messaging: **$20-50/day**

**LLM is <5% of total broadcast cost!**
