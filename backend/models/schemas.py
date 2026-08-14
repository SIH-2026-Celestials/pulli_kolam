from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class RelatedIdea(BaseModel):
    id: str
    title: str
    description: str
    thumbnail_url: str
    grid_size: str
    symmetry: str


class MotifSummary(BaseModel):
    id: int
    edge_count: int
    frequency: int
    label: str


class SymmetrySummary(BaseModel):
    group: str
    coverage: float
    dominant_transform: str
    is_symmetric: bool


class ValiditySummary(BaseModel):
    is_valid: bool
    connected_components: int
    is_eulerian_circuit: bool
    has_eulerian_path: bool
    largest_component_covers_all_nodes: bool


class AnalysisResult(BaseModel):
    analysis_id: str
    image_url: Optional[str] = None
    dot_count: int
    grid_size: str
    symmetry: SymmetrySummary
    motifs: list[MotifSummary]
    validity: ValiditySummary
    bounding_box: tuple[float, float, float, float]
    related_ideas: list[RelatedIdea]
    specifications: Optional[str] = None
    status: str = "ok"
    message: Optional[str] = None


class GenerationRequest(BaseModel):
    analysis_id: Optional[str] = None
    specifications: Optional[str] = None
    dot_count: Optional[int] = None
    symmetry_group: Optional[str] = "D4"
    count: int = Field(default=12, ge=1, le=20)


class GeneratedKolamItem(BaseModel):
    id: str
    title: str
    image_url: str
    grid_size: str
    symmetry: str
    validity: str
    description: str


class GenerationResponse(BaseModel):
    status: str = "ok"
    generated_count: int
    specifications: Optional[str] = None
    kolams: list[GeneratedKolamItem]


class GalleryItem(BaseModel):
    id: str
    title: str
    image_url: str
    grid_size: str
    symmetry: str
    complexity: str


class GalleryResponse(BaseModel):
    total: int
    items: list[GalleryItem]
