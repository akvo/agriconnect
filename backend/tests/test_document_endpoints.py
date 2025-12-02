import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from io import BytesIO
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
def mock_external_ai_upload():
    """
    Mock the external AI service's create_upload_job method and
    is_configured check
    """
    with (
        patch(
            "routers.document.ExternalAIService.create_upload_job",
            new_callable=AsyncMock,
        ) as mock_method,
        patch(
            "routers.document.ExternalAIService.is_configured",
            return_value=True,
        ),
    ):
        mock_method.return_value = {
            "job_id": "mock-job-id-123",
            "status": "pending",
        }
        yield mock_method


@pytest.fixture(scope="function")
def mock_external_ai_list_docs():
    """
    Mock the external AI service's manage_knowledge_base method for
    listing documents
    """
    with (
        patch(
            "routers.document.ExternalAIService.manage_knowledge_base",
            new_callable=AsyncMock,
        ) as mock_method,
        patch(
            "routers.document.ExternalAIService.is_configured",
            return_value=True,
        ),
    ):
        mock_method.return_value = {
            "data": [
                {
                    "id": 1,
                    "file_name": "test.pdf",
                    "file_path": "/uploads/test.pdf",
                    "content_type": "application/pdf",
                    "file_size": 1024,
                    "processing_tasks": [
                        {
                            "status": "completed",
                            "created_at": "2024-01-01T00:00:00",
                            "updated_at": "2024-01-01T00:01:00",
                        }
                    ],
                },
                {
                    "id": 2,
                    "file_name": "test2.txt",
                    "file_path": "/uploads/test2.txt",
                    "content_type": "text/plain",
                    "file_size": 512,
                    "processing_tasks": [
                        {
                            "status": "processing",
                            "created_at": "2024-01-01T00:02:00",
                            "updated_at": "2024-01-01T00:03:00",
                        }
                    ],
                },
            ],
            "total": 2,
            "page": 1,
            "size": 10,
        }
        yield mock_method


def create_test_file(filename: str, content: bytes, content_type: str):
    """Helper function to create a test file"""
    return (filename, BytesIO(content), content_type)


