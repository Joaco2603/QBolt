"""Tests for the reproducible QUBO-to-Ising walkthrough."""

from __future__ import annotations

import importlib.util
from itertools import product
import json
from pathlib import Path
import sys
from typing import Any

import pytest


POWER_CORE = Path(__file__).parents[2]
SCRIPT = POWER_CORE / "src" / "reports" / "generate_ising_walkthrough.py"
INSTANCE = POWER_CORE / "artifacts" / "regional_instance.json"


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("generate_ising_walkthrough", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_fixture() -> dict[str, Any]:
    return json.loads(INSTANCE.read_text(encoding="utf-8"))


def test_qubo_and_ising_energies_match_for_every_assignment() -> None:
    module = load_module()
    instance = load_fixture()
    graph = module.build_graph(instance)
    qubo, ising = module.build_models(graph)

    energies = []
    for values in product((0, 1), repeat=len(qubo.decision_variables)):
        assignment = dict(zip(qubo.decision_variables, values, strict=True))
        qubo_energy = qubo.minimum_energy(assignment)
        ising_energy = ising.energy(ising.binary_to_spins(assignment))
        assert ising_energy == pytest.approx(qubo_energy)
        energies.append(ising_energy)

    assert len(energies) == 64
    assert min(energies) == pytest.approx(-1058.0)


def test_conversion_preserves_the_documented_offset_and_coefficients() -> None:
    module = load_module()
    graph = module.build_graph(load_fixture())
    qubo, ising = module.build_models(graph)

    assert qubo.offset == pytest.approx(0.0)
    assert ising.offset == pytest.approx(-529.0)
    assert ising.linear == {
        "SUB-01": 0.0,
        "SUB-07": 0.0,
        "SUB-15": 0.0,
        "SUB-18": 0.0,
        "SUB-29": 0.0,
        "SUB-47": 0.0,
    }
    assert ising.quadratic[("SUB-01", "SUB-07")] == pytest.approx(115.0)
    assert ising.quadratic[("SUB-15", "SUB-29")] == pytest.approx(69.0)


def test_generates_bilingual_documentation_and_three_figures(tmp_path: Path) -> None:
    module = load_module()

    written = module.generate_reports(INSTANCE, tmp_path)

    assert len(written) == 8
    for language in ("english", "spanish"):
        directory = tmp_path / language / "ising"
        walkthrough = directory / "ising_walkthrough.png"
        coefficients = directory / "ising_coefficients.png"
        energies = directory / "ising_energy_equivalence.png"
        readme = directory / "README.md"
        assert walkthrough.stat().st_size > 10_000
        assert coefficients.stat().st_size > 10_000
        assert energies.stat().st_size > 10_000
        documentation = readme.read_text(encoding="utf-8")
        assert "ising_walkthrough.png" in documentation
        assert "ising_coefficients.png" in documentation
        assert "ising_energy_equivalence.png" in documentation
        assert "64" in documentation
        assert "-1058" in documentation
