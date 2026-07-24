"""Small, dependency-light QUBO builder for binary graph decision variables.

The builder stores a conventional minimisation QUBO:
``offset + sum(linear[i] * x_i) + sum(quadratic[i, j] * x_i * x_j)``.
It keeps auxiliary variables private and minimises over them when evaluating a
primary assignment.  This makes cardinality constraints usable by callers
without exposing their encoding details.
"""

from __future__ import annotations

from itertools import combinations, product
from math import isfinite
from numbers import Real
from typing import Mapping

import networkx as nx


class QuboModel:
    """An immutable-in-practice QUBO model produced by :class:`ConstraintBuilder`."""

    def __init__(
        self,
        *,
        decision_variables: tuple[str, ...],
        auxiliary_variables: tuple[str, ...],
        offset: float,
        linear: Mapping[str, float],
        quadratic: Mapping[tuple[str, str], float],
    ) -> None:
        """Store an independent snapshot of the QUBO coefficients and variables."""
        self.decision_variables = decision_variables
        self.auxiliary_variables = auxiliary_variables
        self.offset = offset
        self.linear = dict(linear)
        self.quadratic = dict(quadratic)

    def minimum_energy(self, assignment: Mapping[str, int]) -> float:
        """Return the minimum energy for primary variables over auxiliaries."""
        expected = set(self.decision_variables)
        supplied = set(assignment)
        missing = expected - supplied
        unknown = supplied - expected
        if missing:
            raise ValueError(f"Assignment is missing decision variables: {sorted(missing)}")
        if unknown:
            raise ValueError(f"Assignment contains unknown variables: {sorted(unknown)}")
        self._validate_binary_assignment(assignment)

        if not self.auxiliary_variables:
            return self._energy(assignment)

        return min(
            self._energy({
                **assignment,
                **dict(zip(self.auxiliary_variables, values, strict=True)),
            })
            for values in product((0, 1), repeat=len(self.auxiliary_variables))
        )

    @staticmethod
    def _validate_binary_assignment(assignment: Mapping[str, int]) -> None:
        """Reject assignments whose values are not exact integer bits, 0 or 1."""
        for variable, value in assignment.items():
            if type(value) is not int or value not in (0, 1):
                raise ValueError(
                    f"Assignment value for {variable!r} must be binary (0 or 1)"
                )

    def _energy(self, assignment: Mapping[str, int]) -> float:
        """Evaluate offset + linear terms + quadratic interactions for one full assignment."""
        energy = self.offset
        for variable, coefficient in self.linear.items():
            energy += coefficient * assignment[variable]
        for (left, right), coefficient in self.quadratic.items():
            energy += coefficient * assignment[left] * assignment[right]
        return energy


