"""Reproducible Goemans-Williamson approximation for weighted Max-Cut."""

from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Integral, Real
from typing import Mapping

import cvxpy as cp
import networkx as nx
import numpy as np


DEFAULT_ROUNDS = 128
DEFAULT_SOLVER = "SCS"
DEFAULT_TOLERANCE = 1e-5
SCS_OPTIONS: dict[str, float | int] = {"eps": 1e-6, "max_iters": 100_000}


class GoemansWilliamsonError(ValueError):
    """Raised when a graph or SDP result violates the solver contract."""


@dataclass(frozen=True)
class GoemansWilliamsonResult:
    """The best cut found by seeded random-hyperplane rounding."""

    positive_partition: tuple[str, ...]
    negative_partition: tuple[str, ...]
    cut_weight: float
    sdp_value: float
    empirical_ratio: float | None
    seed: int
    rounds: int
    winning_round: int
    solver: str
    solver_status: str
    solver_options: tuple[tuple[str, float | int], ...]
    sdp_matrix: np.ndarray = field(compare=False, repr=False)


def _validate_graph(graph: nx.Graph) -> tuple[str, ...]:
    """Validate the supported graph domain and return deterministic node order."""

    if not isinstance(graph, nx.Graph) or graph.is_directed():
        raise GoemansWilliamsonError("graph must be undirected")
    if graph.is_multigraph():
        raise GoemansWilliamsonError("graph must be simple")

    raw_nodes = tuple(graph.nodes)
    if any(not isinstance(node, str) for node in raw_nodes):
        raise GoemansWilliamsonError("node IDs must be strings")
    nodes = tuple(sorted(raw_nodes))
    if any(node == "" for node in nodes):
        raise GoemansWilliamsonError("node IDs must be non-empty strings")
    if any(left == right for left, right in graph.edges):
        raise GoemansWilliamsonError("graph must not contain a self-loop")

    for _, _, data in graph.edges(data=True):
        if "weight" not in data:
            raise GoemansWilliamsonError("each edge requires a weight")
        weight = data["weight"]
        if isinstance(weight, bool) or not isinstance(weight, Real) or not np.isfinite(weight):
            raise GoemansWilliamsonError("each edge weight must be finite")
        if weight < 0:
            raise GoemansWilliamsonError("each edge weight must be non-negative")
    return nodes


def cut_weight(graph: nx.Graph, positive_partition: set[str]) -> float:
    """Return the cut weight, summing each undirected edge exactly once."""

    _validate_graph(graph)
    return float(
        sum(
            data["weight"]
            for left, right, data in graph.edges(data=True)
            if (left in positive_partition) != (right in positive_partition)
        )
    )


def ising_cut_value(graph: nx.Graph, labels: Mapping[str, int]) -> float:
    """Evaluate the edge-list Ising Max-Cut objective."""

    nodes = _validate_graph(graph)
    if set(labels) != set(nodes) or any(label not in (-1, 1) for label in labels.values()):
        raise GoemansWilliamsonError("labels must assign every node either -1 or +1")
    return float(
        0.5
        * sum(
            data["weight"] * (1 - labels[left] * labels[right])
            for left, right, data in graph.edges(data=True)
        )
    )


def _weighted_laplacian(graph: nx.Graph, nodes: tuple[str, ...]) -> np.ndarray:
    """Build the weighted Laplacian in the deterministic node order."""

    adjacency = nx.to_numpy_array(graph, nodelist=nodes, weight="weight", dtype=float)
    return np.diag(adjacency.sum(axis=1)) - adjacency


def laplacian_cut_value(graph: nx.Graph, labels: Mapping[str, int]) -> float:
    """Evaluate the equivalent one-quarter weighted-Laplacian objective."""

    nodes = _validate_graph(graph)
    if set(labels) != set(nodes) or any(label not in (-1, 1) for label in labels.values()):
        raise GoemansWilliamsonError("labels must assign every node either -1 or +1")
    vector = np.array([labels[node] for node in nodes], dtype=float)
    return float(0.25 * vector @ _weighted_laplacian(graph, nodes) @ vector)


def factor_sdp_solution(matrix: np.ndarray, *, tolerance: float = DEFAULT_TOLERANCE) -> np.ndarray:
    """Validate, repair tolerance-sized PSD error, and return unit row vectors."""

    candidate = np.asarray(matrix, dtype=float)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise GoemansWilliamsonError("SDP solution must be a square matrix")
    if not np.isfinite(candidate).all():
        raise GoemansWilliamsonError("SDP solution must be finite")
    if tolerance <= 0:
        raise GoemansWilliamsonError("tolerance must be positive")

    symmetric = 0.5 * (candidate + candidate.T)
    if not np.allclose(np.diag(symmetric), 1.0, atol=tolerance, rtol=0.0):
        raise GoemansWilliamsonError("SDP solution must have a unit diagonal")
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    if eigenvalues.min(initial=0.0) < -tolerance:
        raise GoemansWilliamsonError("SDP solution must be positive semidefinite")

    vectors = eigenvectors * np.sqrt(np.clip(eigenvalues, 0.0, None))
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms <= tolerance):
        raise GoemansWilliamsonError("SDP solution cannot be factored into unit vectors")
    return vectors / norms[:, np.newaxis]


