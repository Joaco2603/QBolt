"""Fast Guppy-free tests for the preliminary Challenge 1 benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import networkx as nx
import pytest

from src.benchmarks.preliminary import (
    BenchmarkConfig,
    build_max_cut_ising,
    exact_max_cut,
    metrics_from_counts,
    run_benchmark,
    write_outputs,
)
from src.optimizer.quantum.qaoa import MeasurementBatch


class DeterministicBackend:
    name = "fake-local"

    def execute(self, program, gamma, beta, *, shots, seed):
        cut_shots = shots * 3 // 4
        return MeasurementBatch(
            {
                "0" * len(program.variables): shots - cut_shots,
                "0" * (len(program.variables) - 1) + "1": cut_shots,
                "1" * len(program.variables): 0,
            },
            metadata={"fake": True, "seed": seed},
        )


class FailingDepthBackend(DeterministicBackend):
    def execute(self, program, gamma, beta, *, shots, seed):
        if program.layers == 2:
            raise RuntimeError("intentional p=2 failure")
        return super().execute(program, gamma, beta, shots=shots, seed=seed)


def _write_two_node_artifact(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source": "test fixture",
                "edge_model": "test",
                "weight_model": "test_weight",
                "weight_units": "unit",
                "weight_definition": "fixture edge weight",
                "limitations": ["fixture only"],
                "nodes": [{"id": "a"}, {"id": "b"}],
                "edges": [{"source": "a", "target": "b", "weight": 2.0}],
            }
        ),
        encoding="utf-8",
    )


def _fake_gw(graph, *, seed, rounds, optimal_weight):
    nodes = tuple(sorted(graph.nodes))
    cut = float(optimal_weight)
    return SimpleNamespace(
        positive_partition=(nodes[0],),
        negative_partition=(nodes[1],),
        cut_weight=cut,
        sdp_value=cut,
        seed=seed,
        rounds=rounds,
        winning_round=0,
        solver="FAKE",
        solver_status="optimal",
        solver_options=(),
    )


def test_exact_max_cut_finds_weighted_optimum() -> None:
    graph = nx.Graph()
    graph.add_weighted_edges_from(
        (("a", "b", 1.0), ("b", "c", 2.0), ("a", "c", 3.0))
    )

    result = exact_max_cut(graph)

    assert result["cut"] == pytest.approx(5.0)
    assert result["assignments_evaluated"] == 4
    assert result["bitstring"] == "001"
    assert result["partition_zero"] == ["a", "b"]
    assert result["partition_one"] == ["c"]


def test_metrics_from_counts_excludes_zero_states_and_uses_expected_cut() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=2.0)
    model = build_max_cut_ising(graph)

    metrics = metrics_from_counts(graph, model, {"00": 1, "01": 3, "11": 0})

    assert metrics["counts"] == {"00": 1, "01": 3}
    assert metrics["shots_observed"] == 4
    assert metrics["expected_cut"] == pytest.approx(1.5)
    assert metrics["expected_energy"] == pytest.approx(-1.5)
    assert metrics["best_sample_cut"] == pytest.approx(2.0)
    assert metrics["best_sample_bitstring"] == "01"
    assert "11" not in metrics["state_metrics"]


def test_schema_and_outputs_are_generated_with_fake_backend(tmp_path: Path) -> None:
    input_path = tmp_path / "instance.json"
    output_dir = tmp_path / "output"
    _write_two_node_artifact(input_path)
    config = BenchmarkConfig(
        depths=(1, 3),
        parameter_candidates=2,
        search_shots=8,
        final_shots=12,
        seed=17,
        gw_rounds=3,
    )

    results = run_benchmark(
        input_path,
        config=config,
        backend=DeterministicBackend(),
        gw_solver=_fake_gw,
    )
    write_outputs(results, output_dir)

    assert results["schema_version"] == 1
    assert results["study_status"] == "preliminary"
    assert results["execution_status"] == "completed"
    assert len(results["input"]["sha256"]) == 64
    assert results["exact"]["cut"] == pytest.approx(2.0)
    assert results["greedy"]["status"] == "completed"
    assert results["goemans_williamson"]["status"] == "completed"
    assert results["reporting"] == {
        "independent_runs_per_configuration": 1,
        "parameter_candidates_are_independent_runs": False,
        "mean_std_error_bars_reported": False,
        "convergence_claimed": False,
        "quantum_advantage_claimed": False,
    }
    assert [item["p"] for item in results["qaoa"]] == [1, 3]
    for item in results["qaoa"]:
        assert item["status"] == "completed"
        assert item["expected_cut"] == pytest.approx(1.5)
        assert item["expected_ratio"] == pytest.approx(0.75)
        assert item["best_sample_ratio"] == pytest.approx(1.0)
        assert item["counts"] == {"00": 3, "01": 9}
        assert len(item["parameters"]["gamma"]) == item["p"]
        assert len(item["candidates"]) == 2
        assert "11" not in item["counts"]

    assert sorted(path.name for path in output_dir.iterdir()) == [
        "README.md",
        "approximation_ratio_vs_p.png",
        "results.json",
    ]
    persisted = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert persisted["input"]["sha256"] == results["input"]["sha256"]
    assert (output_dir / "approximation_ratio_vs_p.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "Estado: `preliminary`" in readme
    assert "candidatos de parámetros dentro de UNA corrida independiente" in readme
    assert "no se reportan media, desviación estándar ni barras de error" in readme


def test_backend_failure_is_preserved_per_depth_and_other_depths_continue(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "instance.json"
    output_dir = tmp_path / "failed-output"
    _write_two_node_artifact(input_path)
    config = BenchmarkConfig(
        depths=(1, 2, 3),
        parameter_candidates=2,
        search_shots=4,
        final_shots=4,
        seed=5,
        gw_rounds=2,
    )

    results = run_benchmark(
        input_path,
        config=config,
        backend=FailingDepthBackend(),
        gw_solver=_fake_gw,
    )
    write_outputs(results, output_dir)

    by_depth = {item["p"]: item for item in results["qaoa"]}
    assert results["execution_status"] == "completed_with_failures"
    assert by_depth[1]["status"] == "completed"
    assert by_depth[2]["status"] == "failed"
    assert by_depth[2]["error"]["message"] == "all parameter candidates failed"
    assert by_depth[2]["parameter_candidates_completed"] == 0
    assert all(candidate["status"] == "failed" for candidate in by_depth[2]["candidates"])
    assert by_depth[3]["status"] == "completed"
    assert (output_dir / "results.json").is_file()
    assert (output_dir / "approximation_ratio_vs_p.png").is_file()
    assert "p=2" in (output_dir / "README.md").read_text(encoding="utf-8")
