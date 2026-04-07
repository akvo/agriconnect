# Statistics API Documentation

This document describes the Statistics API endpoints for external applications (e.g., Streamlit dashboards) to access farmer and EO statistics.

## Authentication

Statistics endpoints (`/api/statistic/*`) require Bearer token authentication using a static API token.

Administrative endpoints (`/api/administrative/*`) are **public** and do not require authentication.

### Getting the Token

There are two ways to get the token:

1. **From the Web UI (Admin only):** Navigate to the Analytics page (`/analytics`) and scroll to the "Statistics API Token" section. Click the copy button to copy the token.

2. **From the system administrator:** Request the `STATISTIC_API_TOKEN` value which is configured in the backend's `.env` file.

### Using the Token

Include the token in the `Authorization` header:

```
Authorization: Bearer <your_token>
```

### Error Responses

| Status Code | Description |
|-------------|-------------|
| 401 | Invalid API token |
| 503 | Statistics API not configured (token not set in environment) |

---

## Administrative Endpoints (Public - No Auth Required)

These endpoints are used to build cascading dropdown filters (Region → District → Ward).

### Get Administrative Levels

**Endpoint:** `GET /api/administrative/levels`

Returns the list of administrative level names in hierarchical order.

**Example Request:**

```bash
curl "http://localhost:8000/api/administrative/levels"
```

**Response:**

```json
["Country", "Region", "District", "Ward"]
```

---

### Get Administrative Areas by Level

**Endpoint:** `GET /api/administrative/?level={level_name}`

Returns all administrative areas at a specific level.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `level` | string | Yes* | Level name (e.g., `Region`, `District`, `Ward`) |

*Either `level` or `parent_id` is required.

**Example Request:**

```bash
# Get all regions
curl "http://localhost:8000/api/administrative/?level=Region"

# Get all districts
curl "http://localhost:8000/api/administrative/?level=District"

# Get all wards
curl "http://localhost:8000/api/administrative/?level=Ward"
```

**Response:**

```json
{
  "administrative": [
    {"id": 1, "name": "Murang'a"},
    {"id": 2, "name": "Nakuru"}
  ],
  "total": 2
}
```

---

### Get Administrative Areas by Parent

**Endpoint:** `GET /api/administrative/?parent_id={parent_id}`

Returns all child administrative areas under a specific parent. Use this for cascading dropdowns.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `parent_id` | integer | Yes* | ID of the parent administrative area |

*Either `level` or `parent_id` is required.

**Example Request:**

```bash
# Get all districts in a region (parent_id = region's ID)
curl "http://localhost:8000/api/administrative/?parent_id=1"

# Get all wards in a district (parent_id = district's ID)
curl "http://localhost:8000/api/administrative/?parent_id=5"
```

**Response:**

```json
{
  "administrative": [
    {"id": 5, "name": "Kiharu"},
    {"id": 6, "name": "Mathioya"},
    {"id": 7, "name": "Kangema"}
  ],
  "total": 3
}
```

---

### Get Administrative Area by ID

**Endpoint:** `GET /api/administrative/{administrative_id}`

Returns details of a specific administrative area including its path.

**Example Request:**

```bash
curl "http://localhost:8000/api/administrative/10"
```

**Response:**

```json
{
  "id": 10,
  "code": "KEN-MUR-KIH-WAN",
  "name": "Wangu",
  "level_id": 4,
  "parent_id": 5,
  "path": "Kenya > Murang'a > Kiharu > Wangu",
  "long": 37.1234,
  "lat": -0.7234
}
```

---

### Building a Cascade Dropdown

To build a Region → District → Ward cascade dropdown:

1. **Load Regions:** `GET /api/administrative/?level=Region`
2. **On Region Select:** `GET /api/administrative/?parent_id={selected_region_id}`
3. **On District Select:** `GET /api/administrative/?parent_id={selected_district_id}`
4. **Use administrative_id:** Pass the selected area's `id` as `administrative_id` to statistics endpoints

**Key Feature: Any Level Works**

The `administrative_id` parameter accepts IDs from **any administrative level**:
- **Region ID** → Aggregates all farmers/stats from all districts and wards in that region
- **District ID** → Aggregates all farmers/stats from all wards in that district
- **Ward ID** → Returns stats for that specific ward only

This means you can filter by region or district without needing to drill down to ward level!

**Example Streamlit Code:**

