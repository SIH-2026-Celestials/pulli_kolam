from __future__ import annotations

import os
from fastapi import APIRouter
from backend.models.schemas import GalleryResponse, GalleryItem

router = APIRouter(prefix="/api", tags=["Gallery"])

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SYNTHETIC_DIR = os.path.join(PROJECT_ROOT, "synthetic_photos")


@router.get("/gallery", response_model=GalleryResponse)
async def gallery_endpoint():
    """API endpoint to list sample Kolams for the gallery viewer."""
    items = []
    if os.path.exists(SYNTHETIC_DIR):
        files = sorted([f for f in os.listdir(SYNTHETIC_DIR) if f.endswith((".jpg", ".png"))])
        for idx, filename in enumerate(files[:24], start=1):
            items.append(
                GalleryItem(
                    id=str(idx),
                    title=f"Pulli Kolam #{idx}",
                    image_url=f"/static/synthetic/{filename}",
                    grid_size="7×7" if idx % 2 == 0 else "5×5",
                    symmetry="D4 Dihedral" if idx % 3 != 0 else "D2 Bilateral",
                    complexity="Medium" if idx % 2 == 0 else "High",
                )
            )

    return GalleryResponse(total=len(items), items=items)
