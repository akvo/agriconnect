import os
import shutil
from io import BytesIO

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def storage_secret(monkeypatch):
    """Set STORAGE_SECRET environment variable"""
    monkeypatch.setenv("STORAGE_SECRET", "test_secret_key_123")
    # Reload the storage router to pick up new env var
    import importlib
    from routers import storage
    importlib.reload(storage)
    return "test_secret_key_123"


@pytest.fixture
def temp_storage_dir(monkeypatch):
    """Use actual storage directory for tests"""
    # Ensure storage directory exists
    storage_dir = "storage"
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)

    # Clean storage directory before test
    for filename in os.listdir(storage_dir):
        file_path = os.path.join(storage_dir, filename)
        if os.path.isfile(file_path) and not filename.startswith('.'):
            os.remove(file_path)

    yield storage_dir

    # Clean storage directory after test
    for filename in os.listdir(storage_dir):
        file_path = os.path.join(storage_dir, filename)
        if os.path.isfile(file_path) and not filename.startswith('.'):
            os.remove(file_path)


def test_list_storage_files_empty(client: TestClient, temp_storage_dir):
    """Test listing storage files when directory is empty"""
    response = client.get("/storage")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Index of /storage/" in response.text
    assert "<table>" in response.text


def test_list_storage_files_with_files(
    client: TestClient, temp_storage_dir
):
    """Test listing storage files when files exist"""
    # Create test files
    with open(os.path.join(temp_storage_dir, "test1.txt"), "w") as f:
        f.write("content1")
    with open(os.path.join(temp_storage_dir, "test2.apk"), "w") as f:
        f.write("content2")

    response = client.get("/storage")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "test1.txt" in response.text
    assert "test2.apk" in response.text
    assert "/storage/test1.txt" in response.text
    assert "/storage/test2.apk" in response.text


def test_upload_file_success(
    client: TestClient, storage_secret, temp_storage_dir
):
    """Test successful file upload with valid secret"""
    file_content = b"test file content"
    files = {"file": ("test.apk", BytesIO(file_content), "application/octet-stream")}
    headers = {"X-Storage-Secret": storage_secret}

    response = client.post(
        "/api/storage/upload",
        files=files,
        headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["filename"] == "test.apk"
    assert data["size"] == len(file_content)
    assert data["url"] == "/storage/test.apk"


def test_upload_file_with_custom_filename(
    client: TestClient, storage_secret, temp_storage_dir
):
    """Test file upload with custom filename"""
    file_content = b"test file content"
    files = {"file": ("original.apk", BytesIO(file_content), "application/octet-stream")}
    data = {"filename": "custom-name.apk"}
    headers = {"X-Storage-Secret": storage_secret}

    response = client.post(
        "/api/storage/upload",
        files=files,
        data=data,
        headers=headers
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["filename"] == "custom-name.apk"
    assert response_data["url"] == "/storage/custom-name.apk"


def test_upload_file_missing_secret(client: TestClient, storage_secret):
    """Test file upload without X-Storage-Secret header"""
    file_content = b"test file content"
    files = {"file": ("test.apk", BytesIO(file_content), "application/octet-stream")}

    response = client.post("/api/storage/upload", files=files)

    assert response.status_code == 401
    assert "Invalid or missing storage secret" in response.json()["detail"]


def test_upload_file_invalid_secret(client: TestClient, storage_secret):
    """Test file upload with invalid secret"""
    file_content = b"test file content"
    files = {"file": ("test.apk", BytesIO(file_content), "application/octet-stream")}
    headers = {"X-Storage-Secret": "wrong_secret"}

    response = client.post(
        "/api/storage/upload",
        files=files,
        headers=headers
    )

    assert response.status_code == 401
    assert "Invalid or missing storage secret" in response.json()["detail"]


def test_upload_file_no_secret_configured(client: TestClient, monkeypatch):
    """Test file upload when STORAGE_SECRET is not configured"""
    # Remove STORAGE_SECRET env var
    monkeypatch.delenv("STORAGE_SECRET", raising=False)
    # Reload the storage router
    import importlib
    from routers import storage
    importlib.reload(storage)

    file_content = b"test file content"
    files = {"file": ("test.apk", BytesIO(file_content), "application/octet-stream")}
    headers = {"X-Storage-Secret": "any_secret"}

    response = client.post(
        "/api/storage/upload",
        files=files,
        headers=headers
    )

    assert response.status_code == 500
    assert "Storage secret not configured" in response.json()["detail"]


def test_upload_file_no_filename(
    client: TestClient, storage_secret, temp_storage_dir
):
    """Test file upload without filename should fail"""
    file_content = b"test file content"
    # Create file with no filename
    files = {"file": (None, BytesIO(file_content), "application/octet-stream")}
    headers = {"X-Storage-Secret": storage_secret}

    response = client.post(
        "/api/storage/upload",
        files=files,
        headers=headers
    )

    # FastAPI returns 422 for validation errors, but our custom logic returns 400
    assert response.status_code in [400, 422]
    if response.status_code == 400:
        assert "Filename must be provided" in response.json()["detail"]


def test_storage_workflow_integration(
    client: TestClient, storage_secret, temp_storage_dir
):
    """Test full workflow: upload file and verify in listing"""
    # 1. Upload a file
    file_content = b"integration test content"
    files = {"file": ("integration.apk", BytesIO(file_content), "application/octet-stream")}
    headers = {"X-Storage-Secret": storage_secret}

    upload_response = client.post(
        "/api/storage/upload",
        files=files,
        headers=headers
    )

    assert upload_response.status_code == 200
    upload_data = upload_response.json()
    assert upload_data["filename"] == "integration.apk"

    # 2. Verify file appears in listing
    list_response = client.get("/storage")
    assert list_response.status_code == 200
    assert "integration.apk" in list_response.text
    assert "/storage/integration.apk" in list_response.text


def test_upload_multiple_files_same_name(
    client: TestClient, storage_secret, temp_storage_dir
):
    """Test uploading multiple files with same name (should overwrite)"""
    headers = {"X-Storage-Secret": storage_secret}

    # Upload first file
    files1 = {"file": ("duplicate.txt", BytesIO(b"first"), "text/plain")}
    response1 = client.post(
        "/api/storage/upload",
        files=files1,
        headers=headers
    )
    assert response1.status_code == 200

    # Upload second file with same name
    files2 = {"file": ("duplicate.txt", BytesIO(b"second"), "text/plain")}
    response2 = client.post(
        "/api/storage/upload",
        files=files2,
        headers=headers
    )
    assert response2.status_code == 200
    assert response2.json()["filename"] == "duplicate.txt"


def test_upload_large_file(
    client: TestClient, storage_secret, temp_storage_dir
):
    """Test uploading a large file"""
    # Create a 1MB file
    large_content = b"x" * (1024 * 1024)
    files = {"file": ("large.apk", BytesIO(large_content), "application/octet-stream")}
    headers = {"X-Storage-Secret": storage_secret}

    response = client.post(
        "/api/storage/upload",
        files=files,
        headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "large.apk"
    assert data["size"] == 1024 * 1024
