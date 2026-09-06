# Chandrayaan-2 OHRC Data

This project reads real Chandrayaan-2 OHRC products from the public archive and creates metadata and preview images for the team.

## Setup

Use Python 3.11 or newer. A Conda environment is recommended because GDAL is needed to read the PDS4 labels and image files.

```powershell
conda create -n sih python=3.11
conda activate sih
conda install -c conda-forge gdal
python -m pip install -r requirements.txt
```

On Windows, make sure VS Code is using the `sih` interpreter:

```text
C:\Users\<you>\anaconda3\envs\sih\python.exe
```

## Data

The source archive is:

<https://archive.org/details/chandrayaan-2-high-resolution-images-of-the-moon>

A product consists of a PDS4 `.xml` label and a matching `.img` file in the same data directory. Only products whose IDs begin with `ch2_` belong to Chandrayaan-2. Do not include `ch1_` products, which are from Chandrayaan-1.

The repository currently includes downloaded OHRC products under:

```text
ch2_ohr_ncp_*/data/calibrated/20200229/
```

## Read one product

From the repository root, run:

```powershell
python -m src.io_ch2 "ch2_ohr_ncp_20200229T0739312111_d_img_d18\data\calibrated\20200229\ch2_ohr_ncp_20200229T0739312111_d_img_d18.xml"
```

The command prints the product ID, image shape, ground sample distance, corner coordinates, acquisition time, and optional instrument metadata.

In Python, use the shared `Product` shape:

```python
from src.io_ch2 import load_product

product = load_product("path/to/product.xml")
print(product.array.shape)
print(product.corners)
```

## Build the inventory

To scan all downloaded labels and write the CSV:

```powershell
python -m scripts.make_ch2_inventory --dir . --out data/ch2_inventory.csv
```

The inventory contains product IDs, instrument names, acquisition times, corner coordinates, GSD, image dimensions, and source label paths.

## Create PNG previews

To create previews for all downloaded products:

```powershell
python -m scripts.preview_ch2 --dir . --out demo/previews
```

The generated grayscale PNG files are written to `demo/previews/` and can be opened directly from VS Code or any image viewer.

## Run tests

```powershell
python -m pytest tests\ -v
```

The tests use synthetic images to validate the matcher. A successful run currently reports two passing tests.

## Expected outputs

After setup and processing, these paths should exist:

```text
data/ch2_inventory.csv
demo/previews/*.png
src/io_ch2.py
```

Large downloaded image files may exceed normal GitHub repository limits. If the raw files are not committed, download them from the archive above and keep the same directory structure before running the commands.

## Registered pair hand-off

Before travelling, confirm that the two Chandrayaan-2 product folders and their
paired `.xml` and `.img` files are present on the USB stick. The USB check is a
physical step and cannot be verified by GitHub or this repository.

The registered-pair command currently works with two LRO NAC products. Place
two real LRO files under `data/lro_nac/`, then run this from the repository root:

```powershell
python -m scripts.make_real_pair_result `
	data/lro_nac/A.IMG `
	data/lro_nac/B.IMG
```

The command reports each stage: loading A, loading B, matching, and writing the
handoff. It warps A into B's pixel frame using the fitted homography and writes
one self-contained result folder:

```text
demo/real_pair_result/
	registered_a_to_b.tif   # A warped into B's frame, GeoTIFF
	overlay_rgb.png         # red=B, green=registered A
	match_points.csv        # human-readable pixel and lon/lat coordinates
	match_points.geojson    # same points as geographic LineString features
	metrics.json            # transform, RMSE, inlier count, and coverage
```

The match-point CSV is the primary honest deliverable. Each row records both
image coordinates, both geographic coordinates, the match score, and whether
RANSAC kept the point as an inlier. Open it in a spreadsheet or inspect it as
plain text before handing it over.

When Reia's inversion and `cnet.py` are available, export the same inlier rows
through `cnet.py`, then parse the result again with `pvl` as a round-trip
validation. That control-network step is intentionally not claimed here until
the inversion implementation lands.

## API and Job Store

The project includes a FastAPI backend (`src/api.py`) for managing products and execution of the LunarMatch pipeline. 

### Starting the API

Run the server from the repository root:

```powershell
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

### Endpoints

- **`GET /products`**: Returns the combined inventory list from `data/lro_inventory.csv` and `data/ch2_inventory.csv`. Exposes product information required for matching, including sun angle and GSD.
- **`POST /register`**: Accepts a JSON payload containing `product_a`, `product_b`, and `rung` (0, 1, or 2). Validates that the products exist in the inventory, assigns a unique `job_id`, updates the `jobs.db` SQLite database to `pending`, and immediately returns the `job_id` while spinning up the real pipeline execution in the background.
- **`GET /jobs/{id}`**: Returns the current status of the job (e.g., `pending`, `completed`, `failed`), along with pipeline metrics like `rmse`, `inliers`, and `coverage`.
- **`GET /jobs/{id}/artefacts/{filename}`**: Serves generated artefacts from the job's directory (`data/jobs/{job_id}`). Can be used to download the overlay PNG (`overlay_rgb.png`), registered raster (`registered_a_to_b.tif`), metrics JSON, etc.

