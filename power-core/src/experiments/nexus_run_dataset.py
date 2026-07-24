"""Persist comparable Max-Cut runs executed through the Nexus simulator.

The file written by :class:`NexusRunDataset` is an experiment dataset, not a
generated graph artifact.  Every record keeps the complete instance snapshot,
configuration, QAOA result (including counts), and failures.  The schema
follows ``power-core/docs/spanish/benchmarks/README.md``.
"""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
from math import isfinite
from numbers import Real
import os
import platform
import sys
from pathlib import Path
from typing import Any, Mapping

import networkx as nx

source_root = Path(__file__).resolve().parents[1]
project_root = source_root.parent
for import_root in (str(project_root), str(source_root)):
    if import_root not in sys.path:
        sys.path.insert(0, import_root)

try:
    # Current package layout.
    from optimizer.quantum.qubo import cut_weight
except ImportError:  # pragma: no cover - compatibility with older checkouts
    from optimizer.quantum.qubo_implementation import cut_weight


SCHEMA_VERSION = 1
DATASET_TYPE = "maxcut_nexus_runs"
MIN_QAOA_INITIALIZATIONS = 5


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
    parsed = float(value)
    if not isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if not isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a finite non-negative number")
    return parsed


def _json_copy(value: Any) -> Any:
    """Return a JSON-compatible copy and fail early for non-serializable data."""
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _validate_run_configuration(*, seed: int, layers: int, starts: int, shots: int) -> None:
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if type(layers) is not int or layers < 1:
        raise ValueError("layers must be a positive integer")
    if type(starts) is not int or starts < MIN_QAOA_INITIALIZATIONS:
        raise ValueError(f"starts must be at least {MIN_QAOA_INITIALIZATIONS}")
    if type(shots) is not int or shots < 1:
        raise ValueError("shots must be a positive integer")


def _validate_run_id(run_id: str, runs: list[object]) -> None:
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a non-blank string")
    if any(isinstance(run, Mapping) and run.get("run_id") == run_id for run in runs):
        raise ValueError(f"run_id already exists in this dataset: {run_id!r}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _environment_snapshot() -> dict[str, Any]:
    """Capture versions needed to interpret a run on another machine."""
    packages = {}
    for name in ("qnexus", "guppylang", "selene-sim", "pytket", "numpy", "scipy"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
    }


def build_instance_snapshot(
    graph: nx.Graph,
    *,
    instance_id: str,
    optimal_cut: float | None = None,
) -> dict[str, Any]:
    """Build a canonical instance snapshot and SHA-256 digest.

    The digest covers node IDs, edge endpoints, edge weights, and graph
    provenance.  It therefore prevents comparing runs over subtly different
    weighted graphs under the same human-readable instance name.
    """
    if not isinstance(graph, nx.Graph) or graph.is_directed() or graph.is_multigraph():
        raise ValueError("graph must be a simple undirected networkx.Graph")
    if any(not isinstance(node, str) or not node for node in graph.nodes):
        raise ValueError("graph node IDs must be non-empty strings")
    nodes = sorted(graph.nodes)
    edges = []
    for left, right, data in graph.edges(data=True):
        weight = data.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, Real) or not isfinite(float(weight)):
            raise ValueError(f"edge ({left!r}, {right!r}) must have a finite numeric weight")
        edges.append({"source": min(left, right), "target": max(left, right), "weight": float(weight)})
    edges.sort(key=lambda edge: (edge["source"], edge["target"]))
    provenance = _json_copy(dict(graph.graph)) if graph.graph else {}
    canonical = {"nodes": nodes, "edges": edges, "provenance": provenance}
    digest = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    snapshot: dict[str, Any] = {
        "id": instance_id,
        "digest_sha256": digest,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "provenance": provenance,
    }
    if optimal_cut is not None:
        snapshot["optimal_cut"] = float(optimal_cut)
    return snapshot


