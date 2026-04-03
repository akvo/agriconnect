# Weather Advisory Upgrades - Issue #154

## Problem Statement

The current weather advisory system sends **generic, LLM-generated advice** that:

❌ Lacks agronomic accuracy (potential for hallucination)
❌ Ignores crop growth stage (flowering vs harvest get same advice)
❌ Doesn't differentiate varieties (Hass and Fuerte need different timing)
❌ Has no source citations (farmers can't verify advice)
❌ May recommend wrong actions at wrong times (e.g., "spray now" during rain)

**Example of current generic message:**
> "Weather for Murang'a: Rain expected 6mm, 11-18°C. Good conditions for avocado growth. Monitor for pests and diseases. Ensure proper drainage."

This is **vague, not actionable, and potentially wrong** depending on growth stage.

---

## Solution: Rule-Based Advisory System (POC Completed)

**Location:** `/scripts/weather_advisory_poc/`

A proof-of-concept system that uses:

### ✅ 75 Weather-Triggered Rules from Published Manuals

- **COLEAD** Sustainable Avocado Production Guide (2023)
- **BIF-CDAAC** Avocado Production Manual, Kenya (2019)
- **Griesbach/ICRAF** Avocado Growing in Kenya (2005)
- **KALRO** Persea Mite Management (2025)

Every rule includes:
- Weather conditions that trigger it
- Risk explanation
- Specific actions with product names
- Source citations (manual + page numbers)

### ✅ Crop Calendar Integration

12-month calendar with:
- Growth stages per variety (Hass vs Fuerte)
- Seasonal pest/disease risk levels
- Management tasks by month

**Example:** In March, Fuerte is harvesting (mature fruit), Hass is fruit enlargement stage. Same weather → different advice.

### ✅ Deterministic Rule Engine

- Pure Python evaluation (no LLM reasoning)
- Filters rules by growth stage
- Identifies best spray/harvest days
- Resolves conflicting recommendations

### ✅ LLM for Formatting Only

- Takes triggered rules + weather data
- Converts to farmer-friendly WhatsApp message
- Translates to Swahili when needed
- Max 500 characters

---

## Example Output

**Input:**
- Location: Kariara, Gatanga, Murang'a
- Variety: Hass (fruit enlargement stage)
- Weather: 6mm rain/day, 11-18°C, 85% humidity

**Triggered Rules:**
1. PHYT-002 (HIGH) - Phytophthora pre-season prevention
2. SPR-003 (HIGH) - Prophylactic fungicide before wet season
3. PM-002 (OPPORTUNITY) - Mite suppression window

**Generated Message:**
```
*Weather Alert - Kariara, Gatanga, Murang'a*
*Hass Avocado - Fruit Enlargement*

*Today (Thu):* Rain 6mm, 11-18°C, humid

*URGENT ACTIONS:*
1. Apply Ridomil soil drench NOW — root rot risk HIGH
2. Clear ALL drainage channels today
3. Apply copper fungicide (pre-season coverage)

*Tomorrow (Fri):* Similar conditions, continue drainage focus

*Rest of week:* Rain continues daily. No spray window this week — focus on cultural controls and monitoring.

*AVOID THIS WEEK:*
• No harvesting (wet conditions → stem end rot)
• No spraying (rain washes off product)
• No overhead irrigation (soil saturated)

Source: COLEAD §6.6.3, BIF p17-23
```

**Compare to current generic advice** - this is:
- ✅ Specific (product names: Ridomil, copper)
- ✅ Actionable (clear dos and don'ts)
- ✅ Timely (urgent today vs rest of week)
- ✅ Source-backed (COLEAD §6.6.3)
- ✅ Growth-stage appropriate (fruit enlargement focus)

---

## Technical Architecture

### Flow

```
Weather API → Parse → Enrich with Calendar → Evaluate 75 Rules
                                           ↓
                                    Filter by Growth Stage
                                           ↓
                                    Triggered Rules (5-10)
                                           ↓
                                    Build Advisory JSON
                                           ↓
                                    LLM Formatting
                                           ↓
                                    WhatsApp Message
```

### Key Components

1. **`avocado_weather_rules.json`** - 75 rules with conditions, actions, sources
2. **`avocado_crop_calendar.json`** - 12-month calendar, variety-specific
3. **`evaluate_rules.py`** - Rule engine (needs production hardening)
4. **`advisory_prompt.txt`** - LLM template for message formatting

### Cost Impact

| Component | Current | With Rules | Change |
|-----------|---------|------------|--------|
| Weather API | Free | Free | 0% |
| Rule evaluation | N/A | <1ms CPU | Negligible |
| LLM tokens | ~800 | ~1,000 | +25% |
| LLM cost per farmer | $0.0004 | $0.0005 | +$0.0001 |
| **Daily cost (1,000 farmers)** | **~$0.40** | **~$0.50** | **+$0.10/day** |

WhatsApp messaging ($20-50/day) is still 99% of total cost.

**Conclusion:** 25% more LLM tokens for 10x better advice quality is worth it.

---

## Integration Requirements

### 1. Database Changes

Add to `customers` table:
- `variety` VARCHAR(50) - "Hass", "Fuerte", "Pinkerton", etc.
- `tree_age_years` INTEGER - Default: 6 (mature)
- `altitude_m` INTEGER - Derived from coordinates, not user input

**Migration strategy:**
- Existing farmers: Default `variety="Hass"` (70% market share)
- Optional: One-time WhatsApp question to refine variety
- New farmers: Add variety to onboarding (1 extra question)

### 2. Backend Services

Create `backend/services/weather_advisory_service.py`:
- Port rule engine from POC
- Load rules/calendar JSON
- Evaluate weather conditions
- Build advisory data JSON

Update `backend/services/weather_broadcast_service.py`:
- Replace generic prompt with rule engine flow
- Group broadcasts by (location, variety) instead of just (location, crop)

### 3. Data Files

Copy to `backend/data/`:
- `avocado_weather_rules.json`
- `avocado_crop_calendar.json`

Replace `backend/templates/weather_broadcast.txt` with:
- `advisory_prompt.txt`

### 4. Broadcast Task Changes

Update `backend/tasks/weather_tasks.py`:
- Group farmers by variety (Hass vs Fuerte get different messages)
- Expected: 2-3 LLM calls per location (vs 1 currently)
- Add error handling (see POC docs)

### 5. Error Handling

**Critical:** Implement graceful degradation (see `ERROR_HANDLING_STRATEGY.md`):

1. Weather API fails → Skip location or use fallback
2. LLM timeout → Use template formatting (no LLM)
3. Missing variety → Default to "Hass"
4. No rules triggered → Send generic weather + seasonal tasks
5. Broadcast partial failure → Continue with other groups

---

## Testing Checklist

- [ ] Rules JSON loads without error
- [ ] Calendar JSON loads without error
- [ ] Rule engine evaluates all 75 rules without crashing
- [ ] Growth stage filtering works (Hass ≠ Fuerte)
- [ ] Missing weather fields don't crash evaluation
- [ ] LLM generates message <600 characters
- [ ] Swahili translation works correctly
- [ ] Template fallback works when LLM fails
- [ ] Weather API timeout handled gracefully
- [ ] Missing farmer variety defaults to Hass
- [ ] Broadcast continues even if one location fails

---

## Rollout Plan

### Phase 1: Backend Integration (Week 1-2)
- [ ] Add database fields (variety, tree_age, altitude)
- [ ] Create weather_advisory_service.py
- [ ] Port rule engine + error handling
- [ ] Write unit tests for rule evaluation
- [ ] Update broadcast task grouping logic

### Phase 2: Data Migration (Week 2)
- [ ] Run migration: set variety="Hass" for existing farmers
- [ ] Derive altitude from coordinates
- [ ] Add variety question to onboarding flow

### Phase 3: Testing (Week 3)
- [ ] Test with sample weather data for all 12 months
- [ ] Validate rule triggering across seasons
- [ ] Test error handling (API failures, LLM timeout)
- [ ] Load testing (1,000+ farmers)

### Phase 4: Pilot (Week 4)
- [ ] Deploy to staging
- [ ] Enable for 50-100 farmers in Murang'a county
- [ ] Collect feedback (survey after 1 week)
- [ ] Monitor metrics: delivery rate, rule trigger rate, LLM cost

### Phase 5: Production (Week 5+)
- [ ] Gradual rollout to all locations
- [ ] Monitor error rates and adjust thresholds
- [ ] Agronomist review of triggered rules (monthly)
- [ ] Iterate based on farmer feedback

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Message delivery rate | >95% | WhatsApp delivery webhooks |
| Rules triggered per broadcast | 3-8 | Log analysis |
| LLM cost per farmer | <$0.001 | Token usage tracking |
| Farmer comprehension | >80% | Post-message survey |
| Actionable advice | >90% | Agronomist review |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rules JSON corrupted | All broadcasts fail | Validate on load, use backup file |
| Weather API down | No forecasts | Retry with exponential backoff, skip if fails |
| LLM timeout/error | Can't format messages | Fall back to template formatting |
| Wrong variety defaults | Suboptimal advice | Optional WhatsApp refinement question |
| Farmers don't understand products | Low adoption | Include generic alternatives in parentheses |

---

## Open Questions

1. **Variety distribution:** What % of farmers are Hass vs Fuerte? (Affects grouping strategy)
2. **Product availability:** Are all recommended products (Ridomil, copper fungicide) accessible?
3. **Swahili product names:** Should we translate product names or keep English?
4. **Message length:** 500 chars sufficient or allow up to 1,000?
5. **Feedback mechanism:** How do farmers report if advice was helpful/not helpful?

---

## Files in POC

See `/scripts/weather_advisory_poc/README.md` for full documentation.

**Core deliverables:**
- ✅ `rules/avocado_weather_rules.json` (75 rules, production-ready)
- ✅ `rules/avocado_crop_calendar.json` (12-month calendar, production-ready)
- ✅ `rules/advisory_prompt.txt` (LLM template, production-ready)
- ✅ `IMPLEMENTATION_SPEC.md` (Integration guide)
- ✅ `ERROR_HANDLING_STRATEGY.md` (Production error handling)
- ⚠️ Rule engine Python files (POC quality, need hardening)

**Source materials** (not committed, gitignored):
- PDFs/ (45MB of agronomic manuals)
- extracted_text/ (Text extracted from PDFs)

---

## Next Actions

1. **Agronomist review:** Validate rules and thresholds against local conditions
2. **Product availability check:** Ensure recommended products are accessible
3. **Backend integration:** Start Phase 1 (database + service layer)
4. **Farmer interviews:** Understand current weather advisory usage and gaps

---

## References

- POC Directory: `/scripts/weather_advisory_poc/`
- Implementation Spec: `/scripts/weather_advisory_poc/IMPLEMENTATION_SPEC.md`
- Error Handling: `/scripts/weather_advisory_poc/ERROR_HANDLING_STRATEGY.md`
- Example Output: `/scripts/weather_advisory_poc/ADVISORY_DATA_EXAMPLE.md`
