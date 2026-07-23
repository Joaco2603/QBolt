"""Public construction helpers for the weighted Max-Cut QUBO.

The model uses the minimisation convention ``energy = -cut_weight + penalties``.
For every edge ``(u, v)`` with weight ``w`` the cut contribution is
``w * (x_u + x_v - 2*x_u*x_v)``. Therefore the QUBO contribution is
``-w*x_u - w*x_v + 2*w*x_u*x_v``.
"""

from __future__ import annotations

from math import isfinite
from numbers import Real
from typing import Callable, Mapping

import networkx as nx

from .qubo.constraint_builder import ConstraintBuilder, QuboModel

ConstraintConfiguration = Callable[[ConstraintBuilder], object]


def recommended_penalty(graph: nx.Graph) -> float:
    """Return a conservative penalty strictly larger than any cut improvement.

    A weighted cut is between zero and the sum of all edge weights. Thus a
    one-unit constraint violation costing more than that sum cannot be rewarded
    by an improvement in the unconstrained Max-Cut objective.
    """
    _validate_max_cut_graph(graph)
    total_weight = sum(float(data["weight"]) for _, _, data in graph.edges(data=True))
    return total_weight + max(1.0, total_weight * 1e-6)


def build_max_cut_qubo(
    graph: nx.Graph,
    *,
    penalty: float | None = None,
    configure_constraints: ConstraintConfiguration | None = None,
) -> QuboModel:
    """Build ``-weighted Max-Cut + penalties`` as a minimisation QUBO.

    ``x_node = 0`` and ``x_node = 1`` denote the two sides of the partition.
    Constraints are optional because ordinary Max-Cut only requires each node
    to have a binary label. When supplied, ``configure_constraints`` receives a
    :class:`ConstraintBuilder` and may call its fluent constraint methods.
    """
    nodes = _validate_max_cut_graph(graph)
    selected_penalty = recommended_penalty(graph) if penalty is None else penalty
    builder = ConstraintBuilder(graph, penalty=selected_penalty)
    if configure_constraints is not None:
        if not callable(configure_constraints):
            raise TypeError("configure_constraints must be callable")
        configure_constraints(builder)
    constraints = builder.build()

    linear = dict(constraints.linear)
    quadratic = dict(constraints.quadratic)
    for left, right, data in graph.edges(data=True):
        weight = float(data["weight"])
        linear[left] = linear.get(left, 0.0) - weight
        linear[right] = linear.get(right, 0.0) - weight
        key = tuple(sorted((left, right)))
        quadratic[key] = quadratic.get(key, 0.0) + 2.0 * weight

    return QuboModel(
        decision_variables=nodes,
        auxiliary_variables=constraints.auxiliary_variables,
        offset=constraints.offset,
        linear=linear,
        quadratic=quadratic,
    )


def cut_weight(graph: nx.Graph, assignment: Mapping[str, int]) -> float:
    """Evaluate the weighted cut represented by a complete binary assignment."""
    nodes = _validate_max_cut_graph(graph)
    expected = set(nodes)
    supplied = set(assignment)
    if supplied != expected:
        missing = expected - supplied
        unknown = supplied - expected
        details = []
        if missing:
            details.append(f"missing nodes: {sorted(missing)}")
        if unknown:
            details.append(f"unknown nodes: {sorted(unknown)}")
        raise ValueError("Assignment must cover the graph exactly; " + "; ".join(details))
    for node, value in assignment.items():
        if type(value) is not int or value not in (0, 1):
            raise ValueError(f"Assignment value for {node!r} must be binary (0 or 1)")
    return float(
        sum(
            data["weight"]
            for left, right, data in graph.edges(data=True)
            if assignment[left] != assignment[right]
        )
    )


def _validate_max_cut_graph(graph: nx.Graph) -> tuple[str, ...]:
    if not isinstance(graph, nx.Graph) or graph.is_directed():
        raise TypeError("graph must be an undirected networkx.Graph")
    if graph.is_multigraph():
        raise ValueError("graph must be simple")
    if any(not isinstance(node, str) or not node for node in graph.nodes):
        raise ValueError("graph node IDs must be non-empty strings")
    if any(left == right for left, right in graph.edges):
        raise ValueError("graph must not contain self-loops")
    for left, right, data in graph.edges(data=True):
        weight = data.get("weight")
        if (
            isinstance(weight, bool)
            or not isinstance(weight, Real)
            or not isfinite(float(weight))
            or weight < 0
        ):
            raise ValueError(
                f"Edge ({left!r}, {right!r}) must have a finite non-negative weight"
            )
    return tuple(sorted(graph.nodes))


__all__ = [
    "ConstraintBuilder",
    "QuboModel",
    "build_max_cut_qubo",
    "cut_weight",
    "recommended_penalty",
]
