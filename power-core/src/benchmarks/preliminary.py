"""Reproducible preliminary local benchmark for Challenge 1 weighted Max-Cut.

Run from the repository root with::

    python power-core/src/benchmarks/preliminary.py

This experiment performs one independent QAOA run per depth.  The default five
parameter trials are candidates inside that one run, not five independent runs.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata as importlib_metadata
from itertools import product
import json
from math import isfinite, pi
from numbers import Real
from pathlib import Path
import platform
import random
import sys
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence


POWER_CORE_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = POWER_CORE_ROOT.parent
if __package__ in {None, ""}:  # Support direct execution from the repository root.
    sys.path.insert(0, str(POWER_CORE_ROOT))

import networkx as nx  # noqa: E402

from src.optimizer.greedy import solve_greedy  # noqa: E402
from src.optimizer.quantum.ising import IsingModel  # noqa: E402
from src.optimizer.quantum.qaoa import (  # noqa: E402
    MeasurementBatch,
    QAOABackend,
    QAOAProgram,
)
from src.optimizer.quantum.qaoa.backends import LocalGuppySeleneBackend  # noqa: E402
from src.optimizer.random_approximation.goemans_williamson import (  # noqa: E402
    solve_goemans_williamson,
)


SCHEMA_VERSION = 1
DEFAULT_INPUT = POWER_CORE_ROOT / "artifacts" / "regional_instance.json"
DEFAULT_OUTPUT_DIR = POWER_CORE_ROOT / "artifacts" / "preliminary_local_benchmark"
DEFAULT_DEPTHS = (1, 2, 3)
DEFAULT_PARAMETER_CANDIDATES = 5
DEFAULT_SEARCH_SHOTS = 128
DEFAULT_FINAL_SHOTS = 1024
DEFAULT_SEED = 1729
DEFAULT_GW_ROUNDS = 128
BETA_MIN = 0.0
BETA_MAX = pi / 2.0
GAMMA_RANGE_FORMULA = (
    "gamma_l ~ Uniform(0, pi / max_abs_J), where max_abs_J = "
    "max_(i,j) |J_ij|; if max_abs_J = 0, gamma_l = 0"
)
BETA_RANGE_FORMULA = "beta_l ~ Uniform(0, pi / 2)"


class BenchmarkInputError(ValueError):
    """Raised when the benchmark input does not satisfy the graph contract."""


class BenchmarkConfigurationError(ValueError):
    """Raised when an experimental configuration is invalid."""


class BenchmarkConfig:
    """Validated immutable-in-practice benchmark configuration."""

    def __init__(
        self,
        *,
        depths: Sequence[int] = DEFAULT_DEPTHS,
        parameter_candidates: int = DEFAULT_PARAMETER_CANDIDATES,
        search_shots: int = DEFAULT_SEARCH_SHOTS,
        final_shots: int = DEFAULT_FINAL_SHOTS,
        seed: int = DEFAULT_SEED,
        gw_rounds: int = DEFAULT_GW_ROUNDS,
    ) -> None:
        normalized_depths = tuple(depths)
        if not normalized_depths:
            raise BenchmarkConfigurationError("depths must not be empty")
        if any(type(depth) is not int or depth <= 0 for depth in normalized_depths):
            raise BenchmarkConfigurationError("every depth must be a positive integer")
        if len(set(normalized_depths)) != len(normalized_depths):
            raise BenchmarkConfigurationError("depths must not contain duplicates")
        for name, value in (
            ("parameter_candidates", parameter_candidates),
            ("search_shots", search_shots),
            ("final_shots", final_shots),
            ("gw_rounds", gw_rounds),
        ):
            if type(value) is not int or value <= 0:
                raise BenchmarkConfigurationError(f"{name} must be a positive integer")
        if type(seed) is not int:
            raise BenchmarkConfigurationError("seed must be an integer")

        self.depths = normalized_depths
        self.parameter_candidates = parameter_candidates
        self.search_shots = search_shots
        self.final_shots = final_shots
        self.seed = seed
        self.gw_rounds = gw_rounds

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible snapshot using unambiguous trial terminology."""

        return {
            "depths": list(self.depths),
            "parameter_candidates_per_run": self.parameter_candidates,
            "parameter_trials": self.parameter_candidates,
            "independent_runs_per_configuration": 1,
            "search_shots_per_candidate": self.search_shots,
            "final_shots": self.final_shots,
            "base_seed": self.seed,
            "gw_rounds": self.gw_rounds,
        }


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def load_instance(path: Path) -> tuple[nx.Graph, dict[str, Any], dict[str, Any]]:
    """Load and validate one JSON regional instance, preserving its digest."""

    input_path = Path(path)
    try:
        raw = input_path.read_bytes()
    except OSError as error:
        raise BenchmarkInputError(f"cannot read input {input_path}: {error}") from error
    digest = hashlib.sha256(raw).hexdigest()
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BenchmarkInputError(f"input is not valid UTF-8 JSON: {error}") from error
    if not isinstance(artifact, dict):
        raise BenchmarkInputError("input root must be a JSON object")

    raw_nodes = artifact.get("nodes")
    raw_edges = artifact.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise BenchmarkInputError("input requires nodes and edges arrays")

    graph = nx.Graph()
    node_ids: list[str] = []
    for index, node in enumerate(raw_nodes):
        if not isinstance(node, dict):
            raise BenchmarkInputError(f"nodes[{index}] must be an object")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise BenchmarkInputError(f"nodes[{index}].id must be a non-empty string")
        if node_id in graph:
            raise BenchmarkInputError(f"duplicate node id: {node_id!r}")
        graph.add_node(node_id)
        node_ids.append(node_id)

    seen_edges: set[tuple[str, str]] = set()
    for index, edge in enumerate(raw_edges):
        if not isinstance(edge, dict):
            raise BenchmarkInputError(f"edges[{index}] must be an object")
        source = edge.get("source")
        target = edge.get("target")
        weight = edge.get("weight")
        if (
            not isinstance(source, str)
            or not isinstance(target, str)
            or source not in graph
            or target not in graph
        ):
            raise BenchmarkInputError(f"edges[{index}] references an unknown node")
        if source == target:
            raise BenchmarkInputError(f"edges[{index}] is a self-loop")
        if (
            isinstance(weight, bool)
            or not isinstance(weight, Real)
            or not isfinite(float(weight))
            or float(weight) < 0.0
        ):
            raise BenchmarkInputError(
                f"edges[{index}].weight must be finite and non-negative"
            )
        key: tuple[str, str] = (
            (source, target) if source < target else (target, source)
        )
        if key in seen_edges:
            raise BenchmarkInputError(f"duplicate undirected edge: {key!r}")
        seen_edges.add(key)
        graph.add_edge(source, target, weight=float(weight))

    input_info = {
        "path": _display_path(input_path),
        "sha256": digest,
        "schema_version": artifact.get("schema_version"),
        "source": artifact.get("source"),
        "edge_model": artifact.get("edge_model"),
        "weight_model": artifact.get("weight_model"),
        "weight_units": artifact.get("weight_units"),
        "weight_definition": artifact.get("weight_definition"),
        "limitations": artifact.get("limitations", []),
        "node_count": len(node_ids),
        "edge_count": len(raw_edges),
    }
    return graph, artifact, input_info


