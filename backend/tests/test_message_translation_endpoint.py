import uuid
import pytest
from unittest.mock import patch
from passlib.context import CryptContext

from models.user import User, UserType


class TestMessageTranslationsEndpoints:
    """Test suite for /api/messages endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self, client, db_session):
        """Setup test data before each test"""
        self.db = db_session
        self.client = client
        self.pwd_context = CryptContext(
            schemes=["bcrypt"], deprecated="auto"
        )

        # Create Admin user
        unique_id = str(uuid.uuid4())[:8]
        self.admin_user = User(
            email=f"admin-{unique_id}@example.com",
            phone_number=f"+987654321{unique_id[:3]}",
            hashed_password=self.pwd_context.hash("adminpassword123"),
            full_name="Admin User",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        self.db.add(self.admin_user)
        self.db.commit()
        self.db.refresh(self.admin_user)

    def _get_auth_headers(self, user: User) -> dict:
        """Generate authentication headers for a user"""
        from utils.auth import create_access_token

        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}

    def test_translate_message_success(self):
        """Test successful translation of a message"""
        with patch(
            "services.openai_service.OpenAIService.translate_text",
            return_value="Hujambo, Habari gani?",
        ):
            source = "en"
            target = "sw"
            response = self.client.get(
                (
                    f"/api/messages/translate/{source}/{target}"
                    "?text=Hello,%20how%20are%20you?"
                ),
                headers=self._get_auth_headers(self.admin_user),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["translated_text"] == "Hujambo, Habari gani?"

    def test_internal_server_error(self):
        """Test handling of internal server error during translation"""
        with patch(
            "services.openai_service.OpenAIService.translate_text",
            side_effect=Exception("Internal Server Error"),
        ):
            source = "en"
            target = "sw"
            response = self.client.get(
                (
                    f"/api/messages/translate/{source}/{target}"
                    "?text=Hello,%20how%20are%20you?"
                ),
                headers=self._get_auth_headers(self.admin_user),
            )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Translation failed: Internal Server Error"
