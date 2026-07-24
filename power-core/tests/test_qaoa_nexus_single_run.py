"""Tests for the standalone single-run Nexus inspection script."""

from collections import Counter
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "qaoa_nexus_single_run.py"
SPEC = importlib.util.spec_from_file_location("qaoa_nexus_single_run", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
single_run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(single_run)


class FakeQsysResult:
    def collated_counts(self):
        return Counter({(("q1", "1"), ("q0", "0"), ("q2", "0")): 3})


class FakeBackendResult:
    def get_counts(self):
        return Counter({(1, 0, 1): 4, (0, 1, 0): 2})


def test_normalize_qsys_collated_counts_in_qubit_order() -> None:
    assert single_run.normalize_result_counts(FakeQsysResult()) == {"010": 3}


def test_normalize_pytket_counts() -> None:
    assert single_run.normalize_result_counts(FakeBackendResult()) == {"010": 2, "101": 4}


def test_build_program_compiles_with_installed_guppy() -> None:
    assert single_run.build_program(gamma=0.8, beta=0.4).compile() is not None


@pytest.mark.parametrize("arguments", [["--shots", "0"], ["--seed", "-1"], ["--gamma", "nan"]])
def test_parser_rejects_invalid_execution_arguments(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        single_run.parse_args(arguments)
