"""Deterministic Ising-model representation used by quantum optimizers."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


def _validate_assignment(
    variables: tuple[str, ...], assignment: Mapping[str, int], *, binary: bool
) -> None:
    expected = set(variables)
    supplied = set(assignment)
    missing = sorted(expected - supplied)
    unknown = sorted(supplied - expected)
    if missing:
        kind = "binary" if binary else "spin"
        raise ValueError(f"Assignment is missing {kind} variables: {missing}")
    if unknown:
        raise ValueError(f"Assignment contains unknown variables: {unknown}")
    allowed = (0, 1) if binary else (-1, 1)
    for variable, value in assignment.items():
        if type(value) is not int or value not in allowed:
            label = "binary (0 or 1)" if binary else "spin (-1 or +1)"
            raise ValueError(f"Assignment value for {variable!r} must be {label}")


@dataclass(frozen=True)
class IsingModel:
    """A finite minimization Hamiltonian ``offset + h·z + J·zz``."""

    variables: tuple[str, ...]
    offset: float
    linear: Mapping[str, float]
    quadratic: Mapping[tuple[str, str], float]

    def __post_init__(self) -> None:
        variables = tuple(self.variables)
        if len(set(variables)) != len(variables) or not all(
            isinstance(variable, str) and variable for variable in variables
        ):
            raise ValueError("Ising variables must be unique, non-empty strings")
        if not isfinite(float(self.offset)):
            raise ValueError("Ising offset must be finite")
        if set(self.linear) != set(variables):
            raise ValueError("Ising linear fields must cover every variable exactly")
        for variable, coefficient in self.linear.items():
            if not isfinite(float(coefficient)):
                raise ValueError(f"Ising field for {variable!r} must be finite")
        for pair, coefficient in self.quadratic.items():
            if len(pair) != 2 or pair[0] == pair[1] or any(
                variable not in variables for variable in pair
            ):
                raise ValueError(f"Invalid Ising coupling pair: {pair!r}")
            if tuple(sorted(pair)) != pair:
                raise ValueError(f"Ising coupling pair is not canonical: {pair!r}")
            if not isfinite(float(coefficient)):
                raise ValueError(f"Ising coupling {pair!r} must be finite")

    @classmethod
    def from_qubo(cls, qubo: object) -> "IsingModel":
        """Convert a repository ``QuboModel`` without mutating it."""
        required = ("decision_variables", "auxiliary_variables", "offset", "linear", "quadratic")
        if not all(hasattr(qubo, attribute) for attribute in required):
            raise TypeError("qubo must be a QuboModel")
        variables = tuple(qubo.decision_variables) + tuple(qubo.auxiliary_variables)
        linear = {variable: float(qubo.linear.get(variable, 0.0)) for variable in variables}
        quadratic: dict[tuple[str, str], float] = {}
        for variable in qubo.linear:
            if variable not in linear:
                raise ValueError(f"QUBO contains unknown variable {variable!r}")
        linear = {variable: -float(qubo.linear.get(variable, 0.0)) / 2.0 for variable in variables}
        offset = float(qubo.offset) + sum(float(value) for value in qubo.linear.values()) / 2.0
        for pair, coefficient in qubo.quadratic.items():
            if len(pair) != 2 or pair[0] == pair[1]:
                raise ValueError(f"QUBO pair must contain two distinct variables: {pair!r}")
            left, right = sorted(pair)
            if left not in linear or right not in linear:
                raise ValueError(f"QUBO contains unknown variable pair: {pair!r}")
            value = float(coefficient) / 4.0
            quadratic[(left, right)] = quadratic.get((left, right), 0.0) + value
            linear[left] -= value
            linear[right] -= value
            offset += value
        return cls(variables, offset, linear, quadratic)

    def energy(self, spins: Mapping[str, int]) -> float:
        """Evaluate the complete Ising energy, including the offset."""
        _validate_assignment(self.variables, spins, binary=False)
        value = self.offset + sum(self.linear[name] * spins[name] for name in self.variables)
        return value + sum(
            coefficient * spins[left] * spins[right]
            for (left, right), coefficient in self.quadratic.items()
        )

    def binary_to_spins(self, assignment: Mapping[str, int]) -> dict[str, int]:
        _validate_assignment(self.variables, assignment, binary=True)
        return {variable: 1 - 2 * assignment[variable] for variable in self.variables}

    def spins_to_binary(self, assignment: Mapping[str, int]) -> dict[str, int]:
        _validate_assignment(self.variables, assignment, binary=False)
        return {variable: (1 - assignment[variable]) // 2 for variable in self.variables}

    @property
    def h(self) -> Mapping[str, float]:
        return self.linear

    @property
    def J(self) -> Mapping[tuple[str, str], float]:
        return self.quadratic