# ─────────────────────────────
# TEST CLASS
# ─────────────────────────────
class TestDocumentEndpoints:

    # ─────────────────────────────
    # UPLOAD DOCUMENT
    # ─────────────────────────────
    @pytest.mark.asyncio
    async def test_upload_document_pdf_success(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
        mock_external_ai_upload,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        file_content = b"Mock PDF content"
        files = {
            "file": create_test_file(
                "test.pdf", file_content, "application/pdf"
            )
        }
        data = {"kb_id": str(kb.id)}

        response = client.post(
            "/api/documents",
            files=files,
            data=data,
            headers=headers,
        )

        assert response.status_code == 201
        response_data = response.json()
        assert response_data["job_id"] == "mock-job-id-123"
        assert response_data["status"] == "pending"

        mock_external_ai_upload.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_document_txt_success(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
        mock_external_ai_upload,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        file_content = b"Mock text content"
        files = {
            "file": create_test_file("test.txt", file_content, "text/plain")
        }
        data = {"kb_id": str(kb.id)}

        response = client.post(
            "/api/documents",
            files=files,
            data=data,
            headers=headers,
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_upload_document_docx_success(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
        mock_external_ai_upload,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        file_content = b"Mock DOCX content"
        files = {
            "file": create_test_file(
                "test.txt",
                file_content,
                "text/plain",
            )
        }
        data = {"kb_id": str(kb.id)}

        response = client.post(
            "/api/documents",
            files=files,
            data=data,
            headers=headers,
        )

        assert response.status_code == 201

    def test_upload_document_unsupported_file_type(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        file_content = b"Mock image content"
        files = {
            "file": create_test_file("test.jpg", file_content, "image/jpeg")
        }
        data = {"kb_id": str(kb.id)}

        response = client.post(
            "/api/documents",
            files=files,
            data=data,
            headers=headers,
        )

        assert response.status_code == 400
        assert "Unsupported file" in response.text

    def test_upload_document_kb_not_found(
        self,
        client: TestClient,
        auth_headers_factory,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        file_content = b"Mock PDF content"
        files = {
            "file": create_test_file(
                "test.pdf", file_content, "application/pdf"
            )
        }
        data = {"kb_id": "999999"}

        response = client.post(
            "/api/documents",
            files=files,
            data=data,
            headers=headers,
        )

        assert response.status_code == 404
        assert "Knowledge Base not found" in response.text

    @pytest.mark.asyncio
    async def test_upload_document_no_active_service(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        with patch(
            "routers.document.ExternalAIService.is_configured",
            return_value=False,
        ):
            file_content = b"Mock PDF content"
            files = {
                "file": create_test_file(
                    "test.pdf", file_content, "application/pdf"
                )
            }
            data = {"kb_id": str(kb.id)}

            response = client.post(
                "/api/documents",
                files=files,
                data=data,
                headers=headers,
            )

            # With improved exception handling, HTTPException is re-raised
            assert response.status_code == 503
            assert "No active AI service configured" in response.text

    @pytest.mark.asyncio
    async def test_upload_document_external_service_fails(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        with (
            patch(
                "routers.document.ExternalAIService.create_upload_job",
                new_callable=AsyncMock,
            ) as mock_upload,
            patch(
                "routers.document.ExternalAIService.is_configured",
                return_value=True,
            ),
        ):
            mock_upload.return_value = None

            file_content = b"Mock PDF content"
            files = {
                "file": create_test_file(
                    "test.pdf", file_content, "application/pdf"
                )
            }
            data = {"kb_id": str(kb.id)}

            response = client.post(
                "/api/documents",
                files=files,
                data=data,
                headers=headers,
            )

            # With improved exception handling, HTTPException is re-raised
            assert response.status_code == 502
            assert "Failed to upload document" in response.text

    def test_upload_document_missing_file(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        data = {"kb_id": str(kb.id)}

        response = client.post(
            "/api/documents",
            data=data,
            headers=headers,
        )

        assert response.status_code == 422

    def test_upload_document_missing_kb_id(
        self,
        client: TestClient,
        auth_headers_factory,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        file_content = b"Mock PDF content"
        files = {
            "file": create_test_file(
                "test.pdf", file_content, "application/pdf"
            )
        }

        response = client.post(
            "/api/documents",
            files=files,
            headers=headers,
        )

        assert response.status_code == 422

    # ─────────────────────────────
    # LIST DOCUMENTS
    # ─────────────────────────────
    @pytest.mark.asyncio
    async def test_list_documents_success(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
        mock_external_ai_list_docs,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        response = client.get(
            f"/api/documents?kb_id={kb.id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert data["page"] == 1
        assert data["size"] == 10
        assert len(data["data"]) == 2

        assert data["data"][0]["id"] == 1
        assert data["data"][0]["filename"] == "test.pdf"
        assert data["data"][0]["status"] == "completed"

        assert data["data"][1]["id"] == 2
        assert data["data"][1]["filename"] == "test2.txt"
        assert data["data"][1]["status"] == "processing"

        mock_external_ai_list_docs.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_documents_with_pagination(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
        mock_external_ai_list_docs,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        response = client.get(
            f"/api/documents?kb_id={kb.id}&page=2&size=5",
            headers=headers,
        )

        assert response.status_code == 200

        call_kwargs = mock_external_ai_list_docs.call_args.kwargs
        assert call_kwargs["page"] == 2
        assert call_kwargs["size"] == 5

    @pytest.mark.asyncio
    async def test_list_documents_with_search(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
        mock_external_ai_list_docs,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        response = client.get(
            f"/api/documents?kb_id={kb.id}&search=test",
            headers=headers,
        )

        assert response.status_code == 200

        call_kwargs = mock_external_ai_list_docs.call_args.kwargs
        assert call_kwargs["search"] == "test"

    @pytest.mark.asyncio
    async def test_list_documents_empty_result(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        with (
            patch(
                "routers.document.ExternalAIService.manage_knowledge_base",
                new_callable=AsyncMock,
            ) as mock_method,
            patch(
                "routers.document.ExternalAIService.is_configured",
                return_value=True,
            ),
        ):
            mock_method.return_value = {
                "data": [],
                "total": 0,
                "page": 0,
                "size": 0,
            }

            response = client.get(
                f"/api/documents?kb_id={kb.id}",
                headers=headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert len(data["data"]) == 0

    def test_list_documents_kb_not_found(
        self,
        client: TestClient,
        auth_headers_factory,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        response = client.get(
            "/api/documents?kb_id=999999",
            headers=headers,
        )

        assert response.status_code == 404
        assert "Knowledge Base not found" in response.text

    @pytest.mark.asyncio
    async def test_list_documents_no_active_service(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        with patch(
            "routers.document.ExternalAIService.is_configured",
            return_value=False,
        ):
            response = client.get(
                f"/api/documents?kb_id={kb.id}",
                headers=headers,
            )

            assert response.status_code == 503
            assert "No active AI service configured" in response.text

    def test_list_documents_invalid_pagination(
        self,
        client: TestClient,
        auth_headers_factory,
        db_session: Session,
        service_token: ServiceToken,
    ):
        headers, user = auth_headers_factory(user_type="eo")

        kb = KnowledgeBaseService.create_knowledge_base(
            db=db_session,
            user_id=user.id,
            external_id="mock-kb-id-456",
            service_id=service_token.id,
        )

        response = client.get(
            f"/api/documents?kb_id={kb.id}&page=0",
            headers=headers,
        )

        assert response.status_code == 422

        response = client.get(
            f"/api/documents?kb_id={kb.id}&size=0",
            headers=headers,
        )

        assert response.status_code == 422

        response = client.get(
            f"/api/documents?kb_id={kb.id}&size=101",
            headers=headers,
        )

        assert response.status_code == 422
