"""Execution adapters for the backend-independent QAOA algorithm."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .qaoa import (
    MeasurementBatch,
    QAOAProgram,
    _canonical_counts,
)


class LocalGuppySeleneBackend:
    """Generate Guppy and execute it with Selene's local state-vector emulator."""

    name = "guppy-selene"

    def __init__(self, executor: Any | None = None) -> None:
        self._executor = executor

    def execute(
        self,
        program: QAOAProgram,
        gamma: Sequence[float],
        beta: Sequence[float],
        *,
        shots: int,
        seed: int | None,
    ) -> MeasurementBatch:
        if self._executor is not None:
            return _as_batch(self._executor(program, gamma, beta, shots=shots, seed=seed))
        main = _build_guppy_program(program, gamma, beta)
        try:
            result = (
                main.emulator(n_qubits=len(program.variables))
                .statevector_sim()
                .with_seed(seed)
                .with_shots(shots)
                .run()
            )
        except ImportError as error:
            raise RuntimeError(
                "LocalGuppySeleneBackend requires guppylang and selene-sim"
            ) from error
        return MeasurementBatch(_counts_from_guppy_result(result, program.variables))


class NexusBackend:
    """Submit Guppy through an already-authenticated Nexus session."""

    name = "quantinuum-nexus"

    def __init__(
        self,
        session: object,
        executor: Any | None = None,
        *,
        project: object | None = None,
        timeout: float | None = None,
        max_cost: float | list[float] | None = None,
    ) -> None:
        if session is None:
            raise ValueError("An authenticated Nexus session is required")
        self.session = session
        self._executor = executor
        self.project = project
        self.timeout = timeout
        self.max_cost = max_cost

    def execute(
        self,
        program: QAOAProgram,
        gamma: Sequence[float],
        beta: Sequence[float],
        *,
        shots: int,
        seed: int | None,
    ) -> MeasurementBatch:
        if self._executor is not None:
            return _as_batch(
                self._executor(
                    self.session, program, gamma, beta, shots=shots, seed=seed
                )
            )
        main = _build_guppy_program(program, gamma, beta)
        try:
            hugr_ref = self.session.hugr.upload(
                hugr_package=main.compile(),
                name="qaoa-ising-program",
            )
            config = self.session.models.SeleneConfig(
                n_qubits=len(program.variables),
                simulator=self.session.models.StatevectorSimulator(),
            )
            job_kwargs: dict[str, Any] = {
                "programs": [hugr_ref],
                "n_shots": [shots],
                "backend_config": config,
                "name": "qaoa-ising-execution",
            }
            if self.project is not None:
                job_kwargs["project"] = self.project
            if self.max_cost is not None:
                job_kwargs["max_cost"] = self.max_cost
            job = self.session.start_execute_job(**job_kwargs)
            self.session.jobs.wait_for(job, timeout=self.timeout)
            result = self.session.jobs.results(job)[0].download_result()
        except AttributeError as error:
            raise RuntimeError(
                "The authenticated Nexus session does not expose the required "
                "hugr, Selene, and jobs APIs"
            ) from error
        return MeasurementBatch(
            _counts_from_collated_counts(result.collated_counts(), program.variables)
        )


def _build_guppy_program(
    program: QAOAProgram, gamma: Sequence[float], beta: Sequence[float]
) -> Any:
    """Build one fully bound Guppy program for one objective evaluation."""
    if len(gamma) != program.layers or len(beta) != program.layers:
        raise ValueError("gamma and beta must contain one value per QAOA layer")
    try:
        from guppylang import guppy
        from guppylang.std.angles import angle
        from guppylang.std.builtins import result
        from guppylang.std.quantum import cx, h, measure, qubit, rx, rz
    except ImportError as error:
        raise RuntimeError(
            "Guppy circuit generation requires the guppylang package"
        ) from error

    def half_turns(value: float) -> str:
        return f"angle({float(value) / 3.141592653589793!r})"

    lines = ["def main() -> None:"]
    lines.extend(f"    q{index} = qubit()" for index in range(len(program.variables)))
    lines.extend(f"    h(q{index})" for index in range(len(program.variables)))
    for layer in range(program.layers):
        for index, (_, coefficient) in enumerate(program.linear):
            lines.append(f"    rz(q{index}, {half_turns(gamma[layer] * coefficient)})")
        for left, right, coefficient in program.quadratic:
            left_index = program.variables.index(left)
            right_index = program.variables.index(right)
            lines.extend(
                (
                    f"    cx(q{left_index}, q{right_index})",
                    f"    rz(q{right_index}, {half_turns(gamma[layer] * coefficient)})",
                    f"    cx(q{left_index}, q{right_index})",
                )
            )
        lines.extend(
            f"    rx(q{index}, {half_turns(beta[layer])})"
            for index in range(len(program.variables))
        )
    lines.extend(
        f'    result("q{index}", measure(q{index}))'
        for index in range(len(program.variables))
    )
    namespace = {
        "cx": cx,
        "h": h,
        "angle": angle,
        "measure": measure,
        "qubit": qubit,
        "result": result,
        "rx": rx,
        "rz": rz,
    }
    import linecache

    source = "\n".join(lines) + "\n"
    filename = f"<qaoa-guppy-{id(program)}-{id(gamma)}-{id(beta)}>"
    linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
    exec(compile(source, filename, "exec"), namespace)
    return guppy(namespace["main"])


def _counts_from_guppy_result(result: Any, variables: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for shot in result.results:
        values = shot.as_dict() if hasattr(shot, "as_dict") else dict(shot)
        bits = "".join(str(int(values[f"q{index}"])) for index in range(len(variables)))
        counts[bits] = counts.get(bits, 0) + 1
    return counts


def _counts_from_collated_counts(
    counts: Any, variables: Sequence[str]
) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in counts.items():
        bitstring = _collated_key_to_bitstring(key, len(variables))
        normalized[bitstring] = normalized.get(bitstring, 0) + int(value)
    return _canonical_counts(normalized, variables)


def _collated_key_to_bitstring(key: Any, qubit_count: int) -> str:
    """Normalize Nexus collated-count keys to q0..qN bitstring order."""
    if isinstance(key, str):
        return key

    if not isinstance(key, tuple):
        raise ValueError(f"Unsupported Nexus measurement key: {key!r}")

    # Nexus may return one named result, e.g. (('result', '011'),).
    if len(key) == 1:
        entry = key[0]
        if isinstance(entry, tuple) and len(entry) == 2:
            return str(entry[1])
        raise ValueError(f"Unsupported Nexus measurement key: {key!r}")

    # Selene can also return one entry per measured qubit:
    # (('q0', '0'), ('q1', '1'), ...).
    if all(isinstance(entry, tuple) and len(entry) == 2 for entry in key):
        named_values = dict(key)
        expected_labels = [f"q{index}" for index in range(qubit_count)]
        if set(named_values) != set(expected_labels) or len(named_values) != len(key):
            raise ValueError(f"Unexpected Nexus measurement labels: {key!r}")
        return "".join(str(named_values[label]) for label in expected_labels)

    raise ValueError(f"Unsupported Nexus measurement key: {key!r}")


def _as_batch(value: MeasurementBatch | Mapping[str, int]) -> MeasurementBatch:
    if isinstance(value, MeasurementBatch):
        return value
    return MeasurementBatch(counts=value)