def build_max_cut_ising(graph: nx.Graph) -> IsingModel:
    """Build the minimization Ising Hamiltonian ``H(z) = -cut(z)``.

    For an edge of weight ``w``, ``-cut = -w/2 + (w/2) z_i z_j``.
    Thus ``offset = -sum(w)/2``, ``h_i = 0``, and ``J_ij = w/2``.
    """

    variables = tuple(sorted(graph.nodes))
    if any(not isinstance(node, str) or not node for node in variables):
        raise BenchmarkInputError("graph node IDs must be non-empty strings")
    total_weight = 0.0
    quadratic: dict[tuple[str, str], float] = {}
    for left, right, data in graph.edges(data=True):
        weight = data.get("weight")
        if (
            left == right
            or isinstance(weight, bool)
            or not isinstance(weight, Real)
            or not isfinite(float(weight))
            or float(weight) < 0.0
        ):
            raise BenchmarkInputError("graph contains an invalid weighted edge")
        key = tuple(sorted((left, right)))
        value = float(weight)
        total_weight += value
        quadratic[key] = value / 2.0
    return IsingModel(
        variables=variables,
        offset=-total_weight / 2.0,
        linear={variable: 0.0 for variable in variables},
        quadratic=quadratic,
    )


def make_qaoa_program(model: IsingModel, depth: int) -> QAOAProgram:
    """Create the backend-neutral program evaluated by this benchmark."""

    return QAOAProgram(
        variables=model.variables,
        offset=float(model.offset),
        linear=tuple((name, float(model.linear[name])) for name in model.variables),
        quadratic=tuple(
            (left, right, float(value))
            for (left, right), value in sorted(model.quadratic.items())
        ),
        layers=depth,
    )


def _cut_from_bitstring(graph: nx.Graph, variables: Sequence[str], bits: str) -> float:
    labels = dict(zip(variables, bits, strict=True))
    return float(
        sum(
            float(data["weight"])
            for left, right, data in graph.edges(data=True)
            if labels[left] != labels[right]
        )
    )


def exact_max_cut(graph: nx.Graph) -> dict[str, Any]:
    """Compute a deterministic exact weighted Max-Cut by exhaustive search.

    Complementary cuts are equivalent, so the first sorted node is fixed to bit
    zero.  This evaluates ``2**(n-1)`` assignments for non-empty graphs.
    """

    started = perf_counter()
    variables = tuple(sorted(graph.nodes))
    if not variables:
        candidates = ("",)
    else:
        candidates = (
            "0" + "".join(str(bit) for bit in tail)
            for tail in product((0, 1), repeat=len(variables) - 1)
        )

    best_bits: str | None = None
    best_cut = float("-inf")
    evaluated = 0
    for bits in candidates:
        evaluated += 1
        value = _cut_from_bitstring(graph, variables, bits)
        if value > best_cut or (value == best_cut and (best_bits is None or bits < best_bits)):
            best_cut = value
            best_bits = bits
    assert best_bits is not None
    elapsed = perf_counter() - started
    return {
        "method": "exhaustive_search_with_complement_symmetry",
        "status": "completed",
        "cut": float(best_cut),
        "ratio": None if best_cut == 0.0 else 1.0,
        "bitstring": best_bits,
        "partition_zero": [
            node for node, bit in zip(variables, best_bits, strict=True) if bit == "0"
        ],
        "partition_one": [
            node for node, bit in zip(variables, best_bits, strict=True) if bit == "1"
        ],
        "assignments_evaluated": evaluated,
        "time_seconds": round(elapsed, 6),
    }


