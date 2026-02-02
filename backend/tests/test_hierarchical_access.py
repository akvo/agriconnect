"""
Tests for hierarchical administrative access control.

These tests verify that extension officers assigned to upper-level
administrative areas (region, district) can access resources in
subordinate wards.
"""

import pytest

from models import (
    Administrative,
    AdministrativeLevel,
    User,
    UserAdministrative,
    UserType,
)
from models.customer import Customer, CustomerLanguage
from models.administrative import CustomerAdministrative
from models.ticket import Ticket
from models.message import Message, MessageFrom
from models.device import Device
from services.administrative_service import AdministrativeService
from services.socketio_service import get_user_wards


@pytest.fixture
def administrative_hierarchy(db_session):
    """
    Create a complete administrative hierarchy for testing.

    Structure:
    - Country: Kenya (KEN)
      - Region: Nairobi (NAI)
        - District: Central (CEN)
          - Ward: Westlands (WST)
          - Ward: Kilimani (KIL)
        - District: Eastern (EST)
          - Ward: Kasarani (KAS)
      - Region: Coast (CST)
        - District: Mombasa (MBS)
          - Ward: Nyali (NYL)
    """
    # Create administrative levels
    country_level = AdministrativeLevel(name="country")
    region_level = AdministrativeLevel(name="region")
    district_level = AdministrativeLevel(name="district")
    ward_level = AdministrativeLevel(name="ward")
    levels = [country_level, region_level, district_level, ward_level]
    db_session.add_all(levels)
    db_session.commit()

    # Create country
    kenya = Administrative(
        code="KEN",
        name="Kenya",
        level_id=country_level.id,
        parent_id=None,
        path="KEN",
    )
    db_session.add(kenya)
    db_session.commit()

    # Create regions
    nairobi = Administrative(
        code="NAI",
        name="Nairobi Region",
        level_id=region_level.id,
        parent_id=kenya.id,
        path="KEN.NAI",
    )
    coast = Administrative(
        code="CST",
        name="Coast Region",
        level_id=region_level.id,
        parent_id=kenya.id,
        path="KEN.CST",
    )
    db_session.add_all([nairobi, coast])
    db_session.commit()

    # Create districts
    central = Administrative(
        code="CEN",
        name="Central District",
        level_id=district_level.id,
        parent_id=nairobi.id,
        path="KEN.NAI.CEN",
    )
    eastern = Administrative(
        code="EST",
        name="Eastern District",
        level_id=district_level.id,
        parent_id=nairobi.id,
        path="KEN.NAI.EST",
    )
    mombasa = Administrative(
        code="MBS",
        name="Mombasa District",
        level_id=district_level.id,
        parent_id=coast.id,
        path="KEN.CST.MBS",
    )
    db_session.add_all([central, eastern, mombasa])
    db_session.commit()

    # Create wards
    westlands = Administrative(
        code="WST",
        name="Westlands Ward",
        level_id=ward_level.id,
        parent_id=central.id,
        path="KEN.NAI.CEN.WST",
    )
    kilimani = Administrative(
        code="KIL",
        name="Kilimani Ward",
        level_id=ward_level.id,
        parent_id=central.id,
        path="KEN.NAI.CEN.KIL",
    )
    kasarani = Administrative(
        code="KAS",
        name="Kasarani Ward",
        level_id=ward_level.id,
        parent_id=eastern.id,
        path="KEN.NAI.EST.KAS",
    )
    nyali = Administrative(
        code="NYL",
        name="Nyali Ward",
        level_id=ward_level.id,
        parent_id=mombasa.id,
        path="KEN.CST.MBS.NYL",
    )
    db_session.add_all([westlands, kilimani, kasarani, nyali])
    db_session.commit()

    return {
        "country": kenya,
        "regions": {"nairobi": nairobi, "coast": coast},
        "districts": {
            "central": central,
            "eastern": eastern,
            "mombasa": mombasa
        },
        "wards": {
            "westlands": westlands,
            "kilimani": kilimani,
            "kasarani": kasarani,
            "nyali": nyali,
        },
        "levels": {
            "country": country_level,
            "region": region_level,
            "district": district_level,
            "ward": ward_level,
        },
    }


