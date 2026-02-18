"""Tests for the docs API endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_docs():
    resp = client.get("/api/docs")
    assert resp.status_code == 200
    data = resp.json()
    assert "pages" in data
    pages = data["pages"]
    assert len(pages) >= 17  # all doc pages
    # Check structure
    for page in pages:
        assert "id" in page
        assert "title" in page
        assert "category" in page
        assert "order" in page


def test_list_docs_categories():
    resp = client.get("/api/docs")
    pages = resp.json()["pages"]
    categories = {p["category"] for p in pages}
    assert categories == {"guide", "advanced", "blog", "reference"}


def test_get_doc_overview():
    resp = client.get("/api/docs/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "overview"
    assert data["title"] == "Overview"
    assert "content" in data
    assert "SimCash" in data["content"]
    assert len(data["content"]) > 100


def test_get_doc_blog():
    resp = client.get("/api/docs/blog-01-liquidity-game")
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "blog"
    assert "date" in data
    assert "content" in data


def test_get_doc_not_found():
    resp = client.get("/api/docs/nonexistent-page")
    assert resp.status_code == 404


def test_all_pages_have_content():
    """Every page listed in the index should have a corresponding markdown file."""
    pages = client.get("/api/docs").json()["pages"]
    for page in pages:
        resp = client.get(f"/api/docs/{page['id']}")
        assert resp.status_code == 200, f"Missing content for {page['id']}"
        assert len(resp.json()["content"]) > 50, f"Content too short for {page['id']}"
