"""Tests for auto-closing stale escalations (tasks/ticket_tasks.py).

A ticket is stale when it is still open, older than the configured
threshold and has no officer (MessageFrom.USER) reply since it was created.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from config import settings
from models.customer import Customer
from models.message import Message, MessageFrom
from models.ticket import Ticket
from seeder.administrative import seed_administrative_data
from services.whatsapp_service import WhatsAppService
from tasks.ticket_tasks import auto_close_stale_tickets, close_stale_tickets

os.environ["TESTING"] = "true"

NOW = datetime.now(timezone.utc)
_counter = {"n": 0}


def _uid():
    _counter["n"] += 1
    return _counter["n"]


@pytest.fixture
def ward(db_session):
    seed_administrative_data(
        db_session,
        [
            {"code": "KE", "name": "Kenya", "level": "Country",
             "parent_code": ""},
            {"code": "KE-MU", "name": "Muranga", "level": "Region",
             "parent_code": "KE"},
            {"code": "KE-MU-KI", "name": "Kiharu", "level": "District",
             "parent_code": "KE-MU"},
            {"code": "KE-MU-KI-WA", "name": "Wangu", "level": "Ward",
             "parent_code": "KE-MU-KI"},
        ],
    )
    from models.administrative import Administrative

    return (
        db_session.query(Administrative).filter_by(code="KE-MU-KI-WA").first()
    )


@pytest.fixture
def send_mocks():
    with patch.object(
        WhatsAppService, "send_message", return_value={"sid": "SM1"}
    ) as send_message, patch.object(
        WhatsAppService,
        "send_template_message",
        return_value={"sid": "SM2"},
    ) as send_template:
        yield send_message, send_template


@pytest.fixture
def no_template():
    with patch.object(
        settings, "whatsapp_ticket_auto_close_template_sid", ""
    ), patch.object(
        settings, "whatsapp_ticket_auto_close_template_sid_sw", ""
    ):
        yield


def make_customer(db, language="en"):
    customer = Customer(
        phone_number=f"+2547000{_uid():05d}",
        full_name="Farmer",
        language=language,
    )
    db.add(customer)
    db.commit()
    return customer


def add_message(db, customer, from_source, created_at, user_id=None):
    msg = Message(
        message_sid=f"SMAUTO{_uid()}",
        customer_id=customer.id,
        user_id=user_id,
        body="hello",
        from_source=from_source,
        created_at=created_at,
    )
    db.add(msg)
    db.commit()
    return msg


def make_ticket(db, ward, customer, created_at, resolved_at=None):
    msg = add_message(db, customer, MessageFrom.CUSTOMER, created_at)
    ticket = Ticket(
        ticket_number=f"AUTO{_uid()}",
        administrative_id=ward.id,
        customer_id=customer.id,
        message_id=msg.id,
        created_at=created_at,
        resolved_at=resolved_at,
    )
    db.add(ticket)
    db.commit()
    return ticket


class TestTicketSelection:
    def test_closes_stale_ticket_without_officer_reply(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        ticket = make_ticket(
            db_session, ward, customer, NOW - timedelta(hours=30)
        )

        result = close_stale_tickets(db_session, now=NOW)

        db_session.refresh(ticket)
        assert ticket.resolved_at is not None
        assert ticket.resolved_by is None
        assert result["closed"] == 1

    def test_keeps_ticket_with_officer_reply(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        ticket = make_ticket(
            db_session, ward, customer, NOW - timedelta(hours=30)
        )
        add_message(
            db_session, customer, MessageFrom.USER,
            NOW - timedelta(hours=29),
        )

        result = close_stale_tickets(db_session, now=NOW)

        db_session.refresh(ticket)
        assert ticket.resolved_at is None
        assert result["closed"] == 0

    def test_officer_reply_before_ticket_does_not_count(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        add_message(
            db_session, customer, MessageFrom.USER,
            NOW - timedelta(days=5),
        )
        ticket = make_ticket(
            db_session, ward, customer, NOW - timedelta(hours=30)
        )

        close_stale_tickets(db_session, now=NOW)

        db_session.refresh(ticket)
        assert ticket.resolved_at is not None

    def test_keeps_ticket_younger_than_threshold(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        ticket = make_ticket(
            db_session, ward, customer, NOW - timedelta(hours=23)
        )

        close_stale_tickets(db_session, now=NOW)

        db_session.refresh(ticket)
        assert ticket.resolved_at is None

    def test_threshold_is_configurable(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        ticket = make_ticket(
            db_session, ward, customer, NOW - timedelta(hours=30)
        )

        with patch.object(settings, "ticket_auto_close_stale_hours", 48):
            close_stale_tickets(db_session, now=NOW)

        db_session.refresh(ticket)
        assert ticket.resolved_at is None

    def test_leaves_resolved_ticket_untouched(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        resolved_at = NOW - timedelta(hours=40)
        ticket = make_ticket(
            db_session, ward, customer, NOW - timedelta(hours=50),
            resolved_at=resolved_at,
        )
        send_message, send_template = send_mocks

        close_stale_tickets(db_session, now=NOW)

        db_session.refresh(ticket)
        assert ticket.resolved_at == resolved_at
        send_message.assert_not_called()
        send_template.assert_not_called()


class TestFarmerNotification:
    def test_uses_template_when_configured(self, db_session, ward, send_mocks):
        customer = make_customer(db_session)
        make_ticket(db_session, ward, customer, NOW - timedelta(hours=30))
        send_message, send_template = send_mocks

        with patch.object(
            settings, "whatsapp_ticket_auto_close_template_sid", "HXAUTO"
        ):
            close_stale_tickets(db_session, now=NOW)

        send_template.assert_called_once_with(
            to=customer.phone_number,
            content_sid="HXAUTO",
            content_variables={"1": "Extension Officer"},
        )
        send_message.assert_not_called()

    def test_free_text_inside_24h_window(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        make_ticket(db_session, ward, customer, NOW - timedelta(hours=30))
        add_message(
            db_session, customer, MessageFrom.CUSTOMER,
            NOW - timedelta(hours=2),
        )
        send_message, _ = send_mocks

        close_stale_tickets(db_session, now=NOW)

        send_message.assert_called_once()
        to, body = send_message.call_args.args
        assert to == customer.phone_number
        assert body == (
            "Your escalation could not be resolved because no Extension "
            "Officer was available. You can continue asking questions in "
            "this chat."
        )

    def test_no_message_outside_window_without_template(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        ticket = make_ticket(
            db_session, ward, customer, NOW - timedelta(hours=30)
        )
        send_message, send_template = send_mocks

        result = close_stale_tickets(db_session, now=NOW)

        db_session.refresh(ticket)
        assert ticket.resolved_at is not None
        send_message.assert_not_called()
        send_template.assert_not_called()
        assert result["not_notified"] == 1

    def test_officer_label_is_configurable(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        make_ticket(db_session, ward, customer, NOW - timedelta(hours=30))
        add_message(
            db_session, customer, MessageFrom.CUSTOMER,
            NOW - timedelta(hours=2),
        )
        send_message, _ = send_mocks

        with patch.object(
            settings, "officer_label", {"en": "Health Worker"}
        ):
            close_stale_tickets(db_session, now=NOW)

        _, body = send_message.call_args.args
        assert "no Health Worker was available" in body

    def test_swahili_farmer_gets_swahili_message(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session, language="sw")
        make_ticket(db_session, ward, customer, NOW - timedelta(hours=30))
        add_message(
            db_session, customer, MessageFrom.CUSTOMER,
            NOW - timedelta(hours=2),
        )
        send_message, _ = send_mocks

        with patch.object(
            settings,
            "officer_label",
            {"en": "Extension Officer", "sw": "Afisa Ugani"},
        ):
            close_stale_tickets(db_session, now=NOW)

        _, body = send_message.call_args.args
        assert "Afisa Ugani" in body
        assert "escalation" not in body

    def test_one_message_per_farmer_with_multiple_stale_tickets(
        self, db_session, ward, send_mocks, no_template
    ):
        customer = make_customer(db_session)
        make_ticket(db_session, ward, customer, NOW - timedelta(hours=50))
        make_ticket(db_session, ward, customer, NOW - timedelta(hours=30))
        add_message(
            db_session, customer, MessageFrom.CUSTOMER,
            NOW - timedelta(hours=2),
        )
        send_message, _ = send_mocks

        result = close_stale_tickets(db_session, now=NOW)

        assert result["closed"] == 2
        send_message.assert_called_once()

    def test_send_failure_does_not_stop_other_closures(
        self, db_session, ward, no_template
    ):
        first = make_customer(db_session)
        second = make_customer(db_session)
        t1 = make_ticket(db_session, ward, first, NOW - timedelta(hours=30))
        t2 = make_ticket(db_session, ward, second, NOW - timedelta(hours=30))
        for c in (first, second):
            add_message(
                db_session, c, MessageFrom.CUSTOMER,
                NOW - timedelta(hours=2),
            )

        with patch.object(
            WhatsAppService, "send_message", side_effect=Exception("twilio")
        ):
            result = close_stale_tickets(db_session, now=NOW)

        db_session.refresh(t1)
        db_session.refresh(t2)
        assert t1.resolved_at is not None
        assert t2.resolved_at is not None
        assert result["closed"] == 2
        assert result["not_notified"] == 2


class TestTask:
    def test_disabled_flag_skips_run(self):
        with patch.object(settings, "ticket_auto_close_enabled", False), \
                patch("tasks.ticket_tasks.SessionLocal") as session_local:
            result = auto_close_stale_tickets()

        assert result["status"] == "disabled"
        session_local.assert_not_called()

    def test_scheduled_daily_at_8pm_eat(self):
        from celery_app import celery_app

        entry = celery_app.conf.beat_schedule["auto-close-stale-tickets"]
        assert entry["task"] == "tasks.ticket_tasks.auto_close_stale_tickets"
        # Celery runs in UTC; 20:00 EAT (UTC+3) is 17:00 UTC
        assert entry["schedule"].hour == {17}
        assert entry["schedule"].minute == {0}