def metrics_from_counts(
    graph: nx.Graph,
    model: IsingModel,
    counts: Mapping[str, int],
) -> dict[str, Any]:
    """Compute expected/best energy and cut metrics from positive counts only."""

    normalized: dict[str, int] = {}
    expected_length = len(model.variables)
    for bitstring, count in counts.items():
        if not isinstance(bitstring, str) or len(bitstring) != expected_length or any(
            bit not in "01" for bit in bitstring
        ):
            raise ValueError(f"invalid measurement bitstring: {bitstring!r}")
        if type(count) is not int or count < 0:
            raise ValueError("measurement counts must be non-negative integers")
        if count > 0:
            normalized[bitstring] = normalized.get(bitstring, 0) + count
    normalized = dict(sorted(normalized.items()))
    shots = sum(normalized.values())
    if shots <= 0:
        raise ValueError("backend returned no positive-count measurement states")

    state_metrics: dict[str, dict[str, float | int]] = {}
    weighted_cut = 0.0
    weighted_energy = 0.0
    for bitstring, count in normalized.items():
        spins = {
            variable: 1 - 2 * int(bit)
            for variable, bit in zip(model.variables, bitstring, strict=True)
        }
        energy = float(model.energy(spins))
        cut = _cut_from_bitstring(graph, model.variables, bitstring)
        if abs(energy + cut) > 1e-8:
            raise ValueError(
                f"Ising/Max-Cut convention mismatch for state {bitstring!r}"
            )
        state_metrics[bitstring] = {"count": count, "energy": energy, "cut": cut}
        weighted_cut += count * cut
        weighted_energy += count * energy

    best_bitstring = min(
        normalized,
        key=lambda bits: (-float(state_metrics[bits]["cut"]), bits),
    )
    return {
        "shots_observed": shots,
        "counts": normalized,
        "state_metrics": state_metrics,
        "expected_energy": weighted_energy / shots,
        "expected_cut": weighted_cut / shots,
        "best_sample_bitstring": best_bitstring,
        "best_sample_energy": float(state_metrics[best_bitstring]["energy"]),
        "best_sample_cut": float(state_metrics[best_bitstring]["cut"]),
    }


def _ratio(value: float | None, optimum: float) -> float | None:
    if value is None or optimum == 0.0:
        return None
    return float(value) / optimum


def _error_record(error: Exception) -> dict[str, str]:
    return {"type": type(error).__name__, "message": str(error)}


def _seed_plan(base_seed: int, depth: int, candidates: int) -> dict[str, Any]:
    candidate_base = base_seed + depth * 100_000
    return {
        "parameter_generation": base_seed + depth * 1_000,
        "candidate_execution": [candidate_base + index for index in range(candidates)],
        "final_sampling": candidate_base + candidates,
    }


def _batch_parts(batch: MeasurementBatch | Mapping[str, int]) -> tuple[Mapping[str, int], Any]:
    if isinstance(batch, Mapping):
        return batch, {}
    counts = getattr(batch, "counts", None)
    if not isinstance(counts, Mapping):
        raise TypeError("backend.execute must return MeasurementBatch or a counts mapping")
    return counts, getattr(batch, "metadata", {})


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return repr(value)


def _failed_depth_record(
    *,
    depth: int,
    backend_name: str,
    config: BenchmarkConfig,
    seeds: Mapping[str, Any],
    gamma_max: float,
    candidates: list[dict[str, Any]],
    started: float,
    error: Exception,
    selected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "p": depth,
        "status": "failed",
        "preliminary": True,
        "backend": backend_name,
        "independent_runs": 1,
        "parameter_candidates_requested": config.parameter_candidates,
        "parameter_candidates_completed": sum(
            candidate["status"] == "completed" for candidate in candidates
        ),
        "search_shots_per_candidate": config.search_shots,
        "final_shots_requested": config.final_shots,
        "gamma_range": [0.0, gamma_max],
        "beta_range": [BETA_MIN, BETA_MAX],
        "seeds": dict(seeds),
        "candidates": candidates,
        "expected_energy": None,
        "expected_cut": None,
        "best_sample_cut": None,
        "expected_ratio": None,
        "best_sample_ratio": None,
        "counts": {},
        "error": _error_record(error),
        "timings_seconds": {"total": round(perf_counter() - started, 6)},
    }
    if selected is not None:
        record["selected_candidate_index"] = selected["index"]
        record["parameters"] = selected["parameters"]
    return record


