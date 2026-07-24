"""Execution adapters for the backend-independent QAOA algorithm."""

from __future__ import annotations

from numbers import Integral
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .qaoa import (
    MeasurementBatch,
    QAOAProgram,
    _canonical_counts,
)


class LocalGuppySeleneBackend:
    """Generate Guppy and execute it with Selene's local state-vector emulator."""

    name = "guppy-selene"
    supports_parallel_starts = False

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
    supports_parallel_starts = True

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
        identifier = uuid4().hex
        hugr_name = f"qaoa-ising-program-{identifier}"
        job_name = f"qaoa-ising-execution-{identifier}"
        job: Any | None = None
        try:
            hugr_ref = self.session.hugr.upload(
                hugr_package=main.compile(),
                name=hugr_name,
                project=self.project,
            )
            config = self.session.models.SeleneConfig(
                n_qubits=len(program.variables),
                simulator=self.session.models.StatevectorSimulator(),
            )
            job_kwargs: dict[str, Any] = {
                "programs": [hugr_ref],
                "n_shots": [shots],
                "backend_config": config,
                "name": job_name,
            }
            if self.project is not None:
                job_kwargs["project"] = self.project
            if self.max_cost is not None:
                job_kwargs["max_cost"] = self.max_cost
            job = self.session.start_execute_job(**job_kwargs)
            self.session.jobs.wait_for(job, timeout=self.timeout)
            results = self.session.jobs.results(job)
            if not results:
                raise RuntimeError("Nexus returned no execution results")
            result_ref = results[0]
            download_result = getattr(result_ref, "download_result", None)
            if not callable(download_result):
                raise RuntimeError(
                    "Nexus execution result does not expose download_result()"
                )
            result = download_result()
            counts = _counts_from_nexus_result(result, program.variables)
        except Exception as error:
            job_id = _job_identifier(job)
            if isinstance(error, AttributeError):
                message = (
                    "The authenticated Nexus session does not expose the required "
                    "hugr, Selene, and jobs APIs"
                )
            else:
                message = "Nexus execution failed"
            raise RuntimeError(
                f"{message} (job {job_id}; {error})"
            ) from error
        return MeasurementBatch(counts)


def _cost_rotation_radians(gamma: float, coefficient: float) -> float:
    """Return the RZ angle implementing ``exp(-i * gamma * coefficient * Z)``."""

    return 2.0 * float(gamma) * float(coefficient)


