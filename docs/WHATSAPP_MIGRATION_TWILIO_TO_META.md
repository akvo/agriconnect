# AgriConnect WhatsApp Migration: Twilio to Meta Cloud API

> **Document Purpose:** Engineering delivery plan for Asana task creation. Optimized for execution speed, simplicity, and low-risk migration.

> **STATUS (June 2026):** The error "You can't currently access payment configurations" is expected - Twilio owns the current WABA. We need to create our own WABA to proceed.

---

## 1. Executive Summary

**What we're doing:** Replacing Twilio WhatsApp API with direct Meta WhatsApp Cloud API.

**Why:** Direct Meta integration eliminates BSP middleman, reduces costs, and gives us full control.

**Scope:** Transport layer only. No changes to AI, RAG, or application logic.

**Estimated effort:** 45-65 engineering hours (see Section 8 for breakdown).

---

## 2. Current vs Target Architecture

```
CURRENT:  AgriConnect → Twilio (BSP) → Meta/WhatsApp
          - We pay Twilio
          - Twilio owns WABA
          - Twilio handles billing

TARGET:   AgriConnect → Meta/WhatsApp (Direct)
          - We pay Meta directly
          - We own WABA
          - Full control
```

---

## 3. Out of Scope

This migration does **NOT** include:

- AI assistant logic changes
- RAG service changes
- RabbitMQ configuration changes
- Knowledge base changes
- Farmer onboarding flow redesign
- Extension Officer workflow redesign
- Analytics or reporting changes
- Mobile app changes
- Frontend dashboard changes
- New product features unrelated to WhatsApp transport
- Multi-provider support (we are doing a full migration, not adding a provider)

**If any of the above is requested, it should be a separate project.**

---

## 4. Task Classification

| Classification | Meaning |
|----------------|---------|
| **Required** | Migration cannot succeed without this |
| **Recommended** | Reduces risk or improves maintainability |
| **Optional** | Nice to have, can be deferred post-migration |

---

## 5. Effort Estimation Notes

Estimates assume:
- Experienced engineer with codebase familiarity
- Claude Code available for implementation
- Existing Twilio integration as reference

Estimates are **conservative** to account for:
- Meta/Twilio coordination delays
- Template approval cycles
- Unexpected integration issues
- Testing iterations

---

## 6. Detailed Task Breakdown

### Phase 0: Discovery & Governance (Required)

---

#### 0.1 Audit Current Twilio Integration

**Classification:** Required

**Description:** Review the repository and document all Twilio-specific functionality before migration begins. This creates the migration checklist.

**User AC:**
- Existing functionality fully understood
- No Twilio feature left unmapped

**Tech AC:**
- Twilio webhook endpoints documented (`/api/whatsapp/webhook`, `/api/whatsapp/status`)
- All Twilio API calls identified in codebase
- Template usage documented (confirmation, reconnection, broadcast)
- Media handling documented (voice download, image upload/download)
- Status callback flow documented
- Environment variables documented (`TWILIO_*` variables)
- Twilio-specific helper/service classes identified (`WhatsAppService`, `TwilioStatusService`)
- Phone number format handling documented (`whatsapp:` prefix)

**Risk / Considerations:**
- Missing functionality may cause production regressions
- This audit becomes the migration checklist

**Estimated Hours:** 2

**Priority:** Critical

**Dependencies:** None

---

#### 0.2 Verify Business Portfolio Ownership

**Classification:** Required

**Description:** Confirm AgriConnect has proper ownership and admin access to Meta Business Portfolio. Document recovery procedures.