def _run_qaoa_depth(
    graph: nx.Graph,
    model: IsingModel,
    optimum: float,
    *,
    depth: int,
    config: BenchmarkConfig,
    backend: QAOABackend,
) -> dict[str, Any]:
    started = perf_counter()
    backend_name = str(getattr(backend, "name", type(backend).__name__))
    program = make_qaoa_program(model, depth)
    max_abs_j = max((abs(float(value)) for value in model.quadratic.values()), default=0.0)
    gamma_max = 0.0 if max_abs_j == 0.0 else pi / max_abs_j
    seeds = _seed_plan(config.seed, depth, config.parameter_candidates)
    rng = random.Random(seeds["parameter_generation"])
    candidates: list[dict[str, Any]] = []

    search_started = perf_counter()
    for index, execution_seed in enumerate(seeds["candidate_execution"]):
        gamma = tuple(rng.uniform(0.0, gamma_max) for _ in range(depth))
        beta = tuple(rng.uniform(BETA_MIN, BETA_MAX) for _ in range(depth))
        candidate_started = perf_counter()
        parameters = {"gamma": list(gamma), "beta": list(beta)}
        try:
            batch = backend.execute(
                program,
                gamma,
                beta,
                shots=config.search_shots,
                seed=execution_seed,
            )
            raw_counts, batch_metadata = _batch_parts(batch)
            metrics = metrics_from_counts(graph, model, raw_counts)
            if metrics["shots_observed"] != config.search_shots:
                raise ValueError(
                    "backend returned "
                    f"{metrics['shots_observed']} shots; expected {config.search_shots}"
                )
            candidates.append(
                {
                    "index": index,
                    "status": "completed",
                    "seed": execution_seed,
                    "shots": config.search_shots,
                    "parameters": parameters,
                    "expected_energy": metrics["expected_energy"],
                    "expected_cut": metrics["expected_cut"],
                    "best_sample_cut": metrics["best_sample_cut"],
                    "counts": metrics["counts"],
                    "backend_metadata": _json_safe(batch_metadata),
                    "time_seconds": round(perf_counter() - candidate_started, 6),
                }
            )
        except Exception as error:  # Preserve failed candidates without aborting the depth.
            candidates.append(
                {
                    "index": index,
                    "status": "failed",
                    "seed": execution_seed,
                    "shots": config.search_shots,
                    "parameters": parameters,
                    "error": _error_record(error),
                    "time_seconds": round(perf_counter() - candidate_started, 6),
                }
            )
    search_elapsed = perf_counter() - search_started

    successful = [candidate for candidate in candidates if candidate["status"] == "completed"]
    if not successful:
        return _failed_depth_record(
            depth=depth,
            backend_name=backend_name,
            config=config,
            seeds=seeds,
            gamma_max=gamma_max,
            candidates=candidates,
            started=started,
            error=RuntimeError("all parameter candidates failed"),
        )
    selected = max(
        successful,
        key=lambda candidate: (float(candidate["expected_cut"]), -int(candidate["index"])),
    )

    final_started = perf_counter()
    try:
        parameters = selected["parameters"]
        batch = backend.execute(
            program,
            parameters["gamma"],
            parameters["beta"],
            shots=config.final_shots,
            seed=seeds["final_sampling"],
        )
        raw_counts, batch_metadata = _batch_parts(batch)
        metrics = metrics_from_counts(graph, model, raw_counts)
        if metrics["shots_observed"] != config.final_shots:
            raise ValueError(
                f"backend returned {metrics['shots_observed']} shots; "
                f"expected {config.final_shots}"
            )
    except Exception as error:
        return _failed_depth_record(
            depth=depth,
            backend_name=backend_name,
            config=config,
            seeds=seeds,
            gamma_max=gamma_max,
            candidates=candidates,
            started=started,
            error=error,
            selected=selected,
        )
    final_elapsed = perf_counter() - final_started

    candidate_failures = sum(candidate["status"] == "failed" for candidate in candidates)
    return {
        "p": depth,
        "status": (
            "completed" if candidate_failures == 0 else "completed_with_candidate_failures"
        ),
        "preliminary": True,
        "backend": backend_name,
        "independent_runs": 1,
        "parameter_candidates_requested": config.parameter_candidates,
        "parameter_candidates_completed": len(successful),
        "selection_rule": "maximum search expected_cut; ties use lowest candidate index",
        "search_shots_per_candidate": config.search_shots,
        "final_shots_requested": config.final_shots,
        "shots_observed": metrics["shots_observed"],
        "gamma_range": [0.0, gamma_max],
        "beta_range": [BETA_MIN, BETA_MAX],
        "seeds": seeds,
        "selected_candidate_index": selected["index"],
        "parameters": selected["parameters"],
        "search_expected_cut": selected["expected_cut"],
        "expected_energy": metrics["expected_energy"],
        "expected_cut": metrics["expected_cut"],
        "best_sample_bitstring": metrics["best_sample_bitstring"],
        "best_sample_cut": metrics["best_sample_cut"],
        "expected_ratio": _ratio(float(metrics["expected_cut"]), optimum),
        "best_sample_ratio": _ratio(float(metrics["best_sample_cut"]), optimum),
        "counts": metrics["counts"],
        "state_metrics": metrics["state_metrics"],
        "backend_metadata": _json_safe(batch_metadata),
        "candidates": candidates,
        "error": None,
        "timings_seconds": {
            "parameter_search": round(search_elapsed, 6),
            "final_sampling": round(final_elapsed, 6),
            "total": round(perf_counter() - started, 6),
        },
    }


