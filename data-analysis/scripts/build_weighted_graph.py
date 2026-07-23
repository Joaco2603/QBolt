"""Join the substation and transmission-line datasets into a weighted graph.

The CSV and GeoJSON variants are validated against each other by FID. Graph
connectivity comes from the transmission circuit names, while node coordinates
come from the substation GeoJSON. Parallel circuits are collapsed into a simple
undirected edge whose weight is the sum of their nominal voltages in kV.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


SUBSTATION_FIELDS = (
    "OBJECTID",
    "Subestacio",
    "Provincia",
    "Canton",
    "Distrito",
    "CodDistrit",
    "PuntoX",
    "PuntoY",
    "Observacio",
)
LINE_FIELDS = ("OBJECTID", "Voltaje", "Circuito", "SHAPE_STLe", "Shape__Length")
ENDPOINT_ALIASES = {"garita": "la garita"}


def _read_csv(path: Path) -> dict[int, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = {int(row["FID"]): row for row in csv.DictReader(handle)}
    if not rows:
        raise ValueError(f"No records found in {path}")
    return rows


def _read_geojson(path: Path) -> tuple[dict[int, dict[str, Any]], str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("type") != "FeatureCollection":
        raise ValueError(f"{path} is not a GeoJSON FeatureCollection")
    features = {int(feature["properties"]["FID"]): feature for feature in document["features"]}
    crs = document.get("crs", {}).get("properties", {}).get("name", "unspecified")
    return features, crs


def _equal_source_value(csv_value: str, geojson_value: Any) -> bool:
    if isinstance(geojson_value, (int, float)):
        try:
            return abs(float(csv_value) - float(geojson_value)) <= 1e-6
        except ValueError:
            return False
    return csv_value == str(geojson_value)


def _validate_pair(
    csv_path: Path,
    geojson_path: Path,
    csv_rows: dict[int, dict[str, str]],
    geo_features: dict[int, dict[str, Any]],
    fields: tuple[str, ...],
) -> None:
    if csv_rows.keys() != geo_features.keys():
        missing_csv = sorted(geo_features.keys() - csv_rows.keys())
        missing_geojson = sorted(csv_rows.keys() - geo_features.keys())
        raise ValueError(
            f"FID mismatch between {csv_path.name} and {geojson_path.name}: "
            f"missing in CSV={missing_csv}, missing in GeoJSON={missing_geojson}"
        )
    for fid, row in csv_rows.items():
        properties = geo_features[fid]["properties"]
        for field in fields:
            if not _equal_source_value(row[field], properties[field]):
                raise ValueError(
                    f"FID {fid} field {field!r} differs between "
                    f"{csv_path.name} and {geojson_path.name}"
                )


def _coordinate_count(geometry: dict[str, Any]) -> int:
    coordinates = geometry["coordinates"]
    if geometry["type"] == "LineString":
        return len(coordinates)
    if geometry["type"] == "MultiLineString":
        return sum(len(line) for line in coordinates)
    raise ValueError(f"Unsupported transmission geometry: {geometry['type']}")


def load_sources(dataset_dir: Path) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    """Load and cross-check both representations of the two logical datasets."""
    substation_csv_path = dataset_dir / "Subestaciones.csv"
    substation_geojson_path = dataset_dir / "Subestaciones.geojson"
    line_csv_path = dataset_dir / "LineasDeTransmision.csv"
    line_geojson_path = dataset_dir / "LineasDeTransmision.geojson"

    substation_csv = _read_csv(substation_csv_path)
    substation_geojson, substation_crs = _read_geojson(substation_geojson_path)
    line_csv = _read_csv(line_csv_path)
    line_geojson, line_crs = _read_geojson(line_geojson_path)
    _validate_pair(
        substation_csv_path,
        substation_geojson_path,
        substation_csv,
        substation_geojson,
        SUBSTATION_FIELDS,
    )
    _validate_pair(line_csv_path, line_geojson_path, line_csv, line_geojson, LINE_FIELDS)
    if substation_crs != line_crs:
        raise ValueError(f"Dataset CRS mismatch: {substation_crs!r} != {line_crs!r}")

    substations: dict[int, dict[str, Any]] = {}
    for fid, row in substation_csv.items():
        feature = substation_geojson[fid]
        if feature["geometry"]["type"] != "Point":
            raise ValueError(f"Substation FID {fid} is not a Point")
        substations[fid] = {
            "fid": fid,
            "object_id": int(row["OBJECTID"]),
            "name": row["Subestacio"],
            "province": row["Provincia"],
            "canton": row["Canton"],
            "district": row["Distrito"],
            "district_code": row["CodDistrit"],
            "code": row["Observacio"],
            "coordinates": feature["geometry"]["coordinates"],
            "csv_x": float(row["X"]),
            "csv_y": float(row["Y"]),
            "point_x": float(row["PuntoX"]),
            "point_y": float(row["PuntoY"]),
            "crs": substation_crs,
        }

    lines: dict[int, dict[str, Any]] = {}
    for fid, row in line_csv.items():
        geometry = line_geojson[fid]["geometry"]
        lines[fid] = {
            "fid": fid,
            "object_id": int(row["OBJECTID"]),
            "circuit": row["Circuito"],
            "voltage_kv": float(row["Voltaje"]),
            "shape_stle": float(row["SHAPE_STLe"]),
            "shape_length": float(row["Shape__Length"]),
            "geometry": geometry,
            "geometry_type": geometry["type"],
            "coordinate_count": _coordinate_count(geometry),
            "crs": line_crs,
        }
    return substations, lines


def normalize_endpoint(name: str) -> str:
    """Normalize accents and known circuit suffixes for endpoint matching."""
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(character)
    ).casefold().strip()
    normalized = re.sub(r"\s*\(siepac\)\s*$", "", normalized)
    normalized = re.sub(r"(?<=[a-z])\d+$", "", normalized)
    normalized = " ".join(normalized.split())
    return ENDPOINT_ALIASES.get(normalized, normalized)


def _source_metadata(dataset_dir: Path) -> list[dict[str, Any]]:
    sources = []
    for name in (
        "Subestaciones.csv",
        "Subestaciones.geojson",
        "LineasDeTransmision.csv",
        "LineasDeTransmision.geojson",
    ):
        path = dataset_dir / name
        sources.append({
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return sources


def build_graph(
    substations: dict[int, dict[str, Any]],
    lines: dict[int, dict[str, Any]],
    *,
    dataset_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a simple weighted graph and retain circuit-level provenance."""
    station_by_name = {normalize_endpoint(item["name"]): item for item in substations.values()}
    edge_circuits: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    unresolved_lines: list[dict[str, Any]] = []

    for line in lines.values():
        raw_endpoints = line["circuit"].split("-")
        normalized_endpoints = [normalize_endpoint(endpoint) for endpoint in raw_endpoints]
        unmatched = [
            endpoint.strip()
            for endpoint, normalized in zip(raw_endpoints, normalized_endpoints, strict=True)
            if normalized not in station_by_name
        ]
        if len(raw_endpoints) != 2 or unmatched:
            unresolved_lines.append({
                "fid": line["fid"],
                "circuit": line["circuit"],
                "unmatched_endpoints": unmatched or [line["circuit"]],
                "voltage_kv": line["voltage_kv"],
                "shape_length": line["shape_length"],
                "geometry_type": line["geometry_type"],
            })
            continue

        endpoint_nodes = [station_by_name[name] for name in normalized_endpoints]
        endpoint_ids = sorted(f"SUB-{node['fid']:02d}" for node in endpoint_nodes)
        edge_circuits[(endpoint_ids[0], endpoint_ids[1])].append({
            "fid": line["fid"],
            "name": line["circuit"],
            "voltage_kv": line["voltage_kv"],
            "shape_stle": line["shape_stle"],
            "shape_length": line["shape_length"],
            "geometry_type": line["geometry_type"],
            "coordinate_count": line["coordinate_count"],
        })

    degree: dict[str, int] = defaultdict(int)
    name_by_id = {f"SUB-{node['fid']:02d}": node["name"] for node in substations.values()}
    edges = []
    for (source, target), circuits in sorted(edge_circuits.items()):
        degree[source] += 1
        degree[target] += 1
        circuits.sort(key=lambda item: item["fid"])
        edges.append({
            "source": source,
            "target": target,
            "source_name": name_by_id[source],
            "target_name": name_by_id[target],
            "weight": sum(circuit["voltage_kv"] for circuit in circuits),
            "circuit_count": len(circuits),
            "circuits": circuits,
        })

    nodes = []
    for node in sorted(substations.values(), key=lambda item: item["fid"]):
        node_id = f"SUB-{node['fid']:02d}"
        nodes.append({"id": node_id, **node, "degree": degree[node_id]})

    resolved_line_count = sum(len(edge["circuits"]) for edge in edges)
    isolated_node_count = sum(node["degree"] == 0 for node in nodes)
    return {
        "schema_version": 1,
        "graph": {
            "type": "undirected_simple_weighted",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "resolved_line_count": resolved_line_count,
            "unresolved_line_count": len(unresolved_lines),
            "isolated_node_count": isolated_node_count,
        },
        "weight_model": "sum_nominal_voltage_kv",
        "weight_units": "kV",
        "weight_definition": (
            "For each substation pair, weight is the sum of nominal voltage_kv "
            "across all transmission circuits connecting the pair."
        ),
        "limitations": [
            "Nominal voltage is a reproducible importance proxy, not line capacity, power flow, impedance, or failure risk.",
            "Lines whose named endpoint is absent from the substation dataset are reported but excluded from graph edges.",
            "Circuit endpoint matching normalizes accents, known numeric circuit suffixes, and the Garita/La Garita alias.",
        ],
        "sources": _source_metadata(dataset_dir) if dataset_dir is not None else [],
        "nodes": nodes,
        "edges": edges,
        "unresolved_lines": sorted(unresolved_lines, key=lambda item: item["fid"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data-analysis/dataset"),
        help="Directory containing the four source files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("power-core/artifacts/transmission_weighted_graph.json"),
    )
    args = parser.parse_args()
    substations, lines = load_sources(args.dataset_dir)
    graph = build_graph(substations, lines, dataset_dir=args.dataset_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = graph["graph"]
    print(
        f"Wrote {summary['node_count']} nodes and {summary['edge_count']} weighted edges "
        f"({summary['resolved_line_count']} resolved lines, "
        f"{summary['unresolved_line_count']} unresolved) to {args.output}"
    )


if __name__ == "__main__":
    main()
