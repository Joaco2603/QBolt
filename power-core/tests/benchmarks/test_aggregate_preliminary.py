"""Contract tests for the size/depth benchmark aggregator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.benchmarks.aggregate_preliminary import aggregate


def _write_result(path: Path, *, node_count: int, depths: tuple[int, ...] = (1, 2)) -> None:
    path.write_text(
        json.dumps(
            {
                "benchmark": "challenge_1_local_preliminary",
                "configuration": {
                    "depths": list(depths),
                    "independent_runs_per_configuration": 1,
                },
                "input": {
                    "node_count": node_count,
                    "edge_count": node_count - 1,
                    "sha256": f"digest-{node_count}",
                    "path": f"instance-{node_count}.json",
                    "source": "ICE",
                    "edge_model": "confirmed_transmission_lines",
                    "weight_model": "sum_nominal_voltage_kv",
                },
                "exact": {"cut": 10.0},
                "greedy": {"cut": 9.0, "ratio": 0.9},
                "goemans_williamson": {"cut": 10.0, "ratio": 1.0},
                "qaoa": [
                    {
                        "p": depth,
                        "status": "completed",
                        "expected_cut": 5.0 + depth,
                        "expected_ratio": (5.0 + depth) / 10.0,
                        "best_sample_cut": 10.0,
                        "best_sample_ratio": 1.0,
                        "independent_runs": 1,
                        "parameter_candidates_completed": 5,
                    }
                    for depth in depths
                ],
            }
        ),
        encoding="utf-8",
    )


def test_aggregate_validates_node_count_and_preserves_single_run_semantics(
    tmp_path: Path,
) -> None:
    eight = tmp_path / "eight.json"
    ten = tmp_path / "ten.json"
    _write_result(eight, node_count=8)
    _write_result(ten, node_count=10)

    result = aggregate([(8, eight), (10, ten)], path_base=tmp_path)

    assert [item["node_count"] for item in result["instances"]] == [8, 10]
    assert [item["results_path"] for item in result["instances"]] == [
        "eight.json",
        "ten.json",
    ]
    assert all("mean_expected_ratio" not in row for row in result["rows"])
    assert all(row["std_expected_ratio"] is None for row in result["rows"])
    assert result["comparison"]["qaoa_observation_unit"] == (
        "one preliminary run per node-count and p"
    )


def test_aggregate_rejects_a_cli_size_that_disagrees_with_the_result(
    tmp_path: Path,
) -> None:
    result_path = tmp_path / "result.json"
    _write_result(result_path, node_count=8)

    with pytest.raises(ValueError, match="declares 10 nodes but result contains 8"):
        aggregate([(10, result_path)])


def test_aggregate_rejects_mixed_depth_configurations(tmp_path: Path) -> None:
    eight = tmp_path / "eight.json"
    ten = tmp_path / "ten.json"
    _write_result(eight, node_count=8, depths=(1, 2))
    _write_result(ten, node_count=10, depths=(1, 3))

    with pytest.raises(ValueError, match="same QAOA depths"):
        aggregate([(8, eight), (10, ten)])