def _software_versions() -> dict[str, str | None]:
    packages = (
        "networkx",
        "numpy",
        "scipy",
        "cvxpy",
        "scs",
        "matplotlib",
        "guppylang",
        "selene-sim",
    )
    versions: dict[str, str | None] = {"python": platform.python_version()}
    for package in packages:
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _classical_results(
    graph: nx.Graph,
    optimum: float,
    config: BenchmarkConfig,
    *,
    greedy_solver: Callable[..., Any],
    gw_solver: Callable[..., Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    greedy_started = perf_counter()
    try:
        greedy = greedy_solver(graph, seed=config.seed)
        greedy_result = {
            "method": "greedy",
            "status": "completed",
            "seed": config.seed,
            "cut": float(greedy.cut_value),
            "ratio": _ratio(float(greedy.cut_value), optimum),
            "partition_zero": list(greedy.partition_zero),
            "partition_one": list(greedy.partition_one),
            "time_seconds": round(perf_counter() - greedy_started, 6),
            "error": None,
        }
    except Exception as error:
        greedy_result = {
            "method": "greedy",
            "status": "failed",
            "seed": config.seed,
            "cut": None,
            "ratio": None,
            "time_seconds": round(perf_counter() - greedy_started, 6),
            "error": _error_record(error),
        }

    gw_seed = config.seed + 1
    gw_started = perf_counter()
    try:
        gw = gw_solver(
            graph,
            seed=gw_seed,
            rounds=config.gw_rounds,
            optimal_weight=optimum,
        )
        gw_result = {
            "method": "goemans_williamson",
            "status": "completed",
            "seed": gw_seed,
            "rounds": config.gw_rounds,
            "cut": float(gw.cut_weight),
            "ratio": _ratio(float(gw.cut_weight), optimum),
            "partition_zero": list(gw.positive_partition),
            "partition_one": list(gw.negative_partition),
            "sdp_value": float(gw.sdp_value),
            "solver": gw.solver,
            "solver_status": gw.solver_status,
            "winning_round": gw.winning_round,
            "solver_options": dict(gw.solver_options),
            "time_seconds": round(perf_counter() - gw_started, 6),
            "error": None,
        }
    except Exception as error:
        gw_result = {
            "method": "goemans_williamson",
            "status": "failed",
            "seed": gw_seed,
            "rounds": config.gw_rounds,
            "cut": None,
            "ratio": None,
            "time_seconds": round(perf_counter() - gw_started, 6),
            "error": _error_record(error),
        }
    return greedy_result, gw_result


def run_benchmark(
    input_path: Path = DEFAULT_INPUT,
    *,
    config: BenchmarkConfig | None = None,
    backend: QAOABackend | None = None,
    greedy_solver: Callable[..., Any] = solve_greedy,
    gw_solver: Callable[..., Any] = solve_goemans_williamson,
) -> dict[str, Any]:
    """Run one preliminary experiment, allowing backend injection in tests."""

    selected_config = config or BenchmarkConfig()
    selected_backend = backend or LocalGuppySeleneBackend()
    benchmark_started = perf_counter()
    graph, artifact, input_info = load_instance(Path(input_path))
    if not graph.nodes:
        raise BenchmarkInputError("QAOA benchmark requires at least one graph node")
    model = build_max_cut_ising(graph)
    exact = exact_max_cut(graph)
    optimum = float(exact["cut"])
    greedy, gw = _classical_results(
        graph,
        optimum,
        selected_config,
        greedy_solver=greedy_solver,
        gw_solver=gw_solver,
    )
    qaoa = [
        _run_qaoa_depth(
            graph,
            model,
            optimum,
            depth=depth,
            config=selected_config,
            backend=selected_backend,
        )
        for depth in selected_config.depths
    ]
    has_failures = any(result["status"] == "failed" for result in qaoa)
    has_failures = has_failures or greedy["status"] == "failed" or gw["status"] == "failed"
    max_abs_j = max((abs(float(value)) for value in model.quadratic.values()), default=0.0)

    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "challenge_1_local_preliminary",
        "study_status": "preliminary",
        "execution_status": "completed_with_failures" if has_failures else "completed",
        "input": input_info,
        "source_provenance": {
            "source": artifact.get("source"),
            "weight_units": artifact.get("weight_units"),
            "weight_definition": artifact.get("weight_definition"),
        },
        "objective": {
            "name": "weighted_max_cut",
            "sense": "maximize cut; minimize Ising energy",
            "ising_formula": (
                "H(z) = -cut(z) = -sum_edges(w)/2 + "
                "sum_edges((w/2) * z_i * z_j)"
            ),
            "max_abs_J": max_abs_j,
            "gamma_range_formula": GAMMA_RANGE_FORMULA,
            "beta_range_formula": BETA_RANGE_FORMULA,
        },
        "configuration": selected_config.as_dict(),
        "software_versions": _software_versions(),
        "reporting": {
            "independent_runs_per_configuration": 1,
            "parameter_candidates_are_independent_runs": False,
            "mean_std_error_bars_reported": False,
            "convergence_claimed": False,
            "quantum_advantage_claimed": False,
        },
        "exact": exact,
        "greedy": greedy,
        "goemans_williamson": gw,
        "qaoa": qaoa,
        "total_time_seconds": round(perf_counter() - benchmark_started, 6),
    }


def _format_number(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _readme(results: Mapping[str, Any], output_dir: Path) -> str:
    input_info = results["input"]
    config = results["configuration"]
    exact = results["exact"]
    rows = [
        (
            "Exacto",
            "fuerza bruta",
            exact["cut"],
            exact["cut"],
            exact["ratio"],
            exact["status"],
            exact["time_seconds"],
        ),
        (
            "Greedy",
            f"seed={results['greedy']['seed']}",
            results["greedy"]["cut"],
            results["greedy"]["cut"],
            results["greedy"]["ratio"],
            results["greedy"]["status"],
            results["greedy"]["time_seconds"],
        ),
        (
            "GW",
            f"seed={results['goemans_williamson']['seed']}, rounds={results['goemans_williamson']['rounds']}",
            results["goemans_williamson"]["cut"],
            results["goemans_williamson"]["cut"],
            results["goemans_williamson"]["ratio"],
            results["goemans_williamson"]["status"],
            results["goemans_williamson"]["time_seconds"],
        ),
    ]
    for qaoa in results["qaoa"]:
        rows.append(
            (
                "QAOA local",
                f"p={qaoa['p']}",
                qaoa["expected_cut"],
                qaoa["best_sample_cut"],
                qaoa["expected_ratio"],
                qaoa["status"],
                qaoa["timings_seconds"]["total"],
            )
        )

    table_lines = [
        "| Método | Configuración | Expected cut | Mejor cut muestreado | Ratio esperado / OPT | Estado | Tiempo (s) |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    table_lines.extend(
        "| " + " | ".join(_format_number(value) for value in row) + " |" for row in rows
    )
    failed = [qaoa for qaoa in results["qaoa"] if qaoa["status"] == "failed"]
    failed_text = (
        "Ninguna profundidad falló."
        if not failed
        else "\n".join(
            f"- `p={item['p']}`: `{item['error']['type']}` — {item['error']['message']}"
            for item in failed
        )
    )
    depths = " ".join(str(depth) for depth in config["depths"])
    output_display = _display_path(output_dir)
    command = (
        "python power-core/src/benchmarks/preliminary.py "
        f"--input {input_info['path']} --output-dir {output_display} "
        f"--depths {depths} "
        f"--parameter-candidates {config['parameter_candidates_per_run']} "
        f"--search-shots {config['search_shots_per_candidate']} "
        f"--final-shots {config['final_shots']} --seed {config['base_seed']} "
        f"--gw-rounds {config['gw_rounds']}"
    )
    weight_definition = input_info.get("weight_definition") or "No weight definition recorded."
    weight_units = input_info.get("weight_units") or "unspecified units"
    weight_limitation = (
        f"- Pesos (`{weight_units}`): {weight_definition} "
        "No deben reinterpretarse como otra magnitud física."
    )
    return "\n".join(
        [
            "# Benchmark local preliminar — Challenge 1",
            "",
            "> **Estado: `preliminary`.** Esta evidencia no es un benchmark final ni demuestra convergencia, ventaja cuántica o superioridad sobre Goemans–Williamson.",
            "",
            "## Reproducción",
            "",
            "```bash",
            command,
            "```",
            "",
            f"- Input: `{input_info['path']}`",
            f"- SHA-256: `{input_info['sha256']}`",
            f"- Grafo: {input_info['node_count']} nodos, {input_info['edge_count']} aristas",
            f"- OPT exacto: {_format_number(exact['cut'])}",
            f"- Backend QAOA: `{results['qaoa'][0]['backend'] if results['qaoa'] else 'N/A'}`",
            f"- Semilla base: `{config['base_seed']}`",
            f"- Shots de búsqueda/finales: `{config['search_shots_per_candidate']}` / `{config['final_shots']}`",
            "",
            "## Resultados",
            "",
            *table_lines,
            "",
            "`approximation_ratio_vs_p.png` muestra el ratio de QAOA por profundidad; `method_comparison.png` compara el corte esperado de QAOA contra OPT y los métodos clásicos; `qaoa_cut_distribution.png` muestra con qué frecuencia apareció cada corte para la mejor profundidad preliminar; y `execution_time_comparison.png` caracteriza los tiempos medidos. La mejor muestra QAOA no se usa como rendimiento típico. No incluyen barras de error porque hay una sola corrida independiente por configuración.",
            "",
            "## Búsqueda aleatoria de parámetros",
            "",
            f"Para cada capa, `{GAMMA_RANGE_FORMULA}`. En esta instancia `max_abs_J = {_format_number(results['objective']['max_abs_J'])}`. Se usa `{BETA_RANGE_FORMULA}`.",
            "",
            f"Cada `p` usa **{config['parameter_candidates_per_run']} candidatos de parámetros dentro de UNA corrida independiente**. Estos candidatos no son {config['parameter_candidates_per_run']} corridas independientes. Se selecciona el candidato de mayor `expected_cut` durante búsqueda y luego se vuelve a muestrear con shots finales. Los estados con count cero se excluyen de métricas y outputs.",
            "",
            "## Fallos conservados",
            "",
            failed_text,
            "",
            "## Limitaciones",
            "",
            "- Solo hay una corrida independiente por `p`; no se reportan media, desviación estándar ni barras de error.",
            "- Los cinco candidatos predeterminados son pruebas de parámetros, no las cinco inicializaciones/corridas independientes exigidas para la evaluación final.",
            "- La búsqueda aleatoria pequeña no permite afirmar convergencia del QAOA.",
            "- `LocalGuppySeleneBackend` recompila el programa Guppy en cada evaluación; los tiempos caracterizan esta implementación preliminar y no ventaja computacional.",
            "- Los shots provienen de emulación local, no de hardware cuántico físico ni de emulación H2.",
            weight_limitation,
            "- No se afirma ventaja cuántica ni superioridad sobre Goemans–Williamson.",
            "- Antes de considerar el benchmark listo para entrega se requieren al menos cinco corridas independientes por configuración y sus estadísticas.",
            "",
            "## Archivos",
            "",
            "- `results.json`: configuración, versiones, seeds, counts positivos, parámetros, tiempos, métricas y fallos.",
            "- `approximation_ratio_vs_p.png`: ratio contra profundidad sin barras de error.",
            "- `method_comparison.png`: comparación visual honesta; QAOA usa `expected_cut`, no su mejor muestra.",
            "- `qaoa_cut_distribution.png`: distribución de probabilidad empírica de los cortes en la profundidad con mayor `expected_cut`.",
            "- `execution_time_comparison.png`: tiempos observados en escala logarítmica; caracterizan esta implementación, no una ventaja computacional.",
            "- `README.md`: este resumen reproducible.",
            "",
        ]
    )


def _write_plot(results: Mapping[str, Any], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    completed = [
        item
        for item in results["qaoa"]
        if item["status"].startswith("completed") and item["expected_ratio"] is not None
    ]
    failed = [item for item in results["qaoa"] if item["status"] == "failed"]
    figure, axis = plt.subplots(figsize=(7.0, 4.5))
    if completed:
        depths = [item["p"] for item in completed]
        axis.plot(
            depths,
            [item["expected_ratio"] for item in completed],
            marker="o",
            label="Expected cut / OPT",
        )
        axis.plot(
            depths,
            [item["best_sample_ratio"] for item in completed],
            marker="s",
            linestyle="--",
            label="Best sample cut / OPT",
        )
    if failed:
        axis.scatter(
            [item["p"] for item in failed],
            [0.0 for _ in failed],
            marker="x",
            s=70,
            label="Failed depth",
        )
    axis.axhline(1.0, color="gray", linewidth=1.0, linestyle=":", label="OPT")
    axis.set_xlabel("QAOA depth p")
    axis.set_ylabel("Approximation ratio")
    axis.set_title("Preliminary: one independent run per depth")
    axis.set_xticks(list(results["configuration"]["depths"]))
    axis.set_ylim(bottom=0.0, top=1.05)
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    axis.text(
        0.01,
        0.02,
        "No mean/std/error bars",
        transform=axis.transAxes,
        fontsize=8,
        color="dimgray",
    )
    figure.tight_layout()
    figure.savefig(
        path,
        dpi=160,
        metadata={"Software": "quantathonv2 preliminary benchmark"},
    )
    plt.close(figure)


def method_comparison_rows(
    results: Mapping[str, Any],
) -> list[tuple[str, float, str]]:
    """Return directly comparable benchmark values for the summary chart."""

    exact_cut = float(results["exact"]["cut"])
    rows = [("OPT exacto", exact_cut, "#4c78a8")]
    for key, label, color in (
        ("greedy", "Greedy", "#59a14f"),
        ("goemans_williamson", "Goemans–Williamson", "#f28e2b"),
    ):
        result = results[key]
        if result["status"] == "completed":
            rows.append((label, float(result["cut"]), color))
    for item in results["qaoa"]:
        if (
            item["status"].startswith("completed")
            and item["expected_cut"] is not None
        ):
            rows.append(
                (
                    f"QAOA esperado (p={item['p']})",
                    float(item["expected_cut"]),
                    "#e15759",
                )
            )
    return rows


def method_comparison_y_limit(rows: Sequence[tuple[str, float, str]]) -> float:
    """Return a positive y-axis limit, including zero-objective instances."""

    return max(1.0, max((value for _, value, _ in rows), default=0.0) * 1.18)


def _write_method_comparison_plot(results: Mapping[str, Any], path: Path) -> None:
    """Write a truthful expected-performance comparison for non-specialists."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = method_comparison_rows(results)
    labels = [item[0] for item in rows]
    cuts = [item[1] for item in rows]
    colors = [item[2] for item in rows]
    exact_cut = float(results["exact"]["cut"])
    figure, axis = plt.subplots(figsize=(10.0, 5.2))
    bars = axis.bar(labels, cuts, color=colors)
    axis.axhline(exact_cut, color="#4c78a8", linestyle=":", linewidth=1.2)
    axis.set_ylabel("Valor de corte ponderado")
    axis.set_title("Preliminar: cortes clásicos vs. corte esperado de QAOA")
    axis.set_ylim(0.0, method_comparison_y_limit(rows))
    axis.grid(axis="y", alpha=0.25)
    axis.tick_params(axis="x", rotation=15)
    for bar, value in zip(bars, cuts, strict=True):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value,
            f"{value:.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    figure.tight_layout()
    figure.savefig(
        path,
        dpi=160,
        metadata={"Software": "quantathonv2 preliminary benchmark"},
    )
    plt.close(figure)


def runtime_comparison_rows(
    results: Mapping[str, Any],
) -> list[tuple[str, float, str]]:
    """Return positive observed runtimes for a log-scale comparison."""

    rows: list[tuple[str, float, str]] = []
    for key, label, color in (
        ("exact", "Exacto", "#4c78a8"),
        ("greedy", "Greedy", "#59a14f"),
        ("goemans_williamson", "Goemans–Williamson", "#f28e2b"),
    ):
        result = results[key]
        seconds = float(result["time_seconds"])
        if result["status"] == "completed" and seconds > 0.0:
            rows.append((label, seconds, color))
    for item in results["qaoa"]:
        seconds = float(item["timings_seconds"]["total"])
        if item["status"].startswith("completed") and seconds > 0.0:
            rows.append((f"QAOA p={item['p']}", seconds, "#e15759"))
    return rows


def _write_runtime_comparison_plot(
    results: Mapping[str, Any],
    path: Path,
) -> None:
    """Plot observed runtimes without presenting them as quantum advantage."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = runtime_comparison_rows(results)
    labels = [label for label, _, _ in rows]
    seconds = [value for _, value, _ in rows]
    colors = [color for _, _, color in rows]
    figure, axis = plt.subplots(figsize=(9.5, 5.2))
    bars = axis.bar(labels, seconds, color=colors)
    axis.set_yscale("log")
    axis.set_ylabel("Tiempo observado (segundos, escala log)")
    axis.set_title("Preliminar: tiempo observado por método")
    axis.grid(axis="y", which="both", alpha=0.25)
    axis.tick_params(axis="x", rotation=15)
    for bar, value in zip(bars, seconds, strict=True):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value,
            f"{value:.3g} s",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    figure.tight_layout()
    figure.savefig(
        path,
        dpi=160,
        metadata={"Software": "quantathonv2 preliminary benchmark"},
    )
    plt.close(figure)


def qaoa_distribution_data(results: Mapping[str, Any]) -> dict[str, Any]:
    """Aggregate QAOA final-shot probabilities by cut value."""

    completed = [
        item
        for item in results["qaoa"]
        if item["status"].startswith("completed")
        and item["expected_cut"] is not None
    ]
    if not completed:
        raise ValueError("no completed QAOA result is available")
    selected = max(
        completed,
        key=lambda item: (float(item["expected_cut"]), -int(item["p"])),
    )
    counts_by_cut: dict[float, int] = {}
    for state in selected["state_metrics"].values():
        cut = float(state["cut"])
        counts_by_cut[cut] = counts_by_cut.get(cut, 0) + int(state["count"])
    total = sum(counts_by_cut.values())
    if total <= 0:
        raise ValueError("selected QAOA result has no positive-count states")
    return {
        "p": int(selected["p"]),
        "expected_cut": float(selected["expected_cut"]),
        "optimal_cut": float(results["exact"]["cut"]),
        "shots": total,
        "probabilities": [
            (cut, count / total)
            for cut, count in sorted(counts_by_cut.items())
        ],
    }


def _write_qaoa_distribution_plot(
    results: Mapping[str, Any],
    path: Path,
) -> None:
    """Plot the empirical cut distribution for the strongest expected QAOA run."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = qaoa_distribution_data(results)
    cuts = [cut for cut, _ in data["probabilities"]]
    probabilities = [probability for _, probability in data["probabilities"]]
    figure, axis = plt.subplots(figsize=(9.5, 5.2))
    axis.bar(cuts, probabilities, color="#e15759", width=35.0)
    axis.axvline(
        data["expected_cut"],
        color="#7f3c8d",
        linestyle="--",
        linewidth=1.5,
        label=f"Esperado: {data['expected_cut']:.1f}",
    )
    axis.axvline(
        data["optimal_cut"],
        color="#4c78a8",
        linestyle=":",
        linewidth=1.5,
        label=f"OPT: {data['optimal_cut']:.0f}",
    )
    axis.set_xlabel("Valor de corte ponderado")
    axis.set_ylabel("Probabilidad empírica")
    axis.set_title(
        f"Preliminar: distribución QAOA para p={data['p']} "
        f"({data['shots']} shots)"
    )
    axis.set_ylim(0.0, max(probabilities, default=0.0) * 1.2 or 1.0)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(
        path,
        dpi=160,
        metadata={"Software": "quantathonv2 preliminary benchmark"},
    )
    plt.close(figure)


def write_outputs(results: Mapping[str, Any], output_dir: Path) -> None:
    """Write the reproducible JSON, README, and benchmark figures."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_plot(results, destination / "approximation_ratio_vs_p.png")
    _write_method_comparison_plot(results, destination / "method_comparison.png")
    _write_qaoa_distribution_plot(
        results,
        destination / "qaoa_cut_distribution.png",
    )
    _write_runtime_comparison_plot(
        results,
        destination / "execution_time_comparison.png",
    )
    (destination / "README.md").write_text(
        _readme(results, destination),
        encoding="utf-8",
    )


def run_and_write(
    input_path: Path,
    output_dir: Path,
    *,
    config: BenchmarkConfig | None = None,
    backend: QAOABackend | None = None,
) -> dict[str, Any]:
    """Run the benchmark and generate ``results.json``, PNG, and README."""

    results = run_benchmark(input_path, config=config, backend=backend)
    write_outputs(results, output_dir)
    return results


def build_parser() -> argparse.ArgumentParser:
    """Build the import-safe command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Run one preliminary local Challenge 1 benchmark per QAOA depth. "
            "Parameter candidates are not independent runs."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--depths", type=int, nargs="+", default=list(DEFAULT_DEPTHS))
    parser.add_argument(
        "--parameter-candidates", type=int, default=DEFAULT_PARAMETER_CANDIDATES
    )
    parser.add_argument("--search-shots", type=int, default=DEFAULT_SEARCH_SHOTS)
    parser.add_argument("--final-shots", type=int, default=DEFAULT_FINAL_SHOTS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--gw-rounds", type=int, default=DEFAULT_GW_ROUNDS)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    backend: QAOABackend | None = None,
) -> int:
    """CLI entry point; the optional backend keeps end-to-end tests Guppy-free."""

    arguments = build_parser().parse_args(argv)
    try:
        config = BenchmarkConfig(
            depths=arguments.depths,
            parameter_candidates=arguments.parameter_candidates,
            search_shots=arguments.search_shots,
            final_shots=arguments.final_shots,
            seed=arguments.seed,
            gw_rounds=arguments.gw_rounds,
        )
        results = run_and_write(
            arguments.input,
            arguments.output_dir,
            config=config,
            backend=backend,
        )
    except (BenchmarkConfigurationError, BenchmarkInputError, OSError) as error:
        print(f"benchmark failed before output generation: {error}", file=sys.stderr)
        return 1

    print(f"wrote preliminary benchmark outputs to {arguments.output_dir}")
    return 2 if results["execution_status"] == "completed_with_failures" else 0


if __name__ == "__main__":
    raise SystemExit(main())