def _mixer_rotation_radians(beta: float) -> float:
    """Return the RX angle implementing ``exp(-i * beta * X)``."""

    return 2.0 * float(beta)


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
            rotation = _cost_rotation_radians(gamma[layer], coefficient)
            lines.append(f"    rz(q{index}, {half_turns(rotation)})")
        for left, right, coefficient in program.quadratic:
            left_index = program.variables.index(left)
            right_index = program.variables.index(right)
            lines.extend(
                (
                    f"    cx(q{left_index}, q{right_index})",
                    f"    rz(q{right_index}, {half_turns(_cost_rotation_radians(gamma[layer], coefficient))})",
                    f"    cx(q{left_index}, q{right_index})",
                )
            )
        lines.extend(
            f"    rx(q{index}, {half_turns(_mixer_rotation_radians(beta[layer]))})"
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
    if not isinstance(counts, Mapping):
        raise ValueError(
            f"Nexus collated_counts() must return a mapping, got {type(counts).__name__}"
        )
    normalized: dict[str, int] = {}
    for key, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
            raise ValueError(f"Invalid Nexus measurement count for {key!r}: {value!r}")
        bitstring = _collated_key_to_bitstring(key, len(variables))
        normalized[bitstring] = normalized.get(bitstring, 0) + int(value)
    return _canonical_counts(normalized, variables)


def _counts_from_nexus_result(
    result: Any, variables: Sequence[str]
) -> dict[str, int]:
    """Normalize the result variants returned by Nexus execution refs.

    HUGR/Selene results normally expose ``collated_counts``. Some Nexus/Pytket
    result versions expose ``get_counts`` instead, so this adapter intentionally
    uses capability checks rather than importing concrete Nexus result classes.
    """
    collated_counts = getattr(result, "collated_counts", None)
    if callable(collated_counts):
        return _counts_from_collated_counts(collated_counts(), variables)

    get_counts = getattr(result, "get_counts", None)
    if callable(get_counts):
        return _counts_from_bit_counts(get_counts(), variables)

    if isinstance(result, Mapping):
        return _counts_from_bit_counts(result, variables)

    raise RuntimeError(
        "Unsupported Nexus execution result type: "
        f"{type(result).__module__}.{type(result).__qualname__}"
    )


def _counts_from_bit_counts(
    counts: Any, variables: Sequence[str]
) -> dict[str, int]:
    """Convert direct bit-tuple counts, such as Pytket BackendResult counts."""
    if not isinstance(counts, Mapping):
        raise ValueError(
            f"Nexus get_counts() must return a mapping, got {type(counts).__name__}"
        )
    normalized: dict[str, int] = {}
    for key, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
            raise ValueError(f"Invalid Nexus measurement count for {key!r}: {value!r}")
        if isinstance(key, str):
            bitstring = key
        elif isinstance(key, (tuple, list)):
            bitstring = "".join(_bit_value_to_char(bit) for bit in key)
        else:
            raise ValueError(f"Unsupported Nexus bit-count key: {key!r}")
        normalized[bitstring] = normalized.get(bitstring, 0) + int(value)
    return _canonical_counts(normalized, variables)


def _collated_key_to_bitstring(key: Any, qubit_count: int) -> str:
    """Normalize Nexus collated-count keys to q0..qN bitstring order."""
    if isinstance(key, str):
        return key

    if not isinstance(key, tuple):
        raise ValueError(f"Unsupported Nexus measurement key: {key!r}")

    # Pytket-style direct counts can also arrive through a generic mapping.
    if all(isinstance(bit, Integral) and not isinstance(bit, bool) for bit in key):
        return "".join(_bit_value_to_char(bit) for bit in key)

    # Nexus may return one named result, e.g. (('result', '011'),).
    if len(key) == 1:
        entry = key[0]
        if isinstance(entry, tuple) and len(entry) == 2:
            return _bitstring_value(entry[1])
        raise ValueError(f"Unsupported Nexus measurement key: {key!r}")

    # Selene can also return one entry per measured qubit:
    # (('q0', '0'), ('q1', '1'), ...).
    if all(isinstance(entry, tuple) and len(entry) == 2 for entry in key):
        named_values = dict(key)
        expected_labels = [f"q{index}" for index in range(qubit_count)]
        if set(named_values) != set(expected_labels) or len(named_values) != len(key):
            raise ValueError(f"Unexpected Nexus measurement labels: {key!r}")
        return "".join(
            _bit_value_to_char(named_values[label]) for label in expected_labels
        )

    raise ValueError(f"Unsupported Nexus measurement key: {key!r}")


def _bit_value_to_char(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, Integral) or value not in (0, 1):
        if value not in ("0", "1"):
            raise ValueError(f"Measurement value must be binary, got {value!r}")
        return value
    return str(int(value))


def _bitstring_value(value: Any) -> str:
    if isinstance(value, str):
        if not value or any(bit not in "01" for bit in value):
            raise ValueError(f"Measurement value must be binary, got {value!r}")
        return value
    if isinstance(value, (tuple, list)):
        return "".join(_bit_value_to_char(bit) for bit in value)
    return _bit_value_to_char(value)


def _as_batch(value: MeasurementBatch | Mapping[str, int]) -> MeasurementBatch:
    if isinstance(value, MeasurementBatch):
        return value
    return MeasurementBatch(counts=value)


def _job_identifier(job: Any | None) -> str:
    """Return a useful Nexus job identifier even for lightweight test doubles."""
    if job is None:
        return "not-submitted"
    for attribute in ("id", "job_id", "name"):
        value = getattr(job, attribute, None)
        if value is not None:
            return str(value)
    return str(job)
