"""Submit one fixed-parameter QAOA circuit to the Nexus Selene simulator.

This is deliberately a small inspection utility.  It builds its own
three-node weighted Max-Cut circuit and submits exactly one job; it does not
import or invoke the repository's QAOA optimizer.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
from math import isfinite
from numbers import Integral
from typing import Any
from uuid import uuid4


NODES = ("A", "B", "C")
EDGES = ((0, 1, 1.0), (1, 2, 1.0), (0, 2, 1.0))


def _bit(value: Any) -> str:
    """Return one validated measurement bit as text."""
    if isinstance(value, bool):
        raise ValueError(f"Measurement value must be 0 or 1, got {value!r}")
    if isinstance(value, Integral) and value in (0, 1):
        return str(int(value))
    if value in ("0", "1"):
        return str(value)
    raise ValueError(f"Measurement value must be 0 or 1, got {value!r}")


def _named_key_to_bitstring(key: Any, qubits: int) -> str:
    """Convert a Nexus ``collated_counts`` key to q0..qN order."""
    if isinstance(key, str):
        return key
    if isinstance(key, tuple) and all(
        isinstance(item, Integral) and not isinstance(item, bool) for item in key
    ):
        return "".join(_bit(item) for item in key)
    if isinstance(key, tuple) and len(key) == 1:
        tag = key[0]
        if isinstance(tag, tuple) and len(tag) == 2:
            value = tag[1]
            if isinstance(value, str):
                return value
            if isinstance(value, (tuple, list)):
                return "".join(_bit(item) for item in value)
            return _bit(value)
    if isinstance(key, tuple) and all(
        isinstance(item, tuple) and len(item) == 2 for item in key
    ):
        named = dict(key)
        labels = [f"q{index}" for index in range(qubits)]
        if set(named) == set(labels) and len(named) == len(key):
            return "".join(_bit(named[label]) for label in labels)
    raise ValueError(f"Unsupported Nexus collated-count key: {key!r}")


def _validate_counts(counts: Mapping[Any, Any], qubits: int) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, count in counts.items():
        if isinstance(count, bool) or not isinstance(count, Integral) or count < 0:
            raise ValueError(f"Invalid measurement count for {key!r}: {count!r}")
        if isinstance(key, (tuple, list)) and all(
            isinstance(bit, Integral) and not isinstance(bit, bool) for bit in key
        ):
            bitstring = "".join(_bit(bit) for bit in key)
        else:
            bitstring = _named_key_to_bitstring(key, qubits)
        if len(bitstring) != qubits or any(bit not in "01" for bit in bitstring):
            raise ValueError(f"Invalid {qubits}-qubit bitstring: {bitstring!r}")
        normalized[bitstring] = normalized.get(bitstring, 0) + int(count)
    if not normalized or sum(normalized.values()) == 0:
        raise ValueError("Nexus returned no measured shots")
    return dict(sorted(normalized.items()))


def normalize_result_counts(result: Any, *, qubits: int = len(NODES)) -> dict[str, int]:
    """Normalize the two result shapes returned by Nexus 0.45.0."""
    collated_counts = getattr(result, "collated_counts", None)
    if callable(collated_counts):
        counts = collated_counts()
        if not isinstance(counts, Mapping):
            raise ValueError("QsysResult.collated_counts() did not return a mapping")
        return _validate_counts(counts, qubits)

    get_counts = getattr(result, "get_counts", None)
    if callable(get_counts):
        counts = get_counts()
        if not isinstance(counts, Mapping):
            raise ValueError("BackendResult.get_counts() did not return a mapping")
        return _validate_counts(counts, qubits)

    raise TypeError(f"Unsupported Nexus result type: {type(result).__name__}")


def _json_safe_raw_counts(result: Any) -> list[dict[str, Any]]:
    """Expose raw count keys without losing Nexus' tuple structure."""
    method = getattr(result, "collated_counts", None)
    if not callable(method):
        method = getattr(result, "get_counts", None)
    if not callable(method):
        return []
    raw_counts = method()
    if not isinstance(raw_counts, Mapping):
        return []
    return [{"key_repr": repr(key), "count": count} for key, count in raw_counts.items()]


