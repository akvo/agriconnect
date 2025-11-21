import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from models import ServiceToken
from services.knowledge_base_service import KnowledgeBaseService


# ─────────────────────────────
# FIXTURES
# ─────────────────────────────
@pytest.fixture(scope="function")
def service_token(db_session: Session) -> ServiceToken:
    """Reusable fixture that creates a valid service token"""
    token = ServiceToken(
        service_name="Test Service",
        access_token="testtoken",
        chat_url="https://api.testservice.com/chat",
        upload_url="https://api.testservice.com/upload",
        kb_url="https://api.testservice.com/kb",
        document_url="https://api.testservice.com/document",
        default_prompt="You are an AI assistant.",
        active=1,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)
    return token


@pytest.fixture(scope="function")
def mock_external_ai_service():
    """
    Mock the external AI service's manage_knowledge_base method and
    is_configured check
    """
    with (
        patch(
            "services.external_ai_service.ExternalAIService.manage_knowledge_base",  # noqa
            new_callable=AsyncMock,
        ) as mock_method,
        patch(
            "services.external_ai_service.ExternalAIService.is_configured",
            return_value=True,
        ),
    ):
        mock_method.return_value = {
            "id": "mock-app-kb-id-123",
            "knowledge_base_id": "mock-kb-id-456",
            "name": "Mock KB",
            "description": "Mock KB Desc",
            "is_default": False,
        }
        yield mock_method


# ─────────────────────────────
# TEST CLASS
# ─────────────────────────────
class TestKnowledgeBaseEndpoints:

    # ─────────────────────────────
    # CREATE
    # ─────────────────────────────
    @pytest.mark.asyncio
    async def test_create_knowledge_base_success(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
        mock_external_ai_service,
    ):
        headers, user = auth_headers_factory(user_type="eo")
        payload = {
            "title": "My KB",
            "description": "Testing create",
        }

        response = client.post("/api/kb", json=payload, headers=headers)
        assert response.status_code == 201

        data = response.json()

        # DB row has NO title/description locally now
        assert data["id"] > 0
        assert data["user_id"] == user.id
        assert data["title"] == "Mock KB"
        assert data["description"] == "Mock KB Desc"

        mock_external_ai_service.assert_awaited_once_with(
            operation="create",
            name=payload["title"],
            description=payload["description"],
        )

    def test_create_knowledge_base_invalid_payload(
        self, client: TestClient, auth_headers_factory
    ):
        headers, _ = auth_headers_factory(user_type="eo")
        payload = {"description": "Missing title"}
        response = client.post("/api/kb", json=payload, headers=headers)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_kb_no_active_service_token(
        self, client: TestClient, auth_headers_factory, db_session: Session
    ):
        headers, _ = auth_headers_factory(user_type="eo")
        db_session.query(ServiceToken).delete()
        db_session.commit()

        payload = {"title": "Test KB", "description": "No service token"}
        response = client.post("/api/kb", json=payload, headers=headers)
        assert response.status_code == 404
        assert "No active service configured" in response.text

    @pytest.mark.asyncio
    async def test_create_kb_external_service_unconfigured(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, _ = auth_headers_factory(user_type="eo")

        with patch(
            "services.external_ai_service.ExternalAIService.is_configured",
            return_value=False,
        ):
            payload = {"title": "Test KB", "description": "Unconfigured AI"}
            response = client.post("/api/kb", json=payload, headers=headers)
            assert response.status_code == 503
            assert "No active AI service configured" in response.text

    # ─────────────────────────────
    # RETRIEVE
    # ─────────────────────────────
    @pytest.mark.asyncio
    async def test_get_knowledge_base_success(
        self,
        client,
        auth_headers_factory,
        db_session,
        service_token,
        mock_external_ai_service,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        response = client.get(f"/api/kb/{kb.id}", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == "Mock KB"
        assert data["description"] == "Mock KB Desc"

        mock_external_ai_service.assert_awaited_once_with(
            operation="get", kb_id="mock-kb-id-456"
        )

    def test_get_knowledge_base_not_found(self, client, auth_headers_factory):
        headers, _ = auth_headers_factory(user_type="eo")
        response = client.get("/api/kb/999999", headers=headers)
        assert response.status_code == 404

    def test_get_knowledge_base_forbidden(
        self, client, auth_headers_factory, db_session, service_token
    ):
        admin_headers, admin = auth_headers_factory(user_type="admin")
        eo_headers, eo_user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=admin.id,
            external_id="test-ext-id",
            service_id=service_token.id,
        )

        response = client.get(f"/api/kb/{kb.id}", headers=eo_headers)
        assert response.status_code == 403

    # ─────────────────────────────
    # UPDATE
    # ─────────────────────────────
    @pytest.mark.asyncio
    async def test_update_knowledge_base_success(
        self,
        client,
        auth_headers_factory,
        db_session,
        service_token,
        mock_external_ai_service,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        payload = {
            "title": "Updated KB",
            "description": "Updated Desc",
        }

        response = client.put(
            f"/api/kb/{kb.id}", json=payload, headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == "Mock KB"
        assert data["description"] == "Mock KB Desc"

        mock_external_ai_service.assert_awaited_once_with(
            operation="update",
            name=payload["title"],
            description=payload["description"],
            kb_id="mock-kb-id-456",
        )

    def test_update_knowledge_base_forbidden(
        self, client, auth_headers_factory, db_session, service_token
    ):
        admin_headers, admin = auth_headers_factory(user_type="admin")
        eo_headers, eo_user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=admin.id,
            external_id="test-ext-id",
            service_id=service_token.id,
        )

        response = client.put(
            f"/api/kb/{kb.id}",
            json={"title": "Hacking attempt"},
            headers=eo_headers,
        )
        assert response.status_code == 403

    # ─────────────────────────────
    # DELETE
    # ─────────────────────────────
    @pytest.mark.asyncio
    async def test_delete_knowledge_base_success(
        self,
        client,
        auth_headers_factory,
        db_session,
        service_token,
        mock_external_ai_service,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        response = client.delete(f"/api/kb/{kb.id}", headers=headers)
        assert response.status_code == 200
        assert (
            response.json()["message"]
            == "Knowledge base deleted successfully."
        )

        mock_external_ai_service.assert_awaited_once_with(
            operation="delete",
            kb_id="mock-kb-id-456",
        )

    def test_delete_knowledge_base_not_found(
        self, client, auth_headers_factory
    ):
        headers, _ = auth_headers_factory(user_type="eo")
        response = client.delete("/api/kb/99999", headers=headers)
        assert response.status_code == 404

    def test_delete_knowledge_base_forbidden(
        self, client, auth_headers_factory, db_session, service_token
    ):
        admin_headers, admin = auth_headers_factory(user_type="admin")
        eo_headers, eo_user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=admin.id,
            external_id="ext-kb-123",
            service_id=service_token.id,
        )

        response = client.delete(f"/api/kb/{kb.id}", headers=eo_headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_delete_any_kb(
        self,
        client,
        auth_headers_factory,
        db_session,
        service_token,
        mock_external_ai_service,
    ):
        eo_headers, eo_user = auth_headers_factory(user_type="eo")
        admin_headers, admin = auth_headers_factory(user_type="admin")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=eo_user.id,
            external_id="ext-kb-123",
            service_id=service_token.id,
        )

        response = client.delete(f"/api/kb/{kb.id}", headers=admin_headers)
        assert response.status_code == 200
        assert (
            response.json()["message"]
            == "Knowledge base deleted successfully."
        )

        mock_external_ai_service.assert_awaited_once_with(
            operation="delete",
            kb_id="ext-kb-123",
        )
