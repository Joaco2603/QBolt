"""Contracts for the Iceberg QED QAOA compiler."""

from __future__ import annotations

import networkx as nx
import pytest

from src.optimizer.quantum.iceberg import (
    IcebergCompileConfig,
    IcebergCompiler,
    IcebergValidationError,
    postselect_counts,
)


def _graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_weighted_edges_from(
        [("a", "b", 1.0), ("b", "c", 2.0), ("c", "d", 3.0), ("d", "e", 1.0), ("e", "f", 2.0)]
    )
    return graph


def test_iceberg_requires_an_even_logical_qubit_count() -> None:
    graph = nx.path_graph(["a", "b", "c"])
    with pytest.raises(IcebergValidationError, match="even"):
        IcebergCompiler().compile(graph, gamma=(0.1,), beta=(0.2,))


def test_iceberg_rejects_non_finite_edge_weights() -> None:
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=float("nan"))
    with pytest.raises(IcebergValidationError, match="finite"):
        IcebergCompiler().compile(graph, gamma=(0.1,), beta=(0.2,))


def test_iceberg_compiles_six_logical_qubits_to_eight_physical_qubits() -> None:
    program = IcebergCompiler().compile(_graph(), gamma=(0.1,), beta=(0.2,))

    assert program.logical_qubits == 6
    assert program.physical_qubits == 8
    assert program.top_qubit == "top"
    assert program.bottom_qubit == "bottom"
    assert program.two_qubit_depth > 0
    assert program.metrics["co_compiled"] is True
    assert program.to_pytket().n_qubits == 8


def test_z2_mixer_schedule_never_has_more_depth_than_single_anchor() -> None:
    graph = _graph()
    shared_anchor = IcebergCompiler(IcebergCompileConfig(use_z2_symmetry=False)).compile(
        graph, gamma=(0.1,), beta=(0.2,)
    )
    symmetric = IcebergCompiler(IcebergCompileConfig(use_z2_symmetry=True)).compile(
        graph, gamma=(0.1,), beta=(0.2,)
    )

    assert symmetric.mixer_two_qubit_depth <= shared_anchor.mixer_two_qubit_depth


def test_compilation_is_deterministic_and_uses_gadget_barriers() -> None:
    compiler = IcebergCompiler(IcebergCompileConfig(syndrome_count=1))
    first = compiler.compile(_graph(), gamma=(0.1,), beta=(0.2,))
    second = compiler.compile(_graph(), gamma=(0.1,), beta=(0.2,))

    assert first.layers == second.layers
    assert any(operation.kind == "BARRIER" for layer in first.layers for operation in layer)


def test_postselection_discards_failed_syndromes_and_decodes_logical_bits() -> None:
    accepted = postselect_counts(
        {"00000000": 4, "00000001": 3}, logical_qubits=6
    )

    assert accepted.accepted_counts == {"000000": 4}
    assert accepted.accepted_shots == 4
    assert accepted.total_shots == 7
    assert accepted.rate == pytest.approx(4 / 7)
