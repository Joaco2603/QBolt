"""Backend-agnostic QAOA orchestration and execution adapters.

The core only knows how to evaluate an :class:`IsingModel` and consume a
backend's measurement counts. Guppy/Selene and Nexus details stay in adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from ..ising import IsingModel


@dataclass(frozen=True)
class QAOAProgram:
    """Backend-neutral description of one parameterized QAOA circuit."""

    variables: tuple[str, ...]
    offset: float
    linear: tuple[tuple[str, float], ...]
    quadratic: tuple[tuple[str, str, float], ...]
    layers: int


@dataclass(frozen=True)
class MeasurementBatch:
    """Canonical measurement counts returned by a backend adapter."""

    counts: Mapping[str, int]
    metadata: Mapping[str, Any] = field(default_factory=dict)


class QAOABackend(Protocol):
    """Protocol implemented by local and cloud execution adapters."""

    name: str

    def execute(
        self,
        program: QAOAProgram,
        gamma: Sequence[float],
        beta: Sequence[float],
        *,
        shots: int,
        seed: int | None,
    ) -> MeasurementBatch:
        ...


@dataclass(frozen=True)
class QAOAResult:
    bitstring: str
    spins: Mapping[str, int]
    energy: float
    gamma: tuple[float, ...]
    beta: tuple[float, ...]
    counts: Mapping[str, int]
    probabilities: Mapping[str, float]
    energies: Mapping[str, float]
    backend: str
    layers: int
    shots: int
    optimizer_status: str
    optimizer_success: bool
    objective_evaluations: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


class QAOA:
    """Optimize and sample a minimization Ising Hamiltonian."""

    def __init__(self, *, layers: int = 1, starts: int = 5, seed: int = 0) -> None:
        if type(layers) is not int or layers < 1:
            raise ValueError("layers must be a positive integer")
        if type(starts) is not int or starts < 5:
            raise ValueError("starts must be an integer of at least 5")
        self.layers = layers
        self.starts = starts
        self.seed = seed

    def run_local(self, model: IsingModel, *, backend: QAOABackend, shots: int = 1024) -> QAOAResult:
        return self.run(model, backend=backend, shots=shots)

    def run_cloud(
        self,
        model: IsingModel,
        *,
        session: object,
        shots: int = 1024,
        backend: QAOABackend | None = None,
    ) -> QAOAResult:
        if backend is None:
            from .backends import NexusBackend

            backend = NexusBackend(session)
        adapter = backend
        return self.run(model, backend=adapter, shots=shots)

    def run(self, model: IsingModel, *, backend: QAOABackend, shots: int = 1024) -> QAOAResult:
        if not isinstance(model, IsingModel):
            raise TypeError("model must be an IsingModel")
        if not model.variables:
            raise ValueError("QAOA requires at least one Ising variable")
        if type(shots) is not int or shots <= 0:
            raise ValueError("shots must be a positive integer")
        program = QAOAProgram(
            variables=model.variables,
            offset=model.offset,
            linear=tuple((name, float(model.linear[name])) for name in model.variables),
            quadratic=tuple((left, right, float(value)) for (left, right), value in model.quadratic.items()),
            layers=self.layers,
        )
        result = self._optimize(model, program, backend, shots)
        return result

    def _optimize(self, model: IsingModel, program: QAOAProgram, backend: QAOABackend, shots: int) -> QAOAResult:
        try:
            import numpy as np
            from scipy.optimize import minimize
        except ImportError as error:
            raise RuntimeError("QAOA optimization requires numpy and scipy") from error

        rng = np.random.default_rng(self.seed)
        evaluations = 0
        best = None

        def objective(parameters: Any) -> float:
            nonlocal evaluations
            evaluations += 1
            gamma = tuple(float(value) for value in parameters[: self.layers])
            beta = tuple(float(value) for value in parameters[self.layers :])
            batch = backend.execute(program, gamma, beta, shots=shots, seed=self.seed + evaluations)
            return _expected_energy(model, batch.counts)

        for _ in range(self.starts):
            initial = rng.uniform(-np.pi, np.pi, size=2 * self.layers)
            outcome = minimize(objective, initial, method="BFGS")
            candidate = (float(outcome.fun), tuple(float(x) for x in outcome.x), outcome)
            if best is None or (candidate[0], candidate[1]) < (best[0], best[1]):
                best = candidate
        assert best is not None
        gamma = best[1][: self.layers]
        beta = best[1][self.layers :]
        batch = backend.execute(program, gamma, beta, shots=shots, seed=self.seed)
        counts = _canonical_counts(batch.counts, model.variables)
        energies = {bits: model.energy(_bits_to_spins(bits, model.variables)) for bits in counts}
        bitstring = min(counts, key=lambda bits: (energies[bits], bits))
        optimizer = best[2]
        return QAOAResult(
            bitstring=bitstring,
            spins=_bits_to_spins(bitstring, model.variables),
            energy=energies[bitstring],
            gamma=gamma,
            beta=beta,
            counts=counts,
            probabilities={bits: count / sum(counts.values()) for bits, count in counts.items()},
            energies=energies,
            backend=getattr(backend, "name", type(backend).__name__),
            layers=self.layers,
            shots=shots,
            optimizer_status=str(getattr(optimizer, "message", "completed")),
            optimizer_success=bool(getattr(optimizer, "success", False)),
            objective_evaluations=evaluations,
            metadata=dict(batch.metadata),
        )


def _bits_to_spins(bitstring: str, variables: Sequence[str]) -> dict[str, int]:
    if len(bitstring) != len(variables) or any(bit not in "01" for bit in bitstring):
        raise ValueError(f"Invalid bitstring {bitstring!r} for {len(variables)} qubits")
    return {variable: 1 - 2 * int(bit) for variable, bit in zip(variables, bitstring, strict=True)}


def _canonical_counts(counts: Mapping[str, int], variables: Sequence[str]) -> dict[str, int]:
    expected = len(variables)
    normalized: dict[str, int] = {}
    for bitstring, count in counts.items():
        if type(count) is not int or count < 0:
            raise ValueError("Measurement counts must be non-negative integers")
        if len(bitstring) != expected or any(bit not in "01" for bit in bitstring):
            raise ValueError(f"Backend returned invalid bitstring {bitstring!r}")
        normalized[bitstring] = normalized.get(bitstring, 0) + count
    if not normalized or sum(normalized.values()) <= 0:
        raise ValueError("Backend returned no measurement shots")
    return dict(sorted(normalized.items()))


def _expected_energy(model: IsingModel, counts: Mapping[str, int]) -> float:
    canonical = _canonical_counts(counts, model.variables)
    total = sum(canonical.values())
    return sum(
        count * model.energy(_bits_to_spins(bits, model.variables))
        for bits, count in canonical.items()
    ) / total

