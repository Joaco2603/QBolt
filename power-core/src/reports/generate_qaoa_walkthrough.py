"""Generate bilingual QAOA algorithm walkthrough graphics without executing a benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import networkx as nx


POWER_CORE_ROOT = Path(__file__).parents[2]
if str(POWER_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(POWER_CORE_ROOT))

from src.optimizer.quantum import IsingModel, QAOAProgram, build_max_cut_qubo  # noqa: E402


DEFAULT_INPUT = POWER_CORE_ROOT / "artifacts" / "regional_instance.json"
DEFAULT_OUTPUT_ROOT = POWER_CORE_ROOT / "docs"
LANGUAGES = ("english", "spanish")
DEFAULT_LAYERS = 2

TEXT = {
    "english": {
        "title": "QAOA: hybrid quantum-classical algorithm step by step",
        "step1": "1. Receive the verified Ising minimization model",
        "step2": "2. Prepare every qubit in the uniform |+⟩ state",
        "step3": "3. Apply the cost unitary with γₖ",
        "step4": "4. Apply the mixer unitary with βₖ",
        "step5": "5. Measure bitstrings and estimate expected energy",
        "step6": "6. Optimize parameters and sample the best candidate",
        "ising": "E(z) = C + Σ hᵢzᵢ + Σ Jᵢⱼzᵢzⱼ",
        "model_summary": "{variables} variables · {couplings} couplings · C={offset:.0f}",
        "uniform": "H|0⟩ = |+⟩\n\n|+⟩⊗ⁿ assigns equal initial amplitude\nto all computational-basis states.",
        "cost": "U_C(γₖ) = exp(−i γₖ H_C)\n\nhᵢzᵢ  →  RZ\nJᵢⱼzᵢzⱼ  →  CX · RZ · CX\n\nThe constant C is not a gate.",
        "mixer": "U_B(βₖ) = exp(−i βₖ Σ Xᵢ)\n\nApply RX to every qubit.\nThis mixes probability between candidates.",
        "measure": "counts = {bitstring: shots}\n\n⟨E⟩ = Σ_b p(b) E(b)\n\nVariable order = qubit order = bitstring order.",
        "optimize": "Repeat p cost/mixer layers\nEvaluate ⟨E⟩ through the backend\nBFGS updates (γ, β)\nAt least five seeded starts\nFinal sampling with best parameters",
        "warning": "Process diagram only: no QAOA backend was executed and no benchmark result is claimed.",
        "circuit_title": "Parameterized QAOA circuit structure",
        "initialization": "Initialization",
        "cost_layer": "Cost layer γ{k}",
        "mixer_layer": "Mixer layer β{k}",
        "measurement": "Measurement",
        "repeat": "Repeat for p layers",
        "offset": "C is added during classical energy evaluation; it is not encoded as a gate.",
        "loop_title": "Seeded multi-start QAOA optimization loop",
        "ising_input": "IsingModel\nordered variables, C, h, J",
        "program": "QAOAProgram\np layers",
        "starts": "≥5 seeded starts\ninitial γ, β ∈ [−π, π]",
        "backend": "Backend adapter\nlocal Selene or authenticated Nexus",
        "counts": "MeasurementBatch\nvalidated counts",
        "expectation": "Expected energy\nΣ p(bitstring)·E",
        "bfgs": "BFGS update\nuntil optimizer stops",
        "select": "Select lowest expected-energy start",
        "final": "Final sampling\nbest parameters",
        "result": "QAOAResult\nbest sample, counts, selected status",
        "feedback": "next parameters",
        "readme_title": "QAOA algorithm walkthrough",
        "intro": "These figures explain the implemented backend-agnostic QAOA orchestration for the documented six-node Ising instance. They describe program construction, circuit layers, measurement, and seeded classical optimization.",
        "what": "What the figures cover",
        "steps": [
            "Create a backend-neutral `QAOAProgram` from the verified `IsingModel`.",
            "Prepare `|+⟩` on every qubit and apply `p` alternating cost and mixer layers.",
            "Execute one bound parameter set through a local or cloud adapter.",
            "Convert validated measurement counts into expected Ising energy.",
            "Use at least five seeded BFGS starts and select the lowest expected-energy outcome.",
            "Sample once more with the selected parameters; `QAOAResult` retains the selected optimizer status, not every start history.",
        ],
        "scope": "Evidence boundary",
        "scope_text": "This is not a benchmark and does not contain measured QAOA performance, approximation ratios, error bars, emulator results, hardware results, or evidence of quantum advantage. `QAOAResult` currently exposes only the selected optimizer status, so benchmark reporting must preserve every start separately.",
        "reproduce": "Regenerate from the repository root",
        "limitation": "The grid weight remains a nominal-voltage proxy, not capacity, flow, impedance, or operational risk.",
    },
    "spanish": {
        "title": "QAOA: algoritmo híbrido cuántico-clásico paso a paso",
        "step1": "1. Recibir el modelo Ising de minimización verificado",
        "step2": "2. Preparar cada cúbit en el estado uniforme |+⟩",
        "step3": "3. Aplicar la unitaria de costo con γₖ",
        "step4": "4. Aplicar la unitaria mezcladora con βₖ",
        "step5": "5. Medir bitstrings y estimar la energía esperada",
        "step6": "6. Optimizar parámetros y muestrear el mejor candidato",
        "ising": "E(z) = C + Σ hᵢzᵢ + Σ Jᵢⱼzᵢzⱼ",
        "model_summary": "{variables} variables · {couplings} acoplamientos · C={offset:.0f}",
        "uniform": "H|0⟩ = |+⟩\n\n|+⟩⊗ⁿ asigna la misma amplitud inicial\na todos los estados de la base computacional.",
        "cost": "U_C(γₖ) = exp(−i γₖ H_C)\n\nhᵢzᵢ  →  RZ\nJᵢⱼzᵢzⱼ  →  CX · RZ · CX\n\nLa constante C no es una compuerta.",
        "mixer": "U_B(βₖ) = exp(−i βₖ Σ Xᵢ)\n\nAplicar RX a cada cúbit.\nEsto mezcla probabilidad entre candidatos.",
        "measure": "conteos = {bitstring: shots}\n\n⟨E⟩ = Σ_b p(b) E(b)\n\nOrden de variables = orden de cúbits = orden del bitstring.",
        "optimize": "Repetir p capas de costo/mezcla\nEvaluar ⟨E⟩ mediante el backend\nBFGS actualiza (γ, β)\nAl menos cinco inicios con semilla\nMuestreo final con los mejores parámetros",
        "warning": "Solo es un diagrama del proceso: no se ejecutó un backend QAOA ni se afirma un resultado de benchmark.",
        "circuit_title": "Estructura del circuito QAOA parametrizado",
        "initialization": "Inicialización",
        "cost_layer": "Capa de costo γ{k}",
        "mixer_layer": "Capa mezcladora β{k}",
        "measurement": "Medición",
        "repeat": "Repetir durante p capas",
        "offset": "C se agrega al evaluar la energía clásicamente; no se codifica como compuerta.",
        "loop_title": "Ciclo QAOA multiinicio con semillas",
        "ising_input": "IsingModel\nvariables ordenadas, C, h, J",
        "program": "QAOAProgram\np capas",
        "starts": "≥5 inicios con semilla\nγ, β iniciales ∈ [−π, π]",
        "backend": "Adaptador de backend\nSelene local o Nexus autenticado",
        "counts": "MeasurementBatch\nconteos validados",
        "expectation": "Energía esperada\nΣ p(bitstring)·E",
        "bfgs": "Actualización BFGS\nhasta que termine el optimizador",
        "select": "Elegir el inicio con menor energía esperada",
        "final": "Muestreo final\nmejores parámetros",
        "result": "QAOAResult\nmejor muestra, conteos y estado elegido",
        "feedback": "siguientes parámetros",
        "readme_title": "Recorrido del algoritmo QAOA",
        "intro": "Estas figuras explican la orquestación QAOA independiente del backend implementada para la instancia Ising documentada de seis nodos. Describen la construcción del programa, las capas del circuito, la medición y la optimización clásica con semillas.",
        "what": "Qué cubren los gráficos",
        "steps": [
            "Crear un `QAOAProgram` independiente del backend desde el `IsingModel` verificado.",
            "Preparar `|+⟩` en cada cúbit y aplicar `p` capas alternadas de costo y mezcla.",
            "Ejecutar un conjunto de parámetros ligados mediante un adaptador local o de nube.",
            "Convertir los conteos validados en energía Ising esperada.",
            "Usar al menos cinco inicios BFGS con semillas y elegir el resultado de menor energía esperada.",
            "Muestrear otra vez con los parámetros elegidos; `QAOAResult` conserva el estado del optimizador seleccionado, no el historial de cada inicio.",
        ],
        "scope": "Límite de la evidencia",
        "scope_text": "Esto no es un benchmark y no contiene rendimiento QAOA medido, razones de aproximación, barras de error, resultados de emulador, resultados de hardware ni evidencia de ventaja cuántica. `QAOAResult` actualmente expone solo el estado del optimizador seleccionado, por lo que un benchmark debe conservar cada inicio por separado.",
        "reproduce": "Regenerar desde la raíz del repositorio",
        "limitation": "El peso de la red sigue siendo un proxy de voltaje nominal, no capacidad, flujo, impedancia ni riesgo operativo.",
    },
}


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


def build_program(
    instance: Mapping[str, Any], *, layers: int = DEFAULT_LAYERS
) -> tuple[IsingModel, QAOAProgram]:
    if type(layers) is not int or layers < 1:
        raise ValueError("layers must be a positive integer")
    model = IsingModel.from_qubo(build_max_cut_qubo(build_graph(instance)))
    program = QAOAProgram(
        variables=model.variables,
        offset=model.offset,
        linear=tuple((name, float(model.linear[name])) for name in model.variables),
        quadratic=tuple(
            (left, right, float(value))
            for (left, right), value in model.quadratic.items()
        ),
        layers=layers,
    )
    return model, program


def _panel(axis: Any, title: str, body: str, *, color: str = "#eff6ff") -> None:
    axis.set_title(title, loc="left", fontweight="bold", fontsize=12)
    axis.axis("off")
    axis.add_patch(
        FancyBboxPatch(
            (0.03, 0.08),
            0.92,
            0.76,
            boxstyle="round,pad=0.025",
            transform=axis.transAxes,
            facecolor=color,
            edgecolor="#94a3b8",
            linewidth=1.3,
        )
    )
    axis.text(
        0.08,
        0.74,
        body,
        transform=axis.transAxes,
        va="top",
        fontsize=12,
        family="monospace",
        linespacing=1.45,
    )


def render_walkthrough(
    instance: Mapping[str, Any], language: str, output: Path, digest: str
) -> None:
    text = TEXT[language]
    model, program = build_program(instance)
    figure = plt.figure(figsize=(17, 15))
    grid = figure.add_gridspec(3, 2)
    figure.subplots_adjust(
        left=0.05, right=0.97, bottom=0.08, top=0.92, hspace=0.3, wspace=0.16
    )
    figure.suptitle(text["title"], fontsize=21, fontweight="bold")

    body = (
        f"{text['ising']}\n\n"
        + text["model_summary"].format(
            variables=len(program.variables),
            couplings=len(program.quadratic),
            offset=program.offset,
        )
        + "\n\n"
        + " → ".join(name.replace("SUB-", "S") for name in program.variables)
    )
    _panel(figure.add_subplot(grid[0, 0]), text["step1"], body, color="#f8fafc")
    _panel(figure.add_subplot(grid[0, 1]), text["step2"], text["uniform"])
    _panel(figure.add_subplot(grid[1, 0]), text["step3"], text["cost"], color="#fff7ed")
    _panel(figure.add_subplot(grid[1, 1]), text["step4"], text["mixer"], color="#f0fdf4")
    _panel(figure.add_subplot(grid[2, 0]), text["step5"], text["measure"], color="#f5f3ff")
    _panel(figure.add_subplot(grid[2, 1]), text["step6"], text["optimize"], color="#fef2f2")

    figure.text(
        0.5,
        0.045,
        text["warning"],
        ha="center",
        fontsize=10.5,
        fontweight="bold",
        color="#b91c1c",
    )
    figure.text(
        0.5,
        0.018,
        f"{text['limitation']}  |  SHA-256: {digest[:12]}…",
        ha="center",
        fontsize=9,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        dpi=220,
        bbox_inches="tight",
        metadata={"Software": "power-core QAOA walkthrough"},
    )
    plt.close(figure)


def _gate(
    axis: Any,
    x: float,
    y: float,
    label: str,
    *,
    color: str,
    width: float = 0.48,
) -> None:
    axis.add_patch(
        FancyBboxPatch(
            (x - width / 2, y - 0.24),
            width,
            0.48,
            boxstyle="round,pad=0.02",
            facecolor=color,
            edgecolor="#334155",
            linewidth=1.1,
        )
    )
    axis.text(x, y, label, ha="center", va="center", fontsize=9, fontweight="bold")


def render_circuit(
    instance: Mapping[str, Any], language: str, output: Path, digest: str
) -> None:
    text = TEXT[language]
    _, program = build_program(instance)
    labels = [name.replace("SUB-", "S") for name in program.variables]
    y_values = list(reversed(range(len(labels))))

    figure, axis = plt.subplots(figsize=(17, 8.5))
    figure.subplots_adjust(left=0.08, right=0.97, bottom=0.2, top=0.82)
    figure.suptitle(text["circuit_title"], fontsize=21, fontweight="bold")
    axis.set_xlim(-0.5, 13.5)
    axis.set_ylim(-1.0, len(labels))
    axis.axis("off")

    for label, y in zip(labels, y_values, strict=True):
        axis.plot((0, 13), (y, y), color="#64748b", linewidth=1.2, zorder=0)
        axis.text(-0.25, y, f"{label} |0⟩", ha="right", va="center", fontsize=10)
        _gate(axis, 0.7, y, "H", color="#dbeafe")
        for layer in range(program.layers):
            base = 2.0 + layer * 4.6
            _gate(axis, base, y, f"RZ\nγ{layer + 1}", color="#ffedd5", width=0.62)
            _gate(axis, base + 2.1, y, f"RX\nβ{layer + 1}", color="#dcfce7", width=0.62)
        _gate(axis, 12.2, y, "M", color="#ede9fe")

    for layer in range(program.layers):
        base = 2.0 + layer * 4.6
        for index, (left, right, _) in enumerate(program.quadratic):
            left_y = y_values[program.variables.index(left)]
            right_y = y_values[program.variables.index(right)]
            x = base + 0.65 + (index % 3) * 0.22
            axis.plot((x, x), (left_y, right_y), color="#ea580c", linewidth=1.5)
            axis.scatter((x, x), (left_y, right_y), color="#ea580c", s=25, zorder=3)

    axis.text(0.7, len(labels) - 0.15, text["initialization"], ha="center", fontsize=10, fontweight="bold")
    for layer in range(program.layers):
        base = 2.0 + layer * 4.6
        axis.text(base + 0.55, len(labels) - 0.15, text["cost_layer"].format(k=layer + 1), ha="center", fontsize=10, fontweight="bold")
        axis.text(base + 2.1, len(labels) - 0.15, text["mixer_layer"].format(k=layer + 1), ha="center", fontsize=10, fontweight="bold")
        axis.add_patch(
            FancyBboxPatch(
                (base - 0.45, -0.55),
                3.2,
                len(labels) - 0.05,
                boxstyle="round,pad=0.03",
                fill=False,
                linestyle="--",
                edgecolor="#94a3b8",
                linewidth=1.1,
            )
        )
    axis.text(12.2, len(labels) - 0.15, text["measurement"], ha="center", fontsize=10, fontweight="bold")
    axis.text(5.35, -0.82, text["repeat"], ha="center", fontsize=10, fontweight="bold")
    figure.text(
        0.5,
        0.075,
        text["warning"],
        ha="center",
        fontsize=10,
        fontweight="bold",
        color="#b91c1c",
    )
    figure.text(0.76, 0.13, text["offset"], ha="center", fontsize=9.5, wrap=True)
    figure.text(
        0.5,
        0.025,
        f"{text['limitation']}  |  SHA-256: {digest[:12]}…",
        ha="center",
        fontsize=9,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        dpi=220,
        bbox_inches="tight",
        metadata={"Software": "power-core QAOA circuit diagram"},
    )
    plt.close(figure)


def _flow_box(
    axis: Any,
    center: tuple[float, float],
    text: str,
    *,
    color: str,
    width: float = 2.25,
    height: float = 0.82,
) -> None:
    x, y = center
    axis.add_patch(
        FancyBboxPatch(
            (x - width / 2, y - height / 2),
            width,
            height,
            boxstyle="round,pad=0.04",
            facecolor=color,
            edgecolor="#475569",
            linewidth=1.2,
        )
    )
    axis.text(x, y, text, ha="center", va="center", fontsize=9.5, fontweight="bold")


def _arrow(
    axis: Any,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    label: str | None = None,
    curve: float = 0.0,
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            linewidth=1.3,
            color="#475569",
            connectionstyle=f"arc3,rad={curve}",
        )
    )
    if label:
        axis.text(
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2 + 0.18,
            label,
            ha="center",
            fontsize=8.5,
            color="#334155",
        )


def render_optimization_loop(
    instance: Mapping[str, Any], language: str, output: Path, digest: str
) -> None:
    text = TEXT[language]
    build_program(instance)
    figure, axis = plt.subplots(figsize=(16, 10))
    figure.subplots_adjust(left=0.04, right=0.96, bottom=0.12, top=0.88)
    figure.suptitle(text["loop_title"], fontsize=21, fontweight="bold")
    axis.set_xlim(0, 14)
    axis.set_ylim(0, 9)
    axis.axis("off")

    boxes = [
        ((1.5, 7.6), text["ising_input"], "#f8fafc", 2.65),
        ((4.2, 7.6), text["program"], "#dbeafe", 2.2),
        ((7.0, 7.6), text["starts"], "#fef3c7", 2.7),
        ((10.2, 7.6), text["backend"], "#ede9fe", 2.85),
        ((10.2, 5.4), text["counts"], "#f5f3ff", 2.65),
        ((7.0, 5.4), text["expectation"], "#ffedd5", 2.7),
        ((4.0, 5.4), text["bfgs"], "#dcfce7", 2.75),
        ((4.0, 3.0), text["select"], "#fee2e2", 3.0),
        ((7.0, 3.0), text["final"], "#dbeafe", 2.35),
        ((10.2, 3.0), text["result"], "#dcfce7", 3.0),
    ]
    for center, label, color, width in boxes:
        _flow_box(axis, center, label, color=color, width=width)

    _arrow(axis, (2.65, 7.6), (3.05, 7.6))
    _arrow(axis, (5.35, 7.6), (5.8, 7.6))
    _arrow(axis, (8.2, 7.6), (9.0, 7.6))
    _arrow(axis, (10.2, 7.15), (10.2, 5.88))
    _arrow(axis, (9.05, 5.4), (8.15, 5.4))
    _arrow(axis, (5.85, 5.4), (5.15, 5.4))
    _arrow(axis, (4.0, 5.0), (6.75, 7.15), label=text["feedback"], curve=-0.26)
    _arrow(axis, (4.0, 4.95), (4.0, 3.48))
    _arrow(axis, (5.55, 3.0), (5.8, 3.0))
    _arrow(axis, (8.2, 3.0), (8.65, 3.0))

    axis.text(
        7.0,
        1.25,
        text["warning"],
        ha="center",
        fontsize=11,
        fontweight="bold",
        color="#b91c1c",
        bbox={"boxstyle": "round", "facecolor": "#fff7ed", "edgecolor": "#fdba74"},
    )
    figure.text(
        0.5,
        0.035,
        f"{text['limitation']}  |  SHA-256: {digest[:12]}…",
        ha="center",
        fontsize=9,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        dpi=220,
        bbox_inches="tight",
        metadata={"Software": "power-core QAOA optimization loop"},
    )
    plt.close(figure)


def write_readme(
    instance: Mapping[str, Any], language: str, output: Path, digest: str
) -> None:
    text = TEXT[language]
    _, program = build_program(instance)
    steps = "\n".join(
        f"{index}. {step}" for index, step in enumerate(text["steps"], start=1)
    )
    content = f"""# {text['readme_title']}

{text['intro']}

![{text['title']}](qaoa_walkthrough.png)

## {text['what']}

{steps}

![{text['circuit_title']}](qaoa_circuit_layers.png)

![{text['loop_title']}](qaoa_optimization_loop.png)

### Program represented

- **Qubits / variables:** {len(program.variables)}
- **Illustrated depth `p`:** {program.layers}
- **Ising local terms:** {len(program.linear)}
- **Ising pair couplings:** {len(program.quadratic)}
- **Ising offset:** {program.offset:.0f}
- **Input SHA-256:** `{digest}`

## {text['scope']}

> {text['scope_text']}

> {text['limitation']}

## {text['reproduce']}

```bash
python power-core/src/reports/generate_qaoa_walkthrough.py
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
        directory = output_root / language / "qaoa"
        walkthrough = directory / "qaoa_walkthrough.png"
        circuit = directory / "qaoa_circuit_layers.png"
        loop = directory / "qaoa_optimization_loop.png"
        readme = directory / "README.md"
        render_walkthrough(instance, language, walkthrough, digest)
        render_circuit(instance, language, circuit, digest)
        render_optimization_loop(instance, language, loop, digest)
        write_readme(instance, language, readme, digest)
        written.extend((walkthrough, circuit, loop, readme))
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
