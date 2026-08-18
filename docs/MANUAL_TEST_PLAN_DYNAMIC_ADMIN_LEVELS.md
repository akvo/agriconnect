# Manual QA Test Plan: Dynamic Administrative Hierarchy & Multi-Tier Onboarding

**Document Version:** 1.0
**Date:** 2026-08-17
**Author:** Galih Pratama
**Specification:** [`docs/DYNAMIC_ADMIN_LEVELS.md`](/docs/DYNAMIC_ADMIN_LEVELS.md)
**Parent Specification:** [`docs/CONFIGURABLE_ONBOARDING_QUESTIONS.md`](/docs/CONFIGURABLE_ONBOARDING_QUESTIONS.md)
**Target:** Dynamic Administrative Hierarchy Engine, Country-Swap Seeder, and WhatsApp Onboarding State Machine

---

## 1. Objective & Scope

This manual test plan provides step-by-step verification procedures for the **Dynamic Administrative Hierarchy Engine** in AgriConnect. It validates that the platform can adapt to any national administrative structure (from 2-tier up to $N$-tier depths) and cleanly swap country data purely through configuration (`config.json`) and seeder parameters, without requiring code rewrites.

### What is Tested:
1. **Default 4-Tier Kenya Deployment** (`Country > Region > District > Ward`).
2. **International Country-Swap to 5-Tier Indonesia Deployment** (`Country > Provinsi > Kabupaten > Kecamatan > Desa`).
3. **Fresh Deployment Safety Guard** (preventing accidental purge of live customer data).
4. **Minimal 2-Tier Hierarchy** (`Country > Region`).
5. **Intermediate Nodes Without Children** (isolated areas gracefully saving at current depth).
6. **WhatsApp Conversational Onboarding Traversal** across all depths with input validation and i18n fallback prompts.
7. **Downstream Statistics & Extension Officer (EO) Escalation** resolving dynamically against configured leaf levels.

---

## 2. Test Environments & Prerequisites

### 2.1 Prerequisites
- Docker containers running via `./dc.sh up -d`
- Backend service operational at `http://localhost:8000` (or active ngrok tunnel)
- PostgreSQL database accessible via `./dc.sh exec db psql -U postgres -d agriconnect_dev`
- API documentation available at `http://localhost:8000/docs`

### 2.2 Test Message Injection Methods
Incoming WhatsApp messages during onboarding can be injected via:
1. **Direct Webhook POST (cURL)**:
   ```bash
   curl -X POST http://localhost:8000/api/whatsapp/webhook \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "From=whatsapp%3A%2B254700111222&Body=Hello&ProfileName=FarmerTest"
   ```
2. **Interactive Swagger UI**: `POST /api/whatsapp/webhook`
3. **Database Inspection**:
   ```sql
   -- Check administrative levels
   SELECT id, name, level_index FROM administrative_levels ORDER BY level_index ASC;

   -- Check customer location links
   SELECT c.phone_number, c.onboarding_status, a.name AS location_name, al.name AS level_name, a.path
   FROM customers c
   LEFT JOIN customer_administrative ca ON c.id = ca.customer_id
   LEFT JOIN administrative a ON ca.administrative_id = a.id
   LEFT JOIN administrative_levels al ON a.level_id = al.id
   WHERE c.phone_number = '+254700111222';
   ```

---

## 3. Conversational Onboarding Flow

