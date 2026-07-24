"""Tests for the reproducible QAOA algorithm walkthrough."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pytest


POWER_CORE = Path(__file__).parents[2]
SCRIPT = POWER_CORE / "src" / "reports" / "generate_qaoa_walkthrough.py"
INSTANCE = POWER_CORE / "artifacts" / "regional_instance.json"


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("generate_qaoa_walkthrough", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_fixture() -> dict[str, Any]:
    return json.loads(INSTANCE.read_text(encoding="utf-8"))


def test_builds_backend_neutral_program_from_the_documented_instance() -> None:
    module = load_module()

    model, program = module.build_program(load_fixture(), layers=2)

    assert program.variables == model.variables
    assert len(program.variables) == 6
    assert program.offset == pytest.approx(-529.0)
    assert len(program.linear) == 6
    assert len(program.quadratic) == 5
    assert program.layers == 2


def test_report_generator_does_not_claim_or_execute_a_qaoa_benchmark() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert ".run(" not in source
    assert ".run_local(" not in source
    assert ".run_cloud(" not in source
    assert "backend.execute(" not in source


def test_generates_bilingual_documentation_and_three_figures(tmp_path: Path) -> None:
    module = load_module()

    written = module.generate_reports(INSTANCE, tmp_path)

    assert len(written) == 8
    for language in ("english", "spanish"):
        directory = tmp_path / language / "qaoa"
        walkthrough = directory / "qaoa_walkthrough.png"
        circuit = directory / "qaoa_circuit_layers.png"
        loop = directory / "qaoa_optimization_loop.png"
        readme = directory / "README.md"
        assert walkthrough.stat().st_size > 10_000
        assert circuit.stat().st_size > 10_000
        assert loop.stat().st_size > 10_000
        documentation = readme.read_text(encoding="utf-8")
        assert "qaoa_walkthrough.png" in documentation
        assert "qaoa_circuit_layers.png" in documentation
        assert "qaoa_optimization_loop.png" in documentation
        assert "five" in documentation.lower() or "cinco" in documentation.lower()
        assert "not a benchmark" in documentation.lower() or "no es un benchmark" in documentation.lower()
