"""Pure-Python contracts for Ising conversion and QAOA orchestration."""

from __future__ import annotations

import pytest
import threading
import time
from types import SimpleNamespace

from src.optimizer.quantum import IsingModel, MeasurementBatch, QAOA
from src.optimizer.quantum.qaoa.backends import (
    _cost_rotation_radians,
    _counts_from_collated_counts,
    _counts_from_nexus_result,
    _mixer_rotation_radians,
)
from src.optimizer.quantum.qubo.constraint_builder import QuboModel

def test_ising_model_converts_qubo_and_preserves_exact_energy() -> None:
    qubo = QuboModel(
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
    assert result.metadata["parallel_backend_enabled"] is False
    assert len(result.metadata["starts"]) == 5
    assert result.objective_evaluations == sum(
        start["objective_evaluations"] for start in result.metadata["starts"]
    )


def test_qaoa_requires_at_least_five_starts() -> None:
    with pytest.raises(ValueError, match="at least 5"):
        QAOA(starts=4)


def test_qaoa_rotation_angles_match_exp_minus_i_hamiltonian_convention() -> None:
    assert _cost_rotation_radians(0.25, 3.0) == pytest.approx(1.5)
    assert _cost_rotation_radians(-0.5, 2.0) == pytest.approx(-2.0)
    assert _mixer_rotation_radians(0.25) == pytest.approx(0.5)


def test_qaoa_rejects_non_positive_parallel_worker_limit() -> None:
    with pytest.raises(ValueError, match="max_parallel_starts"):
        QAOA(max_parallel_starts=0)


class ParallelRecordingBackend(RecordingBackend):
    supports_parallel_starts = True

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def execute(self, program, gamma, beta, *, shots, seed):
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.002)
            return super().execute(program, gamma, beta, shots=shots, seed=seed)
        finally:
            with self._lock:
                self.active -= 1


def test_qaoa_limits_parallel_starts_to_configured_workers() -> None:
    model = IsingModel(("a", "b"), 0.0, {"a": -1.0, "b": -1.0}, {("a", "b"): 0.5})
    backend = ParallelRecordingBackend()
    result = QAOA(starts=5, seed=11, max_parallel_starts=2).run(
        model, backend=backend, shots=8
    )

    assert backend.max_active <= 2
    assert result.metadata["parallel_workers"] == 2
    assert result.metadata["parallel_backend_enabled"] is True


def test_nexus_collated_counts_normalize_named_qubit_results() -> None:
    counts = {
        (
            ("q0", "0"),
            ("q1", "1"),
            ("q2", "1"),
        ): 4
    }

    assert _counts_from_collated_counts(counts, ("a", "b", "c")) == {"011": 4}


def test_nexus_collated_counts_preserve_single_named_result_format() -> None:
    counts = {(('result', '011'),): 4}

    assert _counts_from_collated_counts(counts, ("a", "b", "c")) == {"011": 4}


class FakeQsysResult:
    def __init__(self, counts) -> None:
        self._counts = counts

    def collated_counts(self):
        return self._counts


class FakePytketResult:
    def __init__(self, counts) -> None:
        self._counts = counts

    def get_counts(self):
        return self._counts


def test_nexus_result_normalizer_accepts_qsys_collated_counts() -> None:
    result = FakeQsysResult(
        {(('q1', '1'), ('q0', '0')): 4}
    )

    assert _counts_from_nexus_result(result, ("a", "b")) == {"01": 4}


def test_nexus_result_normalizer_accepts_pytket_bit_tuple_counts() -> None:
    result = FakePytketResult({(0, 1, 1): 3})

    assert _counts_from_nexus_result(result, ("a", "b", "c")) == {"011": 3}


def test_nexus_result_normalizer_rejects_unknown_result_type() -> None:
    with pytest.raises(RuntimeError, match="Unsupported Nexus execution result type"):
        _counts_from_nexus_result(object(), ("a",))


@pytest.mark.parametrize("count", [True, -1, 1.5])
def test_nexus_result_normalizer_rejects_invalid_counts(count) -> None:
    with pytest.raises(ValueError, match="Invalid Nexus measurement count"):
        _counts_from_nexus_result(FakePytketResult({(0,): count}), ("a",))


def test_nexus_backend_uses_unique_names_and_project(monkeypatch) -> None:
    from src.optimizer.quantum.qaoa import backends as backend_module
    from src.optimizer.quantum.qaoa.backends import NexusBackend
    from src.optimizer.quantum.qaoa.qaoa import QAOAProgram

    class FakeMain:
        def compile(self):
            return "compiled"

    uploads = []
    jobs = []

    class FakeJobs:
        def wait_for(self, job, timeout):
            return SimpleNamespace(name="COMPLETED")

        def results(self, job):
            return [SimpleNamespace(download_result=lambda: FakeQsysResult({(('result', '0'),): 2}))]

    class FakeSession:
        hugr = SimpleNamespace(upload=lambda **kwargs: uploads.append(kwargs) or "hugr-ref")
        models = SimpleNamespace(
            SeleneConfig=lambda **kwargs: SimpleNamespace(**kwargs),
            StatevectorSimulator=lambda: SimpleNamespace(),
        )
        jobs = FakeJobs()

        def start_execute_job(self, **kwargs):
            jobs.append(kwargs)
            return SimpleNamespace(id=f"job-{len(jobs)}")

    monkeypatch.setattr(backend_module, "_build_guppy_program", lambda *args: FakeMain())
    backend = NexusBackend(FakeSession(), project="project-ref", timeout=12, max_cost=3.0)
    program = QAOAProgram(("a",), 0.0, (("a", 0.0),), (), 1)

    backend.execute(program, (0.1,), (0.2,), shots=2, seed=7)
    backend.execute(program, (0.3,), (0.4,), shots=2, seed=8)

    assert uploads[0]["project"] == "project-ref"
    assert uploads[0]["name"] != uploads[1]["name"]
    assert jobs[0]["name"] != jobs[1]["name"]
    assert jobs[0]["project"] == "project-ref"
    assert jobs[0]["max_cost"] == 3.0


def test_nexus_backend_error_includes_submitted_job_id(monkeypatch) -> None:
    from src.optimizer.quantum.qaoa import backends as backend_module
    from src.optimizer.quantum.qaoa.backends import NexusBackend
    from src.optimizer.quantum.qaoa.qaoa import QAOAProgram

    class FakeSession:
        hugr = SimpleNamespace(upload=lambda **kwargs: "hugr-ref")
        models = SimpleNamespace(
            SeleneConfig=lambda **kwargs: SimpleNamespace(**kwargs),
            StatevectorSimulator=lambda: SimpleNamespace(),
        )
        jobs = SimpleNamespace(
            wait_for=lambda job, timeout: None,
            results=lambda job: [
                SimpleNamespace(
                    download_result=lambda: (_ for _ in ()).throw(ValueError("bad payload"))
                )
            ],
        )

        def start_execute_job(self, **kwargs):
            return SimpleNamespace(id="job-error-1")

    monkeypatch.setattr(backend_module, "_build_guppy_program", lambda *args: SimpleNamespace(compile=lambda: "compiled"))
    backend = NexusBackend(FakeSession())
    program = QAOAProgram(("a",), 0.0, (("a", 0.0),), (), 1)

    with pytest.raises(RuntimeError, match="job-error-1.*bad payload"):
        backend.execute(program, (0.1,), (0.2,), shots=2, seed=7)
