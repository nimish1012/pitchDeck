import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "endpoints" in data
    assert "generate" in data["endpoints"]


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_status_endpoint():
    """Test status endpoint returns operational details."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "config" in data
    assert "endpoints" in data
    assert "features" in data
    assert data["features"]["sse_streaming"] is True
    assert data["features"]["parallel_slide_gen"] is True
    assert data["features"]["dynamic_layouts"] is True
    assert data["features"]["token_budgeting"] is True


def test_invalid_endpoint():
    """Test 404 for invalid endpoint."""
    response = client.get("/invalid")
    assert response.status_code == 404


def test_generate_missing_prompt():
    """Test that generate endpoint rejects empty body."""
    response = client.post("/api/v1/generate", json={})
    assert response.status_code == 422  # validation error


def test_generate_prompt_too_long():
    """Test that generate rejects overly long prompts."""
    response = client.post("/api/v1/generate", json={
        "prompt": "x" * 2001,
    })
    assert response.status_code == 422


def test_generation_not_found():
    """Test polling a non-existent generation."""
    response = client.get("/api/v1/generate/nonexistent123")
    assert response.status_code == 404


def test_delete_not_found():
    """Test deleting a non-existent generation."""
    response = client.delete("/api/v1/generate/nonexistent123")
    assert response.status_code == 404


def test_list_generations():
    """Test listing generations."""
    response = client.get("/api/v1/generations")
    assert response.status_code == 200
    data = response.json()
    assert "generations" in data
    assert "count" in data
