from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import (
    Administrative,
    AdministrativeLevel,
)


class TestAdministrativeAPI:
    """Test cases for administrative API endpoints"""

    def test_get_administrative_levels(
        self, client: TestClient, db_session: Session
    ):
        """Test getting administrative levels"""
        # Setup test data
        country_level = AdministrativeLevel(name="country")
        region_level = AdministrativeLevel(name="region")
        district_level = AdministrativeLevel(name="district")
        ward_level = AdministrativeLevel(name="ward")
        db_session.add_all(
            [country_level, region_level, district_level, ward_level]
        )
        db_session.commit()

        response = client.get("/api/administrative/levels")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 4
        assert "country" in data
        assert "region" in data
        assert "district" in data
        assert "ward" in data
        # Should be sorted alphabetically
        assert data == sorted(data)

    def test_get_administrative_levels_empty(
        self, client: TestClient, db_session: Session
    ):
        """Test getting administrative levels when none exist"""
        response = client.get("/api/administrative/levels")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 0

    def test_get_public_administrative_list(
        self, client: TestClient, db_session: Session
    ):
        """Test public administrative list endpoint"""
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

        response = client.get("/api/administrative/?level=country")
        assert response.status_code == 200

        data = response.json()
        assert "administrative" in data
        assert "total" in data
        assert len(data["administrative"]) == 1
        assert data["total"] == 1
        # Check lightweight response format
        item = data["administrative"][0]
        assert "id" in item
        assert "name" in item
        assert "code" not in item  # Should not be in lightweight response
        assert "level" not in item  # Should not be in lightweight response
        assert "path" not in item  # Should not be in lightweight response

    def test_get_administrative_missing_parameters(
        self, client: TestClient, db_session: Session
    ):
        """Test administrative endpoint with missing required parameters"""
        response = client.get("/api/administrative/")
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
        assert (
            "Either 'level' or 'parent_id' parameter is required"
            in data["detail"]
        )

    def test_get_administrative_by_level_filter(
        self, client: TestClient, db_session: Session
    ):
        """Test administrative endpoint with level filter"""
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
        db_session.commit()  # Commit Kenya first to get its ID

        nairobi = Administrative(
            code="NBI",
            name="Nairobi Region",
            level_id=region_level.id,
            parent_id=kenya.id,
            path="KEN.NBI",
        )
        db_session.add(nairobi)
        db_session.commit()

        response = client.get("/api/administrative/?level=region")
        assert response.status_code == 200

        data = response.json()
        assert len(data["administrative"]) == 1
        # Check lightweight response format
        item = data["administrative"][0]
        assert "id" in item
        assert "name" in item
        assert "code" not in item  # Should not be in lightweight response
        assert "level" not in item  # Should not be in lightweight response
        assert "path" not in item  # Should not be in lightweight response
        assert data["total"] == 1
