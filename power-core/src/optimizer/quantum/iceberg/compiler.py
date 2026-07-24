"""Deterministic Iceberg ``[[k+2,k,2]]`` compilation for Max-Cut QAOA.

The compiler keeps the QED gadget boundaries explicit.  This is deliberate:
generic circuit optimisation is allowed inside an algorithmic component, but
must not cancel gates across a fault-detection gadget boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from types import MappingProxyType
from typing import Mapping, Sequence

import networkx as nx


class IcebergValidationError(ValueError):
    """Raised when an input cannot be represented by the selected Iceberg code."""


@dataclass(frozen=True)
class IcebergCompileConfig:
    """Controls deterministic, all-to-all Iceberg QAOA compilation."""

    syndrome_count: int = 0
    use_z2_symmetry: bool = True

    def __post_init__(self) -> None:
        if type(self.syndrome_count) is not int or self.syndrome_count < 0:
            raise IcebergValidationError("syndrome_count must be a non-negative integer")


@dataclass(frozen=True)
class IcebergOperation:
    """One logical schedule operation; barriers protect QED gadget boundaries."""

    kind: str
    qubits: tuple[str, ...]
    angle: float | None = None
    component: str = "algorithm"


@dataclass(frozen=True)
class PostselectionResult:
    accepted_counts: Mapping[str, int]
    accepted_shots: int
    total_shots: int

    @property
    def rate(self) -> float:
        return 0.0 if self.total_shots == 0 else self.accepted_shots / self.total_shots


@dataclass(frozen=True)
class IcebergCompiledProgram:
    """A physical data-qubit schedule and its reproducible resource metrics."""

    logical_variables: tuple[str, ...]
    layers: tuple[tuple[IcebergOperation, ...], ...]
    config: IcebergCompileConfig

    @property
    def logical_qubits(self) -> int:
        return len(self.logical_variables)

    @property
    def physical_qubits(self) -> int:
        return self.logical_qubits + 2

    @property
    def top_qubit(self) -> str:
        return "top"

    @property
    def bottom_qubit(self) -> str:
        return "bottom"

    @property
    def data_qubits(self) -> tuple[str, ...]:
        return (*self.logical_variables, self.top_qubit, self.bottom_qubit)

    @property
    def two_qubit_depth(self) -> int:
        return sum(any(len(operation.qubits) == 2 for operation in layer) for layer in self.layers)

    @property
    def mixer_two_qubit_depth(self) -> int:
        return sum(
            any(operation.kind == "RXX" for operation in layer) for layer in self.layers
        )

    @property
    def metrics(self) -> Mapping[str, object]:
        two_qubit_gates = sum(
            len(operation.qubits) == 2 for layer in self.layers for operation in layer
        )
        return MappingProxyType({
            "logical_qubits": self.logical_qubits,
            "physical_data_qubits": self.physical_qubits,
            "two_qubit_gates": two_qubit_gates,
            "two_qubit_depth": self.two_qubit_depth,
            "mixer_two_qubit_depth": self.mixer_two_qubit_depth,
            "syndrome_count": self.config.syndrome_count,
            "co_compiled": True,
            "noise_model": "ideal",
        })

    def to_pytket(self):
        """Export the data-qubit circuit; barriers preserve QED component boundaries.

        Syndrome ancillas are measured/reset implementation resources and are
        represented by protected schedule components rather than persistent data
        qubits in this local ideal export.
        """
        from pytket import Circuit

        circuit = Circuit(self.physical_qubits)
        indices = {qubit: index for index, qubit in enumerate(self.data_qubits)}
        for layer in self.layers:
            for operation in layer:
                if operation.kind == "H":
                    circuit.H(indices[operation.qubits[0]])
                elif operation.kind == "CX":
                    circuit.CX(*(indices[qubit] for qubit in operation.qubits))
                elif operation.kind == "RZZ":
                    left, right = (indices[qubit] for qubit in operation.qubits)
                    circuit.CX(left, right)
                    circuit.Rz(float(operation.angle) / 3.141592653589793, right)
                    circuit.CX(left, right)
                elif operation.kind == "RXX":
                    left, right = (indices[qubit] for qubit in operation.qubits)
                    circuit.H(left)
                    circuit.H(right)
                    circuit.CX(left, right)
                    circuit.Rz(float(operation.angle) / 3.141592653589793, right)
                    circuit.CX(left, right)
                    circuit.H(left)
                    circuit.H(right)
                elif operation.kind == "BARRIER":
                    circuit.add_barrier(list(range(self.physical_qubits)))
        return circuit


class IcebergCompiler:
    """Compile weighted Max-Cut QAOA into an Iceberg physical-gate schedule."""

    def __init__(self, config: IcebergCompileConfig | None = None) -> None:
        self.config = config or IcebergCompileConfig()

    def compile(
        self,
        graph: nx.Graph,
        *,
        gamma: Sequence[float],
        beta: Sequence[float],
    ) -> IcebergCompiledProgram:
        variables = _validate_graph(graph)
        if len(variables) % 2:
            raise IcebergValidationError("Iceberg requires an even logical qubit count")
        if len(gamma) != len(beta) or not gamma:
            raise IcebergValidationError("gamma and beta must be non-empty sequences of equal length")
        physical_qubits = len(variables) + 2
        if self.config.syndrome_count and physical_qubits % 4:
            raise IcebergValidationError(
                "the proposed syndrome gadget requires a physical qubit count divisible by 4"
            )

        layers: list[tuple[IcebergOperation, ...]] = []
        layers.extend(_initialization_layers(variables))
        for depth, (gamma_value, beta_value) in enumerate(zip(gamma, beta, strict=True)):
            layers.extend(_schedule_cost_layer(graph, variables, float(gamma_value), depth))
            layers.extend(_schedule_mixer_layer(variables, float(beta_value), self.config.use_z2_symmetry, depth))
            if self.config.syndrome_count:
                for _ in range(_syndromes_after_layer(depth, len(gamma), self.config.syndrome_count)):
                    layers.extend(_syndrome_layers(variables))
        layers.append((IcebergOperation("BARRIER", (), component="final-measurement"),))
        return IcebergCompiledProgram(variables, tuple(layers), self.config)


def postselect_counts(counts: Mapping[str, int], *, logical_qubits: int) -> PostselectionResult:
    """Reject physical samples failing either Iceberg global parity check.

    The physical bit order is logical bits followed by ``top`` and ``bottom``.
    This is the local ideal decoder contract; noisy backends may supply actual
    syndrome bits and should pre-filter them before calling this helper.
    """
    if type(logical_qubits) is not int or logical_qubits <= 0 or logical_qubits % 2:
        raise IcebergValidationError("logical_qubits must be a positive even integer")
    expected = logical_qubits + 2
    accepted: dict[str, int] = {}
    total = 0
    for bits, count in counts.items():
        if not isinstance(bits, str) or len(bits) != expected or any(bit not in "01" for bit in bits):
            raise IcebergValidationError("physical measurement bitstrings have an invalid length or value")
        if type(count) is not int or count < 0:
            raise IcebergValidationError("measurement counts must be non-negative integers")
        total += count
        # Z stabilizer parity and a decoded X-check proxy in the computational
        # basis. Both ancillas must agree and the full physical parity is even.
        if bits[-1] == bits[-2] and sum(int(bit) for bit in bits) % 2 == 0:
            logical = bits[:logical_qubits]
            accepted[logical] = accepted.get(logical, 0) + count
    return PostselectionResult(MappingProxyType(dict(sorted(accepted.items()))), sum(accepted.values()), total)


def _validate_graph(graph: nx.Graph) -> tuple[str, ...]:
    if not isinstance(graph, nx.Graph) or graph.is_directed() or graph.is_multigraph():
        raise IcebergValidationError("graph must be a simple undirected networkx.Graph")
    variables = tuple(sorted(graph.nodes))
    if not variables or any(not isinstance(node, str) or not node for node in variables):
        raise IcebergValidationError("graph nodes must be non-empty strings")
    for left, right, data in graph.edges(data=True):
        weight = data.get("weight", 1.0)
        if (
            left == right
            or isinstance(weight, bool)
            or not isinstance(weight, Real)
            or not isfinite(float(weight))
        ):
            raise IcebergValidationError("each graph edge must have a finite numeric weight")
    return variables


def _initialization_layers(variables: tuple[str, ...]) -> list[tuple[IcebergOperation, ...]]:
    qubits = (*variables, "top", "bottom")
    layers = [(tuple(IcebergOperation("H", (qubit,), component="initialization") for qubit in qubits))]
    # Two-branch GHZ shape: pair endpoints, then join them.  The schedule is
    # deterministic and leaves an explicit barrier for fault-tolerance bounds.
    pairs = list(zip(qubits[::2], qubits[1::2], strict=True))
    layers.append(tuple(IcebergOperation("CX", pair, component="initialization") for pair in pairs))
    roots = tuple(left for left, _ in pairs)
    while len(roots) > 1:
        pair_roots = tuple(zip(roots[::2], roots[1::2]))
        layers.append(
            tuple(IcebergOperation("CX", pair, component="initialization") for pair in pair_roots)
        )
        roots = tuple(left for left, _ in pair_roots) + (() if len(roots) % 2 == 0 else (roots[-1],))
    layers.append((IcebergOperation("BARRIER", (), component="initialization"),))
    return layers


def _schedule_cost_layer(graph: nx.Graph, variables: tuple[str, ...], gamma: float, depth: int) -> list[tuple[IcebergOperation, ...]]:
    pending = [
        IcebergOperation("RZZ", tuple(sorted((left, right))), 2.0 * gamma * float(data.get("weight", 1.0)), f"cost-{depth}")
        for left, right, data in graph.edges(data=True)
    ]
    return _matching_schedule(pending)


def _schedule_mixer_layer(variables: tuple[str, ...], beta: float, use_z2: bool, depth: int) -> list[tuple[IcebergOperation, ...]]:
    anchors = ("top", "bottom") if use_z2 else ("top",)
    operations = [
        IcebergOperation("RXX", (anchors[index % len(anchors)], variable), 2.0 * beta, f"mixer-{depth}")
        for index, variable in enumerate(variables)
    ]
    return _matching_schedule(operations)


def _syndromes_after_layer(depth: int, total_layers: int, count: int) -> int:
    return int((depth + 1) * count // total_layers) - int(depth * count // total_layers)


def _syndrome_layers(variables: tuple[str, ...]) -> list[tuple[IcebergOperation, ...]]:
    # Each aggregate operation denotes the two ancilla interactions for a data
    # qubit. Their internal ordering is protected by surrounding barriers.
    return [
        (IcebergOperation("BARRIER", (), component="syndrome"),),
        tuple(IcebergOperation("SYNDROME", (qubit,), component="syndrome") for qubit in (*variables, "top", "bottom")),
        (IcebergOperation("BARRIER", (), component="syndrome"),),
    ]


def _matching_schedule(operations: list[IcebergOperation]) -> list[tuple[IcebergOperation, ...]]:
    """Schedule commuting operations using deterministic maximum matchings."""
    remaining = list(operations)
    result: list[tuple[IcebergOperation, ...]] = []
    while remaining:
        graph = nx.Graph()
        by_edge: dict[tuple[str, str], IcebergOperation] = {}
        for operation in remaining:
            left, right = operation.qubits
            edge = tuple(sorted((left, right)))
            graph.add_edge(*edge, weight=1.0)
            by_edge[edge] = operation
        matching = nx.max_weight_matching(graph, maxcardinality=True, weight="weight")
        selected_edges = sorted(tuple(sorted(edge)) for edge in matching)
        selected = tuple(by_edge[edge] for edge in selected_edges)
        result.append(selected)
        selected_set = set(selected)
        remaining = [operation for operation in remaining if operation not in selected_set]
    return result
