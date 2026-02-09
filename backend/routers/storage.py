import os
import re
from fastapi import APIRouter, File, UploadFile, Header, HTTPException, Form
from fastapi.responses import HTMLResponse
from datetime import datetime
from typing import Optional, List, Tuple

from pydantic import BaseModel

router = APIRouter(tags=["storage"])

STORAGE_SECRET = os.getenv("STORAGE_SECRET")


@router.get("/storage", response_class=HTMLResponse)
def list_storage_files():
    """List all files in the storage directory with download links"""
    storage_path = "storage"
    files = []

    if os.path.exists(storage_path):
        for filename in os.listdir(storage_path):
            file_path = os.path.join(storage_path, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append(
                    {
                        "name": filename,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime),
                    }
                )

    # Sort by name
    files.sort(key=lambda x: x["name"])

    # Generate HTML
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Storage Files</title>
        <style>
            body { font-family: monospace; margin: 40px; }
            h1 { font-size: 24px; margin-bottom: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td {
                text-align: left;
                padding: 8px 12px;
                border-bottom: 1px solid #ddd;
            }
            th { background-color: #f5f5f5; font-weight: bold; }
            tr:hover { background-color: #f9f9f9; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .size { text-align: right; }
            .date { color: #666; }
        </style>
    </head>
    <body>
        <h1>Index of /storage/</h1>
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th class="size">Size</th>
                    <th>Modified</th>
                </tr>
            </thead>
            <tbody>
    """

    for file in files:
        size_kb = file["size"] / 1024
        size_str = (
            f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        )
        modified_str = file["modified"].strftime("%Y-%m-%d %H:%M:%S")

        html_content += f"""
        <tr>
            <td><a href="/storage/{file['name']}">{file['name']}</a></td>
            <td class="size">{size_str}</td>
            <td class="date">{modified_str}</td>
        </tr>
        """

    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """

    return html_content


@router.post("/api/storage/upload")
async def upload_file(
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None),
    x_storage_secret: Optional[str] = Header(None),
):
    """Upload a file to the storage directory

    Requires X-Storage-Secret header matching STORAGE_SECRET env variable.
    Optional filename parameter to specify the target filename.
    """
    # Validate secret
    if not STORAGE_SECRET:
        raise HTTPException(
            status_code=500, detail="Storage secret not configured"
        )

    if not x_storage_secret or x_storage_secret != STORAGE_SECRET:
        raise HTTPException(
            status_code=401, detail="Invalid or missing storage secret"
        )

    # Use provided filename or original filename
    target_filename = filename or file.filename

    if not target_filename:
        raise HTTPException(
            status_code=400, detail="Filename must be provided"
        )

    # Ensure storage directory exists
    storage_path = "storage"
    os.makedirs(storage_path, exist_ok=True)

    # Write file
    file_path = os.path.join(storage_path, target_filename)

    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        return {
            "success": True,
            "filename": target_filename,
            "size": len(content),
            "url": f"/storage/{target_filename}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save file: {str(e)}"
        )


class VersionCheckResponse(BaseModel):
    current_version: str
    latest_version: Optional[str] = None
    update_available: bool
    download_url: Optional[str] = None


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse version string into tuple of integers for comparison."""
    try:
        return tuple(int(x) for x in version_str.split("."))
    except (ValueError, AttributeError):
        return (0,)


def find_latest_apk_version() -> Optional[Tuple[str, str]]:
    """Scan storage directory for APK files and return latest version.

    Returns:
        Tuple of (version, filename) or None if no APK found
    """
    storage_path = "storage"
    if not os.path.exists(storage_path):
        return None

    # Pattern: agriconnect-X.Y.Z.apk
    pattern = re.compile(r"^agriconnect-(\d+\.\d+\.\d+)\.apk$")
    versions: List[Tuple[Tuple[int, ...], str, str]] = []

    for filename in os.listdir(storage_path):
        match = pattern.match(filename)
        if match:
            version_str = match.group(1)
            version_tuple = parse_version(version_str)
            versions.append((version_tuple, version_str, filename))

    if not versions:
        return None

    # Sort by version tuple (highest first) and return latest
    versions.sort(reverse=True)
    _, latest_version, latest_filename = versions[0]
    return (latest_version, latest_filename)


@router.get("/api/app/version", response_model=VersionCheckResponse)
def check_app_version(current_version: str):
    """Check if a newer version of the app is available.

    Scans the storage directory for APK files and compares versions.

    Args:
        current_version: The current app version (e.g., "1.2.7")

    Returns:
        Version check result with update availability and download URL
    """
    result = find_latest_apk_version()

    if not result:
        return VersionCheckResponse(
            current_version=current_version,
            latest_version=None,
            update_available=False,
            download_url=None,
        )

    latest_version, latest_filename = result
    current_tuple = parse_version(current_version)
    latest_tuple = parse_version(latest_version)
    update_available = latest_tuple > current_tuple

    return VersionCheckResponse(
        current_version=current_version,
        latest_version=latest_version,
        update_available=update_available,
        download_url=(
            f"/storage/{latest_filename}" if update_available else None
        ),
    )
