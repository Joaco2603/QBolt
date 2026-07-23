"""Behavioural contract for the Goemans-Williamson weighted Max-Cut solver."""

from __future__ import annotations

import importlib.util
import json
import sys
from itertools import product
from pathlib import Path

import networkx as nx
import numpy as np
import pytest


ROOT = Path(__file__).parents[3]
MODULE_PATH = ROOT / "power-core" / "src" / "optimizer" / "goemans_williamson.py"
SPEC = importlib.util.spec_from_file_location("goemans_williamson", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

GoemansWilliamsonError = MODULE.GoemansWilliamsonError
cut_weight = MODULE.cut_weight
factor_sdp_solution = MODULE.factor_sdp_solution
ising_cut_value = MODULE.ising_cut_value
laplacian_cut_value = MODULE.laplacian_cut_value
solve_goemans_williamson = MODULE.solve_goemans_williamson


def exact_max_cut(graph: nx.Graph) -> float:
    """Return the exact optimum by fixing the first node's sign."""

    nodes = tuple(graph.nodes)
    if not nodes:
        return 0.0

    best = 0.0
    for tail in product((-1, 1), repeat=len(nodes) - 1):
        labels = {nodes[0]: 1, **dict(zip(nodes[1:], tail, strict=True))}
        best = max(best, ising_cut_value(graph, labels))
    return best


def weighted_triangle() -> nx.Graph:
    graph = nx.Graph()
    graph.add_weighted_edges_from((("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0)))
    return graph


def test_cut_objectives_match_known_partition_without_double_counting() -> None:
    graph = nx.Graph()
    graph.add_weighted_edges_from((("a", "b", 2.0), ("b", "c", 3.0), ("a", "c", 5.0)))
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
def test_solver_rejects_unsupported_graphs(graph: nx.Graph, message: str) -> None:
    with pytest.raises((GoemansWilliamsonError, TypeError), match=message):
        solve_goemans_williamson(graph, seed=7)


@pytest.mark.parametrize("weight", (float("nan"), float("inf"), -1.0))
def test_solver_rejects_non_finite_or_negative_weights(weight: float) -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=weight)

    with pytest.raises(GoemansWilliamsonError, match="weight"):
        solve_goemans_williamson(graph, seed=7)


def test_solver_rejects_non_string_nodes_loops_and_non_positive_rounds() -> None:
    invalid_node_graph = nx.Graph()
    invalid_node_graph.add_edge(1, 2, weight=1.0)
    loop_graph = nx.Graph()
    loop_graph.add_edge("a", "a", weight=1.0)
    valid_graph = nx.Graph()
    valid_graph.add_edge("a", "b", weight=1.0)

    with pytest.raises(GoemansWilliamsonError, match="string"):
        solve_goemans_williamson(invalid_node_graph, seed=7)
    with pytest.raises(GoemansWilliamsonError, match="self-loop"):
        solve_goemans_williamson(loop_graph, seed=7)
    with pytest.raises(GoemansWilliamsonError, match="rounds"):
        solve_goemans_williamson(valid_graph, seed=7, rounds=0)


def test_single_edge_has_exact_cut_and_sdp_value() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=7.0)

    result = solve_goemans_williamson(graph, seed=11, rounds=8, optimal_weight=7.0)

    assert result.cut_weight == pytest.approx(7.0, abs=1e-4)
    assert result.sdp_value == pytest.approx(7.0, abs=1e-4)
    assert result.empirical_ratio == pytest.approx(1.0)
    assert np.allclose(result.sdp_matrix, result.sdp_matrix.T, atol=1e-6)
    assert np.allclose(np.diag(result.sdp_matrix), 1.0, atol=1e-5)
    assert np.linalg.eigvalsh(result.sdp_matrix).min() >= -1e-5


def test_triangle_has_expected_exact_and_sdp_bounds() -> None:
    graph = weighted_triangle()
    optimum = exact_max_cut(graph)

    result = solve_goemans_williamson(graph, seed=19, rounds=32, optimal_weight=optimum)

    assert optimum == pytest.approx(2.0)
    assert result.cut_weight <= optimum + 1e-6
    assert optimum <= result.sdp_value + 1e-4
    assert result.sdp_value == pytest.approx(2.25, abs=2e-3)
    assert result.empirical_ratio is not None
    assert 0.0 <= result.empirical_ratio <= 1.0


def test_factorization_repairs_only_tolerance_sized_psd_error() -> None:
    repairable = np.array(((1.0, 1.0 + 1e-7), (1.0 + 1e-7, 1.0)))
    vectors = factor_sdp_solution(repairable, tolerance=1e-6)

    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-8)
    with pytest.raises(GoemansWilliamsonError, match="positive semidefinite"):
        factor_sdp_solution(np.array(((1.0, 1.1), (1.1, 1.0))), tolerance=1e-6)


def test_seeded_rounding_is_reproducible_and_partitions_are_valid() -> None:
    graph = weighted_triangle()

    first = solve_goemans_williamson(graph, seed=23, rounds=16)
    second = solve_goemans_williamson(graph, seed=23, rounds=16)

    assert first == second
    assert set(first.positive_partition).isdisjoint(first.negative_partition)
    assert set(first.positive_partition) | set(first.negative_partition) == set(graph.nodes)
    assert 0 <= first.winning_round < first.rounds


def test_multiple_rounds_never_underperform_the_first_seeded_round() -> None:
    graph = weighted_triangle()

    first_round = solve_goemans_williamson(graph, seed=31, rounds=1)
    many_rounds = solve_goemans_williamson(graph, seed=31, rounds=32)

    assert many_rounds.cut_weight >= first_round.cut_weight


def test_empty_and_zero_optimum_graphs_return_undefined_ratio() -> None:
    empty = nx.Graph()
    zero_weight = nx.Graph()
    zero_weight.add_edge("a", "b", weight=0.0)

    empty_result = solve_goemans_williamson(empty, seed=3, optimal_weight=0.0)
    zero_result = solve_goemans_williamson(zero_weight, seed=3, optimal_weight=0.0)

    assert empty_result.cut_weight == empty_result.sdp_value == 0.0
    assert empty_result.empirical_ratio is None
    assert zero_result.cut_weight == pytest.approx(0.0)
    assert zero_result.empirical_ratio is None


def test_unknown_solver_is_reported_as_a_domain_error() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=1.0)

    with pytest.raises(GoemansWilliamsonError, match="solver"):
        solve_goemans_williamson(graph, seed=7, solver="NOT_A_SOLVER")


def test_regional_instance_has_documented_exact_optimum_and_valid_gw_bound() -> None:
    artifact_path = ROOT / "power-core" / "artifacts" / "regional_instance.json"
    artifact = json.loads(artifact_path.read_text())
    graph = nx.Graph()
    graph.add_nodes_from(node["id"] for node in artifact["nodes"])
    graph.add_weighted_edges_from(
        (edge["source"], edge["target"], edge["weight"]) for edge in artifact["edges"]
    )
    optimum = exact_max_cut(graph)

    result = solve_goemans_williamson(graph, seed=42, rounds=128, optimal_weight=optimum)

    assert optimum == pytest.approx(1058.0)
    assert result.cut_weight <= optimum + 1e-6
    assert optimum <= result.sdp_value + 1e-3
    assert result.empirical_ratio is not None
