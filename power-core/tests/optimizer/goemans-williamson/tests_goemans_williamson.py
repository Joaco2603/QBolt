"""Executable Goemans-Williamson behavioural tests.

The implementation is loaded by path so this suite can run independently of
the repository's package-installation configuration.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from itertools import product
from pathlib import Path

import networkx as nx
import numpy as np
import pytest


REPOSITORY_ROOT = Path(__file__).parents[4]
MODULE_PATH = REPOSITORY_ROOT / "power-core" / "src" / "optimizer" / "goemans_williamson.py"
MODULE_SPEC = importlib.util.spec_from_file_location("goemans_williamson_nested_tests", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = MODULE
MODULE_SPEC.loader.exec_module(MODULE)

GoemansWilliamsonError = MODULE.GoemansWilliamsonError
cut_weight = MODULE.cut_weight
factor_sdp_solution = MODULE.factor_sdp_solution
ising_cut_value = MODULE.ising_cut_value
laplacian_cut_value = MODULE.laplacian_cut_value
solve_goemans_williamson = MODULE.solve_goemans_williamson


def exact_max_cut(graph: nx.Graph) -> float:
    """Compute the exact optimum for the small graphs used by this suite."""

    nodes = tuple(graph.nodes)
    if not nodes:
        return 0.0
    return max(
        ising_cut_value(
            graph,
            {nodes[0]: 1, **dict(zip(nodes[1:], labels, strict=True))},
        )
        for labels in product((-1, 1), repeat=len(nodes) - 1)
    )


def triangle() -> nx.Graph:
    graph = nx.Graph()
    graph.add_weighted_edges_from((
        ("a", "b", 1.0),
        ("b", "c", 1.0),
        ("a", "c", 1.0),
    ))
    return graph


def test_cut_objectives_sum_each_undirected_edge_once() -> None:
    graph = nx.Graph()
    graph.add_weighted_edges_from((
        ("a", "b", 2.0),
        ("b", "c", 3.0),
        ("a", "c", 5.0),
    ))
    labels = {"a": 1, "b": -1, "c": 1}

    assert cut_weight(graph, {"a", "c"}) == pytest.approx(5.0)
    assert ising_cut_value(graph, labels) == pytest.approx(5.0)
    assert laplacian_cut_value(graph, labels) == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("graph", "message"),
    [
        (nx.DiGraph((("a", "b", {"weight": 1.0}),)), "undirected"),
        (nx.MultiGraph((("a", "b", {"weight": 1.0}),)), "simple"),
        (nx.Graph((("a", "b"),)), "weight"),
    ],
)
def test_rejects_unsupported_graphs(graph: nx.Graph, message: str) -> None:
    with pytest.raises((GoemansWilliamsonError, TypeError), match=message):
        solve_goemans_williamson(graph, seed=7)


@pytest.mark.parametrize("weight", (float("nan"), float("inf"), -1.0))
def test_rejects_invalid_weights(weight: float) -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=weight)

    with pytest.raises(GoemansWilliamsonError, match="weight"):
        solve_goemans_williamson(graph, seed=7)


def test_rejects_invalid_nodes_rounds_and_seed() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=1.0)
    invalid_node_graph = nx.Graph()
    invalid_node_graph.add_edge(1, 2, weight=1.0)
    loop_graph = nx.Graph()
    loop_graph.add_edge("a", "a", weight=1.0)

    with pytest.raises(GoemansWilliamsonError, match="string"):
        solve_goemans_williamson(invalid_node_graph, seed=7)
    with pytest.raises(GoemansWilliamsonError, match="self-loop"):
        solve_goemans_williamson(loop_graph, seed=7)
    with pytest.raises(GoemansWilliamsonError, match="rounds"):
        solve_goemans_williamson(graph, seed=7, rounds=0)
    with pytest.raises(GoemansWilliamsonError, match="seed"):
        solve_goemans_williamson(graph, seed=True)


def test_single_edge_sdp_is_exact_and_feasible() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=7.0)

    result = solve_goemans_williamson(graph, seed=11, rounds=8, optimal_weight=7.0)

    assert result.cut_weight == pytest.approx(7.0, abs=1e-4)
    assert result.sdp_value == pytest.approx(7.0, abs=1e-4)
    assert result.empirical_ratio == pytest.approx(1.0)
    assert np.allclose(result.sdp_matrix, result.sdp_matrix.T, atol=1e-6)
    assert np.allclose(np.diag(result.sdp_matrix), 1.0, atol=1e-5)
    assert np.linalg.eigvalsh(result.sdp_matrix).min() >= -1e-5


def test_triangle_sdp_is_an_upper_bound_on_exact_optimum() -> None:
    graph = triangle()
    optimum = exact_max_cut(graph)
    result = solve_goemans_williamson(graph, seed=19, rounds=32, optimal_weight=optimum)

    assert optimum == pytest.approx(2.0)
    assert result.cut_weight <= optimum + 1e-6
    assert optimum <= result.sdp_value + 1e-4
    assert result.sdp_value == pytest.approx(2.25, abs=2e-3)
    assert result.empirical_ratio == pytest.approx(result.cut_weight / optimum)


def test_factorization_repairs_only_tolerance_sized_psd_error() -> None:
    repaired = factor_sdp_solution(
        np.array(((1.0, 1.0 + 1e-7), (1.0 + 1e-7, 1.0))),
        tolerance=1e-6,
    )
    assert np.allclose(np.linalg.norm(repaired, axis=1), 1.0, atol=1e-8)

    with pytest.raises(GoemansWilliamsonError, match="positive semidefinite"):
        factor_sdp_solution(np.array(((1.0, 1.1), (1.1, 1.0))), tolerance=1e-6)


@pytest.mark.parametrize("optimal_weight", (True, -1.0, float("nan"), float("inf")))
def test_rejects_invalid_optimal_weight(optimal_weight: float | bool) -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=1.0)

    with pytest.raises(GoemansWilliamsonError, match="optimal_weight"):
        solve_goemans_williamson(graph, seed=7, optimal_weight=optimal_weight)


def test_rejects_failed_solver_output(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=1.0)

    monkeypatch.setattr(MODULE.cp.Problem, "solve", lambda self, **_: None)

    with pytest.raises(GoemansWilliamsonError, match="returned status"):
        solve_goemans_williamson(graph, seed=7)


def test_seeded_rounding_is_reproducible_and_partitions_are_disjoint() -> None:
    first = solve_goemans_williamson(triangle(), seed=23, rounds=16)
    second = solve_goemans_williamson(triangle(), seed=23, rounds=16)

    assert first == second
    assert set(first.positive_partition).isdisjoint(first.negative_partition)
    assert set(first.positive_partition) | set(first.negative_partition) == {"a", "b", "c"}
    assert 0 <= first.winning_round < first.rounds


def test_zero_dot_product_is_positive_and_ties_keep_the_earliest_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedGenerator:
        def __init__(self) -> None:
            self.directions = iter((np.array((0.0, -1.0)), np.array((1.0, 0.0))))

        def normal(self, size: int) -> np.ndarray:
            assert size == 2
            return next(self.directions)

    graph = nx.Graph()
    graph.add_edge("a", "b", weight=0.0)
    monkeypatch.setattr(MODULE, "factor_sdp_solution", lambda _: np.eye(2))
    monkeypatch.setattr(MODULE.np.random, "default_rng", lambda _: FixedGenerator())

    result = solve_goemans_williamson(graph, seed=1, rounds=2)

    assert result.positive_partition == ("a",)
    assert result.negative_partition == ("b",)
    assert result.winning_round == 0


def test_more_rounds_cannot_underperform_first_seeded_round() -> None:
    first = solve_goemans_williamson(triangle(), seed=31, rounds=1)
    many = solve_goemans_williamson(triangle(), seed=31, rounds=32)

    assert many.cut_weight >= first.cut_weight


def test_empty_isolated_and_zero_weight_graphs_have_undefined_ratio() -> None:
    empty = nx.Graph()
    isolated = nx.Graph()
    isolated.add_nodes_from(("a", "b"))
    zero_weight = nx.Graph()
    zero_weight.add_edge("a", "b", weight=0.0)

    for graph in (empty, isolated, zero_weight):
        result = solve_goemans_williamson(graph, seed=3, optimal_weight=0.0)
        assert result.cut_weight == pytest.approx(0.0)
        assert result.empirical_ratio is None


def test_unknown_solver_is_reported_as_a_domain_error() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=1.0)

    with pytest.raises(GoemansWilliamsonError, match="solver"):
        solve_goemans_williamson(graph, seed=7, solver="NOT_A_SOLVER")


def test_regional_artifact_matches_documented_optimum_and_bound() -> None:
    artifact_path = REPOSITORY_ROOT / "power-core" / "artifacts" / "regional_instance.json"
    artifact = json.loads(artifact_path.read_text())
    graph = nx.Graph()
    graph.add_nodes_from(node["id"] for node in artifact["nodes"])
    graph.add_weighted_edges_from(
        (edge["source"], edge["target"], edge["weight"])
        for edge in artifact["edges"]
    )
    optimum = exact_max_cut(graph)
    result = solve_goemans_williamson(graph, seed=42, rounds=128, optimal_weight=optimum)

    assert optimum == pytest.approx(1058.0)
    assert result.cut_weight <= optimum + 1e-6
    assert optimum <= result.sdp_value + 1e-3
    assert result.empirical_ratio == pytest.approx(result.cut_weight / optimum)
    assert {
        frozenset(result.positive_partition),
        frozenset(result.negative_partition),
    } == {
        frozenset(artifact["reference_two_zone_max_cut"]["zone_a"]),
        frozenset(artifact["reference_two_zone_max_cut"]["zone_b"]),
    }
