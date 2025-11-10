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
        # Default mock return value for manage_knowledge_base
        mock_method.return_value = {
            "id": "mock-app-kb-id-123",
            "knowledge_base_id": "mock-kb-id-456",
            "name": "mock-kb-name",
            "description": "mock-kb-description",
            "is_default": False,
        }
        yield mock_method


# ─────────────────────────────
# TEST CLASS
# ─────────────────────────────
class TestKnowledgeBaseEndpoints:
    """Comprehensive tests for Knowledge Base API"""

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
            "title": "My Knowledge Base",
            "description": "This is a new KB for testing.",
            "extra_data": {"topic": "AI"},
        }

        response = client.post("/api/kb", json=payload, headers=headers)
        assert response.status_code == 201

        data = response.json()
        assert data["title"] == payload["title"]
        assert data["description"] == payload["description"]
        assert data["user_id"] == user.id

        mock_external_ai_service.assert_awaited_once_with(
            operation="create",
            name=payload["title"],
            description=payload["description"],
        )

    def test_create_knowledge_base_invalid_payload(
        self, client: TestClient, auth_headers_factory
    ):
        headers, _ = auth_headers_factory(user_type="eo")
        payload = {"description": "Missing required title field"}
        response = client.post("/api/kb", json=payload, headers=headers)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_kb_no_active_service_token(
        self, client: TestClient, auth_headers_factory, db_session: Session
    ):
        headers, _ = auth_headers_factory(user_type="eo")
        # Ensure no active service token
        db_session.query(ServiceToken).delete()
        db_session.commit()

        payload = {"title": "Test KB", "description": "No active service"}
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
    # LIST / SEARCH / PAGINATION
    # ─────────────────────────────
    def test_list_knowledge_bases_user(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")
        for i in range(5):
            KnowledgeBaseService.create_knowledge_base(
                db=db_session,
                user_id=user.id,
                title=f"User KB {i}",
                description=f"Test KB {i}",
                service_id=service_token.id,
            )
        db_session.commit()

        response = client.get("/api/kb?page=1&size=3", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) <= 3
        assert data["total"] >= 5

    def test_list_knowledge_bases_with_search(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")
        KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            title="AI Farming",
            service_id=service_token.id,
        )
        KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            title="Soil Health",
            service_id=service_token.id,
        )

        response = client.get("/api/kb?search=AI", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert any("AI" in kb["title"] for kb in data["data"])

    # ─────────────────────────────
    # RETRIEVE
    # ─────────────────────────────
    def test_get_knowledge_base_success(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session,
        service_token,
    ):
        headers, user = auth_headers_factory(user_type="eo")
        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            title="Get KB",
            description="desc",
            service_id=service_token.id,
        )
        response = client.get(f"/api/kb/{kb.id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Get KB"

    def test_get_knowledge_base_not_found(self, client, auth_headers_factory):
        headers, _ = auth_headers_factory(user_type="eo")
        response = client.get("/api/kb/nonexistent-id", headers=headers)
        assert response.status_code == 404

    def test_get_knowledge_base_forbidden(
        self, client, auth_headers_factory, db_session, service_token
    ):
        admin_headers, admin = auth_headers_factory(user_type="admin")
        eo_headers, eo_user = auth_headers_factory(user_type="eo")
        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=admin.id,
            title="Admin KB",
            description="Private",
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
            title="Old KB",
            description="Old Desc",
            service_id=service_token.id,
        )
        payload = {"title": "Updated KB", "description": "Updated Desc"}
        response = client.put(
            f"/api/kb/{kb.id}", json=payload, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated KB"
        assert data["description"] == "Updated Desc"
        mock_external_ai_service.assert_awaited_once_with(
            operation="update",
            name=payload["title"],
            description=payload["description"],
            kb_id=str(kb.id),
        )

    def test_update_knowledge_base_forbidden(
        self, client, auth_headers_factory, db_session, service_token
    ):
        admin_headers, admin = auth_headers_factory(user_type="admin")
        eo_headers, eo_user = auth_headers_factory(user_type="eo")
        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=admin.id,
            title="Admin Private KB",
            service_id=service_token.id,
        )
        response = client.put(
            f"/api/kb/{kb.id}",
            json={"title": "Hack Attempt"},
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
            title="Delete Me",
            service_id=service_token.id,
        )
        response = client.delete(f"/api/kb/{kb.id}", headers=headers)
        assert response.status_code == 200
        assert (
            response.json()["message"]
            == "Knowledge base deleted successfully."
        )
        mock_external_ai_service.assert_awaited_once_with(
            operation="delete", kb_id=str(kb.id)
        )

    def test_delete_knowledge_base_not_found(
        self, client, auth_headers_factory
    ):
        headers, _ = auth_headers_factory(user_type="eo")
        response = client.delete("/api/kb/nonexistent-id", headers=headers)
        assert response.status_code == 404

    def test_delete_knowledge_base_forbidden(
        self, client, auth_headers_factory, db_session, service_token
    ):
        admin_headers, admin = auth_headers_factory(user_type="admin")
        eo_headers, eo_user = auth_headers_factory(user_type="eo")
        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=admin.id,
            title="Private Admin KB",
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
            title="EO KB",
            service_id=service_token.id,
        )
        response = client.delete(f"/api/kb/{kb.id}", headers=admin_headers)
        assert response.status_code == 200
        assert (
            response.json()["message"]
            == "Knowledge base deleted successfully."
        )
        mock_external_ai_service.assert_awaited_once_with(
            operation="delete", kb_id=str(kb.id)
        )
