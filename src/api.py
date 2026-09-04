import asyncio
import csv
import json
import sqlite3
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="LunarMatch API", description="API and Job Store for Member 5")

DB_PATH = "jobs.db"

class RegisterRequest(BaseModel):
    product_a: str
    product_b: str
    rung: int

class JobResponse(BaseModel):
    id: str
    product_a: str
    product_b: str
    rung: int
    status: str
    rmse: Optional[float]
    inliers: Optional[int]
    coverage: Optional[float]
    created_at: str
    artefact_dir: Optional[str]

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            product_a TEXT,
            product_b TEXT,
            rung INTEGER,
            status TEXT,
            rmse REAL,
            inliers INTEGER,
            coverage REAL,
            created_at TEXT,
            artefact_dir TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.on_event("startup")
async def startup_event():
    init_db()
    print("Models loaded. Performing warm-up call...")
    await asyncio.sleep(0.5)
    print("Warm-up complete. Ready to serve.")

@app.get("/products")
def get_products():
    products = []
    data_dir = Path("data")
    for csv_file in ["lro_inventory.csv", "ch2_inventory.csv"]:
        path = data_dir / csv_file
        if not path.exists():
            continue
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append(row)
    return products

async def process_job(job_id: str, product_a: str, product_b: str, rung: int):
    # Simulate processing time
    await asyncio.sleep(2)
    
    # Read fixture result from demo/real_pair_result/summary.json
    fixture_path = Path("demo/real_pair_result/summary.json")
    rmse = None
    inliers = None
    coverage = None
    artefact_dir = "demo/real_pair_result"

    if fixture_path.exists():
        try:
            with open(fixture_path, "r") as f:
                data = json.load(f)
            rmse = data.get("rmse_fitted_px")
            inliers = data.get("inliers")
            coverage = data.get("coverage_occupied_fraction")
        except Exception as e:
            print(f"Failed to read fixture: {e}")

    conn = get_db_connection()
    conn.execute('''
        UPDATE jobs
        SET status = 'completed', rmse = ?, inliers = ?, coverage = ?, artefact_dir = ?
        WHERE id = ?
    ''', (rmse, inliers, coverage, artefact_dir, job_id))
    conn.commit()
    conn.close()

@app.post("/register")
async def register_job(req: RegisterRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO jobs (id, product_a, product_b, rung, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    ''', (job_id, req.product_a, req.product_b, req.rung, created_at))
    conn.commit()
    conn.close()
    
    background_tasks.add_task(process_job, job_id, req.product_a, req.product_b, req.rung)
    return {"job_id": job_id}

@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)

@app.get("/jobs/{job_id}/artefacts/{filename}")
def get_job_artefact(job_id: str, filename: str):
    conn = get_db_connection()
    row = conn.execute("SELECT artefact_dir FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    artefact_dir = row["artefact_dir"]
    if not artefact_dir:
        raise HTTPException(status_code=404, detail="Artefacts not ready yet")
        
    file_path = Path(artefact_dir) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artefact file not found")
        
    return FileResponse(file_path)
