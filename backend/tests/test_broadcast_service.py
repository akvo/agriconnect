"""
Tests for broadcast service.

Tests cover:
- Broadcast group CRUD operations
- Broadcast message creation
- Ward-based access control
- Owner-only updates/deletes
"""
import pytest
from sqlalchemy.orm import Session

from models.broadcast import (
    BroadcastGroup,
)
from models.customer import (
    Customer,
    CustomerLanguage,
)
from models.user import User, UserType
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    UserAdministrative
)
from services.broadcast_service import BroadcastService


@pytest.fixture
def test_administrative(db_session: Session):
    """Create test administrative structure."""
    # Create administrative levels
    district_level = AdministrativeLevel(name="district")
    ward_level = AdministrativeLevel(name="ward")
    db_session.add_all([district_level, ward_level])
    db_session.commit()

    # Create administrative areas
    district = Administrative(
        code="D01",
        name="Test District",
        level_id=district_level.id,
        parent_id=None,
        path="D01"
    )
    db_session.add(district)
    db_session.commit()

    ward1 = Administrative(
        code="W01",
        name="Ward 1",
        level_id=ward_level.id,
        parent_id=district.id,
        path="D01/W01"
    )
    ward2 = Administrative(
        code="W02",
        name="Ward 2",
        level_id=ward_level.id,
        parent_id=district.id,
        path="D01/W02"
    )

    db_session.add_all([ward1, ward2])
    db_session.commit()

    return {"district": district, "ward1": ward1, "ward2": ward2}


@pytest.fixture
def test_users(db_session: Session, test_administrative):
    """Create test EO users."""
    # EO in Ward 1
    eo1 = User(
        email="eo1@test.com",
        phone_number="+255700000001",
        full_name="EO One",
        user_type=UserType.EXTENSION_OFFICER,
        hashed_password="hashed",
        is_active=True,
    )
    db_session.add(eo1)
    db_session.commit()
    db_session.refresh(eo1)

    # Assign to Ward 1
    user_admin1 = UserAdministrative(
        user_id=eo1.id,
        administrative_id=test_administrative["ward1"].id
    )
    db_session.add(user_admin1)

    # EO in Ward 2
    eo2 = User(
        email="eo2@test.com",
        phone_number="+255700000002",
        full_name="EO Two",
        user_type=UserType.EXTENSION_OFFICER,
        hashed_password="hashed",
        is_active=True,
    )
    db_session.add(eo2)
    db_session.commit()
    db_session.refresh(eo2)

    # Assign to Ward 2
    user_admin2 = UserAdministrative(
        user_id=eo2.id,
        administrative_id=test_administrative["ward2"].id
    )
    db_session.add(user_admin2)

    db_session.commit()

    # Add helper to get ward ID for users
    eo1.administrative_id = test_administrative["ward1"].id
    eo2.administrative_id = test_administrative["ward2"].id

    return {"eo1": eo1, "eo2": eo2}


@pytest.fixture
def test_customers(db_session: Session):
    """Create test customers."""
    customers = [
        Customer(
            id=i,
            phone_number=f"+25571234567{i}",
            full_name=f"Customer {i}",
            language=CustomerLanguage.EN,
        )
        for i in range(1, 6)
    ]
    db_session.add_all(customers)
    db_session.commit()

    return customers


