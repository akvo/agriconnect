import os
from fastapi import APIRouter, File, UploadFile, Header, HTTPException, Form
from fastapi.responses import HTMLResponse
from datetime import datetime
from typing import Optional

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
                files.append({
                    "name": filename,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime)
                })

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
            th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #ddd; }
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
        size_kb = file['size'] / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        modified_str = file['modified'].strftime('%Y-%m-%d %H:%M:%S')

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
            status_code=500,
            detail="Storage secret not configured"
        )

    if not x_storage_secret or x_storage_secret != STORAGE_SECRET:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing storage secret"
        )

    # Use provided filename or original filename
    target_filename = filename or file.filename

    if not target_filename:
        raise HTTPException(
            status_code=400,
            detail="Filename must be provided"
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
            "url": f"/storage/{target_filename}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )
