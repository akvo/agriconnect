# Ticket Auto-Close (Stale Escalations)

Escalated tickets that no officer responds to are closed automatically so
farmers are not left waiting indefinitely (issue #199).

## Behaviour

A Celery beat task, `tasks.ticket_tasks.auto_close_stale_tickets`, runs daily
at **20:00 EAT (17:00 UTC)**. It closes every ticket that:

- is still open (`resolved_at IS NULL`),
- was created more than `stale_hours` ago (default 24), and
- has **no officer reply**, i.e. no message with `from_source = USER` for
  that customer since the ticket was created.

Tickets with any officer reply are never auto-closed. Because the job runs
once a day, a ticket may stay open up to ~`stale_hours + 24` hours.

Auto-closed tickets keep `resolved_by = NULL`, which distinguishes them from
tickets resolved by an officer.

## Farmer notification

Each affected farmer receives one message (even with several stale tickets):

> Your escalation could not be resolved because no Extension Officer was
> available. You can continue asking questions in this chat.

WhatsApp only allows free-form messages within 24 hours of the farmer's last
message, so the message is sent as:

1. the `ticket_auto_close` Twilio template, if configured (`{{1}}` = officer
   label);
2. otherwise free text from `templates/whatsapp_messages.json`
   (`ticket_auto_closed`), only if the farmer messaged within the last 24h;
3. otherwise not sent (logged). The ticket is still closed.

## Configuration (`config.json`)

```json
{
  "officer_label": { "en": "Extension Officer", "sw": "Afisa Ugani" },
  "ticket_auto_close": { "enabled": true, "stale_hours": 24 },
  "whatsapp": {
    "templates": {
      "ticket_auto_close": { "sid": "", "sid_sw": "" }
    }
  }
}
```

- `officer_label` is the role name of the human responder. Change it for other
  sectors (e.g. `"Health Worker"`). It is also used in the `ticket_closed`
  message sent when an officer resolves a ticket.
- Set `ticket_auto_close.enabled` to `false` to pause the job.
- Restart the backend and Celery services after changing `config.json`.

## Notes

- The dashboard is not pushed a `ticket_resolved` WebSocket event, because
  Socket.IO connections live in the backend process, not the Celery worker.
  Auto-closed tickets appear as resolved on the next reload.
