import os
import sys
import asyncio

# Ensure we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api import init_db, load_inventory, register_job, RegisterRequest
from fastapi import BackgroundTasks

async def precompute_demo():
    print("Initializing database...")
    init_db()
    print("Loading inventory...")
    load_inventory()
    
    for rung in [0, 1]:
        print(f"Triggering precomputation for synthetic demo pair (rung {rung})...")
        req = RegisterRequest(
            product_a="synthetic_a",
            product_b="synthetic_b",
            rung=rung
        )
        bg_tasks = BackgroundTasks()
        res = await register_job(req, bg_tasks)
        
        job_id = res["job_id"]
        print(f"Registered job {job_id} for rung {rung}")
        
        if bg_tasks.tasks:
            print(f"Executing background tasks synchronously for job {job_id}...")
            for task in bg_tasks.tasks:
                await task.func(*task.args, **task.kwargs)
        else:
            print(f"Job {job_id} was already precomputed (cache hit).")
            
        print(f"Precomputation completed for job {job_id} (rung {rung})")

if __name__ == "__main__":
    asyncio.run(precompute_demo())
