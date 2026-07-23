"""Behavioural contract for the dynamic QUBO constraint builder.

These tests intentionally precede the production implementation (TDD RED
phase).  The builder must expose a QUBO model whose ``minimum_energy`` method
returns the lowest energy after choosing any auxiliary variables introduced by
the encoding.
"""

from __future__ import annotations

import importlib.util
import json
from itertools import product
from pathlib import Path
from typing import Callable, Mapping, Protocol, Self, cast

import networkx as nx
import pytest


ROOT = Path(__file__).parents[5]
REGIONAL_INSTANCE = ROOT / "power-core" / "artifacts" / "regional_instance.json"
BUILDER_MODULE = (
    ROOT
    / "power-core"
    / "src"
    / "optimizer"
    / "quantum"
    / "qubo"
    / "constraint_builder.py"
)
SPEC = importlib.util.spec_from_file_location("constraint_builder", BUILDER_MODULE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QuboModel(Protocol):
    """Minimal model contract exercised by these tests."""

    decision_variables: tuple[str, ...]

    def minimum_energy(self, assignment: Mapping[str, int]) -> float:
        ...


class ConstraintBuilderApi(Protocol):
    """Public builder methods required by the constraint contract."""

    def __init__(self, graph: nx.Graph, *, penalty: float) -> None:
        ...

    def exactly_one(self, *variables: str) -> Self:
        ...

    def at_most_one(self, *variables: str) -> Self:
        ...

    def at_least_one(self, *variables: str) -> Self:
        ...

    def requires(self, *variables: str, iff: bool = False) -> Self:
        ...

    def at_most_k(self, *variables: str, k: int) -> Self:
        ...

    def at_least_k(self, *variables: str, k: int) -> Self:
        ...

    def mutually_exclusive(self, *variables: str) -> Self:
        ...

    def equal(self, *variables: str) -> Self:
        ...

    def build(self) -> QuboModel:
        ...


BuilderType = type[ConstraintBuilderApi]
ConstraintBuilder: BuilderType = cast(BuilderType, MODULE.ConstraintBuilder)


NODE_A, NODE_B, NODE_C = "SUB-07", "SUB-15", "SUB-29"


@pytest.fixture
def weighted_graph() -> nx.Graph:
    payload = json.loads(REGIONAL_INSTANCE.read_text(encoding="utf-8"))
    graph = nx.Graph()
    graph.add_nodes_from(node["id"] for node in payload["nodes"])
    graph.add_weighted_edges_from(
        (edge["source"], edge["target"], edge["weight"])
        for edge in payload["edges"]
    )
    return graph


def test_weighted_graph_fixture_comes_from_the_six_node_regional_instance() -> None:
    payload = json.loads(REGIONAL_INSTANCE.read_text(encoding="utf-8"))

    assert payload["source"] == "Subestaciones.* + LineasDeTransmision.*"
    assert payload["edge_model"] == "confirmed_transmission_lines"
    assert len(payload["nodes"]) == 6
    assert len(payload["edges"]) == 5


def build_constraint(
    weighted_graph: nx.Graph,
    method_name: str,
    *variables: str,
    penalty: float = 7.0,
    **options: object,
) -> QuboModel:
    builder = ConstraintBuilder(weighted_graph, penalty=penalty)
    constraint_method = cast(Callable[..., None], getattr(builder, method_name))
    constraint_method(*variables, **options)
    return builder.build()


def energy(model: QuboModel, **assignment: int) -> float:
    """Evaluate the best QUBO energy for a primary-variable assignment."""
    return model.minimum_energy(assignment)


def test_builder_accepts_a_weighted_graph_and_preserves_decision_variables(
    weighted_graph: nx.Graph,
) -> None:
    model = build_constraint(weighted_graph, "exactly_one", NODE_A, NODE_B)

    assert model.decision_variables == (NODE_A, NODE_B)
    assert energy(model, **{NODE_A: 1, NODE_B: 0}) == 0


@pytest.mark.parametrize(
    ("assignment", "expected_energy"),
    [
        ({NODE_A: 0, NODE_B: 0, NODE_C: 0}, 7.0),
        ({NODE_A: 1, NODE_B: 0, NODE_C: 0}, 0.0),
        ({NODE_A: 0, NODE_B: 1, NODE_C: 0}, 0.0),
        ({NODE_A: 1, NODE_B: 1, NODE_C: 0}, 7.0),
        ({NODE_A: 1, NODE_B: 1, NODE_C: 1}, 28.0),
    ],
)
def test_exactly_one_uses_the_squared_sum_penalty(
    weighted_graph: nx.Graph, assignment: dict[str, int], expected_energy: float
) -> None:
    model = build_constraint(
        weighted_graph, "exactly_one", NODE_A, NODE_B, NODE_C
    )

    assert energy(model, **assignment) == expected_energy


@pytest.mark.parametrize(
    ("assignment", "expected_energy"),
    [
        ({NODE_A: 0, NODE_B: 0, NODE_C: 0}, 0.0),
        ({NODE_A: 1, NODE_B: 0, NODE_C: 0}, 0.0),
        ({NODE_A: 1, NODE_B: 1, NODE_C: 0}, 7.0),
        ({NODE_A: 1, NODE_B: 1, NODE_C: 1}, 21.0),
    ],
)
def test_at_most_one_penalizes_each_selected_pair(
    weighted_graph: nx.Graph, assignment: dict[str, int], expected_energy: float
) -> None:
    model = build_constraint(
        weighted_graph, "at_most_one", NODE_A, NODE_B, NODE_C
    )

    assert energy(model, **assignment) == expected_energy


def test_at_least_one_supports_three_variables_without_penalizing_valid_choices(
    weighted_graph: nx.Graph,
) -> None:
    model = build_constraint(
        weighted_graph, "at_least_one", NODE_A, NODE_B, NODE_C
    )

    for values in product((0, 1), repeat=3):
        assignment = dict(zip(model.decision_variables, values, strict=True))
        expected_energy = 7.0 if sum(values) == 0 else 0.0
        assert energy(model, **assignment) == expected_energy


@pytest.mark.parametrize(
    ("assignment", "expected_energy"),
    [
        ({NODE_A: 0, NODE_B: 0, NODE_C: 0}, 0.0),
        ({NODE_A: 1, NODE_B: 0, NODE_C: 0}, 0.0),
        ({NODE_A: 1, NODE_B: 1, NODE_C: 0}, 0.0),
        ({NODE_A: 1, NODE_B: 1, NODE_C: 1}, 7.0),
    ],
)
def test_at_most_k_with_k_two_penalizes_only_excess_selections(
    weighted_graph: nx.Graph, assignment: dict[str, int], expected_energy: float
) -> None:
    model = build_constraint(
        weighted_graph, "at_most_k", NODE_A, NODE_B, NODE_C, k=2
    )

    assert energy(model, **assignment) == expected_energy


@pytest.mark.parametrize(
    ("assignment", "expected_energy"),
    [
        ({NODE_A: 0, NODE_B: 0, NODE_C: 0}, 28.0),
        ({NODE_A: 1, NODE_B: 0, NODE_C: 0}, 7.0),
        ({NODE_A: 1, NODE_B: 1, NODE_C: 0}, 0.0),
        ({NODE_A: 1, NODE_B: 1, NODE_C: 1}, 0.0),
    ],
)
def test_at_least_k_with_k_two_penalizes_deficient_selections(
    weighted_graph: nx.Graph, assignment: dict[str, int], expected_energy: float
) -> None:
    model = build_constraint(
        weighted_graph, "at_least_k", NODE_A, NODE_B, NODE_C, k=2
    )

    assert energy(model, **assignment) == expected_energy


@pytest.mark.parametrize(
    ("assignment", "expected_energy"),
    [
        ({NODE_A: 0, NODE_B: 0}, 0.0),
        ({NODE_A: 0, NODE_B: 1}, 0.0),
        ({NODE_A: 1, NODE_B: 0}, 7.0),
        ({NODE_A: 1, NODE_B: 1}, 0.0),
    ],
)
def test_requires_a_only_if_b(weighted_graph: nx.Graph, assignment: dict[str, int], expected_energy: float) -> None:
    model = build_constraint(weighted_graph, "requires", NODE_A, NODE_B)

    assert energy(model, **assignment) == expected_energy


@pytest.mark.parametrize(
    ("assignment", "expected_energy"),
    [
        ({NODE_A: 0, NODE_B: 0}, 0.0),
        ({NODE_A: 0, NODE_B: 1}, 7.0),
        ({NODE_A: 1, NODE_B: 0}, 7.0),
        ({NODE_A: 1, NODE_B: 1}, 0.0),
    ],
)
def test_requires_with_iff_flag_forces_both_variables_to_agree(
    weighted_graph: nx.Graph,
    assignment: dict[str, int],
    expected_energy: float,
) -> None:
    model = build_constraint(
        weighted_graph, "requires", NODE_A, NODE_B, iff=True
    )

    assert energy(model, **assignment) == expected_energy


@pytest.mark.parametrize(
    ("assignment", "expected_energy"),
    [
        ({NODE_A: 0, NODE_B: 0}, 0.0),
        ({NODE_A: 0, NODE_B: 1}, 0.0),
        ({NODE_A: 1, NODE_B: 0}, 0.0),
        ({NODE_A: 1, NODE_B: 1}, 7.0),
    ],
)
def test_mutually_exclusive_penalizes_the_selected_pair(
    weighted_graph: nx.Graph, assignment: dict[str, int], expected_energy: float
) -> None:
    model = build_constraint(weighted_graph, "mutually_exclusive", NODE_A, NODE_B)

    assert energy(model, **assignment) == expected_energy


@pytest.mark.parametrize(
    ("assignment", "expected_energy"),
    [
        ({NODE_A: 0, NODE_B: 0}, 0.0),
        ({NODE_A: 0, NODE_B: 1}, 7.0),
        ({NODE_A: 1, NODE_B: 0}, 7.0),
        ({NODE_A: 1, NODE_B: 1}, 0.0),
    ],
)
def test_equal_requires_both_variables_to_agree(
    weighted_graph: nx.Graph, assignment: dict[str, int], expected_energy: float
) -> None:
    model = build_constraint(weighted_graph, "equal", NODE_A, NODE_B)

    assert energy(model, **assignment) == expected_energy


def test_rejects_constraint_variables_that_are_not_graph_nodes(weighted_graph: nx.Graph) -> None:
    builder = ConstraintBuilder(weighted_graph, penalty=7.0)

    with pytest.raises(ValueError, match="missing"):
        builder.exactly_one(NODE_A, "missing")


def test_builder_composes_constraints_fluently(weighted_graph: nx.Graph) -> None:
    model = (
        ConstraintBuilder(weighted_graph, penalty=7.0)
        .at_most_k(NODE_A, NODE_B, NODE_C, k=2)
        .requires(NODE_A, NODE_B)
        .build()
    )

    assert energy(model, **{NODE_A: 0, NODE_B: 1, NODE_C: 1}) == 0.0
    assert energy(model, **{NODE_A: 1, NODE_B: 0, NODE_C: 0}) == 7.0
    assert energy(model, **{NODE_A: 1, NODE_B: 1, NODE_C: 1}) == 7.0


@pytest.mark.parametrize(
    "method_name",
    ["requires", "mutually_exclusive", "equal"],
)
def test_binary_constraints_reject_any_arity_other_than_two(
    weighted_graph: nx.Graph, method_name: str
) -> None:
    builder = ConstraintBuilder(weighted_graph, penalty=7.0)
    method = cast(Callable[..., object], getattr(builder, method_name))

    with pytest.raises(ValueError, match="exactly two"):
        method(NODE_A)
    with pytest.raises(ValueError, match="exactly two"):
        method(NODE_A, NODE_B, NODE_C)


def test_cardinality_constraints_reject_invalid_k(weighted_graph: nx.Graph) -> None:
    builder = ConstraintBuilder(weighted_graph, penalty=7.0)

    with pytest.raises(ValueError, match="non-negative"):
        builder.at_most_k(NODE_A, NODE_B, k=-1)
    with pytest.raises(ValueError, match="cannot exceed"):
        builder.at_least_k(NODE_A, NODE_B, k=3)


def test_requires_rejects_a_non_boolean_iff_flag(weighted_graph: nx.Graph) -> None:
    builder = ConstraintBuilder(weighted_graph, penalty=7.0)

    with pytest.raises(TypeError, match="iff"):
        builder.requires(NODE_A, NODE_B, iff="true")  # type: ignore[arg-type]


def test_model_rejects_non_binary_missing_and_unknown_assignments(
    weighted_graph: nx.Graph,
) -> None:
    model = build_constraint(weighted_graph, "exactly_one", NODE_A, NODE_B)

    with pytest.raises(ValueError, match="binary"):
        model.minimum_energy({NODE_A: 2, NODE_B: 0})
    with pytest.raises(ValueError, match="missing"):
        model.minimum_energy({NODE_A: 1})
    with pytest.raises(ValueError, match="unknown"):
        model.minimum_energy({NODE_A: 1, NODE_B: 0, NODE_C: 0})


def test_builder_rejects_a_graph_edge_without_a_finite_weight() -> None:
    graph = nx.Graph()
    graph.add_edge(NODE_A, NODE_B, weight=float("nan"))

    with pytest.raises(ValueError, match="finite.*weight"):
        ConstraintBuilder(graph, penalty=7.0)