```python
import streamlit as st
import requests

API_BASE = "http://localhost:8000/api"
TOKEN = "your-api-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Load regions
regions = requests.get(f"{API_BASE}/administrative/?level=Region").json()
region_options = {r["name"]: r["id"] for r in regions["administrative"]}
selected_region = st.selectbox("Region", ["All"] + list(region_options.keys()))

# Track the administrative_id to use for filtering
administrative_id = None

if selected_region != "All":
    # Use region_id for filtering (aggregates all districts/wards)
    administrative_id = region_options[selected_region]

    # Load districts for further drill-down
    districts = requests.get(
        f"{API_BASE}/administrative/?parent_id={administrative_id}"
    ).json()
    district_options = {d["name"]: d["id"] for d in districts["administrative"]}
    selected_district = st.selectbox("District", ["All"] + list(district_options.keys()))

    if selected_district != "All":
        # Use district_id for filtering (aggregates all wards)
        administrative_id = district_options[selected_district]

        # Load wards for further drill-down
        wards = requests.get(
            f"{API_BASE}/administrative/?parent_id={administrative_id}"
        ).json()
        ward_options = {w["name"]: w["id"] for w in wards["administrative"]}
        selected_ward = st.selectbox("Ward", ["All"] + list(ward_options.keys()))

        if selected_ward != "All":
            # Use ward_id for filtering (specific ward)
            administrative_id = ward_options[selected_ward]

# Fetch stats with the selected administrative_id
params = {}
if administrative_id:
    params["administrative_id"] = administrative_id

stats = requests.get(
    f"{API_BASE}/statistic/farmers/stats",
    headers=HEADERS,
    params=params
).json()
```

---

## Farmer Statistics Endpoints

### 1. Get Farmer Statistics

**Endpoint:** `GET /api/statistic/farmers/stats`

Returns comprehensive farmer statistics including onboarding progress, activity metrics, feature usage, and escalation data.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | - | Filter start date (ISO 8601 format, e.g., `2024-01-01`) |
| `end_date` | string | No | - | Filter end date (ISO 8601 format) |
| `administrative_id` | integer | No | - | Filter by administrative area (region, district, or ward). Aggregates data from all descendant areas. |
| `phone_prefix` | string | No | - | Filter by phone number prefix (e.g., `+254`) |
| `crop_type` | string | No | - | Filter by crop type (e.g., `maize`, `coffee`, `potato`) |
| `active_days` | integer | No | 30 | Days to consider a farmer as "active" |

**Example Requests:**

```bash
# Filter by region (aggregates all districts/wards in Murang'a)
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats?administrative_id=47"

# Filter by crop type (maize farmers only)
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats?crop_type=maize"

# Filter by district (aggregates all wards in Kiharu)
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats?administrative_id=56"

# Combine crop type with administrative filter
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats?administrative_id=47&crop_type=coffee"
```

**Response:**

```json
{
  "onboarding": {
    "started": 150,
    "completed": 120,
    "completion_rate": 0.80
  },
  "activity": {
    "active_farmers": 80,
    "dormant_farmers": 40,
    "active_rate": 0.67,
    "avg_days_to_first_question": 2.5,
    "avg_questions_per_farmer": 3.2
  },
  "features": {
    "weather_subscribers": 45
  },
  "escalations": {
    "total_escalated": 25,
    "farmers_who_escalated": 18
  },
  "filters": {
    "start_date": "2024-01-01",
    "end_date": null,
    "administrative_id": 47,
    "phone_prefix": "+254",
    "active_days": 30
  }
}
```

---

### 2. Get Farmer Statistics by Ward

**Endpoint:** `GET /api/statistic/farmers/stats/by-ward`

Returns farmer statistics grouped by ward.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | - | Filter start date (ISO 8601 format) |
| `end_date` | string | No | - | Filter end date (ISO 8601 format) |
| `administrative_id` | integer | No | - | Filter to wards under this area. If region/district ID, shows all wards under that area. |
| `phone_prefix` | string | No | - | Filter by phone number prefix |
| `crop_type` | string | No | - | Filter by crop type (e.g., `maize`, `coffee`, `potato`) |

**Example Requests:**

```bash
# Get stats for all wards (no filter)
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats/by-ward"

# Get stats for wards in Murang'a region only
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats/by-ward?administrative_id=47"

# Get stats for maize farmers by ward
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats/by-ward?crop_type=maize"
```

