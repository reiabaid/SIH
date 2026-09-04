from fastapi.testclient import TestClient
from src.api import app, init_db, get_db_connection, PRODUCT_CACHE
import pytest
import os
import sqlite3

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    # We can use an in-memory DB or a test DB, but since the app hardcodes DB_PATH = "jobs.db", 
    # we'll just re-init it for the test and clear the table.
    init_db()
    conn = get_db_connection()
    conn.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()
    
    # Pre-populate product cache for testing
    PRODUCT_CACHE.clear()
    PRODUCT_CACHE["test_a"] = "dummy_path_a"
    PRODUCT_CACHE["test_b"] = "dummy_path_b"
    
    yield

def test_get_products():
    response = client.get("/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_register_invalid_products():
    response = client.post("/register", json={"product_a": "invalid_a", "product_b": "invalid_b", "rung": 1})
    assert response.status_code == 400
    assert "not found" in response.json()["detail"]

def test_register_and_get_job():
    # Note: the background task will fail because "dummy_path_a" doesn't exist, 
    # but the registration should succeed.
    response = client.post("/register", json={"product_a": "test_a", "product_b": "test_b", "rung": 1})
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    
    job_id = data["job_id"]
    
    # Get the job
    job_response = client.get(f"/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["id"] == job_id
    assert job_data["status"] in ["pending", "failed", "completed"]

def test_get_artefact_not_found():
    # Insert a fake job directly
    conn = get_db_connection()
    conn.execute("INSERT INTO jobs (id, product_a, product_b, rung, status, artefact_dir) VALUES ('fake_job', 'a', 'b', 0, 'completed', 'data/jobs/fake_job')")
    conn.commit()
    conn.close()
    
    response = client.get("/jobs/fake_job/artefacts/missing.png")
    assert response.status_code == 404

def test_get_artefact_path_traversal():
    conn = get_db_connection()
    conn.execute("INSERT INTO jobs (id, product_a, product_b, rung, status, artefact_dir) VALUES ('fake_job2', 'a', 'b', 0, 'completed', 'data/jobs/fake_job2')")
    conn.commit()
    conn.close()
    
    response = client.get("/jobs/fake_job2/artefacts/..%2F..%2F..%2Fjobs.db")
    assert response.status_code in [403, 404] # FastAPI might sanitize path or our logic catches it
