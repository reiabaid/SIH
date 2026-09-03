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