**Response:**

```json
{
  "data": [
    {
      "ward_id": 1,
      "ward_name": "Wangu",
      "ward_path": "Kenya > Murang'a > Kiharu > Wangu",
      "registered_farmers": 50,
      "incomplete_registration": 10,
      "farmers_with_questions": 35,
      "total_questions": 120,
      "farmers_who_escalated": 8,
      "total_escalations": 15
    }
  ],
  "filters": {
    "start_date": null,
    "end_date": null,
    "administrative_id": 47,
    "phone_prefix": null
  }
}
```

---

### 3. Get Registration Chart Data

**Endpoint:** `GET /api/statistic/farmers/registrations`

Returns time series data of farmer registrations for charting.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | - | Filter start date (ISO 8601 format) |
| `end_date` | string | No | - | Filter end date (ISO 8601 format) |
| `administrative_id` | integer | No | - | Filter by administrative area (region, district, or ward). Aggregates data from all descendant areas. |
| `phone_prefix` | string | No | - | Filter by phone number prefix |
| `crop_type` | string | No | - | Filter by crop type (e.g., `maize`, `coffee`, `potato`) |
| `group_by` | string | No | `day` | Group by: `day`, `week`, or `month` |

**Example Request:**

```bash
# Registration trends for entire Murang'a region
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/registrations?administrative_id=47&group_by=week&start_date=2024-01-01"

# Registration trends for maize farmers
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/registrations?crop_type=maize&group_by=month"
```

**Response:**

```json
{
  "data": [
    {"date": "2024-01-15", "count": 12},
    {"date": "2024-01-22", "count": 8},
    {"date": "2024-01-29", "count": 15}
  ],
  "total": 35,
  "filters": {
    "start_date": "2024-01-01",
    "end_date": null,
    "administrative_id": 47,
    "phone_prefix": null,
    "crop_type": null,
    "group_by": "week"
  }
}
```

---

## EO (Extension Officer) Statistics Endpoints

### 4. Get EO Statistics

**Endpoint:** `GET /api/statistic/eo/stats`

Returns EO statistics including ticket handling metrics and bulk message counts.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | - | Filter start date (ISO 8601 format) |
| `end_date` | string | No | - | Filter end date (ISO 8601 format) |
| `eo_id` | integer | No | - | Filter by specific EO ID |
| `administrative_id` | integer | No | - | Filter tickets by customers in this administrative area |

**Example Requests:**

```bash
# EO stats for tickets from customers in Murang'a region
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/stats?administrative_id=47"

# EO stats for a specific EO in a specific district
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/stats?eo_id=5&administrative_id=56"
```

**Response:**

```json
{
  "tickets": {
    "open": 25,
    "closed": 150,
    "avg_response_time_hours": 4.5
  },
  "messages": {
    "bulk_messages_sent": 12
  },
  "filters": {
    "start_date": "2024-01-01",
    "end_date": null,
    "eo_id": null,
    "administrative_id": 47
  }
}
```

---

### 5. Get EO Statistics by EO

**Endpoint:** `GET /api/statistic/eo/stats/by-eo`

Returns statistics for each individual EO.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | - | Filter start date (ISO 8601 format) |
| `end_date` | string | No | - | Filter end date (ISO 8601 format) |
| `administrative_id` | integer | No | - | Filter to EOs assigned to this area or its descendant areas |

**Example Requests:**

```bash
# Get stats for all EOs
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/stats/by-eo"

# Get stats for EOs assigned to Murang'a region (includes all districts/wards)
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/stats/by-eo?administrative_id=47"

# Get stats for EOs assigned to Kiharu district only
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/stats/by-eo?administrative_id=56"
```

**Response:**

```json
{
  "data": [
    {
      "eo_id": 1,
      "eo_name": "John Doe",
      "district": "Kiharu",
      "total_replies": 45,
      "tickets_closed": 30
    },
    {
      "eo_id": 2,
      "eo_name": "Jane Smith",
      "district": "Mathioya",
      "total_replies": 62,
      "tickets_closed": 48
    }
  ],
  "filters": {
    "start_date": null,
    "end_date": null,
    "administrative_id": 47
  }
}
```

---

### 6. Get EO Count

**Endpoint:** `GET /api/statistic/eo/count`

