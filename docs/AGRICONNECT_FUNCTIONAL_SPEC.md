# AgriConnect — Functional Specification

This document provides a complete functional description of AgriConnect sufficient to recreate the system from scratch. It covers architecture, data models, API contracts, authentication, core feature logic, integrations, and configuration.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture](#3-system-architecture)
4. [Database Schema (PostgreSQL)](#4-database-schema-postgresql)
5. [REST API Reference](#5-rest-api-reference)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [WhatsApp Webhook Decision Tree](#7-whatsapp-webhook-decision-tree)
8. [Onboarding System](#8-onboarding-system)
9. [External AI Service Integration](#9-external-ai-service-integration)
10. [Internal OpenAI Integration](#10-internal-openai-integration)
11. [Broadcast Message System](#11-broadcast-message-system)
12. [Weather Broadcast System](#12-weather-broadcast-system)
13. [Real-Time Communication](#13-real-time-communication)
14. [Administrative Hierarchy](#14-administrative-hierarchy)
15. [Frontend Web Dashboard](#15-frontend-web-dashboard)
16. [Mobile App](#16-mobile-app)
17. [Configuration Reference](#17-configuration-reference)
18. [End-to-End Data Flows](#18-end-to-end-data-flows)

---

## 1. System Overview

AgriConnect is an AI-powered agricultural extension platform that connects smallholder farmers with extension officers (EOs) and AI-driven agricultural knowledge.

### Actors

| Actor | Interface | Primary Actions |
|-------|-----------|----------------|
| **Farmer** | WhatsApp only | Ask agricultural questions, receive AI answers, escalate to EO, subscribe to weather alerts |
| **Extension Officer (EO)** | Mobile app (React Native) | View tickets, reply to farmers, send bulk messages, view assigned-area analytics |
| **Administrator** | Web dashboard (Next.js) | Manage users, configure AI services, view system-wide analytics, manage knowledge bases |

### Core Value Proposition

1. Farmer sends a WhatsApp message → AI answers immediately
2. If AI cannot help, farmer escalates → EO receives push notification and replies via mobile app
3. EO receives an AI-generated "whisper" suggestion to assist in crafting the reply
4. Admins manage the knowledge base that powers the AI

### Service URLs (Development)

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/api/docs |
| pgAdmin | http://localhost:5050 |
| Mobile App | exp://<your_ip>:14000 |

---

## 2. Technology Stack

### Backend
- **Python 3.11+** with **FastAPI** (async REST API)
- **SQLAlchemy** ORM with **Alembic** migrations
- **PostgreSQL 17** (primary database)
- **Redis** (Celery task broker)
- **Celery** (async task queue for message delivery, weather broadcasts)
- **Socket.IO** (python-socketio) mounted at `/ws` for real-time events
- **JWT** (python-jose, HS256) for authentication
- **bcrypt** (passlib) for password hashing
- **Twilio** SDK for WhatsApp message send/receive
- **OpenAI Python SDK** for chat completions, Whisper STT, moderation
- **pydantic** for request/response validation

### Frontend
- **Next.js 15.5** (App Router)
- **React 19**
- **TypeScript** (optional) / JavaScript
- **Tailwind CSS 4** with PostCSS
- **Axios 1.11** for API calls
- **Socket.IO-client 4.8** for real-time playground updates
- **Heroicons** for icons
- **Jest + React Testing Library** for tests

### Mobile App
- **React Native 0.81** with **Expo 54**
- **Expo Router 6** (file-based routing)
- **expo-sqlite 16** (local SQLite database)
- **expo-secure-store 15** (encrypted token storage)
- **expo-notifications 0.32** (push notifications)
- **Socket.IO-client 4.8** (real-time WebSocket)
- **@react-native-community/netinfo** (network detection)
- **Firebase Cloud Messaging (FCM)** for Android push notifications

### Infrastructure
- **Docker Compose** for local development
- All services containerized: backend, frontend, mobileapp, postgres, redis, pgadmin, celery_worker

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                           │
│  Twilio WhatsApp API  │  OpenAI API  │  Akvo RAG  │  Google Weather │
└────────┬──────────────────────┬──────────────┬────────────┬─────────┘
         │                      │              │            │
         ▼                      ▼              ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                            │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐  │
│  │ REST API    │  │ Socket.IO    │  │  Celery   │  │  Alembic  │  │
│  │ :8000/api   │  │ :8000/ws     │  │  Worker   │  │ Migrations│  │
│  └──────┬──────┘  └──────┬───────┘  └─────┬─────┘  └───────────┘  │
│         │                │                │                         │
│         └────────────────┴────────────────┘                         │
│                              │                                      │
│                    ┌─────────▼──────────┐                           │
│                    │   PostgreSQL :5432  │                           │
│                    └────────────────────┘                           │
│                                                                     │
│                    ┌────────────────────┐                           │
│                    │   Redis :6379       │  (Celery broker)         │
│                    └────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
         │                      │
         ▼                      ▼
┌──────────────────┐  ┌──────────────────────┐
│ Next.js Frontend │  │ React Native Mobile  │
│  (Admin Web)     │  │  (Extension Officers)│
│  :3000           │  │  (Expo Go / APK)     │
└──────────────────┘  └──────────────────────┘
```

### Request Routing

- All REST API requests: `POST/GET/PUT/DELETE /api/...`
- WebSocket: `/ws/socket.io/` (Socket.IO protocol)
- Static files (uploads): `/storage/...`
- Health check: `GET /api/health-check` → `{"Status": "OK"}`

### Startup Sequence

1. PostgreSQL starts
2. Backend starts → runs Alembic migrations on startup → validates external AI service config
3. Redis starts → Celery worker connects
4. Frontend and mobile app start independently, connect to backend via HTTP/WebSocket

---

## 4. Database Schema (PostgreSQL)

### `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PK | |
| email | VARCHAR | UNIQUE NOT NULL | Login credential |
| phone_number | VARCHAR | UNIQUE NOT NULL | For WhatsApp password reset |
| hashed_password | VARCHAR | NULLABLE | Null until invitation accepted |
| user_type | ENUM('ADMIN','EXTENSION_OFFICER') | NOT NULL | Role |
| full_name | VARCHAR | NOT NULL | Display name |
| is_active | BOOLEAN | DEFAULT false | True after invitation accepted |
| invitation_token | VARCHAR | UNIQUE NULLABLE | One-time account activation token |
| invitation_sent_at | TIMESTAMP | NULLABLE | |
| invitation_expires_at | TIMESTAMP | NULLABLE | 24h from creation |
| password_reset_token | VARCHAR | UNIQUE NULLABLE | One-time reset token |
| password_reset_token_expires_at | TIMESTAMP | NULLABLE | |
| password_set_at | TIMESTAMP | NULLABLE | When password was last set |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

---

### `customers`

Farmers who interact via WhatsApp only.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| phone_number | VARCHAR UNIQUE NOT NULL | WhatsApp number (e.g. `+254...`) |
| full_name | VARCHAR NULLABLE | Set during onboarding or by EO |
| language | ENUM('EN','SW') NULLABLE | Set during first message (auto-detected or asked) |
| profile_data | JSON | Stores: crop_type, gender, birth_year, weather_subscription_asked, weather_subscribed, data_consent_asked, data_consent_given, delete_requested, tree_age_years, planting_season |
| onboarding_status | ENUM('NOT_STARTED','IN_PROGRESS','COMPLETED','FAILED') | |
| current_onboarding_field | VARCHAR NULLABLE | Field currently being collected |
| onboarding_attempts | JSON | `{field_name: attempt_count}` |
| onboarding_candidates | JSON | Fuzzy match candidates awaiting selection |
| last_message_at | TIMESTAMP NULLABLE | Timestamp of last message (any direction) |
| last_message_from | INT NULLABLE | 1=CUSTOMER, 2=USER, 3=LLM |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

Computed properties (not stored, derived in code):
- `age`: calculated from `profile_data.birth_year`
- `age_group`: `"20-35"`, `"36-50"`, or `"51+"` based on age

---

### `messages`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| message_sid | VARCHAR UNIQUE NOT NULL | Twilio message SID (or generated for outbound) |
| customer_id | INT FK→customers | |
| user_id | INT FK→users NULLABLE | Set for EO-sent messages; null for LLM/customer |
| body | TEXT | Message text content |
| from_source | INT | 1=CUSTOMER, 2=USER(EO), 3=LLM |
| message_type | ENUM('REPLY','WHISPER','FOLLOW_UP','BROADCAST','WEATHER') | |
| delivery_status | ENUM('PENDING','QUEUED','SENDING','SENT','DELIVERED','READ','FAILED','UNDELIVERED') | Twilio delivery state |
| twilio_error_code | VARCHAR NULLABLE | Twilio error code on failure |
| twilio_error_message | TEXT NULLABLE | Twilio error detail |
| retry_count | INT DEFAULT 0 | Delivery retry count |
| last_retry_at | TIMESTAMP NULLABLE | |
| delivered_at | TIMESTAMP NULLABLE | |
| media_url | VARCHAR NULLABLE | URL of attached media |
| media_type | ENUM('TEXT','VOICE','IMAGE','VIDEO','DOCUMENT','LOCATION','OTHER') | |
| status | INT | Legacy: 1=PENDING, 2=REPLIED, 3=RESOLVED, 4=ESCALATED |
| created_at | TIMESTAMP | |

---

### `tickets`

Created when a farmer requests human escalation.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| ticket_number | VARCHAR UNIQUE | Human-readable ID (e.g. `TKT-0042`) |
| administrative_id | INT FK→administrative | Ward for EO scope filtering |
| customer_id | INT FK→customers | |
| message_id | INT FK→messages | The escalation trigger message |
| context_message_id | INT FK→messages NULLABLE | The AI message that preceded escalation |
| resolved_by | INT FK→users NULLABLE | EO who resolved the ticket |
| resolved_at | TIMESTAMP NULLABLE | |
| tag | INT NULLABLE | TicketTag enum (see below) |
| tag_confidence | FLOAT NULLABLE | AI classification confidence 0.0–1.0 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**TicketTag enum values**:
- 1 = FERTILIZER
- 2 = PEST
- 3 = PRE_PLANTING
- 4 = HARVESTING
- 5 = IRRIGATION
- 6 = OTHER

---

### `administrative_levels`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| name | VARCHAR UNIQUE | e.g. "Country", "Region", "District", "Ward" |

---

### `administrative`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| code | VARCHAR INDEXED | Short code identifier |
| name | VARCHAR | e.g. "Murang'a", "Kiharu" |
| level_id | INT FK→administrative_levels | |
| parent_id | INT FK→administrative NULLABLE | Self-referential for hierarchy |
| path | VARCHAR | Full path: "Kenya > Murang'a > Kiharu > Wangu" |
| lat | FLOAT NULLABLE | Latitude for map display |
| long | FLOAT NULLABLE | Longitude for map display |

---

### `user_administrative`

Links EOs to their assigned administrative area (one EO can be linked to one node at any level).

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| user_id | INT FK→users | |
| administrative_id | INT FK→administrative | |

---

### `customer_administrative`

Links customers to their ward.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| customer_id | INT FK→customers | |
| administrative_id | INT FK→administrative | Customer's home ward |

---

### `service_tokens`

Stores configuration for external AI services (only one can be active at a time).

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| service_name | VARCHAR UNIQUE | e.g. "akvo_rag" |
| access_token | VARCHAR NULLABLE | Outbound auth token for external service |
| chat_url | VARCHAR NULLABLE | URL to POST chat job requests |
| upload_url | VARCHAR NULLABLE | URL to upload KB documents |
| kb_url | VARCHAR NULLABLE | URL for KB CRUD operations |
| document_url | VARCHAR NULLABLE | URL for document management |
| default_prompt | VARCHAR NULLABLE | System prompt template for AI |
| active | INT DEFAULT 0 | 0=inactive, 1=active |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### `knowledge_bases`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| external_id | VARCHAR | UUID from external AI service |
| is_active | BOOLEAN DEFAULT false | Only one active KB at a time |
| user_id | INT FK→users | Creator |
| service_id | INT FK→service_tokens | Which service this KB belongs to |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### `broadcast_groups`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| name | VARCHAR | Group label |
| administrative_id | INT FK→administrative NULLABLE | Scope for the group |
| created_by | INT FK→users | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### `broadcast_group_contacts`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| broadcast_group_id | INT FK→broadcast_groups | |
| customer_id | INT FK→customers | |
| UNIQUE | (broadcast_group_id, customer_id) | No duplicates |

---

### `broadcast_messages`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| message | TEXT | Content to send |
| created_by | INT FK→users | |
| status | VARCHAR | Campaign status |
| queued_at | TIMESTAMP NULLABLE | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### `broadcast_message_groups`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| broadcast_message_id | INT FK→broadcast_messages | |
| broadcast_group_id | INT FK→broadcast_groups | |
| UNIQUE | (broadcast_message_id, broadcast_group_id) | |

---

### `broadcast_recipients`

Tracks individual delivery per farmer per campaign.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| broadcast_message_id | INT FK→broadcast_messages | |
| customer_id | INT FK→customers | |
| status | DeliveryStatus ENUM | PENDING → CONFIRMED → SENT → DELIVERED |
| confirm_message_sid | VARCHAR NULLABLE | SID of the confirmation template sent |
| actual_message_sid | VARCHAR NULLABLE | SID of the actual broadcast message |
| message_id | INT FK→messages NULLABLE | Once sent, linked to message record |
| retry_count | INT DEFAULT 0 | |
| error_message | VARCHAR NULLABLE | |
| sent_at | TIMESTAMP NULLABLE | |
| confirmed_at | TIMESTAMP NULLABLE | Farmer pressed confirmation button |
| delivered_at | TIMESTAMP NULLABLE | |
| read_at | TIMESTAMP NULLABLE | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### `weather_broadcasts`

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| administrative_id | INT FK→administrative | Ward this broadcast targets |
| crop_type | VARCHAR NULLABLE | Optional: filter by crop |
| location_name | VARCHAR | Human-readable location name |
| weather_data | JSON | Raw API response |
| generated_message_en | TEXT | English weather advisory |
| generated_message_sw | TEXT | Swahili weather advisory |
| status | VARCHAR | Campaign status |
| scheduled_at | TIMESTAMP NULLABLE | |
| started_at | TIMESTAMP NULLABLE | |
| completed_at | TIMESTAMP NULLABLE | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### `weather_broadcast_recipients`

Same structure as `broadcast_recipients` but linked to `weather_broadcasts`.

---

### `devices`

Mobile devices registered for push notifications.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| user_id | INT FK→users NULLABLE | Currently logged-in user |
| administrative_id | INT FK→administrative NOT NULL | Ward for routing notifications |
| push_token | VARCHAR UNIQUE | FCM/APNS token from Expo |
| app_version | VARCHAR NULLABLE | App version string |
| is_active | BOOLEAN DEFAULT true | Deactivated on logout |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### `playground_messages`

Stores AI playground (admin test) chat history.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | |
| session_id | VARCHAR | Groups messages into a session |
| user_id | INT FK→users | Admin user |
| role | ENUM('user','assistant') | |
| content | TEXT | |
| response_time_ms | INT NULLABLE | For assistant messages |
| created_at | TIMESTAMP | |

---

## 5. REST API Reference

All endpoints are prefixed with `/api`. JSON request/response unless noted.

### Auth — `/api/auth`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | None | `{email, password}` → `{access_token, refresh_token, user}` + httpOnly cookie |
| POST | `/refresh` | Cookie or `{mobile_refresh_token}` | → `{access_token}` |
| POST | `/logout` | Bearer | Clears httpOnly refresh cookie |
| GET | `/profile` | Bearer | → current user with administrative location |
| PUT | `/profile` | Bearer | `{full_name, phone_number, current_password?, new_password?}` |
| GET | `/verify-invitation/{token}` | None | → `{valid, expired}` |
| POST | `/accept-invitation` | None | `{invitation_token, password}` → `{access_token, user}` |
| POST | `/forgot-password` | None | `{email}` or `{phone_number}` → always 200 |
| GET | `/verify-reset-token/{token}` | None | → `{valid, expired, user_email}` |
| POST | `/reset-password` | None | `{reset_token, password}` |

---

### Customers — `/api/customers`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | Bearer (admin) | `{phone_number, full_name?, language?}` → customer |
| GET | `/` | Bearer | All customers; admins see all, EOs see their ward(s) + descendants |
| GET | `/list` | Bearer | Paginated: `?page&size&search&administrative_ids&crop_type&gender&age_group` |
| GET | `/export` | Bearer | CSV download with optional filters |
| GET | `/{customer_id}` | Bearer | Customer detail |
| PUT | `/{customer_id}` | Bearer | Update profile fields including profile_data |
| GET | `/phone/{phone_number}` | Bearer (admin) | Lookup by phone |
| DELETE | `/{customer_id}` | Bearer (admin) | Cascade delete all messages, tickets, relationships |

---

### Tickets — `/api/tickets`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Bearer | Paginated: `?page&size&status&administrative_ids&tag&search` |
| GET | `/{ticket_id}` | Bearer | Ticket with full message history |
| GET | `/{ticket_id}/messages` | Bearer | Messages for ticket |
| POST | `/{ticket_id}/resolve` | Bearer | Mark resolved; triggers auto-tagging |
| PUT | `/{ticket_id}` | Bearer | Update ticket metadata |
| DELETE | `/{ticket_id}` | Bearer | Delete ticket |

---

### Messages — `/api/messages`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Bearer | `?ticket_id&page&size` |
| GET | `/{message_id}` | Bearer | Single message |
| PUT | `/{message_id}/status` | Bearer | `{delivery_status}` |
| POST | `/` | Bearer | `{ticket_id, body, from_source}` → sends via Twilio |

---

### Knowledge Base — `/api/kb`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | Bearer | Create KB in external service + store record |
| GET | `/` | Bearer | `?page&size&search` |
| GET | `/{kb_id}` | Bearer | KB details |
| PUT | `/{kb_id}` | Bearer | Toggle is_active; only one active at a time |
| DELETE | `/{kb_id}` | Bearer | Delete from external service + DB |
| POST | `/{kb_id}/documents` | Bearer | Upload document (multipart); triggers external upload job |
| GET | `/{kb_id}/documents` | Bearer | List documents in this KB |

---

### WhatsApp Webhook — `/api/whatsapp`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/webhook` | None (Twilio) | Processes all incoming WhatsApp messages (see Section 7) |

Twilio POST parameters:
- `From`: `whatsapp:+254...`
- `MessageSid`: Unique ID (for dedup)
- `Body`: Text content
- `ButtonPayload`: Button click ID (e.g. `escalate`, `read_broadcast`, `reconnect`)
- `NumMedia`, `MediaUrl0`, `MediaContentType0`: Media attachments

---

### Callbacks — `/api/callback`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/ai` | None | AI service job completion. `{job_id, result, message_type}`. For REPLY: sends to customer. For WHISPER: stores as EO suggestion + notifies via Socket.IO |
| POST | `/kb` | None | KB operation completion callback |
| POST | `/twilio` | None | Twilio message delivery status: `{MessageSid, MessageStatus}` → updates delivery_status |

---

### Administrative — `/api/administrative`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/levels` | Bearer (admin) | Create administrative level |
| GET | `/levels` | Bearer | List levels |
| POST | `/` | Bearer (admin) | `{code, name, level_id, parent_id}` |
| GET | `/` | Bearer | `?level_id&parent_id` — list areas |
| GET | `/{area_id}/hierarchy` | Bearer | Area with parent + children tree |
| PUT | `/{area_id}` | Bearer (admin) | Update name, lat, long |

---

### Admin Users — `/api/admin/users`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Bearer (admin) | `?page&size&search` |
| POST | `/` | Bearer (admin) | `{email, phone_number, full_name, user_type, administrative_id}` → sends invitation email |
| GET | `/{user_id}` | Bearer (admin) | User detail |
| PUT | `/{user_id}` | Bearer (admin) | Update user; can activate/deactivate |
| DELETE | `/{user_id}` | Bearer (admin) | Delete user |
| POST | `/{user_id}/resend-invitation` | Bearer (admin) | Resend activation email |

---

### Analytics — `/api/admin/analytics`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/ticket-tags` | Bearer | `?start_date&end_date&administrative_ids` → ticket counts by tag |
| GET | `/crop-distribution` | Bearer | Farmer crop breakdown |
| GET | `/crop-distribution/matrix` | Bearer | County × crop count matrix |
| GET | `/onboarding-status` | Bearer | Onboarding completion stats |
| GET | `/statistic-api-token` | Bearer (admin) | Generate token for external dashboards |

---

### Service Tokens — `/api/admin/service-tokens`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | Bearer (admin) | Create token config |
| GET | `/` | Bearer (admin) | List all tokens |
| GET | `/{token_id}` | Bearer (admin) | Token detail |
| PUT | `/{token_id}` | Bearer (admin) | Update URLs, credentials, active flag |
| DELETE | `/{token_id}` | Bearer (admin) | Delete |

---

### Weather Admin — `/api/admin/weather`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/test-message` | Bearer (admin) | `{administrative_id, crop_type?}` → returns test weather advisory |
| POST | `/trigger-broadcast` | Bearer (admin) | Manually trigger weather broadcast |

---

### Playground — `/api/admin/playground`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/active-service` | Bearer | Active service token info |
| GET | `/default-prompt` | Bearer | Default system prompt |
| POST | `/chat` | Bearer | `{session_id, message, custom_prompt?}` → queues job |
| GET | `/sessions` | Bearer | List sessions |
| GET | `/sessions/{session_id}/messages` | Bearer | Messages in session |
| DELETE | `/sessions/{session_id}` | Bearer | Delete session |

---

### Broadcast Groups — `/api/broadcast/groups`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | Bearer | `{name, administrative_id?}` |
| GET | `/` | Bearer | `?page&size&search` |
| GET | `/{group_id}` | Bearer | Group + member list |
| PUT | `/{group_id}` | Bearer | Update name |
| DELETE | `/{group_id}` | Bearer | Delete group |
| POST | `/{group_id}/add-members` | Bearer | `{customer_ids: [int]}` |
| DELETE | `/{group_id}/members/{customer_id}` | Bearer | Remove member |

---

### Broadcast Messages — `/api/broadcast/messages`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | Bearer | `{message, group_ids: [int]}` → creates campaign |
| GET | `/` | Bearer | `?page&size` |
| GET | `/{broadcast_id}` | Bearer | Campaign + per-recipient status |
| POST | `/{broadcast_id}/send` | Bearer | Trigger delivery |

---

### Devices — `/api/devices`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | Bearer | `{push_token, administrative_id, app_version?}` |
| GET | `/` | Bearer | List devices for current user |
| DELETE | `/{device_id}` | Bearer | Unregister device |

---

### Statistics (External API) — `/api/statistic`

Uses a separate statistic API token (not user JWT).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/customers` | Customer aggregate stats by region/crop |
| GET | `/messages` | Message stats by type/status |
| GET | `/tickets` | Ticket stats by tag/resolution |

---

### User Stats — `/api/user-stats`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Bearer | `{farmers_reached, conversations_resolved, messages_sent}` for week/month/all-time |

---

## 6. Authentication & Authorization

### Token Scheme

**Access Token (Bearer)**
- Algorithm: HS256
- Expiry: 24 hours (`ACCESS_TOKEN_EXPIRE_MINUTES=1440`)
- Payload: `{sub: email, user_type: "admin"|"extension_officer", exp, type: "access"}`
- Secret: `SECRET_KEY` env var
- Usage: `Authorization: Bearer <token>` header

**Refresh Token**
- Algorithm: HS256
- Expiry: 30 days (`REFRESH_TOKEN_EXPIRE_DAYS=30`)
- Payload: `{sub: email, user_type, exp, type: "refresh"}`
- Secret: `REFRESH_SECRET_KEY` env var (different from access token secret)
- Web storage: httpOnly, Secure, SameSite=lax cookie
- Mobile storage: response body (stored in expo-secure-store)

### User Roles

**ADMIN**
- No administrative area restriction — sees all customers, tickets, messages
- Can manage users (create, update, delete)
- Can configure service tokens, knowledge bases, analytics
- Can trigger/test weather broadcasts
- Can access AI playground

**EXTENSION_OFFICER (EO)**
- Linked to one administrative node (ward, district, or region) via `user_administrative`
- Automatically sees all descendant wards
- Can view customers, tickets, messages in their scope
- Can resolve tickets, send messages, manage broadcast groups
- Cannot manage users, service tokens, or system configuration

### Administrative Scope Enforcement

For EO users, all list queries filter by their accessible ward IDs:

```python
def get_accessible_ward_ids(user_id, db):
    # Get all UserAdministrative records for this user
    user_admins = db.query(UserAdministrative).filter_by(user_id=user_id).all()
    
    all_ids = set()
    for ua in user_admins:
        all_ids.add(ua.administrative_id)
        # Recursively add all child ward IDs
        descendants = AdministrativeService.get_descendant_ward_ids(db, ua.administrative_id)
        all_ids.update(descendants)
    
    return list(all_ids)
```

Applied to:
- Customers: filtered via `CustomerAdministrative.administrative_id IN (ward_ids)`
- Tickets: filtered via `Ticket.administrative_id IN (ward_ids)`
- Messages: filtered via ticket scope
- Analytics: scoped to user's accessible areas

### Invitation Flow

1. Admin calls `POST /api/admin/users` with user details
2. Backend generates unique `invitation_token` (UUID), sets `invitation_expires_at = now + 24h`
3. Email sent with link: `https://{WEBDOMAIN}/accept-invitation/{token}`
4. User visits link → frontend calls `GET /api/auth/verify-invitation/{token}` to confirm validity
5. User submits password → `POST /api/auth/accept-invitation {invitation_token, password}`
6. Backend: validates token not expired, hashes password, sets `is_active=True`, clears token
7. Returns access + refresh tokens (user is now logged in)

### Password Reset Flow

1. `POST /api/auth/forgot-password {email}` — always returns 200 (prevents enumeration)
2. If user found: generates `password_reset_token`, sets expires (24h), sends email with reset link
3. `GET /api/auth/verify-reset-token/{token}` → `{valid, expired, user_email}`
4. `POST /api/auth/reset-password {reset_token, password}` → updates password, clears token

---

## 7. WhatsApp Webhook Decision Tree

`POST /api/whatsapp/webhook` receives every inbound WhatsApp message from Twilio.

The handler processes each message through the following ordered decision tree. Each step may terminate processing (return early) or fall through to the next step.

### Step 1 — Voice Message Transcription

```
IF NumMedia > 0 AND "audio" IN MediaContentType0:
    Download audio file from MediaUrl0 (Twilio credential required)
    Transcribe using OpenAI Whisper (whisper-1 model)
    Set Body = transcription.text
    Set media_url = MediaUrl0, media_type = VOICE
    Continue processing with transcribed text
```

### Step 2 — Duplicate Check

```
IF MessageSid already exists in messages table:
    Return immediately (idempotent for Twilio webhook retries)
```

### Step 3 — Customer Resolution

```
customer = get_customer_by_phone(From)
IF customer is None:
    customer = create_customer(phone=From, language=detect_language(Body))
    is_new_customer = True
ELSE:
    is_new_customer = (message_count_for_customer == 0)
```

Language detection: inspects Body for Swahili keywords; defaults to English.

### Step 4 — 24-Hour Reconnection

```
IF NOT is_new_customer:
    IF last_message_from IN (USER, LLM) AND (now - last_message_at) >= 24 hours:
        Send WhatsApp template message (reconnection template)
        Template SID: config.whatsapp.templates.reconnection.sid (EN) or .sid_sw (SW)
        Continue processing (don't return early)
```

### Step 5 — Account Deletion Flow

```
IF Body LOWER IN ["delete", "futa"]:
    Set customer.profile_data.delete_requested = True
    Send confirmation request: "Reply YES to confirm account deletion"
    RETURN

IF customer.profile_data.delete_requested == True AND Body LOWER IN ["yes", "ndio", "sawa"]:
    Send: "Your account has been deleted"
    delete_customer(customer.id)  # Cascades to all messages, tickets, relationships
    RETURN
```

### Step 6 — Data Consent Check

```
IF customer.language IS SET AND NOT customer.profile_data.data_consent_given:
    IF customer.profile_data.data_consent_asked:
        IF Body LOWER IN ["yes", "agree", "ndio", "kubali"]:
            Set data_consent_given = True
            Continue to onboarding
        ELSE:
            Send: "Understood, your data will not be stored"
            delete_customer(customer.id)
            RETURN
    ELSE:
        Set data_consent_asked = True
        Send consent request message
        RETURN
```

### Step 7 — Generic Onboarding

```
IF customer.needs_onboarding() AND no active unresolved ticket:
    response = onboarding_service.process_onboarding_message(customer, Body)
    
    IF status IN [IN_PROGRESS, AWAITING_SELECTION, AWAITING_CONSENT]:
        Send response.message to customer
        RETURN
    
    IF status == COMPLETED:
        IF response.requires_weather_buttons:
            Send weather subscription buttons (YES / NO)
        RETURN
    
    IF status == FAILED:
        Send error message
        RETURN
    
    # If status == COMPLETED without weather question, fall through
```

### Step 8 — Broadcast Confirmation Button

```
IF ButtonPayload == "read_broadcast":
    # Check weather broadcast first
    recipient = find_weather_broadcast_recipient(customer, status=CONFIRMED_NOT_SENT)
    IF recipient:
        Queue task: send_actual_weather_message(recipient.id)
        RETURN
    
    # Check regular broadcast
    recipient = find_broadcast_recipient(customer, status=CONFIRMED_NOT_SENT)
    IF recipient:
        broadcast_msg = get_broadcast_message(recipient.broadcast_message_id)
        Queue task: send_actual_broadcast_message(recipient.id, broadcast_msg.message)
        RETURN
```

### Step 9 — Weather Subscription Buttons

```
IF customer.profile_data.weather_subscription_asked AND NOT customer.profile_data.weather_subscribed:
    IF ButtonPayload == "weather_yes" OR Body IN ["1", "yes", "ndio"]:
        Set weather_subscribed = True
        Send: "You are now subscribed to weather alerts"
        RETURN
    
    IF ButtonPayload == "weather_no" OR Body IN ["2", "no", "hapana"]:
        Set weather_subscription_asked = True (declined)
        Send: "You can subscribe to weather alerts later"
        RETURN
```

### Step 10 — Reconnection Button

```
IF ButtonPayload == "reconnect":
    Clear reconnection state
    Continue processing (fall through to AI reply)
```

### Step 11 — Escalation

```
IF ButtonPayload == "escalate" OR message_text contains escalation keywords:
    existing_ticket = find_open_ticket(customer.id)
    IF existing_ticket:
        # Already has an open ticket, no new ticket needed
        RETURN
    
    # Create ticket
    message = create_message(body=Body, from_source=CUSTOMER, customer_id=customer.id)
    ticket = create_ticket(customer_id, message_id=message.id, administrative_id=customer_ward_id)
    
    # Queue WHISPER job (AI generates suggestion for EO, not sent to farmer)
    job_id = external_ai_service.create_chat_job(
        message_id=message.id,
        message_type=WHISPER,
        customer_id=customer.id,
        chat_history=last_N_messages
    )
    
    # Notify EOs via Socket.IO
    socketio.emit("ticket_created", {ticket_id, customer_name, ward})
    push_notification_service.send_to_ward(customer_ward_id, title="New ticket", body=...)
    
    RETURN
```

### Step 12 — Standard AI Reply

```
# Default path: farmer sent a general question
message = create_message(body=Body, from_source=CUSTOMER, customer_id=customer.id)

# Query knowledge base for context
kb_context = None
IF active_knowledge_base_exists():
    kb_context = external_ai_service.query_knowledge_base(
        kb_id=active_kb.external_id,
        query=Body,
        filter_by=customer.profile_data.crop_type
    )

# Queue REPLY job (AI response will be sent to farmer)
job_id = external_ai_service.create_chat_job(
    message_id=message.id,
    message_type=REPLY,
    customer_id=customer.id,
    chat_history=last_N_messages,
    kb_context=kb_context
)

# Send immediate acknowledgment with escalation button
send_interactive_buttons(
    to=customer.phone_number,
    body="We're processing your question...",
    buttons=[{id: "escalate", title: "Talk to an expert"}]
)

# Update last_message_from = LLM, last_message_at = now
update_customer_last_message(customer, from_source=LLM)

# Emit real-time update to EO dashboards
socketio.emit("message_received", {customer_id, message_id})
```

### Step 13 — AI Callback Handling (Async)

When external AI completes a job, it calls `POST /api/callback/ai`:

```
IF message_type == REPLY:
    response_text = strip_citations(result.answer)  # Remove [citation:N] patterns
    Store message in DB (from_source=LLM, body=response_text)
    Send to customer via Twilio WhatsApp
    Update delivery_status to PENDING/SENT

IF message_type == WHISPER:
    Store message in DB (from_source=LLM, message_type=WHISPER)
    Emit "whisper" event via Socket.IO to EOs with access to this ticket
    Send push notification to EO devices in the ticket's ward
```

---

## 8. Onboarding System

`onboarding_service.py` manages progressive farmer profile collection via conversational AI.

### Field Priority (collected in order)

1. **administration** — Farmer's ward (REQUIRED; blocks AI replies until complete)
2. **crop_type** — Primary crop from supported list (REQUIRED)
3. **gender** — Optional (male/female/other)
4. **birth_year** — Optional (4-digit year, 1940–2010 valid range)

### Onboarding State Machine

```
NOT_STARTED
    ↓ (first message from customer)
IN_PROGRESS
    ↓ (all required fields collected)
COMPLETED
    ↓ or (too many failed attempts)
FAILED
```

### Field Collection Flow

For each field:

1. **Ask question** — Send localized question for the current field
2. **Receive answer** — Customer replies
3. **Extract value** — Use OpenAI to extract the intended value from natural language
4. **Validate/match**:
   - For `administration`: fuzzy match against all wards in DB; if ambiguous, present 3–5 candidates as numbered list for customer to choose
   - For `crop_type`: fuzzy match against `config.crop_types` list (e.g. Avocado, Potato, Dairy)
   - For `gender`: keyword match (man/mwanamume → MALE, woman/mwanamke → FEMALE)
   - For `birth_year`: parse number, validate in range 1940–2010
5. **Save or retry**:
   - High confidence match: save to `profile_data`, move to next field
   - Low confidence / ambiguous: increment `onboarding_attempts[field]`, ask for clarification
   - Max attempts (3) exceeded: skip optional fields; mark FAILED for required fields

### Candidate Selection

When administration fuzzy match returns multiple candidates:
```
Store candidates in customer.onboarding_candidates
Send: "Did you mean one of these? 1. Wangu 2. Wangige 3. Wanguru"
Next message: parse number → select matching candidate → save
```

### Weather Subscription Prompt

After `COMPLETED`, if `weather.intent_enabled = true` in config:
```
Send interactive message:
  "Would you like to receive weather forecasts for your area?"
  Button 1: "Yes, sign me up"
  Button 2: "No thanks"
Set weather_subscription_asked = True
```

---

## 9. External AI Service Integration

AgriConnect uses a **service-agnostic** external AI integration (primary implementation: Akvo RAG).

### Configuration

Configured entirely via database (`service_tokens` table), not environment variables:
- Only one `service_token` with `active=1` at a time
- Active token cached for 5 minutes (TTL cache); invalidated on PUT/DELETE
- Admin configures via `/api/admin/service-tokens` endpoints

### Chat Job Flow

```
1. Backend creates job:
   POST {service_token.chat_url}
   Headers: Authorization: Bearer {service_token.access_token}
   Body: {
       job_id: uuid,
       message: customer_message_text,
       message_type: 1 (REPLY) or 2 (WHISPER),
       customer_id: int,
       chat_history: [{role, content}, ...],
       kb_id: str (if active KB),
       system_prompt: service_token.default_prompt,
       callback_url: "https://{WEBDOMAIN}/api/callback/ai"
   }

2. External service processes asynchronously

3. External service calls back:
   POST /api/callback/ai
   No auth required (public endpoint)
   Body: {
       job_id: uuid,
       result: {answer: str, citations: [...]},
       message_type: 1 or 2
   }

4. Backend delivers response based on message_type
```

### Knowledge Base Operations

All KB operations proxied through external service:

```
Create KB:
  POST {service_token.kb_url}
  Body: {name, description}
  → Returns: {external_id: uuid}
  → Store in knowledge_bases table

Upload Document:
  POST {service_token.upload_url}
  Multipart: {file, kb_id}
  → Async; completion notified via POST /api/callback/kb

Query KB:
  GET {service_token.kb_url}/{external_id}/query
  Params: {q: text, crop_type?: str}
  → Returns: {passages: [{content, score}]}
```

---

## 10. Internal OpenAI Integration

Direct OpenAI API integration (`openai_service.py`) for synchronous tasks that don't go through the external AI service.

### Use Cases

| Use Case | Method | Model |
|----------|--------|-------|
| Voice message transcription | `transcribe_audio(audio_file)` | whisper-1 |
| Onboarding value extraction | `structured_output(messages, format)` | gpt-4o-mini |
| Content moderation | `moderate_content(text)` | omni-moderation-latest |
| Follow-up question generation | `chat_completion(messages)` | gpt-4o-mini |
| Weather advisory generation | `chat_completion(messages)` | gpt-4o-mini |
| Ticket auto-tagging | `chat_completion(messages)` | gpt-4o-mini |

### Configuration (config.json)

```json
{
  "openai": {
    "enabled": true,
    "models": {
      "chat": "gpt-4o-mini",
      "chat_advanced": "gpt-4o",
      "transcription": "whisper-1",
      "embedding": "text-embedding-3-small",
      "moderation": "omni-moderation-latest"
    },
    "features": {
      "speech_to_text": {"enabled": true, "language": "en"},
      "onboarding": {"enabled": true},
      "content_moderation": {"enabled": true, "auto_flag": true},
      "follow_up": {"enabled": true}
    }
  }
}
```

### Follow-Up Question System

Before sending a farmer's first message to external AI in REPLY mode, the system optionally generates a follow-up question via internal OpenAI to gather more context:

```
IF config.openai.features.follow_up.enabled:
    IF no MessageType.FOLLOW_UP in conversation history:
        follow_up = generate_follow_up_question(customer_message, chat_history, language)
        Send follow_up to customer
        Store message with type=FOLLOW_UP
        RETURN (wait for farmer's follow-up answer before queuing AI job)
    ELSE:
        # Follow-up already asked; proceed to external AI
```

Follow-ups are reset after each ticket is resolved (new conversation gets a new follow-up).

---

## 11. Broadcast Message System

Allows EOs and admins to send a message to a group of farmers via WhatsApp.

### Broadcast Groups

- Named collections of customers (farmers) created and managed by EOs/admins
- EOs can only add farmers from their accessible wards
- Accessible via mobile app (broadcast screens) and web dashboard

### Two-Stage Delivery

WhatsApp's 24-hour messaging window requires a template message for contacts outside the window. AgriConnect handles this transparently:

**Stage 1 — Confirmation Template**
```
For each customer in selected groups:
    Send WhatsApp template message (broadcast template SID)
    Template says: "You have a message from AgriConnect. Tap to read."
    Button: "Read Message" (payload: read_broadcast)
    Store confirm_message_sid in broadcast_recipients
    Set status = PENDING
```

**Stage 2 — Actual Message**
```
When customer taps "Read Message" button:
    Webhook receives ButtonPayload = "read_broadcast"
    Find broadcast_recipient where confirm_message_sid matches
    Send actual broadcast message text
    Update recipient status = DELIVERED
    Link message_id in broadcast_recipients
```

### Delivery Tracking

Per-recipient statuses: `PENDING → CONFIRMED → SENT → DELIVERED → READ`

Failed deliveries retried up to 3 times with backoff (5min, 15min, 60min).

---

## 12. Weather Broadcast System

Delivers daily weather advisories to subscribed farmers.

### Subscription Model

- Farmers opt in during or after onboarding via WhatsApp buttons
- Subscription stored in `customer.profile_data.weather_subscribed`
- Farmers can opt out at any time via WhatsApp command

### Daily Broadcast (Celery)

Scheduled task runs at 6:00 AM UTC daily:
```
For each ward with subscribed farmers:
    lat, long = get_ward_coordinates()
    weather_data = google_weather_api.get_forecast(lat, long, days=6)
    
    For each crop_type in ward:
        message_en = openai.generate_advisory(weather_data, crop_type, lang="en")
        message_sw = openai.generate_advisory(weather_data, crop_type, lang="sw")
        
        Create WeatherBroadcast record
        
        For each subscribed farmer in ward with matching crop:
            Follow same two-stage delivery as Broadcast Message System
```

### Manual Trigger

Admins can trigger a test via `POST /api/admin/weather/trigger-broadcast`.

---

## 13. Real-Time Communication

### Socket.IO Server

Mounted at `/ws/socket.io/` (FastAPI sub-application).

**Authentication**: JWT access token passed in Socket.IO handshake auth:
```javascript
io(backendUrl, {auth: {token: accessToken}, path: "/ws/socket.io/"})
```

Server validates token on connection and associates socket with `user_id`.

### Events (Server → Client)

| Event | Payload | Triggered By |
|-------|---------|--------------|
| `message_received` | `{ticket_id, message: {id, body, from_source, created_at}}` | New customer/EO message |
| `ticket_resolved` | `{ticket_id}` | Ticket resolution |
| `whisper` | `{ticket_id, content: str}` | AI suggestion for EO |
| `broadcast_update` | `{broadcast_id, status}` | Broadcast delivery progress |
| `playground_response` | `{message_id, content, response_time_ms}` | AI playground reply |

### Room Strategy

- EOs join rooms for their accessible ward IDs on connection
- Messages emitted to all EOs with access to the relevant ward
- Multi-device: one user can have multiple concurrent socket connections

### Push Notifications (Fallback)

When WebSocket is disconnected or message is missed:
- Backend sends push notification via Expo Notifications API
- Payload includes `ticketId`, `messageId`, `customerName`
- Mobile app routes to `/chat/[ticketId]` on tap
- On reconnect, WebSocket syncs any missed events

---

## 14. Administrative Hierarchy

### Level Structure

```
Country (Level 1)
└── Region (Level 2)
    └── District (Level 3)
        └── Ward (Level 4)
```

Example path: `"Kenya > Murang'a > Kiharu > Wangu"`

### EO-to-Area Assignment

- EO assigned to any level node via `user_administrative` table
- System automatically expands to all descendant ward IDs for data access
- EO assigned to "Murang'a Region" → sees all customers in all wards within that region

```python
def get_descendant_ward_ids(db, admin_id) -> List[int]:
    area = db.get(Administrative, admin_id)
    if area.level.name == "Ward":
        return [admin_id]
    
    children = db.query(Administrative).filter_by(parent_id=admin_id).all()
    ward_ids = []
    for child in children:
        ward_ids.extend(get_descendant_ward_ids(db, child.id))
    return ward_ids
```

### Ancestor Routing (Notifications)

For push notifications and Socket.IO events, the system routes to EOs assigned to the ticket's ward **and** all ancestor nodes:

```python
def get_ancestor_ids(db, ward_id) -> List[int]:
    area = db.get(Administrative, ward_id)
    ids = []
    current = area.parent
    while current:
        ids.append(current.id)
        current = current.parent
    return ids
```

---

## 15. Frontend Web Dashboard

### Technology

Next.js 15 App Router, React 19, Tailwind CSS 4, Axios, Socket.IO-client.

### Pages

| Route | Auth Required | User Types | Description |
|-------|---------------|------------|-------------|
| `/` | No | All | Shows login form OR dashboard if logged in |
| `/customers` | Yes | admin, eo | Customer list with search, filters, pagination |
| `/users` | Yes | admin | User management (CRUD + invitation) |
| `/knowledge-base` | Yes | admin, eo | KB list and document management |
| `/knowledge-base/[id]` | Yes | admin, eo | Documents within a specific KB |
| `/analytics` | Yes | admin, eo | Ticket tags, crop distribution charts |
| `/playground` | Yes | admin | AI service test interface (chat + WebSocket) |
| `/qr` | No | Public | WhatsApp QR code for farmer onboarding |
| `/forgot-password` | No | Unauth | Password reset request |
| `/reset-password/[token]` | No | Unauth | Password reset form |
| `/accept-invitation/[token]` | No | Unauth | Invitation acceptance + password set |

### Authentication (AuthContext)

- Access token stored in memory (JS variable, cleared on logout)
- User data stored in `localStorage` for session persistence across page reloads
- Refresh token stored in httpOnly cookie (set by backend, not accessible to JS)
- Axios interceptor: on 401 response, call `POST /api/auth/refresh`, retry original request

```
Login → AuthContext.login()
     → POST /api/auth/login
     → Store: token in memory, user in localStorage
     → Backend sets httpOnly refresh cookie
     → Redirect to Dashboard

Page Reload → Check localStorage for user
           → Attempt POST /api/auth/refresh (uses cookie)
           → If success: restore token in memory
           → If fail: clear localStorage → show Login
```

### Key Components

**AdministrativeCascadeFilter** — Renders cascading dropdowns (Country → Region → District → Ward). Loads each level from API dynamically when parent changes. Used in customer/user creation forms and analytics filters.

**TagBadge** — Colored badge for ticket categories with distinct icon per tag type (fertilizer=green, pest=red, pre_planting=yellow, harvesting=orange, irrigation=blue, other=gray).

**Analytics Dashboard** — Three parallel API calls on mount: ticket-tags, crop-distribution, crop-distribution/matrix. Bar charts for tag distribution; county × crop matrix table. Date range filter triggers re-fetch. Includes "Generate API Token" for Streamlit/external dashboard access.

**Playground** — Socket.IO connected with JWT auth. User sends message → `POST /api/admin/playground/chat` → joins session room → receives `playground_response` event with AI reply and response_time_ms.

### API Proxy Route

`/api/[...path]/route.js` — Next.js API route that proxies all `/api/*` calls to the backend. This avoids CORS issues and allows cookie forwarding.

---

## 16. Mobile App

### Technology

React Native 0.81, Expo 54, Expo Router 6, expo-sqlite 16, expo-secure-store 15, expo-notifications 0.32, Socket.IO-client 4.8.

### Navigation Structure

```
RootLayout (_layout.tsx)
└── Providers: SQLiteProvider → NetworkProvider → AuthProvider
    → NotificationProvider → WebSocketProvider → TicketProvider
    ├── Protected Stack (authenticated)
    │   ├── Bottom Tabs
    │   │   ├── /home — Dashboard, stats, bulk message button
    │   │   ├── /inbox — Open/Resolved ticket list with search
    │   │   ├── /stats — Detailed statistics with period selector
    │   │   └── /account — Profile + version check + logout
    │   ├── /chat/[ticketId] — Full chat view
    │   └── /broadcast/... — Bulk message flow
    │       ├── /contact — Select farmers or browse groups
    │       ├── /create — Create new broadcast group
    │       ├── /group/[chatId] — Group detail + members
    │       └── /group/members — Members management
    └── Protected Stack (unauthenticated)
        └── /login — Email/password login
```

### SQLite Schema (Version 10)

Local database `agriconnect.db` with the following tables:

**users** — Cached extension officer profile  
**customer_users** — Cached farmer data for display in chat  
**messages** — All chat messages (inbound + outbound)  
**tickets** — All tickets (open + resolved)  
**profile** — Current user's session (accessToken, settings)  
**user_stats** — Cached statistics (week/month/all-time)

### DAO Layer

`DAOManager` provides unified access:

```typescript
const db = useDatabase(); // from SQLiteProvider
const dao = useMemo(() => new DAOManager(db), [db]);

// Usage:
dao.ticket.findByStatus("open", page=1, size=10)
dao.message.findByTicketId(ticketId, limit=20)
dao.profile.getCurrentProfile(db)
dao.userStats.saveFromApi(db, apiData)
```

**Single database connection rule**: Never call `openDatabaseSync()` directly — always use the `useDatabase()` hook from `SQLiteProvider`.

### Offline Support

| Feature | Offline | Online Required |
|---------|---------|-----------------|
| View cached tickets | ✓ | |
| View chat history | ✓ | |
| View profile | ✓ | |
| View cached stats | ✓ | |
| Send messages | | ✓ |
| Broadcast to farmers | | ✓ |
| Load next page (pagination) | | ✓ |
| Real-time updates | | ✓ |

### Push Notifications

Setup:
1. On login: `registerForPushNotificationsAsync()` → get Expo push token
2. `POST /api/devices` with `{push_token, administrative_id, app_version}`
3. On logout: `DELETE /api/devices/{device_id}` or `POST /api/auth/logout-devices`

Handling:
```
Notification arrives:
  If ticketId == currentActiveTicket → suppress banner (user already in chat)
  Else → show banner + play sound + update badge

User taps notification:
  Extract ticketId from payload
  Navigate to /chat/[ticketId]

Fallback (WebSocket down):
  ticketEmitter.emit(MESSAGE_CREATED, payload)
  Inbox and ChatScreen both listen → update state
```

### WebSocket (Socket.IO)

Connection managed by `WebSocketProvider`:
- Connects using `accessToken` from SecureStore
- Auto-reconnects on token change (`tokenEmitter` event)
- Events handled: `message_received`, `ticket_resolved`, `whisper`

On `message_received`:
1. Upsert message to SQLite
2. Add to messages state in ChatScreen (if open)
3. Update unread count in TicketProvider
4. Scroll to bottom
5. Fetch AI suggestion (async)

### Token Management

```
SecureStore: accessToken + refreshToken (encrypted)
                    ↓
           ApiClient caches accessToken in memory
                    ↓
           On 401 → get refreshToken from SecureStore
                  → POST /auth/refresh
                  → Update memory cache
                  → emit TOKEN_CHANGED
                  → WebSocketProvider reconnects with new token
```

---

## 17. Configuration Reference

### Backend Environment Variables (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT access token signing secret |
| `REFRESH_SECRET_KEY` | Yes | JWT refresh token signing secret |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio account identifier |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio API auth token |
| `TWILIO_WHATSAPP_NUMBER` | Yes | e.g. `whatsapp:+14155238886` |
| `OPENAI_API_KEY` | Yes (if openai enabled) | OpenAI API key |
| `SMTP_HOST` | Yes | Email server host |
| `SMTP_PORT` | Yes | Email server port |
| `SMTP_USER` | Yes | Email sender address |
| `SMTP_PASS` | Yes | Email sender password |
| `SMTP_USE_TLS` | No | `true`/`false` |
| `WEBDOMAIN` | Yes | Public domain for email links (e.g. `https://app.example.com`) |
| `EXPO_TOKEN` | Yes | Expo push notification access token |
| `GOOGLE_SERVICES_JSON` | Yes | Path to Firebase google-services.json |
| `TESTING` | No | Set to `true` to mock Twilio in tests |
| `ENVIRONMENT` | No | `production` enables Secure cookies |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Default: 1440 (24h) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Default: 30 |

### Mobile App Environment Variables (.env)

| Variable | Description |
|----------|-------------|
| `EXPO_PUBLIC_AGRICONNECT_SERVER_URL` | Backend API base URL (e.g. `https://api.example.com/api`) |

### config.json (Backend)

```json
{
  "message_limit": 10,

  "whatsapp": {
    "templates": {
      "confirmation": {"sid": "HX...", "sid_sw": "HX..."},
      "reconnection":  {"sid": "HX...", "sid_sw": "HX..."},
      "broadcast":     {"sid": "HX...", "sid_sw": "HX..."}
    },
    "button_payloads": {
      "escalate": "escalate",
      "read_broadcast": "read_broadcast",
      "reconnect": "reconnect"
    },
    "retry": {
      "enabled": true,
      "max_attempts": 3,
      "backoff_minutes": [5, 15, 60]
    }
  },

  "escalation": {
    "chat_history_limit": 20,
    "reply_history_limit": 10
  },

  "openai": {
    "enabled": true,
    "default_model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 1000,
    "timeout": 30,
    "max_retries": 3,
    "models": {
      "chat": "gpt-4o-mini",
      "chat_advanced": "gpt-4o",
      "transcription": "whisper-1",
      "embedding": "text-embedding-3-small",
      "moderation": "omni-moderation-latest"
    },
    "features": {
      "speech_to_text": {"enabled": true, "language": "en"},
      "onboarding": {"enabled": true},
      "content_moderation": {"enabled": true, "auto_flag": true},
      "follow_up": {"enabled": true}
    }
  },

  "crop_types": ["Avocado", "Potato", "Dairy"],

  "contact_info": {
    "name": "Admin",
    "phone_number": "+1234567891"
  },

  "weather": {
    "broadcast_enabled": true,
    "intent_enabled": true,
    "intent_keywords": ["weather", "forecast", "hali ya hewa"],
    "forecast_days": 6
  }
}
```

---

## 18. End-to-End Data Flows

### Flow 1 — New Farmer First Message

```
Farmer sends WhatsApp: "Hello, my avocado leaves are turning yellow"

1. Twilio delivers to POST /api/whatsapp/webhook
2. Duplicate check: MessageSid not in DB → proceed
3. Customer lookup: phone not found → create new customer (language=EN detected)
4. New customer: skip reconnection check
5. Skip account deletion: Body not "delete"
6. Data consent: customer.data_consent_given = False
   → Send: "AgriConnect collects your farming data to improve advice. Do you agree?"
   → Set data_consent_asked = True
   → RETURN (wait for consent reply)

Farmer replies: "Yes"

7. Consent received: set data_consent_given = True
8. Check onboarding: status = NOT_STARTED
   → Ask: "Which area do you farm in?"
   → Set onboarding_status = IN_PROGRESS, current_field = "administration"
   → RETURN

Farmer replies: "I am in Kiharu"

9. Onboarding: extract "Kiharu" → fuzzy match against wards → high confidence
   → Save CustomerAdministrative(customer_id, ward_id for Kiharu)
   → Ask: "What crop do you mainly grow? (Avocado / Potato / Dairy)"
   → Set current_field = "crop_type"
   → RETURN

Farmer replies: "avocado"

10. Crop matched → save profile_data.crop_type = "Avocado"
    → Ask: "What is your gender? (optional)"
    → Set current_field = "gender"

Farmer replies: "male"

11. Gender parsed → save profile_data.gender = "MALE"
    → Ask: "What year were you born? (optional)"

Farmer replies: "skip"

12. Birth year: no valid year → skip (optional field)
    → onboarding_status = COMPLETED
    → Send weather subscription buttons (requires_weather_buttons=True)
    → RETURN

Farmer taps "Yes, sign me up" for weather

13. Weather subscription: set weather_subscribed = True
    → Send: "You are now subscribed to daily weather alerts"

Farmer sends: "My avocado leaves are turning yellow"

14. Onboarding complete, no active ticket
15. Follow-up enabled: no FOLLOW_UP in history
    → Generate follow-up via OpenAI: "How long have the leaves been yellow? Have you noticed any insects?"
    → Send to farmer, store as MessageType.FOLLOW_UP
    → RETURN

Farmer replies: "About 2 weeks, yes I see some small insects"

16. Follow-up already asked; queue REPLY job to external AI
    → Create message in DB (from_source=CUSTOMER)
    → Query active KB for "avocado yellow leaves insects" (crop_type=Avocado filter)
    → POST {chat_url} with job_id, message, history, kb_context
    → Send acknowledgment to farmer with "Talk to an expert" escalate button

17. External AI calls back: POST /api/callback/ai
    → Strip citations from response
    → Store as DB message (from_source=LLM, type=REPLY)
    → Send via Twilio to farmer: "Yellow leaves with insects may indicate spider mites..."
    → Update delivery_status: PENDING → SENT → DELIVERED
```

---

### Flow 2 — Farmer Escalates to Extension Officer

```
Farmer taps "Talk to an expert" button

1. Webhook: ButtonPayload = "escalate"
2. No open ticket exists → create ticket
   → ticket_number = "TKT-0042"
   → administrative_id = customer's ward ID
3. Queue WHISPER job to external AI
   → AI generates EO suggestion: "This looks like a spider mite infestation. Recommend: neem oil spray"
4. Notify EOs in Kiharu ward:
   → Socket.IO emit "ticket_created" to connected EOs
   → Push notification to all EO devices in Kiharu ward
5. External AI callback (WHISPER):
   → Store message (from_source=LLM, type=WHISPER)
   → Socket.IO emit "whisper" event to EOs with ticket access

EO receives push notification → opens mobile app → navigates to /chat/TKT-0042

6. Mobile app loads ticket: GET /api/tickets/42
7. Load messages: GET /api/tickets/42/messages?limit=20
8. Display messages in FlatList; WHISPER shown as special AI suggestion chip
9. EO reads AI suggestion, types reply: "Hello! This is spider mite damage..."
10. POST /api/messages {ticket_id: 42, body: "Hello...", from_source: 2 (USER)}
11. Backend stores message → sends via Twilio → farmer receives reply
12. Delivery status updated: PENDING → SENT → DELIVERED → READ
13. EO taps resolve → PATCH /api/tickets/42 {status: "resolved"}
14. Backend triggers ticket auto-tagging (OpenAI classifies as PEST with confidence 0.87)
15. Socket.IO emit "ticket_resolved" to all EOs with ticket access
```

---

### Flow 3 — Admin Sends Broadcast to Avocado Farmers

```
Admin logs into web dashboard → Customers page → selects 50 avocado farmers
→ Creates broadcast group "Kiharu Avocado Farmers"
→ POST /api/broadcast/groups {name, customer_ids: [1, 2, ..., 50]}

Admin composes broadcast message:
→ POST /api/broadcast/messages {message: "Avocado spraying season...", group_ids: [group_id]}
→ POST /api/broadcast/messages/{id}/send (trigger delivery)

For each of 50 farmers:
1. Send WhatsApp template message (confirmation template)
   → "AgriConnect has a message for you. Tap to read."
   → Button: "Read Message" (payload: read_broadcast)
   → Store confirm_message_sid, set recipient status = PENDING

Farmer taps "Read Message":
2. Webhook: ButtonPayload = "read_broadcast"
3. Find broadcast_recipient by confirm_message_sid
4. Send actual message text to farmer
5. Update recipient: status = DELIVERED, actual_message_sid, delivered_at

Admin sees live delivery progress in dashboard:
→ GET /api/broadcast/messages/{id} → per-recipient status
→ 47 DELIVERED, 2 PENDING, 1 FAILED
→ Failed recipients auto-retried after 5 minutes
```

---

### Flow 4 — Daily Weather Broadcast

```
6:00 AM UTC: Celery scheduled task fires

For each ward with weather subscribers:
1. Get ward lat/long from administrative table
2. Fetch 6-day forecast from Google Weather API
3. Get unique crop types for subscribed farmers in this ward
4. For each crop_type (e.g. Avocado):
   a. Generate English advisory via OpenAI:
      "Expect 3 days of rain followed by sunshine. For avocado: protect fruit..."
   b. Generate Swahili advisory via OpenAI:
      "Tunatarajia mvua kwa siku 3... Kwa parachichi: linda matunda..."
   c. Create WeatherBroadcast record
   d. For each subscribed farmer in ward with that crop:
      → Send confirmation template (same two-stage flow as broadcast)
      → Farmer taps to read → receives localized advisory
```

---

*End of AgriConnect Functional Specification*
