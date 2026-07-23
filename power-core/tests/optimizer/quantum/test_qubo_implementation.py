"""Verification of the weighted Max-Cut QUBO public API."""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path
import sys
from typing import Any

import networkx as nx
import pytest


ROOT = Path(__file__).parents[4]
sys.path.insert(0, str(ROOT / "power-core"))

from src.optimizer.quantum.qubo_implementation import (  # noqa: E402
    build_max_cut_qubo,
    cut_weight,
    recommended_penalty,
)


def regional_graph() -> tuple[nx.Graph, dict[str, Any]]:
    artifact_path = ROOT / "power-core" / "artifacts" / "regional_instance.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    graph = nx.Graph()
    graph.add_nodes_from(node["id"] for node in artifact["nodes"])
    graph.add_weighted_edges_from(
        (edge["source"], edge["target"], edge["weight"])
        for edge in artifact["edges"]
    )
    return graph, artifact


def test_qubo_energy_is_negative_cut_weight_for_every_regional_partition() -> None:
    graph, _ = regional_graph()
    model = build_max_cut_qubo(graph)

    for values in product((0, 1), repeat=len(model.decision_variables)):
        assignment = dict(zip(model.decision_variables, values, strict=True))
        assert model.minimum_energy(assignment) == pytest.approx(
            -cut_weight(graph, assignment)
        )


def test_regional_reference_partition_reaches_documented_optimum() -> None:
    graph, artifact = regional_graph()
    reference = artifact["reference_two_zone_max_cut"]
    zone_a = set(reference["zone_a"])
    assignment = {node: int(node in zone_a) for node in graph.nodes}
    model = build_max_cut_qubo(graph)

    energies = [
        model.minimum_energy(dict(zip(model.decision_variables, values, strict=True)))
        for values in product((0, 1), repeat=len(model.decision_variables))
    ]

    assert cut_weight(graph, assignment) == pytest.approx(reference["cut_weight_kv"])
    assert model.minimum_energy(assignment) == pytest.approx(-1058.0)
    assert min(energies) == pytest.approx(-1058.0)


def test_constraints_are_added_to_the_max_cut_objective() -> None:
    graph = nx.Graph()
    graph.add_weighted_edges_from((("a", "b", 2.0), ("b", "c", 3.0)))
    penalty = 10.0
    model = build_max_cut_qubo(
        graph,
        penalty=penalty,
        configure_constraints=lambda builder: builder.equal("a", "b"),
    )

    valid = {"a": 0, "b": 0, "c": 1}
    invalid = {"a": 0, "b": 1, "c": 0}
    assert model.minimum_energy(valid) == pytest.approx(-3.0)
    assert model.minimum_energy(invalid) == pytest.approx(-5.0 + penalty)


def test_recommended_penalty_exceeds_the_entire_regional_objective_range() -> None:
    graph, _ = regional_graph()

    assert recommended_penalty(graph) > sum(
        data["weight"] for _, _, data in graph.edges(data=True)
    )


def test_rejects_weights_that_are_not_valid_for_max_cut() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=-1.0)

    with pytest.raises(ValueError, match="non-negative"):
        build_max_cut_qubo(graph)
