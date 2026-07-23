"""Build a small, reproducible Max-Cut instance from Costa Rica grid data.

The default scenario uses confirmed transmission-line connectivity. A geographic
proximity fallback remains available only when explicitly requested.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path
from typing import Any


REAL_SCENARIO_NODE_NAMES = (
    "Pailas",
    "Liberia",
    "Cañas",
    "Corobici",
    "Sandillal",
    "Filadelfia",
)
NATIONAL_PEAK_DEMAND_MW = 1940.23
NATIONAL_PEAK_DEMAND_SOURCE = (
    "ICE DOCSE, Informe de atención de demanda y producción de electricidad "
    "con fuentes renovables, Costa Rica 2025"
)
NATIONAL_PEAK_DEMAND_URL = (
    "https://apps.grupoice.com/CenceWeb/documentos/3/3008/27/"
    "R01-PDOCSE-07%20Informe_Atenci%C3%B3n%20demanda%20y%20producci%C3%B3n_2025_v2_firmado.pdf"
)


def _weighted_graph_module() -> Any:
    """Load the adjacent verified transmission graph builder without packaging scripts."""
    script = Path(__file__).with_name("build_weighted_graph.py")
    spec = importlib.util.spec_from_file_location("build_weighted_graph", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load weighted graph builder from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_sources(dataset_dir: Path) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    """Load the validated substation and transmission-line source pairs."""
    return _weighted_graph_module().load_sources(dataset_dir)


def distance_km(left: tuple[float, float], right: tuple[float, float]) -> float:
    """Return haversine distance for (longitude, latitude) pairs."""
    lon1, lat1 = map(math.radians, left)
    lon2, lat2 = map(math.radians, right)
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(value))


def load_features(geojson_path: Path, csv_path: Path) -> list[dict[str, Any]]:
    geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        csv_rows = {int(row["FID"]): row for row in csv.DictReader(handle)}

    features = []
    for feature in geojson["features"]:
        props = feature["properties"]
        fid = int(props["FID"])
        if fid not in csv_rows:
            raise ValueError(f"FID {fid} exists in GeoJSON but not CSV")
        longitude, latitude = feature["geometry"]["coordinates"]
        features.append({
            "id": f"SUB-{fid:02d}",
            "fid": fid,
            "name": props["Subestacio"],
            "province": props["Provincia"],
            "canton": props["Canton"],
            "district": props["Distrito"],
            "observation": props["Observacio"],
            "longitude": longitude,
            "latitude": latitude,
            "projected_x": float(csv_rows[fid]["X"]),
            "projected_y": float(csv_rows[fid]["Y"]),
        })
    if len(features) != len(csv_rows):
        raise ValueError("CSV and GeoJSON contain different record counts")
    return features


def choose_compact(features: list[dict[str, Any]], province: str, count: int) -> list[dict[str, Any]]:
    candidates = [item for item in features if item["province"].casefold() == province.casefold()]
    if len(candidates) < count:
        raise ValueError(f"Province {province!r} has only {len(candidates)} matching nodes")
    centroid = (
        sum(item["longitude"] for item in candidates) / len(candidates),
        sum(item["latitude"] for item in candidates) / len(candidates),
    )
    return sorted(candidates, key=lambda item: distance_km((item["longitude"], item["latitude"]), centroid))[:count]


def build_instance(nodes: list[dict[str, Any]], neighbors: int) -> dict[str, Any]:
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    for node in nodes:
        origin = (node["longitude"], node["latitude"])
        nearby = sorted(
            (other for other in nodes if other["id"] != node["id"]),
            key=lambda other: distance_km(origin, (other["longitude"], other["latitude"])),
        )[:neighbors]
        for other in nearby:
            pair = tuple(sorted((node["id"], other["id"])))
            length = distance_km(origin, (other["longitude"], other["latitude"]))
            edges[pair] = {"from": pair[0], "to": pair[1], "distance_km": round(length, 3), "weight": round(1 / max(length, 0.001), 6)}
    return {
        "schema_version": 1,
        "source": "Subestaciones.csv + Subestaciones.geojson",
        "edge_model": "proximity_inverse_distance_fallback",
        "limitations": ["Edges are inferred; they are not confirmed ICE transmission lines."],
        "nodes": nodes,
        "edges": sorted(edges.values(), key=lambda edge: (edge["from"], edge["to"])),
    }


def build_real_regional_instance(
    substations: dict[int, dict[str, Any]], lines: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """Build the documented six-node scenario from confirmed transmission lines."""
    full_graph = _weighted_graph_module().build_graph(substations, lines)
    nodes_by_name = {node["name"]: node for node in full_graph["nodes"]}
    missing_nodes = sorted(set(REAL_SCENARIO_NODE_NAMES) - nodes_by_name.keys())
    if missing_nodes:
        raise ValueError(f"Configured scenario nodes are missing: {missing_nodes}")

    scenario_nodes = [dict(nodes_by_name[name]) for name in REAL_SCENARIO_NODE_NAMES]
    demand_per_substation = NATIONAL_PEAK_DEMAND_MW / len(full_graph["nodes"])
    for node in scenario_nodes:
        node["synthetic_peak_demand_mw"] = round(demand_per_substation, 6)

    scenario_ids = {node["id"] for node in scenario_nodes}
    scenario_edges = [
        edge
        for edge in full_graph["edges"]
        if edge["source"] in scenario_ids and edge["target"] in scenario_ids
    ]
    expected_edge_names = {
        frozenset(("Pailas", "Liberia")),
        frozenset(("Liberia", "Cañas")),
        frozenset(("Cañas", "Corobici")),
        frozenset(("Corobici", "Sandillal")),
        frozenset(("Cañas", "Filadelfia")),
    }
    actual_edge_names = {
        frozenset((edge["source_name"], edge["target_name"])) for edge in scenario_edges
    }
    if actual_edge_names != expected_edge_names:
        raise ValueError(
            "Configured scenario no longer has the expected confirmed transmission topology"
        )
    scenario_degree = {node_id: 0 for node_id in scenario_ids}
    for edge in scenario_edges:
        scenario_degree[edge["source"]] += 1
        scenario_degree[edge["target"]] += 1
    for node in scenario_nodes:
        node["degree"] = scenario_degree[node["id"]]

    return {
        "schema_version": 2,
        "source": "Subestaciones.* + LineasDeTransmision.*",
        "edge_model": "confirmed_transmission_lines",
        "weight_model": "sum_nominal_voltage_kv",
        "weight_units": "kV",
        "weight_definition": (
            "Each edge weight is the summed nominal voltage of confirmed circuits "
            "between its two substations."
        ),
        "limitations": [
            "Nominal voltage is an importance proxy, not capacity, flow, impedance, or failure risk.",
            "synthetic_peak_demand_mw is a calibrated scenario value, not observed local demand.",
        ],
        "synthetic_demand": {
            "field": "synthetic_peak_demand_mw",
            "unit": "MW",
            "national_peak_demand_mw": NATIONAL_PEAK_DEMAND_MW,
            "dataset_substation_count": len(full_graph["nodes"]),
            "allocation_method": "equal_share_of_national_peak_across_dataset_substations",
            "scenario_total_mw": round(demand_per_substation * len(scenario_nodes), 6),
            "is_observed_local_demand": False,
            "source": NATIONAL_PEAK_DEMAND_SOURCE,
            "source_url": NATIONAL_PEAK_DEMAND_URL,
        },
        "reference_two_zone_max_cut": {
            "zone_a": ["SUB-01", "SUB-29", "SUB-47"],
            "zone_b": ["SUB-07", "SUB-18", "SUB-15"],
            "cut_weight_kv": sum(edge["weight"] for edge in scenario_edges),
        },
        "nodes": scenario_nodes,
        "edges": sorted(scenario_edges, key=lambda edge: (edge["source"], edge["target"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("confirmed", "proximity-fallback"),
        default="confirmed",
        help="Use confirmed transmission lines (default) or explicit proximity fallback.",
    )
    parser.add_argument("--province", default="Guanacaste")
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--neighbors", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("power-core/artifacts/regional_instance.json"))
    args = parser.parse_args()
    if not 6 <= args.count <= 12:
        parser.error("--count must be between 6 and 12")
    if args.neighbors < 1:
        parser.error("--neighbors must be positive")
    root = Path(__file__).parents[2]
    if args.mode == "confirmed":
        substations, lines = load_sources(root / "data-analysis/dataset")
        instance = build_real_regional_instance(substations, lines)
    else:
        features = load_features(root / "data-analysis/dataset/Subestaciones.geojson", root / "data-analysis/dataset/Subestaciones.csv")
        selected = choose_compact(features, args.province, args.count)
        instance = build_instance(selected, args.neighbors)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(instance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(instance['nodes'])} nodes and {len(instance['edges'])} "
        f"{args.mode} edges to {args.output}"
    )


if __name__ == "__main__":
    main()
