"""
Unit and integration tests for dynamic administration levels and seeder.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.administrative import AdministrativeLevel


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
        from config import settings

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
        from config import Settings

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
