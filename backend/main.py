from __future__ import annotations

import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.routers import analyze, generate, gallery
from backend.utils.image_utils import UPLOAD_DIR

app = FastAPI(
    title="PULLI — Kolam Design-Principle Engine API",
    description="Backend API for Kolam analysis, motif induction, Eulerian validity, and AI generation.",
    version="1.0.0",
)

# Enable CORS for local dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows Vite dev server & production web client
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static file endpoints
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

synthetic_dir = os.path.join(PROJECT_ROOT, "synthetic_photos")
if os.path.exists(synthetic_dir):
    app.mount("/static/synthetic", StaticFiles(directory=synthetic_dir), name="synthetic")

real_photos_dir = os.path.join(PROJECT_ROOT, "real_photos")
if os.path.exists(real_photos_dir):
    app.mount("/static/sample_ideas", StaticFiles(directory=real_photos_dir), name="sample_ideas")

# Include API routers
app.include_router(analyze.router)
app.include_router(generate.router)
app.include_router(gallery.router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "engine": "PULLI Deterministic Graph & Motif Engine",
        "version": "1.0.0",
    }
