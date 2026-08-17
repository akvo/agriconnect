"""
Unit and integration tests for dynamic administration levels and seeder.
"""

import csv

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import Settings, settings
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
)
from models.customer import Customer
from seeder.administrative import (
    clear_administrative_data,
    get_or_create_level,
    main as seeder_main,
    seed_administrative_data,
)


class TestAdministrativeLevelModel:
    """Test suite for AdministrativeLevel model dynamic level_index support."""

    def test_level_index_column_exists_and_persists(self, db_session: Session):
        """Test that AdministrativeLevel stores and retrieves level_index."""
        level = AdministrativeLevel(name="province", level_index=1)
        db_session.add(level)
        db_session.commit()
        db_session.refresh(level)

        assert level.id is not None
        assert level.name == "province"
        assert level.level_index == 1

        # Query back from DB
        fetched = (
            db_session.query(AdministrativeLevel)
            .filter_by(level_index=1)
            .first()
        )
        assert fetched is not None
        assert fetched.name == "province"

    def test_level_index_unique_constraint(self, db_session: Session):
        """Test that level_index enforces uniqueness in database."""
        level1 = AdministrativeLevel(name="region", level_index=1)
        db_session.add(level1)
        db_session.commit()

        level2 = AdministrativeLevel(name="province", level_index=1)
        db_session.add(level2)

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

    def test_level_index_nullable(self, db_session: Session):
        """Test that level_index can be null for backward compatibility."""
        level = AdministrativeLevel(name="unassigned_level", level_index=None)
        db_session.add(level)
        db_session.commit()
        db_session.refresh(level)

        assert level.level_index is None


class TestAdministrativeHierarchyConfig:
    """Test suite for administrative_hierarchy configuration and properties."""

    def test_default_admin_hierarchy_settings(self):
        """Test default administrative hierarchy properties on settings."""
        assert isinstance(settings.administrative_hierarchy, dict)
        assert settings.admin_level_order == ["region", "district", "ward"]
        assert settings.admin_country_level_name == "country"
        assert settings.admin_leaf_level_name == "ward"
        assert settings.admin_leaf_level_index == 3
        assert settings.admin_delimiter == " > "

    def test_custom_admin_hierarchy_properties(self, monkeypatch):
        """
        Test hierarchy properties with custom 4-tier IDN config.
        """
        custom_cfg = {
            "country_code": "IDN",
            "delimiter": " > ",
            "levels": [
                {"level_index": 0, "name": "country"},
                {"level_index": 1, "name": "provinsi"},
                {"level_index": 2, "name": "kabupaten"},
                {"level_index": 3, "name": "kecamatan"},
                {"level_index": 4, "name": "desa"},
            ],
        }

        s = Settings()
        monkeypatch.setattr(s, "administrative_hierarchy", custom_cfg)

        assert s.admin_level_order == [
            "provinsi",
            "kabupaten",
            "kecamatan",
            "desa",
        ]
        assert s.admin_country_level_name == "country"
        assert s.admin_leaf_level_name == "desa"
        assert s.admin_leaf_level_index == 4
        assert s.admin_delimiter == " > "


