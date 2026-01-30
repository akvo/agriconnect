"""
Tests for Weather Router endpoints.
"""

from unittest.mock import AsyncMock, patch

from fastapi import status
from passlib.context import CryptContext

from models.user import User, UserType


class TestWeatherRouter:
    """Test suite for weather router endpoints"""

    def _create_admin_and_login(self, client, db_session):
        """Helper to create admin user and get token"""
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("testpass123")

        admin_user = User(
            email="weatheradmin@test.com",
            phone_number="+1234567899",
            hashed_password=hashed_password,
            full_name="Weather Admin",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()

        login_response = client.post(
            "/api/auth/login/",
            json={"email": "weatheradmin@test.com", "password": "testpass123"},
        )
        return login_response.json()["access_token"]

    def test_test_message_requires_auth(self, client):
        """Test that endpoint requires authentication"""
        response = client.post(
            "/api/admin/weather/test-message",
            json={"location": "Nairobi", "language": "en"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_test_message_requires_admin(self, client, db_session):
        """Test that endpoint requires admin role"""
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("testpass123")

        # Create non-admin user
        eo_user = User(
            email="eo@test.com",
            phone_number="+1234567898",
            hashed_password=hashed_password,
            full_name="EO User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(eo_user)
        db_session.commit()

        login_response = client.post(
            "/api/auth/login/",
            json={"email": "eo@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        response = client.post(
            "/api/admin/weather/test-message",
            json={"location": "Nairobi", "language": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_test_message_success(self, client, db_session):
        """Test successful weather message generation"""
        token = self._create_admin_and_login(client, db_session)

        with patch(
            "routers.weather.get_weather_broadcast_service"
        ) as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_weather_data.return_value = {"temp": 25}
            mock_instance.generate_message = AsyncMock(
                return_value="Good morning! Sunny day ahead."
            )

            response = client.post(
                "/api/admin/weather/test-message",
                json={"location": "Nairobi", "language": "en"},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.text == "Good morning! Sunny day ahead."
            mock_instance.get_weather_data.assert_called_once_with(
                location="Nairobi",
                lat=None,
                lon=None,
            )
            mock_instance.generate_message.assert_called_once_with(
                location="Nairobi",
                language="en",
                weather_data={"temp": 25},
            )

    def test_test_message_swahili(self, client, db_session):
        """Test weather message generation in Swahili"""
        token = self._create_admin_and_login(client, db_session)

        with patch(
            "routers.weather.get_weather_broadcast_service"
        ) as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_weather_data.return_value = {"temp": 28}
            mock_instance.generate_message = AsyncMock(
                return_value="Habari za asubuhi! Siku ya jua."
            )

            response = client.post(
                "/api/admin/weather/test-message",
                json={"location": "Dar es Salaam", "language": "sw"},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.text == "Habari za asubuhi! Siku ya jua."
            mock_instance.get_weather_data.assert_called_once_with(
                location="Dar es Salaam",
                lat=None,
                lon=None,
            )
            mock_instance.generate_message.assert_called_once_with(
                location="Dar es Salaam",
                language="sw",
                weather_data={"temp": 28},
            )

    def test_test_message_service_failure(self, client, db_session):
        """Test handling of service failure"""
        token = self._create_admin_and_login(client, db_session)

        with patch(
            "routers.weather.get_weather_broadcast_service"
        ) as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.generate_message = AsyncMock(return_value=None)

            response = client.post(
                "/api/admin/weather/test-message",
                json={"location": "InvalidLocation", "language": "en"},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == (
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            assert "Failed to generate" in response.json()["detail"]

    def test_test_message_invalid_language(self, client, db_session):
        """Test validation of language enum"""
        token = self._create_admin_and_login(client, db_session)

        response = client.post(
            "/api/admin/weather/test-message",
            json={"location": "Nairobi", "language": "invalid"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_test_message_missing_location(self, client, db_session):
        """Test validation of required location field"""
        token = self._create_admin_and_login(client, db_session)

        response = client.post(
            "/api/admin/weather/test-message",
            json={"language": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_test_message_empty_location(self, client, db_session):
        """Test validation of empty location"""
        token = self._create_admin_and_login(client, db_session)

        response = client.post(
            "/api/admin/weather/test-message",
            json={"location": "", "language": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_test_message_default_language(self, client, db_session):
        """Test that language defaults to English"""
        token = self._create_admin_and_login(client, db_session)

        with patch(
            "routers.weather.get_weather_broadcast_service"
        ) as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_weather_data.return_value = {"temp": 22}
            mock_instance.generate_message = AsyncMock(
                return_value="Weather message"
            )

            response = client.post(
                "/api/admin/weather/test-message",
                json={"location": "Nairobi"},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == status.HTTP_200_OK
            mock_instance.get_weather_data.assert_called_once_with(
                location="Nairobi",
                lat=None,
                lon=None,
            )
            mock_instance.generate_message.assert_called_once_with(
                location="Nairobi",
                language="en",
                weather_data={"temp": 22},
            )

    # Tests for trigger-broadcast endpoint

    def test_trigger_broadcast_requires_auth(self, client):
        """Test that trigger endpoint requires authentication"""
        response = client.post("/api/admin/weather/trigger-broadcast")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_trigger_broadcast_requires_admin(self, client, db_session):
        """Test that trigger endpoint requires admin role"""
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("testpass123")

        eo_user = User(
            email="eo_trigger@test.com",
            phone_number="+1234567897",
            hashed_password=hashed_password,
            full_name="EO User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        db_session.add(eo_user)
        db_session.commit()

        login_response = client.post(
            "/api/auth/login/",
            json={"email": "eo_trigger@test.com", "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        response = client.post(
            "/api/admin/weather/trigger-broadcast",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_trigger_broadcast_success(self, client, db_session):
        """Test successful weather broadcast trigger"""
        token = self._create_admin_and_login(client, db_session)

        with patch(
            "routers.weather.get_weather_broadcast_service"
        ) as mock_service, patch(
            "routers.weather.send_weather_broadcasts"
        ) as mock_task:
            mock_instance = mock_service.return_value
            mock_instance.is_configured.return_value = True

            mock_task_result = mock_task.delay.return_value
            mock_task_result.id = "test-task-id-123"

            response = client.post(
                "/api/admin/weather/trigger-broadcast",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert data["status"] == "queued"
            assert data["task_id"] == "test-task-id-123"
            assert "successfully" in data["message"]
            mock_task.delay.assert_called_once()

    def test_trigger_broadcast_not_configured(self, client, db_session):
        """Test trigger fails when service not configured"""
        token = self._create_admin_and_login(client, db_session)

        with patch(
            "routers.weather.get_weather_broadcast_service"
        ) as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.is_configured.return_value = False

            response = client.post(
                "/api/admin/weather/trigger-broadcast",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "not configured" in response.json()["detail"]