class TestBroadcastGroupManagement:
    """Test broadcast group CRUD operations."""

    def test_create_group(
        self, db_session: Session, test_users, test_customers
    ):
        """Test creating a broadcast group."""
        service = BroadcastService(db_session)

        group = service.create_group(
            name="Test Group",
            customer_ids=[1, 2, 3],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
            crop_types=[1, 2],  # Example crop type IDs
            age_groups=["20-35", "36-50"]  # Example age groups
        )

        assert group.id is not None
        assert group.name == "Test Group"
        assert group.crop_types == [1, 2]
        assert group.age_groups == ["20-35", "36-50"]
        assert group.created_by == test_users["eo1"].id
        assert len(group.group_contacts) == 3

    def test_get_groups_for_eo_ward_filtered(
        self, db_session: Session, test_users, test_customers
    ):
        """Test that EOs only see groups in their ward."""
        service = BroadcastService(db_session)

        # EO1 creates a group in Ward 1
        group1 = service.create_group(
            name="Ward 1 Group",
            customer_ids=[1, 2],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # EO2 creates a group in Ward 2
        group2 = service.create_group(
            name="Ward 2 Group",
            customer_ids=[3, 4],
            created_by=test_users["eo2"].id,
            administrative_id=test_users["eo2"].administrative_id,
        )

        # EO1 should only see Ward 1 groups
        eo1_groups = service.get_groups_for_eo(
            eo_id=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        assert len(eo1_groups) == 1
        assert eo1_groups[0].id == group1.id

        # EO2 should only see Ward 2 groups
        eo2_groups = service.get_groups_for_eo(
            eo_id=test_users["eo2"].id,
            administrative_id=test_users["eo2"].administrative_id,
        )
        assert len(eo2_groups) == 1
        assert eo2_groups[0].id == group2.id

    def test_get_group_by_id_access_control(
        self, db_session: Session, test_users, test_customers
    ):
        """Test ward-based access control for group retrieval."""
        service = BroadcastService(db_session)

        # EO1 creates a group
        group = service.create_group(
            name="EO1 Group",
            customer_ids=[1, 2],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # EO1 can retrieve it
        found_group = service.get_group_by_id(
            group_id=group.id,
            eo_id=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        assert found_group is not None
        assert found_group.id == group.id

        # EO2 from different ward cannot retrieve it
        not_found = service.get_group_by_id(
            group_id=group.id,
            eo_id=test_users["eo2"].id,
            administrative_id=test_users["eo2"].administrative_id,
        )
        assert not_found is None

    def test_update_group_owner_only(
        self, db_session: Session, test_users, test_customers
    ):
        """Test that only owner can update a group."""
        service = BroadcastService(db_session)

        # EO1 creates a group
        group = service.create_group(
            name="Original Name",
            customer_ids=[1, 2],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # EO1 (owner) can update
        updated_group = service.update_group(
            group_id=group.id,
            eo_id=test_users["eo1"].id,
            name="Updated Name",
            administrative_id=test_users["eo1"].administrative_id,
        )
        assert updated_group is not None
        assert updated_group.name == "Updated Name"

        # Create another EO in same ward
        eo3 = User(
            email="eo3@test.com",
            phone_number="+255700000003",
            full_name="EO Three",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(eo3)
        db_session.commit()
        db_session.refresh(eo3)

        # Assign to same ward as EO1
        user_admin3 = UserAdministrative(
            user_id=eo3.id,
            administrative_id=test_users["eo1"].administrative_id
        )
        db_session.add(user_admin3)
        db_session.commit()

        # EO3 (non-owner, same ward) cannot update
        result = service.update_group(
            group_id=group.id,
            eo_id=eo3.id,
            name="Should Not Update",
            administrative_id=test_users["eo1"].administrative_id,
        )
        assert result is None

    def test_update_group_contacts(
        self, db_session: Session, test_users, test_customers
    ):
        """Test updating group contacts."""
        service = BroadcastService(db_session)

        group = service.create_group(
            name="Test Group",
            customer_ids=[1, 2],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # Update with new customer list
        updated_group = service.update_group(
            group_id=group.id,
            eo_id=test_users["eo1"].id,
            customer_ids=[2, 3, 4],
            administrative_id=test_users["eo1"].administrative_id,
        )

        assert len(updated_group.group_contacts) == 3
        contact_customer_ids = [
            c.customer_id for c in updated_group.group_contacts
        ]
        assert set(contact_customer_ids) == {2, 3, 4}

    def test_delete_group_owner_only(
        self, db_session: Session, test_users, test_customers
    ):
        """Test that only owner can delete a group."""
        service = BroadcastService(db_session)

        # EO1 creates a group
        group = service.create_group(
            name="Test Group",
            customer_ids=[1, 2],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # Create another EO in same ward
        eo3 = User(
            email="eo3@test.com",
            phone_number="+255700000003",
            full_name="EO Three",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(eo3)
        db_session.commit()
        db_session.refresh(eo3)

        # Assign to same ward as EO1
        user_admin3 = UserAdministrative(
            user_id=eo3.id,
            administrative_id=test_users["eo1"].administrative_id
        )
        db_session.add(user_admin3)
        db_session.commit()

        # EO3 (non-owner) cannot delete
        result = service.delete_group(
            group_id=group.id,
            eo_id=eo3.id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        assert result is False

        # EO1 (owner) can delete
        result = service.delete_group(
            group_id=group.id,
            eo_id=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        assert result is True

        # Verify group is deleted
        found = service.get_group_by_id(
            group_id=group.id,
            eo_id=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        assert found is None


class TestBroadcastMessageCreation:
    """Test broadcast message creation."""

    def test_create_broadcast(
        self, db_session: Session, test_users, test_customers
    ):
        """Test creating a broadcast message."""
        service = BroadcastService(db_session)

        # Create groups
        group1 = service.create_group(
            name="Group 1",
            customer_ids=[1, 2, 3],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        group2 = service.create_group(
            name="Group 2",
            customer_ids=[3, 4, 5],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # Create broadcast
        broadcast = service.create_broadcast(
            message="Test broadcast message",
            group_ids=[group1.id, group2.id],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        assert broadcast is not None
        assert broadcast.message == "Test broadcast message"
        assert broadcast.status == "pending"
        # Should have 5 unique recipients (1, 2, 3, 4, 5)
        assert len(broadcast.broadcast_recipients) == 5

    def test_create_broadcast_deduplicates_recipients(
        self, db_session: Session, test_users, test_customers
    ):
        """Test that broadcast deduplicates recipients across groups."""
        service = BroadcastService(db_session)

        # Create groups with overlapping customers
        group1 = service.create_group(
            name="Group 1",
            customer_ids=[1, 2, 3],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        group2 = service.create_group(
            name="Group 2",
            customer_ids=[2, 3, 4],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        broadcast = service.create_broadcast(
            message="Test message",
            group_ids=[group1.id, group2.id],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # Should have 4 unique recipients (1, 2, 3, 4)
        assert len(broadcast.broadcast_recipients) == 4
        recipient_ids = {c.customer_id for c in broadcast.broadcast_recipients}
        assert recipient_ids == {1, 2, 3, 4}

    def test_create_broadcast_validates_access(
        self, db_session: Session, test_users, test_customers
    ):
        """Test that broadcast creation validates group access."""
        service = BroadcastService(db_session)

        # EO1 creates a group
        group = service.create_group(
            name="EO1 Group",
            customer_ids=[1, 2],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # EO2 from different ward cannot create broadcast with EO1's group
        broadcast = service.create_broadcast(
            message="Test message",
            group_ids=[group.id],
            created_by=test_users["eo2"].id,
            administrative_id=test_users["eo2"].administrative_id,
        )

        # Should fail due to access control
        assert broadcast is None

    def test_create_broadcast_with_empty_groups(
        self, db_session: Session, test_users, test_customers
    ):
        """Test broadcast creation with groups that have no customers."""
        service = BroadcastService(db_session)

        # Create empty group (no customers)
        group = BroadcastGroup(
            name="Empty Group",
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        db_session.add(group)
        db_session.commit()
        db_session.refresh(group)

        # Try to create broadcast
        broadcast = service.create_broadcast(
            message="Test message",
            group_ids=[group.id],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # Should fail - no recipients
        assert broadcast is None

    def test_get_broadcast_status(
        self, db_session: Session, test_users, test_customers
    ):
        """Test retrieving broadcast status."""
        service = BroadcastService(db_session)

        # Create group and broadcast
        group = service.create_group(
            name="Test Group",
            customer_ids=[1, 2, 3],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        broadcast = service.create_broadcast(
            message="Test message",
            group_ids=[group.id],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # Retrieve status
        found_broadcast = service.get_broadcast_status(
            broadcast_id=broadcast.id, created_by=test_users["eo1"].id
        )

        assert found_broadcast is not None
        assert found_broadcast.id == broadcast.id
        assert len(found_broadcast.broadcast_recipients) == 3

    def test_get_broadcast_status_access_control(
        self, db_session: Session, test_users, test_customers
    ):
        """Test that only creator can view broadcast status."""
        service = BroadcastService(db_session)

        # EO1 creates broadcast
        group = service.create_group(
            name="Test Group",
            customer_ids=[1, 2],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )
        broadcast = service.create_broadcast(
            message="Test message",
            group_ids=[group.id],
            created_by=test_users["eo1"].id,
            administrative_id=test_users["eo1"].administrative_id,
        )

        # EO1 can view
        found = service.get_broadcast_status(
            broadcast_id=broadcast.id, created_by=test_users["eo1"].id
        )
        assert found is not None

        # EO2 cannot view
        not_found = service.get_broadcast_status(
            broadcast_id=broadcast.id, created_by=test_users["eo2"].id
        )
        assert not_found is None
