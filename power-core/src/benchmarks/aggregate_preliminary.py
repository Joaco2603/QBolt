"""Aggregate preliminary benchmark results by instance size and QAOA depth."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


def _display_path(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base))
    except ValueError:
        return str(path)


def _parse_input(value: str) -> tuple[int, Path]:
    try:
        size_text, path_text = value.split("=", 1)
        size = int(size_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("inputs must use NODES=RESULTS_JSON") from error
    if size < 6:
        raise argparse.ArgumentTypeError("instance size must be at least 6")
    path = Path(path_text)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"results file does not exist: {path}")
    return size, path


def aggregate(
    inputs: list[tuple[int, Path]],
    *,
    path_base: Path | None = None,
) -> dict[str, Any]:
    """Combine compatible benchmark results while keeping paths portable."""
    display_base = (path_base or Path.cwd()).resolve()
    rows: list[dict[str, Any]] = []
    instances: list[dict[str, Any]] = []
    documents: list[tuple[int, Path, dict[str, Any]]] = []
    expected_depths: tuple[int, ...] | None = None
    for node_count, path in sorted(inputs):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("benchmark") != "challenge_1_local_preliminary":
            raise ValueError(f"{path} is not a Challenge 1 preliminary benchmark")
        input_info = document["input"]
        actual_node_count = int(input_info["node_count"])
        if actual_node_count != node_count:
            raise ValueError(
                f"CLI declares {node_count} nodes but result contains "
                f"{actual_node_count}: {path}"
            )
        depths = tuple(int(depth) for depth in document["configuration"]["depths"])
        if expected_depths is None:
            expected_depths = depths
        elif depths != expected_depths:
            raise ValueError("all aggregated results must use the same QAOA depths")
        if tuple(item["p"] for item in document["qaoa"]) != depths:
            raise ValueError(f"QAOA rows do not match configured depths: {path}")
        documents.append((node_count, path, document))
        instances.append({
            "node_count": node_count,
            "edge_count": input_info["edge_count"],
            "sha256": input_info["sha256"],
            "source": input_info.get("source"),
            "edge_model": input_info.get("edge_model"),
            "weight_model": input_info.get("weight_model"),
            "results_path": _display_path(path, display_base),
        })
        for qaoa in document["qaoa"]:
            rows.append({
                "node_count": node_count,
                "p": qaoa["p"],
                "expected_cut": qaoa.get("expected_cut"),
                "expected_ratio": qaoa.get("expected_ratio"),
                "best_sample_cut": qaoa.get("best_sample_cut"),
                "best_sample_ratio": qaoa.get("best_sample_ratio"),
                "status": qaoa.get("status"),
                "independent_runs": qaoa.get("independent_runs", document["configuration"].get("independent_runs_per_configuration")),
                "parameter_candidates": qaoa.get("parameter_candidates_completed"),
                "expected_ratio_observation": (
                    qaoa.get("expected_ratio")
                    if str(qaoa.get("status", "")).startswith("completed")
                    else None
                ),
                "std_expected_ratio": None,
            })
    return {
        "benchmark": "challenge_1_preliminary_size_depth_comparison",
        "comparison": {
            "metric": "expected QAOA cut / exact optimal cut",
            "ratio_definition": "E_QAOA / E_optimal",
            "qaoa_observation_unit": "one preliminary run per node-count and p",
            "standard_deviation": "null because each configuration has one independent run",
        },
        "instances": instances,
        "rows": rows,
        "baselines": [
            {
                "node_count": node_count,
                "exact_cut": document["exact"]["cut"],
                "greedy_cut": document["greedy"]["cut"],
                "greedy_ratio": document["greedy"]["ratio"],
                "gw_cut": document["goemans_williamson"]["cut"],
                "gw_ratio": document["goemans_williamson"]["ratio"],
            }
            for node_count, _path, document in documents
        ],
    }


def render(document: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with (output_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        rows = document["rows"]
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    figure, axis = plt.subplots(figsize=(10, 6))
    rows = document["rows"]
    for depth in sorted({row["p"] for row in rows}):
        selected = [
            row
            for row in rows
            if row["p"] == depth and str(row["status"]).startswith("completed")
        ]
        axis.plot(
            [row["node_count"] for row in selected],
            [row["expected_ratio_observation"] for row in selected],
            marker="o",
            label=f"QAOA p={depth}",
        )
    baseline = document["baselines"]
    axis.plot([row["node_count"] for row in baseline], [row["greedy_ratio"] for row in baseline], "--", label="Greedy")
    axis.plot([row["node_count"] for row in baseline], [row["gw_ratio"] for row in baseline], "--", label="Goemans–Williamson")
    axis.set_xlabel("Número de nodos")
    axis.set_ylabel("Ratio de aproximación esperado")
    axis.set_title("Benchmark preliminar: profundidad p frente al tamaño de instancia")
    axis.set_ylim(0, 1.05)
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "approximation_ratio_vs_nodes_and_p.png", dpi=220)
    plt.close(figure)

    input_lines = [
        f"  --input {item['node_count']}={item['results_path']} \\"
        for item in document["instances"]
    ]
    lines = [
        "# Comparación preliminar por tamaño y profundidad",
        "",
        "Este agregado compara QAOA por tamaño de instancia y profundidad.",
        "La métrica principal es `E_QAOA / E_optimal`; también se incluyen greedy y GW.",
        "",
        "Cada configuración tiene una sola corrida independiente. Por ello no se",
        "reportan desviaciones estándar: se guardan como `null`. Los cinco candidatos",
        "de parámetros no equivalen a cinco corridas independientes.",
        "",
        "Todas las instancias deben declarar el modelo de aristas y el peso en el JSON.",
        "No se afirma escalabilidad ni ventaja cuántica a partir de una sola corrida.",
        "",
        "## Reproducción",
        "",
        "```bash",
        "python power-core/src/benchmarks/aggregate_preliminary.py \\",
        *input_lines,
        "  --output-dir power-core/artifacts/preliminary_size_depth_comparison",
        "```",
    ]
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=_parse_input, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    render(aggregate(args.input), args.output_dir)
    print(f"wrote aggregate benchmark outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
