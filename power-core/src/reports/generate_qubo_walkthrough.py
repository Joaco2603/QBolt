"""Generate a bilingual, step-by-step weighted Max-Cut QUBO report.

This reporting script intentionally does not import the optimizer implementation.
It reconstructs the documented QUBO convention from the immutable regional input
artifact and verifies every binary assignment before rendering the figures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from textwrap import fill
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import networkx as nx


POWER_CORE_ROOT = Path(__file__).parents[2]
DEFAULT_INPUT = POWER_CORE_ROOT / "artifacts" / "regional_instance.json"
DEFAULT_OUTPUT_ROOT = POWER_CORE_ROOT / "docs"
LANGUAGES = ("english", "spanish")

TEXT = {
    "english": {
        "title": "Weighted Max-Cut QUBO: step-by-step verification",
        "step1": "1. Input: regional transmission graph ({node_count} nodes)",
        "step2": "2. One binary variable per substation",
        "step3": "3. Convert every edge into QUBO terms",
        "step4": "4. Assemble the symmetric Q matrix",
        "step5": "5. Verify all binary assignments",
        "step6": "6. Minimum energy gives the maximum cut",
        "zone0": "Zone 0",
        "zone1": "Zone 1",
        "uncut": "Not cut",
        "cut": "Cut edge",
        "assignment": "Assignment index",
        "energy": "QUBO energy (kV proxy)",
        "linear": "Linear",
        "quadratic": "Quadratic",
        "variables": "0 and 1 identify the two sides of the partition.",
        "formula": (
            "For edge (u, v) with weight w:\n"
            "cut = w(xᵤ + xᵥ − 2xᵤxᵥ)\n"
            "minimize E = −cut\n"
            "⇒ −wxᵤ − wxᵥ + 2wxᵤxᵥ"
        ),
        "matrix_note": "E(x) = xᵀQx; off-diagonal terms store half the pair coefficient.",
        "verified": "Verified exhaustively: E(x) = −cut(x) for all {count} assignments.",
        "optimum": "Optimal cut: {cut:.0f} kV proxy  |  minimum energy: {energy:.0f}",
        "limitation": "Weight = summed nominal circuit voltage; it is not capacity, flow, impedance, or risk.",
        "readme_title": "Weighted Max-Cut QUBO walkthrough",
        "readme_intro": "This report reconstructs and verifies the QUBO transformation from the regional input artifact without importing or changing the optimizer implementation.",
        "steps": [
            "Load the {node_count}-node transmission graph and preserve its source weights.",
            "Assign one binary variable to every substation; its value selects a partition side.",
            "For each weighted edge, negate its cut contribution to obtain a minimization QUBO.",
            "Aggregate the linear and pairwise coefficients in a symmetric matrix.",
            "Enumerate all {assignment_count} assignments and verify that QUBO energy equals negative cut weight.",
            "Select the minimum-energy assignment, which reaches the maximum reference cut.",
        ],
        "reproduce": "Regenerate from the repository root:",
        "provenance": "Input provenance",
        "nodes": "Nodes in this report",
        "digest": "SHA-256 of the input artifact",
        "results_title": "Optimal partition: class membership",
        "membership_title": "Result for each substation",
        "class0": "Class 0 / Zone B",
        "class1": "Class 1 / Zone A",
        "cut_edges_title": "Edges between classes",
        "result_summary": "{count} of {total} edges cross the partition · total: {cut:.0f} kV proxy",
        "symmetry": "Max-Cut is symmetric: swapping every 0 and 1 gives the same partition and cut weight.",
        "partition_heading": "Optimal class assignment",
        "class_column": "Class",
        "substation_column": "Substation",
        "adjacency_title": "Weighted adjacency matrix of the regional graph",
        "adjacency_heading": "Weighted adjacency matrix",
        "adjacency_note": "Aᵢⱼ is the summed nominal voltage when substations i and j are directly connected; 0 means no direct edge.",
        "adjacency_value": "Direct connection weight (kV)",
    },
    "spanish": {
        "title": "QUBO Max-Cut ponderado: verificación paso a paso",
        "step1": "1. Entrada: grafo regional de transmisión ({node_count} nodos)",
        "step2": "2. Una variable binaria por subestación",
        "step3": "3. Convertir cada arista en términos QUBO",
        "step4": "4. Ensamblar la matriz Q simétrica",
        "step5": "5. Verificar todas las asignaciones binarias",
        "step6": "6. La energía mínima produce el corte máximo",
        "zone0": "Zona 0",
        "zone1": "Zona 1",
        "uncut": "No cortada",
        "cut": "Arista cortada",
        "assignment": "Índice de asignación",
        "energy": "Energía QUBO (proxy kV)",
        "linear": "Lineal",
        "quadratic": "Cuadrático",
        "variables": "0 y 1 identifican los dos lados de la partición.",
        "formula": (
            "Para la arista (u, v) con peso w:\n"
            "corte = w(xᵤ + xᵥ − 2xᵤxᵥ)\n"
            "minimizar E = −corte\n"
            "⇒ −wxᵤ − wxᵥ + 2wxᵤxᵥ"
        ),
        "matrix_note": "E(x) = xᵀQx; los términos fuera de la diagonal guardan la mitad del coeficiente del par.",
        "verified": "Verificación exhaustiva: E(x) = −corte(x) en las {count} asignaciones.",
        "optimum": "Corte óptimo: {cut:.0f} proxy kV  |  energía mínima: {energy:.0f}",
        "limitation": "Peso = suma del voltaje nominal; no es capacidad, flujo, impedancia ni riesgo.",
        "readme_title": "Recorrido paso a paso del QUBO Max-Cut ponderado",
        "readme_intro": "Este reporte reconstruye y verifica la transformación QUBO desde el artefacto regional de entrada, sin importar ni modificar la implementación del optimizador.",
        "steps": [
            "Cargar el grafo de transmisión de {node_count} nodos y conservar sus pesos de origen.",
            "Asignar una variable binaria a cada subestación; su valor elige un lado de la partición.",
            "Negar la contribución al corte de cada arista ponderada para obtener un QUBO de minimización.",
            "Agregar los coeficientes lineales y por pares en una matriz simétrica.",
            "Enumerar las {assignment_count} asignaciones y verificar que la energía QUBO sea el negativo del peso del corte.",
            "Elegir la asignación de energía mínima, que alcanza el corte máximo de referencia.",
        ],
        "reproduce": "Regenerar desde la raíz del repositorio:",
        "provenance": "Procedencia de la entrada",
        "nodes": "Nodos en este reporte",
        "digest": "SHA-256 del artefacto de entrada",
        "results_title": "Partición óptima: pertenencia a cada clase",
        "membership_title": "Resultado de cada subestación",
        "class0": "Clase 0 / Zona B",
        "class1": "Clase 1 / Zona A",
        "cut_edges_title": "Aristas entre clases",
        "result_summary": "{count} de {total} aristas cruzan la partición · total: {cut:.0f} proxy kV",
        "symmetry": "Max-Cut es simétrico: intercambiar todos los 0 y 1 produce la misma partición y el mismo peso de corte.",
        "partition_heading": "Asignación óptima de clases",
        "class_column": "Clase",
        "substation_column": "Subestación",
        "adjacency_title": "Matriz de adyacencia ponderada del grafo regional",
        "adjacency_heading": "Matriz de adyacencia ponderada",
        "adjacency_note": "Aᵢⱼ es la suma del voltaje nominal cuando las subestaciones i y j están conectadas directamente; 0 significa que no existe una arista directa.",
        "adjacency_value": "Peso de conexión directa (kV)",
    },
}


@dataclass(frozen=True)
class QuboCoefficients:
    """QUBO coefficients using one explicit coefficient per variable pair."""

    nodes: tuple[str, ...]
    linear: dict[str, float]
    quadratic: dict[tuple[str, str], float]


@dataclass(frozen=True)
class Evaluation:
    """Energy and cut value for one complete binary assignment."""

    bits: tuple[int, ...]
    assignment: dict[str, int]
    energy: float
    cut_weight: float


def load_instance(path: Path) -> dict[str, Any]:
    """Load and minimally validate a regional graph artifact."""
    instance = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(instance, dict):
        raise ValueError("The regional instance must be a JSON object")
    for key in ("nodes", "edges", "reference_two_zone_max_cut"):
        if key not in instance:
            raise ValueError(f"The regional instance is missing {key!r}")
    return instance


def build_graph(instance: Mapping[str, Any]) -> nx.Graph:
    """Build a weighted graph while retaining names and coordinates."""
    graph = nx.Graph()
    for node in instance["nodes"]:
        graph.add_node(
            node["id"],
            name=node["name"],
            position=tuple(node["coordinates"]),
        )
    for edge in instance["edges"]:
        graph.add_edge(edge["source"], edge["target"], weight=float(edge["weight"]))
    if graph.number_of_nodes() != len(instance["nodes"]):
        raise ValueError("Node IDs in the regional instance must be unique")
    return graph


def derive_max_cut_qubo(graph: nx.Graph, nodes: Sequence[str]) -> QuboCoefficients:
    """Derive ``-weighted cut`` as a minimization QUBO from graph data."""
    ordered_nodes = tuple(nodes)
    if set(ordered_nodes) != set(graph.nodes) or len(ordered_nodes) != len(graph):
        raise ValueError("nodes must contain every graph node exactly once")
    linear = {node: 0.0 for node in ordered_nodes}
    quadratic: dict[tuple[str, str], float] = {}
    order = {node: index for index, node in enumerate(ordered_nodes)}
    for left, right, data in graph.edges(data=True):
        weight = float(data["weight"])
        linear[left] -= weight
        linear[right] -= weight
        pair = (left, right) if order[left] < order[right] else (right, left)
        quadratic[pair] = quadratic.get(pair, 0.0) + 2.0 * weight
    return QuboCoefficients(ordered_nodes, linear, quadratic)


def qubo_energy(coefficients: QuboCoefficients, assignment: Mapping[str, int]) -> float:
    """Evaluate the explicit QUBO polynomial for an assignment."""
    return sum(
        coefficient * assignment[node]
        for node, coefficient in coefficients.linear.items()
    ) + sum(
        coefficient * assignment[left] * assignment[right]
        for (left, right), coefficient in coefficients.quadratic.items()
    )


def graph_cut_weight(graph: nx.Graph, assignment: Mapping[str, int]) -> float:
    """Return the sum of weights whose endpoints have different labels."""
    return sum(
        float(data["weight"])
        for left, right, data in graph.edges(data=True)
        if assignment[left] != assignment[right]
    )


def enumerate_and_verify(
    graph: nx.Graph, coefficients: QuboCoefficients
) -> list[Evaluation]:
    """Enumerate every partition and verify the QUBO/cut identity."""
    evaluations = []
    for bits in product((0, 1), repeat=len(coefficients.nodes)):
        bit_values: tuple[int, ...] = tuple(bits)
        assignment: dict[str, int] = dict(
            zip(coefficients.nodes, bit_values, strict=True)
        )
        energy = qubo_energy(coefficients, assignment)
        cut = graph_cut_weight(graph, assignment)
        if abs(energy + cut) > 1e-9:
            raise ValueError(f"QUBO verification failed for assignment {assignment}")
        evaluations.append(Evaluation(bit_values, assignment, energy, cut))
    return evaluations


def symmetric_qubo_matrix(coefficients: QuboCoefficients) -> list[list[float]]:
    """Return Q where ``x.T @ Q @ x`` equals the explicit QUBO polynomial."""
    indices = {node: index for index, node in enumerate(coefficients.nodes)}
    size = len(coefficients.nodes)
    matrix = [[0.0] * size for _ in range(size)]
    for node, coefficient in coefficients.linear.items():
        matrix[indices[node]][indices[node]] = coefficient
    for (left, right), coefficient in coefficients.quadratic.items():
        half = coefficient / 2.0
        matrix[indices[left]][indices[right]] = half
        matrix[indices[right]][indices[left]] = half
    return matrix


def weighted_adjacency_matrix(
    graph: nx.Graph, nodes: Sequence[str]
) -> list[list[float]]:
    """Return the symmetric weighted adjacency matrix in the requested order."""
    ordered_nodes = tuple(nodes)
    if set(ordered_nodes) != set(graph.nodes) or len(ordered_nodes) != len(graph):
        raise ValueError("nodes must contain every graph node exactly once")
    indices = {node: index for index, node in enumerate(ordered_nodes)}
    matrix = [[0.0] * len(ordered_nodes) for _ in ordered_nodes]
    for left, right, data in graph.edges(data=True):
        weight = float(data["weight"])
        matrix[indices[left]][indices[right]] = weight
        matrix[indices[right]][indices[left]] = weight
    return matrix


def choose_reference_optimum(
    evaluations: Sequence[Evaluation], reference_zone_a: set[str]
) -> Evaluation:
    """Select the reference orientation among tied minimum-energy partitions."""
    minimum = min(item.energy for item in evaluations)
    candidates = [item for item in evaluations if abs(item.energy - minimum) < 1e-9]
    return min(
        candidates,
        key=lambda item: sum(
            item.assignment[node] != int(node in reference_zone_a)
            for node in item.assignment
        ),
    )


def _draw_graph(
    axis: Any,
    graph: nx.Graph,
    assignment: Mapping[str, int] | None,
) -> None:
    positions = nx.kamada_kawai_layout(graph, weight=None)
    if assignment is None:
        node_colors = ["#64748b"] * len(graph)
        edge_colors = ["#2563eb"] * graph.number_of_edges()
    else:
        node_colors = [
            "#f97316" if assignment[node] else "#2563eb" for node in graph.nodes
        ]
        edge_colors = [
            "#dc2626" if assignment[left] != assignment[right] else "#94a3b8"
            for left, right in graph.edges
        ]
    widths = [1.5 + graph[left][right]["weight"] / 150 for left, right in graph.edges]
    nx.draw_networkx_edges(
        graph, positions, ax=axis, edge_color=edge_colors, width=widths, alpha=0.9
    )
    nx.draw_networkx_nodes(
        graph,
        positions,
        ax=axis,
        node_color=node_colors,
        node_size=1150,
        edgecolors="white",
        linewidths=1.8,
    )
    labels = {
        node: f"{data['name']}\n({node})" for node, data in graph.nodes(data=True)
    }
    nx.draw_networkx_labels(graph, positions, labels=labels, ax=axis, font_size=7.5)
    edge_labels = {
        (left, right): f"{data['weight']:.0f}"
        for left, right, data in graph.edges(data=True)
    }
    nx.draw_networkx_edge_labels(
        graph, positions, edge_labels=edge_labels, ax=axis, font_size=7
    )
    axis.set_axis_off()


def render_walkthrough(
    instance: Mapping[str, Any], language: str, output: Path, source_digest: str
) -> None:
    """Render the six-stage walkthrough for one language."""
    if language not in TEXT:
        raise ValueError(f"Unsupported language: {language}")
    text = TEXT[language]
    graph = build_graph(instance)
    nodes = tuple(node["id"] for node in instance["nodes"])
    coefficients = derive_max_cut_qubo(graph, nodes)
    evaluations = enumerate_and_verify(graph, coefficients)
    reference = instance["reference_two_zone_max_cut"]
    optimum = choose_reference_optimum(evaluations, set(reference["zone_a"]))
    expected_cut = float(reference["cut_weight_kv"])
    if abs(optimum.cut_weight - expected_cut) > 1e-9:
        raise ValueError("Enumerated optimum does not match the documented reference cut")

    figure = plt.figure(figsize=(17, 16))
    grid = figure.add_gridspec(3, 2)
    figure.subplots_adjust(
        left=0.05,
        right=0.96,
        bottom=0.07,
        top=0.93,
        hspace=0.3,
        wspace=0.18,
    )
    figure.suptitle(text["title"], fontsize=20, fontweight="bold")

    input_axis = figure.add_subplot(grid[0, 0])
    input_axis.set_title(
        text["step1"].format(node_count=len(nodes)), loc="left", fontweight="bold"
    )
    _draw_graph(input_axis, graph, None)

    variable_axis = figure.add_subplot(grid[0, 1])
    variable_axis.set_title(text["step2"], loc="left", fontweight="bold")
    variable_axis.axis("off")
    variable_lines = [
        f"x{i + 1} = {node['id']} ({node['name']})"
        for i, node in enumerate(instance["nodes"])
    ]
    variable_axis.text(
        0.05,
        0.88,
        "xᵢ ∈ {0, 1}\n\n" + "\n".join(variable_lines),
        va="top",
        fontsize=13,
        family="monospace",
    )
    variable_axis.text(0.05, 0.1, text["variables"], fontsize=11)

    terms_axis = figure.add_subplot(grid[1, 0])
    terms_axis.set_title(text["step3"], loc="left", fontweight="bold")
    terms_axis.axis("off")
    terms_axis.text(0.03, 0.96, text["formula"], va="top", fontsize=12)
    edge_lines = []
    for left, right, data in graph.edges(data=True):
        weight = float(data["weight"])
        edge_lines.append(
            f"{left}—{right} ({weight:.0f}):  −{weight:.0f}xᵤ −{weight:.0f}xᵥ +{2 * weight:.0f}xᵤxᵥ"
        )
    terms_axis.text(
        0.03,
        0.43,
        "\n".join(edge_lines),
        va="top",
        fontsize=10.5,
        family="monospace",
    )

    matrix_axis = figure.add_subplot(grid[1, 1])
    matrix_axis.set_title(text["step4"], loc="left", fontweight="bold")
    matrix = symmetric_qubo_matrix(coefficients)
    maximum = max(abs(value) for row in matrix for value in row)
    image = matrix_axis.imshow(matrix, cmap="coolwarm", vmin=-maximum, vmax=maximum)
    short_labels = [node.replace("SUB-", "S") for node in nodes]
    matrix_axis.set_xticks(range(len(nodes)), short_labels)
    matrix_axis.set_yticks(range(len(nodes)), short_labels)
    for row, values in enumerate(matrix):
        for column, value in enumerate(values):
            if value:
                matrix_axis.text(
                    column,
                    row,
                    f"{value:.0f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if abs(value) > maximum * 0.55 else "black",
                )
    figure.colorbar(image, ax=matrix_axis, shrink=0.75, label="Q coefficient")
    matrix_axis.set_xlabel(text["matrix_note"], fontsize=9)

    energy_axis = figure.add_subplot(grid[2, 0])
    energy_axis.set_title(text["step5"], loc="left", fontweight="bold")
    energies = [item.energy for item in evaluations]
    colors = ["#dc2626" if abs(value - optimum.energy) < 1e-9 else "#64748b" for value in energies]
    energy_axis.bar(range(len(energies)), energies, color=colors, width=0.85)
    energy_axis.axhline(optimum.energy, color="#dc2626", linestyle="--", linewidth=1)
    energy_axis.set_xlabel(text["assignment"])
    energy_axis.set_ylabel(text["energy"])
    energy_axis.grid(axis="y", linestyle=":", alpha=0.4)
    energy_axis.text(
        0.02,
        0.04,
        text["verified"].format(count=len(evaluations)),
        transform=energy_axis.transAxes,
        fontsize=9.5,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.9},
    )

    optimum_axis = figure.add_subplot(grid[2, 1])
    optimum_axis.set_title(text["step6"], loc="left", fontweight="bold")
    _draw_graph(optimum_axis, graph, optimum.assignment)
    optimum_axis.text(
        0.5,
        -0.03,
        text["optimum"].format(cut=optimum.cut_weight, energy=optimum.energy),
        transform=optimum_axis.transAxes,
        ha="center",
        fontsize=11,
        fontweight="bold",
    )

    figure.text(
        0.5,
        0.02,
        f"{text['limitation']}  |  SHA-256: {source_digest[:12]}…",
        ha="center",
        fontsize=9,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        dpi=220,
        bbox_inches="tight",
        metadata={"Software": "power-core QUBO walkthrough report"},
    )
    plt.close(figure)


def render_adjacency_matrix(
    instance: Mapping[str, Any], language: str, output: Path, source_digest: str
) -> None:
    """Render the weighted adjacency matrix for one language."""
    if language not in TEXT:
        raise ValueError(f"Unsupported language: {language}")
    text = TEXT[language]
    graph = build_graph(instance)
    nodes = tuple(node["id"] for node in instance["nodes"])
    matrix = weighted_adjacency_matrix(graph, nodes)
    node_names = {node["id"]: node["name"] for node in instance["nodes"]}
    maximum = max((value for row in matrix for value in row), default=0.0)

    figure, axis = plt.subplots(figsize=(11, 10))
    figure.subplots_adjust(left=0.14, right=0.88, bottom=0.22, top=0.86)
    figure.suptitle(text["adjacency_title"], fontsize=19, fontweight="bold")
    image = axis.imshow(matrix, cmap="Blues", vmin=0.0, vmax=maximum or 1.0)
    short_labels = [node.replace("SUB-", "S") for node in nodes]
    axis.set_xticks(range(len(nodes)), short_labels)
    axis.set_yticks(range(len(nodes)), short_labels)
    axis.set_xlabel(fill(text["adjacency_note"], width=85), fontsize=10, labelpad=14)
    for row, values in enumerate(matrix):
        for column, value in enumerate(values):
            label = "—" if row == column else f"{value:.0f}"
            axis.text(
                column,
                row,
                label,
                ha="center",
                va="center",
                fontsize=11,
                fontweight="bold" if value else "normal",
                color="white" if maximum and value > maximum * 0.55 else "#334155",
            )
    figure.colorbar(image, ax=axis, shrink=0.8, label=text["adjacency_value"])
    node_key = "   ·   ".join(f"{node.replace('SUB-', 'S')} = {node_names[node]}" for node in nodes)
    figure.text(0.5, 0.105, node_key, ha="center", fontsize=9.5, wrap=True)
    figure.text(
        0.5,
        0.035,
        f"{text['limitation']}  |  SHA-256: {source_digest[:12]}…",
        ha="center",
        fontsize=9,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        dpi=220,
        bbox_inches="tight",
        metadata={"Software": "power-core weighted adjacency matrix report"},
    )
    plt.close(figure)


def render_partition_results(
    instance: Mapping[str, Any], language: str, output: Path, source_digest: str
) -> None:
    """Render the optimal class membership and the edges between both classes."""
    if language not in TEXT:
        raise ValueError(f"Unsupported language: {language}")
    text = TEXT[language]
    graph = build_graph(instance)
    nodes = tuple(node["id"] for node in instance["nodes"])
    coefficients = derive_max_cut_qubo(graph, nodes)
    evaluations = enumerate_and_verify(graph, coefficients)
    reference = instance["reference_two_zone_max_cut"]
    optimum = choose_reference_optimum(evaluations, set(reference["zone_a"]))
    node_names = {node["id"]: node["name"] for node in instance["nodes"]}
    classes = {
        value: [node for node in nodes if optimum.assignment[node] == value]
        for value in (0, 1)
    }
    cut_edges = [
        (left, right, float(data["weight"]))
        for left, right, data in graph.edges(data=True)
        if optimum.assignment[left] != optimum.assignment[right]
    ]

    figure = plt.figure(figsize=(15, 9))
    grid = figure.add_gridspec(1, 2, width_ratios=(1.35, 1.0))
    figure.subplots_adjust(left=0.04, right=0.97, bottom=0.12, top=0.88, wspace=0.12)
    figure.suptitle(text["results_title"], fontsize=20, fontweight="bold")

    graph_axis = figure.add_subplot(grid[0, 0])
    _draw_graph(graph_axis, graph, optimum.assignment)
    graph_axis.text(
        0.02,
        0.02,
        text["result_summary"].format(
            count=len(cut_edges), total=graph.number_of_edges(), cut=optimum.cut_weight
        ),
        transform=graph_axis.transAxes,
        fontsize=11,
        fontweight="bold",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.9},
    )

    result_axis = figure.add_subplot(grid[0, 1])
    result_axis.set_title(text["membership_title"], loc="left", fontweight="bold")
    result_axis.axis("off")
    y_position = 0.92
    for value, color, title in (
        (0, "#2563eb", text["class0"]),
        (1, "#f97316", text["class1"]),
    ):
        members = "\n".join(
            f"x = {value}   {node} — {node_names[node]}" for node in classes[value]
        )
        result_axis.text(
            0.03,
            y_position,
            f"{title}\n\n{members}",
            va="top",
            fontsize=12,
            color="white",
            family="monospace",
            bbox={"boxstyle": "round,pad=0.8", "facecolor": color, "alpha": 0.95},
        )
        y_position -= 0.31

    edge_lines = "\n".join(
        f"{left} — {right}: {weight:.0f} kV" for left, right, weight in cut_edges
    )
    result_axis.text(
        0.03,
        0.3,
        f"{text['cut_edges_title']}\n\n{edge_lines}",
        va="top",
        fontsize=10.5,
        family="monospace",
    )
    result_axis.text(
        0.03,
        0.03,
        text["symmetry"],
        va="bottom",
        fontsize=10,
        wrap=True,
        bbox={"boxstyle": "round", "facecolor": "#f1f5f9", "alpha": 1.0},
    )
    figure.text(
        0.5,
        0.035,
        f"{text['limitation']}  |  SHA-256: {source_digest[:12]}…",
        ha="center",
        fontsize=9,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        dpi=220,
        bbox_inches="tight",
        metadata={"Software": "power-core QUBO partition results report"},
    )
    plt.close(figure)


def write_readme(
    instance: Mapping[str, Any], language: str, output: Path, source_digest: str
) -> None:
    """Write the localized explanation accompanying a generated figure."""
    text = TEXT[language]
    reference = instance["reference_two_zone_max_cut"]
    node_count = len(instance["nodes"])
    assignment_count = 2**node_count
    graph = build_graph(instance)
    nodes = tuple(node["id"] for node in instance["nodes"])
    coefficients = derive_max_cut_qubo(graph, nodes)
    optimum = choose_reference_optimum(
        enumerate_and_verify(graph, coefficients), set(reference["zone_a"])
    )
    node_names = {node["id"]: node["name"] for node in instance["nodes"]}
    membership_rows = "\n".join(
        f"| {optimum.assignment[node]} | `{node}` | {node_names[node]} |"
        for node in nodes
    )
    numbered_steps = "\n".join(
        f"{index}. {step.format(node_count=node_count, assignment_count=assignment_count)}"
        for index, step in enumerate(text["steps"], start=1)
    )
    content = f"""# {text['readme_title']}