class NexusRunDataset:
    """Collect QAOA runs in a versioned JSON dataset.

    ``append_result`` accepts the project's ``QAOAResult`` without importing
    its concrete class, which also makes recording easy in offline tests.
    ``append_failure`` preserves a Nexus/API failure as a first-class record.
    """

    def __init__(self, *, instance: Mapping[str, Any], path: Path | None = None) -> None:
        self.path = path
        self._document: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "dataset_type": DATASET_TYPE,
            "objective": {
                "name": "weighted_max_cut",
                "convention": "maximize_cut_weight",
                "qubo_convention": "minimize_energy = -cut_weight",
                "weight_definition": "summed nominal circuit voltage (kV); not capacity, flow, impedance, or risk",
            },
            "comparison_specification": {
                "source": "power-core/docs/spanish/benchmarks/README.md",
                "minimum_qaoa_initializations": MIN_QAOA_INITIALIZATIONS,
                "approximation_ratio": "cut_value / optimal_cut",
                "failed_runs_are_retained": True,
            },
            "instance": _json_copy(dict(instance)),
            "runs": [],
        }

    @classmethod
    def load(cls, path: Path) -> "NexusRunDataset":
        """Load an existing dataset and validate its top-level identity."""
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            raise ValueError("Nexus dataset must contain a JSON object")
        if document.get("schema_version") != SCHEMA_VERSION or document.get("dataset_type") != DATASET_TYPE:
            raise ValueError("Unsupported or non-Nexus Max-Cut dataset")
        if not isinstance(document.get("runs"), list):
            raise ValueError("Dataset runs must be a list")
        instance = document.get("instance")
        if not isinstance(instance, Mapping) or not isinstance(instance.get("digest_sha256"), str):
            raise ValueError("Dataset instance must include digest_sha256")
        dataset = cls(instance=document["instance"], path=path)
        dataset._document = document
        return dataset

    @classmethod
    def load_or_create(cls, *, instance: Mapping[str, Any], path: Path) -> "NexusRunDataset":
        """Open one dataset without mixing runs from different instances."""
        if not path.exists():
            return cls(instance=instance, path=path)
        dataset = cls.load(path)
        expected = instance.get("digest_sha256")
        actual = dataset.document["instance"].get("digest_sha256")
        if actual != expected:
            raise ValueError(
                "Existing Nexus dataset belongs to a different instance; choose another output path"
            )
        return dataset

    @property
    def document(self) -> Mapping[str, Any]:
        """Return the current JSON-compatible dataset document."""
        return self._document

    def append_result(
        self,
        result: Any,
        *,
        graph: nx.Graph,
        seed: int,
        layers: int,
        starts: int,
        shots: int,
        run_id: str,
        optimal_cut: float | None = None,
        configuration: Mapping[str, Any] | None = None,
        recorded_at_utc: str | None = None,
    ) -> dict[str, Any]:
        """Append one successful or non-converged QAOA result."""
        _validate_run_configuration(seed=seed, layers=layers, starts=starts, shots=shots)
        _validate_run_id(run_id, self._document["runs"])
        self._validate_graph(graph)
        if optimal_cut is not None and float(optimal_cut) == 0:
            ratio = None
        else:
            ratio = None if optimal_cut is None else _cut_value(graph, result) / float(optimal_cut)
        partition = _partition_from_result(result)
        cut_value = _cut_value(graph, result)
        metadata = dict(getattr(result, "metadata", {}) or {})
        initializations = metadata.get("starts")
        record = {
            "run_id": run_id,
            "recorded_at_utc": recorded_at_utc or _utc_now(),
            "instance_digest_sha256": self._document["instance"]["digest_sha256"],
            "environment": _environment_snapshot(),
            "solver": {
                "id": "qaoa",
                "backend": getattr(result, "backend", "quantinuum-nexus"),
                "layers_p": layers,
                "starts": starts,
                "initializations": initializations,
                "shots": shots,
                "seed": seed,
                "configuration": _json_copy(dict(configuration or {})),
            },
            "result": {
                "status": "succeeded" if bool(getattr(result, "optimizer_success", False)) else "not_converged",
                "optimizer_success": bool(getattr(result, "optimizer_success", False)),
                "optimizer_status": getattr(result, "optimizer_status", "unknown"),
                "objective_evaluations": getattr(result, "objective_evaluations", None),
                "bitstring": getattr(result, "bitstring", None),
                "partition": partition,
                "cut_value": cut_value,
                "optimal_cut": optimal_cut,
                "approximation_ratio": ratio,
                "ising_energy": getattr(result, "energy", None),
                "gamma": list(getattr(result, "gamma", ()) or ()),
                "beta": list(getattr(result, "beta", ()) or ()),
                "counts": dict(getattr(result, "counts", {}) or {}),
                "probabilities": dict(getattr(result, "probabilities", {}) or {}),
                "energies": dict(getattr(result, "energies", {}) or {}),
                "metadata": _json_copy(metadata),
            },
        }
        self._document["runs"].append(_json_copy(record))
        return record

    def append_failure(
        self,
        *,
        run_id: str,
        seed: int,
        layers: int,
        starts: int,
        shots: int,
        error: BaseException | str,
        configuration: Mapping[str, Any] | None = None,
        recorded_at_utc: str | None = None,
    ) -> dict[str, Any]:
        """Append a failed Nexus/QAOA attempt without fabricating a result."""
        _validate_run_configuration(seed=seed, layers=layers, starts=starts, shots=shots)
        _validate_run_id(run_id, self._document["runs"])
        record = {
            "run_id": run_id,
            "recorded_at_utc": recorded_at_utc or _utc_now(),
            "instance_digest_sha256": self._document["instance"]["digest_sha256"],
            "environment": _environment_snapshot(),
            "solver": {"id": "qaoa", "backend": "quantinuum-nexus", "layers_p": layers, "starts": starts, "shots": shots, "seed": seed, "configuration": _json_copy(dict(configuration or {}))},
            "result": {"status": "failed", "optimizer_success": False},
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        self._document["runs"].append(_json_copy(record))
        return record

    def _validate_graph(self, graph: nx.Graph) -> None:
        current = build_instance_snapshot(
            graph,
            instance_id=str(self._document["instance"].get("id", "instance")),
        )
        expected = self._document["instance"].get("digest_sha256")
        if current["digest_sha256"] != expected:
            raise ValueError(
                "graph digest does not match the dataset instance; refusing to mix runs"
            )

    def save(self, path: Path | None = None) -> Path:
        """Write the dataset atomically and return its path."""
        target = path or self.path
        if target is None:
            raise ValueError("A dataset path is required")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(json.dumps(self._document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(target)
        self.path = target
        return target


@contextmanager
def _exclusive_output_lock(path: Path):
    """Serialize CLI writers for one output file across supported platforms."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            lock_file.write(b"0")
            lock_file.flush()
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _partition_from_result(result: Any) -> dict[str, int]:
    spins = getattr(result, "spins", None)
    if spins:
        return {str(node): (1 - int(value)) // 2 for node, value in sorted(spins.items())}
    bitstring = getattr(result, "bitstring", None)
    if not bitstring:
        return {}
    variables = getattr(result, "metadata", {}).get("variables", [])
    return {str(node): int(bit) for node, bit in zip(variables, bitstring, strict=True)}


def _cut_value(graph: nx.Graph, result: Any) -> float:
    partition = _partition_from_result(result)
    if set(partition) != set(graph.nodes):
        raise ValueError("QAOA result does not contain a complete graph partition")
    return cut_weight(graph, partition)


def _load_instance(path: Path) -> tuple[nx.Graph, dict[str, Any]]:
    """Load the repository's regional JSON artifact as a weighted graph."""
    document = json.loads(path.read_text(encoding="utf-8"))
    graph = nx.Graph()
    graph.add_nodes_from(node["id"] for node in document["nodes"])
    graph.add_weighted_edges_from(
        (edge["source"], edge["target"], edge["weight"])
        for edge in document["edges"]
    )
    graph.graph.update({key: value for key, value in document.items() if key not in {"nodes", "edges"}})
    return graph, document


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate arguments before any Nexus authentication occurs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instance",
        type=Path,
        default=Path("power-core/artifacts/regional_instance.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("power-core/artifacts/nexus_maxcut_runs.json"),
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=_non_negative_int, required=True)
    parser.add_argument("--layers", type=_positive_int, default=1)
    parser.add_argument("--starts", type=_positive_int, default=5)
    parser.add_argument("--shots", type=_positive_int, default=1024)
    parser.add_argument("--max-parallel-starts", type=_positive_int, default=5)
    parser.add_argument(
        "--optimal-cut",
        type=_non_negative_float,
        default=None,
        help="Exact OPT used for the approximation ratio; omit to leave ratio null.",
    )
    parser.add_argument("--project", default="Quantum Power QAOA")
    parser.add_argument("--timeout", type=_positive_float, default=3600.0)
    parser.add_argument("--max-cost", type=_non_negative_float, default=10.0)
    args = parser.parse_args(argv)
    if args.starts < MIN_QAOA_INITIALIZATIONS:
        parser.error(f"--starts must be at least {MIN_QAOA_INITIALIZATIONS}")
    return args


def main() -> None:
    """Execute QAOA on Nexus and append the attempt to a JSON dataset."""
    args = parse_args()

    graph, artifact = _load_instance(args.instance)
    instance = build_instance_snapshot(
        graph,
        instance_id=str(artifact.get("source", args.instance.stem)),
        optimal_cut=args.optimal_cut,
    )
    configuration = {
        "instance_path": str(args.instance),
        "max_parallel_starts": args.max_parallel_starts,
        "project_name": args.project,
        "timeout_seconds": args.timeout,
        "max_cost": args.max_cost,
    }

    with _exclusive_output_lock(args.output):
        dataset = NexusRunDataset.load_or_create(instance=instance, path=args.output)
        try:
            import qnexus as qnx
            from optimizer.quantum import IsingModel, NexusBackend, QAOA
            from optimizer.quantum.qubo_implementation import build_max_cut_qubo

            qnx.login()
            project = qnx.projects.get_or_create(name=args.project)
            qnx.context.set_active_project(project)
            if not qnx.quotas.check_quota(name="simulation"):
                raise RuntimeError("No simulation quota available")
            qubo = build_max_cut_qubo(graph)
            ising = IsingModel.from_qubo(qubo)
            backend = NexusBackend(
                qnx,
                project=project,
                timeout=args.timeout,
                max_cost=args.max_cost,
            )
            result = QAOA(
                layers=args.layers,
                starts=args.starts,
                seed=args.seed,
                max_parallel_starts=args.max_parallel_starts,
            ).run_cloud(ising, session=qnx, backend=backend, shots=args.shots)
        except Exception as error:
            dataset.append_failure(
                run_id=args.run_id,
                seed=args.seed,
                layers=args.layers,
                starts=args.starts,
                shots=args.shots,
                error=error,
                configuration=configuration,
            )
            dataset.save()
            raise
        else:
            dataset.append_result(
                result,
                graph=graph,
                seed=args.seed,
                layers=args.layers,
                starts=args.starts,
                shots=args.shots,
                run_id=args.run_id,
                optimal_cut=args.optimal_cut,
                configuration=configuration,
            )
            output = dataset.save()
            print(f"Recorded Nexus run {args.run_id!r} in {output}")


if __name__ == "__main__":
    main()
