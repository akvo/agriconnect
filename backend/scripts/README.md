# Backend Scripts

Utility scripts for data export and testing.

## Scripts

### export_tickets_to_csv.py

Export escalated tickets to CSV. Supports filtering by status (open, resolved, or all) and includes resolver information for closed tickets.

```bash
# Export open tickets (default)
./dc.sh exec backend python scripts/export_tickets_to_csv.py \
    -o /tmp/tickets.csv

# Export resolved tickets
./dc.sh exec backend python scripts/export_tickets_to_csv.py \
    -o /tmp/tickets.csv --status resolved

# Export all tickets
./dc.sh exec backend python scripts/export_tickets_to_csv.py \
    -o /tmp/tickets.csv --status all
```

### export_conversations.py

Export conversation summaries to CSV. Exports merged farmer questions (before + after FOLLOW_UP messages) with anonymized customer context (farmer_id, ward, crop, gender, age_group).

```bash
# Export with default threshold (5 minutes)
./dc.sh exec backend python scripts/export_conversations.py \
    -o /tmp/conversations.csv

# Export with custom threshold
./dc.sh exec backend python scripts/export_conversations.py \
    -o /tmp/conversations.csv -t 10
```

### whisper.py

Test script for AI callback webhook with WHISPER message type. Sends a mock AI suggestion to an open ticket for testing the escalation flow.

```bash
./dc.sh exec backend python scripts/whisper.py \
    --customer "+254123456789" \
    --status completed \
    --suggestion maize
```

### bulk_whatsapp.py

Send bulk WhatsApp template messages to farmers from a CSV file. Tracks delivery status and supports retries for failed messages.

**Setup:**
1. Create and approve a WhatsApp template in [Twilio Console](https://console.twilio.com)
2. Edit the configuration section at the top of the script:
   - `CSV_PATH` - Path to your CSV file
   - `TEMPLATE_SID` - Your approved template SID (starts with `HX...`)
   - `DRY_RUN` - Set to `False` to actually send messages

**CSV Format:**

| Column | Description |
|--------|-------------|
| `id` | Unique identifier |
| `company` | Cooperative name |
| `name` | Farmer name (optional, for template variable) |
| `phone` | Phone number (required) |
| `status` | Updated by script: `queued`, `sent`, `failed`, `invalid_phone` |
| `retries` | Number of send attempts |
| `last_batch_date` | Timestamp of last attempt |
| `message_sid` | Twilio message SID for tracking |
| `error` | Error message if failed |

```bash
# Edit configuration in the script first, then:

# Dry run (validate phones without sending)
./dc.sh exec backend python scripts/bulk_whatsapp.py

# After setting DRY_RUN = False, send messages
./dc.sh exec backend python scripts/bulk_whatsapp.py

# To retry failed messages, set RETRY_FAILED_ONLY = True
./dc.sh exec backend python scripts/bulk_whatsapp.py
```

## Running in Kubernetes

```bash
# Copy script output from pod
kubectl cp <namespace>/<pod-name>:/tmp/output.csv ./output.csv -c backend

# Run script in pod
kubectl exec <pod-name> -n <namespace> -c backend -- \
    python scripts/<script_name>.py -o /tmp/output.csv
```
