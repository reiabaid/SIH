# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the backend and serve
FROM python:3.10-slim
WORKDIR /app

# Install system dependencies needed for OpenCV, etc.
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and pre-built frontend
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY data/ ./data/
COPY demo/ ./demo/
# Copy frontend build output
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Precompute the demo pairs
RUN python scripts/precompute_demo.py

EXPOSE 8000

# entrypoint.sh: runs ingest_catalog once on first boot (NAIF WebGeocalc calls at runtime,
# not build time), then starts the server.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
