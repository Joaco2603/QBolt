"""Generate bilingual, reproducible QUBO-to-Ising walkthrough graphics."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np


POWER_CORE_ROOT = Path(__file__).parents[2]
if str(POWER_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(POWER_CORE_ROOT))

from src.optimizer.quantum import IsingModel, QuboModel, build_max_cut_qubo  # noqa: E402


DEFAULT_INPUT = POWER_CORE_ROOT / "artifacts" / "regional_instance.json"
DEFAULT_OUTPUT_ROOT = POWER_CORE_ROOT / "docs"
LANGUAGES = ("english", "spanish")

TEXT = {
    "english": {
        "title": "From QUBO to Ising: exact conversion step by step",
        "step1": "1. Start with the verified minimization QUBO",
        "step2": "2. Replace each binary variable with a spin",
        "step3": "3. Expand and group constant, linear, and pair terms",
        "step4": "4. Build the Ising Hamiltonian",
        "step5": "5. Map a complete assignment without changing its meaning",
        "step6": "6. Verify the energy identity on all 64 assignments",
        "mapping": "xᵢ = (1 − zᵢ) / 2\nzᵢ = 1 − 2xᵢ\n\nxᵢ = 0  ↔  zᵢ = +1\nxᵢ = 1  ↔  zᵢ = −1",
        "qubo_formula": "E_Q(x) = c + Σ aᵢxᵢ + Σ bᵢⱼxᵢxⱼ",
        "ising_formula": "E_I(z) = C + Σ hᵢzᵢ + Σ Jᵢⱼzᵢzⱼ",
        "coefficient_formula": (
            "Jᵢⱼ = bᵢⱼ / 4\n"
            "hᵢ = −aᵢ / 2 − Σⱼ bᵢⱼ / 4\n"
            "C = c + Σᵢ aᵢ / 2 + Σᵢ<ⱼ bᵢⱼ / 4"
        ),
        "offset_note": "The constant C is retained: it does not change the argmin, but it is required for exact energy comparisons.",
        "assignment": "Reference optimum",
        "verified": "Maximum |E_Q(x) − E_I(1−2x)|",
        "coeff_title": "QUBO and Ising coefficients for the same six-node instance",
        "qubo_matrix": "QUBO coefficients",
        "ising_matrix": "Ising couplings J",
        "linear_terms": "Linear terms: QUBO aᵢ versus Ising hᵢ",
        "offsets": "Constant offsets",
        "energy_offset": "Energy offset",
        "linear_count": "{count} linear terms (aᵢ)",
        "pair_count": "{count} pair terms (bᵢⱼ)",
        "field_count": "{count} non-zero local fields (hᵢ)",
        "coupling_count": "{count} couplings (Jᵢⱼ)",
        "energy_title": "Exact QUBO–Ising energy equivalence",
        "energy_axis": "Energy (kV proxy)",
        "assignment_axis": "Binary assignment index",
        "residual_axis": "E_Q − E_I",
        "readme_title": "QUBO-to-Ising walkthrough",
        "intro": "These figures use the implemented `QuboModel` and `IsingModel` on the documented six-node regional instance. They prove that the conversion changes representation, not the objective energy.",
        "process": "Process",
        "process_steps": [
            "Build the weighted Max-Cut minimization QUBO from the regional graph.",
            "Apply `z = 1 - 2x`, so binary labels become Ising spins.",
            "Convert the offset, linear coefficients, and pair coefficients without rounding.",
            "Evaluate all 64 assignments in both representations.",
            "Confirm exact energy equality and the shared minimum of -1058 proxy kV.",
        ],
        "interpretation": "What the graphics show",
        "interpretation_text": "For this unconstrained Max-Cut instance every Ising local field is zero because each QUBO linear term cancels the incident pair contributions. That is a property of this formulation, not a general rule for constrained QUBOs.",
        "reproduce": "Regenerate from the repository root",
        "limitation": "The graph weight is summed nominal circuit voltage. It is a modelling proxy, not capacity, power flow, impedance, or operational risk.",
    },
    "spanish": {
        "title": "De QUBO a Ising: conversión exacta paso a paso",
        "step1": "1. Partir del QUBO de minimización verificado",
        "step2": "2. Reemplazar cada variable binaria por un espín",
        "step3": "3. Expandir y agrupar términos constantes, lineales y por pares",
        "step4": "4. Construir el Hamiltoniano de Ising",
        "step5": "5. Mapear una asignación completa sin cambiar su significado",
        "step6": "6. Verificar la identidad energética en las 64 asignaciones",
        "mapping": "xᵢ = (1 − zᵢ) / 2\nzᵢ = 1 − 2xᵢ\n\nxᵢ = 0  ↔  zᵢ = +1\nxᵢ = 1  ↔  zᵢ = −1",
        "qubo_formula": "E_Q(x) = c + Σ aᵢxᵢ + Σ bᵢⱼxᵢxⱼ",
        "ising_formula": "E_I(z) = C + Σ hᵢzᵢ + Σ Jᵢⱼzᵢzⱼ",
        "coefficient_formula": (
            "Jᵢⱼ = bᵢⱼ / 4\n"
            "hᵢ = −aᵢ / 2 − Σⱼ bᵢⱼ / 4\n"
            "C = c + Σᵢ aᵢ / 2 + Σᵢ<ⱼ bᵢⱼ / 4"
        ),
        "offset_note": "La constante C se conserva: no cambia el argmin, pero es necesaria para comparar energías exactamente.",
        "assignment": "Óptimo de referencia",
        "verified": "Máximo |E_Q(x) − E_I(1−2x)|",
        "coeff_title": "Coeficientes QUBO e Ising para la misma instancia de seis nodos",
        "qubo_matrix": "Coeficientes QUBO",
        "ising_matrix": "Acoplamientos Ising J",
        "linear_terms": "Términos lineales: QUBO aᵢ frente a Ising hᵢ",
        "offsets": "Desplazamientos constantes",
        "energy_offset": "Desplazamiento de energía",
        "linear_count": "{count} términos lineales (aᵢ)",
        "pair_count": "{count} términos por pares (bᵢⱼ)",
        "field_count": "{count} campos locales no nulos (hᵢ)",
        "coupling_count": "{count} acoplamientos (Jᵢⱼ)",
        "energy_title": "Equivalencia energética exacta entre QUBO e Ising",
        "energy_axis": "Energía (proxy kV)",
        "assignment_axis": "Índice de asignación binaria",
        "residual_axis": "E_Q − E_I",
        "readme_title": "Recorrido de QUBO a Ising",
        "intro": "Estas figuras usan las implementaciones reales de `QuboModel` e `IsingModel` sobre la instancia regional documentada de seis nodos. Demuestran que la conversión cambia la representación, no la energía del objetivo.",
        "process": "Proceso",
        "process_steps": [
            "Construir el QUBO de minimización para Max-Cut ponderado desde el grafo regional.",
            "Aplicar `z = 1 - 2x` para convertir etiquetas binarias en espines de Ising.",
            "Convertir el desplazamiento, los coeficientes lineales y los coeficientes por pares sin redondear.",
            "Evaluar las 64 asignaciones en ambas representaciones.",
            "Confirmar la igualdad exacta de energías y el mínimo compartido de -1058 proxy kV.",
        ],
        "interpretation": "Qué muestran los gráficos",
        "interpretation_text": "En esta instancia Max-Cut sin restricciones todos los campos locales de Ising son cero porque cada término lineal QUBO se cancela con las contribuciones de sus pares incidentes. Es una propiedad de esta formulación, no una regla general para QUBO con restricciones.",
        "reproduce": "Regenerar desde la raíz del repositorio",
        "limitation": "El peso del grafo es la suma del voltaje nominal. Es un proxy de modelado, no capacidad, flujo de potencia, impedancia ni riesgo operativo.",
    },
}


@dataclass(frozen=True)
class Evaluation:
    bits: tuple[int, ...]
    qubo_energy: float
    ising_energy: float
    spins: Mapping[str, int]


def load_instance(path: Path) -> dict[str, Any]:
    instance = json.loads(path.read_text(encoding="utf-8"))
    for key in ("nodes", "edges", "reference_two_zone_max_cut"):
        if key not in instance:
            raise ValueError(f"The regional instance is missing {key!r}")
    return instance


def build_graph(instance: Mapping[str, Any]) -> nx.Graph:
    graph = nx.Graph()
    for node in instance["nodes"]:
        graph.add_node(node["id"], name=node["name"])
    for edge in instance["edges"]:
        graph.add_edge(edge["source"], edge["target"], weight=float(edge["weight"]))
    return graph


def build_models(graph: nx.Graph) -> tuple[QuboModel, IsingModel]:
    qubo = build_max_cut_qubo(graph)
    return qubo, IsingModel.from_qubo(qubo)


def enumerate_and_verify(qubo: QuboModel, ising: IsingModel) -> list[Evaluation]:
    evaluations = []
    for values in product((0, 1), repeat=len(qubo.decision_variables)):
        assignment = dict(zip(qubo.decision_variables, values, strict=True))
        spins = ising.binary_to_spins(assignment)
        qubo_energy = qubo.minimum_energy(assignment)
        ising_energy = ising.energy(spins)
        if abs(qubo_energy - ising_energy) > 1e-9:
            raise ValueError(f"QUBO/Ising energy mismatch for {assignment}")
        evaluations.append(Evaluation(values, qubo_energy, ising_energy, spins))
    return evaluations


def _matrix(
    variables: tuple[str, ...],
    diagonal: Mapping[str, float],
    pairs: Mapping[tuple[str, str], float],
    *,
    split_pairs: bool,
) -> np.ndarray:
    indices = {name: index for index, name in enumerate(variables)}
    matrix = np.zeros((len(variables), len(variables)))
    for name, value in diagonal.items():
        matrix[indices[name], indices[name]] = value
    for (left, right), value in pairs.items():
        stored = value / 2.0 if split_pairs else value
        matrix[indices[left], indices[right]] = stored
        matrix[indices[right], indices[left]] = stored
    return matrix


def _annotate_matrix(axis: Any, matrix: np.ndarray, maximum: float) -> None:
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            if abs(value) > 1e-12:
                axis.text(
                    column,
                    row,
                    f"{value:.0f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if abs(value) > maximum * 0.55 else "#0f172a",
                )


def _reference_evaluation(
    instance: Mapping[str, Any],
    qubo: QuboModel,
    evaluations: list[Evaluation],
) -> Evaluation:
    zone_a = set(instance["reference_two_zone_max_cut"]["zone_a"])
    expected = tuple(int(node in zone_a) for node in qubo.decision_variables)
    return next(item for item in evaluations if item.bits == expected)


def render_walkthrough(
    instance: Mapping[str, Any], language: str, output: Path, digest: str
) -> None:
    text = TEXT[language]
    qubo, ising = build_models(build_graph(instance))
    evaluations = enumerate_and_verify(qubo, ising)
    reference = _reference_evaluation(instance, qubo, evaluations)
    residual = max(abs(item.qubo_energy - item.ising_energy) for item in evaluations)

    figure = plt.figure(figsize=(17, 15))
    grid = figure.add_gridspec(3, 2)
    figure.subplots_adjust(left=0.05, right=0.97, bottom=0.07, top=0.92, hspace=0.32, wspace=0.18)
    figure.suptitle(text["title"], fontsize=21, fontweight="bold")

    axis = figure.add_subplot(grid[0, 0])
    axis.set_title(text["step1"], loc="left", fontweight="bold")
    axis.axis("off")
    axis.text(0.03, 0.84, text["qubo_formula"], fontsize=16, family="monospace")
    axis.text(
        0.03,
        0.62,
        f"c = {qubo.offset:.0f}\n"
        f"{text['linear_count'].format(count=len(qubo.linear))}\n"
        f"{text['pair_count'].format(count=len(qubo.quadratic))}\n\n"
        f"min E_Q = {min(item.qubo_energy for item in evaluations):.0f}",
        va="top",
        fontsize=13,
        family="monospace",
    )

    axis = figure.add_subplot(grid[0, 1])
    axis.set_title(text["step2"], loc="left", fontweight="bold")
    axis.axis("off")
    axis.text(0.08, 0.82, text["mapping"], va="top", fontsize=17, family="monospace")

    axis = figure.add_subplot(grid[1, 0])
    axis.set_title(text["step3"], loc="left", fontweight="bold")
    axis.axis("off")
    axis.text(0.03, 0.86, text["coefficient_formula"], va="top", fontsize=15, family="monospace")
    axis.text(
        0.03,
        0.18,
        "aᵢxᵢ  →  aᵢ/2 − (aᵢ/2)zᵢ\n"
        "bᵢⱼxᵢxⱼ → bᵢⱼ/4 · (1 − zᵢ − zⱼ + zᵢzⱼ)",
        fontsize=12,
        family="monospace",
    )

    axis = figure.add_subplot(grid[1, 1])
    axis.set_title(text["step4"], loc="left", fontweight="bold")
    axis.axis("off")
    nonzero_fields = sum(abs(value) > 1e-12 for value in ising.linear.values())
    axis.text(0.03, 0.84, text["ising_formula"], fontsize=16, family="monospace")
    axis.text(
        0.03,
        0.61,
        f"C = {ising.offset:.0f}\n"
        f"{text['field_count'].format(count=nonzero_fields)}\n"
        f"{text['coupling_count'].format(count=len(ising.quadratic))}\n\n"
        f"min E_I = {min(item.ising_energy for item in evaluations):.0f}",
        va="top",
        fontsize=13,
        family="monospace",
    )
    axis.text(0.03, 0.12, text["offset_note"], fontsize=10.5, wrap=True)

    axis = figure.add_subplot(grid[2, 0])
    axis.set_title(text["step5"], loc="left", fontweight="bold")
    axis.axis("off")
    binary_lines = [
        f"{name.replace('SUB-', 'S')}: x={bit} → z={reference.spins[name]:+d}"
        for name, bit in zip(qubo.decision_variables, reference.bits, strict=True)
    ]
    axis.text(
        0.03,
        0.88,
        f"{text['assignment']}\n\n" + "\n".join(binary_lines),
        va="top",
        fontsize=12,
        family="monospace",
    )
    axis.text(
        0.55,
        0.56,
        f"E_Q = {reference.qubo_energy:.0f}\n=\nE_I = {reference.ising_energy:.0f}",
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
        bbox={"boxstyle": "round", "facecolor": "#dbeafe", "edgecolor": "#2563eb"},
    )

    axis = figure.add_subplot(grid[2, 1])
    axis.set_title(text["step6"], loc="left", fontweight="bold")
    q_values = [item.qubo_energy for item in evaluations]
    i_values = [item.ising_energy for item in evaluations]
    axis.scatter(q_values, i_values, color="#2563eb", s=28, alpha=0.8)
    lower, upper = min(q_values), max(q_values)
    axis.plot((lower, upper), (lower, upper), color="#dc2626", linestyle="--")
    axis.set_xlabel("E_Q")
    axis.set_ylabel("E_I")
    axis.grid(linestyle=":", alpha=0.4)
    axis.text(
        0.04,
        0.92,
        f"{text['verified']}: {residual:.1e}",
        transform=axis.transAxes,
        fontsize=10,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.9},
    )

    figure.text(0.5, 0.02, f"{text['limitation']}  |  SHA-256: {digest[:12]}…", ha="center", fontsize=9)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight", metadata={"Software": "power-core Ising walkthrough"})
    plt.close(figure)


def render_coefficients(
    instance: Mapping[str, Any], language: str, output: Path, digest: str
) -> None:
    text = TEXT[language]
    qubo, ising = build_models(build_graph(instance))
    variables = qubo.decision_variables
    q_matrix = _matrix(variables, qubo.linear, qubo.quadratic, split_pairs=True)
    j_matrix = _matrix(variables, {}, ising.quadratic, split_pairs=False)
    labels = [name.replace("SUB-", "S") for name in variables]

    figure = plt.figure(figsize=(15, 11))
    grid = figure.add_gridspec(2, 2)
    figure.subplots_adjust(left=0.07, right=0.96, bottom=0.09, top=0.9, hspace=0.32, wspace=0.24)
    figure.suptitle(text["coeff_title"], fontsize=20, fontweight="bold")

    for axis, matrix, title in (
        (figure.add_subplot(grid[0, 0]), q_matrix, text["qubo_matrix"]),
        (figure.add_subplot(grid[0, 1]), j_matrix, text["ising_matrix"]),
    ):
        maximum = max(float(np.max(np.abs(matrix))), 1.0)
        image = axis.imshow(matrix, cmap="coolwarm", vmin=-maximum, vmax=maximum)
        axis.set_title(title, fontweight="bold")
        axis.set_xticks(range(len(labels)), labels)
        axis.set_yticks(range(len(labels)), labels)
        _annotate_matrix(axis, matrix, maximum)
        figure.colorbar(image, ax=axis, shrink=0.78)

    axis = figure.add_subplot(grid[1, 0])
    positions = np.arange(len(variables))
    axis.bar(positions - 0.18, [qubo.linear[name] for name in variables], width=0.36, label="aᵢ (QUBO)", color="#f97316")
    axis.bar(positions + 0.18, [ising.linear[name] for name in variables], width=0.36, label="hᵢ (Ising)", color="#2563eb")
    axis.set_title(text["linear_terms"], fontweight="bold")
    axis.set_xticks(positions, labels)
    axis.axhline(0, color="#334155", linewidth=0.8)
    axis.grid(axis="y", linestyle=":", alpha=0.4)
    axis.legend()

    axis = figure.add_subplot(grid[1, 1])
    axis.set_title(text["offsets"], fontweight="bold")
    bars = axis.bar(("c (QUBO)", "C (Ising)"), (qubo.offset, ising.offset), color=("#f97316", "#2563eb"))
    axis.axhline(0, color="#334155", linewidth=0.8)
    axis.set_ylim(min(ising.offset, qubo.offset) * 1.12, 55)
    axis.text(0, 12, f"{qubo.offset:.0f}", ha="center", va="bottom", fontweight="bold")
    axis.text(1, ising.offset - 12, f"{ising.offset:.0f}", ha="center", va="top", fontweight="bold")
    axis.set_ylabel(text["energy_offset"])
    axis.grid(axis="y", linestyle=":", alpha=0.4)
    axis.text(
        0.03,
        0.88,
        text["offset_note"],
        transform=axis.transAxes,
        fontsize=9.5,
        va="top",
        wrap=True,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.92},
    )

    figure.text(0.5, 0.025, f"{text['limitation']}  |  SHA-256: {digest[:12]}…", ha="center", fontsize=9)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight", metadata={"Software": "power-core Ising coefficient report"})
    plt.close(figure)


def render_energy_equivalence(
    instance: Mapping[str, Any], language: str, output: Path, digest: str
) -> None:
    text = TEXT[language]
    qubo, ising = build_models(build_graph(instance))
    evaluations = enumerate_and_verify(qubo, ising)
    q_values = np.array([item.qubo_energy for item in evaluations])
    i_values = np.array([item.ising_energy for item in evaluations])
    residuals = q_values - i_values
    indices = np.arange(len(evaluations))
    minima = np.isclose(q_values, q_values.min())

    figure, (energy_axis, residual_axis) = plt.subplots(
        2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": (3, 1)}, sharex=True
    )
    figure.subplots_adjust(left=0.09, right=0.97, bottom=0.1, top=0.88, hspace=0.12)
    figure.suptitle(text["energy_title"], fontsize=20, fontweight="bold")
    energy_axis.plot(indices, q_values, color="#f97316", linewidth=2.2, label="QUBO E_Q")
    energy_axis.scatter(indices, i_values, color="#2563eb", s=20, label="Ising E_I", zorder=3)
    energy_axis.scatter(indices[minima], q_values[minima], color="#dc2626", s=65, label=f"min = {q_values.min():.0f}", zorder=4)
    energy_axis.set_ylabel(text["energy_axis"])
    energy_axis.grid(axis="y", linestyle=":", alpha=0.4)
    energy_axis.legend(ncol=3)

    residual_axis.bar(indices, residuals, color="#16a34a", width=0.8)
    residual_axis.axhline(0, color="#334155", linewidth=0.8)
    residual_axis.set_ylim(-1.0, 1.0)
    residual_axis.set_xlabel(text["assignment_axis"])
    residual_axis.set_ylabel(text["residual_axis"])
    residual_axis.grid(axis="y", linestyle=":", alpha=0.4)
    residual_axis.text(
        0.01,
        0.78,
        f"{text['verified']}: {max(abs(residuals)):.1e}",
        transform=residual_axis.transAxes,
        fontsize=10,
    )

    figure.text(0.5, 0.025, f"{text['limitation']}  |  SHA-256: {digest[:12]}…", ha="center", fontsize=9)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight", metadata={"Software": "power-core QUBO Ising energy verification"})
    plt.close(figure)


def write_readme(
    instance: Mapping[str, Any], language: str, output: Path, digest: str
) -> None:
    text = TEXT[language]
    qubo, ising = build_models(build_graph(instance))
    evaluations = enumerate_and_verify(qubo, ising)
    minimum = min(item.qubo_energy for item in evaluations)
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(text["process_steps"], start=1))
    content = f"""# {text['readme_title']}

