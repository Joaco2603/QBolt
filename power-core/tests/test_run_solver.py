"""TDD contract for the optimizer-agnostic Max-Cut solver runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Mapping

import networkx as nx
import pytest


MODULE_PATH = Path(__file__).parents[1] / "src" / "run_solver.py"
SPEC = importlib.util.spec_from_file_location("run_solver", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def success_result(
    *,
    optimizer_id: str = "recording",
    partition: Mapping[str, int] | None = None,
    cut_value: float | None = 110.0,
) -> object:
    return MODULE.SolverRunResult(
        optimizer_id=optimizer_id,
        status="succeeded",
        partition=partition or {"SUB-01": 0, "SUB-02": 1},
        cut_value=cut_value,
        seed=42,
        metadata={"source": "fake"},
    )


class RecordingStrategy:
    def __init__(self, identifier: str, result: object) -> None:
        self.id = identifier
        self._result = result
        self.requests: list[object] = []

    def solve(self, received_request: object) -> object:
        self.requests.append(received_request)
        return self._result


def weighted_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_edge("SUB-01", "SUB-02", weight=110.0)
    return graph


def request(**overrides: object) -> object:
    values = {
        "graph": weighted_graph(),
        "optimizer_id": "recording",
        "seed": 42,
        "options": {"rounds": 16},
        "run_id": "integration-42",
    }
    values.update(overrides)
    return MODULE.SolverRunRequest(**values)


def test_runner_delegates_to_the_strategy_selected_by_optimizer_id() -> None:
    run_request = request()
    strategy = RecordingStrategy("recording", success_result())
    runner = MODULE.SolverRunner([strategy])

    result = runner.run(run_request)

    assert result.optimizer_id == "recording"
    assert strategy.requests == [run_request]


def test_runner_forwards_the_original_request_without_mutation() -> None:
    graph = weighted_graph()
    options = {"rounds": 16}
    run_request = request(graph=graph, options=options)
    strategy = RecordingStrategy("recording", success_result())

    MODULE.SolverRunner([strategy]).run(run_request)

    assert strategy.requests[0] is run_request
    assert strategy.requests[0].graph is graph
    assert strategy.requests[0].seed == 42
    assert strategy.requests[0].optimizer_id == "recording"
    assert dict(strategy.requests[0].options) == options
    assert strategy.requests[0].run_id == "integration-42"
    assert options == {"rounds": 16}


def test_runner_selects_different_registered_strategies_without_conditional_logic() -> None:
    first = RecordingStrategy("first", success_result(optimizer_id="first"))
    second = RecordingStrategy("second", success_result(optimizer_id="second"))
    runner = MODULE.SolverRunner([first, second])

    first_result = runner.run(request(optimizer_id="first"))
    second_result = runner.run(request(optimizer_id="second"))

    assert first_result.optimizer_id == "first"
    assert second_result.optimizer_id == "second"
    assert len(first.requests) == 1
    assert len(second.requests) == 1


def test_runner_rejects_an_unknown_optimizer_id_with_registered_identifiers() -> None:
    strategy = RecordingStrategy("alpha", success_result(optimizer_id="alpha"))
    runner = MODULE.SolverRunner([strategy])

    with pytest.raises(MODULE.SolverRunValidationError, match="missing.*available: alpha"):
        runner.run(request(optimizer_id="missing"))

    assert strategy.requests == []


def test_runner_rejects_duplicate_strategy_identifiers() -> None:
    first = RecordingStrategy("duplicate", success_result(optimizer_id="duplicate"))
    second = RecordingStrategy("duplicate", success_result(optimizer_id="duplicate"))

    with pytest.raises(MODULE.SolverRunValidationError, match="Duplicate"):
        MODULE.SolverRunner([first, second])


def test_runner_requires_an_explicit_optimizer_id() -> None:
    strategy = RecordingStrategy("recording", success_result())

    with pytest.raises(MODULE.SolverRunValidationError, match="optimizer_id"):
        MODULE.SolverRunner([strategy]).run(request(optimizer_id=" "))

    assert strategy.requests == []


def test_runner_rejects_a_success_result_with_missing_partition_nodes() -> None:
    strategy = RecordingStrategy(
        "recording",
        success_result(partition={"SUB-01": 0}),
    )

    with pytest.raises(MODULE.SolverRunValidationError, match="missing"):
        MODULE.SolverRunner([strategy]).run(request())


def test_runner_rejects_a_success_result_with_unknown_partition_nodes() -> None:
    strategy = RecordingStrategy(
        "recording",
        success_result(partition={"SUB-01": 0, "SUB-02": 1, "UNKNOWN": 0}),
    )

    with pytest.raises(MODULE.SolverRunValidationError, match="unknown"):
        MODULE.SolverRunner([strategy]).run(request())


def test_runner_rejects_a_success_result_with_an_invalid_partition_label() -> None:
    strategy = RecordingStrategy(
        "recording",
        success_result(partition={"SUB-01": 0, "SUB-02": 2}),
    )

    with pytest.raises(MODULE.SolverRunValidationError, match="partition labels"):
        MODULE.SolverRunner([strategy]).run(request())


@pytest.mark.parametrize("invalid_cut_value", [float("nan"), float("inf"), float("-inf")])
def test_runner_rejects_a_success_result_with_non_finite_cut_value(
    invalid_cut_value: float,
) -> None:
    strategy = RecordingStrategy("recording", success_result(cut_value=invalid_cut_value))

    with pytest.raises(MODULE.SolverRunValidationError, match="finite"):
        MODULE.SolverRunner([strategy]).run(request())


@pytest.mark.parametrize("status", ["failed", "not_converged"])
def test_runner_preserves_failed_and_not_converged_results(status: str) -> None:
    result = MODULE.SolverRunResult(
        optimizer_id="recording",
        status=status,
        partition=None,
        cut_value=None,
        seed=42,
        metadata={"iterations": 8},
        error={"code": status},
    )
    strategy = RecordingStrategy("recording", result)

    returned = MODULE.SolverRunner([strategy]).run(request())

    assert returned is result
    assert returned.status == status
    assert dict(returned.error) == {"code": status}


def test_runner_does_not_fallback_after_a_strategy_failure() -> None:
    failed_result = MODULE.SolverRunResult(
        optimizer_id="failing",
        status="failed",
        partition=None,
        cut_value=None,
        seed=42,
        metadata={},
        error={"code": "solver_failure"},
    )
    failing = RecordingStrategy("failing", failed_result)
    fallback = RecordingStrategy("fallback", success_result(optimizer_id="fallback"))
    runner = MODULE.SolverRunner([failing, fallback])

    result = runner.run(request(optimizer_id="failing"))

    assert result is failed_result
    assert len(failing.requests) == 1
    assert fallback.requests == []
