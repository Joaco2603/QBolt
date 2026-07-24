"""Seed-reproducible greedy baseline for weighted Max-Cut."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isfinite
from numbers import Integral, Real
from typing import Collection

import networkx as nx


ALGORITHM = "sequential-weighted-greedy"
ALGORITHM_VERSION = 1
APPROXIMATION_GUARANTEE = 0.5
ORDERING_POLICY = "weighted_degree_descending_then_node_id"
TIE_BREAK_POLICY = "sha256_seed_node_parity"


class GreedyError(ValueError):
    """Raised when an input violates the greedy Max-Cut contract."""


@dataclass(frozen=True)
class GreedyResult:
    """Partition and reproducibility data returned by the greedy baseline."""

    partition_zero: tuple[str, ...]
    partition_one: tuple[str, ...]
    cut_value: float
    total_edge_weight: float
    seed: int
    node_order: tuple[str, ...]


def _validate_seed(seed: int) -> int:
    """Validate and normalize the seed used for deterministic tie-breaking."""

    if isinstance(seed, bool) or not isinstance(seed, Integral):
        raise GreedyError("seed must be an integer")
    return int(seed)


def _validate_graph(graph: nx.Graph) -> tuple[str, ...]:
    """Validate the supported graph domain and return sorted node IDs."""

    if not isinstance(graph, nx.Graph) or graph.is_directed():
        raise GreedyError("graph must be an undirected networkx.Graph")
    if graph.is_multigraph():
        raise GreedyError("graph must be simple")

    raw_nodes = tuple(graph.nodes)
    if any(not isinstance(node, str) for node in raw_nodes):
        raise GreedyError("node IDs must be strings")
    nodes = tuple(sorted(raw_nodes))
    if any(not node for node in nodes):
        raise GreedyError("node IDs must be non-empty strings")
    if any(left == right for left, right in graph.edges):
        raise GreedyError("graph must not contain a self-loop")

    for left, right, data in graph.edges(data=True):
        if "weight" not in data:
            raise GreedyError(f"edge ({left!r}, {right!r}) requires a weight")
        weight = data["weight"]
        if (
            isinstance(weight, bool)
            or not isinstance(weight, Real)
            or not isfinite(float(weight))
        ):
            raise GreedyError(
                f"edge ({left!r}, {right!r}) weight must be finite"
            )
        if weight < 0:
            raise GreedyError(
                f"edge ({left!r}, {right!r}) weight must be non-negative"
            )
    return nodes


def cut_value(graph: nx.Graph, partition_zero: Collection[str]) -> float:
    """Return the cut value, summing each undirected edge exactly once."""

    _validate_graph(graph)
    zero = set(partition_zero)
    return float(
        sum(
            float(data["weight"])
            for left, right, data in graph.edges(data=True)
            if (left in zero) != (right in zero)
        )
    )


def _ordered_nodes(graph: nx.Graph, nodes: tuple[str, ...]) -> tuple[str, ...]:
    """Order nodes by decreasing weighted degree, then by node ID."""

    weighted_degrees = {
        node: sum(float(data["weight"]) for data in graph[node].values())
        for node in nodes
    }
    return tuple(
        sorted(nodes, key=lambda node: (-weighted_degrees[node], node))
    )


def _tie_label(seed: int, node: str) -> int:
    """Choose a stable seeded label without Python hash randomization."""

    payload = json.dumps(
        (seed, node),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).digest()[0] & 1


def solve_greedy(graph: nx.Graph, *, seed: int) -> GreedyResult:
    """Build a weighted Max-Cut using sequential maximum-gain assignments.

    Every edge is considered when its later endpoint is assigned. Choosing the
    better side cuts at least half of the newly considered non-negative edge
    weight, yielding the standard 1/2 approximation guarantee.
    """

    normalized_seed = _validate_seed(seed)
    nodes = _validate_graph(graph)
    node_order = _ordered_nodes(graph, nodes)
    labels: dict[str, int] = {}

    for node in node_order:
        gain_if_zero = 0.0
        gain_if_one = 0.0
        for neighbor, data in graph[node].items():
            neighbor_label = labels.get(neighbor)
            if neighbor_label is None:
                continue
            weight = float(data["weight"])
            if neighbor_label == 1:
                gain_if_zero += weight
            else:
                gain_if_one += weight

        if gain_if_zero > gain_if_one:
            labels[node] = 0
        elif gain_if_one > gain_if_zero:
            labels[node] = 1
        else:
            labels[node] = _tie_label(normalized_seed, node)

    partition_zero = tuple(node for node in nodes if labels[node] == 0)
    partition_one = tuple(node for node in nodes if labels[node] == 1)
    total_edge_weight = float(
        sum(float(data["weight"]) for _, _, data in graph.edges(data=True))
    )
    return GreedyResult(
        partition_zero=partition_zero,
        partition_one=partition_one,
        cut_value=cut_value(graph, set(partition_zero)),
        total_edge_weight=total_edge_weight,
        seed=normalized_seed,
        node_order=node_order,
    )