```mermaid
sequenceDiagram
    autonumber
    actor Farmer as Farmer (WhatsApp)
    participant WH as WhatsApp Webhook
    participant OS as OnboardingService
    participant Cfg as config.json (Settings)
    participant DB as PostgreSQL

    Farmer->>WH: "Hello" (Triggers Onboarding)
    WH->>OS: process_customer_message()
    OS->>Cfg: Read settings.admin_level_order (e.g. ['provinsi', 'kabupaten', 'kecamatan', 'desa'])
    OS->>DB: Query root level children (level_index = 1)
    DB-->>OS: [1. Jawa Barat, 2. Jawa Tengah]
    OS-->>Farmer: "Let's find your location step by step.\n\nPlease select your area:\n\n1. Jawa Barat\n2. Jawa Tengah"

    Farmer->>WH: "1"
    WH->>OS: _process_hierarchical_selection("1")
    OS->>DB: Query children of 'Jawa Barat' at level_index = 2
    DB-->>OS: [1. Bandung, 2. Bogor]
    OS-->>Farmer: "Great! You selected Jawa Barat.\n\nPlease choose your sub-area:\n\n1. Bandung\n2. Bogor"

    Farmer->>WH: "1"
    WH->>OS: _process_hierarchical_selection("1")
    OS->>DB: Query children of 'Bandung' at level_index = 3
    DB-->>OS: [1. Cileunyi, 2. Coblong]
    OS-->>Farmer: "Great! You selected Bandung.\n\nPlease choose your sub-area:\n\n1. Cileunyi\n2. Coblong"

    Farmer->>WH: "1"
    WH->>OS: _process_hierarchical_selection("1")
    OS->>DB: Query children of 'Cileunyi' at level_index = 4 (Leaf)
    DB-->>OS: [1. Cibiruhilir, 2. Cinunuk]
    OS-->>Farmer: "Great! You selected Cileunyi.\n\nPlease choose your sub-area:\n\n1. Cibiruhilir\n2. Cinunuk"

    Farmer->>WH: "1"
    WH->>OS: _process_hierarchical_selection("1")
    Note over OS,DB: Detected max level_index (4) -> Leaf Reached!
    OS->>DB: INSERT INTO customer_administrative (customer_id, administrative_id=Cibiruhilir.id)
    OS-->>Farmer: "Location saved! What is your main crop?"
```

---

## 4. Test Scenarios

---

### 🧪 Scenario 1: Standard 4-Tier Kenya Hierarchy (Default Deployment)

#### Goal:
Verify that the default Kenya administrative hierarchy (`country` $\rightarrow$ `region` $\rightarrow$ `district` $\rightarrow$ `ward`) seeds correctly, assigns numeric `level_index` values (`0, 1, 2, 3`), and successfully navigates a 3-step WhatsApp onboarding location questionnaire to save the final ward.

#### Setup:
1. Ensure `backend/config.json` has standard Kenya hierarchy:
   ```json
   "administrative_hierarchy": {
     "country_code": "KEN",
     "delimiter": " > ",
     "levels": [
       { "level_index": 0, "name": "country", "display": { "en": "Country" } },
       { "level_index": 1, "name": "region", "display": { "en": "Region", "sw": "Mkoa" } },
       { "level_index": 2, "name": "district", "display": { "en": "District", "sw": "Wilaya" } },
       { "level_index": 3, "name": "ward", "display": { "en": "Ward", "sw": "Kata" } }
     ]
   }
   ```
2. Run seeder:
   ```bash
   ./dc.sh exec backend python -m seeder.administrative
   ```

