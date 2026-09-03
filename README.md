# SIH Hackathon Project: Lunar Illumination Invariance

## How to run

**IMPORTANT: Do not run scripts directly (e.g. `python src/render.py`).**
This project relies on absolute imports from the `src` package. Running scripts directly will shadow Python standard libraries (like `types`) and cause `ImportError` crashes.

Always run scripts as modules from the root of the repository using the `-m` flag:

```bash
# Correct way to run scripts:
python -m src.render
python -m src.premise_test
python -m scripts.build_lro_inventory
```
