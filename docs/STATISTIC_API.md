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
4. **Use Ward ID:** Pass the selected ward's `id` as `ward_id` to statistics endpoints

**Example Streamlit Code:**

```python
import streamlit as st
import requests

API_BASE = "http://localhost:8000/api"

# Load regions
regions = requests.get(f"{API_BASE}/administrative/?level=Region").json()
region_options = {r["name"]: r["id"] for r in regions["administrative"]}
selected_region = st.selectbox("Region", ["All"] + list(region_options.keys()))

# Load districts based on region
if selected_region != "All":
    districts = requests.get(
        f"{API_BASE}/administrative/?parent_id={region_options[selected_region]}"
    ).json()
    district_options = {d["name"]: d["id"] for d in districts["administrative"]}
    selected_district = st.selectbox("District", ["All"] + list(district_options.keys()))

    # Load wards based on district
    if selected_district != "All":
        wards = requests.get(
            f"{API_BASE}/administrative/?parent_id={district_options[selected_district]}"
        ).json()
        ward_options = {w["name"]: w["id"] for w in wards["administrative"]}
        selected_ward = st.selectbox("Ward", ["All"] + list(ward_options.keys()))

        # Use ward_id in statistics call
        ward_id = ward_options.get(selected_ward) if selected_ward != "All" else None
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
| `ward_id` | integer | No | - | Filter by specific ward ID |
| `phone_prefix` | string | No | - | Filter by phone number prefix (e.g., `+254`) |
| `active_days` | integer | No | 30 | Days to consider a farmer as "active" |

**Example Request:**

```bash
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats?start_date=2024-01-01&phone_prefix=%2B254"
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
    "ward_id": null,
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
| `phone_prefix` | string | No | - | Filter by phone number prefix |

**Example Request:**

```bash
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/stats/by-ward"
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
| `ward_id` | integer | No | - | Filter by specific ward ID |
| `phone_prefix` | string | No | - | Filter by phone number prefix |
| `group_by` | string | No | `day` | Group by: `day`, `week`, or `month` |

**Example Request:**

```bash
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/farmers/registrations?group_by=week&start_date=2024-01-01"
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
    "ward_id": null,
    "phone_prefix": null,
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

**Example Request:**

```bash
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/stats?start_date=2024-01-01"
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
    "eo_id": null
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

**Example Request:**

```bash
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/stats/by-eo"
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
    "end_date": null
  }
}
```

---

### 6. Get EO Count by District

**Endpoint:** `GET /api/statistic/eo/count-by-district`

Returns the number of active EOs per district (sub-county).

**Example Request:**

```bash
curl -H "Authorization: Bearer your-secret-token" \
  "http://localhost:8000/api/statistic/eo/count-by-district"
```

**Response:**

```json
{
  "data": [
    {"district_id": 1, "district_name": "Kiharu", "eo_count": 5},
    {"district_id": 2, "district_name": "Mathioya", "eo_count": 3}
  ]
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

## Rate Limiting

There are currently no rate limits on the Statistics API. However, be mindful of query complexity, especially when using date ranges that span large periods.

---

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI:** `http://localhost:8000/api/docs`
- **ReDoc:** `http://localhost:8000/api/redoc`

The Statistics API endpoints are grouped under the `statistics` tag.
