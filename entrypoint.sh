#!/bin/sh
# entrypoint.sh — run ingest_catalog once on first boot, then start the server.
#
# ingest_catalog makes live NAIF WebGeocalc calls (~35-50s per LRO product) so
# it cannot run at docker build time. We guard with a sentinel file so that
# subsequent container restarts skip it and start the server immediately.

SENTINEL=/app/data/.catalog_ingested

if [ ! -f "$SENTINEL" ]; then
    echo "[entrypoint] First boot: running ingest_catalog (this may take a few minutes)..."
    python -m scripts.ingest_catalog || echo "[entrypoint] ingest_catalog failed or partial — continuing anyway"
    touch "$SENTINEL"
    echo "[entrypoint] Catalog ingest complete."
else
    echo "[entrypoint] Catalog already ingested, skipping."
fi

echo "[entrypoint] Starting uvicorn..."
exec uvicorn src.api:app --host 0.0.0.0 --port 8000
