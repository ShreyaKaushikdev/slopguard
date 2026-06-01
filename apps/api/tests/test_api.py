import pytest
from fastapi.testclient import TestClient
from slopguard.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "slopguard-api"}

def test_score_text_endpoint():
    payload = {
        "text": "Fixed JWT secret exposure in auth/middleware.js. P95 latency dropped from 420ms to 85ms.",
        "domain": "code_review"
    }
    response = client.post("/score/text", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "score" in data
    assert "oversight" in data
    assert data["domain"] == "code_review"
    assert "signals" in data
    
    # We expect a good score for specific measurements
    assert data["score"] > 40

def test_score_pr_endpoint():
    payload = {
        "title": "Fix auth",
        "description": "Fixed JWT secret exposure.",
        "diff": "+ const secret = process.env.JWT_SECRET;",
        "comments": []
    }
    response = client.post("/score/pr", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert data["domain"] == "code_review"

def test_demo_scenarios():
    response = client.get("/demo/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0

def test_adapters_status():
    response = client.get("/adapters/status")
    assert response.status_code == 200
    data = response.json()
    assert "live_ingestion" in data
