from fastapi.testclient import TestClient
from src.api import app, init_db, get_db_connection, PRODUCT_CACHE
import pytest
import os
import sqlite3

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_jobs.db")
    monkeypatch.setattr("src.api.DB_PATH", test_db)
    init_db()
    
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


def test_register_job_cache_hit_returns_completed_job():
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO jobs (id, product_a, product_b, rung, status, created_at, inliers, rmse) "
        "VALUES ('cached_completed_job', 'test_a', 'test_b', 0, 'completed', '2026-09-17T12:00:00', 42, 0.5)"
    )
    conn.commit()
    conn.close()

    response = client.post("/register", json={"product_a": "test_a", "product_b": "test_b", "rung": 0})
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "cached_completed_job"

    # Confirm no duplicate row was created
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM jobs WHERE product_a = 'test_a' AND product_b = 'test_b'").fetchone()[0]
    conn.close()
    assert count == 1


def test_register_job_cache_miss_creates_new_job():
    response = client.post("/register", json={"product_a": "test_a", "product_b": "test_b", "rung": 0})
    assert response.status_code == 200
    new_job_id = response.json()["job_id"]

    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (new_job_id,)).fetchone()
    conn.close()
    assert job is not None
    assert job["product_a"] == "test_a"
    assert job["status"] in ["pending", "failed", "completed"]


def test_register_job_does_not_reuse_failed_or_pending_jobs():
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO jobs (id, product_a, product_b, rung, status, created_at) "
        "VALUES ('failed_job', 'test_a', 'test_b', 0, 'failed', '2026-09-17T11:00:00')"
    )
    conn.execute(
        "INSERT INTO jobs (id, product_a, product_b, rung, status, created_at) "
        "VALUES ('pending_job', 'test_a', 'test_b', 1, 'pending', '2026-09-17T11:30:00')"
    )
    conn.commit()
    conn.close()

    # Requesting rung 0 should not return failed_job
    res0 = client.post("/register", json={"product_a": "test_a", "product_b": "test_b", "rung": 0})
    assert res0.status_code == 200
    assert res0.json()["job_id"] != "failed_job"

    # Requesting rung 1 should not return pending_job
    res1 = client.post("/register", json={"product_a": "test_a", "product_b": "test_b", "rung": 1})
    assert res1.status_code == 200
    assert res1.json()["job_id"] != "pending_job"


def test_register_job_different_rungs_do_not_collide():
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO jobs (id, product_a, product_b, rung, status, created_at) "
        "VALUES ('job_rung_0', 'test_a', 'test_b', 0, 'completed', '2026-09-17T10:00:00')"
    )
    conn.commit()
    conn.close()

    # Rung 0 hits cache
    res0 = client.post("/register", json={"product_a": "test_a", "product_b": "test_b", "rung": 0})
    assert res0.json()["job_id"] == "job_rung_0"

    # Rung 1 misses cache and creates a different job
    res1 = client.post("/register", json={"product_a": "test_a", "product_b": "test_b", "rung": 1})
    assert res1.json()["job_id"] != "job_rung_0"

