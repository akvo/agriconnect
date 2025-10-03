"""Test cases for the Ticket API endpoints.

This file contains integration-style tests that seed minimal DB state using
the `db_session` fixture and exercise the tickets endpoints via the test
client. Each test follows the numbered notes in the original template and
verifies the shape and minimal content of responses.

Endpoints covered:
- GET /api/tickets
- GET /api/tickets/{ticket_id}
- GET /api/tickets/{ticket_id}/messages
- POST /api/tickets
- PATCH /api/tickets/{ticket_id}
"""

from datetime import datetime
import pytest

from models.customer import Customer
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.administrative import Administrative
from seeder.administrative import seed_administrative_data


@pytest.fixture
def administrative_data(db_session):
    """Seed administrative data for tests with multiple wards."""
    rows = [
        {
            "code": "TZ",
            "name": "Tanzania",
            "level": "Country",
            "parent_code": "",
        },
        {
            "code": "MWZ",
            "name": "Mwanza",
            "level": "Region",
            "parent_code": "TZ",
        },
        {
            "code": "MWZ-KWM",
            "name": "Kwimba",
            "level": "District",
            "parent_code": "MWZ",
        },
        {
            "code": "MWZ-KWM-NGU",
            "name": "Ngudu",
            "level": "Ward",
            "parent_code": "MWZ-KWM",
        },
        {
            "code": "MWZ-KWM-BUK",
            "name": "Bukandwe",
            "level": "Ward",
            "parent_code": "MWZ-KWM",
        },
    ]
    seed_administrative_data(db_session, rows)

    # Return dict with both wards for easy access in tests
    ward_ngudu = (
        db_session.query(Administrative).filter_by(code="MWZ-KWM-NGU").first()
    )
    ward_bukandwe = (
        db_session.query(Administrative).filter_by(code="MWZ-KWM-BUK").first()
    )

    return {
        "ward_ngudu": ward_ngudu,
        "ward_bukandwe": ward_bukandwe,
    }


