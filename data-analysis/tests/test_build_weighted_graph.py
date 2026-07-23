from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "data-analysis" / "scripts" / "build_weighted_graph.py"
SPEC = importlib.util.spec_from_file_location("build_weighted_graph", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_load_sources_validates_and_joins_all_four_dataset_files() -> None:
    substations, lines = MODULE.load_sources(ROOT / "data-analysis" / "dataset")

    assert len(substations) == 70
    assert len(lines) == 102
    assert substations[1]["name"] == "Pailas"
    assert substations[1]["coordinates"] == [-85.3589556083694, 10.7560934802952]
    assert lines[1]["circuit"] == "Liberia-Papagayo"
    assert lines[1]["geometry"]["type"] == "MultiLineString"


def test_build_graph_uses_real_lines_and_aggregates_parallel_circuits() -> None:
    substations, lines = MODULE.load_sources(ROOT / "data-analysis" / "dataset")
    graph = MODULE.build_graph(substations, lines)

    assert graph["graph"]["node_count"] == 70
    assert graph["graph"]["edge_count"] == 92
    assert graph["graph"]["resolved_line_count"] == 96
    assert graph["graph"]["unresolved_line_count"] == 6
    assert graph["weight_model"] == "sum_nominal_voltage_kv"

    edge = next(
        item
        for item in graph["edges"]
        if {item["source_name"], item["target_name"]} == {"La Caja", "Lindora"}
    )
    assert edge["weight"] == 460.0
    assert edge["circuit_count"] == 2
    assert {circuit["name"] for circuit in edge["circuits"]} == {
        "Lindora-La Caja",
        "Lindora-La Caja2",
    }


def test_build_graph_reports_lines_outside_the_substation_dataset() -> None:
    substations, lines = MODULE.load_sources(ROOT / "data-analysis" / "dataset")
    graph = MODULE.build_graph(substations, lines)

    unresolved = {item["circuit"]: item["unmatched_endpoints"] for item in graph["unresolved_lines"]}
    assert unresolved["Liberia-Frontera Nicaragua"] == ["Frontera Nicaragua"]
    assert unresolved["SIEPAC"] == ["SIEPAC"]
    assert "Garita-La Caja" not in unresolved


def test_nodes_keep_isolated_substations_for_complete_provenance() -> None:
    substations, lines = MODULE.load_sources(ROOT / "data-analysis" / "dataset")
    graph = MODULE.build_graph(substations, lines)

    tanque = next(node for node in graph["nodes"] if node["name"] == "Tanque")
    assert tanque["degree"] == 0
    assert graph["graph"]["isolated_node_count"] == 1
