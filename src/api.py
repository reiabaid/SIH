import asyncio
import csv
import json
import sqlite3
import os
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.pipeline import run_pipeline
from src.deliverable import build_deliverable
from src.types import MatchResult
import src.io_lro as io_lro
import src.io_ch2 as io_ch2

app = FastAPI(title="LunarMatch API", description="API and Job Store for Member 5")

DB_PATH = "jobs.db"
PRODUCT_CACHE = {}

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

def load_inventory():
    global PRODUCT_CACHE
    PRODUCT_CACHE.clear()
    data_dir = Path("data")
    for csv_file in ["lro_inventory.csv", "ch2_inventory.csv"]:
        path = data_dir / csv_file
        if not path.exists():
            continue
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row.get("product_id")
                fpath = row.get("path")
                if pid and fpath:
                    PRODUCT_CACHE[pid] = fpath

@app.on_event("startup")
async def startup_event():
    init_db()
    load_inventory()
    print("Models loaded and inventory cached. Ready to serve.")

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

def load_product_dynamically(product_id: str, path: str):
    if product_id.startswith("ch2_"):
        return io_ch2.load_product(path)
    else:
        return io_lro.load_product(path)

def process_job_sync(job_id: str, id_a: str, path_a: str, id_b: str, path_b: str, rung: int, artefact_dir: str):
    os.makedirs(artefact_dir, exist_ok=True)
    try:
        product_a = load_product_dynamically(id_a, path_a)
        product_b = load_product_dynamically(id_b, path_b)
        
        # We determine the matcher based on rung. 0 -> sift, 1 -> mod-x (which is mapped to "sift" rung 1 in some code, or "sift" but rung 1. In pipeline it takes matcher="sift" and rung=rung)
        matcher = "sift"
        if rung == 2:
            matcher = "lightglue"

        out = run_pipeline(product_a, product_b, matcher=matcher, rung=rung, align=True)
        mr = out["match_result"]
        result = MatchResult(
            pts_a=mr["pts_a"], pts_b=mr["pts_b"], scores=mr["scores"],
            inlier_mask=mr["inlier_mask"], transform=mr["transform"], matcher=mr["matcher"],
            shape_a=mr["shape_a"], shape_b=mr["shape_b"], runtime_s=mr["runtime_s"],
        )
        metrics = build_deliverable(product_a, product_b, result, artefact_dir)
        return metrics
    except Exception as e:
        traceback.print_exc()
        raise e

async def process_job(job_id: str, id_a: str, path_a: str, id_b: str, path_b: str, rung: int):
    artefact_dir = f"data/jobs/{job_id}"
    conn = get_db_connection()
    try:
        metrics = await asyncio.to_thread(process_job_sync, job_id, id_a, path_a, id_b, path_b, rung, artefact_dir)
        rmse = metrics.get("reprojection_residual")
        inliers = metrics.get("inlier_count")
        coverage = metrics.get("occupied_fraction")
        
        conn.execute('''
            UPDATE jobs
            SET status = 'completed', rmse = ?, inliers = ?, coverage = ?, artefact_dir = ?
            WHERE id = ?
        ''', (rmse, inliers, coverage, artefact_dir, job_id))
    except Exception as e:
        conn.execute('''
            UPDATE jobs
            SET status = 'failed', artefact_dir = ?
            WHERE id = ?
        ''', (artefact_dir, job_id))
    finally:
        conn.commit()
        conn.close()

@app.post("/register")
async def register_job(req: RegisterRequest, background_tasks: BackgroundTasks):
    path_a = PRODUCT_CACHE.get(req.product_a)
    path_b = PRODUCT_CACHE.get(req.product_b)
    
    if not path_a or not path_b:
        raise HTTPException(status_code=400, detail="One or both products not found in inventory")

    job_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO jobs (id, product_a, product_b, rung, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    ''', (job_id, req.product_a, req.product_b, req.rung, created_at))
    conn.commit()
    conn.close()
    
    background_tasks.add_task(process_job, job_id, req.product_a, path_a, req.product_b, path_b, req.rung)
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
        
    try:
        base_dir = Path(artefact_dir).resolve(strict=False)
        file_path = Path(os.path.join(base_dir, filename)).resolve(strict=False)
        
        # Path traversal prevention
        if base_dir not in file_path.parents and file_path != base_dir:
            raise HTTPException(status_code=403, detail="Invalid file path")
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid file path")
        
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artefact file not found")
        
    return FileResponse(str(file_path))
