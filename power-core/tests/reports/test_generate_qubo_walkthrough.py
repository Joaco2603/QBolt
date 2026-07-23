"""Tests for the decoupled QUBO walkthrough report generator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pytest


POWER_CORE = Path(__file__).parents[2]
SCRIPT = POWER_CORE / "src" / "reports" / "generate_qubo_walkthrough.py"
INSTANCE = POWER_CORE / "artifacts" / "regional_instance.json"
SPEC = importlib.util.spec_from_file_location("generate_qubo_walkthrough", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def load_fixture() -> dict[str, Any]:
    return json.loads(INSTANCE.read_text(encoding="utf-8"))


def test_derived_qubo_matches_negative_cut_for_every_assignment() -> None:
    instance = load_fixture()
    graph = MODULE.build_graph(instance)
    nodes = tuple(node["id"] for node in instance["nodes"])
    coefficients = MODULE.derive_max_cut_qubo(graph, nodes)

    evaluations = MODULE.enumerate_and_verify(graph, coefficients)

    assert len(nodes) == 6
    assert len(evaluations) == 2 ** len(nodes) == 64
    assert min(item.energy for item in evaluations) == pytest.approx(-1058.0)
    assert max(item.cut_weight for item in evaluations) == pytest.approx(1058.0)


def test_symmetric_matrix_preserves_explicit_pair_coefficients() -> None:
    instance = load_fixture()
    graph = MODULE.build_graph(instance)
    nodes = tuple(node["id"] for node in instance["nodes"])
    coefficients = MODULE.derive_max_cut_qubo(graph, nodes)

    matrix = MODULE.symmetric_qubo_matrix(coefficients)
    pailas = nodes.index("SUB-01")
    liberia = nodes.index("SUB-07")

    assert coefficients.linear["SUB-07"] == pytest.approx(-460.0)
    assert coefficients.quadratic[("SUB-01", "SUB-07")] == pytest.approx(460.0)
    assert matrix[pailas][liberia] == pytest.approx(230.0)
    assert matrix[liberia][pailas] == pytest.approx(230.0)


def test_weighted_adjacency_matrix_preserves_direct_connections() -> None:
    instance = load_fixture()
    graph = MODULE.build_graph(instance)
    nodes = tuple(node["id"] for node in instance["nodes"])

    matrix = MODULE.weighted_adjacency_matrix(graph, nodes)
    pailas = nodes.index("SUB-01")
    liberia = nodes.index("SUB-07")
    canas = nodes.index("SUB-29")

    assert matrix[pailas][pailas] == 0.0
    assert matrix[pailas][liberia] == pytest.approx(230.0)
    assert matrix[liberia][pailas] == pytest.approx(230.0)
    assert matrix[pailas][canas] == 0.0


def test_reporter_remains_decoupled_from_optimizer_implementation() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "from src.optimizer" not in source
    assert "import src.optimizer" not in source
    assert "qubo_implementation" not in source


def test_generates_bilingual_documentation_and_figures(tmp_path: Path) -> None:
    written = MODULE.generate_reports(INSTANCE, tmp_path)

    assert len(written) == 8
    for language in ("english", "spanish"):
        figure = tmp_path / language / "qubo" / "qubo_walkthrough.png"
        adjacency = tmp_path / language / "qubo" / "qubo_adjacency_matrix.png"
        results = tmp_path / language / "qubo" / "qubo_partition_results.png"
        readme = tmp_path / language / "qubo" / "README.md"
        assert figure.stat().st_size > 10_000
        assert adjacency.stat().st_size > 10_000
        assert results.stat().st_size > 10_000
        documentation = readme.read_text(encoding="utf-8")
        assert "1058" in documentation
        assert "qubo_adjacency_matrix.png" in documentation
        assert "64" in documentation
        assert "| 1 | `SUB-01` | Pailas |" in documentation
        assert "| 0 | `SUB-07` | Liberia |" in documentation
        assert "**Nodes in this report:** 6" in documentation or "**Nodos en este reporte:** 6" in documentation