class TestAdministrativeSeeder:
    """Test suite for dynamic administrative seeder and country swap."""

    def test_seeder_get_or_create_level_assigns_index(
        self, db_session: Session
    ):
        """Test get_or_create_level assigns level_index when creating."""
        lvl = get_or_create_level(db_session, "province", level_index=1)
        assert lvl.id is not None
        assert lvl.name == "province"
        assert lvl.level_index == 1

    def test_seeder_get_or_create_level_backfills_index(
        self, db_session: Session
    ):
        """Test get_or_create_level backfills level_index on existing level."""
        # Create without index
        lvl = AdministrativeLevel(name="old_level", level_index=None)
        db_session.add(lvl)
        db_session.commit()

        # Call with index
        updated_lvl = get_or_create_level(
            db_session, "old_level", level_index=2
        )
        assert updated_lvl.id == lvl.id
        assert updated_lvl.level_index == 2

    def test_seeder_populates_level_indices_from_config(
        self, db_session: Session
    ):
        """Test seed_administrative_data assigns indices defined in config."""
        rows = [
            {
                "code": "KEN",
                "name": "Kenya",
                "level": "country",
                "parent_code": "",
            },
            {
                "code": "REG1",
                "name": "Central Region",
                "level": "region",
                "parent_code": "KEN",
            },
            {
                "code": "DIST1",
                "name": "Nairobi District",
                "level": "district",
                "parent_code": "REG1",
            },
            {
                "code": "WARD1",
                "name": "Westlands Ward",
                "level": "ward",
                "parent_code": "DIST1",
            },
        ]

        stats = seed_administrative_data(db_session, rows)
        assert stats["created"] == 4
        assert stats["errors"] == 0

        # Verify all levels have correct level_index matching config
        country_lvl = (
            db_session.query(AdministrativeLevel)
            .filter_by(name="country")
            .first()
        )
        region_lvl = (
            db_session.query(AdministrativeLevel)
            .filter_by(name="region")
            .first()
        )
        district_lvl = (
            db_session.query(AdministrativeLevel)
            .filter_by(name="district")
            .first()
        )
        ward_lvl = (
            db_session.query(AdministrativeLevel)
            .filter_by(name="ward")
            .first()
        )

        assert country_lvl.level_index == 0
        assert region_lvl.level_index == 1
        assert district_lvl.level_index == 2
        assert ward_lvl.level_index == 3

    def test_clear_administrative_data(self, db_session: Session):
        """
        Test clear_administrative_data purges all administrative entities.
        """
        # Setup test entities
        lvl = AdministrativeLevel(name="ward", level_index=3)
        db_session.add(lvl)
        db_session.commit()

        admin = Administrative(
            code="W1",
            name="Ward 1",
            level_id=lvl.id,
            path="Kenya > Ward 1",
        )
        db_session.add(admin)
        db_session.commit()

        cust = Customer(phone_number="+254700000001", language="en")
        db_session.add(cust)
        db_session.commit()

        ca = CustomerAdministrative(
            customer_id=cust.id,
            administrative_id=admin.id,
        )
        db_session.add(ca)
        db_session.commit()

        # Clear data
        counts = clear_administrative_data(db_session)
        assert counts["customer_administrative"] >= 1
        assert counts["administrative"] >= 1
        assert counts["administrative_levels"] >= 1

        # Check tables are empty of administrative data
        assert db_session.query(CustomerAdministrative).count() == 0
        assert db_session.query(Administrative).count() == 0
        assert db_session.query(AdministrativeLevel).count() == 0
        # Customer record itself is preserved
        assert db_session.query(Customer).filter_by(id=cust.id).count() == 1

    def test_replace_country_safety_guard_blocks_when_customers_exist(
        self, db_session: Session, monkeypatch
    ):
        """
        Safety guard must abort --replace-country if live customers exist.
        """
        # Create live customer record
        cust = Customer(phone_number="+254700000099", language="en")
        db_session.add(cust)
        db_session.commit()

        monkeypatch.setattr(
            "sys.argv", ["seeder/administrative.py", "--replace-country"]
        )

        with pytest.raises(SystemExit) as exc_info:
            seeder_main()

        assert exc_info.value.code == 1

    def test_replace_country_succeeds_on_fresh_deploy(
        self, db_session: Session, monkeypatch, tmp_path
    ):
        """
        Country swap must succeed on fresh deploy without customers.
        """
        # Clean customer tables to ensure fresh deploy
        db_session.query(CustomerAdministrative).delete()
        db_session.query(Customer).delete()
        db_session.commit()

        # Create temporary custom CSV for country swap (e.g. Indonesia)
        csv_file = tmp_path / "custom_admin.csv"
        fieldnames = ["code", "name", "level", "parent_code", "latitude", "longitude"]  # noqa: E501
        rows = [
            {"code": "IDN", "name": "Indonesia", "level": "country", "parent_code": "", "latitude": "", "longitude": ""},  # noqa: E501
            {"code": "JB", "name": "Jawa Barat", "level": "region", "parent_code": "IDN", "latitude": "", "longitude": ""},  # noqa: E501
        ]
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        monkeypatch.setattr(
            "sys.argv",
            [
                "seeder/administrative.py",
                "--replace-country",
                "--source",
                str(csv_file),
            ],
        )

        seeder_main()

        # Verify new country data exists
        country = (
            db_session.query(Administrative).filter_by(code="IDN").first()
        )
        assert country is not None
        assert country.name == "Indonesia"
        assert country.path == "Indonesia"

        region = db_session.query(Administrative).filter_by(code="JB").first()
        assert region is not None
        assert region.name == "Jawa Barat"
        assert region.path == "Indonesia > Jawa Barat"


