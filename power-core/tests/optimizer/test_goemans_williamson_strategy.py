"""Contract tests for the Goemans-Williamson solver strategy adapter."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import networkx as nx
import pytest

from src.optimizer import GoemansWilliamsonStrategy as ExportedStrategy
from src.optimizer import goemans_williamson_strategy as strategy_module
from src.optimizer.goemans_williamson import GoemansWilliamsonError
from src.optimizer.goemans_williamson_strategy import GoemansWilliamsonStrategy
from src.run_solver import SolverRunRequest, SolverRunner


def weighted_graph() -> nx.Graph:
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
        optimizer_id="goemans-williamson",
        seed=42,
        options={} if options is None else options,
        run_id="gw-42",
    )


def core_result(**overrides: Any) -> SimpleNamespace:
    values: dict[str, object] = {
        "positive_partition": ("a", "c"),
        "negative_partition": ("b",),
        "cut_weight": 999.0,
        "sdp_value": 10.5,
        "empirical_ratio": None,
        "seed": 42,
        "rounds": 128,
        "winning_round": 3,
        "solver": "SCS",
        "solver_status": "optimal",
        "solver_options": (("eps", 1e-6), ("max_iters", 100_000)),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_strategy_exposes_stable_identifier() -> None:
    assert ExportedStrategy is GoemansWilliamsonStrategy
    assert GoemansWilliamsonStrategy.id == "goemans-williamson"


def test_strategy_uses_defaults_and_returns_normalized_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = weighted_graph()
    received: dict[str, object] = {}

    def fake_solve(received_graph: nx.Graph, **kwargs: object) -> SimpleNamespace:
        received["graph"] = received_graph
        received.update(kwargs)
        return core_result()

    monkeypatch.setattr(strategy_module, "solve_goemans_williamson", fake_solve)

    result = GoemansWilliamsonStrategy().solve(request(graph))

    assert received == {
        "graph": graph,
        "seed": 42,
        "rounds": 128,
        "solver": "SCS",
    }
    assert result.status == "succeeded"
    assert dict(result.partition or {}) == {"a": 1, "b": 0, "c": 1}
    assert result.cut_value == pytest.approx(5.0)
    assert result.seed == 42
    assert result.error is None
    assert dict(result.metadata) == {
        "rounds": 128,
        "winning_round": 3,
        "solver": "SCS",
        "solver_status": "optimal",
        "solver_options": {"eps": 1e-6, "max_iters": 100_000},
        "sdp_value": 10.5,
    }
    json.dumps(dict(result.metadata))


def test_strategy_forwards_valid_options_without_mutating_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = weighted_graph()
    graph_snapshot = deepcopy(nx.node_link_data(graph, edges="edges"))
    options = {"rounds": 16, "solver": "SCS"}
    received: dict[str, object] = {}

    def fake_solve(received_graph: nx.Graph, **kwargs: object) -> SimpleNamespace:
        received["graph"] = received_graph
        received.update(kwargs)
        return core_result(rounds=16)

    monkeypatch.setattr(strategy_module, "solve_goemans_williamson", fake_solve)
    run_request = request(graph, options=options)

    GoemansWilliamsonStrategy().solve(run_request)

    assert received == {
        "graph": graph,
        "seed": 42,
        "rounds": 16,
        "solver": "SCS",
    }
    assert dict(run_request.options) == options
    assert options == {"rounds": 16, "solver": "SCS"}
    assert nx.node_link_data(graph, edges="edges") == graph_snapshot


@pytest.mark.parametrize(
    "options",
    (
        {"unknown": 1},
        {"rounds": 0},
        {"rounds": True},
        {"solver": ""},
        {"solver": 7},
        {"optimal_weight": 10.0},
    ),
)
def test_strategy_returns_failed_for_invalid_options(
    monkeypatch: pytest.MonkeyPatch,
    options: dict[str, object],
) -> None:
    called = False

    def unexpected_call(*_: object, **__: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        strategy_module,
        "solve_goemans_williamson",
        unexpected_call,
    )

    result = GoemansWilliamsonStrategy().solve(request(weighted_graph(), options=options))

    assert result.status == "failed"
    assert result.partition is None
    assert result.cut_value is None
    assert result.seed == 42
    assert result.error is not None
    assert result.error["code"] == "invalid_options"
    assert called is False


def test_strategy_normalizes_core_solver_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_: object, **__: object) -> None:
        raise GoemansWilliamsonError("solver 'SCS' returned status 'infeasible'")

    monkeypatch.setattr(strategy_module, "solve_goemans_williamson", fail)

    result = GoemansWilliamsonStrategy().solve(request(weighted_graph()))

    assert result.status == "failed"
    assert result.partition is None
    assert result.cut_value is None
    assert result.error == {
        "code": "solver_error",
        "message": "solver 'SCS' returned status 'infeasible'",
    }
    json.dumps(dict(result.error))


def test_strategy_rejects_invalid_core_partitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        strategy_module,
        "solve_goemans_williamson",
        lambda *_args, **_kwargs: core_result(
            positive_partition=("a", "b"),
            negative_partition=("b",),
        ),
    )

    result = GoemansWilliamsonStrategy().solve(request(weighted_graph()))

    assert result.status == "failed"
    assert result.error is not None
    assert result.error["code"] == "solver_error"
    assert "partitions" in str(result.error["message"])


def test_strategy_integrates_with_runner_without_runner_conditionals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = weighted_graph()
    monkeypatch.setattr(
        strategy_module,
        "solve_goemans_williamson",
        lambda *_args, **_kwargs: core_result(),
    )
    runner = SolverRunner([GoemansWilliamsonStrategy()])

    result = runner.run(request(graph))

    assert result.optimizer_id == "goemans-williamson"
    assert result.status == "succeeded"
    assert result.cut_value == pytest.approx(5.0)


def test_strategy_solves_regional_reference_instance() -> None:
    artifact_path = (
        Path(__file__).parents[2] / "artifacts" / "regional_instance.json"
    )
    artifact = json.loads(artifact_path.read_text())
    graph = nx.Graph()
    graph.add_nodes_from(node["id"] for node in artifact["nodes"])
    graph.add_weighted_edges_from(
        (edge["source"], edge["target"], edge["weight"])
        for edge in artifact["edges"]
    )

    result = SolverRunner([GoemansWilliamsonStrategy()]).run(
        request(graph, options={"rounds": 128})
    )

    assert result.status == "succeeded"
    assert result.cut_value == pytest.approx(1058.0)
    assert set(result.partition or {}) == set(graph.nodes)
