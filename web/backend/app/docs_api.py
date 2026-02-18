"""API endpoints for serving documentation markdown files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

DOCS_DIR = Path(__file__).parent.parent / "docs"

# Ordered registry of all doc pages
DOC_PAGES: list[dict[str, Any]] = [
    # Guides
    {"id": "overview", "title": "Overview", "icon": "📖", "category": "guide", "order": 0},
    {"id": "how-it-works", "title": "How the Simulator Works", "icon": "⚙️", "category": "guide", "order": 1},
    {"id": "cost-model", "title": "The Cost Model", "icon": "💰", "category": "guide", "order": 2},
    {"id": "policy-optimization", "title": "AI Policy Optimization", "icon": "🤖", "category": "guide", "order": 3},
    {"id": "experiments", "title": "Experiments", "icon": "🧪", "category": "guide", "order": 4},
    {"id": "game-theory", "title": "Game Theory Primer", "icon": "♟️", "category": "guide", "order": 5},
    {"id": "architecture", "title": "Technical Architecture", "icon": "🏗️", "category": "guide", "order": 6},
    {"id": "validation", "title": "Validation & Verification", "icon": "✅", "category": "guide", "order": 7},
    # Advanced
    {"id": "scenarios", "title": "Scenario System", "icon": "🎬", "category": "advanced", "order": 0},
    {"id": "policies", "title": "Policy Decision Trees", "icon": "🌳", "category": "advanced", "order": 1},
    {"id": "llm-optimization", "title": "LLM Optimization Deep Dive", "icon": "🧠", "category": "advanced", "order": 2},
    # Blog
    {"id": "blog-01-liquidity-game", "title": "Do LLM Agents Converge?", "icon": "📝", "category": "blog", "order": 0, "date": "2026-02-17"},
    {"id": "blog-02-stress-testing", "title": "Financial Stress Tests", "icon": "📝", "category": "blog", "order": 1, "date": "2026-02-17"},
    {"id": "blog-03-policy-evolution", "title": "From FIFO to Nash", "icon": "📝", "category": "blog", "order": 2, "date": "2026-02-17"},
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
