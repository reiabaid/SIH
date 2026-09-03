import os
import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image

def load_dem_patch(path: str, row_start: int, col_start: int, size: int) -> tuple[np.ndarray, float]:
    """
    Open the GeoTIFF at path and read a square window of size x size pixels.
    Returns the DEM as a 2D float32 numpy array and the pixel spacing in metres.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"DEM file not found: {path}")

    with rasterio.open(path) as src:
        # Check bounds
        if row_start < 0 or col_start < 0 or row_start + size > src.height or col_start + size > src.width:
            raise ValueError(f"Requested window (row={row_start}, col={col_start}, size={size}) "
                             f"is out of bounds for raster {path} (shape {src.height}x{src.width})")

        window = Window(col_start, row_start, size, size)
        dem = src.read(1, window=window).astype(np.float32)
        
        # Pixel spacing is usually the scale in the transform (dx, dy).
        # We assume square pixels here (dx == -dy or dx == dy).
        transform = src.transform
        pixel_spacing = float(abs(transform.a))

    return dem, pixel_spacing


def compute_surface_normals(dem: np.ndarray, pixel_spacing: float) -> np.ndarray:
    """
    Compute per-pixel surface normal vectors from a DEM.
    Returns an array of shape (H, W, 3).
    """
    # np.gradient returns gradients along axes. For a 2D array, it returns (dy, dx).
    # Note: row index increases downwards, so np.gradient(dem)[0] is dz/d_row.
    # If we map row to -Y (North is up) and col to +X (East is right):
    dy_px, dx_px = np.gradient(dem, pixel_spacing)
    
    # We negate the gradients to form the normal vector.
    # To maintain an ENU (East, North, Up) convention where X is East and Y is North:
    # dz/dx is dx_px. dz/dy is -dy_px (since row increases South).
    # Normal is [-dz/dx, -dz/dy, 1].
    # Thus, normal_x = -dx_px, normal_y = dy_px, normal_z = 1.
    nx = -dx_px
    ny = dy_px
    nz = np.ones_like(dem)

    # Normalize the vectors
    magnitude = np.sqrt(nx**2 + ny**2 + nz**2)
    
    # Stack into (H, W, 3)
    normals = np.stack([nx / magnitude, ny / magnitude, nz / magnitude], axis=-1)
    return normals


def sun_direction(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """
    Convert sun azimuth and elevation into a 3D unit vector in the ENU frame.
    Azimuth: 0 = North, 90 = East.
    """
    az_rad = np.radians(azimuth_deg)
    el_rad = np.radians(elevation_deg)
    
    # ENU frame: X = East, Y = North, Z = Up
    # Azimuth is clockwise from North.
    sx = np.sin(az_rad) * np.cos(el_rad)
    sy = np.cos(az_rad) * np.cos(el_rad)
    sz = np.sin(el_rad)
    
    return np.array([sx, sy, sz], dtype=np.float32)


def render_hillshade(dem: np.ndarray, pixel_spacing: float, azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """
    Render a shaded relief image from the DEM given sun azimuth and elevation.
    Returns a 2D uint8 array [0, 255].
    """
    normals = compute_surface_normals(dem, pixel_spacing)
    sun_vec = sun_direction(azimuth_deg, elevation_deg)
    
    # Dot product: normals is (H, W, 3), sun_vec is (3,)
    # Result is (H, W)
    illumination = np.dot(normals, sun_vec)
    
    # Clip to [0, 1] (ignore light from below ground)
    illumination = np.clip(illumination, 0, 1)
    
    # Scale to [0, 255]
    img = (illumination * 255).astype(np.uint8)
    return img


if __name__ == "__main__":
    DEM_PATH = "data/dem/LDEM_60S_240MPP_ADJ.tiff"
    OUT_DIR = "demo/synthetic_renders"
    
    # Create output directory
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # Sensible crop: try to pick an interesting patch
    # We use a try-except to handle if the file doesn't exist yet on disk.
    try:
        size = 512
        # Pixel index of 69.37S, 32.35E is roughly (row=1653, col=5290)
        # We subtract half the size (256) to perfectly center the landing site!
        row_start = 1397
        col_start = 5034
        
        print(f"Loading DEM patch from {DEM_PATH}...")
        dem, spacing = load_dem_patch(DEM_PATH, row_start, col_start, size)
        
        print(f"Patch loaded. Mean elevation: {dem.mean():.1f}m, Std dev: {dem.std():.1f}m")
        if dem.std() < 5.0:
            print("WARNING: The selected patch is very flat (std < 5m). You may want to adjust the row/col offset.")
            
        elevation = 30.0
        azimuths = [0, 15, 30, 60, 120]
        
        for az in azimuths:
            print(f"Rendering hillshade for Azimuth={az}°, Elevation={elevation}°...")
            img_arr = render_hillshade(dem, spacing, az, elevation)
            
            out_path = os.path.join(OUT_DIR, f"hillshade_az{az}.png")
            Image.fromarray(img_arr).save(out_path)
            print(f"  Saved {out_path}")
            
    except Exception as e:
        print(f"Execution failed: {e}")
