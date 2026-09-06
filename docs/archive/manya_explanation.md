# Manya's Lane: Complete Explanation

Here is a comprehensive breakdown of everything accomplished in Manya's lane. If you need to explain your contribution to the judges, you can walk them through these exact three pillars: the simulator, the proof, and the real-world dataset.

---

## 1. The 3D Sun Simulator (`src/render.py`)
**Why we built it:** 
Our entire project is based on the idea that shadows ruin standard image matching algorithms. However, finding real photographs of the exact same crater under perfect, incrementally changing lighting conditions is nearly impossible. We needed absolute, mathematical control over the sun.

**What you did:**
1. You downloaded the **NASA SLDEM2015** (`data/dem/LDEM_60S_240MPP_ADJ.tiff`), which is a massive 3D elevation map of the Moon's South Pole.
2. You wrote `src/render.py`, a custom hillshade rendering engine built entirely in `numpy`. 
3. **How it works:** The script takes a crop of the 3D map centered perfectly on the Chandrayaan-3 landing site. It calculates the physical slope (surface normal vector) of every single pixel. Then, by providing a "fake" sun angle (azimuth and elevation), it computes a dot-product to figure out exactly how much light hits that slope. This allows us to generate infinite synthetic photos of the crater with perfect shadow simulation.

---

## 2. The Core Proof (`src/premise_test.py`)
**Why we built it:** 
Before the rest of the team spends hours building advanced software to fix the shadow problem, we needed to mathematically prove to the judges that the problem actually exists. We needed to prove that standard software fails.

**What you did:**
1. You used your `render.py` simulator to generate 5 images of the crater. The sun's height was kept the same, but the sun's rotation (azimuth) was changed in each image (0°, 15°, 30°, 60°, 120°).
2. You wrote `src/premise_test.py` to run a standard, industry-standard image matcher (**OpenCV SIFT**) on those images.
3. **The Result:** You proved that as the shadows rotated across the crater, the SIFT algorithm completely collapsed. It went from finding ~1,500 perfect matches to finding just 4 matches. 
4. You plotted this failure into a graph (`demo/premise_plot.png`), which serves as the ultimate justification for why ISRO needs our team's custom solution.

---

## 3. The Ground Truth Dataset (`src/io_lro.py` & `data/lro_nac`)
**Why we built it:** 
Simulated images are great for proving the concept, but the team's final software needs to be tested against real space photographs. We chose NASA LRO (Lunar Reconnaissance Orbiter) images because, unlike Chandrayaan-2 images, NASA embeds the exact solar angle into the file's metadata.

**What you did:**
1. **The Images:** You searched NASA's servers and downloaded 5 massive `.IMG` files. You mathematically verified that the bounding box of every single image perfectly overlaps the Chandrayaan-3 landing site (`69.37°S, 32.35°E`), and that they offer a beautiful spread of lighting conditions (incidence angles ranging from 68° to 78°).
2. **The Reader:** A NASA `.IMG` file contains complex, raw text headers (SPICE kernels). You wrote `src/io_lro.py` to open these weird files, extract the exact coordinates and lighting data, and format them into the shared `Product` structure the rest of the team uses.
3. **The Inventory:** Because opening 250MB files is slow, you generated `data/lro_inventory.csv`. This acts as a lightning-fast spreadsheet that tells the software exactly what images are available without having to load the massive files into memory.

---

### Summary
Your lane provides the **foundation** for the hackathon project. You built the simulator that generated the test data, you wrote the script that mathematically proved the problem exists, and you prepared the real-world NASA photographs that the team will use for final testing.