{text['intro']}

![{text['title']}](ising_walkthrough.png)

## {text['process']}

{steps}

```text
{text['qubo_formula']}
{text['mapping'].splitlines()[0]}
{text['ising_formula']}
```

## {text['interpretation']}

![{text['coeff_title']}](ising_coefficients.png)

{text['interpretation_text']}

![{text['energy_title']}](ising_energy_equivalence.png)

- **Assignments verified:** {len(evaluations)}
- **QUBO offset `c`:** {qubo.offset:.0f}
- **Ising offset `C`:** {ising.offset:.0f}
- **Shared minimum energy:** {minimum:.0f} proxy kV
- **Maximum absolute energy difference:** {max(abs(item.qubo_energy - item.ising_energy) for item in evaluations):.1e}
- **Input SHA-256:** `{digest}`

> {text['limitation']}

## {text['reproduce']}

```bash
python power-core/src/reports/generate_ising_walkthrough.py
```
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def generate_reports(input_path: Path, output_root: Path) -> list[Path]:
    raw_input = input_path.read_bytes()
    digest = hashlib.sha256(raw_input).hexdigest()
    instance = load_instance(input_path)
    written = []
    for language in LANGUAGES:
        directory = output_root / language / "ising"
        walkthrough = directory / "ising_walkthrough.png"
        coefficients = directory / "ising_coefficients.png"
        energies = directory / "ising_energy_equivalence.png"
        readme = directory / "README.md"
        render_walkthrough(instance, language, walkthrough, digest)
        render_coefficients(instance, language, coefficients, digest)
        render_energy_equivalence(instance, language, energies, digest)
        write_readme(instance, language, readme, digest)
        written.extend((walkthrough, coefficients, energies, readme))
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    arguments = parser.parse_args()
    for path in generate_reports(arguments.input, arguments.output_root):
        print(path)


if __name__ == "__main__":
    main()
