"""Behavioural contract for the QUBO-to-Ising conversion boundary."""

from __future__ import annotations

from itertools import product
from math import inf, nan
from typing import Mapping

import networkx as nx
import pytest

from src.optimizer.quantum.ising import IsingModel
from src.optimizer.quantum.qubo.constraint_builder import ConstraintBuilder, QuboModel


def make_qubo(
    *,
    decision_variables: tuple[str, ...],
    auxiliary_variables: tuple[str, ...] = (),
    offset: float = 0.0,
    linear: Mapping[str, float] | None = None,
    quadratic: Mapping[tuple[str, str], float] | None = None,
) -> QuboModel:
    """Build a small QUBO fixture without involving quantum execution."""

    return QuboModel(
        decision_variables=decision_variables,
        auxiliary_variables=auxiliary_variables,
        offset=offset,
        linear={} if linear is None else linear,
        quadratic={} if quadratic is None else quadratic,
    )


def test_from_qubo_converts_one_linear_term() -> None:
    qubo = make_qubo(decision_variables=("x",), offset=3.0, linear={"x": -6.0})

    model = IsingModel.from_qubo(qubo)

    assert model.variables == ("x",)
    assert model.offset == pytest.approx(0.0)
    assert model.linear == {"x": 3.0}
    assert model.quadratic == {}


def test_from_qubo_converts_one_quadratic_term() -> None:
    qubo = make_qubo(
        decision_variables=("x", "y"),
        offset=2.0,
        linear={"x": 0.0, "y": 0.0},
        quadratic={("x", "y"): 8.0},
    )

    model = IsingModel.from_qubo(qubo)

    assert model.offset == pytest.approx(4.0)
    assert model.linear == {"x": -2.0, "y": -2.0}
    assert model.quadratic == {("x", "y"): 2.0}


def test_from_qubo_accumulates_multiple_terms_per_variable() -> None:
    qubo = make_qubo(
        decision_variables=("a", "b", "c"),
        linear={"a": 4.0, "b": -2.0, "c": 6.0},
        quadratic={("a", "b"): 8.0, ("a", "c"): -4.0},
    )

    model = IsingModel.from_qubo(qubo)

    assert model.linear == {"a": -3.0, "b": -1.0, "c": -2.0}
    assert model.quadratic == {("a", "b"): 2.0, ("a", "c"): -1.0}


def test_from_qubo_preserves_decision_then_auxiliary_variable_order() -> None:
    qubo = make_qubo(
        decision_variables=("decision_b", "decision_a"),
        auxiliary_variables=("aux_1", "aux_0"),
        linear={"decision_b": 1.0, "aux_0": -2.0},
    )

    model = IsingModel.from_qubo(qubo)

    assert model.variables == ("decision_b", "decision_a", "aux_1", "aux_0")
    assert set(model.linear) == set(model.variables)


def test_from_qubo_canonicalizes_pair_keys() -> None:
    qubo = make_qubo(
        decision_variables=("a", "b", "c"),
        quadratic={("b", "a"): 4.0, ("c", "a"): -8.0},
    )

    model = IsingModel.from_qubo(qubo)

    assert model.quadratic == {("a", "b"): 1.0, ("a", "c"): -2.0}
    assert all(left < right for left, right in model.quadratic)


def test_energy_matches_qubo_for_every_two_variable_assignment() -> None:
    qubo = make_qubo(
        decision_variables=("x", "y"),
        offset=1.25,
        linear={"x": -2.0, "y": 3.0},
        quadratic={("x", "y"): 4.0},
    )
    model = IsingModel.from_qubo(qubo)

    for x, y in product((0, 1), repeat=2):
        binary = {"x": x, "y": y}
        assert model.energy(model.binary_to_spins(binary)) == pytest.approx(
            qubo.minimum_energy(binary)
        )