class TestGetDescendantWardIds:
    """Tests for AdministrativeService.get_descendant_ward_ids()"""

    def test_region_returns_all_descendant_wards(
        self, db_session, administrative_hierarchy
    ):
        """Region should return all wards within that region."""
        nairobi = administrative_hierarchy["regions"]["nairobi"]

        ward_ids = AdministrativeService.get_descendant_ward_ids(
            db_session, nairobi.id
        )

        # Nairobi region contains: Westlands, Kilimani, Kasarani
        assert len(ward_ids) == 3

        expected_wards = [
            administrative_hierarchy["wards"]["westlands"].id,
            administrative_hierarchy["wards"]["kilimani"].id,
            administrative_hierarchy["wards"]["kasarani"].id,
        ]
        assert set(ward_ids) == set(expected_wards)

    def test_district_returns_all_descendant_wards(
        self, db_session, administrative_hierarchy
    ):
        """District should return all wards within that district."""
        central = administrative_hierarchy["districts"]["central"]

        ward_ids = AdministrativeService.get_descendant_ward_ids(
            db_session, central.id
        )

        # Central district contains: Westlands, Kilimani
        assert len(ward_ids) == 2

        expected_wards = [
            administrative_hierarchy["wards"]["westlands"].id,
            administrative_hierarchy["wards"]["kilimani"].id,
        ]
        assert set(ward_ids) == set(expected_wards)

    def test_ward_returns_only_itself(
        self, db_session, administrative_hierarchy
    ):
        """Ward should return only itself (no descendants)."""
        westlands = administrative_hierarchy["wards"]["westlands"]

        ward_ids = AdministrativeService.get_descendant_ward_ids(
            db_session, westlands.id
        )

        assert len(ward_ids) == 1
        assert ward_ids[0] == westlands.id

    def test_nonexistent_area_returns_input(self, db_session):
        """Non-existent area should return the input ID."""
        ward_ids = AdministrativeService.get_descendant_ward_ids(
            db_session, 99999
        )

        assert len(ward_ids) == 1
        assert ward_ids[0] == 99999


class TestGetAncestorIds:
    """Tests for AdministrativeService.get_ancestor_ids()"""

    def test_ward_returns_district_and_region(
        self, db_session, administrative_hierarchy
    ):
        """Ward should return district and region (not country)."""
        westlands = administrative_hierarchy["wards"]["westlands"]
        central = administrative_hierarchy["districts"]["central"]
        nairobi = administrative_hierarchy["regions"]["nairobi"]

        ancestor_ids = AdministrativeService.get_ancestor_ids(
            db_session, westlands.id
        )

        # Should include district and region, but NOT country
        assert len(ancestor_ids) == 2
        assert central.id in ancestor_ids
        assert nairobi.id in ancestor_ids
        # Country should NOT be included
        assert administrative_hierarchy["country"].id not in ancestor_ids

    def test_district_returns_only_region(
        self, db_session, administrative_hierarchy
    ):
        """District should return only region (not country)."""
        central = administrative_hierarchy["districts"]["central"]
        nairobi = administrative_hierarchy["regions"]["nairobi"]

        ancestor_ids = AdministrativeService.get_ancestor_ids(
            db_session, central.id
        )

        # Should include only region
        assert len(ancestor_ids) == 1
        assert nairobi.id in ancestor_ids

    def test_region_returns_empty(self, db_session, administrative_hierarchy):
        """Region should return empty (country excluded)."""
        nairobi = administrative_hierarchy["regions"]["nairobi"]

        ancestor_ids = AdministrativeService.get_ancestor_ids(
            db_session, nairobi.id
        )

        # Region's parent is country, which is excluded
        assert len(ancestor_ids) == 0

    def test_nonexistent_area_returns_empty(self, db_session):
        """Non-existent area should return empty list."""
        ancestor_ids = AdministrativeService.get_ancestor_ids(
            db_session, 99999
        )

        assert len(ancestor_ids) == 0


