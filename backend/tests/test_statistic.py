"""
Test cases for the Statistics API endpoints.

Tests for /api/statistic/* endpoints that provide farmer and EO statistics
for external applications (e.g., Streamlit dashboards).
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest

from models.customer import Customer, CustomerLanguage, OnboardingStatus
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.user import User, UserType
from models.administrative import (
    Administrative,
    CustomerAdministrative,
    UserAdministrative,
)
from models.broadcast import BroadcastMessage
from seeder.administrative import seed_administrative_data


# Test token for statistics API
TEST_STATISTIC_TOKEN = "test-statistic-token-12345"


@pytest.fixture
def statistic_headers():
    """Headers with valid statistic API token."""
    return {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}


@pytest.fixture
def administrative_data(db_session):
    """Seed administrative data for tests."""
    rows = [
        {
            "code": "KEN",
            "name": "Kenya",
            "level": "Country",
            "parent_code": "",
        },
        {
            "code": "KEN-MUR",
            "name": "Murang'a",
            "level": "Region",
            "parent_code": "KEN",
        },
        {
            "code": "KEN-MUR-KIH",
            "name": "Kiharu",
            "level": "District",
            "parent_code": "KEN-MUR",
        },
        {
            "code": "KEN-MUR-KIH-WAN",
            "name": "Wangu",
            "level": "Ward",
            "parent_code": "KEN-MUR-KIH",
        },
        {
            "code": "KEN-MUR-KIH-MUK",
            "name": "Mukangu",
            "level": "Ward",
            "parent_code": "KEN-MUR-KIH",
        },
    ]
    seed_administrative_data(db_session, rows)

    ward1 = (
        db_session.query(Administrative)
        .filter_by(code="KEN-MUR-KIH-WAN")
        .first()
    )
    ward2 = (
        db_session.query(Administrative)
        .filter_by(code="KEN-MUR-KIH-MUK")
        .first()
    )
    district = (
        db_session.query(Administrative)
        .filter_by(code="KEN-MUR-KIH")
        .first()
    )
    return {"ward1": ward1, "ward2": ward2, "district": district}


class TestStatisticAuth:
    """Test authentication for statistics API."""

    def test_requires_auth_token(self, client):
        """Test that endpoints require authentication."""
        response = client.get("/api/statistic/farmers/stats")
        assert response.status_code == 403

    def test_invalid_token_returns_401(self, client):
        """Test that invalid token returns 401."""
        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": "Bearer wrong-token"}
            response = client.get(
                "/api/statistic/farmers/stats", headers=headers
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid API token"

    def test_unconfigured_api_returns_503(self, client):
        """Test that unconfigured API returns 503."""
        with patch("config.settings.statistic_api_token", ""):
            headers = {"Authorization": "Bearer any-token"}
            response = client.get(
                "/api/statistic/farmers/stats", headers=headers
            )
            assert response.status_code == 503
            assert "not configured" in response.json()["detail"]

    def test_valid_token_succeeds(self, client, db_session):
        """Test that valid token allows access."""
        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/stats", headers=headers
            )
            assert response.status_code == 200


class TestFarmerStats:
    """Test farmer statistics endpoint."""

    def test_empty_stats(self, client, db_session):
        """Test stats with no data returns zeros."""
        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/stats", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert "onboarding" in data
            assert "activity" in data
            assert "features" in data
            assert "escalations" in data
            assert "filters" in data

            assert data["onboarding"]["started"] == 0
            assert data["onboarding"]["completed"] == 0
            assert data["escalations"]["total_escalated"] == 0

    def test_onboarding_stats(self, client, db_session, administrative_data):
        """Test onboarding statistics are calculated correctly."""
        # Create customers with different onboarding statuses
        c1 = Customer(
            phone_number="+254700000001",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        c2 = Customer(
            phone_number="+254700000002",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            language=CustomerLanguage.EN,
        )
        c3 = Customer(
            phone_number="+254700000003",
            onboarding_status=OnboardingStatus.NOT_STARTED,
            language=CustomerLanguage.EN,
        )
        c4 = Customer(
            phone_number="+254700000004",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        db_session.add_all([c1, c2, c3, c4])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/stats", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            # Started = NOT_STARTED excluded = 3
            assert data["onboarding"]["started"] == 3
            # Completed = 2
            assert data["onboarding"]["completed"] == 2
            # Completion rate = 2/3 = 0.67
            assert data["onboarding"]["completion_rate"] == 0.67

    def test_activity_stats(self, client, db_session, administrative_data):
        """Test activity statistics are calculated correctly."""
        now = datetime.now(timezone.utc)

        # Create completed customers
        c1 = Customer(
            phone_number="+254700000010",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        c2 = Customer(
            phone_number="+254700000011",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        db_session.add_all([c1, c2])
        db_session.commit()

        # c1 is active (sent message recently)
        m1 = Message(
            message_sid="STAT_ACT_1",
            customer_id=c1.id,
            body="Hello",
            from_source=MessageFrom.CUSTOMER,
            created_at=now - timedelta(days=5),
        )
        db_session.add(m1)
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/stats?active_days=30", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert data["activity"]["active_farmers"] == 1
            assert data["activity"]["dormant_farmers"] == 1
            assert data["activity"]["active_rate"] == 0.5

    def test_weather_subscribers(self, client, db_session):
        """Test weather subscriber count."""
        c1 = Customer(
            phone_number="+254700000020",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
            profile_data={"weather_subscribed": True},
        )
        c2 = Customer(
            phone_number="+254700000021",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
            profile_data={"weather_subscribed": False},
        )
        c3 = Customer(
            phone_number="+254700000022",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        db_session.add_all([c1, c2, c3])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/stats", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert data["features"]["weather_subscribers"] == 1

    def test_escalation_stats(self, client, db_session, administrative_data):
        """Test escalation statistics."""
        c1 = Customer(
            phone_number="+254700000030",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        c2 = Customer(
            phone_number="+254700000031",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        db_session.add_all([c1, c2])
        db_session.commit()

        # Create messages for tickets
        m1 = Message(
            message_sid="STAT_ESC_1",
            customer_id=c1.id,
            body="Help",
            from_source=MessageFrom.CUSTOMER,
        )
        m2 = Message(
            message_sid="STAT_ESC_2",
            customer_id=c1.id,
            body="More help",
            from_source=MessageFrom.CUSTOMER,
        )
        m3 = Message(
            message_sid="STAT_ESC_3",
            customer_id=c2.id,
            body="Question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add_all([m1, m2, m3])
        db_session.commit()

        # Create tickets (escalations)
        t1 = Ticket(
            ticket_number="STAT_T001",
            administrative_id=administrative_data["ward1"].id,
            customer_id=c1.id,
            message_id=m1.id,
        )
        t2 = Ticket(
            ticket_number="STAT_T002",
            administrative_id=administrative_data["ward1"].id,
            customer_id=c1.id,
            message_id=m2.id,
        )
        t3 = Ticket(
            ticket_number="STAT_T003",
            administrative_id=administrative_data["ward1"].id,
            customer_id=c2.id,
            message_id=m3.id,
        )
        db_session.add_all([t1, t2, t3])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/stats", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert data["escalations"]["total_escalated"] == 3
            assert data["escalations"]["farmers_who_escalated"] == 2

    def test_phone_prefix_filter(self, client, db_session):
        """Test filtering by phone prefix."""
        c1 = Customer(
            phone_number="+254700000040",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        c2 = Customer(
            phone_number="+255700000041",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        db_session.add_all([c1, c2])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/stats?phone_prefix=%2B254",
                headers=headers,
            )
            assert response.status_code == 200

            data = response.json()
            assert data["onboarding"]["completed"] == 1
            assert data["filters"]["phone_prefix"] == "+254"


class TestFarmerStatsByWard:
    """Test farmer statistics by ward endpoint."""

    def test_stats_by_ward(self, client, db_session, administrative_data):
        """Test stats grouped by ward."""
        # Create customers in different wards
        c1 = Customer(
            phone_number="+254700000050",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        c2 = Customer(
            phone_number="+254700000051",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        c3 = Customer(
            phone_number="+254700000052",
            onboarding_status=OnboardingStatus.IN_PROGRESS,
            language=CustomerLanguage.EN,
        )
        db_session.add_all([c1, c2, c3])
        db_session.commit()

        # Assign to wards
        ca1 = CustomerAdministrative(
            customer_id=c1.id,
            administrative_id=administrative_data["ward1"].id,
        )
        ca2 = CustomerAdministrative(
            customer_id=c2.id,
            administrative_id=administrative_data["ward2"].id,
        )
        ca3 = CustomerAdministrative(
            customer_id=c3.id,
            administrative_id=administrative_data["ward1"].id,
        )
        db_session.add_all([ca1, ca2, ca3])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/stats/by-ward", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert "data" in data
            assert len(data["data"]) >= 1

            # Find ward1 stats
            ward1_stats = next(
                (
                    w for w in data["data"]
                    if w["ward_id"] == administrative_data["ward1"].id
                ),
                None,
            )
            if ward1_stats:
                assert ward1_stats["registered_farmers"] == 1
                assert ward1_stats["incomplete_registration"] == 1


class TestRegistrationChart:
    """Test registration chart data endpoint."""

    def test_registration_data_by_day(self, client, db_session):
        """Test registration data grouped by day."""
        now = datetime.now(timezone.utc)

        c1 = Customer(
            phone_number="+254700000060",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        c1.created_at = now - timedelta(days=1)

        c2 = Customer(
            phone_number="+254700000061",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        c2.created_at = now

        db_session.add_all([c1, c2])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/farmers/registrations?group_by=day",
                headers=headers,
            )
            assert response.status_code == 200

            data = response.json()
            assert "data" in data
            assert data["total"] == 2
            assert data["filters"]["group_by"] == "day"


class TestEOStats:
    """Test EO statistics endpoint."""

    def test_eo_ticket_stats(self, client, db_session, administrative_data):
        """Test EO ticket statistics."""
        # Create EO user
        eo = User(
            email="eo_stat@test.com",
            phone_number="+254700000070",
            full_name="Test EO",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(eo)
        db_session.commit()

        # Create customer and messages
        c1 = Customer(
            phone_number="+254700000071",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        db_session.add(c1)
        db_session.commit()

        m1 = Message(
            message_sid="STAT_EO_1",
            customer_id=c1.id,
            body="Help",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(m1)
        db_session.commit()

        now = datetime.now(timezone.utc)

        # Create open ticket
        t1 = Ticket(
            ticket_number="STAT_EO_T001",
            administrative_id=administrative_data["ward1"].id,
            customer_id=c1.id,
            message_id=m1.id,
        )
        db_session.add(t1)
        db_session.commit()

        # Create closed ticket
        m2 = Message(
            message_sid="STAT_EO_2",
            customer_id=c1.id,
            body="Another help",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(m2)
        db_session.commit()

        t2 = Ticket(
            ticket_number="STAT_EO_T002",
            administrative_id=administrative_data["ward1"].id,
            customer_id=c1.id,
            message_id=m2.id,
            resolved_at=now,
            resolved_by=eo.id,
        )
        db_session.add(t2)
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/eo/stats", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert data["tickets"]["open"] == 1
            assert data["tickets"]["closed"] == 1

    def test_eo_bulk_messages(self, client, db_session, administrative_data):
        """Test EO bulk message count."""
        eo = User(
            email="eo_bulk@test.com",
            phone_number="+254700000080",
            full_name="Bulk EO",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(eo)
        db_session.commit()

        # Create broadcast messages
        bm1 = BroadcastMessage(
            message="Test broadcast 1",
            created_by=eo.id,
        )
        bm2 = BroadcastMessage(
            message="Test broadcast 2",
            created_by=eo.id,
        )
        db_session.add_all([bm1, bm2])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/eo/stats", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert data["messages"]["bulk_messages_sent"] == 2


class TestEOStatsByEO:
    """Test EO statistics by individual EO endpoint."""

    def test_stats_by_eo(self, client, db_session, administrative_data):
        """Test stats grouped by individual EO."""
        # Create EOs
        eo1 = User(
            email="eo1_stat@test.com",
            phone_number="+254700000090",
            full_name="EO One",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        eo2 = User(
            email="eo2_stat@test.com",
            phone_number="+254700000091",
            full_name="EO Two",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add_all([eo1, eo2])
        db_session.commit()

        # Assign EO1 to district
        ua1 = UserAdministrative(
            user_id=eo1.id,
            administrative_id=administrative_data["district"].id,
        )
        db_session.add(ua1)
        db_session.commit()

        # Create customer
        c1 = Customer(
            phone_number="+254700000092",
            onboarding_status=OnboardingStatus.COMPLETED,
            language=CustomerLanguage.EN,
        )
        db_session.add(c1)
        db_session.commit()

        # EO1 sends messages
        m1 = Message(
            message_sid="STAT_BYEO_1",
            customer_id=c1.id,
            user_id=eo1.id,
            body="Reply from EO1",
            from_source=MessageFrom.USER,
        )
        m2 = Message(
            message_sid="STAT_BYEO_2",
            customer_id=c1.id,
            user_id=eo1.id,
            body="Another reply",
            from_source=MessageFrom.USER,
        )
        db_session.add_all([m1, m2])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/eo/stats/by-eo", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert "data" in data

            # Find EO1 stats
            eo1_stats = next(
                (e for e in data["data"] if e["eo_id"] == eo1.id), None
            )
            if eo1_stats:
                assert eo1_stats["total_replies"] == 2
                assert eo1_stats["eo_name"] == "EO One"


class TestEOCount:
    """Test EO count endpoint."""

    def test_eo_count_total(
        self, client, db_session, administrative_data
    ):
        """Test total EO count without filter."""
        # Create EOs and assign to district
        eo1 = User(
            email="eo_dist1@test.com",
            phone_number="+254700000100",
            full_name="District EO 1",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        eo2 = User(
            email="eo_dist2@test.com",
            phone_number="+254700000101",
            full_name="District EO 2",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add_all([eo1, eo2])
        db_session.commit()

        # Assign to district and ward
        ua1 = UserAdministrative(
            user_id=eo1.id,
            administrative_id=administrative_data["district"].id,
        )
        ua2 = UserAdministrative(
            user_id=eo2.id,
            administrative_id=administrative_data["ward1"].id,
        )
        db_session.add_all([ua1, ua2])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}

            # Test total count (no filter)
            response = client.get(
                "/api/statistic/eo/count", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert "count" in data
            assert data["count"] == 2
            assert data["administrative_id"] is None

    def test_eo_count_by_administrative_id(
        self, client, db_session, administrative_data
    ):
        """Test EO count filtered by administrative_id."""
        # Create EOs
        eo1 = User(
            email="eo_count1@test.com",
            phone_number="+254700000102",
            full_name="Count EO 1",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        eo2 = User(
            email="eo_count2@test.com",
            phone_number="+254700000103",
            full_name="Count EO 2",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add_all([eo1, eo2])
        db_session.commit()

        # Assign EO1 to district, EO2 to ward under district
        ua1 = UserAdministrative(
            user_id=eo1.id,
            administrative_id=administrative_data["district"].id,
        )
        ua2 = UserAdministrative(
            user_id=eo2.id,
            administrative_id=administrative_data["ward1"].id,
        )
        db_session.add_all([ua1, ua2])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}

            # Filter by district - should include both EOs
            district_id = administrative_data["district"].id
            response = client.get(
                f"/api/statistic/eo/count?administrative_id={district_id}",
                headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert data["count"] == 2
            assert data["administrative_id"] == district_id

            # Filter by ward - should include only EO2
            ward_id = administrative_data["ward1"].id
            response = client.get(
                f"/api/statistic/eo/count?administrative_id={ward_id}",
                headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert data["count"] == 1
            assert data["administrative_id"] == ward_id


class TestEOList:
    """Test EO list endpoint."""

    def test_eo_list_sorted_alphabetically(
        self, client, db_session, administrative_data
    ):
        """Test EO list is sorted alphabetically."""
        # Create EOs with names that test sorting
        eo_z = User(
            email="eo_z@test.com",
            phone_number="+254700000110",
            full_name="Zara Officer",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        eo_a = User(
            email="eo_a@test.com",
            phone_number="+254700000111",
            full_name="Alice Officer",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        eo_m = User(
            email="eo_m@test.com",
            phone_number="+254700000112",
            full_name="Mike Officer",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add_all([eo_z, eo_a, eo_m])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/eo/list", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 3

            # Verify alphabetical order
            names = [eo["name"] for eo in data["data"]]
            assert names == sorted(names)
            assert names[0] == "Alice Officer"
            assert names[-1] == "Zara Officer"

    def test_eo_list_excludes_inactive(self, client, db_session):
        """Test that inactive EOs are excluded from list."""
        eo_active = User(
            email="eo_active@test.com",
            phone_number="+254700000120",
            full_name="Active EO",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        eo_inactive = User(
            email="eo_inactive@test.com",
            phone_number="+254700000121",
            full_name="Inactive EO",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=False,
        )
        db_session.add_all([eo_active, eo_inactive])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/eo/list", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            names = [eo["name"] for eo in data["data"]]
            assert "Active EO" in names
            assert "Inactive EO" not in names

    def test_eo_list_excludes_admins(self, client, db_session):
        """Test that admin users are excluded from EO list."""
        eo = User(
            email="eo_only@test.com",
            phone_number="+254700000130",
            full_name="Real EO",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        admin = User(
            email="admin_only@test.com",
            phone_number="+254700000131",
            full_name="Admin User",
            user_type=UserType.ADMIN,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add_all([eo, admin])
        db_session.commit()

        with patch(
            "config.settings.statistic_api_token", TEST_STATISTIC_TOKEN
        ):
            headers = {"Authorization": f"Bearer {TEST_STATISTIC_TOKEN}"}
            response = client.get(
                "/api/statistic/eo/list", headers=headers
            )
            assert response.status_code == 200

            data = response.json()
            names = [eo["name"] for eo in data["data"]]
            assert "Real EO" in names
            assert "Admin User" not in names