def build_program(*, gamma: float, beta: float) -> Any:
    """Build one p=1 QAOA circuit for the fixed weighted triangle."""
    try:
        from guppylang import guppy
        from guppylang.std.angles import angle
        from guppylang.std.builtins import result
        from guppylang.std.quantum import cx, h, measure, qubit, rx, rz
    except ImportError as error:
        raise RuntimeError("Install Guppy and Selene in .venv before running this script") from error

    def half_turns(value: float) -> str:
        return f"angle({value / 3.141592653589793!r})"

    lines = ["def main() -> None:"]
    lines.extend(f"    q{index} = qubit()" for index in range(len(NODES)))
    lines.extend(f"    h(q{index})" for index in range(len(NODES)))
    for left, right, weight in EDGES:
        # For -Max-Cut, the non-constant Ising term is +(weight / 2) Z_i Z_j.
        lines.extend((
            f"    cx(q{left}, q{right})",
            f"    rz(q{right}, {half_turns(gamma * weight / 2.0)})",
            f"    cx(q{left}, q{right})",
        ))
    lines.extend(f"    rx(q{index}, {half_turns(beta)})" for index in range(len(NODES)))
    lines.extend(f'    result("q{index}", measure(q{index}))' for index in range(len(NODES)))

    namespace = {
        "angle": angle, "cx": cx, "h": h, "measure": measure,
        "qubit": qubit, "result": result, "rx": rx, "rz": rz,
    }
    source = "\n".join(lines) + "\n"
    import linecache

    filename = "<single-nexus-qaoa>"
    linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
    exec(compile(source, filename, "exec"), namespace)
    return guppy(namespace["main"])


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    """Submit exactly one Nexus execution and return an inspection document."""
    try:
        import qnexus as qnx
    except ImportError as error:
        raise RuntimeError("Install qnexus in .venv before running this script") from error

    qnx.login()
    if not qnx.quotas.check_quota(name="simulation"):
        raise RuntimeError("No Nexus simulation quota is available")
    project = qnx.projects.get_or_create(name=args.project)
    qnx.context.set_active_project(project)
    program = build_program(gamma=args.gamma, beta=args.beta)
    package_name = f"single-qaoa-triangle-{uuid4().hex}"
    hugr_ref = qnx.hugr.upload(hugr_package=program.compile(), name=package_name, project=project)
    job = qnx.start_execute_job(
        programs=[hugr_ref], n_shots=[args.shots],
        backend_config=qnx.models.SeleneConfig(
            n_qubits=len(NODES), simulator=qnx.models.StatevectorSimulator(seed=args.seed)
        ),
        name=f"single-qaoa-triangle-{uuid4().hex}", project=project,
        max_cost=args.max_cost,
    )
    status = qnx.jobs.wait_for(job, timeout=args.timeout)
    results = qnx.jobs.results(job)
    if not results:
        raise RuntimeError(f"Nexus returned no results for job {job.id}")
    result = results[0].download_result()
    counts = normalize_result_counts(result)
    best_bitstring = max(counts, key=lambda bits: (counts[bits], bits))
    return {
        "job_id": str(job.id), "job_status": str(status),
        "result_type": f"{type(result).__module__}.{type(result).__qualname__}",
        "raw_counts": _json_safe_raw_counts(result), "counts": counts,
        "total_shots": sum(counts.values()), "most_frequent_bitstring": best_bitstring,
        "configuration": {
            "nodes": NODES, "edges": EDGES, "layers": 1, "gamma": args.gamma,
            "beta": args.beta, "shots": args.shots, "seed": args.seed,
            "seed_note": "Passed to Nexus 0.45.0 StatevectorSimulator.",
        },
    }


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not isfinite(parsed):
        raise argparse.ArgumentTypeError("must be finite")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def _positive_float(value: str) -> float:
    parsed = _finite_float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = _finite_float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gamma", type=_finite_float, default=0.8)
    parser.add_argument("--beta", type=_finite_float, default=0.4)
    parser.add_argument("--shots", type=_positive_int, default=100)
    parser.add_argument("--seed", type=_non_negative_int, default=7)
    parser.add_argument("--project", default="Quantum Power QAOA")
    parser.add_argument("--timeout", type=_positive_float, default=600.0)
    parser.add_argument("--max-cost", type=_non_negative_float, default=1.0)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    print(json.dumps(run_once(args), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
