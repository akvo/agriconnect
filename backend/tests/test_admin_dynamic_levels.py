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
    UserAdministrative,
)
from models.customer import Customer, OnboardingStatus
from models.user import User, UserType
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

    def test_level_index_ordering_query(self, db_session: Session):
        """Test database query ordering by level_index."""
        l3 = AdministrativeLevel(name="lvl3", level_index=3)
        l1 = AdministrativeLevel(name="lvl1", level_index=1)
        l2 = AdministrativeLevel(name="lvl2", level_index=2)
        l0 = AdministrativeLevel(name="lvl0", level_index=0)
        db_session.add_all([l3, l1, l2, l0])
        db_session.commit()

        ordered = (
            db_session.query(AdministrativeLevel)
            .filter(AdministrativeLevel.level_index.isnot(None))
            .order_by(AdministrativeLevel.level_index.asc())
            .all()
        )
        assert [lvl.name for lvl in ordered] == [
            "lvl0",
            "lvl1",
            "lvl2",
            "lvl3",
        ]


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
        """Test hierarchy properties with custom 5-tier IDN config."""
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

    def test_admin_level_order_unsorted_config_levels(self, monkeypatch):
        """
        Test that admin_level_order sorts by level_index even if unsorted.
        """
        unsorted_cfg = {
            "country_code": "TEST",
            "delimiter": " > ",
            "levels": [
                {"level_index": 3, "name": "ward"},
                {"level_index": 0, "name": "country"},
                {"level_index": 2, "name": "district"},
                {"level_index": 1, "name": "region"},
            ],
        }
        s = Settings()
        monkeypatch.setattr(s, "administrative_hierarchy", unsorted_cfg)

        assert s.admin_level_order == ["region", "district", "ward"]
        assert s.admin_country_level_name == "country"
        assert s.admin_leaf_level_name == "ward"
        assert s.admin_leaf_level_index == 3

    def test_custom_delimiter(self, monkeypatch):
        """Test hierarchy with custom path delimiter (e.g. ' / ')."""
        custom_cfg = {
            "country_code": "MYS",
            "delimiter": " / ",
            "levels": [
                {"level_index": 0, "name": "country"},
                {"level_index": 1, "name": "negeri"},
                {"level_index": 2, "name": "daerah"},
            ],
        }
        s = Settings()
        monkeypatch.setattr(s, "administrative_hierarchy", custom_cfg)

        assert s.admin_delimiter == " / "
        assert s.admin_level_order == ["negeri", "daerah"]
        assert s.admin_leaf_level_name == "daerah"
        assert s.admin_leaf_level_index == 2

    def test_minimal_2_tier_hierarchy(self, monkeypatch):
        """Test minimal 2-tier hierarchy (country + state)."""
        custom_cfg = {
            "country_code": "USA",
            "delimiter": " > ",
            "levels": [
                {"level_index": 0, "name": "country"},
                {"level_index": 1, "name": "state"},
            ],
        }
        s = Settings()
        monkeypatch.setattr(s, "administrative_hierarchy", custom_cfg)

        assert s.admin_level_order == ["state"]
        assert s.admin_leaf_level_name == "state"
        assert s.admin_leaf_level_index == 1


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

    def test_clear_administrative_data_with_user_administrative(
        self, db_session: Session
    ):
        """Test that UserAdministrative is also safely cleared in FK order."""
        lvl = AdministrativeLevel(name="region", level_index=1)
        db_session.add(lvl)
        db_session.commit()

        admin = Administrative(
            code="R_TEST",
            name="Region Test",
            level_id=lvl.id,
            path="Kenya > Region Test",
        )
        db_session.add(admin)

        user = User(
            email="eo_test@agriconnect.org",
            full_name="Test EO",
            phone_number="+254711223344",
            user_type=UserType.EXTENSION_OFFICER,
            hashed_password="fakehashedpassword",
        )
        db_session.add(user)
        db_session.commit()

        ua = UserAdministrative(user_id=user.id, administrative_id=admin.id)
        db_session.add(ua)
        db_session.commit()

        counts = clear_administrative_data(db_session)
        assert counts["user_administrative"] >= 1
        assert counts["administrative"] >= 1
        assert counts["administrative_levels"] >= 1

        assert db_session.query(UserAdministrative).count() == 0
        assert db_session.query(Administrative).count() == 0
        # User is preserved
        assert db_session.query(User).filter_by(id=user.id).count() == 1

    def test_replace_country_missing_source_file_fails_gracefully(
        self, db_session: Session, monkeypatch
    ):
        """Test that missing source CSV causes clean failure."""
        # Ensure fresh deploy
        db_session.query(CustomerAdministrative).delete()
        db_session.query(Customer).delete()
        db_session.commit()

        monkeypatch.setattr(
            "sys.argv",
            [
                "seeder/administrative.py",
                "--replace-country",
                "--source",
                "non_existent_path_to_file.csv",
            ],
        )

        with pytest.raises(SystemExit) as exc_info:
            seeder_main()

        assert exc_info.value.code == 1


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

    def test_full_multi_tier_onboarding_traversal_to_leaf_save(
        self, db_session: Session, monkeypatch
    ):
        """Test complete 4-step traversal on 5-tier hierarchy saving leaf."""
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
        monkeypatch.setattr(settings, "administrative_hierarchy", custom_cfg)

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        p_lvl = AdministrativeLevel(name="provinsi", level_index=1)
        k_lvl = AdministrativeLevel(name="kabupaten", level_index=2)
        kc_lvl = AdministrativeLevel(name="kecamatan", level_index=3)
        d_lvl = AdministrativeLevel(name="desa", level_index=4)
        db_session.add_all([c_lvl, p_lvl, k_lvl, kc_lvl, d_lvl])
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

        kec = Administrative(
            code="CLY",
            name="Cileunyi",
            level_id=kc_lvl.id,
            parent_id=kab.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi",
        )
        db_session.add(kec)
        db_session.commit()

        desa = Administrative(
            code="CBR",
            name="Cibiruhilir",
            level_id=d_lvl.id,
            parent_id=kec.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi > Cibiruhilir",
        )
        db_session.add(desa)
        db_session.commit()

        cust = Customer(phone_number="+6281999888777", language="en")
        db_session.add(cust)
        db_session.commit()

        service = OnboardingService(db_session)

        # Step 1: Start (Provinsi)
        resp1 = service._start_hierarchical_selection(cust)
        assert resp1.status == "awaiting_selection"
        assert "Which Provinsi are you from?" in resp1.message

        # Step 2: Select Provinsi 1 (Jawa Barat) -> asks Kabupaten
        resp2 = service._process_hierarchical_selection(cust, "1")
        assert resp2.status == "awaiting_selection"
        assert "Which Kabupaten are you in?" in resp2.message

        # Step 3: Select Kabupaten 1 (Bandung) -> asks Kecamatan
        resp3 = service._process_hierarchical_selection(cust, "1")
        assert resp3.status == "awaiting_selection"
        assert "Which Kecamatan are you in?" in resp3.message

        # Step 4: Select Kecamatan 1 (Cileunyi) -> asks Desa
        resp4 = service._process_hierarchical_selection(cust, "1")
        assert resp4.status == "awaiting_selection"
        assert "Which Desa are you in?" in resp4.message

        # Step 5: Select Desa 1 (Cibiruhilir) -> final leaf reached!
        resp5 = service._process_hierarchical_selection(cust, "1")
        assert resp5.status == "in_progress"

        # Verify CustomerAdministrative is saved with the leaf Desa
        ca = (
            db_session.query(CustomerAdministrative)
            .filter_by(customer_id=cust.id)
            .first()
        )
        assert ca is not None
        assert ca.administrative_id == desa.id

    def test_onboarding_out_of_range_selection(self, db_session: Session):
        """Test user entering a number greater than options available."""
        from services.onboarding_service import OnboardingService

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        r_lvl = AdministrativeLevel(name="region", level_index=1)
        db_session.add_all([c_lvl, r_lvl])
        db_session.commit()

        country = Administrative(
            code="KEN", name="Kenya", level_id=c_lvl.id, path="Kenya"
        )
        db_session.add(country)
        db_session.commit()

        reg = Administrative(
            code="R1",
            name="Central",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Central",
        )
        db_session.add(reg)
        db_session.commit()

        cust = Customer(phone_number="+254700000088", language="en")
        db_session.add(cust)
        db_session.commit()

        service = OnboardingService(db_session)
        service._start_hierarchical_selection(cust)

        # Enter selection 9 when only 1 option exists
        resp = service._process_hierarchical_selection(cust, "9")
        assert resp.status == "awaiting_selection"
        assert "Please select a number between 1 and 1" in resp.message

    def test_onboarding_invalid_non_numeric_selection(
        self, db_session: Session
    ):
        """Test user entering text instead of a number during selection."""
        from services.onboarding_service import OnboardingService

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        r_lvl = AdministrativeLevel(name="region", level_index=1)
        db_session.add_all([c_lvl, r_lvl])
        db_session.commit()

        country = Administrative(
            code="KEN", name="Kenya", level_id=c_lvl.id, path="Kenya"
        )
        db_session.add(country)
        db_session.commit()

        reg = Administrative(
            code="R1",
            name="Central",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Central",
        )
        db_session.add(reg)
        db_session.commit()

        cust = Customer(phone_number="+254700000087", language="en")
        db_session.add(cust)
        db_session.commit()

        service = OnboardingService(db_session)
        service._start_hierarchical_selection(cust)

        resp = service._process_hierarchical_selection(cust, "hello region")
        assert resp.status == "awaiting_selection"
        assert "Please reply with a number" in resp.message

    def test_onboarding_intermediate_node_without_children(
        self, db_session: Session
    ):
        """Intermediate selection without children saves immediately."""
        from services.onboarding_service import OnboardingService

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        r_lvl = AdministrativeLevel(name="region", level_index=1)
        db_lvl = AdministrativeLevel(name="district", level_index=2)
        db_session.add_all([c_lvl, r_lvl, db_lvl])
        db_session.commit()

        country = Administrative(
            code="KEN", name="Kenya", level_id=c_lvl.id, path="Kenya"
        )
        db_session.add(country)
        db_session.commit()

        reg = Administrative(
            code="R_ISOLATED",
            name="Isolated Region",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Isolated Region",
        )
        db_session.add(reg)
        db_session.commit()

        cust = Customer(phone_number="+254700000086", language="en")
        db_session.add(cust)
        db_session.commit()

        service = OnboardingService(db_session)
        service._start_hierarchical_selection(cust)

        # Select Isolated Region (which has 0 districts)
        resp = service._process_hierarchical_selection(cust, "1")
        # Should save region as final location and advance to next field
        assert resp.status == "in_progress"

        ca = (
            db_session.query(CustomerAdministrative)
            .filter_by(customer_id=cust.id)
            .first()
        )
        assert ca is not None
        assert ca.administrative_id == reg.id

    def test_onboarding_swahili_dynamic_fallback(
        self, db_session: Session, monkeypatch
    ):
        """Test Swahili language fallback for custom unlocalized levels."""
        from services.onboarding_service import OnboardingService

        custom_cfg = {
            "country_code": "IDN",
            "delimiter": " > ",
            "levels": [
                {"level_index": 0, "name": "country"},
                {"level_index": 1, "name": "provinsi"},
            ],
        }
        monkeypatch.setattr(settings, "administrative_hierarchy", custom_cfg)

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
        db_session.commit()

        cust = Customer(phone_number="+62811223344", language="sw")
        db_session.add(cust)
        db_session.commit()

        service = OnboardingService(db_session)
        resp = service._start_hierarchical_selection(cust)

        assert resp.status == "awaiting_selection"
        assert "Unatoka Provinsi gani?" in resp.message
        assert "1. Jawa Barat" in resp.message


