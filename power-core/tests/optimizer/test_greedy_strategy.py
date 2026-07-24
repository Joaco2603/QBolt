"""Contract tests for the greedy SolverStrategy adapter."""

from __future__ import annotations

import json

import networkx as nx
import pytest

from src.optimizer.greedy import GreedyStrategy
from src.run_solver import SolverRunRequest, SolverRunner


def weighted_triangle() -> nx.Graph:
    graph = nx.Graph()
    graph.add_weighted_edges_from(
        (("a", "b", 2.0), ("b", "c", 3.0), ("a", "c", 5.0))
    )
    return graph


def request(
    graph: nx.Graph,
    *,
    options: dict[str, object] | None = None,
) -> SolverRunRequest:
    return SolverRunRequest(
        graph=graph,
        optimizer_id="greedy",
        seed=42,
        options={} if options is None else options,
        run_id="greedy-42",
    )


def test_strategy_integrates_with_runner_and_returns_reproducible_metadata() -> None:
    graph = weighted_triangle()

    result = SolverRunner([GreedyStrategy()]).run(request(graph))

    assert GreedyStrategy.id == "greedy"
    assert result.status == "succeeded"
    assert result.error is None
    assert result.seed == 42
    assert set(result.partition or {}) == set(graph.nodes)
    assert result.cut_value == pytest.approx(8.0)
    assert dict(result.metadata) == {
        "algorithm": "sequential-weighted-greedy",
        "algorithm_version": 1,
        "approximation_guarantee": 0.5,
        "ordering_policy": "weighted_degree_descending_then_node_id",
        "tie_break_policy": "sha256_seed_node_parity",
        "node_order": ("c", "a", "b"),
        "total_edge_weight": 10.0,
    }
    json.dumps(dict(result.metadata))


def test_strategy_supports_empty_graphs() -> None:
    result = SolverRunner([GreedyStrategy()]).run(request(nx.Graph()))

    assert result.status == "succeeded"
    assert dict(result.partition or {}) == {}
    assert result.cut_value == pytest.approx(0.0)
    assert result.metadata["node_order"] == ()


def test_strategy_rejects_unknown_options_without_running() -> None:
    result = GreedyStrategy().solve(
        request(weighted_triangle(), options={"rounds": 4})
    )

    assert result.status == "failed"
    assert result.partition is None
    assert result.cut_value is None
    assert result.error == {
        "code": "invalid_options",
        "message": "unknown greedy options: rounds",
    }


def test_strategy_normalizes_domain_errors_for_the_runner() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=-1.0)

    result = SolverRunner([GreedyStrategy()]).run(request(graph))

    assert result.status == "failed"
    assert result.partition is None
    assert result.cut_value is None
    assert result.error is not None
    assert result.error["code"] == "solver_error"
    assert "non-negative" in str(result.error["message"])
    assert result.metadata["algorithm_version"] == 1
    json.dumps(dict(result.error))
