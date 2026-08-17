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
