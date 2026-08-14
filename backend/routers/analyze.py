from __future__ import annotations

import os
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from backend.models.schemas import AnalysisResult
from backend.services.analysis_service import analyze_kolam_image
from backend.utils.image_utils import download_image_from_url, validate_and_save_upload

router = APIRouter(prefix="/api", tags=["Analysis"])


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_endpoint(
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    specifications: Optional[str] = Form(None),
):
    """API endpoint to analyze an uploaded Kolam image or image URL.
    
    Extracts dot grid, symmetry group, motif families, single-stroke validity,
    and returns relevant Kolam design suggestions.
    """
    local_path = None
    public_url = None

    if image is not None and image.filename:
        file_bytes = await image.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image file size exceeds 10MB limit.")
        try:
            local_path = validate_and_save_upload(file_bytes, image.filename)
            public_url = f"/static/uploads/{os.path.basename(local_path)}"
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
    elif image_url and image_url.strip():
        try:
            local_path = await download_image_from_url(image_url.strip())
            public_url = f"/static/uploads/{os.path.basename(local_path)}"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch image from URL: {e}")
    else:
        # Default fallback to a sample image in real_photos if no image provided
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sample_path = os.path.join(project_root, "real_photos", "kolam2_tshrinivasan.jpg")
        if os.path.exists(sample_path):
            local_path = sample_path
            public_url = "/static/sample_ideas/kolam2_tshrinivasan.jpg"
        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide an image file upload or image_url.",
            )

    try:
        result = analyze_kolam_image(
            image_path=local_path,
            specifications=specifications,
            public_url=public_url,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing image: {str(e)}")
