import os
import uuid
import httpx
from PIL import Image

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))

os.makedirs(UPLOAD_DIR, exist_ok=True)


async def download_image_from_url(url: str) -> str:
    """Download an image from a URL and save it to UPLOAD_DIR. Returns local file path."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    ext = ".jpg"
    content_type = resp.headers.get("content-type", "")
    if "png" in content_type:
        ext = ".png"
    elif "jpeg" in content_type or "jpg" in content_type:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(resp.content)

    return filepath


def validate_and_save_upload(file_bytes: bytes, original_filename: str) -> str:
    """Save raw uploaded image bytes to disk after validating basic image format."""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(file_bytes)

    # Verify it can be opened by PIL
    try:
        with Image.open(filepath) as img:
            img.verify()
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise ValueError(f"Invalid image file: {e}")

    return filepath
