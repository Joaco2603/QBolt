from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "data-analysis" / "scripts" / "build_regional_instance.py"
SPEC = importlib.util.spec_from_file_location("build_regional_instance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _real_instance() -> dict[str, object]:
    substations, lines = MODULE.load_sources(ROOT / "data-analysis" / "dataset")
    return MODULE.build_real_regional_instance(substations, lines)


def test_real_regional_instance_uses_connected_confirmed_six_node_topology() -> None:
    instance = _real_instance()

    assert instance["edge_model"] == "confirmed_transmission_lines"
    assert {node["name"] for node in instance["nodes"]} == {
        "Pailas",
        "Liberia",
        "Cañas",
        "Corobici",
        "Sandillal",
        "Filadelfia",
    }
    assert {frozenset((edge["source_name"], edge["target_name"])) for edge in instance["edges"]} == {
        frozenset(("Pailas", "Liberia")),
        frozenset(("Liberia", "Cañas")),
        frozenset(("Cañas", "Corobici")),
        frozenset(("Corobici", "Sandillal")),
        frozenset(("Cañas", "Filadelfia")),
    }
    assert all("distance_km" not in edge for edge in instance["edges"])
    assert {node["name"]: node["degree"] for node in instance["nodes"]} == {
        "Pailas": 1,
        "Liberia": 2,
        "Cañas": 3,
        "Corobici": 2,
        "Sandillal": 1,
        "Filadelfia": 1,
    }


def test_synthetic_peak_demand_is_calibrated_from_official_national_peak() -> None:
    instance = _real_instance()

    demand_values = [node["synthetic_peak_demand_mw"] for node in instance["nodes"]]
    assert demand_values == pytest.approx([1940.23 / 70] * 6, abs=1e-6)
    metadata = instance["synthetic_demand"]
    assert metadata["national_peak_demand_mw"] == 1940.23
    assert metadata["dataset_substation_count"] == 70
    assert metadata["scenario_total_mw"] == pytest.approx(6 * 1940.23 / 70, abs=1e-6)
    assert metadata["is_observed_local_demand"] is False


def test_reference_two_zone_max_cut_cuts_every_confirmed_edge() -> None:
    instance = _real_instance()

    reference = instance["reference_two_zone_max_cut"]
    zones = {
        node_id: "a"
        for node_id in reference["zone_a"]
    } | {
        node_id: "b"
        for node_id in reference["zone_b"]
    }
    assert all(zones[edge["source"]] != zones[edge["target"]] for edge in instance["edges"])
    assert reference["cut_weight_kv"] == 1058.0


@pytest.mark.parametrize("count", [8, 10, 12])
def test_confirmed_regional_instances_expand_deterministically_with_real_ice_lines(
    count: int,
) -> None:
    substations, lines = MODULE.load_sources(ROOT / "data-analysis" / "dataset")

    instance = MODULE.build_real_regional_instance(substations, lines, count=count)

    assert len(instance["nodes"]) == count
    assert instance["edge_model"] == "confirmed_transmission_lines"
    assert instance["weight_model"] == "sum_nominal_voltage_kv"
    assert instance["weight_units"] == "kV"
    assert {node["province"] for node in instance["nodes"]} == {"Guanacaste"}
    assert all({"source", "target", "weight"} <= edge.keys() for edge in instance["edges"])
    assert all("from" not in edge and "to" not in edge for edge in instance["edges"])

    selected = {node["id"] for node in instance["nodes"]}
    adjacency = {node_id: set() for node_id in selected}
    for edge in instance["edges"]:
        adjacency[edge["source"]].add(edge["target"])
        adjacency[edge["target"]].add(edge["source"])
    visited = set()
    pending = [min(selected)]
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        pending.extend(adjacency[node_id] - visited)
    assert visited == selected


def test_proximity_fallback_uses_the_shared_source_target_edge_schema() -> None:
    nodes = [
        {"id": "SUB-01", "longitude": -85.0, "latitude": 10.0},
        {"id": "SUB-02", "longitude": -85.1, "latitude": 10.1},
    ]

    instance = MODULE.build_instance(nodes, neighbors=1)

    assert instance["edges"] == [
        {
            "source": "SUB-01",
            "target": "SUB-02",
            "distance_km": pytest.approx(15.605, abs=0.001),
            "weight": pytest.approx(0.064081, abs=0.000001),
        }
    ]
