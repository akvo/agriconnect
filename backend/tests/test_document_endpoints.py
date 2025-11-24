# import io
# import pytest
# from unittest.mock import AsyncMock, patch
# from fastapi import status
# from fastapi.testclient import TestClient
# from sqlalchemy.orm import Session

# from models import ServiceToken
# from services.knowledge_base_service import KnowledgeBaseService


# @pytest.fixture(scope="function")
# def service_token(db_session: Session) -> ServiceToken:
#     """
#     Reusable fixture that creates a valid service token for external service.
#     """
#     token = ServiceToken(
#         service_name="Test Service",
#         access_token="testtoken",
#         chat_url="https://api.testservice.com/chat",
#         upload_url="https://api.testservice.com/upload",
#         kb_url="https://api.testservice.com/kb",
#         document_url="https://api.testservice.com/document",
#         default_prompt="You are an AI assistant.",
#         active=1,
#     )
#     db_session.add(token)
#     db_session.commit()
#     db_session.refresh(token)
#     return token


# @pytest.fixture(scope="function")
# def mock_external_ai_upload():
#     """Mock for ExternalAIService.create_upload_job."""
#     with patch(
#         "services.external_ai_service.ExternalAIService.create_upload_job",
#         new_callable=AsyncMock,
#     ) as mock_method:
#         mock_method.return_value = {
#             "job_id": "mock-job-123",
#             "status": "uploaded",
#             "external_id": "rag-doc-456",
#         }
#         yield mock_method


# class TestDocumentEndpoints:
#     """Test suite for /documents API endpoints."""

#     # ─────────────────────────────
#     # CREATE DOCUMENT
#     # ─────────────────────────────
#     @pytest.mark.asyncio
#     async def test_create_document_success(
#         self,
#         client: TestClient,
#         auth_headers_factory,
#         db_session: Session,
#         service_token: ServiceToken,
#         mock_external_ai_upload,
#     ):
#         headers, user = auth_headers_factory(user_type="eo")

#         kb = KnowledgeBaseService.create_knowledge_base(
#             db=db_session,
#             user_id=user.id,
#             title="Docs KB",
#             description="Docs for testing",
#             service_id=service_token.id,
#         )

#         # Prepare file upload
#         file_content = io.BytesIO(b"dummy pdf content")
#         files = {
#             "file": ("test.pdf", file_content, "application/pdf"),
#         }
#         data = {
#             "kb_id": str(kb.id),
#             "title": "Test Document",
#             "description": "Sample file for upload test",
#         }

#         response = client.post(
#             "/api/documents", files=files, data=data, headers=headers
#         )
#         assert response.status_code == status.HTTP_201_CREATED
#         json_data = response.json()

#         assert json_data["filename"] == "test.pdf"
#         assert json_data["kb_id"] == str(kb.id)
#         assert json_data["user_id"] == user.id

#         mock_external_ai_upload.assert_awaited_once()

#     def test_create_document_invalid_file_type(
#         self,
#         client: TestClient,
#         auth_headers_factory,
#         db_session: Session,
#         service_token: ServiceToken,
#     ):
#         headers, user = auth_headers_factory(user_type="eo")
#         kb = KnowledgeBaseService.create_knowledge_base(
#             db=db_session,
#             user_id=user.id,
#             title="KB Invalid Type",
#             service_id=service_token.id,
#         )

#         file_content = io.BytesIO(b"fake image")
#         files = {"file": ("hack.png", file_content, "image/png")}
#         data = {
#             "kb_id": str(kb.id),
#             "title": "Invalid",
#             "description": "Should fail",
#         }

#         response = client.post(
#             "/api/documents", files=files, data=data, headers=headers
#         )
#         assert response.status_code == status.HTTP_400_BAD_REQUEST

#     def test_create_document_kb_not_found(
#         self,
#         client: TestClient,
#         auth_headers_factory,
#     ):
#         headers, _ = auth_headers_factory(user_type="eo")
#         file_content = io.BytesIO(b"some text")
#         files = {"file": ("note.txt", file_content, "text/plain")}
#         data = {"kb_id": "nonexistent", "title": "Lost Doc"}

#         response = client.post(
#             "/api/documents", files=files, data=data, headers=headers
#         )
#         assert response.status_code == status.HTTP_404_NOT_FOUND

#     # ─────────────────────────────
#     # LIST DOCUMENTS
#     # ─────────────────────────────
#     def test_list_documents_user_filter(
#         self,
#         client: TestClient,
#         auth_headers_factory,
#         db_session: Session,
#         service_token: ServiceToken,
#     ):
#         headers, user = auth_headers_factory(user_type="eo")

