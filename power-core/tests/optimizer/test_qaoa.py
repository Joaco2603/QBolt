"""Pure-Python contracts for Ising conversion and QAOA orchestration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from optimizer.quantum import IsingModel, MeasurementBatch, QAOA

def test_ising_model_converts_qubo_and_preserves_exact_energy() -> None:
    qubo = SimpleNamespace(
        decision_variables=("a", "b"),
        auxiliary_variables=(),
        offset=2.0,
        linear={"a": 3.0, "b": -1.0},
        quadratic={("b", "a"): 4.0},
    )
    model = IsingModel.from_qubo(qubo)

    assert model.variables == ("a", "b")
    assert model.offset == pytest.approx(4.0)
    assert model.linear == {"a": -2.5, "b": -0.5}
    assert model.quadratic == {("a", "b"): 1.0}
    for a in (0, 1):
        for b in (0, 1):
            binary = {"a": a, "b": b}
            spins = model.binary_to_spins(binary)
            expected = 2.0 + 3.0 * a - b + 4.0 * a * b
            assert model.energy(spins) == pytest.approx(expected)


def test_ising_model_rejects_incomplete_assignments() -> None:
    model = IsingModel(("a",), 0.0, {"a": 1.0}, {})
    with pytest.raises(ValueError, match="missing"):
        model.energy({})
    with pytest.raises(ValueError, match="binary"):
        model.binary_to_spins({"a": True})


class RecordingBackend:
    name = "recording"

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[float, ...], tuple[float, ...]]] = []

    def execute(self, program, gamma, beta, *, shots, seed):
        self.calls.append((tuple(gamma), tuple(beta)))
        return MeasurementBatch({"00": shots, "11": 0})


def test_qaoa_runs_seeded_multistart_and_returns_statistics() -> None:
    model = IsingModel(("a", "b"), 0.0, {"a": -1.0, "b": -1.0}, {("a", "b"): 0.5})
    backend = RecordingBackend()
    result = QAOA(layers=1, starts=5, seed=11).run(model, backend=backend, shots=8)

    assert len(backend.calls) >= 6  # five optimization starts plus final sampling
    assert result.bitstring == "00"
    assert result.spins == {"a": 1, "b": 1}
    assert result.counts == {"00": 8, "11": 0}
    assert result.probabilities == {"00": 1.0, "11": 0.0}
    assert result.energies["00"] == pytest.approx(-1.5)
    assert result.layers == 1


def test_qaoa_requires_at_least_five_starts() -> None:
    with pytest.raises(ValueError, match="at least 5"):
        QAOA(starts=4)
