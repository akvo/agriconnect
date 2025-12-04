from unittest.mock import patch


class TestCropTypeAPI:
    """Tests for the Crop Types API endpoints."""

    def test_get_crop_types_empty(self, client):
        # mock config to have no crop types
        with patch("config.settings.crop_types", []):
            response = client.get("/api/crop-types/")
            assert response.status_code == 200
            assert response.json() == []

    def test_get_crop_types_with_data(self, client):
        # mock config to have some crop types
        with patch(
            "config.settings.crop_types",
            ["Maize", "Wheat", "Rice"]
        ):
            response = client.get("/api/crop-types/")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3
            names = [ct["name"] for ct in data]
            assert "Maize" in names
            assert "Wheat" in names
            assert "Rice" in names