class TestTickets:
    def test_create_ticket(self, client, db_session, administrative_data):
        # 1-2. Create a customer and a message
        customer = Customer(phone_number="+255100000001", full_name="Farmer A")
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        message = Message(
            message_sid="SMTEST1",
            customer_id=customer.id,
            body="Help needed",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # 3-4. Create a ticket and verify response
        payload = {"customer_id": customer.id, "message_id": message.id}
        response = client.post("/api/tickets", json=payload)

        # Verify status code (4)
        assert response.status_code == 201, "Expected 201 Created status"
        data = response.json()

        # Verify response structure (4, 12)
        assert "ticket" in data, "Response should contain 'ticket' key"
        ticket_data = data["ticket"]

        # 6. Ensure ticket is linked to correct customer and message
        assert (
            ticket_data["customer"]["id"] == customer.id
        ), "Customer ID mismatch"
        assert (
            ticket_data["customer"]["name"] == customer.full_name
        ), "Customer name mismatch"
        assert (
            ticket_data["message"]["id"] == message.id
        ), "Message ID mismatch"
        assert (
            ticket_data["message"]["body"] == message.body
        ), "Message body mismatch"

        # 7. Verify ticket number format (timestamp-based)
        assert "ticket_number" in ticket_data, "Ticket number missing"
        assert (
            len(ticket_data["ticket_number"]) == 14
        ), "Ticket number should be 14 digits (YYYYMMDDHHMMSS)"
        assert ticket_data[
            "ticket_number"
        ].isdigit(), "Ticket number should be numeric"

        # 8. Verify administrative_id is set (default to 1)
        assert "id" in ticket_data, "Ticket ID missing"

        # 11. Check timestamps are set
        assert (
            ticket_data["created_at"] is not None
        ), "created_at should be set"
        assert (
            ticket_data["status"] == "open"
        ), "New ticket should have 'open' status"
        assert (
            ticket_data["resolved_at"] is None
        ), "New ticket should not have resolved_at"
        assert (
            ticket_data["resolver"] is None
        ), "New ticket should not have resolver"

        # Verify ticket persisted in DB (6, 8)
        created = (
            db_session.query(Ticket)
            .filter(
                Ticket.message_id == message.id,
                Ticket.customer_id == customer.id,
            )
            .first()
        )
        assert created is not None, "Ticket should be persisted in database"
        assert (
            created.message_id == message.id
        ), "DB ticket message_id mismatch"
        assert (
            created.customer_id == customer.id
        ), "DB ticket customer_id mismatch"
        assert (
            created.administrative_id is not None
        ), "administrative_id should be set"
        assert (
            created.ticket_number == ticket_data["ticket_number"]
        ), "Ticket number mismatch"

        # 9. Test with invalid customer_id
        invalid_customer_payload = {
            "customer_id": 99999,
            "message_id": message.id,
        }
        invalid_customer_response = client.post(
            "/api/tickets", json=invalid_customer_payload
        )
        assert (
            invalid_customer_response.status_code == 404
        ), "Should return 404 for invalid customer_id"
        assert (
            "Customer not found" in invalid_customer_response.json()["detail"]
        )

        # 9. Test with invalid message_id
        invalid_message_payload = {
            "customer_id": customer.id,
            "message_id": 99999,
        }
        invalid_message_response = client.post(
            "/api/tickets", json=invalid_message_payload
        )
        assert (
            invalid_message_response.status_code == 404
        ), "Should return 404 for invalid message_id"
        assert "Message not found" in invalid_message_response.json()["detail"]

        # 10. Test duplicate ticket creation (message already linked)
        duplicate_payload = {
            "customer_id": customer.id,
            "message_id": message.id,
        }
        duplicate_response = client.post(
            "/api/tickets", json=duplicate_payload
        )
        assert (
            duplicate_response.status_code == 400
        ), "Should return 400 for duplicate message_id"
        assert "already linked" in duplicate_response.json()["detail"].lower()

    def test_list_tickets(
        self, client, auth_headers_factory, db_session, administrative_data
    ):
        # 1. Test with both admin and EO authentication
        eo_headers, eo_user = auth_headers_factory(user_type="eo")
        admin_headers, admin_user = auth_headers_factory(user_type="admin")

        # Seed customers, messages, and tickets
        c1 = Customer(phone_number="+255200000001", full_name="Customer One")
        c2 = Customer(phone_number="+255200000002", full_name="Customer Two")
        c3 = Customer(phone_number="+255200000003", full_name="Customer Three")
        db_session.add_all([c1, c2, c3])
        db_session.commit()

        m1 = Message(
            message_sid="LT1",
            customer_id=c1.id,
            body="Message A",
            from_source=MessageFrom.CUSTOMER,
        )
        m2 = Message(
            message_sid="LT2",
            customer_id=c2.id,
            body="Message B",
            from_source=MessageFrom.CUSTOMER,
        )
        m3 = Message(
            message_sid="LT3",
            customer_id=c3.id,
            body="Message C",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add_all([m1, m2, m3])
        db_session.commit()

        # Create EO users for different wards
        eo1_headers, eo1_user = auth_headers_factory(
            user_type="eo",
            email="eo1@example.com",
            phone_number="+10000000003",
            full_name="EO Ward Ngudu",
            administrative_ids=[administrative_data["ward_ngudu"].id],
        )

        eo2_headers, eo2_user = auth_headers_factory(
            user_type="eo",
            email="eo2@example.com",
            phone_number="+10000000004",
            full_name="EO Ward Bukandwe",
            administrative_ids=[administrative_data["ward_bukandwe"].id],
        )

        # Create open tickets in different wards
        t1 = Ticket(
            ticket_number="T001",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=c1.id,
            message_id=m1.id,
            last_message_at=datetime(2025, 1, 3),
        )
        t2 = Ticket(
            ticket_number="T002",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=c2.id,
            message_id=m2.id,
            last_message_at=datetime(2025, 1, 2),
        )
        t3 = Ticket(
            ticket_number="T003",
            administrative_id=administrative_data["ward_bukandwe"].id,
            customer_id=c3.id,
            message_id=m3.id,
            resolved_at=datetime(2025, 1, 1),
            resolved_by=admin_user.id,
            last_message_at=datetime(2025, 1, 1),
        )
        db_session.add_all([t1, t2, t3])
        db_session.commit()

        # 1, 13. Test EO1 can only access tickets in their ward (Ngudu)
        eo1_response = client.get(
            "/api/tickets?status=open&page=1&page_size=10", headers=eo1_headers
        )
        assert (
            eo1_response.status_code == 200
        ), "EO should be able to access tickets"
        eo1_data = eo1_response.json()
        assert (
            eo1_data["total"] == 2
        ), "EO1 should see only 2 tickets from Ngudu ward"
        for ticket in eo1_data["tickets"]:
            # Verify ticket belongs to Ngudu ward
            db_ticket = (
                db_session.query(Ticket)
                .filter(Ticket.id == ticket["id"])
                .first()
            )
            assert (
                db_ticket.administrative_id
                == administrative_data["ward_ngudu"].id
            ), "EO1 should only see Ngudu ward tickets"

        # 13. Test EO2 can only access tickets in their ward (Bukandwe)
        eo2_response = client.get(
            "/api/tickets?status=open&page=1&page_size=10", headers=eo2_headers
        )
        assert (
            eo2_response.status_code == 200
        ), "EO2 should be able to access tickets"
        eo2_data = eo2_response.json()
        assert (
            eo2_data["total"] == 0
        ), "EO2 should see 0 open tickets (only resolved ticket in Bukandwe)"

        # Test EO2 can see resolved tickets in their ward
        eo2_resolved_response = client.get(
            "/api/tickets?status=resolved&page=1&page_size=10",
            headers=eo2_headers,
        )
        assert eo2_resolved_response.status_code == 200
        eo2_resolved_data = eo2_resolved_response.json()
        assert (
            eo2_resolved_data["total"] == 1
        ), "EO2 should see 1 resolved ticket in Bukandwe"

        # 1. Test admin can access tickets from all wards
        response = client.get(
            "/api/tickets?status=open&page=1&page_size=10",
            headers=admin_headers,
        )
        assert (
            response.status_code == 200
        ), "Admin should be able to access tickets"

        # 1. Test admin can access tickets
        response = client.get(
            "/api/tickets?status=open&page=1&page_size=10",
            headers=admin_headers,
        )
        assert (
            response.status_code == 200
        ), "Admin should be able to access tickets"
        payload = response.json()

        # 3, 7. Verify response structure
        assert "tickets" in payload, "Response should contain 'tickets' key"
        assert "total" in payload, "Response should contain 'total' key"
        assert "page" in payload, "Response should contain 'page' key"
        assert "size" in payload, "Response should contain 'size' key"

        # 4, 7. Verify pagination parameters
        assert isinstance(payload["total"], int), "total should be an integer"
        assert payload["page"] == 1, "page should be 1"
        assert payload["size"] == 10, "size should be 10"

        # 2. Test status=open filtering
        assert payload["total"] == 2, "Should have 2 open tickets"
        assert len(payload["tickets"]) == 2, "Should return 2 open tickets"

        # 8, 11. Validate each ticket object and sorting
        tickets = payload["tickets"]
        for i, ticket in enumerate(tickets):
            assert "id" in ticket, "Ticket should have 'id'"
            assert (
                "ticket_number" in ticket
            ), "Ticket should have 'ticket_number'"
            assert "customer" in ticket, "Ticket should have 'customer'"
            assert "id" in ticket["customer"], "Customer should have 'id'"
            assert "name" in ticket["customer"], "Customer should have 'name'"
            assert "message" in ticket, "Ticket should have 'message'"
            assert "id" in ticket["message"], "Message should have 'id'"
            assert "body" in ticket["message"], "Message should have 'body'"
            assert ticket["status"] == "open", "Status should be 'open'"
            assert "created_at" in ticket, "Ticket should have 'created_at'"
            assert (
                ticket["resolved_at"] is None
            ), "Open ticket should not have resolved_at"
            assert (
                ticket["resolver"] is None
            ), "Open ticket should not have resolver"
            assert (
                "last_message_at" in ticket
            ), "Ticket should have 'last_message_at'"

            # 11. Verify descending order by last_message_at
            if i > 0:
                prev_ts = tickets[i - 1]["last_message_at"]
                curr_ts = ticket["last_message_at"]
                assert (
                    prev_ts >= curr_ts
                ), "Tickets should be sorted by last_message_at descending"

        # 2. Test status=resolved filtering
        resolved_response = client.get(
            "/api/tickets?status=resolved&page=1&page_size=10",
            headers=admin_headers,
        )
        assert resolved_response.status_code == 200
        resolved_payload = resolved_response.json()
        assert resolved_payload["total"] == 1, "Should have 1 resolved ticket"
        resolved_ticket = resolved_payload["tickets"][0]
        assert (
            resolved_ticket["status"] == "resolved"
        ), "Status should be 'resolved'"
        assert (
            resolved_ticket["resolved_at"] is not None
        ), "Resolved ticket should have resolved_at"
        assert (
            resolved_ticket["resolver"] is not None
        ), "Resolved ticket should have resolver"
        assert (
            resolved_ticket["resolver"]["id"] == admin_user.id
        ), "Resolver should match admin user"

        # 4, 10. Test different page sizes
        small_page_response = client.get(
            "/api/tickets?status=open&page=1&page_size=1",
            headers=admin_headers,
        )
        assert small_page_response.status_code == 200
        small_page_payload = small_page_response.json()
        assert small_page_payload["size"] == 1, "Page size should be 1"
        assert (
            len(small_page_payload["tickets"]) == 1
        ), "Should return 1 ticket"
        assert small_page_payload["total"] == 2, "Total should still be 2"

        # 6. Test page number exceeding total pages
        beyond_response = client.get(
            "/api/tickets?status=open&page=999&page_size=10",
            headers=admin_headers,
        )
        assert (
            beyond_response.status_code == 200
        ), "Should handle page beyond total"
        beyond_payload = beyond_response.json()
        assert (
            len(beyond_payload["tickets"]) == 0
        ), "Should return empty list for page beyond total"
        assert beyond_payload["total"] == 2, "Total should still be correct"

        # 12. Test empty results (no tickets with specific filter)
        # Clean database and test
        db_session.query(Ticket).delete()
        db_session.commit()
        empty_response = client.get(
            "/api/tickets?status=open&page=1&page_size=10",
            headers=admin_headers,
        )
        assert (
            empty_response.status_code == 200
        ), "Should handle no tickets gracefully"
        empty_payload = empty_response.json()
        assert empty_payload["total"] == 0, "Total should be 0"
        assert (
            len(empty_payload["tickets"]) == 0
        ), "Tickets list should be empty"

    def test_get_ticket_header(
        self, client, auth_headers_factory, db_session, administrative_data
    ):
        # 1. Create auth headers for both admin and EO
        eo_headers, eo_user = auth_headers_factory(user_type="eo")
        admin_headers, admin_user = auth_headers_factory(user_type="admin")

        # Create a ticket record
        customer = Customer(phone_number="+255100000002", full_name="Farmer B")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SMTEST2",
            customer_id=customer.id,
            body="Issue",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message)
        db_session.commit()

        # Create EO users for different wards
        eo1_headers, eo1_user = auth_headers_factory(
            user_type="eo",
            email="eo1@example.com",
            phone_number="+10000000003",
            full_name="EO Ward Ngudu",
            administrative_ids=[administrative_data["ward_ngudu"].id],
        )

        eo2_headers, eo2_user = auth_headers_factory(
            user_type="eo",
            email="eo2@example.com",
            phone_number="+10000000004",
            full_name="EO Ward Bukandwe",
            administrative_ids=[administrative_data["ward_bukandwe"].id],
        )

        # Create tickets in different wards
        ticket_ngudu = Ticket(
            ticket_number="20251101000001",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=customer.id,
            message_id=message.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_ngudu)
        db_session.commit()
        db_session.refresh(ticket_ngudu)

        message_buk = Message(
            message_sid="SMTEST2B",
            customer_id=customer.id,
            body="Issue in Bukandwe",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message_buk)
        db_session.commit()

        ticket_bukandwe = Ticket(
            ticket_number="20251101000002",
            administrative_id=administrative_data["ward_bukandwe"].id,
            customer_id=customer.id,
            message_id=message_buk.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_bukandwe)
        db_session.commit()
        db_session.refresh(ticket_bukandwe)

        # 1, 8. Test EO1 can access ticket in their ward (Ngudu)
        eo1_response = client.get(
            f"/api/tickets/{ticket_ngudu.id}", headers=eo1_headers
        )
        assert (
            eo1_response.status_code == 200
        ), "EO1 should be able to access ticket in their ward"

        # 8. Test EO1 cannot access ticket outside their ward (Bukandwe)
        eo1_forbidden_response = client.get(
            f"/api/tickets/{ticket_bukandwe.id}", headers=eo1_headers
        )
        assert (
            eo1_forbidden_response.status_code == 403
        ), "EO1 should not be able to access ticket outside their ward"
        assert (
            "administrative area"
            in eo1_forbidden_response.json()["detail"].lower()
        ), "Error should mention administrative area"

        # 1. Test admin can access tickets from both wards
        response_ngudu = client.get(
            f"/api/tickets/{ticket_ngudu.id}", headers=admin_headers
        )
        assert (
            response_ngudu.status_code == 200
        ), "Admin should be able to access Ngudu ticket"

        response_bukandwe = client.get(
            f"/api/tickets/{ticket_bukandwe.id}", headers=admin_headers
        )
        assert (
            response_bukandwe.status_code == 200
        ), "Admin should be able to access Bukandwe ticket"

        # Use ticket_ngudu for remaining validation tests
        response = client.get(
            f"/api/tickets/{ticket_ngudu.id}", headers=admin_headers
        )
        data = response.json()

        # 2, 6. Verify response structure
        assert "ticket" in data, "Response should contain 'ticket' key"
        t = data["ticket"]

        # 3, 6. Validate returned header shape and content
        assert "id" in t, "Ticket should have 'id'"
        assert t["id"] == ticket_ngudu.id, "Ticket ID should match"
        assert "ticket_number" in t, "Ticket should have 'ticket_number'"
        assert (
            t["ticket_number"] == ticket_ngudu.ticket_number
        ), "Ticket number should match"

        # 5, 6. Check customer details
        assert "customer" in t, "Ticket should have 'customer'"
        assert t["customer"]["id"] == customer.id, "Customer ID should match"
        assert (
            t["customer"]["name"] == customer.full_name
        ), "Customer name should match"

        # 5, 6. Check message details
        assert "message" in t, "Ticket should have 'message'"
        assert t["message"]["id"] == message.id, "Message ID should match"
        assert (
            t["message"]["body"] == message.body
        ), "Message body should match"

        # 6, 7. Check status and timestamps for open ticket
        assert "status" in t, "Ticket should have 'status'"
        assert (
            t["status"] == "open"
        ), "Status should be 'open' (no resolved_at)"
        assert "created_at" in t, "Ticket should have 'created_at'"
        assert t["created_at"] is not None, "created_at should be set"
        assert (
            t["resolved_at"] is None
        ), "Open ticket should not have resolved_at"
        assert t["resolver"] is None, "Open ticket should not have resolver"
        assert "last_message_at" in t, "Ticket should have 'last_message_at'"

        # Test with resolved ticket (7)
        message_resolved = Message(
            message_sid="SMTEST2C",
            customer_id=customer.id,
            body="Resolved issue",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message_resolved)
        db_session.commit()

        resolved_ticket = Ticket(
            ticket_number="20251101000003",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=customer.id,
            message_id=message_resolved.id,
            resolved_at=datetime.utcnow(),
            resolved_by=admin_user.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(resolved_ticket)
        db_session.commit()
        db_session.refresh(resolved_ticket)

        resolved_response = client.get(
            f"/api/tickets/{resolved_ticket.id}", headers=admin_headers
        )
        assert resolved_response.status_code == 200
        resolved_data = resolved_response.json()["ticket"]
        assert (
            resolved_data["status"] == "resolved"
        ), "Status should be 'resolved' when resolved_at is set"
        assert (
            resolved_data["resolved_at"] is not None
        ), "Resolved ticket should have resolved_at"
        assert (
            resolved_data["resolver"] is not None
        ), "Resolved ticket should have resolver"
        assert (
            resolved_data["resolver"]["id"] == admin_user.id
        ), "Resolver ID should match"
        assert (
            resolved_data["resolver"]["name"] == admin_user.full_name
        ), "Resolver name should match"

        # 4, 10. Invalid ticket id returns 404
        not_found = client.get("/api/tickets/999999", headers=admin_headers)
        assert (
            not_found.status_code == 404
        ), "Should return 404 for invalid ticket ID"
        assert (
            "not found" in not_found.json()["detail"].lower()
        ), "Error message should indicate ticket not found"

        # 9. Test unauthorized access (no auth header)
        unauth_response = client.get(f"/api/tickets/{ticket_ngudu.id}")
        assert (
            unauth_response.status_code == 403
        ), "Should return 403 for unauthorized access"

    def test_get_ticket_conversation(
        self, client, auth_headers_factory, db_session, administrative_data
    ):
        # 1. Create auth headers for both admin and EO
        admin_headers, admin_user = auth_headers_factory(user_type="admin")

        # Seed a ticket and messages
        customer = Customer(phone_number="+255100000003", full_name="Farmer C")
        db_session.add(customer)
        db_session.commit()

        # Create EO users for different wards
        eo1_headers, eo1_user = auth_headers_factory(
            user_type="eo",
            email="eo1@example.com",
            phone_number="+10000000005",
            full_name="EO Ward Ngudu Conv",
            administrative_ids=[administrative_data["ward_ngudu"].id],
        )

        eo2_headers, eo2_user = auth_headers_factory(
            user_type="eo",
            email="eo2@example.com",
            phone_number="+10000000006",
            full_name="EO Ward Bukandwe Conv",
            administrative_ids=[administrative_data["ward_bukandwe"].id],
        )

        # Create messages with different timestamps for testing ordering
        msg_base = Message(
            message_sid="SMTEST3",
            customer_id=customer.id,
            body="Question",
            from_source=MessageFrom.CUSTOMER,
            created_at=datetime(2025, 1, 1, 10, 0, 0),
        )
        db_session.add(msg_base)
        db_session.commit()

        # Create ticket in Ngudu ward
        ticket_ngudu = Ticket(
            ticket_number="20251101000002",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=customer.id,
            message_id=msg_base.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_ngudu)
        db_session.commit()
        db_session.refresh(ticket_ngudu)

        # Create additional messages for conversation
        msg1 = Message(
            message_sid="C1",
            customer_id=customer.id,
            body="First message",
            from_source=MessageFrom.CUSTOMER,
            created_at=datetime(2025, 1, 1, 11, 0, 0),
        )
        msg2 = Message(
            message_sid="C2",
            customer_id=customer.id,
            body="Second message",
            from_source=MessageFrom.USER,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        )
        msg3 = Message(
            message_sid="C3",
            customer_id=customer.id,
            body="Third message",
            from_source=MessageFrom.CUSTOMER,
            created_at=datetime(2025, 1, 1, 13, 0, 0),
        )
        db_session.add_all([msg1, msg2, msg3])
        db_session.commit()

        # Create ticket in Bukandwe ward for testing EO restrictions
        msg_buk = Message(
            message_sid="SMTEST3B",
            customer_id=customer.id,
            body="Question in Bukandwe",
            from_source=MessageFrom.CUSTOMER,
            created_at=datetime(2025, 1, 1, 10, 0, 0),
        )
        db_session.add(msg_buk)
        db_session.commit()

        ticket_bukandwe = Ticket(
            ticket_number="20251101000003",
            administrative_id=administrative_data["ward_bukandwe"].id,
            customer_id=customer.id,
            message_id=msg_buk.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_bukandwe)
        db_session.commit()
        db_session.refresh(ticket_bukandwe)

        # 12. Test EO1 can access conversation in their ward (Ngudu)
        eo1_response = client.get(
            f"/api/tickets/{ticket_ngudu.id}/messages?limit=10",
            headers=eo1_headers,
        )
        assert (
            eo1_response.status_code == 200
        ), "EO1 should be able to access conversation in their ward"

        # 12. Test EO1 cannot access conversation outside their ward
        eo1_forbidden_response = client.get(
            f"/api/tickets/{ticket_bukandwe.id}/messages?limit=10",
            headers=eo1_headers,
        )
        assert (
            eo1_forbidden_response.status_code == 403
        ), "EO1 should not access conversation outside their ward"
        assert (
            "administrative area"
            in eo1_forbidden_response.json()["detail"].lower()
        ), "Error should mention administrative area"

        # 1. Test admin can access conversation
        response = client.get(
            f"/api/tickets/{ticket_ngudu.id}/messages?before_ts=&limit=10",
            headers=admin_headers,
        )
        assert (
            response.status_code == 200
        ), "Admin should be able to access ticket conversation"
        payload = response.json()

        # 2, 6. Verify response structure
        assert "messages" in payload, "Response should contain 'messages' key"
        assert "total" in payload, "Response should contain 'total'"
        assert "before_ts" in payload, "Response should contain 'before_ts'"
        assert "limit" in payload, "Response should contain 'limit'"
        assert payload["limit"] == 10, "Limit should match requested value"

        # 9. Validate each message object
        messages = payload["messages"]
        # Note: API returns ALL messages for the customer,
        # not just for this ticket
        # So we expect: msg_base + msg1 + msg2 + msg3 + msg_buk = 5 messages
        assert (
            len(messages) >= 4
        ), "Should return at least 4 messages for this customer"

        for i, m in enumerate(messages):
            assert "id" in m, "Message should have 'id'"
            assert "message_sid" in m, "Message should have 'message_sid'"
            assert "body" in m, "Message should have 'body'"
            assert "from_source" in m, "Message should have 'from_source'"
            assert "message_type" in m, "Message should have 'message_type'"
            assert "created_at" in m, "Message should have 'created_at'"

            # 7. Verify descending order by created_at
            if i > 0:
                prev_ts = messages[i - 1]["created_at"]
                curr_ts = m["created_at"]
                assert (
                    prev_ts >= curr_ts
                ), "Messages should be sorted by created_at descending"

        # 5, 10. Test with different limit values
        limited_response = client.get(
            f"/api/tickets/{ticket_ngudu.id}/messages?limit=2",
            headers=admin_headers,
        )
        assert limited_response.status_code == 200
        limited_payload = limited_response.json()
        assert (
            len(limited_payload["messages"]) == 2
        ), "Should return only 2 messages with limit=2"
        assert limited_payload["limit"] == 2, "Limit should be 2"

        # 5, 8. Test with before_ts parameter
        middle_ts = datetime(2025, 1, 1, 12, 30, 0).isoformat()
        before_response = client.get(
            f"/api/tickets/{ticket_ngudu.id}/messages?"
            f"before_ts={middle_ts}&limit=10",
            headers=admin_headers,
        )
        assert before_response.status_code == 200
        before_payload = before_response.json()
        # Should return messages before 12:30
        # (msg2 at 12:00, msg1 at 11:00, msg_base + msg_buk at 10:00)
        assert (
            len(before_payload["messages"]) >= 3
        ), "Should return at least 3 messages before specified timestamp"
        for msg in before_payload["messages"]:
            assert (
                msg["created_at"] < middle_ts
            ), "All messages should be before specified timestamp"

        # 8. Test with before_ts earlier than all messages
        early_ts = datetime(2025, 1, 1, 9, 0, 0).isoformat()
        early_response = client.get(
            f"/api/tickets/{ticket_ngudu.id}/messages?"
            f"before_ts={early_ts}&limit=10",
            headers=admin_headers,
        )
        assert early_response.status_code == 200
        early_payload = early_response.json()
        assert (
            len(early_payload["messages"]) == 0
        ), "Should return no messages when before_ts is earlier than all"

        # 4, 11. Invalid ticket ID returns 404
        not_found = client.get(
            "/api/tickets/99999/messages?limit=10", headers=admin_headers
        )
        assert (
            not_found.status_code == 404
        ), "Should return 404 for invalid ticket ID"
        assert (
            "not found" in not_found.json()["detail"].lower()
        ), "Error message should indicate ticket not found"

        # 13. Test unauthorized access (no auth header)
        unauth_response = client.get(
            f"/api/tickets/{ticket_ngudu.id}/messages?limit=10"
        )
        assert (
            unauth_response.status_code == 403
        ), "Should return 403 for unauthorized access"

    def test_mark_ticket_resolved(
        self, client, auth_headers_factory, db_session, administrative_data
    ):
        # 1. Create auth headers for both admin and EO
        admin_headers, admin_user = auth_headers_factory(user_type="admin")

        # Seed tickets for testing
        customer = Customer(phone_number="+255100000004", full_name="Farmer D")
        db_session.add(customer)
        db_session.commit()

        # Create EO users for different wards
        eo1_headers, eo1_user = auth_headers_factory(
            user_type="eo",
            email="eo1@example.com",
            phone_number="+10000000007",
            full_name="EO Ward Ngudu Resolve",
            administrative_ids=[administrative_data["ward_ngudu"].id],
        )

        eo2_headers, eo2_user = auth_headers_factory(
            user_type="eo",
            email="eo2@example.com",
            phone_number="+10000000008",
            full_name="EO Ward Bukandwe Resolve",
            administrative_ids=[administrative_data["ward_bukandwe"].id],
        )

        message = Message(
            message_sid="SMTEST4",
            customer_id=customer.id,
            body="Resolve me",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message)
        db_session.commit()

        # Create ticket in Ngudu ward
        ticket_ngudu = Ticket(
            ticket_number="20251101000003",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=customer.id,
            message_id=message.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_ngudu)
        db_session.commit()
        db_session.refresh(ticket_ngudu)

        # Create ticket in Bukandwe ward for testing EO restrictions
        message_buk = Message(
            message_sid="SMTEST4B",
            customer_id=customer.id,
            body="Resolve me Bukandwe",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message_buk)
        db_session.commit()

        ticket_bukandwe = Ticket(
            ticket_number="20251101000004",
            administrative_id=administrative_data["ward_bukandwe"].id,
            customer_id=customer.id,
            message_id=message_buk.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_bukandwe)
        db_session.commit()
        db_session.refresh(ticket_bukandwe)

        # 10. Prepare payload with valid resolved_at timestamp
        resolved_timestamp = datetime.utcnow()
        payload = {"resolved_at": resolved_timestamp.isoformat()}

        # 12. Test EO1 can resolve ticket in their ward (Ngudu)
        eo1_response = client.patch(
            f"/api/tickets/{ticket_ngudu.id}",
            json=payload,
            headers=eo1_headers,
        )
        assert (
            eo1_response.status_code == 200
        ), "EO1 should be able to resolve ticket in their ward"

        # 12. Test EO1 cannot resolve ticket outside their ward
        eo1_forbidden_response = client.patch(
            f"/api/tickets/{ticket_bukandwe.id}",
            json=payload,
            headers=eo1_headers,
        )
        assert (
            eo1_forbidden_response.status_code == 403
        ), "EO1 should not resolve ticket outside their ward"
        assert (
            "administrative area"
            in eo1_forbidden_response.json()["detail"].lower()
        ), "Error should mention administrative area"

        # Create new ticket for admin tests
        message_admin = Message(
            message_sid="SMTEST4C",
            customer_id=customer.id,
            body="Admin test",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message_admin)
        db_session.commit()

        ticket_admin = Ticket(
            ticket_number="20251101000005",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=customer.id,
            message_id=message_admin.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_admin)
        db_session.commit()
        db_session.refresh(ticket_admin)

        # 13. Unauthorized attempt should be rejected (no auth header)
        unauth = client.patch(f"/api/tickets/{ticket_admin.id}", json=payload)
        assert (
            unauth.status_code == 403
        ), "Should return 403 for unauthorized access"

        # 14. Record before_update timestamp
        before_update = ticket_admin.updated_at

        # 1, 2, 5, 6. Successful resolution with admin user
        response = client.patch(
            f"/api/tickets/{ticket_admin.id}",
            json=payload,
            headers=admin_headers,
        )
        assert (
            response.status_code == 200
        ), "Should successfully resolve ticket"
        data = response.json()

        # 6. Validate response structure
        assert "ticket" in data, "Response should contain 'ticket' key"
        resolved_ticket = data["ticket"]

        # 2, 5. Verify ticket is marked as resolved
        assert (
            resolved_ticket["resolved_at"] is not None
        ), "resolved_at should be set"
        assert resolved_ticket["resolved_at"].startswith(
            payload["resolved_at"][:19]
        ), "resolved_at should match payload (timestamp)"
        assert (
            resolved_ticket["status"] == "resolved"
        ), "Status should be 'resolved'"

        # 9. Verify resolver information
        assert (
            resolved_ticket["resolver"] is not None
        ), "Resolver should be set"
        assert (
            resolved_ticket["resolver"]["id"] == admin_user.id
        ), "Resolver ID should match admin user"
        assert (
            resolved_ticket["resolver"]["name"] == admin_user.full_name
        ), "Resolver name should match"

        # 5, 9, 14. Verify DB was updated
        db_session.refresh(ticket_admin)
        assert (
            ticket_admin.resolved_at is not None
        ), "resolved_at should be set in DB"
        assert (
            ticket_admin.resolved_by == admin_user.id
        ), "resolved_by should be set to admin user ID"
        assert ticket_admin.updated_at is not None, "updated_at should be set"
        if before_update is not None:
            assert (
                ticket_admin.updated_at >= before_update
            ), "updated_at should be updated"

        # 7, 8. Trying to resolve already resolved ticket should fail
        second = client.patch(
            f"/api/tickets/{ticket_admin.id}",
            json=payload,
            headers=admin_headers,
        )
        assert second.status_code in (
            400,
            409,
        ), "Should return 400 or 409 for already resolved ticket"
        assert (
            "already resolved" in second.json()["detail"].lower()
        ), "Error should indicate ticket is already resolved"

        # 11. Invalid timestamp format should return 400
        # (create new ticket for this test)
        message_invalid = Message(
            message_sid="SMTEST4D",
            customer_id=customer.id,
            body="Test invalid timestamp",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message_invalid)
        db_session.commit()

        ticket_invalid = Ticket(
            ticket_number="20251101000010",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=customer.id,
            message_id=message_invalid.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_invalid)
        db_session.commit()
        db_session.refresh(ticket_invalid)

        bad_payload = {"resolved_at": "not-a-valid-timestamp"}
        bad = client.patch(
            f"/api/tickets/{ticket_invalid.id}",
            json=bad_payload,
            headers=admin_headers,
        )
        assert (
            bad.status_code == 400
        ), "Should return 400 for invalid timestamp format"
        assert (
            "invalid" in bad.json()["detail"].lower()
        ), "Error should indicate invalid format"

        # 4. Invalid ticket id returns 404
        nf = client.patch(
            "/api/tickets/999999", json=payload, headers=admin_headers
        )
        assert nf.status_code == 404, "Should return 404 for invalid ticket ID"
        assert (
            "not found" in nf.json()["detail"].lower()
        ), "Error should indicate ticket not found"

        # Test missing resolved_at in payload (create new unresolved ticket)
        message_empty = Message(
            message_sid="SMTEST6",
            customer_id=customer.id,
            body="Test empty payload",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message_empty)
        db_session.commit()

        ticket_empty = Ticket(
            ticket_number="20251101000011",
            administrative_id=administrative_data["ward_ngudu"].id,
            customer_id=customer.id,
            message_id=message_empty.id,
            last_message_at=datetime.utcnow(),
        )
        db_session.add(ticket_empty)
        db_session.commit()
        db_session.refresh(ticket_empty)

        empty_payload = {}
        empty_response = client.patch(
            f"/api/tickets/{ticket_empty.id}",
            json=empty_payload,
            headers=admin_headers,
        )
        assert (
            empty_response.status_code == 400
        ), "Should return 400 when resolved_at is missing"
        assert (
            "required" in empty_response.json()["detail"].lower()
        ), "Error should indicate resolved_at is required"
