"""Render the six-node confirmed transmission graph used by the QUBO instance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx


def load_instance(path: Path) -> dict[str, Any]:
    """Load a regional graph artifact."""
    return json.loads(path.read_text(encoding="utf-8"))


def build_graph(instance: dict[str, Any]) -> nx.Graph:
    """Convert the regional artifact into a weighted NetworkX graph."""
    graph = nx.Graph()
    for node in instance["nodes"]:
        graph.add_node(
            node["id"],
            name=node["name"],
            longitude=node["coordinates"][0],
            latitude=node["coordinates"][1],
        )
    for edge in instance["edges"]:
        graph.add_edge(
            edge["source"], edge["target"], weight=edge["weight"]
        )
    return graph


def plot_graph(instance: dict[str, Any], output: Path) -> None:
    """Plot the graph geographically and highlight the reference Max-Cut."""
    graph = build_graph(instance)
    zone_a = set(instance["reference_two_zone_max_cut"]["zone_a"])
    zone_b = set(instance["reference_two_zone_max_cut"]["zone_b"])
    positions = {
        node_id: (data["longitude"], data["latitude"])
        for node_id, data in graph.nodes(data=True)
    }
    node_colors = ["#2563eb" if node_id in zone_a else "#f97316" for node_id in graph]
    edge_colors = [
        "#dc2626" if (left in zone_a and right in zone_b) or (left in zone_b and right in zone_a) else "#94a3b8"
        for left, right in graph.edges
    ]
    edge_widths = [1.5 + graph[left][right]["weight"] / 100 for left, right in graph.edges]

    figure, axis = plt.subplots(figsize=(10, 7), constrained_layout=True)
    nx.draw_networkx_edges(
        graph,
        positions,
        ax=axis,
        edge_color=edge_colors,
        width=edge_widths,
        alpha=0.9,
    )
    nx.draw_networkx_nodes(
        graph,
        positions,
        ax=axis,
        node_color=node_colors,
        node_size=1500,
        edgecolors="white",
        linewidths=2,
    )
    labels = {node_id: data["name"] for node_id, data in graph.nodes(data=True)}
    nx.draw_networkx_labels(graph, positions, labels=labels, ax=axis, font_weight="bold", font_size=10)
    edge_labels = {(left, right): f"{graph[left][right]['weight']:.0f} kV" for left, right in graph.edges}
    nx.draw_networkx_edge_labels(graph, positions, edge_labels=edge_labels, ax=axis, font_size=9)

    cut_weight = instance["reference_two_zone_max_cut"]["cut_weight_kv"]
    axis.set_title(f"Regional transmission graph for QUBO / Max-Cut\nReference cut weight: {cut_weight:.0f} kV")
    axis.set_xlabel("Longitude")
    axis.set_ylabel("Latitude")
    axis.grid(True, linestyle=":", alpha=0.35)
    axis.set_aspect("equal", adjustable="datalim")
    axis.text(
        0.01,
        0.01,
        "Blue = zone A  |  Orange = zone B  |  Red = cut edge\n"
        "Weight proxy: summed nominal circuit voltage (kV)",
        transform=axis.transAxes,
        fontsize=9,
        va="bottom",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("power-core/artifacts/regional_instance.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("power-core/artifacts/regional_instance_graph.png")
    )
    args = parser.parse_args()
    plot_graph(load_instance(args.input), args.output)
    print(f"Wrote graph visualization to {args.output}")


if __name__ == "__main__":
    main()