{text['readme_intro']}

![{text['title']}](qubo_walkthrough.png)

## {text['adjacency_heading']}

![{text['adjacency_title']}](qubo_adjacency_matrix.png)

{text['adjacency_note']}

## {text['partition_heading']}

![{text['results_title']}](qubo_partition_results.png)

| {text['class_column']} | ID | {text['substation_column']} |
| ---: | --- | --- |
{membership_rows}

> {text['symmetry']}

## {text['title']}

{numbered_steps}

- **{text['provenance']}:** `{instance['source']}`
- **{text['nodes']}:** {node_count}
- **Weight model:** `{instance['weight_model']}` ({instance['weight_units']})
- **Reference cut:** {float(reference['cut_weight_kv']):.0f} {instance['weight_units']}
- **{text['digest']}:** `{source_digest}`

> {text['limitation']}

## {text['reproduce']}

```bash
python power-core/src/reports/generate_qubo_walkthrough.py
```
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def generate_reports(input_path: Path, output_root: Path) -> list[Path]:
    """Generate localized figures and documentation, returning written paths."""
    raw_input = input_path.read_bytes()
    digest = hashlib.sha256(raw_input).hexdigest()
    instance = load_instance(input_path)
    written = []
    for language in LANGUAGES:
        directory = output_root / language / "qubo"
        figure_path = directory / "qubo_walkthrough.png"
        adjacency_path = directory / "qubo_adjacency_matrix.png"
        results_path = directory / "qubo_partition_results.png"
        readme_path = directory / "README.md"
        render_walkthrough(instance, language, figure_path, digest)
        render_adjacency_matrix(instance, language, adjacency_path, digest)
        render_partition_results(instance, language, results_path, digest)
        write_readme(instance, language, readme_path, digest)
        written.extend((figure_path, adjacency_path, results_path, readme_path))
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Regional JSON instance (default: the current six-node instance)",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    for path in generate_reports(args.input, args.output_root):
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