Returns the total count of active Extension Officers.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `administrative_id` | integer | No | - | Filter to EOs in this area. Works with any level (region, district, ward). |

**Example Requests:**

```bash
# Get total EO count (all areas)
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/count"

# Get EO count for Murang'a region (includes all districts/wards)
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/count?administrative_id=47"

# Get EO count for Kiharu district only
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/count?administrative_id=56"
```

**Response:**

```json
{
  "count": 8,
  "administrative_id": 47
}
```

---

### 7. List EOs (for Filter Dropdown)

**Endpoint:** `GET /api/statistic/eo/list`

Returns a list of all active EOs, sorted alphabetically by name. Useful for populating filter dropdowns in dashboards.

**Example Request:**

```bash
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/list"
```

**Response:**

```json
{
  "data": [
    {"id": 2, "name": "Alice Mwangi"},
    {"id": 3, "name": "Bob Ochieng"},
    {"id": 1, "name": "John Doe"}
  ]
}
```

---

## Aggregate Endpoints (Dashboard View)

These endpoints provide a **different approach** to viewing statistics, designed specifically for dashboard pages where you want to see data **aggregated by administrative level** with filter highlighting.

### Why Aggregate Endpoints?

The existing endpoints (`/farmers/stats`, `/eo/stats`) are designed for **drill-down workflows**:
1. User selects Region → District → Ward
2. Each selection narrows the data

