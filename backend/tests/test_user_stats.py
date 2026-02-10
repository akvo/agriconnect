"""Test cases for the User Stats API endpoint.

This file contains tests for the /api/user/stats endpoint that returns
user statistics: farmers_reached, conversations_resolved, messages_sent.
"""

from datetime import datetime, timezone, timedelta
import pytest

from models.customer import Customer
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.administrative import Administrative
from seeder.administrative import seed_administrative_data


@pytest.fixture
def administrative_data(db_session):
    """Seed administrative data for tests."""
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
    ]
    seed_administrative_data(db_session, rows)

    ward = (
        db_session.query(Administrative).filter_by(code="MWZ-KWM-NGU").first()
    )
    return {"ward": ward}


class TestUserStats:
    def test_get_user_stats_requires_auth(self, client):
        """Test that the endpoint requires authentication."""
        response = client.get("/api/user/stats")
        assert response.status_code == 403, (
            "Should return 403 for unauthenticated requests"
        )

    def test_get_user_stats_empty(
        self, client, auth_headers_factory, db_session
    ):
        """Test stats endpoint returns zeros when user has no activity."""
        eo_headers, eo_user = auth_headers_factory(user_type="eo")

        response = client.get("/api/user/stats", headers=eo_headers)
        assert response.status_code == 200

        data = response.json()

        # Verify response structure
        assert "farmers_reached" in data
        assert "conversations_resolved" in data
        assert "messages_sent" in data

        # Verify each metric has all time periods
        for metric in ["farmers_reached", "conversations_resolved",
                       "messages_sent"]:
            assert "this_week" in data[metric]
            assert "this_month" in data[metric]
            assert "all_time" in data[metric]

        # All values should be 0 for a new user
        assert data["farmers_reached"]["all_time"] == 0
        assert data["conversations_resolved"]["all_time"] == 0
        assert data["messages_sent"]["all_time"] == 0

    def test_get_user_stats_with_data(
        self, client, auth_headers_factory, db_session, administrative_data
    ):
        """Test stats endpoint returns correct counts."""
        eo_headers, eo_user = auth_headers_factory(user_type="eo")

        # Create customers
        c1 = Customer(phone_number="+255100000001", full_name="Farmer A")
        c2 = Customer(phone_number="+255100000002", full_name="Farmer B")
        c3 = Customer(phone_number="+255100000003", full_name="Farmer C")
        db_session.add_all([c1, c2, c3])
        db_session.commit()

        now = datetime.now(timezone.utc)

        # Create messages sent by the EO to different customers
        # Messages to c1 (should count as 1 unique farmer)
        m1 = Message(
            message_sid="STAT1",
            customer_id=c1.id,
            user_id=eo_user.id,
            body="Hello farmer 1",
            from_source=MessageFrom.USER,
            created_at=now,
        )
        m2 = Message(
            message_sid="STAT2",
            customer_id=c1.id,
            user_id=eo_user.id,
            body="Another message to farmer 1",
            from_source=MessageFrom.USER,
            created_at=now,
        )
        # Message to c2 (counts as another unique farmer)
        m3 = Message(
            message_sid="STAT3",
            customer_id=c2.id,
            user_id=eo_user.id,
            body="Hello farmer 2",
            from_source=MessageFrom.USER,
            created_at=now,
        )
        db_session.add_all([m1, m2, m3])
        db_session.commit()

        # Create tickets and resolve them
        # Need customer messages for tickets
        cm1 = Message(
            message_sid="CSTAT1",
            customer_id=c1.id,
            body="Help needed",
            from_source=MessageFrom.CUSTOMER,
        )
        cm2 = Message(
            message_sid="CSTAT2",
            customer_id=c2.id,
            body="Question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add_all([cm1, cm2])
        db_session.commit()

        t1 = Ticket(
            ticket_number="STAT001",
            administrative_id=administrative_data["ward"].id,
            customer_id=c1.id,
            message_id=cm1.id,
            resolved_at=now,
            resolved_by=eo_user.id,
        )
        t2 = Ticket(
            ticket_number="STAT002",
            administrative_id=administrative_data["ward"].id,
            customer_id=c2.id,
            message_id=cm2.id,
            resolved_at=now,
            resolved_by=eo_user.id,
        )
        db_session.add_all([t1, t2])
        db_session.commit()

        # Get stats
        response = client.get("/api/user/stats", headers=eo_headers)
        assert response.status_code == 200

        data = response.json()

        # Verify farmers reached (2 unique customers)
        assert data["farmers_reached"]["all_time"] == 2, (
            "Should have reached 2 unique farmers"
        )

        # Verify conversations resolved (2 tickets)
        assert data["conversations_resolved"]["all_time"] == 2, (
            "Should have resolved 2 conversations"
        )

        # Verify messages sent (3 total)
        assert data["messages_sent"]["all_time"] == 3, (
            "Should have sent 3 messages"
        )

    def test_get_user_stats_time_periods(
        self, client, auth_headers_factory, db_session, administrative_data
    ):
        """Test stats correctly filter by time periods."""
        eo_headers, eo_user = auth_headers_factory(user_type="eo")

        # Create customers
        c1 = Customer(phone_number="+255200000001", full_name="Time Farmer A")
        c2 = Customer(phone_number="+255200000002", full_name="Time Farmer B")
        db_session.add_all([c1, c2])
        db_session.commit()

        now = datetime.now(timezone.utc)
        # Calculate time boundaries
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        month_start = now.replace(day=1, hour=0, minute=0, second=0)

        # Message from this week
        m_week = Message(
            message_sid="TWEEK1",
            customer_id=c1.id,
            user_id=eo_user.id,
            body="This week message",
            from_source=MessageFrom.USER,
            created_at=now,
        )
        # Message from last month (before this month started)
        m_old = Message(
            message_sid="TOLD1",
            customer_id=c2.id,
            user_id=eo_user.id,
            body="Old message",
            from_source=MessageFrom.USER,
            created_at=month_start - timedelta(days=35),
        )
        db_session.add_all([m_week, m_old])
        db_session.commit()

        # Create and resolve tickets
        cm1 = Message(
            message_sid="TCM1",
            customer_id=c1.id,
            body="Help",
            from_source=MessageFrom.CUSTOMER,
        )
        cm2 = Message(
            message_sid="TCM2",
            customer_id=c2.id,
            body="Question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add_all([cm1, cm2])
        db_session.commit()

        t_week = Ticket(
            ticket_number="TWEEK001",
            administrative_id=administrative_data["ward"].id,
            customer_id=c1.id,
            message_id=cm1.id,
            resolved_at=now,
            resolved_by=eo_user.id,
        )
        t_old = Ticket(
            ticket_number="TOLD001",
            administrative_id=administrative_data["ward"].id,
            customer_id=c2.id,
            message_id=cm2.id,
            resolved_at=month_start - timedelta(days=35),
            resolved_by=eo_user.id,
        )
        db_session.add_all([t_week, t_old])
        db_session.commit()

        # Get stats
        response = client.get("/api/user/stats", headers=eo_headers)
        assert response.status_code == 200

        data = response.json()

        # This week should have 1 farmer, 1 resolved, 1 message
        assert data["farmers_reached"]["this_week"] == 1
        assert data["conversations_resolved"]["this_week"] == 1
        assert data["messages_sent"]["this_week"] == 1

        # This month should have 1 farmer, 1 resolved, 1 message
        # (old data is from before this month)
        assert data["farmers_reached"]["this_month"] == 1
        assert data["conversations_resolved"]["this_month"] == 1
        assert data["messages_sent"]["this_month"] == 1

        # All time should have 2 farmers, 2 resolved, 2 messages
        assert data["farmers_reached"]["all_time"] == 2
        assert data["conversations_resolved"]["all_time"] == 2
        assert data["messages_sent"]["all_time"] == 2

    def test_get_user_stats_only_counts_own_activity(
        self, client, auth_headers_factory, db_session, administrative_data
    ):
        """Test that stats only count the current user's activity."""
        eo1_headers, eo1_user = auth_headers_factory(
            user_type="eo",
            email="eo1@stats.test",
            phone_number="+10000000010",
        )
        eo2_headers, eo2_user = auth_headers_factory(
            user_type="eo",
            email="eo2@stats.test",
            phone_number="+10000000011",
        )

        # Create customer
        c1 = Customer(phone_number="+255300000001", full_name="Shared Farmer")
        db_session.add(c1)
        db_session.commit()

        now = datetime.now(timezone.utc)

        # EO1 sends 2 messages
        m1 = Message(
            message_sid="EO1M1",
            customer_id=c1.id,
            user_id=eo1_user.id,
            body="EO1 message 1",
            from_source=MessageFrom.USER,
            created_at=now,
        )
        m2 = Message(
            message_sid="EO1M2",
            customer_id=c1.id,
            user_id=eo1_user.id,
            body="EO1 message 2",
            from_source=MessageFrom.USER,
            created_at=now,
        )
        # EO2 sends 1 message
        m3 = Message(
            message_sid="EO2M1",
            customer_id=c1.id,
            user_id=eo2_user.id,
            body="EO2 message 1",
            from_source=MessageFrom.USER,
            created_at=now,
        )
        db_session.add_all([m1, m2, m3])
        db_session.commit()

        # Create tickets - EO1 resolves 1, EO2 resolves 1
        cm1 = Message(
            message_sid="SCM1",
            customer_id=c1.id,
            body="Help 1",
            from_source=MessageFrom.CUSTOMER,
        )
        cm2 = Message(
            message_sid="SCM2",
            customer_id=c1.id,
            body="Help 2",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add_all([cm1, cm2])
        db_session.commit()

        t1 = Ticket(
            ticket_number="SEO1T1",
            administrative_id=administrative_data["ward"].id,
            customer_id=c1.id,
            message_id=cm1.id,
            resolved_at=now,
            resolved_by=eo1_user.id,
        )
        t2 = Ticket(
            ticket_number="SEO2T1",
            administrative_id=administrative_data["ward"].id,
            customer_id=c1.id,
            message_id=cm2.id,
            resolved_at=now,
            resolved_by=eo2_user.id,
        )
        db_session.add_all([t1, t2])
        db_session.commit()

        # EO1 stats
        eo1_response = client.get("/api/user/stats", headers=eo1_headers)
        assert eo1_response.status_code == 200
        eo1_data = eo1_response.json()

        assert eo1_data["farmers_reached"]["all_time"] == 1, (
            "EO1 should have reached 1 farmer"
        )
        assert eo1_data["conversations_resolved"]["all_time"] == 1, (
            "EO1 should have resolved 1 conversation"
        )
        assert eo1_data["messages_sent"]["all_time"] == 2, (
            "EO1 should have sent 2 messages"
        )

        # EO2 stats
        eo2_response = client.get("/api/user/stats", headers=eo2_headers)
        assert eo2_response.status_code == 200
        eo2_data = eo2_response.json()

        assert eo2_data["farmers_reached"]["all_time"] == 1, (
            "EO2 should have reached 1 farmer"
        )
        assert eo2_data["conversations_resolved"]["all_time"] == 1, (
            "EO2 should have resolved 1 conversation"
        )
        assert eo2_data["messages_sent"]["all_time"] == 1, (
            "EO2 should have sent 1 message"
        )

    def test_get_user_stats_excludes_customer_and_llm_messages(
        self, client, auth_headers_factory, db_session, administrative_data
    ):
        """Test that stats only count USER messages, not CUSTOMER or LLM."""
        eo_headers, eo_user = auth_headers_factory(user_type="eo")

        c1 = Customer(phone_number="+255400000001", full_name="Message Farmer")
        db_session.add(c1)
        db_session.commit()

        now = datetime.now(timezone.utc)

        # User message (should count)
        m_user = Message(
            message_sid="MUSER1",
            customer_id=c1.id,
            user_id=eo_user.id,
            body="EO message",
            from_source=MessageFrom.USER,
            created_at=now,
        )
        # Customer message (should NOT count)
        m_customer = Message(
            message_sid="MCUST1",
            customer_id=c1.id,
            body="Customer message",
            from_source=MessageFrom.CUSTOMER,
            created_at=now,
        )
        # LLM message (should NOT count)
        m_llm = Message(
            message_sid="MLLM1",
            customer_id=c1.id,
            body="LLM response",
            from_source=MessageFrom.LLM,
            created_at=now,
        )
        db_session.add_all([m_user, m_customer, m_llm])
        db_session.commit()

        response = client.get("/api/user/stats", headers=eo_headers)
        assert response.status_code == 200
        data = response.json()

        # Only 1 message should be counted (the USER message)
        assert data["messages_sent"]["all_time"] == 1, (
            "Should only count USER messages, not CUSTOMER or LLM"
        )
        assert data["farmers_reached"]["all_time"] == 1, (
            "Should count farmer reached via USER message"
        )
