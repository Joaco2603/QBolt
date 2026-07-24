"""Regenerate confirmed ICE instances and every local benchmark artifact."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Sequence

POWER_CORE_ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(POWER_CORE_ROOT))

from src.benchmarks.aggregate_preliminary import aggregate, render
from src.benchmarks.preliminary import BenchmarkConfig, QAOABackend, run_and_write


DEFAULT_SIZES = (6, 8, 10, 12)


def _regional_builder(repository_root: Path) -> Any:
    script = repository_root / "data-analysis" / "scripts" / "build_regional_instance.py"
    spec = importlib.util.spec_from_file_location("build_regional_instance", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load regional instance builder from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def instance_path(repository_root: Path, size: int) -> Path:
    name = "regional_instance.json" if size == 6 else f"regional_instance_{size}.json"
    return repository_root / "power-core" / "artifacts" / name


def benchmark_output_dir(repository_root: Path, size: int) -> Path:
    name = (
        "preliminary_local_benchmark"
        if size == 6
        else f"preliminary_local_benchmark_{size}"
    )
    return repository_root / "power-core" / "artifacts" / name


def reproduce(
    repository_root: Path,
    *,
    sizes: Sequence[int] = DEFAULT_SIZES,
    config: BenchmarkConfig | None = None,
    backend: QAOABackend | None = None,
) -> list[Path]:
    """Regenerate versioned inputs, solver outputs, and the size/depth aggregate."""
    normalized_sizes = tuple(sorted(set(sizes)))
    if not normalized_sizes or any(size < 6 or size > 12 for size in normalized_sizes):
        raise ValueError("sizes must contain integers between 6 and 12")
    selected_config = config or BenchmarkConfig()
    builder = _regional_builder(repository_root)
    substations, lines = builder.load_sources(
        repository_root / "data-analysis" / "dataset"
    )

    result_paths: list[Path] = []
    for size in normalized_sizes:
        destination = instance_path(repository_root, size)
        instance = builder.build_real_regional_instance(
            substations,
            lines,
            count=size,
        )
        destination.write_text(
            json.dumps(instance, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        output_dir = benchmark_output_dir(repository_root, size)
        run_and_write(
            destination,
            output_dir,
            config=selected_config,
            backend=backend,
        )
        result_paths.append(output_dir / "results.json")

    aggregate_document = aggregate(
        list(zip(normalized_sizes, result_paths, strict=True)),
        path_base=repository_root,
    )
    render(
        aggregate_document,
        repository_root
        / "power-core"
        / "artifacts"
        / "preliminary_size_depth_comparison",
    )
    return result_paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=list(DEFAULT_SIZES))
    parser.add_argument("--depths", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--parameter-candidates", type=int, default=5)
    parser.add_argument("--search-shots", type=int, default=128)
    parser.add_argument("--final-shots", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--gw-rounds", type=int, default=128)
    args = parser.parse_args()
    config = BenchmarkConfig(
        depths=args.depths,
        parameter_candidates=args.parameter_candidates,
        search_shots=args.search_shots,
        final_shots=args.final_shots,
        seed=args.seed,
        gw_rounds=args.gw_rounds,
    )
    repository_root = Path(__file__).resolve().parents[3]
    result_paths = reproduce(
        repository_root,
        sizes=args.sizes,
        config=config,
    )
    print(f"regenerated {len(result_paths)} local benchmark result sets")


if __name__ == "__main__":
    main()
