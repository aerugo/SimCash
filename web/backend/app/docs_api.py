"""API endpoints for serving documentation markdown files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

DOCS_DIR = Path(__file__).parent.parent / "docs"
IMAGES_DIR = Path(__file__).parent.parent / "docs" / "images"

# Ordered registry of all doc pages
DOC_PAGES: list[dict[str, Any]] = [
    # Guides
    {"id": "overview", "title": "Overview", "icon": "📖", "category": "guide", "order": 0},
    {"id": "how-it-works", "title": "How the Simulator Works", "icon": "⚙️", "category": "guide", "order": 1},
    {"id": "cost-model", "title": "The Cost Model", "icon": "💰", "category": "guide", "order": 2},
    {"id": "policy-optimization", "title": "AI Policy Optimization", "icon": "🤖", "category": "guide", "order": 3},
    {"id": "architecture", "title": "Technical Architecture", "icon": "🏗️", "category": "guide", "order": 4},
    # Paper
    {"id": "paper-introduction", "title": "Introduction & Methods", "icon": "📄", "category": "paper", "order": 0},
    {"id": "paper-results", "title": "Results", "icon": "📊", "category": "paper", "order": 1},
    {"id": "paper-discussion", "title": "Discussion & Conclusion", "icon": "💬", "category": "paper", "order": 2},
    {"id": "paper-appendix", "title": "Detailed Data", "icon": "📋", "category": "paper", "order": 3},
    # Advanced
    {"id": "scenarios", "title": "Scenario System", "icon": "🎬", "category": "advanced", "order": 0},
    {"id": "policies", "title": "Policy Decision Trees", "icon": "🌳", "category": "advanced", "order": 1},
    {"id": "policy-tree-spec", "title": "Policy Tree Specification", "icon": "📋", "category": "advanced", "order": 2},
    {"id": "llm-optimization", "title": "LLM Optimization Deep Dive", "icon": "🧠", "category": "advanced", "order": 3},
    # Reference
    {"id": "schema-reference", "title": "Schema Reference", "icon": "📐", "category": "reference", "order": 0},
    {"id": "api-reference", "title": "API Reference", "icon": "🔌", "category": "reference", "order": 1},
    {"id": "references", "title": "References & Reading", "icon": "📚", "category": "reference", "order": 2},
]

_PAGE_INDEX = {p["id"]: p for p in DOC_PAGES}


@router.get("/api/docs")
def list_docs():
    """Return list of doc pages with metadata."""
    return {"pages": DOC_PAGES}


@router.get("/api/docs/images/{path:path}")
def get_doc_image(path: str):
    """Serve static images for documentation."""
    img_path = DOCS_DIR / "images" / path
    if not img_path.exists() or not img_path.is_file():
        raise HTTPException(status_code=404, detail=f"Image '{path}' not found")
    # Security: ensure path doesn't escape docs/images
    try:
        img_path.resolve().relative_to((DOCS_DIR / "images").resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    suffix = img_path.suffix.lower()
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp"}
    media_type = media_types.get(suffix, "application/octet-stream")
    return FileResponse(img_path, media_type=media_type)


@router.get("/api/docs/{doc_id}")
def get_doc(doc_id: str):
    """Return markdown content for a specific doc page."""
    meta = _PAGE_INDEX.get(doc_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Doc page '{doc_id}' not found")

    md_path = DOCS_DIR / f"{doc_id}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"Markdown file for '{doc_id}' not found")

    content = md_path.read_text(encoding="utf-8")
    return {**meta, "content": content}
