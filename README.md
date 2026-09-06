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

## Docs

- [`docs/USAGE.md`](docs/USAGE.md) — reading real CH2/LRO data, building inventories, running the API
- [`docs/ARCHITECTURE_AND_SOLUTION.md`](docs/ARCHITECTURE_AND_SOLUTION.md) — pipeline architecture and approach
- [`docs/FRONTEND.md`](docs/FRONTEND.md) — frontend build spec
- [`docs/OPTIMIZATION_REPORT.md`](docs/OPTIMIZATION_REPORT.md) — match.py vectorization/parallelization notes
- [`docs/TARGET_AREA.md`](docs/TARGET_AREA.md) — current real target search box
- [`docs/PITCH_DECK_FOR_JUDGES.md`](docs/PITCH_DECK_FOR_JUDGES.md) — hackathon pitch deck
- [`docs/archive/`](docs/archive/) — superseded status reports and individual team members' working notes, kept for history