However, dashboards often need a **different view**:
- Show all regions/districts/wards **side by side** with their statistics
- Let users **compare** areas at the same level
- **Highlight** which filter options have data (so users don't select empty areas)

The aggregate endpoints solve this by:
1. **Grouping data by administrative level** - See all regions, districts, or wards at once
2. **Including an `available` object** - Lists all areas and crop types that have data, so your UI can highlight valid filter options
3. **Supporting crop type filtering** - Filter by specific crops (e.g., maize, coffee)

### 8. Get Farmer Data Aggregated by Level

**Endpoint:** `GET /api/statistic/aggregate/farmers`

Returns farmer statistics grouped by administrative level (region, district, or ward).

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `level` | string | No | `region` | Administrative level: `region`, `district`, or `ward` |
| `administrative_id` | integer | No | - | Filter to children of this area only |
| `crop_type` | string | No | - | Filter by crop type (e.g., `maize`, `coffee`, `potato`) |
| `start_date` | string | No | - | Filter start date (ISO 8601 format) |
| `end_date` | string | No | - | Filter end date (ISO 8601 format) |

**Example Requests:**

```bash
# Get all regions with farmer counts
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8000/api/statistic/aggregate/farmers?level=region"

# Get all districts with farmer counts
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8000/api/statistic/aggregate/farmers?level=district"

# Get districts in a specific region only
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8000/api/statistic/aggregate/farmers?level=district&administrative_id=47"

# Filter by crop type (maize farmers only)
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8000/api/statistic/aggregate/farmers?level=region&crop_type=maize"
```

**Response:**

```json
{
  "data": [
    {
      "id": 47,
      "name": "Murang'a",
      "path": "Kenya > Murang'a",
      "farmer_count": 150,
      "completed_onboarding": 120,
      "incomplete_onboarding": 30,
      "questions_count": 450,
      "escalations_count": 25,
      "weather_subscribers": 85
    },
    {
      "id": 52,
      "name": "Nakuru",
      "path": "Kenya > Nakuru",
      "farmer_count": 230,
      "completed_onboarding": 200,
      "incomplete_onboarding": 30,
      "questions_count": 680,
      "escalations_count": 42,
      "weather_subscribers": 120
    }
  ],
  "filters": {
    "level": "region",
    "administrative_id": null,
    "crop_type": null,
    "start_date": null,
    "end_date": null
  },
  "available": {
    "regions": [
      {"id": 47, "name": "Murang'a"},
      {"id": 52, "name": "Nakuru"}
    ],
    "districts": [
      {"id": 56, "name": "Kiharu"},
      {"id": 59, "name": "Maragwa"},
      {"id": 65, "name": "Naivasha"}
    ],
    "wards": [
      {"id": 57, "name": "Wangu"},
      {"id": 58, "name": "Mugoiri"},
      {"id": 70, "name": "Mai Mahiu"}
    ],
    "crop_types": ["coffee", "maize", "potato"]
  }
}
```

---

### 9. Get EO Data Aggregated by Level

**Endpoint:** `GET /api/statistic/aggregate/eo`

Returns EO statistics grouped by administrative level (region, district, or ward).

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `level` | string | No | `region` | Administrative level: `region`, `district`, or `ward` |
| `administrative_id` | integer | No | - | Filter to children of this area only |
| `start_date` | string | No | - | Filter start date (ISO 8601 format) |
| `end_date` | string | No | - | Filter end date (ISO 8601 format) |

**Example Requests:**

```bash
# Get all regions with EO stats
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8000/api/statistic/aggregate/eo?level=region"

# Get all districts with EO stats
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8000/api/statistic/aggregate/eo?level=district"

# Get wards in a specific district
curl -H "Authorization: Bearer your-token" \
  "http://localhost:8000/api/statistic/aggregate/eo?level=ward&administrative_id=56"
```

**Response:**

```json
{
  "data": [
    {
      "id": 47,
      "name": "Murang'a",
      "path": "Kenya > Murang'a",
      "eo_count": 8,
      "open_tickets": 25,
      "closed_tickets": 150,
      "total_replies": 320
    },
    {
      "id": 52,
      "name": "Nakuru",
      "path": "Kenya > Nakuru",
      "eo_count": 12,
      "open_tickets": 18,
      "closed_tickets": 220,
      "total_replies": 480
    }
  ],
  "filters": {
    "level": "region",
    "administrative_id": null,
    "crop_type": null,
    "start_date": null,
    "end_date": null
  },
  "available": {
    "regions": [{"id": 47, "name": "Murang'a"}, {"id": 52, "name": "Nakuru"}],
    "districts": [{"id": 56, "name": "Kiharu"}, {"id": 65, "name": "Naivasha"}],
    "wards": [{"id": 57, "name": "Wangu"}, {"id": 70, "name": "Mai Mahiu"}],
    "crop_types": ["coffee", "maize", "potato"]
  }
}
```

---

### Using the `available` Object for Filter Highlighting

The `available` object in the response contains lists of regions, districts, wards, and crop types that **have actual farmer data**. This is useful for:

1. **Highlighting valid options** in dropdown menus
2. **Disabling empty options** to prevent users from selecting areas with no data
3. **Building smarter filters** that adapt to the data

**Example Streamlit Implementation:**

```python
import streamlit as st
import requests

API_BASE = "http://localhost:8000/api"
HEADERS = {"Authorization": "Bearer your-token"}

# Fetch aggregate data (includes available filters)
response = requests.get(
    f"{API_BASE}/statistic/aggregate/farmers",
    headers=HEADERS,
    params={"level": "region"}
).json()

data = response["data"]
available = response["available"]

# Get all regions from administrative API
all_regions = requests.get(f"{API_BASE}/administrative/?level=Region").json()

# Build dropdown with highlighting
region_options = {}
for region in all_regions["administrative"]:
    # Check if this region has data
    has_data = any(r["id"] == region["id"] for r in available["regions"])
    if has_data:
        region_options[f"✓ {region['name']}"] = region["id"]  # Highlight with checkmark
    else:
        region_options[f"  {region['name']} (no data)"] = region["id"]

selected = st.selectbox("Region", ["All"] + list(region_options.keys()))

# Build crop type filter from available options
crop_options = ["All"] + available["crop_types"]
selected_crop = st.selectbox("Crop Type", crop_options)
```

---

## Metric Definitions

### Onboarding Metrics

| Metric | Definition |
|--------|------------|
| `started` | Customers with `onboarding_status != NOT_STARTED` |
| `completed` | Customers with `onboarding_status = COMPLETED` |
| `completion_rate` | `completed / started` |

### Activity Metrics

| Metric | Definition |
|--------|------------|
| `active_farmers` | Completed farmers who sent a message within `active_days` |
| `dormant_farmers` | `completed_farmers - active_farmers` |
| `active_rate` | `active_farmers / completed_farmers` |
| `avg_days_to_first_question` | Average days between registration and first message |
| `avg_questions_per_farmer` | Total questions / farmers who asked questions |

### Feature Metrics

| Metric | Definition |
|--------|------------|
| `weather_subscribers` | Customers with `profile_data.weather_subscribed = true` |

### Escalation Metrics

| Metric | Definition |
|--------|------------|
| `total_escalated` | Count of all tickets |
| `farmers_who_escalated` | Distinct customers who created tickets |

### EO Metrics

| Metric | Definition |
|--------|------------|
| `open` | Tickets with `resolved_at IS NULL` |
| `closed` | Tickets with `resolved_at IS NOT NULL` |
| `avg_response_time_hours` | Average `(resolved_at - created_at)` in hours |
| `bulk_messages_sent` | Count of broadcast messages created |
| `total_replies` | Messages sent by EO (from_source = USER) |
| `tickets_closed` | Tickets resolved by specific EO |

### Aggregate Farmer Metrics

| Metric | Definition |
|--------|------------|
| `farmer_count` | Total customers in the area |
| `completed_onboarding` | Customers with `onboarding_status = COMPLETED` |
| `incomplete_onboarding` | Customers with `onboarding_status IN (IN_PROGRESS, FAILED)` |
| `questions_count` | Total messages from customers in the area |
| `escalations_count` | Total tickets created by customers in the area |
| `weather_subscribers` | Customers with `profile_data.weather_subscribed = true` |

### Aggregate EO Metrics

| Metric | Definition |
|--------|------------|
| `eo_count` | Number of active EOs assigned to the area |
| `open_tickets` | Tickets from customers in the area with `resolved_at IS NULL` |
| `closed_tickets` | Tickets from customers in the area with `resolved_at IS NOT NULL` |
| `total_replies` | Messages from EOs to customers in the area |

---

## Date Format

All date parameters should be in ISO 8601 format:

- **Date only:** `2024-01-15`
- **With time:** `2024-01-15T10:30:00`
- **With timezone:** `2024-01-15T10:30:00+03:00`

---

## Phone Prefix Filter

The `phone_prefix` parameter filters customers by phone number prefix. This is useful for filtering by country code:

- Kenya: `+254`
- Tanzania: `+255`
- Uganda: `+256`

Note: URL-encode the `+` sign as `%2B` when using in query strings.

---

## Administrative ID Filter (Hierarchical Aggregation)

The `administrative_id` parameter is a powerful filter that accepts IDs from **any administrative level** and automatically aggregates data from all descendant areas.

### How It Works

```
Murang'a (Region, id=47)
├── Kangema (District, id=48)
│   ├── Ward A (id=49) → 10 farmers
│   └── Ward B (id=50) → 15 farmers
├── Kiharu (District, id=56)
│   ├── Wangu (id=57) → 20 farmers
│   └── Mugoiri (id=58) → 12 farmers
└── Maragwa (District, id=59)
    ├── Ward X (id=60) → 8 farmers
    └── Ward Y (id=61) → 5 farmers
```

| Filter | Result |
|--------|--------|
| `?administrative_id=47` (Murang'a region) | Aggregates all 70 farmers across all districts/wards |
| `?administrative_id=56` (Kiharu district) | Aggregates 32 farmers (Wangu + Mugoiri) |
| `?administrative_id=57` (Wangu ward) | Returns 20 farmers (single ward) |
| No filter | Returns stats for all farmers |

### Endpoints Supporting administrative_id

| Endpoint | Behavior |
|----------|----------|
| `/api/statistic/farmers/stats` | Aggregates farmer stats from all wards under the area |
| `/api/statistic/farmers/stats/by-ward` | Returns only wards under the specified area |
| `/api/statistic/farmers/registrations` | Aggregates registration data from all wards under the area |
| `/api/statistic/eo/stats` | Filters tickets by customers in the area |
| `/api/statistic/eo/stats/by-eo` | Filters to EOs assigned to the area or its descendants |
| `/api/statistic/eo/count` | Returns EO count for the area and its descendants |
| `/api/statistic/aggregate/farmers` | Filters to show only areas under the specified parent |
| `/api/statistic/aggregate/eo` | Filters to show only areas under the specified parent |

### Benefits

1. **No need to drill down** - Filter by region or district without selecting specific wards
2. **Automatic aggregation** - Statistics are automatically summed across all descendant areas
3. **Flexible** - Works with any level in the hierarchy
4. **Consistent** - Same parameter name across all endpoints

---

## Rate Limiting

There are currently no rate limits on the Statistics API. However, be mindful of query complexity, especially when using date ranges that span large periods.

---

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI:** `http://localhost:8000/api/docs`
- **ReDoc:** `http://localhost:8000/api/redoc`

The Statistics API endpoints are grouped under the `statistics` tag.
