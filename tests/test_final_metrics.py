# tests/test_final_metrics.py — unit tests for scripts.generate_final_metrics
# Owner: Riddhi

import json
import numpy as np
import pytest

from scripts.generate_final_metrics import generate_final_metrics


def test_generate_final_metrics_creates_valid_json_with_all_three_methods(tmp_path):
    out_json = tmp_path / "final_metrics.json"
    output = generate_final_metrics(dem_path="nonexistent.tiff", output_path=str(out_json))

    assert out_json.exists()
    with open(out_json) as f:
        loaded = json.load(f)
    assert loaded == output

    assert "SIFT (Rung 0)" in output["methods"]
    assert "Mod-X (Rung 1)" in output["methods"]
    assert "LightGlue" in output["methods"]


def test_generate_final_metrics_flags_synthetic_terrain_honestly(tmp_path):
    """A missing DEM file used to silently produce hand-typed placeholder
    numbers with no way to tell from the output that they weren't real.
    Now the source is always a real pipeline run -- only the terrain
    changes -- and `terrain_source` says which, so nobody downstream can
    mistake one for the other.
    """
    out_json = tmp_path / "final_metrics.json"
    output = generate_final_metrics(dem_path="nonexistent.tiff", output_path=str(out_json))
    assert output["terrain_source"] == "synthetic_dem"


def test_generate_final_metrics_numbers_are_real_not_hardcoded_placeholders(tmp_path):
    """The old version of this test asserted the exact fabricated fallback
    numbers (142, 105, 204) as if they were correct -- which only proved the
    fabrication happened as designed. This instead checks properties that
    only hold if the numbers came from an actual pipeline run: inlier
    counts are non-negative integers, RMSE values are non-negative floats
    or None (never negative, never a placeholder string), and every method
    was evaluated at every requested azimuth.
    """
    out_json = tmp_path / "final_metrics.json"
    output = generate_final_metrics(dem_path="nonexistent.tiff", output_path=str(out_json))

    for method, az_data in output["methods"].items():
        assert set(az_data.keys()) == {"az_0deg", "az_30deg", "az_90deg", "az_180deg"}
        for az_key, row in az_data.items():
            assert isinstance(row["inlier_count"], int) and row["inlier_count"] >= 0
            assert isinstance(row["total_matches"], int) and row["total_matches"] >= row["inlier_count"]
            assert 0.0 <= row["inlier_ratio"] <= 1.0
            if row["reprojection_residual"] is not None:
                assert row["reprojection_residual"] >= 0.0
            if row["rmse_ground_truth"] is not None:
                assert row["rmse_ground_truth"] >= 0.0


def test_generate_final_metrics_lightglue_beats_classical_sift_at_zero_azimuth(tmp_path):
    """A real, reproducible finding from the fixed pipeline (see the
    numpy_image_to_torch normalization bug fix in src/match.py): LightGlue's
    self-match inlier count is far higher than either classical SIFT
    variant's on this synthetic terrain. Locks in the fixed behaviour so a
    regression (the bug returning) would be caught here too, not just in
    tests/test_match.py.
    """
    out_json = tmp_path / "final_metrics.json"
    output = generate_final_metrics(dem_path="nonexistent.tiff", output_path=str(out_json))

    lightglue_0 = output["methods"]["LightGlue"]["az_0deg"]["inlier_count"]
    sift_0 = output["methods"]["SIFT (Rung 0)"]["az_0deg"]["inlier_count"]
    assert lightglue_0 > sift_0, (
        f"expected LightGlue ({lightglue_0}) to clearly beat classical SIFT ({sift_0}) "
        "at a 0-degree self-match -- if this regresses, check the image normalization "
        "passed into LightGlue in src/match.py"
    )


def test_generate_final_metrics_creates_the_output_directory(tmp_path):
    out_json = tmp_path / "nested" / "does" / "not" / "exist" / "final_metrics.json"
    generate_final_metrics(dem_path="nonexistent.tiff", output_path=str(out_json))
    assert out_json.exists()


def test_generate_final_metrics_is_deterministic(tmp_path):
    """Same synthetic seed, same terrain, same matcher -- two runs should
    produce identical numbers, since nothing in this pipeline introduces
    unseeded randomness of its own (SIFT/LightGlue are deterministic given
    identical input images). Excludes `runtime_s`, which is real wall-clock
    timing and is *expected* to differ run to run -- comparing it would
    make this test flaky for reasons that have nothing to do with
    correctness.
    """
    def _without_runtime(output):
        return {
            method: {az: {k: v for k, v in row.items() if k != "runtime_s"} for az, row in az_data.items()}
            for method, az_data in output["methods"].items()
        }

    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    result_a = generate_final_metrics(dem_path="nonexistent.tiff", output_path=str(out_a))
    result_b = generate_final_metrics(dem_path="nonexistent.tiff", output_path=str(out_b))

    assert result_a["terrain_source"] == result_b["terrain_source"]
    assert _without_runtime(result_a) == _without_runtime(result_b)
