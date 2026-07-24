from pathlib import Path
from types import SimpleNamespace
import sys

import networkx as nx
import pytest

import experiments.nexus_run_dataset as nexus_cli
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


def test_cli_does_not_reference_removed_qubo_module() -> None:
    source = Path(nexus_cli.__file__).read_text(encoding="utf-8")

    assert "optimizer.quantum.qubo_implementation" not in source
    assert "from optimizer.quantum.qubo import build_max_cut_qubo" in source


def test_cli_completes_authenticated_nexus_flow_and_persists_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[object] = []

    class FakeQnexus:
        class projects:
            @staticmethod
            def get_or_create(*, name: str) -> str:
                calls.append(("project", name))
                return "project-ref"

        class context:
            @staticmethod
            def set_active_project(project: object) -> None:
                calls.append(("active-project", project))

        class quotas:
            @staticmethod
            def check_quota(*, name: str) -> bool:
                calls.append(("quota", name))
                return True

        @staticmethod
        def login() -> None:
            calls.append("login")

    class FakeBackend:
        def __init__(self, session: object, **kwargs: object) -> None:
            calls.append(("backend", session, kwargs))

    class FakeQAOA:
        def __init__(self, **kwargs: object) -> None:
            calls.append(("qaoa", kwargs))

        def run_cloud(self, ising: object, *, session: object, backend: object, shots: int):
            calls.append(("run-cloud", ising, session, backend, shots))
            return result()

    import optimizer.quantum as quantum

    monkeypatch.setitem(sys.modules, "qnexus", FakeQnexus)
    monkeypatch.setattr(quantum, "NexusBackend", FakeBackend)
    monkeypatch.setattr(quantum, "QAOA", FakeQAOA)
    monkeypatch.setattr(nexus_cli, "_environment_snapshot", lambda: {"fake": True})

    instance_path = tmp_path / "instance.json"
    instance_path.write_text(
        __import__("json").dumps({
            "source": "tiny",
            "nodes": [{"id": node} for node in ("A", "B", "C")],
            "edges": [
                {"source": "A", "target": "B", "weight": 10},
                {"source": "B", "target": "C", "weight": 5},
            ],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "runs.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nexus_run_dataset.py", "--instance", str(instance_path),
            "--output", str(output), "--run-id", "fake-success", "--seed", "7",
            "--starts", "5", "--shots", "16", "--optimal-cut", "15",
        ],
    )
    nexus_cli.main()

    document = NexusRunDataset.load(output).document
    run = document["runs"][0]
    assert run["result"]["status"] == "succeeded"
    assert run["solver"]["optimizer_method"] == "unknown"
    assert "login" in calls
    assert ("quota", "simulation") in calls
    assert any(call[0] == "run-cloud" for call in calls if isinstance(call, tuple))
    assert "fake-success" in capsys.readouterr().out


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
