"""API endpoints for serving documentation markdown files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

DOCS_DIR = Path(__file__).parent.parent / "docs"
IMAGES_DIR = Path(__file__).parent.parent / "docs" / "images"
PAPER_DATA = DOCS_DIR / "papers" / "q1-campaign" / "chart-data.json"

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


@router.get("/api/docs/chart-data/{chart_id}")
def get_chart_data(chart_id: str):
    """Return chart-ready data for paper visualizations."""
    data = _load_paper_data()
    return _build_chart(chart_id, data)


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


# --- Chart data helpers ---


def _load_paper_data() -> dict:
    """Load and cache paper data. Reloads if file changed."""
    if not PAPER_DATA.exists():
        return {"summary": [], "baselines": {}, "experiments": []}
    return json.loads(PAPER_DATA.read_text())


def _build_chart(chart_id: str, data: dict) -> dict:
    """Build chart-specific data from paper-data.json."""
    summary = data.get("summary", [])
    baselines = data.get("baselines", {})
    experiments = data.get("experiments", [])

    SIMPLE = {"2b_3t", "3b_6t", "4b_8t", "castro_exp2"}
    COMPLEX = {"periodic_shocks", "large_network", "lehman_month"}
    LABELS = {
        "2b_3t": "2B 3T", "3b_6t": "3B 6T", "4b_8t": "4B 8T",
        "castro_exp2": "Castro Exp2", "periodic_shocks": "Periodic Shocks",
        "large_network": "Large Network", "lehman_month": "Lehman Month",
    }

    if chart_id == "cost-comparison":
        rows = []
        for scenario in ["2b_3t", "3b_6t", "4b_8t", "castro_exp2"]:
            row = {"scenario": LABELS.get(scenario, scenario)}
            for s in summary:
                if s["scenario"] == scenario:
                    row[s["model"]] = s["cost"]
            rows.append(row)
        return {"type": "bar", "data": rows, "keys": ["baseline", "flash", "pro"]}

    elif chart_id == "complex-cost-delta":
        rows = []
        for scenario in ["periodic_shocks", "large_network", "lehman_month"]:
            row = {"scenario": LABELS.get(scenario, scenario)}
            for s in summary:
                if s["scenario"] == scenario and s["model"] in ("flash", "pro"):
                    row[s["model"]] = s.get("cost_delta_pct", 0)
            rows.append(row)
        return {"type": "bar", "data": rows, "keys": ["flash", "pro"]}

    elif chart_id == "settlement-degradation":
        # Find periodic_shocks flash run 1 daily SR data
        target = None
        for exp in experiments:
            if exp["scenario"] == "periodic_shocks" and exp["model"] == "flash" and exp.get("run") == 1:
                target = exp
                break
        if not target:
            # Fallback: any periodic_shocks flash
            for exp in experiments:
                if exp["scenario"] == "periodic_shocks" and exp["model"] == "flash":
                    target = exp
                    break

        daily = []
        if target and "daily_sr" in target:
            for d in target["daily_sr"]:
                daily.append({
                    "day": d["day"],
                    "sr": round(d["cumulative_rate"] * 100, 1),
                })

        bl_sr = baselines.get("periodic_shocks", {}).get("sr", 0)
        return {
            "type": "line",
            "data": daily,
            "baseline_sr": round(bl_sr * 100, 1),
            "label": "Periodic Shocks (Flash): Cumulative Settlement Rate",
        }

    elif chart_id == "all-scenarios":
        # Full summary for custom charts
        rows = []
        for s in summary:
            rows.append({
                "scenario": LABELS.get(s["scenario"], s["scenario"]),
                "model": s["model"],
                "cost": s["cost"],
                "sr": round(s["sr"] * 100, 1),
                "cost_delta_pct": s.get("cost_delta_pct"),
                "num_days": s.get("num_days"),
            })
        return {"type": "table", "data": rows}

    else:
        raise HTTPException(status_code=404, detail=f"Unknown chart '{chart_id}'")
