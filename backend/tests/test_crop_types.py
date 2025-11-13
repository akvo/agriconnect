from models.customer import CropType


class TestCropTypeAPI:
    """Tests for the Crop Types API endpoints."""

    def test_get_crop_types_empty(self, client, db_session):
        # Clean up any existing crop types
        db_session.query(CropType).delete()
        db_session.commit()
        response = client.get("/api/crop-types/")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_crop_types_with_data(self, client, db_session):
        # Seed some crop types
        crop_types = [
            CropType(name="Maize"),
            CropType(name="Wheat"),
            CropType(name="Rice")
        ]
        db_session.add_all(crop_types)
        db_session.commit()

        response = client.get("/api/crop-types/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        names = [ct["name"] for ct in data]
        assert "Maize" in names
        assert "Wheat" in names
        assert "Rice" in names
