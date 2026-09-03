# Target search area — supersedes the landing-site coordinates in the plan

**Search LRO around this instead of the Chandrayaan-3 landing site.** The
original plan told Manya to center her LROC search on 69.37°S, 32.35°E (the
landing site). That's wrong for this team's actual data — Mehak's real CH2
downloads aren't anywhere near there, so searching LRO at the landing site
would produce zero overlap with any CH2 product we actually have.

## Where Mehak's real CH2 data actually is

Extracted from the geometry ground-track CSVs shipped with each product
(`*_g_grd_*.csv`) — these ship separately from the raster, so this was known
before the .img files finished downloading.

| Product | Lat range | Lon range | Center |
|---|---|---|---|
| `ch2_ohr_ncp_20200229T0739312111_d_img_d18` | −74.3661° to −73.5168° | 43.3595° to 43.9577° | (−73.94, 43.67) |
| `ch2_ohr_ncp_20200229T0938004033_d_img_d32` | −73.9204° to −73.0714° | 42.4571° to 43.0316° | (−73.50, 42.75) |

Confirmed via `geo.footprint_overlap()`: these two products do **not**
overlap each other (0.0 both directions) — adjacent orbit passes, ~0.33°
longitude gap. That's fine; they don't need to overlap each other, only
whatever LRO reference Manya finds.

## Target for Manya's LROC search

**Combined bounding box (union of both products, generous margin for search):**
- Latitude: **−74.4° to −73.1°** (i.e. ~73–74.4°S)
- Longitude: **42.4° to 44.0°E**
- Center point to search from: **(−73.7°, 43.2°)**

Search [data.lroc.im-ldi.com/lroc/search](https://data.lroc.im-ldi.com/lroc/search)
with a bounding box around that center, filtered on incidence angle as
originally planned — that part of the task is unchanged, only the location is.

## Why this matters

`footprint_overlap(ch2_product, lro_product)` needs to come back non-zero for
a pair to be usable at all. Searching independently at two different
locations (landing site vs wherever CH2 actually is) guarantees it comes back
zero. This file is the single target both lanes should build against, so
nobody has to guess or re-derive it.