class TestAdministrativeServiceDynamicLeaf:
    """Test suite for AdministrativeService dynamic leaf area resolution."""

    def test_get_descendant_ward_ids_default_kenya(self, db_session: Session):
        """Test descendant leaf lookup with Kenya 4-tier default hierarchy."""
        from services.administrative_service import AdministrativeService

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        r_lvl = AdministrativeLevel(name="region", level_index=1)
        d_lvl = AdministrativeLevel(name="district", level_index=2)
        w_lvl = AdministrativeLevel(name="ward", level_index=3)
        db_session.add_all([c_lvl, r_lvl, d_lvl, w_lvl])
        db_session.commit()

        country = Administrative(
            code="KEN", name="Kenya", level_id=c_lvl.id, path="Kenya"
        )
        db_session.add(country)
        db_session.commit()

        reg = Administrative(
            code="R1",
            name="Central",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Central",
        )
        db_session.add(reg)
        db_session.commit()

        dist = Administrative(
            code="D1",
            name="Kiharu",
            level_id=d_lvl.id,
            parent_id=reg.id,
            path="Kenya > Central > Kiharu",
        )
        db_session.add(dist)
        db_session.commit()

        ward = Administrative(
            code="W1",
            name="Wangu",
            level_id=w_lvl.id,
            parent_id=dist.id,
            path="Kenya > Central > Kiharu > Wangu",
        )
        db_session.add(ward)
        db_session.commit()

        # Descendant from region
        leaf_ids = AdministrativeService.get_descendant_ward_ids(
            db_session, reg.id
        )
        assert leaf_ids == [ward.id]

        # Descendant from ward (itself)
        self_ids = AdministrativeService.get_descendant_ward_ids(
            db_session, ward.id
        )
        assert self_ids == [ward.id]

    def test_get_descendant_ward_ids_custom_hierarchy(
        self, db_session: Session, monkeypatch
    ):
        """Test descendant leaf lookup with Indonesia 5-tier hierarchy."""
        from services.administrative_service import AdministrativeService

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
        monkeypatch.setattr(settings, "administrative_hierarchy", custom_cfg)

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        p_lvl = AdministrativeLevel(name="provinsi", level_index=1)
        k_lvl = AdministrativeLevel(name="kabupaten", level_index=2)
        kc_lvl = AdministrativeLevel(name="kecamatan", level_index=3)
        d_lvl = AdministrativeLevel(name="desa", level_index=4)
        db_session.add_all([c_lvl, p_lvl, k_lvl, kc_lvl, d_lvl])
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

        kec = Administrative(
            code="CLY",
            name="Cileunyi",
            level_id=kc_lvl.id,
            parent_id=kab.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi",
        )
        db_session.add(kec)
        db_session.commit()

        desa = Administrative(
            code="CBR",
            name="Cibiruhilir",
            level_id=d_lvl.id,
            parent_id=kec.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi > Cibiruhilir",
        )
        db_session.add(desa)
        db_session.commit()

        # Query from provinsi -> finds desa
        leaf_ids = AdministrativeService.get_descendant_ward_ids(
            db_session, prov.id
        )
        assert leaf_ids == [desa.id]

    def test_get_descendant_ward_ids_non_existent_id(
        self, db_session: Session
    ):
        """Test lookup on non-existent administrative area ID returns [id]."""
        from services.administrative_service import AdministrativeService

        res = AdministrativeService.get_descendant_ward_ids(db_session, 99999)
        assert res == [99999]

    def test_get_descendant_ward_ids_from_root_country(
        self, db_session: Session
    ):
        """Test lookup from root country returns all leaf areas."""
        from services.administrative_service import AdministrativeService

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        r_lvl = AdministrativeLevel(name="region", level_index=1)
        w_lvl = AdministrativeLevel(name="ward", level_index=2)
        db_session.add_all([c_lvl, r_lvl, w_lvl])
        db_session.commit()

        country = Administrative(
            code="KEN", name="Kenya", level_id=c_lvl.id, path="Kenya"
        )
        db_session.add(country)
        db_session.commit()

        r1 = Administrative(
            code="R1",
            name="Reg1",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Reg1",
        )
        r2 = Administrative(
            code="R2",
            name="Reg2",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Reg2",
        )
        db_session.add_all([r1, r2])
        db_session.commit()

        w1 = Administrative(
            code="W1",
            name="Ward1",
            level_id=w_lvl.id,
            parent_id=r1.id,
            path="Kenya > Reg1 > Ward1",
        )
        w2 = Administrative(
            code="W2",
            name="Ward2",
            level_id=w_lvl.id,
            parent_id=r2.id,
            path="Kenya > Reg2 > Ward2",
        )
        db_session.add_all([w1, w2])
        db_session.commit()

        leaf_ids = AdministrativeService.get_descendant_ward_ids(
            db_session, country.id
        )
        assert set(leaf_ids) == {w1.id, w2.id}

    def test_get_descendant_ward_ids_branching_hierarchy(
        self, db_session: Session
    ):
        """Test branching structure with multiple districts and wards."""
        from services.administrative_service import AdministrativeService

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        r_lvl = AdministrativeLevel(name="region", level_index=1)
        d_lvl = AdministrativeLevel(name="district", level_index=2)
        w_lvl = AdministrativeLevel(name="ward", level_index=3)
        db_session.add_all([c_lvl, r_lvl, d_lvl, w_lvl])
        db_session.commit()

        country = Administrative(
            code="KEN", name="Kenya", level_id=c_lvl.id, path="Kenya"
        )
        db_session.add(country)
        db_session.commit()

        reg = Administrative(
            code="R1",
            name="Central",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Central",
        )
        db_session.add(reg)
        db_session.commit()

        d1 = Administrative(
            code="D1",
            name="Dist 1",
            level_id=d_lvl.id,
            parent_id=reg.id,
            path="Kenya > Central > Dist 1",
        )
        d2 = Administrative(
            code="D2",
            name="Dist 2",
            level_id=d_lvl.id,
            parent_id=reg.id,
            path="Kenya > Central > Dist 2",
        )
        db_session.add_all([d1, d2])
        db_session.commit()

        w1_1 = Administrative(
            code="W1_1",
            name="Ward 1.1",
            level_id=w_lvl.id,
            parent_id=d1.id,
            path="Kenya > Central > Dist 1 > Ward 1.1",
        )
        w1_2 = Administrative(
            code="W1_2",
            name="Ward 1.2",
            level_id=w_lvl.id,
            parent_id=d1.id,
            path="Kenya > Central > Dist 1 > Ward 1.2",
        )
        w2_1 = Administrative(
            code="W2_1",
            name="Ward 2.1",
            level_id=w_lvl.id,
            parent_id=d2.id,
            path="Kenya > Central > Dist 2 > Ward 2.1",
        )
        db_session.add_all([w1_1, w1_2, w2_1])
        db_session.commit()

        # Query region -> returns all 3 leaf wards
        res = AdministrativeService.get_descendant_ward_ids(
            db_session, reg.id
        )
        assert set(res) == {w1_1.id, w1_2.id, w2_1.id}

        # Query dist 1 -> returns only wards under d1
        d1_res = AdministrativeService.get_descendant_ward_ids(
            db_session, d1.id
        )
        assert set(d1_res) == {w1_1.id, w1_2.id}

    def test_get_ancestor_ids_with_deep_hierarchy(
        self, db_session: Session
    ):
        """Test ancestor traversal upwards excluding country level."""
        from services.administrative_service import AdministrativeService

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        p_lvl = AdministrativeLevel(name="provinsi", level_index=1)
        k_lvl = AdministrativeLevel(name="kabupaten", level_index=2)
        kc_lvl = AdministrativeLevel(name="kecamatan", level_index=3)
        d_lvl = AdministrativeLevel(name="desa", level_index=4)
        db_session.add_all([c_lvl, p_lvl, k_lvl, kc_lvl, d_lvl])
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

        kec = Administrative(
            code="CLY",
            name="Cileunyi",
            level_id=kc_lvl.id,
            parent_id=kab.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi",
        )
        db_session.add(kec)
        db_session.commit()

        desa = Administrative(
            code="CBR",
            name="Cibiruhilir",
            level_id=d_lvl.id,
            parent_id=kec.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi > Cibiruhilir",
        )
        db_session.add(desa)
        db_session.commit()

        ancestors = AdministrativeService.get_ancestor_ids(db_session, desa.id)
        # Should include [kec, kab, prov] (parents excluding desa itself and root country)  # noqa: E501
        assert ancestors == [kec.id, kab.id, prov.id]


