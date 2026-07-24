"""Behavioural tests for the weighted Max-Cut greedy baseline."""

from __future__ import annotations

from typing import Any, cast

import networkx as nx
import pytest

from src.optimizer.greedy import GreedyError, cut_value, solve_greedy


def weighted_triangle() -> nx.Graph:
    graph = nx.Graph()
    graph.add_weighted_edges_from(
        (("a", "b", 2.0), ("b", "c", 3.0), ("a", "c", 5.0))
    )
    return graph


def test_greedy_finds_a_valid_weighted_cut() -> None:
    result = solve_greedy(weighted_triangle(), seed=42)

    assert result.node_order == ("c", "a", "b")
    assert result.cut_value == pytest.approx(8.0)
    assert result.total_edge_weight == pytest.approx(10.0)
    assert {frozenset(result.partition_zero), frozenset(result.partition_one)} == {
        frozenset(("a", "b")),
        frozenset(("c",)),
    }
    assert result.cut_value >= 0.5 * result.total_edge_weight


def test_cut_value_uses_weights_and_counts_each_edge_once() -> None:
    graph = weighted_triangle()

    assert cut_value(graph, {"a", "c"}) == pytest.approx(5.0)


def test_same_seed_is_deterministic_across_edge_insertion_orders() -> None:
    first_graph = weighted_triangle()
    second_graph = nx.Graph()
    second_graph.add_weighted_edges_from(
        (("c", "a", 5.0), ("c", "b", 3.0), ("b", "a", 2.0))
    )

    first = solve_greedy(first_graph, seed=19)
    second = solve_greedy(second_graph, seed=19)

    assert first == second


def test_seeded_tie_breaking_is_explicit_and_reproducible() -> None:
    graph = nx.Graph()
    graph.add_nodes_from(("isolated-b", "isolated-a"))

    first = solve_greedy(graph, seed=7)
    second = solve_greedy(graph, seed=7)

    assert first == second
    assert first.node_order == ("isolated-a", "isolated-b")


def test_empty_and_isolated_graphs_return_complete_zero_cuts() -> None:
    empty_result = solve_greedy(nx.Graph(), seed=3)
    assert empty_result.partition_zero == ()
    assert empty_result.partition_one == ()
    assert empty_result.node_order == ()
    assert empty_result.cut_value == pytest.approx(0.0)

    isolated = nx.Graph()
    isolated.add_nodes_from(("a", "b", "c"))
    isolated_result = solve_greedy(isolated, seed=3)
    assert set(isolated_result.partition_zero).isdisjoint(
        isolated_result.partition_one
    )
    assert set(isolated_result.partition_zero) | set(
        isolated_result.partition_one
    ) == {"a", "b", "c"}
    assert isolated_result.cut_value == pytest.approx(0.0)
    assert isolated_result.total_edge_weight == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("graph", "message"),
    (
        (nx.DiGraph((("a", "b", {"weight": 1.0}),)), "undirected"),
        (nx.MultiGraph((("a", "b", {"weight": 1.0}),)), "simple"),
        (nx.Graph((("a", "b"),)), "requires a weight"),
    ),
)
def test_rejects_unsupported_graphs(graph: nx.Graph, message: str) -> None:
    with pytest.raises(GreedyError, match=message):
        solve_greedy(graph, seed=1)


@pytest.mark.parametrize(
    "weight",
    (True, -1.0, float("nan"), float("inf"), float("-inf")),
)
def test_rejects_invalid_weights(weight: object) -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=weight)

    with pytest.raises(GreedyError, match="weight"):
        solve_greedy(graph, seed=1)


def test_rejects_invalid_nodes_self_loops_and_seeds() -> None:
    numeric_nodes = nx.Graph()
    numeric_nodes.add_edge(1, 2, weight=1.0)
    self_loop = nx.Graph()
    self_loop.add_edge("a", "a", weight=1.0)
    graph = weighted_triangle()

    with pytest.raises(GreedyError, match="strings"):
        solve_greedy(numeric_nodes, seed=1)
    with pytest.raises(GreedyError, match="self-loop"):
        solve_greedy(self_loop, seed=1)
    with pytest.raises(GreedyError, match="seed"):
        solve_greedy(graph, seed=True)
    with pytest.raises(GreedyError, match="seed"):
        solve_greedy(graph, seed=cast(Any, 1.5))