#         kb = KnowledgeBaseService.create_knowledge_base(
#             db=db_session,
#             user_id=user.id,
#             title="KB",
#             service_id=service_token.id,
#         )

#         for i in range(5):
#             DocumentService.create_document(
#                 db=db_session,
#                 kb_id=str(kb.id),
#                 user_id=user.id,
#                 filename=f"file_{i}.pdf",
#                 content_type="application/pdf",
#                 file_size=1000,
#             )

#         db_session.commit()
#         response = client.get(
# "/api/documents?page=1&size=3", headers=headers)
#         assert response.status_code == 200
#         data = response.json()
#         assert "data" in data
#         assert len(data["data"]) <= 3
#         assert data["total"] >= 5

#     # ─────────────────────────────
#     # RETRIEVE
#     # ─────────────────────────────
#     def test_get_document_success(
#         self,
#         client: TestClient,
#         auth_headers_factory,
#         db_session: Session,
#         service_token: ServiceToken,
#     ):
#         headers, user = auth_headers_factory(user_type="eo")
#         kb = KnowledgeBaseService.create_knowledge_base(
#             db=db_session,
#             user_id=user.id,
#             title="KB",
#             service_id=service_token.id,
#         )
#         doc = DocumentService.create_document(
#             db=db_session,
#             kb_id=str(kb.id),
#             user_id=user.id,
#             filename="mydoc.pdf",
#             content_type="application/pdf",
#         )

#         response = client.get(f"/api/documents/{doc.id}", headers=headers)
#         assert response.status_code == 200
#         data = response.json()
#         assert data["filename"] == "mydoc.pdf"

#     def test_get_document_not_found(
#         self, client: TestClient, auth_headers_factory
#     ):
#         headers, _ = auth_headers_factory(user_type="eo")
#         response = client.get("/api/documents/9999", headers=headers)
#         assert response.status_code == 404

#     def test_get_document_forbidden(
#         self,
#         client: TestClient,
#         auth_headers_factory,
#         db_session: Session,
#         service_token: ServiceToken,
#     ):
#         admin_headers, admin = auth_headers_factory(user_type="admin")
#         eo_headers, eo_user = auth_headers_factory(user_type="eo")

#         kb = KnowledgeBaseService.create_knowledge_base(
#             db=db_session,
#             user_id=admin.id,
#             title="KB",
#             service_id=service_token.id,
#         )
#         doc = DocumentService.create_document(
#             db=db_session,
#             kb_id=str(kb.id),
#             user_id=admin.id,
#             filename="secret.pdf",
#             content_type="application/pdf",
#         )

#         response = client.get(f"/api/documents/{doc.id}", headers=eo_headers)
#         assert response.status_code == 403

#     # ─────────────────────────────
#     # UPDATE
#     # ─────────────────────────────
#     def test_update_document_success(
#         self,
#         client: TestClient,
#         auth_headers_factory,
#         db_session: Session,
#         service_token: ServiceToken,
#     ):
#         headers, user = auth_headers_factory(user_type="eo")
#         kb = KnowledgeBaseService.create_knowledge_base(
#             db=db_session,
#             user_id=user.id,
#             title="KB",
#             service_id=service_token.id,
#         )
#         doc = DocumentService.create_document(
#             db=db_session,
#             kb_id=str(kb.id),
#             user_id=user.id,
#             filename="old.pdf",
#             extra_data={"title": "Old Title", "description": "Old metadata"},
#             content_type="application/pdf",
#         )

#         payload = {"title": "Updated Title"}
#         response = client.put(
#             f"/api/documents/{doc.id}", json=payload, headers=headers
#         )
#         assert response.status_code == 200
#         assert response.json()["extra_data"]["title"] == "Updated Title"
#         assert response.json()["extra_data"]["description"] == "Old metadata"

#     def test_update_document_forbidden(
#         self,
#         client: TestClient,
#         auth_headers_factory,
#         db_session: Session,
#         service_token: ServiceToken,
#     ):
#         admin_headers, admin = auth_headers_factory(user_type="admin")
#         eo_headers, eo_user = auth_headers_factory(user_type="eo")

#         kb = KnowledgeBaseService.create_knowledge_base(
#             db=db_session,
#             user_id=admin.id,
#             title="KB",
#             service_id=service_token.id,
#         )
#         doc = DocumentService.create_document(
#             db=db_session,
#             kb_id=str(kb.id),
#             user_id=admin.id,
#             filename="private.pdf",
#             content_type="application/pdf",
#         )

#         response = client.put(
#             f"/api/documents/{doc.id}",
#             json={"extra_data": {"hack": True}},
#             headers=eo_headers,
#         )
#         assert response.status_code == 403
