"""One-time pass that records a footprint for every LRO product in the
inventory, so /candidates and /overlap can answer from metadata alone.

CH2 footprints need no ingest (parsed from each label on demand). An LRO
footprint only exists after the product has been loaded once, because its
corners come from SPICE geometry; src/io_lro.py records it at that point.
This just forces that first load for products that haven't had one. Loads
served from the product cache are fast; a never-loaded product makes NAIF
WebGeocalc network calls (~35-50s each).

    python -m scripts.ingest_catalog
"""
import time

import src.api as api
import src.catalog as catalog
import src.io_lro as io_lro


def main():
    api.load_inventory()
    todo = [(pid, path) for pid, path in api.PRODUCT_CACHE.items()
            if not catalog.is_ch2(pid) and not pid.startswith("synthetic_")]
    print(f"{len(todo)} LRO products in the inventory")
    for pid, path in sorted(todo):
        if catalog.footprint(pid, path) is not None:
            print(f"  {pid:<16} already has a footprint")
            continue
        t0 = time.time()
        try:
            io_lro.load_product(path)
        except Exception as exc:  # keep going: one bad product shouldn't block the rest
            print(f"  {pid:<16} FAILED to load: {exc}")
            continue
        ok = catalog.footprint(pid, path) is not None
        print(f"  {pid:<16} {'recorded' if ok else 'loaded, but geometry unresolved (no footprint)'}"
              f"  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