**User AC:**
- Business Portfolio ownership documented
- At least 2 administrators have full access
- Recovery contact documented
- No single point of failure (one employee leaving doesn't lock us out)

**Tech AC:**
- Business Portfolio ID documented
- All admin users listed with access levels
- Business verification status confirmed as "Verified"
- Recovery path documented (how to regain access if primary admin unavailable)
- Meta Business support contact information saved

**Risk / Considerations:**
- If only one person has admin access, add another before proceeding
- Recovery procedures should be tested by secondary admin

**Estimated Hours:** 1.5

**Priority:** Critical

**Dependencies:** None

---

### Phase 1: Meta Setup (Required)

---

#### 1.1 Create New WABA

**Classification:** Required

**Description:** Create a WhatsApp Business Account directly under our Business Portfolio (separate from Twilio's WABA).

**User AC:**
- New WABA exists under AgriConnect's direct control
- WABA name clearly identifies it (e.g., "AgriConnect Direct")

**Tech AC:**
- WABA ID documented
- WABA visible in Business Settings → Accounts → WhatsApp Accounts

**Risk / Considerations:**
- We will have two WABAs temporarily (Twilio's and ours)
- Do NOT delete Twilio's WABA - it stays active until migration complete

**Estimated Hours:** 0.5

**Priority:** Critical

**Dependencies:** 0.2

---

#### 1.2 Configure Payment Method

**Classification:** Required

**Description:** Add payment method to our new WABA.

**User AC:**
- WhatsApp API can be used without payment failures
- Billing notifications go to appropriate team

**Tech AC:**
- Credit card or payment method added
- Billing threshold configured
- Notification email set

**Risk / Considerations:**
- Requires finance team coordination for payment details
- Set reasonable spending limits initially

**Estimated Hours:** 0.5

**Priority:** Critical

**Dependencies:** 1.1

---

#### 1.3 Create Meta App and Generate Access Token

**Classification:** Required

**Description:** Create Facebook App with WhatsApp product and generate permanent access token.

**User AC:**
- API credentials ready for engineering team

**Tech AC:**
- Facebook App created at developers.facebook.com
- WhatsApp product added to app
- System User created in Business Settings
- Permanent access token generated (NOT temporary 24-hour token)
- Token has permissions: `whatsapp_business_management`, `whatsapp_business_messaging`
- Phone Number ID documented

**Risk / Considerations:**
- Use System User tokens, not personal tokens
- Document token rotation procedure

**Estimated Hours:** 1

**Priority:** Critical

**Dependencies:** 1.1

---

#### 1.4 Create Template Drafts

**Classification:** Required

**Description:** Draft all WhatsApp message templates for submission to Meta.

**User AC:**
- Template content matches current Twilio templates
- Templates prepared in both EN and SW

**Tech AC:**
- Confirmation template drafted (EN + SW) - with escalate button
- Reconnection template drafted (EN + SW) - for 24-hour re-engagement
- Broadcast template drafted (EN + SW) - for announcements
- Template names documented
- Button payloads defined

**Risk / Considerations:**
- Review Meta's template guidelines before drafting
- Have backup wording ready in case of rejection

**Estimated Hours:** 2

**Priority:** Critical

**Dependencies:** 1.1

---

#### 1.5 Submit Templates for Approval

**Classification:** Required

**Description:** Submit drafted templates to Meta for approval.

**User AC:**
- All templates submitted
- Approval status tracked

**Tech AC:**
- Templates submitted via WhatsApp Manager
- Submission timestamps documented
- Expected approval timeline noted (typically 1-24 hours)

**Risk / Considerations:**
- Approval can take 1-24 hours, sometimes longer
- Do not proceed to backend template integration until approved

**Estimated Hours:** 0.5

**Priority:** Critical

**Dependencies:** 1.4

---

#### 1.6 Review and Revise Rejected Templates

**Classification:** Required (if rejections occur)

**Description:** Handle any template rejections from Meta.

**User AC:**
- All templates eventually approved

**Tech AC:**
- Rejection reasons analyzed
- Templates revised per Meta guidelines
- Resubmitted and approved

**Risk / Considerations:**
- May require multiple revision cycles
- Common rejection reasons: unclear purpose, spam-like content, policy violations

**Estimated Hours:** 1-3 (contingency)

**Priority:** High

**Dependencies:** 1.5

---

### Phase 2: Phone Number Migration (Required)

---

#### 2.1 Document Current Twilio Setup

**Classification:** Required

**Description:** Document current phone number configuration in Twilio before migration.

**User AC:**
- Clear record of what we're migrating

**Tech AC:**
- Phone number documented (full E.164 format)
- Twilio Account SID documented
- Current webhook configurations noted
- Confirm number is active and working

**Estimated Hours:** 0.5

**Priority:** Critical

**Dependencies:** 0.1

---

#### 2.2 Contact Twilio to Request Migration

**Classification:** Required

**Description:** Submit migration request to Twilio support.

**User AC:**
- Migration process initiated
- Timeline and process confirmed by Twilio

**Tech AC:**
- Support ticket submitted with:
  - Phone number
  - Twilio Account SID
  - Target WABA ID
  - Preferred migration window
- Response received with migration instructions
- Actual downtime expectations clarified

**Risk / Considerations:**
- Twilio response may take 1-3 business days
- Have fallback dates for migration window
- **Do not commit to specific downtime duration until Twilio confirms**

**Estimated Hours:** 1 (plus waiting time)

**Priority:** Critical

**Dependencies:** 1.1, 1.2, 1.3, 1.5, 2.1

---

#### 2.3 Schedule Migration Window

**Classification:** Required

**Description:** Coordinate migration timing with Twilio and internal team.

**User AC:**
- All stakeholders aware of potential service disruption
- Migration scheduled for low-traffic period

**Tech AC:**
- Date/time confirmed with Twilio
- Internal team notified
- Rollback plan documented
- Customer communication prepared (if needed)

**Risk / Considerations:**
- Actual migration behavior depends on Twilio and Meta processing
- Downtime may range from minutes to several hours
- Timeline should be confirmed with Twilio before communicating externally
- Avoid committing to specific downtime duration until migration guidance is received
- Schedule for weekend night if possible to minimize impact

**Estimated Hours:** 1

**Priority:** Critical

**Dependencies:** 2.2

---

#### 2.4 Execute Migration Window

**Classification:** Required

**Description:** Complete phone number migration from Twilio to our WABA.

**User AC:**
- Phone number registered under our WABA
- Customers can reach us on same number

**Tech AC:**
- Twilio releases number
- Number registered in our WABA
- Verification code received and entered
- Display name configured
- Webhooks configured to point to our backend

**Risk / Considerations:**
- Have backend deployed and ready BEFORE this step
- Monitor closely for issues
- Have Twilio support contact ready

**Estimated Hours:** 2 (active time during migration)

**Priority:** Critical

**Dependencies:** 2.3, all Phase 3 tasks complete

---

#### 2.5 Validate Migrated Number

**Classification:** Required

**Description:** Confirm number is working correctly after migration.

**User AC:**
- Test messages send and receive successfully

**Tech AC:**
- Send test message from number
- Receive test message to number
- Verify webhooks receiving events
- Verify delivery status callbacks working

**Estimated Hours:** 1

**Priority:** Critical

**Dependencies:** 2.4

---

### Phase 3: Backend Development (Required)

---

#### 3.1 Add Meta Configuration to Environment

**Classification:** Required

**Description:** Add Meta WhatsApp Cloud API configuration to backend.

**User AC:**
- Backend can be configured for Meta API

**Tech AC:**
- Add to `.env.example`:
  - `META_WHATSAPP_ACCESS_TOKEN`
  - `META_WHATSAPP_PHONE_NUMBER_ID`
  - `META_WHATSAPP_BUSINESS_ACCOUNT_ID`
  - `META_WEBHOOK_VERIFY_TOKEN`
  - `META_APP_SECRET`
- Add to `backend/config.py`:
  - Meta settings class/section
- Update template configuration in `config.json` for Meta template names

**Files to modify:**
- `.env.example`
- `backend/config.py`
- `backend/config.json`

**Estimated Hours:** 1

**Priority:** Critical

**Dependencies:** 1.3

---

#### 3.2 Implement Webhook Verification Endpoint

**Classification:** Required

**Description:** Add GET endpoint for Meta webhook verification handshake.

**User AC:**
- Meta can verify our webhook URL

**Tech AC:**
- GET endpoint at `/api/whatsapp/webhook` (reuse existing path)
- Accepts: `hub.mode`, `hub.verify_token`, `hub.challenge`
- Returns `hub.challenge` when verification succeeds
- Returns 403 when verification fails

**Files to modify:**
- `backend/routers/whatsapp.py`

**Estimated Hours:** 0.5

**Priority:** Critical

**Dependencies:** 3.1

---

#### 3.3 Create Meta Webhook Payload Parser

**Classification:** Required

**Description:** Parse incoming Meta webhook payloads into internal message format.

**User AC:**
- Incoming messages are processed correctly

**Tech AC:**
- Parse `entry[].changes[].value.messages[]` structure
- Extract: sender phone, message type, text body, timestamp
- Handle message types: text, audio, image, button/interactive
- Handle status updates: `entry[].changes[].value.statuses[]`
- Create Pydantic models for Meta payloads

**Files to create/modify:**
- Create: `backend/schemas/meta_webhook.py`
- Modify: `backend/routers/whatsapp.py`

**Estimated Hours:** 2

**Priority:** Critical

**Dependencies:** 3.1

---

#### 3.4 Implement Meta Message Sending

**Classification:** Required

**Description:** Create MetaWhatsAppService with text message sending.

**User AC:**
- System can send text messages via Meta API

**Tech AC:**
- Create `MetaWhatsAppService` class in `backend/services/meta_whatsapp_service.py`
- Implement `send_message(to_number, message_body)` method
- Use endpoint: `POST https://graph.facebook.com/v18.0/{phone_number_id}/messages`
- Handle authentication via Bearer token
- Return message ID (`wamid`) for tracking
- Reuse existing `sanitize_whatsapp_content()` function

**Files to create:**
- `backend/services/meta_whatsapp_service.py`

**Estimated Hours:** 1.5

**Priority:** Critical

**Dependencies:** 3.1

---

#### 3.5 Implement Template Message Sending

**Classification:** Required

**Description:** Implement template message sending for business-initiated conversations.

**User AC:**
- Confirmation, reconnection, and broadcast templates work

**Tech AC:**
- Implement `send_template_message(to_number, template_name, language, components)`
- Handle body parameters
- Handle button components (quick_reply payloads)
- Support EN and SW languages
- Map existing template logic to new method

**Files to modify:**
- `backend/services/meta_whatsapp_service.py`

**Estimated Hours:** 2

**Priority:** Critical

**Dependencies:** 3.4, 1.5 (templates approved)

---

#### 3.6 Implement Interactive Button Messages

**Classification:** Required

**Description:** Send interactive button messages (within 24-hour session).

**User AC:**
- Weather subscription buttons work
- Other interactive flows work

**Tech AC:**
- Implement `send_interactive_buttons(to_number, body_text, buttons)`
- Support reply buttons
- Handle button ID responses in webhook

**Files to modify:**
- `backend/services/meta_whatsapp_service.py`

**Estimated Hours:** 1

**Priority:** Critical

**Dependencies:** 3.4

---

#### 3.7 Implement Media Handling

**Classification:** Required

**Description:** Handle incoming and outgoing media (images, voice).

**User AC:**
- Voice messages are transcribed
- Images are stored
- EOs can send images to customers

**Tech AC:**
- **Incoming:** Download media using `GET /v18.0/{media_id}` then fetch URL with auth header
- **Outgoing:** Upload media first via `POST /v18.0/{phone_number_id}/media`, then send with media ID
- Reuse existing `download_twilio_media()` logic pattern
- Update voice transcription flow to use new download method

**Files to modify:**
- `backend/services/meta_whatsapp_service.py`
- `backend/routers/whatsapp.py` (media extraction)

**Estimated Hours:** 2.5

**Priority:** Critical

**Dependencies:** 3.4

---

#### 3.8 Update Status Callback Handling

**Classification:** Required

**Description:** Map Meta status updates to existing DeliveryStatus enum.

**User AC:**
- Message delivery status is tracked

**Tech AC:**
- Map Meta statuses: `sent`, `delivered`, `read`, `failed`
- Update `TwilioStatusService` → rename to `MessageStatusService`
- Use `wamid` instead of `message_sid` for message lookup
- Handle error details for failed messages

**Files to modify:**
- `backend/services/twilio_status_service.py` → `backend/services/message_status_service.py`
- `backend/routers/whatsapp.py`

**Estimated Hours:** 1.5

**Priority:** Critical

**Dependencies:** 3.3

---

#### 3.9 Implement Webhook Signature Verification

**Classification:** Recommended

**Description:** Verify webhook payloads are from Meta using signature.

**User AC:**
- Only genuine Meta webhooks are processed

**Tech AC:**
- Verify `X-Hub-Signature-256` header
- Use `META_APP_SECRET` for HMAC computation
- Skip verification in test mode (`TESTING=true`)
- Log failed verification attempts

**Files to modify:**
- `backend/routers/whatsapp.py`

**Estimated Hours:** 0.5

**Priority:** High

**Dependencies:** 3.3

---

#### 3.10 Integrate Meta Service into Router

**Classification:** Required

**Description:** Replace Twilio service calls with Meta service throughout the webhook handler.

**User AC:**
- All message flows use Meta API

**Tech AC:**
- Replace `WhatsAppService` calls with `MetaWhatsAppService`
- Update phone number format handling (remove `whatsapp:` prefix)
- Update message SID handling to use `wamid`
- Test all message flows

**Files to modify:**
- `backend/routers/whatsapp.py`
- `backend/services/message_service.py` (if needed)

**Estimated Hours:** 2.5

**Priority:** Critical

**Dependencies:** 3.4, 3.5, 3.6, 3.7, 3.8

---

### Phase 4: Testing (Required)

---

#### 4.1 Update Unit Tests

**Classification:** Required

**Description:** Update existing WhatsApp tests for Meta payloads.

**User AC:**
- All tests pass

**Tech AC:**
- Create Meta webhook fixtures in `backend/tests/fixtures/`
- Update test mocks to mock Meta API responses
- Ensure existing test coverage is maintained

**Files to modify:**
- `backend/tests/test_whatsapp.py`
- `backend/tests/test_whatsapp_service.py`
- `backend/tests/test_whatsapp_ai_integration.py`
- Other WhatsApp-related test files

**Estimated Hours:** 3

**Priority:** Critical

**Dependencies:** 3.10

---

#### 4.2 Local Integration Testing

**Classification:** Recommended

**Description:** Test Meta integration locally with ngrok tunnel.

**User AC:**
- Developer can test webhook locally before production

**Tech AC:**
- Document ngrok setup for local testing
- Configure test phone number in Meta app (test mode)
- Verify end-to-end message flow locally

**Estimated Hours:** 2

**Priority:** High

**Dependencies:** 3.10

---

#### 4.3 End-to-End Testing with Real Messages

**Classification:** Required

**Description:** Test all message flows with real WhatsApp messages post-migration.

**User AC:**
- All customer flows verified working

**Tech AC:**
- Test matrix:
  - [ ] Customer sends text → AI responds
  - [ ] Customer sends voice → Transcribed and processed
  - [ ] Customer sends image → Stored and processed
  - [ ] 24-hour reconnection template
  - [ ] Escalation button → Ticket created
  - [ ] EO sends image to customer
  - [ ] Message delivery status tracked
  - [ ] Broadcast message delivery

**Estimated Hours:** 3

**Priority:** Critical

**Dependencies:** 2.4, 4.1

---

### Phase 5: Deployment (Required)

---

#### 5.1 Prepare Production Environment

**Classification:** Required

**Description:** Configure production environment variables for Meta.

**User AC:**
- Production ready for Meta API

**Tech AC:**
- Set all `META_*` environment variables in production
- Verify configuration with dry-run test (if possible)

**Estimated Hours:** 1

**Priority:** Critical

**Dependencies:** 3.1, 1.3

---

#### 5.2 Deploy Backend Changes

**Classification:** Required

**Description:** Deploy Meta integration code to production.

**User AC:**
- Production backend uses Meta API

**Tech AC:**
- Deploy during or before migration window (Task 2.4)
- Verify deployment successful
- Monitor logs for errors

**Estimated Hours:** 1

**Priority:** Critical

**Dependencies:** 4.1, 5.1

---

#### 5.3 Configure Meta Webhooks for Production

**Classification:** Required

**Description:** Point Meta webhooks to production URL.

**User AC:**
- Production receives Meta webhook events

**Tech AC:**
- Configure webhook URL in Meta App Dashboard
- Verify webhook with Meta's verification handshake
- Subscribe to: messages, message_status

**Estimated Hours:** 0.5

**Priority:** Critical

**Dependencies:** 5.2

---

#### 5.4 Post-Migration Monitoring

**Classification:** Required

**Description:** Monitor system after migration for issues.

**User AC:**
- Any issues are detected and addressed quickly

**Tech AC:**
- Monitor error logs for 48 hours
- Check message delivery rates
- Verify no failed messages accumulating
- Confirm retry logic working

**Estimated Hours:** 2 (spread over 48 hours)

**Priority:** Critical

**Dependencies:** 5.3

---

### Phase 6: Stabilization & Cleanup (Required)

---

#### 6.1 Maintain Twilio Rollback Capability

**Classification:** Required

**Description:** Keep Twilio account and configuration available as rollback option.

**User AC:**
- Rollback to Twilio is possible if critical issues arise

**Tech AC:**
- Twilio account remains active for minimum 30 days post-migration
- Twilio credentials preserved (not deleted from secrets manager)
- Old `WhatsAppService` code kept in codebase (can be commented or archived)
- Rollback procedure documented

**Risk / Considerations:**
- Do not cancel Twilio subscription until stability confirmed
- Rolling back requires re-migration coordination with Twilio

**Estimated Hours:** 1

**Priority:** Critical

**Dependencies:** 5.4

---

#### 6.2 Remove Twilio Dependencies

**Classification:** Recommended

**Description:** Remove Twilio-specific code after successful stabilization period.

**User AC:**
- Codebase is clean, no dead code

**Tech AC:**
- Remove `twilio` from requirements
- Remove Twilio environment variables from production
- Remove or archive `WhatsAppService` (old Twilio version)
- Update imports

**Risk / Considerations:**
- Only execute after 30+ days of stable operation
- Ensure rollback is no longer needed

**Estimated Hours:** 1

**Priority:** Medium

**Dependencies:** 6.1 (after 30 days stability)

---

#### 6.3 Update Documentation

**Classification:** Recommended

**Description:** Update CLAUDE.md and other docs for Meta API.

**User AC:**
- Documentation reflects current implementation

**Tech AC:**
- Update CLAUDE.md WhatsApp section
- Update any API documentation
- Archive this migration document

**Estimated Hours:** 1

**Priority:** Medium

**Dependencies:** 6.2

---

## 7. Rollback Plan

If critical issues occur after migration:

**During Migration Window:**
- Contact Twilio immediately to halt/reverse migration
- Re-register number with Twilio if needed

**After Migration Complete:**
- Rollback requires new migration request to Twilio
- Coordinate with Twilio support for timeline
- Keep Twilio account active for 30 days post-migration to enable this

**Rollback Decision Criteria:**
- Message delivery rate drops below 90%
- Critical message flows broken (AI responses, escalation, templates)
- Unable to receive customer messages for extended period

---

## 8. Total Effort Summary

| Category | Min Hours | Max Hours |
|----------|-----------|-----------|
| Admin / Meta Setup | 8 | 12 |
| Backend Development | 16 | 22 |
| QA / Testing | 6 | 10 |
| Deployment | 4 | 6 |
| Documentation | 1 | 2 |
| Contingency Buffer | 6 | 10 |
| **Total** | **41** | **62** |

**Planning Estimates:**
- **Minimum realistic effort:** 45 hours
- **Maximum realistic effort:** 65 hours
- **Recommended planning estimate:** 55 hours

**Notes:**
- Admin hours exclude waiting time (Twilio response 1-3 days, template approval 1-24 hours, migration coordination)
- Contingency covers: template rejections, unexpected API differences, integration issues
- Calendar time: approximately 3-4 weeks including waiting periods

---

## 9. Recommended Implementation Sequence

```
Week 1 (Discovery + Admin Setup)
├── Day 1: Task 0.1 (Audit Twilio), Task 0.2 (Verify Portfolio)
├── Day 2: Tasks 1.1, 1.2 (WABA + Payment)
├── Day 3: Task 1.3 (Meta App), Tasks 1.4, 1.5 (Templates)
├── Day 4-5: Begin Backend (Tasks 3.1-3.4)
└── [Wait for template approval]

Week 2 (Backend Development)
├── Day 1-2: Tasks 3.5-3.8 (Templates, Buttons, Media, Status)
├── Day 3: Tasks 3.9, 3.10 (Signature, Integration)
├── Day 4: Task 4.1 (Unit Tests)
├── Day 5: Task 4.2 (Local Testing), Task 2.1, 2.2 (Contact Twilio)
└── [Wait for Twilio response]

Week 3 (Migration Execution)
├── Confirm migration window with Twilio
├── Tasks 5.1, 5.2 (Production prep, Deploy)
├── Task 2.4 (Execute migration - schedule low-traffic)
├── Tasks 2.5, 5.3 (Validate, Configure webhooks)
└── Tasks 4.3, 5.4 (E2E Testing, Monitoring)

Week 4+ (Stabilization)
├── Continue monitoring
├── Task 6.1 (Maintain rollback)
└── After 30 days: Tasks 6.2, 6.3 (Cleanup, Docs)
```

---

## 10. Task Summary by Classification

### Required Tasks (Must Complete)

| Task | Hours | Phase |
|------|-------|-------|
| 0.1 Audit Current Twilio Integration | 2 | Discovery |
| 0.2 Verify Business Portfolio Ownership | 1.5 | Governance |
| 1.1 Create New WABA | 0.5 | Meta Setup |
| 1.2 Configure Payment Method | 0.5 | Meta Setup |
| 1.3 Create Meta App and Access Token | 1 | Meta Setup |
| 1.4 Create Template Drafts | 2 | Meta Setup |
| 1.5 Submit Templates for Approval | 0.5 | Meta Setup |
| 2.1 Document Current Twilio Setup | 0.5 | Migration |
| 2.2 Contact Twilio for Migration | 1 | Migration |
| 2.3 Schedule Migration Window | 1 | Migration |
| 2.4 Execute Migration Window | 2 | Migration |
| 2.5 Validate Migrated Number | 1 | Migration |
| 3.1 Add Meta Configuration | 1 | Backend |
| 3.2 Implement Webhook Verification | 0.5 | Backend |
| 3.3 Create Meta Webhook Parser | 2 | Backend |
| 3.4 Implement Meta Message Sending | 1.5 | Backend |
| 3.5 Implement Template Sending | 2 | Backend |
| 3.6 Implement Interactive Buttons | 1 | Backend |
| 3.7 Implement Media Handling | 2.5 | Backend |
| 3.8 Update Status Handling | 1.5 | Backend |
| 3.10 Integrate Meta Service | 2.5 | Backend |
| 4.1 Update Unit Tests | 3 | QA |
| 4.3 End-to-End Testing | 3 | QA |
| 5.1 Prepare Production Environment | 1 | Deploy |
| 5.2 Deploy Backend Changes | 1 | Deploy |
| 5.3 Configure Meta Webhooks | 0.5 | Deploy |
| 5.4 Post-Migration Monitoring | 2 | Deploy |
| 6.1 Maintain Twilio Rollback | 1 | Stabilization |

### Recommended Tasks (Should Complete)

| Task | Hours | Phase |
|------|-------|-------|
| 3.9 Webhook Signature Verification | 0.5 | Backend |
| 4.2 Local Integration Testing | 2 | QA |
| 6.2 Remove Twilio Dependencies | 1 | Cleanup |
| 6.3 Update Documentation | 1 | Cleanup |

### Conditional Tasks

| Task | Hours | Condition |
|------|-------|-----------|
| 1.6 Revise Rejected Templates | 1-3 | If templates rejected |

---

# Asana Task Breakdown

Copy the tasks below directly into Asana.

---

### [Discovery] Audit Current Twilio Integration

**Description:**
Review the repository and document all Twilio-specific functionality before migration begins. Creates the migration checklist.

**User AC:**
- Existing functionality fully understood
- No Twilio feature left unmapped

**Tech AC:**
- Twilio endpoints documented
- Twilio webhooks documented
- Template usage documented
- Media usage documented
- Status callbacks documented
- Environment variables documented
- Twilio-specific service classes identified

**Risk / Considerations:**
- Missing functionality may cause production regressions

**Estimated Hours:** 2

**Priority:** Critical

**Classification:** Required

**Dependencies:** None

---

### [Admin] Verify Business Portfolio Ownership

**Description:**
Confirm AgriConnect has proper ownership and admin access to Meta Business Portfolio. Document recovery procedures.

**User AC:**
- Business Portfolio ownership documented
- At least 2 administrators have full access
- Recovery contact documented

**Tech AC:**
- Business Portfolio ID documented
- All admin users listed with access levels
- Business verification status confirmed
- Recovery path documented

**Estimated Hours:** 1.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** None

---

### [Admin] Create New WABA

**Description:**
Create WhatsApp Business Account directly under our Business Portfolio.

**User AC:**
- New WABA under our direct control

**Tech AC:**
- WABA created in Business Settings → Accounts → WhatsApp Accounts
- WABA ID documented

**Risk / Considerations:**
- Keep Twilio's WABA active until migration complete

**Estimated Hours:** 0.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Verify Business Portfolio Ownership

---

### [Admin] Configure WABA Payment Method

**Description:**
Add payment method to new WABA.

**User AC:**
- WhatsApp API usable without payment failures

**Tech AC:**
- Payment method added
- Billing threshold configured
- Notification email set

**Risk / Considerations:**
- Coordinate with finance for payment details

**Estimated Hours:** 0.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Create New WABA

---

### [Admin] Create Meta App and Access Token

**Description:**
Create Facebook App with WhatsApp product and generate permanent System User access token.

**User AC:**
- API credentials ready for engineering

**Tech AC:**
- Facebook App created at developers.facebook.com
- WhatsApp product added
- System User created
- Permanent access token generated
- Phone Number ID documented

**Risk / Considerations:**
- Use System User tokens, not personal tokens

**Estimated Hours:** 1

**Priority:** Critical

**Classification:** Required

**Dependencies:** Create New WABA

---

### [Admin] Create Template Drafts

**Description:**
Draft all WhatsApp message templates for submission to Meta.

**User AC:**
- Template content matches current Twilio templates
- Templates prepared in EN and SW

**Tech AC:**
- Confirmation template drafted (EN + SW)
- Reconnection template drafted (EN + SW)
- Broadcast template drafted (EN + SW)
- Template names documented

**Estimated Hours:** 2

**Priority:** Critical

**Classification:** Required

**Dependencies:** Create New WABA

---

### [Admin] Submit Templates for Approval

**Description:**
Submit drafted templates to Meta for approval.

**User AC:**
- All templates submitted
- Approval status tracked

**Tech AC:**
- Templates submitted via WhatsApp Manager
- Submission timestamps documented

**Risk / Considerations:**
- Approval can take 1-24 hours

**Estimated Hours:** 0.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Create Template Drafts

---

### [Admin] Review and Revise Rejected Templates

**Description:**
Handle any template rejections from Meta.

**User AC:**
- All templates eventually approved

**Tech AC:**
- Rejection reasons analyzed
- Templates revised and resubmitted

**Estimated Hours:** 1-3

**Priority:** High

**Classification:** Required (if rejections occur)

**Dependencies:** Submit Templates for Approval

---

### [Admin] Document Current Twilio Setup

**Description:**
Document current phone number configuration in Twilio before migration.

**User AC:**
- Clear record of what we're migrating

**Tech AC:**
- Phone number documented (E.164)
- Twilio Account SID documented
- Current configurations noted

**Estimated Hours:** 0.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Audit Current Twilio Integration

---

### [Admin] Contact Twilio for Migration

**Description:**
Submit phone number migration request to Twilio support.

**User AC:**
- Migration process initiated with Twilio

**Tech AC:**
- Support ticket submitted with phone number, Account SID, target WABA ID
- Response received with instructions
- Actual downtime expectations clarified

**Risk / Considerations:**
- Response may take 1-3 business days
- Do not commit to downtime duration until Twilio confirms

**Estimated Hours:** 1

**Priority:** Critical

**Classification:** Required

**Dependencies:** Create New WABA, Configure WABA Payment, Create Meta App, Submit Templates, Document Current Twilio Setup

---

### [Admin] Schedule Migration Window

**Description:**
Coordinate migration timing with Twilio and internal team.

**User AC:**
- All stakeholders aware of potential disruption
- Low-traffic period selected

**Tech AC:**
- Date/time confirmed with Twilio
- Team notified
- Rollback plan ready

**Risk / Considerations:**
- Downtime may range from minutes to several hours
- Confirm timeline with Twilio before external communication

**Estimated Hours:** 1

**Priority:** Critical

**Classification:** Required

**Dependencies:** Contact Twilio for Migration

---

### [Backend] Add Meta Configuration

**Description:**
Add Meta WhatsApp Cloud API environment variables and configuration.

**User AC:**
- Backend configurable for Meta API

**Tech AC:**
- `.env.example` updated with META_* variables
- `backend/config.py` updated with Meta settings
- `config.json` updated for Meta template names

**Estimated Hours:** 1

**Priority:** Critical

**Classification:** Required

**Dependencies:** Create Meta App and Access Token

---

### [Backend] Implement Webhook Verification

**Description:**
Add GET endpoint for Meta webhook verification handshake.

**User AC:**
- Meta can verify our webhook URL

**Tech AC:**
- GET endpoint accepts hub.mode, hub.verify_token, hub.challenge
- Returns challenge on success, 403 on failure

**Files:** `backend/routers/whatsapp.py`

**Estimated Hours:** 0.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Add Meta Configuration

---

### [Backend] Create Meta Webhook Parser

**Description:**
Parse incoming Meta webhook payloads into internal message format.

**User AC:**
- Incoming messages processed correctly

**Tech AC:**
- Parse entry[].changes[].value.messages[]
- Handle text, audio, image, button types
- Handle status updates
- Pydantic models created

**Files:** `backend/schemas/meta_webhook.py`, `backend/routers/whatsapp.py`

**Estimated Hours:** 2

**Priority:** Critical

**Classification:** Required

**Dependencies:** Add Meta Configuration

---

### [Backend] Implement Meta Message Sending

**Description:**
Create MetaWhatsAppService with text message sending.

**User AC:**
- System can send text messages via Meta

**Tech AC:**
- MetaWhatsAppService class created
- send_message() method implemented
- Bearer token authentication
- Returns wamid for tracking

**Files:** `backend/services/meta_whatsapp_service.py`

**Estimated Hours:** 1.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Add Meta Configuration

---

### [Backend] Implement Template Sending

**Description:**
Add template message sending for business-initiated conversations.

**User AC:**
- Confirmation, reconnection, broadcast templates work

**Tech AC:**
- send_template_message() method implemented
- Body parameters handled
- Button components handled
- EN and SW languages supported

**Files:** `backend/services/meta_whatsapp_service.py`

**Estimated Hours:** 2

**Priority:** Critical

**Classification:** Required

**Dependencies:** Implement Meta Message Sending, Submit Templates for Approval

---

### [Backend] Implement Interactive Buttons

**Description:**
Send interactive button messages within 24-hour session.

**User AC:**
- Weather subscription buttons work

**Tech AC:**
- send_interactive_buttons() method implemented
- Reply buttons supported

**Files:** `backend/services/meta_whatsapp_service.py`

**Estimated Hours:** 1

**Priority:** Critical

**Classification:** Required

**Dependencies:** Implement Meta Message Sending

---

### [Backend] Implement Media Handling

**Description:**
Handle incoming media download and outgoing media upload.

**User AC:**
- Voice messages transcribed, images stored, EOs can send images

**Tech AC:**
- Incoming media download with auth header
- Outgoing media upload then send
- Voice transcription flow updated

**Files:** `backend/services/meta_whatsapp_service.py`, `backend/routers/whatsapp.py`

**Estimated Hours:** 2.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Implement Meta Message Sending

---

### [Backend] Update Status Handling

**Description:**
Map Meta status updates to DeliveryStatus enum.

**User AC:**
- Message delivery status tracked

**Tech AC:**
- Meta statuses mapped (sent, delivered, read, failed)
- Service renamed to MessageStatusService
- wamid used for lookup

**Files:** `backend/services/message_status_service.py`, `backend/routers/whatsapp.py`

**Estimated Hours:** 1.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Create Meta Webhook Parser

---

### [Backend] Implement Signature Verification

**Description:**
Verify webhook payloads are from Meta using HMAC signature.

**User AC:**
- Only genuine Meta webhooks processed

**Tech AC:**
- X-Hub-Signature-256 header verified
- Skip in test mode
- Failed attempts logged

**Files:** `backend/routers/whatsapp.py`

**Estimated Hours:** 0.5

**Priority:** High

**Classification:** Recommended

**Dependencies:** Create Meta Webhook Parser

---

### [Backend] Integrate Meta Service into Router

**Description:**
Replace all Twilio service calls with Meta service in webhook handler.

**User AC:**
- All message flows use Meta API

**Tech AC:**
- WhatsAppService calls replaced with MetaWhatsAppService
- Phone number format updated (no whatsapp: prefix)
- Message SID → wamid
- All flows tested

**Files:** `backend/routers/whatsapp.py`

**Estimated Hours:** 2.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** All other Backend tasks

---

### [QA] Update Unit Tests

**Description:**
Update WhatsApp tests for Meta webhook payloads and API responses.

**User AC:**
- All tests pass

**Tech AC:**
- Meta webhook fixtures created
- Test mocks updated for Meta API
- Coverage maintained

**Files:** All `backend/tests/test_whatsapp*.py` files

**Estimated Hours:** 3

**Priority:** Critical

**Classification:** Required

**Dependencies:** Integrate Meta Service into Router

---

### [QA] Local Integration Testing

**Description:**
Test Meta integration locally using ngrok tunnel.

**User AC:**
- Developer can test webhooks locally

**Tech AC:**
- ngrok setup documented
- Test phone number configured
- End-to-end flow verified locally

**Estimated Hours:** 2

**Priority:** High

**Classification:** Recommended

**Dependencies:** Integrate Meta Service into Router

---

### [Deploy] Prepare Production Environment

**Description:**
Configure production environment variables for Meta API.

**User AC:**
- Production ready for Meta

**Tech AC:**
- All META_* env vars set in production
- Configuration verified

**Estimated Hours:** 1

**Priority:** Critical

**Classification:** Required

**Dependencies:** Add Meta Configuration, Create Meta App and Access Token

---

### [Deploy] Execute Phone Number Migration

**Description:**
Complete phone number migration during scheduled window.

**User AC:**
- Number registered under our WABA

**Tech AC:**
- Twilio releases number
- Number registered in our WABA
- Display name configured
- Webhooks configured

**Risk / Considerations:**
- Deploy backend BEFORE this task
- Monitor closely

**Estimated Hours:** 2

**Priority:** Critical

**Classification:** Required

**Dependencies:** Schedule Migration Window, All Backend and QA tasks

---

### [Deploy] Deploy Backend and Configure Webhooks

**Description:**
Deploy Meta integration code and configure production webhooks.

**User AC:**
- Production using Meta API

**Tech AC:**
- Backend deployed
- Webhook URL configured in Meta
- Webhook verified
- Subscribed to messages and statuses

**Estimated Hours:** 1.5

**Priority:** Critical

**Classification:** Required

**Dependencies:** Prepare Production Environment, Execute Phone Number Migration

---

### [QA] End-to-End Production Testing

**Description:**
Verify all message flows with real WhatsApp messages in production.

**User AC:**
- All customer flows verified

**Tech AC:**
- Test all items in test matrix (text, voice, image, templates, buttons, delivery status)

**Estimated Hours:** 3

**Priority:** Critical

**Classification:** Required

**Dependencies:** Deploy Backend and Configure Webhooks

---

### [Deploy] Post-Migration Monitoring

**Description:**
Monitor system for 48 hours after migration.

**User AC:**
- Issues detected and resolved quickly

**Tech AC:**
- Error logs monitored
- Delivery rates checked
- No failed message backlog

**Estimated Hours:** 2

**Priority:** Critical

**Classification:** Required

**Dependencies:** End-to-End Production Testing

---

### [Stabilization] Maintain Twilio Rollback Capability

**Description:**
Keep Twilio account and configuration available as rollback option for 30 days.

**User AC:**
- Rollback to Twilio is possible if critical issues arise

**Tech AC:**
- Twilio account remains active
- Twilio credentials preserved
- Rollback procedure documented

**Estimated Hours:** 1

**Priority:** Critical

**Classification:** Required

**Dependencies:** Post-Migration Monitoring

---

### [Cleanup] Remove Twilio Dependencies

**Description:**
Remove Twilio code and dependencies after 30+ days stability.

**User AC:**
- Clean codebase

**Tech AC:**
- twilio removed from requirements
- Twilio env vars removed
- Old WhatsAppService removed

**Estimated Hours:** 1

**Priority:** Medium

**Classification:** Recommended

**Dependencies:** Maintain Twilio Rollback (after 30 days)

---

### [Docs] Update Documentation

**Description:**
Update CLAUDE.md and other docs for Meta API.

**User AC:**
- Documentation current

**Tech AC:**
- CLAUDE.md updated
- API docs updated
- Migration doc archived

**Estimated Hours:** 1

**Priority:** Medium

**Classification:** Recommended

**Dependencies:** Remove Twilio Dependencies