def test_energy_matches_qubo_for_a_three_variable_constraint_model() -> None:
    graph = nx.Graph()
    graph.add_weighted_edges_from((("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0)))
    qubo = ConstraintBuilder(graph, penalty=7.0).exactly_one("a", "b", "c").build()
    model = IsingModel.from_qubo(qubo)

    for values in product((0, 1), repeat=3):
        binary = dict(zip(("a", "b", "c"), values, strict=True))
        assert model.energy(model.binary_to_spins(binary)) == pytest.approx(
            qubo.minimum_energy(binary)
        )


def test_energy_includes_the_constant_offset() -> None:
    qubo = make_qubo(decision_variables=("x",), offset=9.5, linear={"x": 0.0})
    model = IsingModel.from_qubo(qubo)

    assert model.offset == pytest.approx(9.5)
    assert model.energy({"x": 1}) == pytest.approx(9.5)
    assert model.energy({"x": -1}) == pytest.approx(9.5)


def test_binary_to_spins_uses_zero_to_positive_one_and_one_to_negative_one() -> None:
    model = IsingModel.from_qubo(make_qubo(decision_variables=("x", "y")))

    assert model.binary_to_spins({"x": 0, "y": 1}) == {"x": 1, "y": -1}


def test_spins_to_binary_is_the_inverse_mapping() -> None:
    model = IsingModel.from_qubo(make_qubo(decision_variables=("x", "y")))
    binary = {"x": 1, "y": 0}

    assert model.spins_to_binary(model.binary_to_spins(binary)) == binary


def test_energy_rejects_missing_and_unknown_variables() -> None:
    model = IsingModel.from_qubo(make_qubo(decision_variables=("x", "y")))

    with pytest.raises(ValueError, match="missing"):
        model.energy({"x": 1})
    with pytest.raises(ValueError, match="unknown"):
        model.energy({"x": 1, "y": -1, "z": 1})


@pytest.mark.parametrize("invalid_spin", (0, 2, -2, True, False))
def test_energy_rejects_non_spin_values_including_booleans(invalid_spin: int) -> None:
    model = IsingModel.from_qubo(make_qubo(decision_variables=("x",)))

    with pytest.raises(ValueError, match="spin"):
        model.energy({"x": invalid_spin})


@pytest.mark.parametrize("invalid_binary", (-1, 2, True, False))
def test_binary_to_spins_rejects_non_binary_values_including_booleans(
    invalid_binary: int,
) -> None:
    model = IsingModel.from_qubo(make_qubo(decision_variables=("x",)))

    with pytest.raises(ValueError, match="binary"):
        model.binary_to_spins({"x": invalid_binary})


@pytest.mark.parametrize("invalid", (nan, inf, -inf))
def test_from_qubo_rejects_non_finite_coefficients(invalid: float) -> None:
    offset_qubo = make_qubo(decision_variables=("x",), offset=invalid, linear={"x": 0.0})
    linear_qubo = make_qubo(decision_variables=("x",), linear={"x": invalid})
    quadratic_qubo = make_qubo(
        decision_variables=("x", "y"), quadratic={("x", "y"): invalid}
    )

    for qubo in (offset_qubo, linear_qubo, quadratic_qubo):
        with pytest.raises(ValueError, match="finite"):
            IsingModel.from_qubo(qubo)


def test_conversion_does_not_mutate_the_qubo() -> None:
    qubo = make_qubo(
        decision_variables=("x",),
        auxiliary_variables=("aux",),
        offset=1.0,
        linear={"x": 2.0, "aux": -3.0},
        quadratic={("x", "aux"): 4.0},
    )
    snapshot = (
        qubo.decision_variables,
        qubo.auxiliary_variables,
        qubo.offset,
        dict(qubo.linear),
        dict(qubo.quadratic),
    )

    IsingModel.from_qubo(qubo)

    assert (
        qubo.decision_variables,
        qubo.auxiliary_variables,
        qubo.offset,
        qubo.linear,
        qubo.quadratic,
    ) == snapshot


def test_energy_does_not_mutate_the_spin_assignment() -> None:
    model = IsingModel.from_qubo(make_qubo(decision_variables=("x", "y")))
    spins = {"x": 1, "y": -1}
    snapshot = dict(spins)

    model.energy(spins)

    assert spins == snapshot
