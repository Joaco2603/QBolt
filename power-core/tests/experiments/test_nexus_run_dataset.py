from pathlib import Path
from types import SimpleNamespace

import networkx as nx
import pytest

from experiments.nexus_run_dataset import NexusRunDataset, build_instance_snapshot, parse_args


def graph() -> nx.Graph:
    value = nx.Graph()
    value.add_edge("A", "B", weight=10)
    value.add_edge("B", "C", weight=5)
    value.graph["source_digests"] = {"regional_instance": "abc"}
    return value


def result(success: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        backend="quantinuum-nexus",
        optimizer_success=success,
        optimizer_status="ok" if success else "did not converge",
        objective_evaluations=12,
        bitstring="010",
        spins={"A": 1, "B": -1, "C": 1},
        energy=-10.0,
        gamma=(0.1,),
        beta=(0.2,),
        counts={"010": 8},
        probabilities={"010": 1.0},
        energies={"010": -10.0},
        metadata={"starts": [{"index": i, "seed": i} for i in range(5)]},
    )


def test_snapshot_digest_changes_when_edge_weight_changes() -> None:
    first = build_instance_snapshot(graph(), instance_id="tiny", optimal_cut=15)
    changed = graph()
    changed["A"]["B"]["weight"] = 11

    assert first["node_count"] == 3
    assert first["edge_count"] == 2
    assert first["digest_sha256"] != build_instance_snapshot(changed, instance_id="tiny")["digest_sha256"]


def test_dataset_records_ratio_partition_and_metadata(tmp_path: Path) -> None:
    instance = build_instance_snapshot(graph(), instance_id="tiny", optimal_cut=15)
    dataset = NexusRunDataset(instance=instance, path=tmp_path / "runs.json")

    record = dataset.append_result(
        result(), graph=graph(), seed=7, layers=1, starts=5, shots=32,
        run_id="run-7", optimal_cut=15, recorded_at_utc="2026-01-01T00:00:00Z",
    )
    dataset.save()
    loaded = NexusRunDataset.load(tmp_path / "runs.json")

    assert record["result"]["partition"] == {"A": 0, "B": 1, "C": 0}
    assert record["result"]["cut_value"] == 15.0
    assert record["result"]["approximation_ratio"] == 1.0
    assert loaded.document["runs"][0]["solver"]["seed"] == 7


def test_dataset_retains_failures_and_rejects_too_few_initializations() -> None:
    dataset = NexusRunDataset(instance=build_instance_snapshot(graph(), instance_id="tiny"))
    with pytest.raises(ValueError, match="at least 5"):
        dataset.append_failure(run_id="bad", seed=1, layers=1, starts=4, shots=1, error="quota")

    record = dataset.append_failure(run_id="failed", seed=1, layers=1, starts=5, shots=1, error=RuntimeError("quota"))
    assert record["result"]["status"] == "failed"
    assert record["error"] == {"type": "RuntimeError", "message": "quota"}


def test_dataset_load_or_create_appends_to_the_same_instance(tmp_path: Path) -> None:
    path = tmp_path / "runs.json"
    instance = build_instance_snapshot(graph(), instance_id="tiny")
    first = NexusRunDataset.load_or_create(instance=instance, path=path)
    first.append_failure(run_id="run-1", seed=1, layers=1, starts=5, shots=1, error="quota")
    first.save()

    second = NexusRunDataset.load_or_create(instance=instance, path=path)
    second.append_failure(run_id="run-2", seed=2, layers=1, starts=5, shots=1, error="quota")
    second.save()

    assert [run["run_id"] for run in NexusRunDataset.load(path).document["runs"]] == ["run-1", "run-2"]


def test_dataset_rejects_duplicate_run_ids_and_different_instances(tmp_path: Path) -> None:
    path = tmp_path / "runs.json"
    instance = build_instance_snapshot(graph(), instance_id="tiny")
    dataset = NexusRunDataset.load_or_create(instance=instance, path=path)
    dataset.append_failure(run_id="run-1", seed=1, layers=1, starts=5, shots=1, error="quota")
    with pytest.raises(ValueError, match="already exists"):
        dataset.append_failure(run_id="run-1", seed=2, layers=1, starts=5, shots=1, error="quota")
    dataset.save()

    changed = graph()
    changed["A"]["B"]["weight"] = 11
    other_instance = build_instance_snapshot(changed, instance_id="other")
    with pytest.raises(ValueError, match="different instance"):
        NexusRunDataset.load_or_create(instance=other_instance, path=path)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--run-id", "test", "--seed", "1", "--starts", "4"],
        ["--run-id", "test", "--seed", "1", "--shots", "0"],
        ["--run-id", "test", "--seed", "-1"],
    ],
)
def test_parser_rejects_invalid_run_configuration(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(arguments)
