"""How often do SIFT (rung 0) and Log-Gabor (rung 1) independently agree on the
8 real pairs? Runs run_pipeline(cascade=True, verify=True) as production Auto does.

    python -m scripts.validate_agreement
"""
import json
import time

from scripts.validate_ch2_crop import CH2_XMLS, PAIRS
from src.io_ch2 import load_product as load_ch2
from src.io_lro import load_product as load_lro
from src.pipeline import run_pipeline

OUT = "docs/research/agreement_validation.json"


def main():
    rows = []
    for ch2_id, lro_file in PAIRS:
        label = f"{ch2_id}_x_{lro_file[:-4]}"
        lro = load_lro(f"data/lro_nac/{lro_file}")
        ch2 = load_ch2(CH2_XMLS[ch2_id], overlap_hint=lro)
        t0 = time.time()
        out = run_pipeline(ch2, lro, align=True, cascade=True, verify=True)
        row = {"pair": label, "seconds": round(time.time() - t0, 1),
               "kept_rung": out["config"]["rung"], **out["config"]["agreement"]}
        print(row, flush=True)
        rows.append(row)
        json.dump(rows, open(OUT, "w"), indent=2)


if __name__ == "__main__":
    main()
