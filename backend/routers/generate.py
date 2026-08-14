from __future__ import annotations

from fastapi import APIRouter
from backend.models.schemas import GenerationRequest, GenerationResponse
from backend.services.generation_service import generate_kolams_from_spec

router = APIRouter(prefix="/api", tags=["Generation"])


@router.post("/generate", response_model=GenerationResponse)
async def generate_endpoint(req: GenerationRequest):
    """API endpoint to generate 10-15 Kolam variations based on user specifications and analyzed features."""
    return generate_kolams_from_spec(req)