def _canonical_partitions(labels: np.ndarray, nodes: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return complementary partitions in a deterministic orientation."""

    positive = tuple(node for node, label in zip(nodes, labels, strict=True) if label >= 0)
    negative = tuple(node for node, label in zip(nodes, labels, strict=True) if label < 0)
    return (positive, negative) if positive <= negative else (negative, positive)


def _validate_parameters(seed: int, rounds: int, optimal_weight: float | None) -> None:
    """Validate reproducibility and optional evaluation inputs."""

    if isinstance(seed, bool) or not isinstance(seed, Integral):
        raise GoemansWilliamsonError("seed must be an integer")
    if isinstance(rounds, bool) or not isinstance(rounds, Integral) or rounds <= 0:
        raise GoemansWilliamsonError("rounds must be a positive integer")
    if optimal_weight is not None:
        if isinstance(optimal_weight, bool) or not isinstance(optimal_weight, Real):
            raise GoemansWilliamsonError("optimal_weight must be a finite non-negative number")
        if not np.isfinite(optimal_weight) or optimal_weight < 0:
            raise GoemansWilliamsonError("optimal_weight must be a finite non-negative number")


def solve_goemans_williamson(
    graph: nx.Graph,
    *,
    seed: int,
    rounds: int = DEFAULT_ROUNDS,
    solver: str = DEFAULT_SOLVER,
    optimal_weight: float | None = None,
) -> GoemansWilliamsonResult:
    """Solve the Max-Cut SDP and return the best seeded hyperplane rounding."""

    _validate_parameters(seed, rounds, optimal_weight)
    nodes = _validate_graph(graph)
    options = tuple(sorted(SCS_OPTIONS.items()))
    if not nodes:
        return GoemansWilliamsonResult(
            positive_partition=(),
            negative_partition=(),
            cut_weight=0.0,
            sdp_value=0.0,
            empirical_ratio=None,
            seed=int(seed),
            rounds=int(rounds),
            winning_round=0,
            solver=solver,
            solver_status="not_applicable",
            solver_options=options,
            sdp_matrix=np.empty((0, 0)),
        )

    laplacian = _weighted_laplacian(graph, nodes)
    matrix = cp.Variable((len(nodes), len(nodes)), symmetric=True)
    problem = cp.Problem(
        cp.Maximize(0.25 * cp.trace(laplacian @ matrix)),
        [matrix >> 0, cp.diag(matrix) == 1],
    )
    try:
        problem.solve(solver=solver, **SCS_OPTIONS)
    except Exception as error:  # CVXPY exposes several solver-specific exception types.
        raise GoemansWilliamsonError(f"solver '{solver}' failed: {error}") from error

    status = str(problem.status)
    if status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} or matrix.value is None:
        raise GoemansWilliamsonError(f"solver '{solver}' returned status '{status}'")
    if problem.value is None or not np.isfinite(problem.value):
        raise GoemansWilliamsonError(f"solver '{solver}' did not return a finite objective")

    raw_matrix = np.asarray(matrix.value, dtype=float)
    vectors = factor_sdp_solution(raw_matrix)
    generator = np.random.default_rng(int(seed))
    best_cut = -np.inf
    best_partitions: tuple[tuple[str, ...], tuple[str, ...]] | None = None
    winning_round = 0
    for round_index in range(int(rounds)):
        direction = generator.normal(size=vectors.shape[1])
        labels = vectors @ direction
        positive, negative = _canonical_partitions(labels, nodes)
        value = cut_weight(graph, set(positive))
        if value > best_cut:
            best_cut = value
            best_partitions = (positive, negative)
            winning_round = round_index

    assert best_partitions is not None
    ratio = None if optimal_weight is None or optimal_weight == 0 else best_cut / optimal_weight
    return GoemansWilliamsonResult(
        positive_partition=best_partitions[0],
        negative_partition=best_partitions[1],
        cut_weight=float(best_cut),
        sdp_value=float(problem.value),
        empirical_ratio=ratio,
        seed=int(seed),
        rounds=int(rounds),
        winning_round=winning_round,
        solver=solver,
        solver_status=status,
        solver_options=options,
        sdp_matrix=raw_matrix,
    )