class TestOnboardingServiceDynamicLevels:
    """Test suite for OnboardingService with dynamic administrative levels."""

    def test_onboarding_service_initializes_with_dynamic_levels(
        self, db_session: Session
    ):
        """Test OnboardingService uses settings.admin_level_order."""
        from services.onboarding_service import OnboardingService

        service = OnboardingService(db_session)
        assert service.admin_level_order == settings.admin_level_order

    def test_start_hierarchical_selection_with_default_kenya(
        self, db_session: Session
    ):
        """Test start_hierarchical_selection uses select_region for Kenya."""
        from services.onboarding_service import OnboardingService

        # Setup country and regions
        c_lvl = AdministrativeLevel(name="country", level_index=0)
        r_lvl = AdministrativeLevel(name="region", level_index=1)
        db_session.add_all([c_lvl, r_lvl])
        db_session.commit()

        country = Administrative(
            code="KEN", name="Kenya", level_id=c_lvl.id, path="Kenya"
        )
        db_session.add(country)
        db_session.commit()

        reg1 = Administrative(
            code="R1",
            name="Central Region",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Central Region",
        )
        db_session.add(reg1)

        cust = Customer(phone_number="+254700000005", language="en")
        db_session.add(cust)
        db_session.commit()

        service = OnboardingService(db_session)
        resp = service._start_hierarchical_selection(cust)

        assert resp.status == "awaiting_selection"
        assert "Which county/region are you from?" in resp.message
        assert "1. Central Region" in resp.message

    def test_start_hierarchical_selection_custom_fallback(
        self, db_session: Session, monkeypatch
    ):
        """Test fallback to select_level for unlocalized level name."""
        from services.onboarding_service import OnboardingService

        custom_cfg = {
            "country_code": "IDN",
            "delimiter": " > ",
            "levels": [
                {"level_index": 0, "name": "country"},
                {"level_index": 1, "name": "provinsi"},
                {"level_index": 2, "name": "kabupaten"},
                {"level_index": 3, "name": "kecamatan"},
                {"level_index": 4, "name": "desa"},
            ],
        }
        monkeypatch.setattr(
            settings, "administrative_hierarchy", custom_cfg
        )

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        p_lvl = AdministrativeLevel(name="provinsi", level_index=1)
        db_session.add_all([c_lvl, p_lvl])
        db_session.commit()

        country = Administrative(
            code="IDN", name="Indonesia", level_id=c_lvl.id, path="Indonesia"
        )
        db_session.add(country)
        db_session.commit()

        prov = Administrative(
            code="JB",
            name="Jawa Barat",
            level_id=p_lvl.id,
            parent_id=country.id,
            path="Indonesia > Jawa Barat",
        )
        db_session.add(prov)

        cust = Customer(phone_number="+628123456789", language="en")
        db_session.add(cust)
        db_session.commit()

        service = OnboardingService(db_session)
        resp = service._start_hierarchical_selection(cust)

        assert resp.status == "awaiting_selection"
        # Uses generic fallback with level="Provinsi"
        assert "Which Provinsi are you from?" in resp.message
        assert "1. Jawa Barat" in resp.message

    def test_process_hierarchical_selection_custom_fallback(
        self, db_session: Session, monkeypatch
    ):
        """Test fallback to select_next when stepping down dynamic levels."""
        from services.onboarding_service import OnboardingService

        custom_cfg = {
            "country_code": "IDN",
            "delimiter": " > ",
            "levels": [
                {"level_index": 0, "name": "country"},
                {"level_index": 1, "name": "provinsi"},
                {"level_index": 2, "name": "kabupaten"},
                {"level_index": 3, "name": "kecamatan"},
                {"level_index": 4, "name": "desa"},
            ],
        }
        monkeypatch.setattr(
            settings, "administrative_hierarchy", custom_cfg
        )

        p_lvl = AdministrativeLevel(name="provinsi", level_index=1)
        k_lvl = AdministrativeLevel(name="kabupaten", level_index=2)
        db_session.add_all([p_lvl, k_lvl])
        db_session.commit()

        prov = Administrative(
            code="JB",
            name="Jawa Barat",
            level_id=p_lvl.id,
            path="Indonesia > Jawa Barat",
        )
        db_session.add(prov)
        db_session.commit()

        kab = Administrative(
            code="BDG",
            name="Bandung",
            level_id=k_lvl.id,
            parent_id=prov.id,
            path="Indonesia > Jawa Barat > Bandung",
        )
        db_session.add(kab)
        db_session.commit()

        cust = Customer(phone_number="+628123456788", language="en")
        db_session.add(cust)
        db_session.commit()

        service = OnboardingService(db_session)
        # Set state as if provinsi was selected
        service._set_admin_hierarchy_state(
            cust, "provinsi", None, [prov.id]
        )
        db_session.commit()

        # User chooses '1' (Jawa Barat)
        resp = service._process_hierarchical_selection(cust, "1")

        assert resp.status == "awaiting_selection"
        assert "Great! You selected Jawa Barat." in resp.message
        assert "Which Kabupaten are you in?" in resp.message
        assert "1. Bandung" in resp.message
