# Storage System

## Overview

AgriConnect includes a file storage system for managing uploaded files, particularly APK files for mobile app distribution. The storage system provides both file upload API endpoints and a web-based file browser.

## Architecture

### Components

1. **Backend Storage Router** (`backend/routers/storage.py`):
   - File upload API endpoint
   - Directory listing HTML page
   - File serving via FastAPI StaticFiles

2. **Nginx Proxy Configuration** (`nginx/conf.d/default.conf`):
   - Routes `/storage` requests to backend
   - Required for production deployments

3. **Storage Directory** (`backend/storage/`):
   - Automatically created on backend startup
   - Stores uploaded files
   - Must be writable by the backend process

## Endpoints

### File Browser: `GET /storage`

Browse uploaded files through an HTML interface.

**Response**: HTML page with file listing including:
- File names with download links
- File sizes (KB/MB)
- Last modified timestamps

**Example**:
```bash
curl https://agriconnect2.akvotest.org/storage
```

### File Upload: `POST /api/storage/upload`

Upload files to the storage directory.

**Authentication**: Requires `X-Storage-Secret` header matching `STORAGE_SECRET` environment variable.

**Request**:
```bash
curl -X POST https://agriconnect2.akvotest.org/api/storage/upload \
  -H "X-Storage-Secret: your-secret-here" \
  -F "file=@app-release.apk" \
  -F "filename=myapp.apk"
```

**Parameters**:
- `file` (required): The file to upload
- `filename` (optional): Custom filename for the uploaded file. If not provided, uses original filename.

**Response**:
```json
{
  "success": true,
  "filename": "myapp.apk",
  "size": 52428800,
  "url": "/storage/myapp.apk"
}
```

### File Download: `GET /storage/{filename}`

Direct file download via StaticFiles mount.

**Example**:
```bash
curl -O https://agriconnect2.akvotest.org/storage/myapp.apk
```

## Configuration

### Environment Variables

**Backend** (`.env`):
```bash
STORAGE_SECRET=your-random-secret-key
```

Generate a secure secret:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Nginx Configuration

The nginx configuration **must** include a location block for `/storage`:

```nginx
location /storage {
    proxy_pass              http://backend:8000;
    proxy_set_header        Host $host;
    proxy_set_header        X-Real-IP $remote_addr;
    proxy_set_header        X-Forwarded-Host $host;
    proxy_set_header        X-Forwarded-Proto $scheme;
    proxy_http_version      1.1;
}
```

**Important**: Without this nginx configuration, `/storage` requests will be routed to the frontend instead of the backend, causing 500 errors in production.

### File Size Limits

Adjust in `nginx/conf.d/default.conf`:
```nginx
client_max_body_size 10M;  # Increase for larger APK files
```

## Deployment

### Local Development

Storage system works automatically:
```bash
./dc.sh up -d
# Access at http://localhost:8000/storage
```

### Production Deployment

1. **Set environment variable**:
   ```bash
   # In production .env file
   STORAGE_SECRET=your-production-secret
   ```

2. **Verify nginx configuration** includes `/storage` location block

3. **Deploy and restart services**:
   ```bash
   git pull
   docker-compose restart nginx backend
   ```

4. **Verify storage directory permissions**:
   ```bash
   ls -la backend/storage
   # Should be writable by the backend container user
   ```

## Usage Examples

### Upload APK for Mobile App Distribution

```bash
# Upload with custom filename
curl -X POST https://agriconnect2.akvotest.org/api/storage/upload \
  -H "X-Storage-Secret: ${STORAGE_SECRET}" \
  -F "file=@app-release.apk" \
  -F "filename=agriconnect-latest.apk"
```

### Automated Deployment (GitHub Actions)

```yaml
- name: Upload APK to Storage
  run: |
    curl -X POST ${{ secrets.BACKEND_URL }}/api/storage/upload \
      -H "X-Storage-Secret: ${{ secrets.STORAGE_SECRET }}" \
      -F "file=@app-release.apk" \
      -F "filename=agriconnect-v${{ github.run_number }}.apk"
```

## Troubleshooting

### 500 Internal Server Error on /storage

**Symptoms**: `/storage` endpoint returns "Internal Server Error" in production but works locally.

**Cause**: Missing nginx location block for `/storage`.

**Solution**: Add the nginx configuration shown above and restart nginx.

### 401 Unauthorized on Upload

**Cause**: Missing or incorrect `X-Storage-Secret` header.

**Solution**: Verify the header matches the `STORAGE_SECRET` environment variable.

### Permission Denied When Writing Files

**Cause**: Storage directory not writable by backend container.

**Solution**:
```bash
# Fix permissions on host
chmod 755 backend/storage

# Or in Docker
docker exec backend chmod 755 /app/storage
```

### File Not Found After Upload

**Cause**: StaticFiles mount not working or storage directory path mismatch.

**Solution**: Verify `storage` directory exists and `main.py` creates it before mounting:
```python
os.makedirs("storage", exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")
```

## Security Considerations

1. **Secret Management**:
   - Never commit `STORAGE_SECRET` to version control
   - Use different secrets for development and production
   - Rotate secrets periodically

2. **File Validation**:
   - Only trusted users should have the storage secret
   - Consider adding file type validation
   - Implement file size limits via nginx

3. **Access Control**:
   - Upload requires authentication (X-Storage-Secret header)
   - File browsing and downloads are public (no authentication)
   - Consider adding authentication for file access if needed

## API Integration Example

### Python
```python
import requests

def upload_file(file_path, storage_secret, custom_filename=None):
    url = "https://agriconnect2.akvotest.org/api/storage/upload"
    headers = {"X-Storage-Secret": storage_secret}

    with open(file_path, "rb") as f:
        files = {"file": f}
        data = {"filename": custom_filename} if custom_filename else {}
        response = requests.post(url, headers=headers, files=files, data=data)

    return response.json()
```

### JavaScript/Node.js
```javascript
const FormData = require('form-data');
const fs = require('fs');

async function uploadFile(filePath, storageSecret, customFilename = null) {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  if (customFilename) {
    form.append('filename', customFilename);
  }

  const response = await fetch('https://agriconnect2.akvotest.org/api/storage/upload', {
    method: 'POST',
    headers: {
      'X-Storage-Secret': storageSecret,
    },
    body: form,
  });

  return response.json();
}
```
