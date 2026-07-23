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