class TestStatisticServiceDynamicHierarchy:
    """Test suite for StatisticService dynamic administrative hierarchy."""

    def test_get_child_level_default_kenya(self, db_session: Session):
        """Test child level transitions with default Kenya configuration."""
        from services.statistic_service import StatisticService

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        r_lvl = AdministrativeLevel(name="region", level_index=1)
        d_lvl = AdministrativeLevel(name="district", level_index=2)
        w_lvl = AdministrativeLevel(name="ward", level_index=3)
        db_session.add_all([c_lvl, r_lvl, d_lvl, w_lvl])
        db_session.commit()

        country = Administrative(
            code="KEN", name="Kenya", level_id=c_lvl.id, path="Kenya"
        )
        db_session.add(country)
        db_session.commit()

        reg = Administrative(
            code="R1",
            name="Central",
            level_id=r_lvl.id,
            parent_id=country.id,
            path="Kenya > Central",
        )
        db_session.add(reg)
        db_session.commit()

        dist = Administrative(
            code="D1",
            name="Murang'a",
            level_id=d_lvl.id,
            parent_id=reg.id,
            path="Kenya > Central > Murang'a",
        )
        db_session.add(dist)
        db_session.commit()

        ward = Administrative(
            code="W1",
            name="Kiharu",
            level_id=w_lvl.id,
            parent_id=dist.id,
            path="Kenya > Central > Murang'a > Kiharu",
        )
        db_session.add(ward)
        db_session.commit()

        svc = StatisticService(db_session)

        # No filter -> Region
        lvl, name = svc._get_child_level(None)
        assert lvl.name == "region"
        assert name == "Region"

        # Region filter -> District
        lvl, name = svc._get_child_level(reg.id)
        assert lvl.name == "district"
        assert name == "District"

        # District filter -> Ward
        lvl, name = svc._get_child_level(dist.id)
        assert lvl.name == "ward"
        assert name == "Ward"

        # Ward filter -> Ward (leaf returns itself)
        lvl, name = svc._get_child_level(ward.id)
        assert lvl.name == "ward"
        assert name == "Ward"

    def test_get_child_level_indonesia_5_tier(
        self, db_session: Session, monkeypatch
    ):
        """Test child level transitions with custom Indonesia 5-tier config."""
        from services.statistic_service import StatisticService

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
        monkeypatch.setattr(settings, "administrative_hierarchy", custom_cfg)

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        p_lvl = AdministrativeLevel(name="provinsi", level_index=1)
        k_lvl = AdministrativeLevel(name="kabupaten", level_index=2)
        kc_lvl = AdministrativeLevel(name="kecamatan", level_index=3)
        d_lvl = AdministrativeLevel(name="desa", level_index=4)
        db_session.add_all([c_lvl, p_lvl, k_lvl, kc_lvl, d_lvl])
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

        kec = Administrative(
            code="CLY",
            name="Cileunyi",
            level_id=kc_lvl.id,
            parent_id=kab.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi",
        )
        db_session.add(kec)
        db_session.commit()

        desa = Administrative(
            code="CBR",
            name="Cibiruhilir",
            level_id=d_lvl.id,
            parent_id=kec.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi > Cibiruhilir",
        )
        db_session.add(desa)
        db_session.commit()

        svc = StatisticService(db_session)

        # No filter -> Provinsi
        lvl, name = svc._get_child_level(None)
        assert lvl.name == "provinsi"
        assert name == "Provinsi"

        # Provinsi filter -> Kabupaten
        lvl, name = svc._get_child_level(prov.id)
        assert lvl.name == "kabupaten"
        assert name == "Kabupaten"

        # Kabupaten filter -> Kecamatan
        lvl, name = svc._get_child_level(kab.id)
        assert lvl.name == "kecamatan"
        assert name == "Kecamatan"

        # Kecamatan filter -> Desa
        lvl, name = svc._get_child_level(kec.id)
        assert lvl.name == "desa"
        assert name == "Desa"

        # Desa filter -> Desa (leaf returns itself)
        lvl, name = svc._get_child_level(desa.id)
        assert lvl.name == "desa"
        assert name == "Desa"

    def test_get_child_level_non_existent_parent_id(
        self, db_session: Session
    ):
        """Test child level fallback when administrative_id is invalid."""
        from services.statistic_service import StatisticService

        r_lvl = AdministrativeLevel(name="region", level_index=1)
        db_session.add(r_lvl)
        db_session.commit()

        svc = StatisticService(db_session)
        lvl, name = svc._get_child_level(99999)
        assert lvl.name == "region"
        assert name == "Region"

    def test_get_farmer_stats_by_ward_custom_leaf_and_filter(
        self, db_session: Session, monkeypatch
    ):
        """Test get_farmer_stats_by_ward with custom Indonesia leaf level."""
        from services.statistic_service import StatisticService

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
        monkeypatch.setattr(settings, "administrative_hierarchy", custom_cfg)

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        p_lvl = AdministrativeLevel(name="provinsi", level_index=1)
        k_lvl = AdministrativeLevel(name="kabupaten", level_index=2)
        kc_lvl = AdministrativeLevel(name="kecamatan", level_index=3)
        d_lvl = AdministrativeLevel(name="desa", level_index=4)
        db_session.add_all([c_lvl, p_lvl, k_lvl, kc_lvl, d_lvl])
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

        kec = Administrative(
            code="CLY",
            name="Cileunyi",
            level_id=kc_lvl.id,
            parent_id=kab.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi",
        )
        db_session.add(kec)
        db_session.commit()

        desa1 = Administrative(
            code="CBR",
            name="Cibiruhilir",
            level_id=d_lvl.id,
            parent_id=kec.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi > Cibiruhilir",
        )
        db_session.add(desa1)
        db_session.commit()

        cust = Customer(
            phone_number="+628111222333",
            profile_data={"crop_type": "padi"},
            onboarding_status=OnboardingStatus.COMPLETED,
            language="en",
        )
        db_session.add(cust)
        db_session.commit()

        ca = CustomerAdministrative(
            customer_id=cust.id, administrative_id=desa1.id
        )
        db_session.add(ca)
        db_session.commit()

        svc = StatisticService(db_session)

        # Query stats filtered to kab (Bandung) -> returns desa1 stats
        stats = svc.get_farmer_stats_by_ward(administrative_id=kab.id)
        assert len(stats) == 1
        assert stats[0]["ward_id"] == desa1.id
        assert stats[0]["ward_name"] == "Cibiruhilir"
        assert stats[0]["registered_farmers"] == 1

    def test_get_crop_distribution_matrix_with_custom_hierarchy(
        self, db_session: Session, monkeypatch
    ):
        """Test get_crop_distribution_matrix dynamically resolves target level."""  # noqa: E501
        from services.statistic_service import StatisticService

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
        monkeypatch.setattr(settings, "administrative_hierarchy", custom_cfg)

        c_lvl = AdministrativeLevel(name="country", level_index=0)
        p_lvl = AdministrativeLevel(name="provinsi", level_index=1)
        k_lvl = AdministrativeLevel(name="kabupaten", level_index=2)
        kc_lvl = AdministrativeLevel(name="kecamatan", level_index=3)
        d_lvl = AdministrativeLevel(name="desa", level_index=4)
        db_session.add_all([c_lvl, p_lvl, k_lvl, kc_lvl, d_lvl])
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

        kec = Administrative(
            code="CLY",
            name="Cileunyi",
            level_id=kc_lvl.id,
            parent_id=kab.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi",
        )
        db_session.add(kec)
        db_session.commit()

        desa = Administrative(
            code="CBR",
            name="Cibiruhilir",
            level_id=d_lvl.id,
            parent_id=kec.id,
            path="Indonesia > Jawa Barat > Bandung > Cileunyi > Cibiruhilir",
        )
        db_session.add(desa)
        db_session.commit()

        cust = Customer(
            phone_number="+628111222444",
            profile_data={"crop_type": "padi"},
            onboarding_status=OnboardingStatus.COMPLETED,
            language="en",
        )
        db_session.add(cust)
        db_session.commit()

        ca = CustomerAdministrative(
            customer_id=cust.id, administrative_id=desa.id
        )
        db_session.add(ca)
        db_session.commit()

        svc = StatisticService(db_session)
        # Without filter -> aggregates by target child level of country: Provinsi (Jawa Barat)  # noqa: E501
        res = svc.get_crop_distribution_matrix()
        assert res["level_name"] == "Provinsi"
        assert len(res["matrix"]) == 1
        assert res["matrix"][0]["county"] == "Jawa Barat"
        assert res["matrix"][0]["crops"].get("padi") == 1
