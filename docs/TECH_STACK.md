# LunarMatch Tech Stack

## Overview

LunarMatch is a scientific computer-vision and photogrammetry application for registering Chandrayaan-2 and NASA LRO lunar imagery under changing illumination conditions.

## Frontend

- React 18
- Vite
- Tailwind CSS
- Chart.js and `react-chartjs-2` for metrics and evidence charts
- Three.js for the 3D lunar terrain view
- Lucide React for interface icons
- JavaScript/JSX

## Backend

- Python 3.11+
- FastAPI for the HTTP API
- Uvicorn as the ASGI server
- SQLite for job and status tracking
- FastAPI background tasks for pipeline execution
- CORS middleware for frontend-backend communication

## Computer Vision and Machine Learning

- OpenCV for image processing, SIFT, homography estimation, and geometric matching
- PyTorch for deep-learning inference
- LightGlue and SuperPoint for learned feature matching
- NumPy for numerical operations and vectorized descriptors
- SciPy for scientific computation
- MAGSAC/USAC for robust homography fitting
- Custom modulo-pi gradient descriptors for illumination-invariant matching
- Sub-pixel correlation refinement
- Multi-threaded tiled matching for large lunar images

## Geospatial and Scientific Libraries

- Rasterio/GDAL for raster and GeoTIFF processing
- Shapely for geographic footprint intersection and overlap calculations
- Pillow for image handling
- PVL for ISIS control-network parsing and validation
- Matplotlib for scientific plots and benchmark evidence

## Supported Data and Formats

- Chandrayaan-2 OHRC/TMC imagery
- NASA LRO NAC imagery
- PDS3 and PDS4 metadata
- SLDEM2015 lunar digital elevation data
- GeoTIFF
- GeoJSON
- CSV
- PNG
- JSON
- ISIS `.net` control-network files

## API Workflow

1. The frontend requests available products from the FastAPI backend.
2. The backend calculates product footprint overlap.
3. A registration job is created and processed in the background.
4. The pipeline aligns imagery, extracts features, matches points, and estimates a transformation.
5. Metrics and photogrammetry artefacts are written to the job directory.
6. The frontend polls the job status and displays the results.

## Testing and Development Tools

- Pytest for automated Python tests
- npm scripts for frontend development and production builds
- Python module execution from the repository root
- Vite development server

## Deployment Considerations

The current application is best deployed on a persistent Linux virtual machine because it uses:

- Large local raster datasets
- CPU-intensive image processing
- Optional PyTorch/LightGlue inference
- Background processing inside the FastAPI process
- SQLite and local generated artefacts

A practical deployment arrangement is:

- React/Vite frontend hosted on Vercel, Netlify, or Nginx
- FastAPI backend hosted on a persistent VM such as AWS EC2, Google Compute Engine, Azure VM, or DigitalOcean
- Persistent disk for imagery, model files, SQLite, and generated artefacts

For production scale, SQLite and in-process background tasks should be replaced with PostgreSQL plus a dedicated job queue such as Redis with Celery or RQ. Large imagery and generated artefacts should be stored in object storage such as Amazon S3.

## Current Limitations

- No Docker configuration is currently included.
- Frontend API URLs currently point to localhost and should be configured through a production environment variable.
- The existing job system is suitable for a demo or single-server deployment, but not for horizontal scaling.