class ConstraintBuilder:
    """Build composable QUBO penalties over nodes of a weighted graph."""

    def __init__(self, graph: nx.Graph, *, penalty: float) -> None:
        """Start an empty builder and validate the graph weights and penalty scale."""
        if not isinstance(graph, nx.Graph):
            raise TypeError("graph must be a networkx.Graph")
        if not isinstance(penalty, Real) or not isfinite(float(penalty)) or penalty <= 0:
            raise ValueError("penalty must be a positive finite number")
        self._validate_weights(graph)
        self._graph = graph
        self._penalty = float(penalty)
        self._decision_variables: list[str] = []
        self._auxiliary_variables: list[str] = []
        self._offset = 0.0
        self._linear: dict[str, float] = {}
        self._quadratic: dict[tuple[str, str], float] = {}

    def exactly_one(self, *variables: str) -> ConstraintBuilder:
        """Penalize every assignment except those where exactly one variable is 1.

        Encodes ``penalty * (sum(x_i) - 1)^2``.
        """
        names = self._validate_variables(variables)
        self._add_square({name: 1.0 for name in names}, constant=-1.0)
        return self

    def at_most_one(self, *variables: str) -> ConstraintBuilder:
        """Penalize pairs of selected variables so no more than one can be 1."""
        names = self._validate_variables(variables)
        for left, right in combinations(names, 2):
            self._add_quadratic(left, right, self._penalty)
        return self

    def at_least_one(self, *variables: str) -> ConstraintBuilder:
        """Require one or more selected variables; shorthand for ``at_least_k(..., k=1)``."""
        return self.at_least_k(*variables, k=1)

    def requires(self, *variables: str, iff: bool = False) -> ConstraintBuilder:
        """Require the first variable to imply the second, or make them equal when ``iff`` is true.

        The one-way penalty is ``penalty * left * (1 - right)``.
        """
        left, right = self._validate_binary_variables(variables)
        if type(iff) is not bool:
            raise TypeError("iff must be a boolean")
        if iff:
            return self.equal(left, right)
        self._add_linear(left, self._penalty)
        self._add_quadratic(left, right, -self._penalty)
        return self

    def at_most_k(self, *variables: str, k: int) -> ConstraintBuilder:
        """Limit selected variables to ``k`` using private binary-encoded slack variables."""
        names = self._validate_variables(variables)
        self._validate_k(k, len(names), maximum_can_exceed=True)
        if k >= len(names):
            return self
        coefficients = {name: 1.0 for name in names}
        coefficients.update(
            (auxiliary, float(weight))
            for auxiliary, weight in self._new_slack_variables(k)
        )
        self._add_square(coefficients, constant=-float(k))
        return self

    def at_least_k(self, *variables: str, k: int) -> ConstraintBuilder:
        """Require at least ``k`` selected variables using private binary-encoded slack variables."""
        names = self._validate_variables(variables)
        self._validate_k(k, len(names), maximum_can_exceed=False)
        if k == 0:
            return self
        coefficients = {name: 1.0 for name in names}
        coefficients.update(
            (auxiliary, -float(weight))
            for auxiliary, weight in self._new_slack_variables(len(names) - k)
        )
        self._add_square(coefficients, constant=-float(k))
        return self

    def mutually_exclusive(self, *variables: str) -> ConstraintBuilder:
        """Prevent two variables from both being 1 via ``penalty * left * right``."""
        left, right = self._validate_binary_variables(variables)
        self._add_quadratic(left, right, self._penalty)
        return self

    def equal(self, *variables: str) -> ConstraintBuilder:
        """Force two variables to have the same value via ``penalty * (left - right)^2``."""
        left, right = self._validate_binary_variables(variables)
        self._add_linear(left, self._penalty)
        self._add_linear(right, self._penalty)
        self._add_quadratic(left, right, -2.0 * self._penalty)
        return self

    def build(self) -> QuboModel:
        """Create a model snapshot without mutating the builder."""
        return QuboModel(
            decision_variables=tuple(self._decision_variables),
            auxiliary_variables=tuple(self._auxiliary_variables),
            offset=self._offset,
            linear=self._linear,
            quadratic=self._quadratic,
        )

    @staticmethod
    def _validate_weights(graph: nx.Graph) -> None:
        """Ensure every graph edge supplies a finite numeric weight before building constraints."""
        for left, right, attributes in graph.edges(data=True):
            weight = attributes.get("weight")
            if not isinstance(weight, Real) or not isfinite(float(weight)):
                raise ValueError(
                    f"Edge ({left!r}, {right!r}) must have a finite weight"
                )

    def _validate_variables(self, variables: tuple[str, ...]) -> tuple[str, ...]:
        """Validate graph-node variables and register each as a primary decision variable."""
        if not variables:
            raise ValueError("A constraint requires at least one variable")
        if len(set(variables)) != len(variables):
            raise ValueError("Constraint variables must be unique")
        missing = [variable for variable in variables if variable not in self._graph]
        if missing:
            raise ValueError(f"Constraint variables are missing from graph: {missing}")
        for variable in variables:
            if not isinstance(variable, str):
                raise TypeError("Constraint variables must be graph node IDs as strings")
            if variable not in self._decision_variables:
                self._decision_variables.append(variable)
        return variables

    def _validate_binary_variables(self, variables: tuple[str, ...]) -> tuple[str, str]:
        """Validate and return exactly two primary variables for pairwise constraints."""
        if len(variables) != 2:
            raise ValueError("Binary constraints require exactly two variables")
        names = self._validate_variables(variables)
        return names[0], names[1]

    @staticmethod
    def _validate_k(k: int, variable_count: int, *, maximum_can_exceed: bool) -> None:
        """Check cardinality bounds, allowing a redundant upper bound when requested."""
        if type(k) is not int:
            raise TypeError("k must be an integer")
        if k < 0:
            raise ValueError("k must be non-negative")
        if not maximum_can_exceed and k > variable_count:
            raise ValueError("k cannot exceed the number of variables")

    def _new_slack_variables(self, maximum: int) -> tuple[tuple[str, int], ...]:
        """Create private auxiliary bits whose weighted sum represents values up to ``maximum``."""
        weights = self._binary_weights(maximum)
        variables: list[tuple[str, int]] = []
        for weight in weights:
            name = self._next_auxiliary_name()
            self._auxiliary_variables.append(name)
            variables.append((name, weight))
        return tuple(variables)

    @staticmethod
    def _binary_weights(maximum: int) -> tuple[int, ...]:
        """Return compact binary weights that can represent every integer from 0 to ``maximum``."""
        if maximum == 0:
            return ()
        weights: list[int] = []
        covered = 0
        next_weight = 1
        while covered + next_weight < maximum:
            weights.append(next_weight)
            covered += next_weight
            next_weight *= 2
        weights.append(maximum - covered)
        return tuple(weights)

    def _next_auxiliary_name(self) -> str:
        """Return an unused, deterministic name for the next private slack variable."""
        occupied = set(self._graph.nodes) | set(self._decision_variables) | set(self._auxiliary_variables)
        index = len(self._auxiliary_variables)
        name = f"__qubo_aux_{index}"
        while name in occupied:
            index += 1
            name = f"__qubo_aux_{index}"
        return name

    def _add_square(self, coefficients: Mapping[str, float], *, constant: float) -> None:
        """Expand ``penalty * (constant + sum(coefficient_i * x_i))^2`` into QUBO terms.

        The expansion contributes a constant offset, linear ``x_i`` terms, and
        quadratic ``x_i * x_j`` interactions.
        """
        self._offset += self._penalty * constant * constant
        items = tuple(coefficients.items())
        for variable, coefficient in items:
            self._add_linear(
                variable,
                self._penalty * (coefficient * coefficient + 2.0 * constant * coefficient),
            )
        for (left, left_coefficient), (right, right_coefficient) in combinations(items, 2):
            self._add_quadratic(
                left,
                right,
                2.0 * self._penalty * left_coefficient * right_coefficient,
            )

    def _add_linear(self, variable: str, coefficient: float) -> None:
        """Accumulate a linear QUBO coefficient for a term of the form ``c * x_i``."""
        self._linear[variable] = self._linear.get(variable, 0.0) + coefficient

    def _add_quadratic(self, left: str, right: str, coefficient: float) -> None:
        """Accumulate a quadratic coefficient ``c * x_i * x_j`` in canonical key order.

        A diagonal term is linear because binary variables satisfy ``x_i^2 = x_i``.
        """
        if left == right:
            self._add_linear(left, coefficient)
            return
        key = tuple(sorted((left, right)))
        self._quadratic[key] = self._quadratic.get(key, 0.0) + coefficient
