# Akvo Connect – Technical Summary & Architectural Proposal

**Context:** Discussion between Galih & Deden | 13 October 2026  
**Status:** Completed Proposal & Evaluation Draft  
**Target Systems:** AgriConnect (`backend`, `frontend`, `app`), Akvo RAG (`akvo/akvo-rag` - `epic/rag-monorepo-mcp` / PR #163)

---

## Executive Summary

The objective of this document is to establish a clear architectural roadmap for transforming **AgriConnect** from an agriculture-specific, single-tenant deployment into **Akvo Connect**—a generic, sector-agnostic advisory platform that can serve multiple organizations across Agriculture, Public Health (Johns Hopkins University), and Water/WASH (UNICEF, WaterNet).

Following our architectural discussions:
1. **Existing Technical Debt** (including consolidating agriculture branches and migrating to the newly consolidated **Akvo RAG Monorepo PR #163**) must be addressed as Step 0.
2. **Each tenant must maintain its own distinct WhatsApp number** for organizational identity, partner credibility, and regulatory compliance. Therefore, the hypothetical concept of sharing a single WhatsApp number across organizations has been **dismissed**.
3. Two concrete architectural models are evaluated:
   - **Option 1: Shared Multi-Tenant Architecture** (One deployment, shared database with `tenant_id` isolation, edge channel resolution).
   - **Option 2: Independent Deployment per Tenant** (Dedicated deployments per tenant, unified codebase on `main`, interactive provisioning CLI, and centralized CI/CD).

---

## 1. Existing Technical Debt (Prerequisite Cleanup)

Before expanding to new sectors or provisioning additional organizations, the following technical debt must be resolved on `main`.

### 1.1 Akvo RAG Monorepo Migration (`akvo/akvo-rag` PR #163)

The new Akvo RAG architecture developed in branch `epic/rag-monorepo-mcp` (PR #163) modernizes the AI engine but has not yet been connected to AgriConnect:

* **Key PR #163 Changes:**
  - Consolidated vector microservices into a unified monorepo.
  - Eliminated Celery & RabbitMQ in favor of native asynchronous **Redis Request-Reply queues** with `correlation_id` via `MCPQueueDispatcher`.
  - Added dedicated workers: `vector-kb-mcp` (Query RPC) and `vector-kb-mcp-ingestion` (Document parsing & chunking).
  - Modernized data layer to **PostgreSQL 17** (`asyncpg` with dedicated `alembic_version_vkb`), **MinIO S3** (`:9010`) for raw files/images, and ChromaDB (`:8002`) with SQLite WAL mode.
* **Migration Requirements:**
  1. **Update Akvo RAG Manifests & Deployment:** Modify `akvo-rag` deployment manifests, Docker Compose, and infrastructure orchestration to support the new 8-container topology (Redis, MinIO, dual workers, PostgreSQL 17).
  2. **Transition Backend Integration:** Update AgriConnect's legacy `ExternalAIService` to communicate with the Redis-backed RPC interface.
  3. **Develop KB Migration & Ingestion Pipeline Script (RAG-02):** Because there is currently no automated script to extract and structure legacy Knowledge Bases, a migration and re-ingestion tool must be built to:
     - Connect to legacy storage and download all existing documents.
     - Folderize files cleanly by `KB Name` and map them to their corresponding `KB ID`.
     - Re-upload raw files into the new MinIO S3 bucket (`tenant-{id}-kb`).
     - **Re-execute the complete Data Ingestion Pipeline:** Dispatch parsing/chunking tasks to the new `vector-kb-mcp-ingestion` Redis queue worker, generate dense embeddings, populate the new vector collections in Chroma/Qdrant, and monitor/verify asynchronous callback status (`/api/callback/kb`) until index readiness is confirmed.
  4. **Integration & Regression Testing:** Validate webhook callback schemas (`/api/callback/ai` and `/api/callback/kb`) against the new monorepo.

### 1.2 Comprehensive Inventory of Agriculture-Specific Code & Artifacts

Beyond the high-level onboarding and escalation notes, an in-depth codebase audit reveals deep-rooted agricultural coupling across all layers:

#### A. Database Schema & ORM Models
* **`models/user.py`:** Role enum `UserType` currently hardcodes `EXTENSION_OFFICER = "eo"`. Rather than creating separate sector-specific user roles (e.g., CHW, Water Technician), **this role will be consolidated into a single General User Type** (e.g., `OFFICER` or `STAFF` / `FIELD_OFFICER`) for all tenant sectors. Operational staff across agriculture, water, and health perform the exact same workflows (responding to escalated tickets, broadcasting announcements, viewing assigned geographic jurisdictions). Any sector-specific naming differences are purely cosmetic and handled via tenant display configuration (`officer_label: {"en": "Health Worker"}`).
* **`models/customer.py`:** The `Customer` model contains a hardcoded Python property `@property def crop_type(self)`.
* **`models/weather_broadcast.py`:** The database table `weather_broadcasts` explicitly includes a `crop_type` column (`Column(String(100))`), and broadcast recipients are grouped strictly by `(administrative_id, crop_type)`.

#### B. API Endpoints & Routers
* **`routers/crop_types.py`:** An entire dedicated API router (`GET /api/crop-types`) exists solely to serve crop lists from configuration.
* **`routers/statistic.py`:** Endpoints hardcode agricultural entity paths and Pydantic schemas:
  - `GET /api/statistic/farmers/stats` (`FarmerStatsResponse`)
  - `GET /api/statistic/farmers/stats/by-ward` (`FarmerStatsByWardResponse`)
  - `GET /api/statistic/farmers/registrations`
  - `GET /api/statistic/aggregate/farmers` (`FarmerAggregateResponse`)
  - `GET /api/statistic/crops/distribution` (`CropDistributionResponse`)
  - `GET /api/statistic/crops/distribution/matrix` (`CropDistributionMatrixResponse`)
* **`routers/user_stats.py`:** Officer metrics return `farmers_reached` instead of generic `beneficiaries_reached` or `citizens_reached`.
* **`routers/customers.py`:** The CSV export handler explicitly hardcodes `"Crop Type"` as a CSV column header and extracts `customer.crop_type`.

#### C. Backend Services & Business Logic
* **`services/statistic_service.py`:** Over 600 lines of query logic filtering on `Customer.profile_data.op("->>")("crop_type")` and computing farmer metrics (`active_farmers`, `dormant_farmers`, `farmers_with_questions`, `farmers_who_escalated`, `avg_questions_per_farmer`).
* **`services/onboarding_service.py`:** Contains dedicated AI crop extraction methods (`_normalize_crop_name`, `_build_crop_identification_prompt`, `resolve_crop_ambiguity`, `_format_crops_numbered`, `_get_crop_by_number`) and multiple explicit `if field_name == "crop_type":` branches.
* **`services/follow_up_service.py`:** Hardcoded English and Swahili system prompts instructing OpenAI: *"You are a helpful agricultural assistant. A farmer has just asked a question... What specific crop or livestock is affected?"*, along with the `FarmerContext` dataclass.
* **`utils/conversation_summary.py`:** `get_customer_context()` extracts `"farmer_id"` and `"crop"`.
* **`utils/i18n.py`:** Dedicated helper `get_crop_name_translated()`.

#### D. Prompts, Locales, and Email Templates
* **`templates/invitation.html` & `.txt`:** "Welcome to AgriConnect... Agricultural Extension Platform... Customer and farmer management... Agricultural resources and information".
* **`templates/advisory_prompt.txt` & `generic_weather_prompt.txt`:** Prompts tailored with "farming neighbor in Kenya", livestock rules, spraying calendars, and pest terminology.
* **`locales/en.json` & `locales/sw.json`:** Hardcoded `"crops"` dictionary (`Avocado`, `Cacao`, `Potato`, `Dairy`) and UI prompts referencing "extension service provider" and "Talk to Officer".
* **`config.py` & `config.template.json`:** Fallback `openai_onboarding_system_prompt` defaults to "helpful agricultural assistant helping farmers", and `officer_label` defaults to "Extension Officer".

#### E. Mobile Application (`/app/` - React Native Expo)
* **Local SQLite Schema:**
  - `customer_users` table has an explicit column `cropType TEXT` (Migration `011_alter_customer_add_profile.ts`).
  - `user_stats` table has explicit columns `farmers_reached_week`, `farmers_reached_month`, `farmers_reached_all` (Migration `013_create_user_stats.ts`).
  - `customerUserDAO.ts` & `userStatsDAO.ts` contain hardcoded typings and queries for `cropType` and `farmers_reached`.
* **Mobile UI & State Management:**
  - `BroadcastContext.tsx`: Explicit `CropType` interface and `cropTypes` filter state.
  - `components/broadcast/filter-modal.tsx`: Dedicated "Crop Types" section.
  - `components/broadcast/filter-pills.tsx`: Dedicated "Crop Type Pills".
  - `components/chat/customer-profile-modal.tsx`: Modal header "Farmer Profile" and "Crop Type" field display.
  - `services/api.ts`: Calls `${this.baseUrl}/crop-types/` and parses `farmers_reached`.

#### F. Frontend Web Application (`/frontend/` - Next.js)
* **`app/analytics/page.js`:** UI components for "Crop Distribution Bar Chart", "Crop Distribution Matrix", and "Total Farmers (by Crop)".
* **`components/customers/EditCustomerModal.js`:** Calls `/api/crop-types/` and renders a dedicated "Crop Type" dropdown.
* **`components/Dashboard.js`:** Welcome text: "As an extension officer, you're at the forefront of agricultural innovation... improve crop yields and farmer livelihoods."
* **`app/layout.js`, `app/page.js`, `app/forgot-password/page.js`:** Footer copyright: "AgriConnect © 2025. Connecting farmers with agricultural extension officers".

#### G. Seeders & Test Fixtures
* **`seeder/customer.py` & `seeder/ticket.py`:** Generates fake data using `settings.crop_types`, Tanzanian/Kenyan farmer personas, and agriculture ticket descriptions.
* **Test Suites:** Extensive test files (`test_weather_intent.py`, `test_whisper_command.py`, `test_whatsapp.py`) rely on hardcoded crops ("Avocado", "Maize", "Coffee").

---

## 2. Architectural Challenges

| Challenge | Core Question | Architectural Strategy |
| :--- | :--- | :--- |
| **2.1 Generic Mobile App & General User Type** | How can field staff across agriculture, water, and health use a single mobile app? | Unify operational roles into a single **General User Type** (`OFFICER` / `STAFF`) with identical core permissions; apply dynamic terminology bootstrap after login (`officer_label`); reset local SQLite when switching accounts; sector-based feature toggling. |
| **2.2 Twilio & Channel Management** | How to securely manage separate credentials per tenant? | Encrypted credential vault in database; provider abstraction layer; Twilio subaccounts. |
| **2.3 WhatsApp Number Registration** | How can partner-owned WhatsApp numbers be onboarded without friction? | Standardized Onboarding Playbook (Meta Embedded Signup or Twilio Senders API). |
| **2.4 WhatsApp Template Management** | How to manage independent template IDs across tenants? | Store template IDs per tenant channel; explore programmatic template submission via Twilio API. |
| **2.5 Migrating `config.json` to Database (Decided)** | Should we keep `config.json` or migrate to DB? | **Decision: Fully migrate runtime tenant configuration to PostgreSQL (`tenant_configs` JSONB).** Global infrastructure settings stay in `.env`, while all tenant-specific workflows, hierarchies, and channel settings live in the DB. `config.json` is preserved solely as an initial seed blueprint. |

> [!IMPORTANT]
> **Architectural Decision: Retiring Runtime `config.json` in Favor of PostgreSQL JSONB**
> Following architectural evaluation, **we will NOT maintain `config.json` as the runtime configuration source**. Instead, configuration is partitioned into two distinct tiers:
> 1. **Machine & Infrastructure Tier (`.env` only):**
>    - Parameters required before database connection: `DATABASE_URL`, `REDIS_URL`, `MASTER_ENCRYPTION_KEY` (for Fernet token encryption in DB), and `ENVIRONMENT`.
> 2. **Tenant & Business Tier (PostgreSQL Tables):**
>    - `tenants`: Core identity (`slug`, `name`, `sector`, `is_active`).
>    - `tenant_channels`: Phone numbers, encrypted Twilio tokens, WABA IDs, and WhatsApp template SIDs.
>    - `tenant_configs`: JSONB schema storing administrative hierarchy, dynamic onboarding fields, officer terminology (`officer_labels`), sector feature toggles, and RAG knowledge base assignments.
> 3. **High-Performance In-Memory TTL Cache (5 Minutes):**
>    - To eliminate repeated database queries on every WhatsApp webhook, the backend leverages the proven **5-minute In-Memory TTL Cache** pattern (already running in `service_token_service.py`). Lookups take **< 1ms**.
> 4. **Zero-Downtime Hot Reloading:**
>    - Updating templates or terminology no longer requires server restarts (`docker compose restart`). Changes in the database take effect immediately on next cache expiration or on update trigger.
> 5. **Repurposing `config.json`:**
>    - `config.json` is renamed to `config.blueprint.json`, used strictly as default template values during initial database seeding.

---

## 3. Detailed Architectural Proposals

### Option 1: Shared Multi-Tenant Architecture

In this model, all partner organizations share a **single application deployment, single backend, and shared database** with strict row-level isolation via `tenant_id`.

> **Note on WhatsApp Numbers:** Each tenant maintains its **own dedicated WhatsApp number and Twilio credentials**. Messages sent to a specific number are resolved at the edge to the corresponding tenant.

#### Architecture Diagram (Option 1: Shared Multitenancy)

```mermaid
flowchart TD
    subgraph Citizens["Citizens & Field Users"]
        C_AGRI["Farmer (Kenya)"] -->|"1. Send WhatsApp (+254...)"| TW_KENYA["Twilio / Meta (Kenya WABA)"]
        C_WATER["Caretaker (Mali)"] -->|"1. Send WhatsApp (+223...)"| TW_MALI["Twilio / Meta (Mali WABA)"]
        C_HEALTH["Patient (Sudan)"] -->|"1. Send WhatsApp (+249...)"| TW_SUDAN["Twilio / Meta (Sudan WABA)"]
    end

    subgraph Edge["Shared Edge & Routing Layer"]
        TW_KENYA -->|"2. Webhook POST"| RES["Tenant Resolver<br/>(Lookup by Destination Address)"]
        TW_MALI -->|"2. Webhook POST"| RES
        TW_SUDAN -->|"2. Webhook POST"| RES
    end

    subgraph Core_Platform["Akvo Connect Platform (Shared Cluster)"]
        RES -->|"3. Inject TenantContext"| API["FastAPI Backend Cluster"]
        
        STAFF["Staff Mobile / Web"] -->|"3b. Auth (JWT with tenant_id)"| API
        
        API -->|"4. Scoped Query/Write"| DB[("PostgreSQL 17<br/>Shared DB with tenant_id<br/>Scoped Query Helpers")]
    end

    subgraph Akvo_RAG["Akvo RAG Monorepo (PR #163)"]
        RAG_API["Akvo RAG Backend (:8010)"]
        REDIS_RPC[("Redis RPC Queues<br/>(MCPQueueDispatcher)")]
        VKB["vector-kb-mcp Workers<br/>(Scoped by tenant_id)"]
        MINIO[("MinIO S3 Storage<br/>bucket: tenant-{id}-kb")]
        VDB[("Vector DB (Qdrant / Chroma)<br/>Payload Filter: tenant_id")]
        
        RAG_API -->|"6. Enqueue RPC"| REDIS_RPC --> VKB
        VKB -->|"7. Vector & Document Lookup"| MINIO & VDB
    end

    API -->|"5. POST /chat (Bearer token & kb_ids)"| RAG_API
    RAG_API -.->|"8. Webhook Callback (/api/callback/ai)"| API
    API -->|"9. Outbound reply via Tenant Credentials"| Citizens
```

##### Architectural Execution Flow by Step (Option 1):
1. **Step 1 (Inbound Citizen Messaging):** A citizen (e.g., farmer, water caretaker, or patient) sends an SMS or WhatsApp message to their local organization's dedicated phone number (`+254...`, `+223...`, `+249...`).
2. **Step 2 (Channel Inbound Webhook):** The communications provider (Twilio or Meta WhatsApp Business API) receives the message and triggers an HTTP POST webhook to the platform's shared edge routing layer.
3. **Step 3 (Tenant Resolution & Context Injection):** The **Tenant Resolver** inspects the inbound destination address (`To`), maps it to the registered organization in the `tenant_channels` registry, initializes an active `TenantContext(tenant_id)`, and forwards the request to the FastAPI application cluster. *(In parallel, **Step 3b** allows field staff to authenticate via mobile/web dashboards using JWTs carrying their assigned `tenant_id`)*.
4. **Step 4 (Scoped State & Ticket Persistence):** The backend queries and persists citizen profiles, message histories, and tickets in PostgreSQL 17 using tenant-scoped query helpers (`WHERE tenant_id = ...`) to prevent cross-tenant data bleed.
5. **Step 5 (Centralized AI Inference Request):** The backend calls the shared Akvo RAG service (`POST /chat`) using the tenant's Bearer token (retrieved with <1ms latency from the 5-minute In-Memory TTL cache) and authorized `knowledge_base_ids`.
6. **Step 6 (RPC Queuing & Dispatch):** The Akvo RAG API dispatches the task into Redis RPC queues (`MCPQueueDispatcher`) for background worker consumption.
7. **Step 7 (Vector Search & Knowledge Retrieval):** `vector-kb-mcp` worker processes query MinIO S3 storage and the Vector DB (Qdrant/Chroma), applying hard payload filters strictly isolated to the tenant's knowledge bases.
8. **Step 8 (Asynchronous Webhook Callback):** Once RAG inference is generated, the Akvo RAG cluster sends an asynchronous callback to the platform's callback endpoint (`/api/callback/ai`).
9. **Step 9 (Outbound Response Delivery):** The backend delivers the AI advisory response or escalation update back to the citizen via WhatsApp using the tenant's outbound credentials.

#### User Workflow (Option 1: Shared Multitenancy)

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Akvo Platform Admin
    actor Partner as Partner Admin (e.g. UNICEF)
    actor Citizen as Citizen / Water Caretaker
    actor Staff as Field Officer / Technician
    participant Platform as Akvo Connect (Shared)
    participant Channel as Twilio / Meta API

    Note over Admin,Platform: 1. Tenant Provisioning
    Admin->>Platform: Create Tenant ('unicef-water', timezone, sector='water')
    Partner->>Platform: Input Twilio Credentials, WABA ID, Phone Number (+223...)
    Platform->>Channel: Validate credentials & register webhook URL

    Note over Citizen,Platform: 2. Inbound Communication
    Citizen->>Channel: Send WhatsApp message to +223...
    Channel->>Platform: Webhook POST (To: +223..., Body: "Pump broken")
    Platform->>Platform: Resolve destination address (+223...) -> Tenant: 'unicef-water'
    Platform->>Platform: Process message within TenantContext('unicef-water')

    Note over Staff,Platform: 3. Staff Operation
    Staff->>Platform: Login via universal mobile app (JWT carries tenant_id)
    Platform-->>Staff: Return water-sector terminology & theme ('Caretaker', 'Water Point')
    Staff->>Platform: Review and resolve escalated ticket
```

##### Workflow Description by Persona:

1. **Akvo Platform Admin (Tenant Onboarding):**
   * Logs into the centralized Akvo Admin Console and registers a new organization profile (e.g., `unicef-water`, Mali, `UTC+0`, Sector: `water`).
   * Configures sector-specific features (e.g., enable photo diagnostics, disable agriculture weather forecasts).
2. **Partner Admin (Channel & Content Setup):**
   * Accesses the tenant management view to input their organization's dedicated Twilio credentials (Subaccount SID, Auth Token) and registered WhatsApp Business phone number (`+223...`).
   * Enters approved WhatsApp template IDs for initial outreach, escalation notifications, and reconnection triggers.
   * Uploads sector-specific Knowledge Base manuals (PDF/DOCX/PPTX) which are ingested into Akvo RAG and bound to their `tenant_id`.
3. **Citizen / End-User (Daily Inbound Advisory):**
   * A citizen (e.g., water point caretaker) sends a message or photo of a broken handpump to the partner's dedicated WhatsApp number.
   * The webhook arrives at the shared Akvo Connect edge layer. The **Tenant Resolver** inspects the destination number (`To: +223...`), matches it in the channel registry, and initializes the execution context under `TenantContext('unicef-water')`.
   * Akvo RAG generates grounded diagnostic suggestions. If the AI confidence threshold is met and auto-reply is enabled, the citizen receives immediate guidance; otherwise, a ticket is escalated to field staff.
4. **Field Staff / Extension Officer (Ticket Handling & Mobile App):**
   * The officer opens the single **universal Akvo Connect mobile app** and logs in with their account.
   * Upon successful authentication, the mobile app inspects the user's `tenant_id` claim, fetches the dynamic tenant profile, and applies sector terminology:
     * UI labels automatically change from *"Farmer"* and *"Crop"* to *"Caretaker"* and *"Water Point"*.
     * Local SQLite storage is strictly partitioned (and automatically wiped if switching between accounts).
   * The officer reviews escalated citizen questions, edits or approves AI-suggested answers, and resolves tickets.

---

### Option 2: Independent Deployment per Tenant (with Centralized Akvo RAG)

In this model, each tenant runs as an **isolated, dedicated AgriConnect application deployment** (separate FastAPI backend, separate PostgreSQL database, and dedicated Twilio/Meta channel credentials). All deployments are built from a **single codebase on `main`**, provisioned via an **interactive CLI tool**, and updated via a **centralized CI/CD pipeline**.

> **Centralized AI Architecture:**  
> Rather than duplicating the heavy Akvo RAG infrastructure (MinIO S3, Redis queues, Vector DB, embedding workers) for every tenant, **a single centralized Akvo RAG cluster** serves all tenant deployments. Each dedicated AgriConnect instance connects to the shared Akvo RAG service using its own unique `access_token` (managed in the `service_tokens` table) and accesses only its authorized `knowledge_base_ids`.

#### Tenant Configuration Management Strategy in Option 2

To maintain distinct configurations for multiple tenants without code duplication or maintaining long-lived tenant branches (`tenant/com`, `tenant/mhm-rmi`), Option 2 adopts a **3-Tier Configuration & GitOps Model**:

1. **Tier 1: Machine & Infrastructure Bootstrap (`.env` per Deployment Instance)**
   * Stored securely on the host filesystem per tenant container (e.g., `/opt/akvoconnect/tenants/{tenant_slug}/.env`).
   * Limited strictly to parameters required *before* database connectivity:
     * Instance Domain & Subdomain (e.g., `mali.akvoconnect.org`).
     * Dedicated PostgreSQL credentials (`DATABASE_URL`).
     * Dedicated Redis broker URL (`REDIS_URL`).
     * Master Encryption Key (`MASTER_ENCRYPTION_KEY` for Fernet channel token decryption).
     * Server runtime environment (`ENVIRONMENT=production`, `PORT=8000`).

2. **Tier 2: External Services & Business Configurations (Dedicated PostgreSQL DB Tables)**
   * Each tenant's dedicated database manages runtime configurations and external credentials dynamically without touching server environment files:
     * **`service_tokens` Table (External AI Integration):** Already implemented in the database schema. Stores `service_name="akvo-rag"`, `access_token`, `chat_url`, `upload_url`, `kb_url`, and `document_url`. Accessed via `ExternalAIService` with the existing 5-minute In-Memory TTL Cache (< 1ms lookup latency). Tokens can be rotated dynamically via API/Admin Console without restarting containers.
     * **`tenant_channels` Table:** Stores dedicated Twilio/Meta credentials (`account_sid`, `auth_token`, `waba_id`, `phone_number`, template SIDs) encrypted at-rest.
     * **`tenant_configs` JSONB Table:** Holds sector business rules (`sector: "water"`), dynamic onboarding forms (pumps vs. crops), sector escalation questions, officer/beneficiary terminology (`officer_label`), and feature toggles (`enable_photo_diagnostics: true`).
   * **Hot-Reloading without Downtime:** Partner admins can update templates, AI service tokens, or terminology via their instance's Admin UI/API with instant zero-downtime hot-reloading (via the 5-minute In-Memory TTL Cache), without editing files on the server or restarting Docker containers.

3. **Tier 3: Centralized Deployment Inventory (GitOps / CI/CD Inventory)**
   * A centralized private repository or CI/CD inventory tracks all tenant instances:
     ```yaml
     # deployments/inventory/tenants.yml
     tenants:
       - slug: kenya-agri
         domain: kenya.akvoconnect.org
         channel: stable
         sector: agriculture
       - slug: mali-water
         domain: mali.akvoconnect.org
         channel: stable
         sector: water
       - slug: sudan-health
         domain: sudan.akvoconnect.org
         channel: beta
         sector: health
     ```
   * **Upgrades without Config Overwrite:** When GitHub Actions deploys a new release of `main`, it pulls the new container image, runs database migrations (`alembic upgrade head`), and performs a rolling container restart. Because tenant configuration is decoupled into the host `.env` and PostgreSQL persistent volume, application code upgrades never overwrite tenant-specific settings.

4. **Automated Tenant Initialization (CLI):**
   * New tenants are initialized using `./provision_tenant.sh --tenant=mali-water --sector=water`.
   * The CLI interactively prompts for domain and DB/Redis credentials, registers the service token with Centralized Akvo RAG, seeds the dedicated DB with the sector blueprint (`tenant_configs`) and `service_tokens`, and registers the instance in the CI/CD inventory.

#### Architecture Diagram (Option 2: Independent Deployment + Centralized Akvo RAG)

```mermaid
flowchart TD
    subgraph Repo["Unified Codebase"]
        CODE["agriconnect (main branch)<br/>Generic Core + Feature Flags"]
        CLI["Tenant Provisioning CLI Tool"]
    end

    subgraph CICD["Centralized Release Pipeline (CI/CD)"]
        CODE -->|"1a. Push/Merge release"| PIPELINE["GitHub Actions / Centralized Pipeline<br/>• Bulk Deployment to all instances<br/>• Selective Deployment<br/>• Rolling Updates & Rollback"]
    end

    subgraph Tenant_A["Tenant 1 Deployment (Kenya Agri)"]
        TW_A["Dedicated Twilio (+254...)"] -->|"4. Direct Webhook POST"| APP_A["FastAPI Backend<br/>(kenya.akvoconnect.org)"]
        APP_A -->|"5. Local Query/Write"| DB_A[("Dedicated PostgreSQL")]
    end

    subgraph Tenant_B["Tenant 2 Deployment (Mali Water)"]
        TW_B["Dedicated Twilio (+223...)"] -->|"4. Direct Webhook POST"| APP_B["FastAPI Backend<br/>(mali.akvoconnect.org)"]
        APP_B -->|"5. Local Query/Write"| DB_B[("Dedicated PostgreSQL")]
    end

    subgraph Tenant_C["Tenant 3 Deployment (Sudan Health)"]
        TW_C["Dedicated Twilio (+249...)"] -->|"4. Direct Webhook POST"| APP_C["FastAPI Backend<br/>(sudan.akvoconnect.org)"]
        APP_C -->|"5. Local Query/Write"| DB_C[("Dedicated PostgreSQL")]
    end

    subgraph Shared_AI["Centralized Akvo RAG Cluster (PR #163)"]
        RAG_API["Akvo RAG Backend (:8010)<br/>Token-based Authentication & Scoping"]
        RAG_REDIS[("Redis RPC Queues")]
        RAG_WORKER["vector-kb-mcp Workers"]
        RAG_MINIO[("MinIO S3 Storage")]
        RAG_VDB[("Vector DB (Qdrant / Chroma)")]
        
        RAG_API -->|"7a. Enqueue RPC"| RAG_REDIS --> RAG_WORKER
        RAG_WORKER -->|"7b. Vector & Doc Lookup"| RAG_MINIO & RAG_VDB
    end

    %% Step 1b & 2: Provisioning & Deployments
    CLI -->|"1b. Provision instance (bootstrap .env & seed DB)"| Tenant_A & Tenant_B & Tenant_C
    PIPELINE -->|"2. Rolling container updates"| Tenant_A & Tenant_B & Tenant_C

    %% Step 3: End User Message (represented to Twilio accounts)
    CITIZEN_A["Farmer (Kenya)"] -->|"3. Send WhatsApp"| TW_A
    CITIZEN_B["Caretaker (Mali)"] -->|"3. Send WhatsApp"| TW_B
    CITIZEN_C["Patient (Sudan)"] -->|"3. Send WhatsApp"| TW_C

    %% Step 6 & 8: Centralized AI Calls with Token Isolation
    APP_A -->|"6. POST /chat (Bearer Token A)"| RAG_API
    APP_B -->|"6. POST /chat (Bearer Token B)"| RAG_API
    APP_C -->|"6. POST /chat (Bearer Token C)"| RAG_API

    RAG_API -.->|"8. Callback /api/callback/ai"| APP_A
    RAG_API -.->|"8. Callback /api/callback/ai"| APP_B
    RAG_API -.->|"8. Callback /api/callback/ai"| APP_C

    %% Step 9: Outbound Replies
    APP_A -->|"9. Outbound reply"| CITIZEN_A
    APP_B -->|"9. Outbound reply"| CITIZEN_B
    APP_C -->|"9. Outbound reply"| CITIZEN_C
```

##### Architectural Execution Flow by Step (Option 2):
* **Provisioning & Deployment Lifecycle (DevOps & Management):**
  * **Step 1a (Code Release):** Application code and generic feature updates are merged into the `main` branch of the unified `agriconnect` repository.
  * **Step 1b (Automated Tenant Provisioning):** DevOps runs the interactive provisioning CLI (`./provision_tenant.sh --tenant={name} --sector={sector}`). The CLI generates the container bootstrap `.env`, initializes the dedicated PostgreSQL database volume, registers the access token with Centralized Akvo RAG, and seeds the `service_tokens` and `tenant_configs` (JSONB) tables.
  * **Step 2 (Automated Rolling Updates):** GitHub Actions detects registered instances in the deployment inventory and executes automated rolling deployments with health checks and zero-downtime container restarts.
* **Daily Operational Inbound & AI Advisory Lifecycle:**
  * **Step 3 (Citizen Inbound Message):** A citizen sends a WhatsApp inquiry to the organization's dedicated phone number.
  * **Step 4 (Direct Inbound Webhook):** Twilio forwards the webhook directly to the tenant's dedicated subdomain (e.g., `https://mali.akvoconnect.org/api/whatsapp/webhook`), completely eliminating the need for an edge tenant resolution proxy.
  * **Step 5 (Local Database Persistence):** The dedicated FastAPI backend reads and writes citizen records, message logs, and tickets into its physically separate PostgreSQL database.
  * **Step 6 (Centralized AI Request):** The instance calls the Centralized Akvo RAG service (`POST /chat`) using the specific `access_token` stored in its dedicated `service_tokens` table (cached with a 5-minute TTL).
  * **Step 7a & 7b (Centralized RAG Retrieval):** Akvo RAG routes the job through its Redis RPC queues to `vector-kb-mcp` workers, performing semantic vector searches across MinIO and Qdrant scoped to the tenant's authorized `knowledge_base_ids`.
  * **Step 8 (Instance Webhook Callback):** The Akvo RAG cluster returns the synthesized response to the calling instance's callback webhook (`https://mali.akvoconnect.org/api/callback/ai`).
  * **Step 9 (Outbound Response Delivery):** The dedicated FastAPI backend dispatches the advisory answer back to the citizen via its dedicated Twilio account.

#### User Workflow (Option 2: Independent Deployment)

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Akvo DevOps / Platform Admin
    actor Citizen as Citizen / Farmer
    participant CLI as Tenant Provisioning CLI
    participant CICD as Centralized CI/CD Pipeline
    participant AppInstance as Dedicated Instance (e.g. Kenya)
    participant CentralRAG as Centralized Akvo RAG Cluster

    Note over Admin,AppInstance: 1. Automated Tenant Provisioning
    Admin->>CLI: Run ./provision_tenant.sh --tenant=agri-kenya
    CLI->>Admin: Prompt: Twilio SID, WhatsApp Number, Domain, DB Password
    CLI->>CentralRAG: Provision new Service Token & KB ID for 'agri-kenya'
    CentralRAG-->>CLI: Return access_token & kb_ids
    CLI->>AppInstance: Generate docker-compose.yml, bootstrap .env, seed DB (service_tokens & tenant_configs)
    CLI->>CICD: Register new target instance in inventory

    Note over Admin,CICD: 2. Release & Maintenance Workflow
    Admin->>CICD: Trigger Release (v3.2.0)
    CICD->>AppInstance: Rolling deploy to agri-kenya (healthcheck, migrate, restart)

    Note over Citizen,CentralRAG: 3. Daily Usage with Centralized AI
    Citizen->>AppInstance: WhatsApp message to dedicated number (+254...)
    AppInstance->>CentralRAG: POST chat_url (Bearer access_token, kb_ids, payload)
    CentralRAG->>CentralRAG: Process via Redis queue & scoped Vector KB
    CentralRAG-->>AppInstance: Webhook callback (/api/callback/ai)
    AppInstance-->>Citizen: WhatsApp reply with advisory answer
```

##### Workflow Description by Persona:

1. **Akvo DevOps / Platform Admin (Automated Instance Provisioning):**
   * Runs the interactive CLI tool: `./provision_tenant.sh --tenant=agri-kenya`.
   * The CLI interactively prompts for tenant domain (`kenya.akvoconnect.org`), Twilio account SID/token, WhatsApp phone number, and DB credentials.
   * The CLI contacts the Centralized Akvo RAG service to provision an authorized `access_token` and `kb_ids`, seeds the `service_tokens` table and `tenant_configs` into the dedicated PostgreSQL database, generates the dedicated bootstrap `.env` and `docker-compose.override.yml`, runs database migrations, and adds the host to the centralized deployment inventory.
2. **Citizen / End-User (Direct Inbound Advisory):**
   * A citizen messages the dedicated organization phone number (+254...).
   * Twilio routes the webhook directly to the dedicated subdomain (`https://kenya.akvoconnect.org/api/whatsapp/webhook`).
   * The dedicated backend processes user state locally and calls the Centralized Akvo RAG cluster using its specific `access_token`.
   * Centralized Akvo RAG processes the query via its Redis queue, executes vector lookup in MinIO/Qdrant, and returns the callback to `https://kenya.akvoconnect.org/api/callback/ai`, which delivers the response back to the citizen.
3. **Field Staff / Extension Officer (Dedicated Data Access):**
   * The officer logs into their organization's dedicated web dashboard (`kenya.akvoconnect.org`) or points the mobile app to their instance.
   * Because data resides in a physically separate PostgreSQL database, the officer has guaranteed sovereign data isolation with zero performance impact from other tenants' workloads.
4. **DevOps & Release Engineer (Centralized Release Management):**
   * When updates are merged to `main`, GitHub Actions triggers a centralized release pipeline.
   * The pipeline performs automated rolling deployments across all registered tenant instances, checking health endpoints and executing automated rollbacks if an instance fails verification.

---

## 4. Comprehensive Pros & Cons Comparison

| Dimension | Option 1: Shared Multitenancy | Option 2: Independent Deployment |
| :--- | :--- | :--- |
| **Data Isolation & Security** | ⚠️ **Application-enforced.** Requires strict scoped query helpers and automated leak testing. A bug in filtering could leak data across tenants. | ✅ **Hard physical/container isolation.** Database and memory are completely separated per tenant. Zero risk of cross-tenant leakage. |
| **Operational Overhead** | ✅ **Low at scale.** 1 cluster, 1 database, 1 Celery/Redis cluster to monitor, backup, and patch regardless of tenant count. | ❌ **High at scale.** Managing 10–20 separate VM/container stacks, backups, and SSL certs creates infrastructure sprawl. |
| **Initial Development Effort** | ❌ **High.** Requires refactoring global `Settings` to `TenantContext`, adding `tenant_id` to dozens of models, and building edge routing. | ✅ **Medium-Low.** Minimal application-level refactoring; logic stays similar to current code while building CLI and CI/CD pipelines. |
| **Infrastructure Cost** | ✅ **Highly Cost-Efficient.** Efficient resource pooling. Small pilot tenants consume virtually zero incremental compute/RAM. | ⚠️ **Moderate Cost.** Heavy AI, MinIO, and Vector DB resources are centralized in one Akvo RAG cluster (saving significant compute/RAM). Only the lightweight FastAPI/PostgreSQL stack is duplicated per tenant. |
| **Release & Deployment Complexity** | ✅ **Single Deploy.** One deployment automatically delivers updates, bug fixes, and features to all organizations simultaneously. | ⚠️ **Requires Centralized Pipeline.** Requires sophisticated CI/CD tooling for bulk/selective updates, rolling rollouts, and multi-host monitoring. |
| **Partner Data Residency Compliance** | ⚠️ **Complex.** Hard to satisfy contracts requiring data to physically reside within specific geographic boundaries in a shared DB. | ✅ **Native Compliance.** Each instance can easily be deployed in any cloud region or on partner-managed sovereign infrastructure. |
| **Tenant Onboarding & Config Management** | ✅ **Database-driven (Zero Infra Overhead).** <br>• Runtime configuration is fully migrated from `config.json` to PostgreSQL (`tenant_configs` JSONB).<br>• Tenant onboarding is purely a database record addition via API or Admin Console wizard.<br>• Instant zero-downtime hot-reloading via In-Memory TTL Cache (no server restarts when config changes). | ⚠️ **File-based + Infra Overhead.** <br>• Configuration remains a local physical `config.json` file per instance.<br>• Every new tenant requires provisioning new containers, new database, Nginx subdomain, SSL Certbot certificates, and initial DB migrations (~15–30 minutes per tenant). |
| **Noisy Neighbor Risk** | ⚠️ **Present.** A massive broadcast campaign by one tenant could saturate shared Celery/Redis queues and database connections. | ✅ **Zero.** Performance issues or queue backlogs on one tenant never impact other organizations. |

## 5. Level of Effort (LoE) Estimation (Realistic Engineering Standard)

Rather than assuming an unbuffered "best-case" or an overly conservative scenario, this estimate applies an **Average Realistic Engineering Standard** (with slight optimism, leveraging AI-assisted pairing, familiar tech stacks, and existing branch assets):
* **Productive Capacity:** Calculated on an average of **5–6 focused engineering hours per working day** (30h/week), with peer reviews adhering to Akvo's 1–3 review cycle standard (~15–20% of dev time).
* **Leveraging Existing Codebases:** Takes into account that the Akvo RAG Monorepo (PR #163) and dynamic onboarding (`tenant/com`, `tenant/mhm-rmi`) are already implemented on working branches and require integration/consolidation rather than development from scratch.
* **Effort Columns:** Structured into direct development effort (**Dev LoE**, including unit testing) and **QA & Review** (staging deployment, code review, and integration validation).

---

### Step 0: Shared Technical Debt Resolution (Required for BOTH Options)
*Prerequisite baseline cleanup before expanding to new sectors.*

| Task ID | Story / Task Description | Dev LoE | QA & Review | Total Average Realistic |
| :--- | :--- | :---: | :---: | :---: |
| **RAG-01** | Connect Akvo RAG Monorepo PR #163 & update akvo-rag deployment manifests | 12h | 3h | **15h (~0.5 wk / 2.5 days)** |
| **RAG-02** | Develop KB migration & ingestion script (download, folderize by KB name/ID, re-upload to MinIO & trigger full vector ingestion pipeline) & verify callback | 10h | 2h | **12h (~0.4 wk / 2 days)** |
| **CORE-01** | Consolidate `tenant/com` & `tenant/mhm-rmi` dynamic onboarding into `main` | 8h | 2h | **10h (~0.3 wk / 1.5 days)** |
| **CORE-02** | Decouple weather service, ag escalation questions, and generalize models (unify `UserType` to General User Type & decouple `Customer.crop_type`) | 8h | 2h | **10h (~0.3 wk / 1.5 days)** |
| **FE-01** | Generalize user/officer UI, dynamic analytics charts (replace hardcoded crop matrix), and clean mobile SQLite/Context crop references | 10h | 3h | **13h (~0.4 wk / 2 days)** |
| **Subtotal** | **Baseline Technical Debt Cleanup** | **48h** | **12h** | **60h (~2.0 calendar weeks)** |

---

### Option 1: Shared Multi-Tenant Implementation

| Task ID | Story / Task Description | Dev LoE | QA & Review | Total Average Realistic |
| :--- | :--- | :---: | :---: | :---: |
| **SMT-01** | DB schema refactor: `tenants`, `tenant_channels`, `tenant_configs`, `tenant_id` | 12h | 3h | **15h (~0.5 wk)** |
| **SMT-02** | Runtime `TenantContext` & replace global `Settings` (~29 modules) | 18h | 4h | **22h (~0.7 wk)** |
| **SMT-03** | Edge tenant resolver for WhatsApp/Twilio webhooks (destination address) | 8h | 2h | **10h (~0.3 wk)** |
| **SMT-04** | Dynamic channel vault (encrypted Twilio credentials & outbound routing) | 10h | 2h | **12h (~0.4 wk)** |
| **SMT-05** | Universal mobile app bootstrap (dynamic terminology & SQLite session wipe) | 12h | 3h | **15h (~0.5 wk)** |
| **SMT-06** | Cross-tenant data isolation test suite & leak regression tests | 10h | 3h | **13h (~0.4 wk)** |
| **SMT-07** | Admin console / API for tenant provisioning & channel setup | 12h | 3h | **15h (~0.5 wk)** |
| **Subtotal** | **Option 1 Implementation** | **82h** | **20h** | **102h (~3.4 calendar weeks)** |
| **TOTAL** | **Step 0 + Option 1 Delivery** | **130h** | **32h** | **162h (~5.4 calendar weeks / ~1.3 months)** |

---

### Option 2: Independent Deployment Implementation (with Centralized Akvo RAG)

| Task ID | Story / Task Description | Dev LoE | QA & Review | Total Average Realistic |
| :--- | :--- | :---: | :---: | :---: |
| **IND-01** | Standardize unified configuration schema (`config.json` + `.env`) on `main` | 8h | 2h | **10h (~0.3 wk)** |
| **IND-02** | Develop interactive Tenant Provisioning CLI (`./provision_tenant.sh`) | 12h | 3h | **15h (~0.5 wk)** |
| **IND-03** | Docker Compose modularization & multi-instance port/domain mapping | 8h | 2h | **10h (~0.3 wk)** |
| **IND-04** | Centralized CI/CD pipeline (GitHub Actions for bulk & selective deployments)| 14h | 3h | **17h (~0.6 wk)** |
| **IND-05** | Rolling update automation, health check gates, and rollback scripts | 10h | 2h | **12h (~0.4 wk)** |
| **IND-06** | Universal mobile app host switching / dynamic server configuration | 8h | 2h | **10h (~0.3 wk)** |
| **IND-07** | Centralized monitoring & logging aggregator (Prometheus/Grafana/Loki) | 8h | 2h | **10h (~0.3 wk)** |
| **Subtotal** | **Option 2 Implementation** | **68h** | **16h** | **84h (~2.8 calendar weeks)** |
| **TOTAL** | **Step 0 + Option 2 Delivery** | **116h** | **28h** | **144h (~4.8 calendar weeks / ~1.2 months)** |

---

## 6. Key Decisions Required to Finalize the HLD

To reach final consensus between engineering and product leadership, the following decisions must be made:

1. **Architecture Path Selection:**
   - Choose **Option 1 (Shared Multi-Tenancy)** if the long-term goal is a low-maintenance SaaS platform and the team can commit to the ~5.4-week timeline for deep database/core refactoring.
   - Choose **Option 2 (Independent Deployments + Centralized RAG)** if faster time-to-market (~4.8 weeks) and sovereign physical isolation are prioritized without touching core database schemas.
2. **Channel Onboarding Strategy:**
   - Will Akvo register partner numbers under Akvo's master Twilio account (via subaccounts), or will partners be required to bring their own pre-configured Twilio/Meta accounts?
3. **Template Creation Automation:**
   - Conduct a spike on the Twilio Content API to verify whether WhatsApp templates can be programmatically submitted and synced during tenant onboarding to eliminate manual dashboard steps.
4. **Mobile App Distribution:**
   - Confirm the single universal app strategy with dynamic login-time terminology (Option A) versus maintaining separate white-label EAS build profiles (Option B).
5. **Decision Reached: Migrate Runtime `config.json` to PostgreSQL:**
   - **Confirmed:** Runtime configuration will be migrated entirely from static `config.json` to PostgreSQL (`tenant_configs` JSONB and `tenant_channels`).
   - Machine infrastructure settings remain in `.env` (`DATABASE_URL`, `REDIS_URL`, `MASTER_ENCRYPTION_KEY`).
   - In-memory TTL caching (5 minutes) eliminates database load and enables instant hot-reloading (zero server restarts when updating templates or settings).
   - `config.json` is repurposed as `config.blueprint.json` strictly for initial database seeding templates.

---

## 7. Recommended Action Plan

```
[Phase 0: Technical Debt & RAG Integration]  (Weeks 1 – 2.0)
├── Update akvo-rag deployment manifests & infrastructure
├── Merge Akvo RAG Monorepo PR #163 into staging
├── Develop KB migration script (download, folderize, re-upload & re-run ingestion pipeline)
├── Decouple agriculture models (unify UserType to General User Type & Customer.crop_type)
├── Consolidate tenant/com & tenant/mhm-rmi dynamic logic into main
└── Extract weather & ag-specific escalation questions behind feature flags
                         │
                         ▼
[Phase 1: Architecture Decision Gate] (End of Week 2.0)
├── Finalize choice between Option 1 vs Option 2
└── Conduct Twilio Content API spike for template automation
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
[Track A: Option 1 (Shared Multi-Tenant)] [Track B: Option 2 (Independent Deploy)]
├── Weeks 3 – 5.5 (~3.4 weeks)            ├── Weeks 3 – 5.0 (~2.8 weeks)
├── TenantContext & Schema Refactor       ├── Provisioning CLI Tooling
├── Edge Webhook Routing & Channel Vault  ├── Centralized CI/CD Bulk Pipeline
└── Universal Mobile App Terminology      └── Multi-Host Monitoring Setup
```
