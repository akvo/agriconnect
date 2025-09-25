import pytest

from models import (
    Administrative,
    AdministrativeLevel,
    User,
    UserAdministrative,
    UserType,
)
from schemas.administrative import (
    AdministrativeAssign,
    AdministrativeCreate,
    AdministrativeUpdate,
)
from services.administrative_service import AdministrativeService


class TestAdministrativeService:
    """Test cases for administrative service layer"""

    def test_get_all_administrative(self, db_session):
        """Test getting all administrative areas"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        db_session.add(country_level)
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        uganda = Administrative(
            code="UGA",
            name="Uganda",
            level_id=country_level.id,
            parent_id=None,
            path="UGA",
        )
        db_session.add_all([kenya, uganda])
        db_session.commit()

        result = AdministrativeService.get_all_administrative(db_session)
        assert len(result) == 2

        codes = [admin.code for admin in result]
        assert "KEN" in codes
        assert "UGA" in codes

    def test_get_administrative_by_id(self, db_session):
        """Test getting administrative area by ID"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        db_session.add(country_level)
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        db_session.add(kenya)
        db_session.commit()

        result = AdministrativeService.get_administrative_by_id(
            db_session, kenya.id
        )
        assert result.code == "KEN"
        assert result.name == "Kenya"

    def test_get_administrative_by_id_not_found(self, db_session):
        """Test getting non-existent administrative area by ID"""
        with pytest.raises(Exception):  # Should raise HTTPException
            AdministrativeService.get_administrative_by_id(db_session, 999)

    def test_get_administrative_by_level(self, db_session):
        """Test getting administrative areas by level"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        db_session.add_all([country_level, region_level])
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        nairobi = Administrative(
            code="NBI",
            name="Nairobi Region",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="KEN.NBI",
        )
        kampala = Administrative(
            code="KLA",
            name="Kampala Region",
            level_id=region_level.id,
            parent_id=None,  # Standalone region
            path="KLA",
        )
        db_session.add_all([kenya, nairobi, kampala])
        db_session.commit()

        result = AdministrativeService.get_administrative_by_level(
            db_session, "region"
        )
        assert len(result) == 2

        codes = [admin.code for admin in result]
        assert "NBI" in codes
        assert "KLA" in codes

    def test_get_administrative_by_parent(self, db_session):
        """Test getting administrative areas by parent"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        db_session.add_all([country_level, region_level])
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        uganda = Administrative(
            code="UGA",
            name="Uganda",
            level_id=country_level.id,
            parent_id=None,
            path="UGA",
        )
        db_session.add_all([kenya, uganda])
        db_session.commit()  # Commit parents first to get their IDs

        nairobi = Administrative(
            code="NBI",
            name="Nairobi Region",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="KEN.NBI",
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

        result = AdministrativeService.get_administrative_by_parent(
            db_session, kenya.id
        )
        assert len(result) == 2  # Nairobi and Coast

        codes = [admin.code for admin in result]
        assert "NBI" in codes
        assert "CST" in codes

    def test_create_administrative(self, db_session):
        """Test creating administrative area"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        db_session.add(country_level)
        db_session.commit()

        admin_data = AdministrativeCreate(
            code="TZA", name="Tanzania", level="country", parent_id=None
        )

        result = AdministrativeService.create_administrative(
            db_session, admin_data
        )
        assert result.code == "TZA"
        assert result.name == "Tanzania"
        assert result.path == "TZA"

    def test_create_administrative_with_parent(self, db_session):
        """Test creating administrative area with parent"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        db_session.add_all([country_level, region_level])
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        db_session.add(kenya)
        db_session.commit()

        admin_data = AdministrativeCreate(
            code="WST",
            name="Western Region",
            level="region",
            parent_id=kenya.id,
        )

        result = AdministrativeService.create_administrative(
            db_session, admin_data
        )
        assert result.code == "WST"
        assert result.name == "Western Region"
        assert result.path == "KEN.WST"
        assert result.parent_id == kenya.id

    def test_create_administrative_duplicate_code(self, db_session):
        """Test creating administrative area with duplicate code"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        db_session.add(country_level)
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        db_session.add(kenya)
        db_session.commit()

        admin_data = AdministrativeCreate(
            code="KEN", name="Kenya Duplicate", level="country", parent_id=None
        )

        with pytest.raises(
            Exception
        ):  # Should raise HTTPException for duplicate
            AdministrativeService.create_administrative(db_session, admin_data)

    def test_update_administrative(self, db_session):
        """Test updating administrative area"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        db_session.add_all([country_level, region_level])
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        nairobi = Administrative(
            code="NBI",
            name="Nairobi Region",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="KEN.NBI",
        )
        db_session.add_all([kenya, nairobi])
        db_session.commit()

        update_data = AdministrativeUpdate(name="Nairobi Metropolitan Region")
        result = AdministrativeService.update_administrative(
            db_session, nairobi.id, update_data
        )
        assert result.name == "Nairobi Metropolitan Region"

    def test_assign_user_to_administrative(self, db_session):
        """Test assigning user to administrative areas"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        db_session.add(country_level)
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        uganda = Administrative(
            code="UGA",
            name="Uganda",
            level_id=country_level.id,
            parent_id=None,
            path="UGA",
        )
        user = User(
            email="test@example.com",
            phone_number="+254700000000",
            hashed_password="hashed_password",
            full_name="Test User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add_all([kenya, uganda, user])
        db_session.commit()

        assignment_data = AdministrativeAssign(
            administrative_ids=[kenya.id, uganda.id]
        )
        result = AdministrativeService.assign_user_to_administrative(
            db_session, user.id, assignment_data
        )

        assert len(result) == 2
        assigned_ids = [assignment.administrative_id for assignment in result]
        assert kenya.id in assigned_ids
        assert uganda.id in assigned_ids

    def test_get_user_administrative(self, db_session):
        """Test getting administrative areas assigned to user"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        db_session.add(country_level)
        db_session.commit()

        kenya = Administrative(
            code="KEN",
            name="Kenya",
            level_id=country_level.id,
            parent_id=None,
            path="KEN",
        )
        uganda = Administrative(
            code="UGA",
            name="Uganda",
            level_id=country_level.id,
            parent_id=None,
            path="UGA",
        )
        user = User(
            email="test@example.com",
            phone_number="+254700000000",
            hashed_password="hashed_password",
            full_name="Test User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add_all([kenya, uganda, user])
        db_session.commit()

        # Create assignments
        assignment1 = UserAdministrative(
            user_id=user.id, administrative_id=kenya.id
        )
        assignment2 = UserAdministrative(
            user_id=user.id, administrative_id=uganda.id
        )
        db_session.add_all([assignment1, assignment2])
        db_session.commit()

        result = AdministrativeService.get_user_administrative(
            db_session, user.id
        )
        assert len(result) == 2

        codes = [admin.code for admin in result]
        assert "KEN" in codes
        assert "UGA" in codes
