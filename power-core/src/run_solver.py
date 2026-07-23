"""Optimizer-agnostic execution boundary for weighted Max-Cut strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence

import networkx as nx


class SolverRunValidationError(ValueError):
    """Raised when a runner request, registry, or result violates its contract."""


@dataclass(frozen=True)
class SolverRunRequest:
    """Immutable shared input for a single solver strategy execution."""

    graph: nx.Graph
    optimizer_id: str
    seed: int
    options: Mapping[str, object] = field(default_factory=dict)
    run_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


@dataclass(frozen=True)
class SolverRunResult:
    """Normalized result returned by a solver strategy."""

    optimizer_id: str
    status: str
    partition: Mapping[str, int] | None
    cut_value: float | None
    seed: int
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        partition = None
        if self.partition is not None:
            partition = MappingProxyType(dict(self.partition))
        object.__setattr__(self, "partition", partition)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        error = None if self.error is None else MappingProxyType(dict(self.error))
        object.__setattr__(self, "error", error)


class SolverStrategy(Protocol):
    """Contract implemented by optimizer adapters."""

    id: str

    def solve(self, request: SolverRunRequest) -> SolverRunResult:
        """Solve one request and return its normalized result."""


class SolverRunner:
    """Select and execute one injected solver strategy without fallback."""

    def __init__(self, strategies: Sequence[SolverStrategy]) -> None:
        self._strategies = self._build_registry(strategies)

    @staticmethod
    def _build_registry(strategies: Sequence[SolverStrategy]) -> Mapping[str, SolverStrategy]:
        registry: dict[str, SolverStrategy] = {}
        for strategy in strategies:
            identifier = strategy.id
            if identifier in registry:
                raise SolverRunValidationError(
                    f"Duplicate solver strategy identifier: {identifier!r}"
                )
            registry[identifier] = strategy
        return MappingProxyType(registry)

    def run(self, request: SolverRunRequest) -> SolverRunResult:
        """Delegate a request to its selected strategy and validate its result."""
        self._validate_request(request)
        try:
            strategy = self._strategies[request.optimizer_id]
        except KeyError as error:
            available = ", ".join(sorted(self._strategies))
            raise SolverRunValidationError(
                f"Unknown optimizer_id {request.optimizer_id!r}; available: {available}"
            ) from error
        result = strategy.solve(request)
        self._validate_result(request, result)
        return result

    @staticmethod
    def _validate_request(request: SolverRunRequest) -> None:
        if not isinstance(request, SolverRunRequest):
            raise SolverRunValidationError("request must be a SolverRunRequest")
        if not isinstance(request.graph, nx.Graph) or request.graph.is_directed():
            raise SolverRunValidationError("graph must be an undirected networkx.Graph")
        if request.graph.is_multigraph():
            raise SolverRunValidationError("graph must be simple")
        for left, right, attributes in request.graph.edges(data=True):
            weight = attributes.get("weight")
            if (
                isinstance(weight, bool)
                or not isinstance(weight, Real)
                or not isfinite(float(weight))
            ):
                raise SolverRunValidationError(
                    f"edge ({left!r}, {right!r}) must have a finite weight"
                )
        if (
            not isinstance(request.optimizer_id, str)
            or not request.optimizer_id.strip()
        ):
            raise SolverRunValidationError("optimizer_id must be a non-blank string")
        if isinstance(request.seed, bool) or not isinstance(request.seed, Integral):
            raise SolverRunValidationError("seed must be an integer")

    @staticmethod
    def _validate_result(request: SolverRunRequest, result: SolverRunResult) -> None:
        if not isinstance(result, SolverRunResult):
            raise SolverRunValidationError("strategy must return a SolverRunResult")
        if result.optimizer_id != request.optimizer_id:
            raise SolverRunValidationError("result optimizer_id must match the selected strategy")
        if result.seed != request.seed:
            raise SolverRunValidationError(
                "result seed must match the request seed"
            )
        if result.status not in {"succeeded", "failed", "not_converged"}:
            raise SolverRunValidationError(
                "result status must be succeeded, failed, or not_converged"
            )
        if result.status != "succeeded":
            return
        if result.partition is None:
            raise SolverRunValidationError("successful result requires a partition")
        expected_nodes = set(request.graph.nodes)
        partition_nodes = set(result.partition)
        missing = expected_nodes - partition_nodes
        unknown = partition_nodes - expected_nodes
        if missing:
            raise SolverRunValidationError(
                "successful partition is missing nodes: "
                f"{sorted(map(repr, missing))!r}"
            )
        if unknown:
            raise SolverRunValidationError(
                "successful partition contains unknown nodes: "
                f"{sorted(map(repr, unknown))!r}"
            )
        if any(
            type(label) is not int or label not in (0, 1)
            for label in result.partition.values()
        ):
            raise SolverRunValidationError("successful partition labels must be 0 or 1")
        if (
            isinstance(result.cut_value, bool)
            or not isinstance(result.cut_value, Real)
            or not isfinite(float(result.cut_value))
        ):
            raise SolverRunValidationError("successful result cut_value must be finite")
