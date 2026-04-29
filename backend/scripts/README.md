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

## Running in Kubernetes

```bash
# Copy script output from pod
kubectl cp <namespace>/<pod-name>:/tmp/output.csv ./output.csv -c backend

# Run script in pod
kubectl exec <pod-name> -n <namespace> -c backend -- \
    python scripts/<script_name>.py -o /tmp/output.csv
```
