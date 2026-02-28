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
    # Papers — nested: papers/<paper-slug>/<section>
    {"id": "papers/simcash/introduction", "title": "Introduction & Methods", "icon": "📄", "category": "paper", "paper": "simcash", "paper_title": "SimCash: LLM-Optimized Payment Coordination", "order": 0},
    {"id": "papers/simcash/results", "title": "Results", "icon": "📊", "category": "paper", "paper": "simcash", "paper_title": "SimCash: LLM-Optimized Payment Coordination", "order": 1},
    {"id": "papers/simcash/discussion", "title": "Discussion & Conclusion", "icon": "💬", "category": "paper", "paper": "simcash", "paper_title": "SimCash: LLM-Optimized Payment Coordination", "order": 2},
    {"id": "papers/simcash/appendix", "title": "Detailed Data", "icon": "📋", "category": "paper", "paper": "simcash", "paper_title": "SimCash: LLM-Optimized Payment Coordination", "order": 3},
    # Q1 2026 Campaign Paper
    {"id": "papers/q1-campaign/introduction", "title": "Introduction & Setup", "icon": "📄", "category": "paper", "paper": "q1-campaign", "paper_title": "Q1 2026: The Complexity Threshold", "order": 0},
    {"id": "papers/q1-campaign/results", "title": "Results", "icon": "📊", "category": "paper", "paper": "q1-campaign", "paper_title": "Q1 2026: The Complexity Threshold", "order": 1},
    {"id": "papers/q1-campaign/discussion", "title": "Discussion & Conclusion", "icon": "💬", "category": "paper", "paper": "q1-campaign", "paper_title": "Q1 2026: The Complexity Threshold", "order": 2},
    {"id": "papers/q1-campaign/appendix", "title": "Detailed Data", "icon": "📋", "category": "paper", "paper": "q1-campaign", "paper_title": "Q1 2026: The Complexity Threshold", "order": 3},
    # Research
    {"id": "showcase", "title": "Experiment Showcase", "icon": "🔬", "category": "research", "order": 0},
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


@router.get("/api/docs/{doc_id:path}")
def get_doc(doc_id: str):
    """Return markdown content for a specific doc page."""
    meta = _PAGE_INDEX.get(doc_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Doc page '{doc_id}' not found")

    # Nested IDs like "papers/simcash/introduction" map to "papers/simcash/introduction.md"
    md_path = DOCS_DIR / f"{doc_id}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"Markdown file for '{doc_id}' not found")

    # Security: ensure path doesn't escape docs dir
    try:
        md_path.resolve().relative_to(DOCS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    content = md_path.read_text(encoding="utf-8")
    return {**meta, "content": content}