class TestRegionEOTicketAccess:
    """Test that region-level EOs can access ward tickets."""

    def test_region_eo_can_access_ward_ticket(
        self, client, db_session, administrative_hierarchy,
        auth_headers_factory
    ):
        """Region EO can access tickets in subordinate wards."""
        nairobi = administrative_hierarchy["regions"]["nairobi"]
        westlands = administrative_hierarchy["wards"]["westlands"]

        # Create EO assigned to Nairobi region
        auth_headers, eo_user = auth_headers_factory(
            user_type="eo",
            email="region_eo@example.com",
            administrative_ids=[nairobi.id],
        )

        # Create a customer in Westlands ward
        customer = Customer(
            phone_number="+255999000001",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=westlands.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Create a message
        message = Message(
            customer_id=customer.id,
            message_sid="MSG001",
            body="Test message",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message)
        db_session.commit()

        # Create a ticket in Westlands ward
        ticket = Ticket(
            ticket_number="202401010001",
            customer_id=customer.id,
            message_id=message.id,
            administrative_id=westlands.id,
        )
        db_session.add(ticket)
        db_session.commit()

        # Region EO should be able to access this ticket
        url = f"/api/tickets/{ticket.id}"
        response = client.get(url, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["ticket"]["id"] == ticket.id

    def test_region_eo_sees_tickets_from_all_wards(
        self, client, db_session, administrative_hierarchy,
        auth_headers_factory
    ):
        """Region EO sees tickets from all wards in their region."""
        nairobi = administrative_hierarchy["regions"]["nairobi"]
        westlands = administrative_hierarchy["wards"]["westlands"]
        kilimani = administrative_hierarchy["wards"]["kilimani"]
        kasarani = administrative_hierarchy["wards"]["kasarani"]

        # Create EO assigned to Nairobi region
        auth_headers, eo_user = auth_headers_factory(
            user_type="eo",
            email="region_eo2@example.com",
            administrative_ids=[nairobi.id],
        )

        # Create tickets in different wards within Nairobi region
        tickets_data = [
            (westlands, "+255999000010", "WST ticket"),
            (kilimani, "+255999000011", "KIL ticket"),
            (kasarani, "+255999000012", "KAS ticket"),
        ]

        for ward, phone, body in tickets_data:
            customer = Customer(
                phone_number=phone, language=CustomerLanguage.EN
            )
            db_session.add(customer)
            db_session.commit()

            customer_admin = CustomerAdministrative(
                customer_id=customer.id,
                administrative_id=ward.id,
            )
            db_session.add(customer_admin)

            message = Message(
                customer_id=customer.id,
                message_sid=f"MSG_{phone}",
                body=body,
                from_source=MessageFrom.CUSTOMER,
            )
            db_session.add(message)
            db_session.commit()

            ticket = Ticket(
                ticket_number=f"2024{phone[-4:]}",
                customer_id=customer.id,
                message_id=message.id,
                administrative_id=ward.id,
            )
            db_session.add(ticket)
            db_session.commit()

        # Region EO should see all 3 tickets
        url = "/api/tickets/?status=open"
        response = client.get(url, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 3


class TestDistrictEOTicketAccess:
    """Test that district-level EOs can access ward tickets."""

    def test_district_eo_can_access_ward_ticket(
        self, client, db_session, administrative_hierarchy,
        auth_headers_factory
    ):
        """District EO can access tickets in subordinate wards."""
        central = administrative_hierarchy["districts"]["central"]
        westlands = administrative_hierarchy["wards"]["westlands"]

        # Create EO assigned to Central district
        auth_headers, eo_user = auth_headers_factory(
            user_type="eo",
            email="district_eo@example.com",
            administrative_ids=[central.id],
        )

        # Create a customer in Westlands ward
        customer = Customer(
            phone_number="+255999000020",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=westlands.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Create a message
        message = Message(
            customer_id=customer.id,
            message_sid="MSG020",
            body="Test message",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message)
        db_session.commit()

        # Create a ticket in Westlands ward
        ticket = Ticket(
            ticket_number="202401010020",
            customer_id=customer.id,
            message_id=message.id,
            administrative_id=westlands.id,
        )
        db_session.add(ticket)
        db_session.commit()

        # District EO should be able to access this ticket
        url = f"/api/tickets/{ticket.id}"
        response = client.get(url, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["ticket"]["id"] == ticket.id

    def test_district_eo_cannot_access_other_district_ticket(
        self, client, db_session, administrative_hierarchy,
        auth_headers_factory
    ):
        """District EO should NOT access other district tickets."""
        central = administrative_hierarchy["districts"]["central"]
        # kasarani is in Eastern district, not Central
        kasarani = administrative_hierarchy["wards"]["kasarani"]

        # Create EO assigned to Central district
        auth_headers, eo_user = auth_headers_factory(
            user_type="eo",
            email="district_eo2@example.com",
            administrative_ids=[central.id],
        )

        # Create a customer in Kasarani ward (Eastern district)
        customer = Customer(
            phone_number="+255999000030",
            language=CustomerLanguage.EN,
        )
        db_session.add(customer)
        db_session.commit()

        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=kasarani.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        # Create a message
        message = Message(
            customer_id=customer.id,
            message_sid="MSG030",
            body="Test message",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message)
        db_session.commit()

        # Create a ticket in Kasarani ward
        ticket = Ticket(
            ticket_number="202401010030",
            customer_id=customer.id,
            message_id=message.id,
            administrative_id=kasarani.id,
        )
        db_session.add(ticket)
        db_session.commit()

        # Central district EO should NOT access this (it's in Eastern)
        url = f"/api/tickets/{ticket.id}"
        response = client.get(url, headers=auth_headers)
        assert response.status_code == 403


class TestSocketIOWardIds:
    """Test that Socket.IO get_user_wards includes descendants."""

    def test_region_eo_ward_ids_include_descendants(
        self, db_session, administrative_hierarchy
    ):
        """Region EO's ward_ids should include all descendant wards."""
        nairobi = administrative_hierarchy["regions"]["nairobi"]

        # Create EO assigned to Nairobi region
        user = User(
            email="socket_region_eo@example.com",
            phone_number="+254700000100",
            hashed_password="hashed",
            full_name="Region EO",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        user_admin = UserAdministrative(
            user_id=user.id,
            administrative_id=nairobi.id,
        )
        db_session.add(user_admin)
        db_session.commit()

        # Get ward IDs for socket events
        ward_ids = get_user_wards(user, db_session)

        # Should include the region itself and all 3 descendant wards
        assert len(ward_ids) == 4  # region + 3 wards
        assert nairobi.id in ward_ids
        wards = administrative_hierarchy["wards"]
        assert wards["westlands"].id in ward_ids
        assert wards["kilimani"].id in ward_ids
        assert wards["kasarani"].id in ward_ids

    def test_admin_returns_empty_ward_ids(
        self, db_session, administrative_hierarchy
    ):
        """Admin should return empty ward_ids (receives all events)."""
        user = User(
            email="socket_admin@example.com",
            phone_number="+254700000101",
            hashed_password="hashed",
            full_name="Admin User",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        ward_ids = get_user_wards(user, db_session)

        # Admin returns empty (handled specially in emit logic)
        assert len(ward_ids) == 0


class TestPushNotificationRouting:
    """Test that push notifications are routed to upper-level EOs."""

    def test_region_eo_device_in_ancestors(
        self, db_session, administrative_hierarchy
    ):
        """
        Test that get_ancestor_ids correctly identifies ancestors
        for push notification routing.
        """
        westlands = administrative_hierarchy["wards"]["westlands"]
        central = administrative_hierarchy["districts"]["central"]
        nairobi = administrative_hierarchy["regions"]["nairobi"]

        # Get ancestors of Westlands ward
        ancestor_ids = AdministrativeService.get_ancestor_ids(
            db_session, westlands.id
        )

        # Should include Central district and Nairobi region
        assert central.id in ancestor_ids
        assert nairobi.id in ancestor_ids

        # Verify a region EO's device would be found via ancestors
        user = User(
            email="push_region_eo@example.com",
            phone_number="+254700000200",
            hashed_password="hashed",
            full_name="Region EO for Push",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # Assign EO to Nairobi region
        user_admin = UserAdministrative(
            user_id=user.id,
            administrative_id=nairobi.id,
        )
        db_session.add(user_admin)
        db_session.commit()

        # Register device for the region EO
        device = Device(
            user_id=user.id,
            administrative_id=nairobi.id,
            push_token="ExponentPushToken[region-eo-token]",
            is_active=True,
        )
        db_session.add(device)
        db_session.commit()

        # Query for users assigned to ancestor areas
        users_in_ancestors = (
            db_session.query(UserAdministrative)
            .filter(UserAdministrative.administrative_id.in_(ancestor_ids))
            .all()
        )

        # The region EO should be found
        user_ids = [ua.user_id for ua in users_in_ancestors]
        assert user.id in user_ids