#### Execution Steps:
| Step | Action / Payload | Expected Response | DB Verification | Status |
|---|---|---|---|---|
| **1.1** | Verify seeded levels | Seeder logs: `Seeded 4 administrative levels, 1 countries, ...` | `SELECT name, level_index FROM administrative_levels ORDER BY level_index;`<br>$\rightarrow$ `country: 0`, `region: 1`, `district: 2`, `ward: 3` | [x] **PASSED** (2026-08-18) |
| **1.2** | Send WhatsApp message:<br>`From=+254700000101`<br>`Body=Hello` | Welcome greeting + Language selection (or direct name prompt). | Customer row created with `onboarding_status='in_progress'`. | [x] **PASSED** (2026-08-18) |
| **1.3** | Send Name:<br>`Body=John Doe` | Asks for Region:<br>`"Where is your farm located?\n\nPlease select your region:\n\n1. Central\n2. Coast\n..."` | Customer `full_name` updated. Onboarding field advances to `administration`. | [x] **PASSED** (2026-08-18) |
| **1.4** | Send Region selection:<br>`Body=1` (Central) | Asks for District under Central:<br>`"Great! You selected Central.\n\nPlease choose your district:\n\n1. Murang'a\n2. Kiambu\n..."` | Temporary hierarchy state stored in `customer.profile_data["_admin_hierarchy"]`. | [x] **PASSED** (2026-08-18) |
| **1.5** | Send District selection:<br>`Body=1` (Murang'a) | Asks for Ward under Murang'a:<br>`"Great! You selected Murang'a.\n\nPlease choose your ward:\n\n1. Kiharu\n2. Kangema\n..."` | Hierarchy state advances to level index 2. | [x] **PASSED** (2026-08-18) |
| **1.6** | Send Ward selection:<br>`Body=1` (Kiharu) | Location saved confirmation and advances to next question (e.g. crop type):<br>`"What crops do you grow?"` | `SELECT * FROM customer_administrative WHERE customer_id = <cust_id>;`<br>Points to `Kiharu` ward ID. `_admin_hierarchy` cleaned up. | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 2: Country Swap to Indonesia 5-Tier Hierarchy (International Deployment)

#### Goal:
Verify that on a fresh deployment, AgriConnect can replace the entire national administrative hierarchy with Indonesia's 5-tier system (`Country` $\rightarrow$ `Provinsi` $\rightarrow$ `Kabupaten` $\rightarrow$ `Kecamatan` $\rightarrow$ `Desa`) and seamlessly guide farmers through a 4-step location onboarding flow to save the leaf `desa`.

#### Setup:
1. Update `backend/config.json`:
   ```json
   "administrative_hierarchy": {
     "country_code": "IDN",
     "delimiter": " > ",
     "levels": [
       { "level_index": 0, "name": "country", "display": { "en": "Country" } },
       { "level_index": 1, "name": "provinsi", "display": { "en": "Provinsi" } },
       { "level_index": 2, "name": "kabupaten", "display": { "en": "Kabupaten" } },
       { "level_index": 3, "name": "kecamatan", "display": { "en": "Kecamatan" } },
       { "level_index": 4, "name": "desa", "display": { "en": "Desa" } }
     ]
   }
   ```
2. Create sample source CSV at `backend/source/indonesia_sample.csv`:
   ```csv
   code,name,level,parent_code
   IDN,Indonesia,country,
   IDN-JB,Jawa Barat,provinsi,IDN
   IDN-JB-BDG,Kabupaten Bandung,kabupaten,IDN-JB
   IDN-JB-BDG-CLY,Kecamatan Cileunyi,kecamatan,IDN-JB-BDG
   IDN-JB-BDG-CLY-CBR,Desa Cibiruhilir,desa,IDN-JB-BDG-CLY
   IDN-JB-BDG-CLY-CNN,Desa Cinunuk,desa,IDN-JB-BDG-CLY
   ```
3. Run Country Swap Seeder:
   ```bash
   ./dc.sh exec backend python -m seeder.administrative --replace-country --source source/indonesia_sample.csv
   ```

#### Execution Steps:
| Step | Action / Payload | Expected Response | DB Verification | Status |
|---|---|---|---|---|
| **2.1** | Verify Country Swap Execution | CLI Output:<br>`REPLACE-COUNTRY mode active: Purging all existing administrative entities...`<br>`Purged records: {...}`<br>`Successfully seeded administrative data for Indonesia` | `SELECT count(*) FROM administrative WHERE path LIKE 'Indonesia%';`<br>Returns 10 rows. Kenya rows are completely purged. | [x] **PASSED** (2026-08-18) |
| **2.2** | Send WhatsApp message:<br>`From=+628123456789`<br>`Body=Halo` | Greeting prompt + Name inquiry. | New customer created with phone `+6281999103535`. | [x] **PASSED** (2026-08-18) |
| **2.3** | Send Name:<br>`Body=Pratama` | Asks for Level 1 (Provinsi):<br>`"Let's find your location step by step.\n\nPlease select your area:\n\n1. Jawa Barat"` | Hierarchy starts dynamically at `settings.admin_level_order[0]` (`provinsi`). | [x] **PASSED** (2026-08-18) |
| **2.4** | Select Provinsi:<br>`Body=1` (Jawa Barat) | Asks for Level 2 (Kabupaten):<br>`"Great! You selected Jawa Barat.\n\nPlease choose your sub-area:\n\n1. Kabupaten Bandung"` | Candidate IDs stored for level 2. | [x] **PASSED** (2026-08-18) |
| **2.5** | Select Kabupaten:<br>`Body=1` (Kabupaten Bandung) | Asks for Level 3 (Kecamatan):<br>`"Great! You selected Kabupaten Bandung.\n\nPlease choose your sub-area:\n\n1. Kecamatan Cileunyi"` | Candidate IDs stored for level 3. | [x] **PASSED** (2026-08-18) |
| **2.6** | Select Kecamatan:<br>`Body=1` (Kecamatan Cileunyi) | Asks for Level 4 (Desa):<br>`"Great! You selected Kecamatan Cileunyi.\n\nPlease choose your sub-area:\n\n1. Desa Cibiruhilir\n2. Desa Cinunuk"` | Candidate IDs stored for leaf level 4. | [x] **PASSED** (2026-08-18) |
| **2.7** | Select Desa:<br>`Body=1` (Desa Cibiruhilir) | Leaf reached! Saves location and advances to crop question:<br>`"Location saved! What crops do you grow?"` | `SELECT a.name, a.path, al.level_index FROM customer_administrative ca JOIN administrative a ON ca.administrative_id = a.id JOIN administrative_levels al ON a.level_id = al.id WHERE ca.customer_id = <cust_id>;`<br>Returns `Desa Cibiruhilir`, `level_index: 4`. | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 3: Country-Swap Safety Guard Live Protection

#### Goal:
Verify that the `--replace-country` flag is strictly forbidden on non-fresh deployments where customer records exist in the database, preventing accidental destruction of live customer data.

#### Setup:
1. Ensure at least 1 customer exists:
   ```sql
   INSERT INTO customers (phone_number, language, onboarding_status)
   VALUES ('+254711999888', 'en', 'completed')
   ON CONFLICT (phone_number) DO NOTHING;
   ```

#### Execution Steps:
| Step | Action / Command | Expected Result | Status |
|---|---|---|---|
| **3.1** | Run Country-Swap Seeder:<br>`./dc.sh exec backend python -m seeder.administrative --replace-country --source source/indonesia_sample.csv` | **Execution ABORTS immediately** with error output:<br>`❌ ERROR: Cannot run --replace-country! Found 21 live customer records in database.`<br>`Country replacement is restricted to fresh deployments to prevent data corruption.`<br>Exit code: `1`. | [x] **PASSED** (2026-08-18) |
| **3.2** | Check DB integrity:<br>`SELECT count(*) FROM customers;`<br>`SELECT count(*) FROM administrative;` | All existing customers (21) and administrative areas (332) remain completely intact and untouched. | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 4: Minimal 2-Tier Hierarchy (Single-Step Onboarding)

#### Goal:
Verify that if a deployment configures a minimal 2-tier system (`Country` $\rightarrow$ `Region`), onboarding only prompts once for the region, recognizes it as the leaf level (`level_index = 1`), saves it immediately to `customer_administrative`, and advances to the next profile question without asking for nonexistent child levels.

#### Setup:
1. Update `backend/config.json`:
   ```json
   "administrative_hierarchy": {
     "country_code": "SGP",
     "delimiter": " > ",
     "levels": [
       { "level_index": 0, "name": "country" },
       { "level_index": 1, "name": "district" }
     ]
   }
   ```

#### Execution Steps:
| Step | Action / Payload | Expected Response | DB Verification | Status |
|---|---|---|---|---|
| **4.1** | Trigger location onboarding:<br>`From=+6281999103535`<br>`Body=John Tan` | Prompts for District:<br>`"Let's find your location step by step.\n\nWhich District are you from?\n\n1. Central District\n2. North District\n3. East District"` | Level 1 loaded dynamically using display name. | [x] **PASSED** (2026-08-18) |
| **4.2** | Select District:<br>`Body=1` (Central District) | System recognizes level 1 is max `level_index` (`settings.admin_leaf_level_index == 1`). Location saved immediately:<br>`"Crop saved as ..."` | `customer_administrative` points to `Central District` ID. No deeper sub-area prompted. | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 5: Intermediate Node Without Children (Isolated Area Handling)

#### Goal:
Verify that if an administrative area at an intermediate level has 0 children registered in the database (e.g. an isolated region without sub-districts yet mapped), selecting that area during onboarding gracefully treats it as the final location, saves it, and advances rather than erroring or showing an empty menu.

#### Setup:
1. In database, create an isolated Region under Kenya that has no child Districts:
   ```sql
   INSERT INTO administrative (code, name, level_id, parent_id, path)
   VALUES ('KEN-ISL', 'Isolated Region', (SELECT id FROM administrative_levels WHERE name='region'), (SELECT id FROM administrative WHERE name='Kenya'), 'Kenya > Isolated Region');
   ```

#### Execution Steps:
| Step | Action / Payload | Expected Response | DB Verification | Status |
|---|---|---|---|---|
| **5.1** | Trigger onboarding & view Provinsi options | List includes isolated node `"Bali"`. | State awaiting provinsi selection. | [x] **PASSED** (2026-08-18) |
| **5.2** | Select `"Bali"` (`Body=3`) | System queries child kabupatens of `Bali`, finds 0 rows, logs: `No kabupatens found for Bali, saving as final location`, and proceeds:<br>`"Crop saved as ..."` | `customer_administrative` links customer directly to `Bali` (`Indonesia > Bali`). | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 6: User Input Resilience, Validation & i18n Fallbacks

#### Goal:
Verify that user errors (out-of-range numbers, text inputs) are handled gracefully with localized error prompts, and that non-English languages (e.g. Swahili) dynamically format fallback selection prompts.

#### Execution Steps:
| Scenario | Input / Action | Expected System Response | Status |
|---|---|---|---|
| **6A: Out of Range** | When 3 regions are shown (`1..3`), user sends `Body=9` | `"Please select a number between 1 and 3"`<br>(Status remains `awaiting_selection`, attempts incremented). | [x] **PASSED** (2026-08-18) |
| **6B: Non-Numeric Text** | When numbered list is shown, user sends `Body=Central` | `"Please reply with a number (e.g., '1', '2') corresponding to your choice."` | [x] **PASSED** (2026-08-18) |
| **6C: Swahili Fallback** | Customer with `language='sw'` enters location step on custom unlocalized level (e.g. `Provinsi`) | `"Hebu tupate eneo lako hatua kwa hatua.\n\nUnatoka Provinsi gani?\n\n1. Jawa Barat\n..."` | [x] **PASSED** (2026-08-18) |
| **6D: Strict Mandatory Enforcement** | User sends `Body=skip` or `Body=lewati` on required location field | Rejects skip with numeric prompt (`"Please reply with a number (e.g., '1', '2') corresponding to your choice."`) preserving mandatory collection integrity. | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 7: Extension Officer (EO) Routing & Statistics Matrix Drilldown

#### Goal:
Verify that `AdministrativeService` and `StatisticService` correctly resolve leaf areas and hierarchical rollups under dynamic configurations.

#### Execution Steps:
| Step | API Endpoint / Action | Expected Result | Status |
|---|---|---|---|
| **7.1** | Query descendant leaf IDs for an area:<br>`AdministrativeService.get_descendant_ward_ids(db, prov_id)` | Returns all leaf `desa` or `ward` IDs that start with `prov_id.path`. | [x] **PASSED** (2026-08-18) |
| **7.2** | Call Crop Distribution Matrix API:<br>`GET /api/statistic/crops/distribution` | Returns matrix where `level_name` matches first child level (`Region` or `Provinsi`), and crops are aggregated across all descendant farmers. | [x] **PASSED** (2026-08-18) |
| **7.3** | Call Ward Farmer Stats API:<br>`GET /api/statistic/farmers/wards?administrative_id=<kab_id>` | Returns farmer counts grouped by each leaf area under the specified parent area. | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 8: Combined Dynamic Onboarding Fields with Dynamic Hierarchy (Custom Partner Flow)

#### Goal:
Verify that deployment partners can configure both **custom onboarding fields** (e.g. custom enum for farm size, optional irrigation source) and **dynamic administrative hierarchy** simultaneously in `config.json`, and that farmers seamlessly progress through the combined flow.

#### Setup:
1. Update `backend/config.json` with Indonesia 5-tier hierarchy and custom onboarding fields:
   ```json
   "administrative_hierarchy": {
     "country_code": "IDN",
     "delimiter": " > ",
     "levels": [
       { "level_index": 0, "name": "country", "display": { "en": "Country" } },
       { "level_index": 1, "name": "provinsi", "display": { "en": "Provinsi" } },
       { "level_index": 2, "name": "kabupaten", "display": { "en": "Kabupaten" } },
       { "level_index": 3, "name": "kecamatan", "display": { "en": "Kecamatan" } },
       { "level_index": 4, "name": "desa", "display": { "en": "Desa" } }
     ]
   },
   "onboarding": {
     "enabled": true,
     "fields": [
       { "field_name": "language", "enabled": true, "required": true, "priority": 0, "field_type": "enum", "options": ["en", "id"] },
       { "field_name": "full_name", "enabled": true, "required": true, "priority": 1, "field_type": "string", "extraction_method": "extract_full_name" },
       { "field_name": "administration", "enabled": true, "required": true, "priority": 2, "field_type": "location", "extraction_method": "extract_location" },
       {
         "field_name": "farm_size",
         "db_field": "farm_size",
         "enabled": true,
         "required": true,
         "priority": 3,
         "field_type": "enum",
         "extraction_method": "extract_enum",
         "options": [
           { "id": "small", "labels": { "en": "< 1 Hectare", "id": "< 1 Hektar" } },
           { "id": "medium", "labels": { "en": "1 - 5 Hectares", "id": "1 - 5 Hektar" } },
           { "id": "large", "labels": { "en": "> 5 Hectares", "id": "> 5 Hektar" } }
         ],
         "questions": {
           "en": "What is the size of your farm?\n1. < 1 Hectare\n2. 1 - 5 Hectares\n3. > 5 Hectares",
           "id": "Berapa luas lahan pertanian Anda?\n1. < 1 Hektar\n2. 1 - 5 Hektar\n3. > 5 Hektar"
         },
         "labels": { "en": "Farm Size", "id": "Luas Lahan" }
       },
       {
         "field_name": "water_source",
         "db_field": "water_source",
         "enabled": true,
         "required": false,
         "priority": 4,
         "field_type": "string",
         "extraction_method": "extract_string",
         "questions": {
           "en": "What is your main water source? (e.g. Well, River, Rainfed)",
           "id": "Apa sumber air utama pertanian Anda? (contoh: Sumur, Sungai, Tadah Hujan)"
         },
         "labels": { "en": "Water Source", "id": "Sumber Air" }
       },
       { "field_name": "crop_type", "enabled": true, "required": true, "priority": 5, "field_type": "string", "extraction_method": "extract_crop_type" }
     ]
   }
   ```

#### Execution Steps:
| Step | Action / User Message | Expected System Response | DB & State Verification | Status |
|---|---|---|---|---|
| **8.1** | Send Greeting:<br>`Body=Halo` | Welcome prompt + Language selection (`1. English`, `2. Swahili`). | Customer created with `status='in_progress'`. | [x] **PASSED** (2026-08-18) |
| **8.2** | Select Language & Name:<br>`Body=1` $\rightarrow$ `Body=Hajirin` | Name confirmed (`Thank you, Hajirin!`) and **immediately transitions** to dynamic Level 1 (Provinsi):<br>`"Where is your farm located?\n\nPlease select your area:\n\n1. Jawa Barat\n2. Jawa Tengah"` | `customer.full_name = 'Hajirin'`, `current_onboarding_field = 'administration'`. | [x] **PASSED** (2026-08-18) |
| **8.3** | Traverse 4-Level Location:<br>`Body=1` (Jawa Barat)<br>`Body=1` (Kabupaten Bandung)<br>`Body=1` (Kecamatan Cileunyi)<br>`Body=1` (Desa Cibiruhilir) | Progresses through all 4 levels. On reaching leaf `Desa Cibiruhilir`, confirms location and transitions to **custom field `farm_size`**:<br>`"What is the size of your farm?\n1. < 1 Hectare\n2. 1 - 5 Hectares\n3. > 5 Hectares"` | `customer_administrative` linked to `Desa Cibiruhilir` (`level_index: 4`). `_admin_hierarchy` state cleared. | [x] **PASSED** (2026-08-18) |
| **8.4** | Select Custom Field 1:<br>`Body=1` (< 1 Hectare) | Saves `farm_size='1'` and asks optional `water_source` question:<br>`"What is your main water source? (e.g. Well, River, Rainfed)\n\n(Reply 'skip' if you prefer not to answer)"` | `customer.profile_data['farm_size'] = '1'`. | [x] **PASSED** (2026-08-18) |
| **8.5** | Answer Optional Field 2:<br>`Body=River` | Acknowledges answer and advances to `crop_type` list. | `customer.profile_data['water_source'] = 'River'`. | [x] **PASSED** (2026-08-18) |
| **8.6** | Select Crop & Demographics:<br>`Body=2` (Potato), Female, 34 | Onboarding completes! Displays summary with custom fields and dynamic 5-tier location path. | `status = 'completed'`. Summary displays `Location: Indonesia > Jawa Barat > Kabupaten Bandung > Kecamatan Cileunyi > Desa Cibiruhilir`, `Farm Size: 1`, `Water Source: River`, `Primary Crops: potato`. | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 9: Dynamic Question Re-ordering (Location Precedence)

#### Goal:
Verify that if `administration` is configured with `priority: 1` (asked before `full_name` or after demographics), the onboarding state machine handles the flow seamlessly without assuming hardcoded question sequences.

#### Execution Steps:
| Step | Configuration & Action | Expected Result | DB Verification | Status |
|---|---|---|---|---|
| **9.1** | Configure `administration` with `priority: 1` and `full_name` with `priority: 2` in `config.json`. | System begins location questionnaire immediately after language choice. | `current_onboarding_field = 'administration'`. | [x] **PASSED** (2026-08-18) |
| **9.2** | Complete hierarchical location selection (`2` $\rightarrow$ `1` $\rightarrow$ `1` $\rightarrow$ `1`). | On saving leaf area, system advances to `full_name` (`"What is your full name?"`). | `customer_administrative` saved while `full_name` is still pending. | [x] **PASSED** (2026-08-18) |
| **9.3** | Enter name (`Body=Said`) $\rightarrow$ complete remaining questions. | Flow completes normally with full summary. | Customer record has both name and administrative location. | [x] **PASSED** (2026-08-18) |

---

### 🧪 Scenario 10: Mandatory Location Enforcement (Strict Selection Guard)

#### Goal:
Verify that because `administration` is configured as a `required: true` field, sending text inputs like `"skip"`, `"pass"`, or arbitrary text while in the middle of a multi-tier location questionnaire (e.g. at Level 2 Kabupaten) correctly enforces numeric selection without advancing or leaving corrupted in-flight state.

#### Execution Steps:
| Step | Action / Message | Expected Result | DB Verification |
|---|---|---|---|
| **10.1** | Farmer at Level 1 selects `1` (Jawa Barat). System shows Level 2 Kabupaten options. | State has `_admin_hierarchy` with candidate Kabupaten IDs. | `customer.profile_data['_admin_hierarchy']` present. |
| **10.2** | Farmer replies `Body=skip` (or `Body=lewati`). | System strictly rejects skip with validation warning (`"Please reply with a number (e.g., '1', '2') corresponding to your choice."`). | State preserved at `awaiting_selection`. No data lost. |
| **10.3** | Farmer replies `Body=1` (Kabupaten Bandung). | System proceeds to Level 3 Kecamatan normally. | Hierarchy traversal continues seamlessly. |

---

## 5. QA Verification & Sign-Off Matrix

| Scenario ID | Test Scenario Description | Pass Criteria | Tester | Status |
|---|---|---|---|---|
| **TC-01** | Kenya 4-Tier Seeder & `level_index` Assignment | Levels 0, 1, 2, 3 persisted with unique constraint | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-02** | Kenya 4-Tier WhatsApp Onboarding | 3-step prompt completes and saves ward in DB | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-03** | Country Swap Seeder (`--replace-country`) | Clean purge and re-seed of 5-tier Indonesia structure | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-04** | Indonesia 5-Tier WhatsApp Onboarding | 4-step prompt completes and saves desa in DB | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-05** | Country-Swap Safety Guard Block | Aborts with code 1 if `customers.count() > 0` | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-06** | Minimal 2-Tier Hierarchy Onboarding | Single-step selection saves leaf region immediately | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-07** | Isolated Area (0 Children) Handling | Saves intermediate area without crash or empty menu | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-08** | Input Validation (Out of Range & Non-Numeric) | Localized error message re-prompts choice | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-09** | Swahili Locale Dynamic Prompts | Correct Swahili phrasing for custom level names | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-10** | Statistics API Leaf & Drilldown Resolution | Dynamic level naming and accurate descendant rollups | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-11** | Combined Dynamic Hierarchy + Custom Questions (Scenario 8) | Custom enum/optional fields + 4-tier traversal in single flow | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-12** | Dynamic Question Re-ordering (Scenario 9) | Location prompt before full name executes cleanly | Galih Pratama | [x] **PASSED** (2026-08-18) |
| **TC-13** | Mandatory Location Enforcement (Scenario 10) | Rejects non-numeric text/skip and enforces selection | Galih Pratama | [x] **PASSED** (2026-08-18) |
