"""Tests for the single local benchmark reproduction entry point."""

from pathlib import Path

from src.benchmarks.reproduce_local import benchmark_output_dir, instance_path


def test_reproduction_paths_are_versioned_and_stable(tmp_path: Path) -> None:
    assert instance_path(tmp_path, 6) == (
        tmp_path / "power-core" / "artifacts" / "regional_instance.json"
    )
    assert instance_path(tmp_path, 10) == (
        tmp_path / "power-core" / "artifacts" / "regional_instance_10.json"
    )
    assert benchmark_output_dir(tmp_path, 6) == (
        tmp_path / "power-core" / "artifacts" / "preliminary_local_benchmark"
    )
    assert benchmark_output_dir(tmp_path, 10) == (
        tmp_path / "power-core" / "artifacts" / "preliminary_local_benchmark_10"
    )
